"""Async Bright Data SERP API client."""

import asyncio
import aiohttp
import sys
from typing import Optional
from urllib.parse import urlparse

from config import (
    BRIGHT_DATA_API_KEY,
    BRIGHT_DATA_ZONE,
    API_BASE_URL,
    BASE_PARAMS,
    POLL_INTERVAL,
    MAX_POLLS,
    MAX_RETRIES,
    RETRY_BACKOFF,
)


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "")
    except Exception:
        return ""


async def make_serp_request(
    session: aiohttp.ClientSession,
    query: str,
    start: int = 0,
    retries: int = MAX_RETRIES,
) -> dict:
    """
    Make a single SERP request with retry logic.

    Args:
        session: aiohttp client session
        query: Search query string
        start: Pagination offset (0, 10, 20, ...)
        retries: Number of retry attempts

    Returns:
        dict: API response with organic results or error
    """
    params = {**BASE_PARAMS, "q": query, "start": str(start)}
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"https://www.google.com/search?{query_string}"

    headers = {
        "Authorization": f"Bearer {BRIGHT_DATA_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {"zone": BRIGHT_DATA_ZONE, "url": url, "format": "raw"}

    for attempt in range(retries):
        try:
            # Step 1: Submit request
            async with session.post(
                f"{API_BASE_URL}/serp/req",
                headers=headers,
                json=body,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                data = await response.json()
                response_id = data.get("response_id")

                if not response_id:
                    return {"error": "no_response_id", "data": data}

            # Step 2: Poll for results
            for _ in range(MAX_POLLS):
                await asyncio.sleep(POLL_INTERVAL)
                async with session.get(
                    f"{API_BASE_URL}/serp/get_result",
                    headers=headers,
                    params={"response_id": response_id},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as poll_response:
                    if poll_response.status == 200:
                        return await poll_response.json()
                    elif poll_response.status not in [102, 202]:
                        return {"error": f"http_{poll_response.status}"}

            return {"error": "polling_timeout"}

        except asyncio.TimeoutError:
            if attempt < retries - 1:
                wait_time = RETRY_BACKOFF ** attempt
                print(f"  Timeout, retrying in {wait_time}s...", file=sys.stderr)
                await asyncio.sleep(wait_time)
            else:
                return {"error": "timeout_exhausted"}

        except aiohttp.ClientError as e:
            if attempt < retries - 1:
                wait_time = RETRY_BACKOFF ** attempt
                print(f"  Error: {e}, retrying in {wait_time}s...", file=sys.stderr)
                await asyncio.sleep(wait_time)
            else:
                return {"error": str(e)[:100]}

        except Exception as e:
            return {"error": str(e)[:100]}

    return {"error": "retries_exhausted"}


async def fetch_page(
    session: aiohttp.ClientSession,
    query: str,
    page: int,
    semaphore: asyncio.Semaphore,
) -> tuple[int, dict]:
    """
    Fetch a single page with semaphore control.

    Returns:
        tuple: (page_number, response_dict)
    """
    async with semaphore:
        start = (page - 1) * 10
        response = await make_serp_request(session, query, start)
        return page, response


async def fetch_all_pages(
    session: aiohttp.ClientSession,
    query: str,
    max_pages: int,
    concurrency: int,
    progress_callback: Optional[callable] = None,
) -> dict:
    """
    Fetch all pages for a query concurrently.

    Stops after 3 consecutive empty pages.
    Returns complete Bright Data response structure with deduplicated organic results.

    Args:
        session: aiohttp client session
        query: Search query string
        max_pages: Maximum pages to fetch
        concurrency: Maximum concurrent requests
        progress_callback: Optional callback(page, total, results_count)

    Returns:
        dict: Complete response matching Bright Data schema with dedup metadata
        {
            "url": str,
            "keyword": None,
            "general": {...},
            "related": [...],
            "pagination": [...],
            "organic": [...],  # deduplicated with aggregation metadata
            "people_also_ask": [...],
            "navigation": [...],
            "language": None,
            "country": None,
            "page_html": None,
            "aio_text": None
        }
    """
    semaphore = asyncio.Semaphore(concurrency)

    # Initialize result structure matching Bright Data schema
    query_result = {
        "url": None,
        "keyword": None,
        "general": {},
        "related": [],
        "pagination": [],
        "organic": [],
        "people_also_ask": [],
        "navigation": [],
        "language": None,
        "country": None,
        "page_html": None,
        "aio_text": None,
    }

    # Track organic results for deduplication
    organic_by_url: dict[str, dict] = {}
    pagination_seen: set[str] = set()
    first_response_captured = False

    # Create tasks for all pages
    tasks = [
        fetch_page(session, query, page, semaphore)
        for page in range(1, max_pages + 1)
    ]

    # Process as they complete
    consecutive_empty = 0

    for coro in asyncio.as_completed(tasks):
        page, response = await coro

        if "error" in response:
            print(f"  Page {page}: ERROR - {response['error']}", file=sys.stderr)
            consecutive_empty += 1
        else:
            # Capture metadata from first successful response
            if not first_response_captured:
                first_response_captured = True
                query_result["url"] = response.get("url")
                query_result["keyword"] = response.get("keyword")
                query_result["related"] = response.get("related", [])
                query_result["people_also_ask"] = response.get("people_also_ask", [])
                query_result["navigation"] = response.get("navigation", [])
                query_result["language"] = response.get("language")
                query_result["country"] = response.get("country")
                query_result["aio_text"] = response.get("aio_text")

                # Capture general metadata and ensure query is set
                general = response.get("general", {})
                if not general.get("query"):
                    general["query"] = query
                query_result["general"] = general

            # Collect unique pagination links from all pages
            for pag in response.get("pagination", []):
                # Handle both dict and string formats
                if isinstance(pag, dict):
                    pag_key = pag.get("page", "")
                    if pag_key and pag_key not in pagination_seen:
                        pagination_seen.add(pag_key)
                        query_result["pagination"].append(pag)
                elif isinstance(pag, str) and pag not in pagination_seen:
                    pagination_seen.add(pag)
                    query_result["pagination"].append({"link": pag, "page": str(len(pagination_seen)), "page_html": None})

            # Aggregate organic results with deduplication
            organic = response.get("organic", [])

            if organic:
                consecutive_empty = 0
                for result in organic:
                    url = result.get("link", "")
                    if not url:
                        continue

                    rank = result.get("rank", 0)

                    if url not in organic_by_url:
                        # First occurrence - store full result
                        organic_by_url[url] = {
                            "link": url,
                            "rank": rank,
                            "title": result.get("title", ""),
                            "description": result.get("description"),
                            "url": result.get("url", ""),
                            "positions": [rank],
                            "pages": [page],
                        }
                    else:
                        # Already seen - track position and page
                        organic_by_url[url]["positions"].append(rank)
                        organic_by_url[url]["pages"].append(page)
            else:
                consecutive_empty += 1

        if progress_callback:
            count = len(response.get("organic", [])) if "error" not in response else -1
            progress_callback(page, max_pages, count)

        # Early termination after 3 consecutive empty pages
        if consecutive_empty >= 3:
            for task in tasks:
                if not task.done():
                    task.cancel()
            break

    # Build final organic array with deduplication metadata
    for url, data in organic_by_url.items():
        positions = data.pop("positions")
        pages = data.pop("pages")

        query_result["organic"].append({
            **data,
            "best_position": min(positions),
            "avg_position": round(sum(positions) / len(positions), 2),
            "frequency": len(positions),
            "pages_seen": sorted(set(pages)),
        })

    # Sort organic by best_position
    query_result["organic"].sort(key=lambda x: x["best_position"])

    # Sort pagination by page number
    query_result["pagination"].sort(key=lambda x: int(x.get("page", "0")))

    return query_result
