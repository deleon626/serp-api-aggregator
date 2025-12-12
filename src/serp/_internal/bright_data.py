"""Bright Data SERP API client (internal implementation)."""

import asyncio
from urllib.parse import urlparse

import aiohttp

from ..exceptions import SerpAPIError, SerpRateLimitError, SerpTimeoutError
from ..models import (
    GeneralMetadata,
    OrganicResult,
    PaginationItem,
    SearchResult,
)
from ..progress import NullProgress, ProgressEvent, ProgressReporter
from ..rate_limiter import AdaptiveRateLimiter, NullRateLimiter, RateLimiter
from ..settings import SerpSettings


def extract_domain(url: str) -> str:
    """Extract domain from URL, removing www prefix."""
    try:
        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "")
    except Exception:
        return ""


async def make_serp_request(
    session: aiohttp.ClientSession,
    settings: SerpSettings,
    query: str,
    start: int = 0,
    rate_limiter: RateLimiter | None = None,
) -> dict:
    """
    Make a single SERP request with retry logic.

    Args:
        session: aiohttp client session
        settings: Configuration settings
        query: Search query string
        start: Pagination offset (0, 10, 20, ...)
        rate_limiter: Optional rate limiter

    Returns:
        dict: API response with organic results

    Raises:
        SerpAPIError: On API communication errors
        SerpTimeoutError: On timeout
        SerpRateLimitError: On rate limit (429)
    """
    if rate_limiter is None:
        rate_limiter = NullRateLimiter()

    # Build search URL
    base_params = {
        "gl": settings.default_country,
        "hl": settings.default_language,
        "brd_json": "1",
    }
    params = {**base_params, "q": query, "start": str(start)}
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"https://www.google.com/search?{query_string}"

    headers = {
        "Authorization": f"Bearer {settings.bright_data_api_key.get_secret_value()}",
        "Content-Type": "application/json",
    }
    body = {"zone": settings.bright_data_zone, "url": url, "format": "raw"}

    for attempt in range(settings.max_retries + 1):
        try:
            # Apply rate limiting
            await rate_limiter.acquire()

            # Step 1: Submit request
            async with session.post(
                f"{settings.api_base_url}/serp/req",
                headers=headers,
                json=body,
                timeout=aiohttp.ClientTimeout(total=settings.request_timeout),
            ) as response:
                if response.status == 429:
                    await rate_limiter.on_rate_limit()
                    raise SerpRateLimitError(
                        "Rate limit exceeded on submit",
                        status_code=429,
                    )

                data = await response.json()
                response_id = data.get("response_id")

                if not response_id:
                    await rate_limiter.on_error()
                    raise SerpAPIError(
                        "No response_id returned from API",
                        status_code=response.status,
                    )

            # Step 2: Poll for results
            for poll_num in range(settings.max_polls):
                await asyncio.sleep(settings.poll_interval)

                async with session.get(
                    f"{settings.api_base_url}/serp/get_result",
                    headers=headers,
                    params={"response_id": response_id},
                    timeout=aiohttp.ClientTimeout(total=settings.request_timeout),
                ) as poll_response:
                    if poll_response.status == 200:
                        await rate_limiter.on_success()
                        return await poll_response.json()

                    elif poll_response.status == 429:
                        await rate_limiter.on_rate_limit()
                        raise SerpRateLimitError(
                            "Rate limit exceeded during polling",
                            status_code=429,
                            response_id=response_id,
                        )

                    elif poll_response.status not in [102, 202]:
                        await rate_limiter.on_error()
                        raise SerpAPIError(
                            f"Unexpected status during polling: {poll_response.status}",
                            status_code=poll_response.status,
                            response_id=response_id,
                        )

            # Polling timeout
            await rate_limiter.on_error()
            raise SerpTimeoutError(
                f"Polling timeout after {settings.max_polls} attempts",
                response_id=response_id,
                elapsed_seconds=settings.poll_interval * settings.max_polls,
            )

        except asyncio.TimeoutError:
            await rate_limiter.on_error()
            if attempt < settings.max_retries:
                wait_time = settings.retry_backoff**attempt
                await asyncio.sleep(wait_time)
            else:
                raise SerpTimeoutError(
                    "Request timeout after all retries",
                    elapsed_seconds=settings.request_timeout,
                )

        except aiohttp.ClientError as e:
            await rate_limiter.on_error()
            if attempt < settings.max_retries:
                wait_time = settings.retry_backoff**attempt
                await asyncio.sleep(wait_time)
            else:
                raise SerpAPIError(f"Client error: {str(e)[:100]}")

        except (SerpAPIError, SerpTimeoutError, SerpRateLimitError):
            # Re-raise our own exceptions
            raise

        except Exception as e:
            await rate_limiter.on_error()
            raise SerpAPIError(f"Unexpected error: {str(e)[:100]}")

    raise SerpAPIError("All retries exhausted")


async def fetch_page(
    session: aiohttp.ClientSession,
    settings: SerpSettings,
    query: str,
    page: int,
    semaphore: asyncio.Semaphore,
    rate_limiter: RateLimiter | None = None,
) -> tuple[int, dict | None, str | None]:
    """
    Fetch a single page with semaphore control.

    Returns:
        tuple: (page_number, response_dict or None, error_message or None)
    """
    async with semaphore:
        start = (page - 1) * 10
        try:
            response = await make_serp_request(
                session=session,
                settings=settings,
                query=query,
                start=start,
                rate_limiter=rate_limiter,
            )
            return page, response, None
        except Exception as e:
            return page, None, str(e)


async def fetch_all_pages(
    session: aiohttp.ClientSession,
    settings: SerpSettings,
    query: str,
    max_pages: int | None = None,
    concurrency: int | None = None,
    progress: ProgressReporter | None = None,
    rate_limiter: RateLimiter | None = None,
    raw_collector: list[dict] | None = None,
) -> SearchResult:
    """
    Fetch all pages for a query concurrently with deduplication.

    Stops after consecutive_empty_limit empty pages.
    Returns SearchResult with deduplicated organic results.

    Args:
        session: aiohttp client session
        settings: Configuration settings
        query: Search query string
        max_pages: Maximum pages to fetch (default from settings)
        concurrency: Concurrent requests (default from settings)
        progress: Progress reporter
        rate_limiter: Rate limiter
        raw_collector: Optional list to collect raw API responses

    Returns:
        SearchResult with deduplicated organic results and metadata
    """
    if progress is None:
        progress = NullProgress()

    if rate_limiter is None:
        rate_limiter = AdaptiveRateLimiter(
            initial_rps=settings.rate_limit_rps,
        ) if settings.rate_limit_enabled else NullRateLimiter()

    max_pages = max_pages or settings.default_max_pages
    concurrency = concurrency or settings.default_concurrency

    progress.on_query_start(query, max_pages)

    semaphore = asyncio.Semaphore(concurrency)
    organic_by_url: dict[str, dict] = {}
    pagination_seen: set[str] = set()
    errors: list[str] = []
    first_response: dict | None = None
    consecutive_empty = 0
    pages_fetched = 0

    # Create tasks for all pages
    tasks = [
        asyncio.create_task(
            fetch_page(session, settings, query, page, semaphore, rate_limiter)
        )
        for page in range(1, max_pages + 1)
    ]

    # Process as they complete
    for coro in asyncio.as_completed(tasks):
        page, response, error = await coro
        pages_fetched += 1

        if error:
            errors.append(f"Page {page}: {error}")
            progress.on_error(query, error, page)
            consecutive_empty += 1

        elif response:
            # Collect raw response if collector provided
            if raw_collector is not None:
                raw_collector.append(response)

            # Capture first response metadata
            if first_response is None:
                first_response = response

            # Process organic results with deduplication
            organic = response.get("organic", [])

            if organic:
                consecutive_empty = 0
                for result in organic:
                    url = result.get("link", "")
                    if not url:
                        continue

                    rank = result.get("rank", 0)

                    if url not in organic_by_url:
                        organic_by_url[url] = {
                            "link": url,
                            "rank": rank,
                            "title": result.get("title", ""),
                            "description": result.get("description"),
                            "positions": [rank],
                            "pages": [page],
                        }
                    else:
                        organic_by_url[url]["positions"].append(rank)
                        organic_by_url[url]["pages"].append(page)
            else:
                consecutive_empty += 1

            # Collect pagination
            for pag in response.get("pagination", []):
                if isinstance(pag, dict):
                    pag_key = pag.get("page", "")
                    if pag_key and pag_key not in pagination_seen:
                        pagination_seen.add(pag_key)

            progress.on_page_complete(
                ProgressEvent(
                    query=query,
                    page=page,
                    total_pages=max_pages,
                    results_count=len(organic),
                    status="complete" if organic else "empty",
                )
            )

        # Early termination after consecutive empty pages
        if consecutive_empty >= settings.consecutive_empty_limit:
            for task in tasks:
                if not task.done():
                    task.cancel()
            break

    # Build organic results with deduplication metadata
    organic_results = []
    for url, data in organic_by_url.items():
        positions = data["positions"]
        pages = data["pages"]

        organic_results.append(
            OrganicResult(
                link=data["link"],
                title=data["title"],
                description=data["description"],
                rank=data["rank"],
                best_position=min(positions),
                avg_position=round(sum(positions) / len(positions), 2),
                frequency=len(positions),
                pages_seen=sorted(set(pages)),
            )
        )

    # Sort by best_position
    organic_results.sort(key=lambda x: x.best_position)

    # Build general metadata
    general_data = (first_response or {}).get("general", {})
    general = GeneralMetadata(
        query=general_data.get("query", query),
        datetime=general_data.get("datetime"),
        language=general_data.get("language"),
        location=general_data.get("location"),
        search_engine=general_data.get("search_engine", "google"),
        search_type=general_data.get("search_type", "text"),
        page_title=general_data.get("page_title"),
    )

    # Build pagination
    pagination = []
    for pag in (first_response or {}).get("pagination", []):
        if isinstance(pag, dict):
            pagination.append(
                PaginationItem(
                    link=pag.get("link", ""),
                    page=pag.get("page", ""),
                    page_html=pag.get("page_html"),
                )
            )
    pagination.sort(key=lambda x: int(x.page) if x.page.isdigit() else 0)

    result = SearchResult(
        url=first_response.get("url") if first_response else None,
        keyword=first_response.get("keyword") if first_response else None,
        general=general,
        organic=organic_results,
        related=first_response.get("related", []) if first_response else [],
        people_also_ask=first_response.get("people_also_ask", []) if first_response else [],
        pagination=pagination,
        navigation=first_response.get("navigation", []) if first_response else [],
        language=first_response.get("language") if first_response else None,
        country=first_response.get("country") if first_response else None,
        aio_text=first_response.get("aio_text") if first_response else None,
        pages_fetched=pages_fetched,
        errors=errors,
    )

    progress.on_query_complete(query, len(organic_results), 0.0)  # TODO: track elapsed

    return result
