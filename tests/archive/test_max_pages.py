#!/usr/bin/env python3
"""
Test maximum pagination depth for multiple queries.
Finds where results become empty for each query.
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime
from pathlib import Path

BRIGHT_DATA_API_KEY = "c69f9a87-ded2-4064-a901-5439af92bb54"
BRIGHT_DATA_ZONE = "serp_api1"
API_BASE_URL = "https://api.brightdata.com"

BASE_PARAMS = {"gl": "us", "hl": "en", "brd_json": "1"}

RESULTS_DIR = Path(__file__).parent / "results" / "max_pages"


async def make_serp_request(session, query, start):
    """Make a single SERP request."""
    params = {**BASE_PARAMS, "q": query, "start": str(start)}
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"https://www.google.com/search?{query_string}"

    headers = {
        "Authorization": f"Bearer {BRIGHT_DATA_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {"zone": BRIGHT_DATA_ZONE, "url": url, "format": "raw"}

    try:
        async with session.post(
            f"{API_BASE_URL}/serp/req",
            headers=headers,
            json=body,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            data = await response.json()
            response_id = data.get("response_id")
            if not response_id:
                return {"error": "no_response_id"}

        for _ in range(20):
            await asyncio.sleep(2)
            async with session.get(
                f"{API_BASE_URL}/serp/get_result",
                headers=headers,
                params={"response_id": response_id},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as pr:
                if pr.status == 200:
                    return json.loads(await pr.text())
                elif pr.status not in [102, 202]:
                    return {"error": f"http_{pr.status}"}
        return {"error": "timeout"}
    except Exception as e:
        return {"error": str(e)[:100]}


def count_organic_results(response):
    """Count organic results in response."""
    if "error" in response:
        return -1
    organic = response.get("organic", [])
    return len(organic)


async def test_query_pagination(session, query, max_pages=30):
    """Test pagination depth for a single query."""
    print(f"\n{'='*60}")
    print(f"Query: \"{query}\"")
    print(f"{'='*60}")

    results = []
    last_page_with_results = 0
    total_results = 0
    consecutive_empty = 0

    for page in range(1, max_pages + 1):
        start = (page - 1) * 10
        print(f"  Page {page:2d} (start={start:3d})... ", end="", flush=True)

        start_time = time.time()
        response = await make_serp_request(session, query, start)
        duration = time.time() - start_time

        count = count_organic_results(response)

        if count > 0:
            print(f"{count:2d} results ({duration:.1f}s)")
            last_page_with_results = page
            total_results += count
            consecutive_empty = 0
        elif count == 0:
            print(f" 0 results ({duration:.1f}s) - EMPTY")
            consecutive_empty += 1
        else:
            print(f"ERROR: {response.get('error', 'unknown')}")
            consecutive_empty += 1

        results.append({
            "page": page,
            "start": start,
            "count": count,
            "duration": round(duration, 2)
        })

        # Stop after 3 consecutive empty pages
        if consecutive_empty >= 3:
            print(f"  Stopping - 3 consecutive empty pages")
            break

    summary = {
        "query": query,
        "max_page": last_page_with_results,
        "max_offset": (last_page_with_results - 1) * 10 if last_page_with_results > 0 else 0,
        "total_results": total_results,
        "pages_tested": len(results),
        "pages": results
    }

    print(f"\n  SUMMARY: Max page {last_page_with_results}, Total results: {total_results}")

    return summary


async def main():
    queries = [
        "python programming tutorial",
        "machine learning",
        "best restaurants near me",
        "climate change effects",
        "iphone 15 review"
    ]

    print(f"\n{'#'*60}")
    print("# MAX PAGINATION DEPTH TEST - 5 QUERIES")
    print(f"# Timestamp: {datetime.now().isoformat()}")
    print(f"{'#'*60}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    all_results = []

    async with aiohttp.ClientSession() as session:
        for i, query in enumerate(queries, 1):
            result = await test_query_pagination(session, query, max_pages=30)
            all_results.append(result)

            # Save individual result
            safe_name = query.replace(" ", "_")[:30]
            with open(RESULTS_DIR / f"{i}_{safe_name}.json", "w") as f:
                json.dump(result, f, indent=2)

            # Brief pause between queries
            if i < len(queries):
                await asyncio.sleep(2)

    # Final summary
    print(f"\n{'='*60}")
    print("FINAL SUMMARY - MAX PAGINATION DEPTH")
    print(f"{'='*60}")
    print(f"{'Query':<35} {'Max Page':<10} {'Max Offset':<12} {'Total Results'}")
    print("-" * 70)

    for r in all_results:
        print(f"{r['query'][:34]:<35} {r['max_page']:<10} {r['max_offset']:<12} {r['total_results']}")

    # Calculate averages
    avg_max_page = sum(r['max_page'] for r in all_results) / len(all_results)
    avg_total = sum(r['total_results'] for r in all_results) / len(all_results)

    print("-" * 70)
    print(f"{'AVERAGE':<35} {avg_max_page:<10.1f} {(avg_max_page-1)*10:<12.0f} {avg_total:.0f}")

    # Save combined results
    with open(RESULTS_DIR / "summary.json", "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "queries": all_results,
            "averages": {
                "max_page": round(avg_max_page, 1),
                "total_results": round(avg_total)
            }
        }, f, indent=2)

    print(f"\nResults saved to: {RESULTS_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
