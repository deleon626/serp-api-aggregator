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
) -> list[dict]:
    """
    Fetch all pages for a query concurrently.

    Stops after 3 consecutive empty pages.

    Args:
        session: aiohttp client session
        query: Search query string
        max_pages: Maximum pages to fetch
        concurrency: Maximum concurrent requests
        progress_callback: Optional callback(page, total, results_count)

    Returns:
        list: All organic results with page metadata
    """
    semaphore = asyncio.Semaphore(concurrency)
    all_results = []

    # Create tasks for all pages
    tasks = [
        fetch_page(session, query, page, semaphore)
        for page in range(1, max_pages + 1)
    ]

    # Process as they complete
    consecutive_empty = 0
    pages_with_results = {}

    for coro in asyncio.as_completed(tasks):
        page, response = await coro

        if "error" in response:
            print(f"  Page {page}: ERROR - {response['error']}", file=sys.stderr)
            consecutive_empty += 1
        else:
            organic = response.get("organic", [])
            pages_with_results[page] = len(organic)

            if organic:
                consecutive_empty = 0
                for i, result in enumerate(organic):
                    all_results.append({
                        "query": query,
                        "page": page,
                        "position": i + 1,
                        "global_rank": result.get("global_rank", (page - 1) * 10 + i + 1),
                        "url": result.get("link", ""),
                        "domain": extract_domain(result.get("link", "")),
                        "title": result.get("title", ""),
                        "description": result.get("description", ""),
                        "source": result.get("source", ""),
                        "display_link": result.get("display_link", ""),
                        "extensions": result.get("extensions", []),
                    })
            else:
                consecutive_empty += 1

        if progress_callback:
            progress_callback(page, max_pages, len(organic) if "error" not in response else -1)

        # Early termination after 3 consecutive empty pages
        # Only check after we have enough sequential pages
        if consecutive_empty >= 3:
            # Cancel remaining tasks
            for task in tasks:
                if not task.done():
                    task.cancel()
            break

    # Sort results by page and position
    all_results.sort(key=lambda x: (x["page"], x["position"]))

    return all_results
