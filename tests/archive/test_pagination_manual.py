#!/usr/bin/env python3
"""
Google SERP Pagination & Consistency Test Script
================================================
Lightweight script for manual testing and comparison of:
1. Pagination depth (max pages with fresh results)
2. Result consistency (do duplicate requests return same results?)

Usage:
    # Run pagination depth test
    python test_pagination_manual.py --pagination

    # Run consistency test
    python test_pagination_manual.py --consistency

    # Run single page test
    python test_pagination_manual.py --page 3

    # Run all tests
    python test_pagination_manual.py --all
"""

import os
import json
import time
import asyncio
import aiohttp
import argparse
from datetime import datetime
from pathlib import Path

# ============================================================================
# Configuration
# ============================================================================

BRIGHT_DATA_API_KEY = "c69f9a87-ded2-4064-a901-5439af92bb54"
BRIGHT_DATA_ZONE = "serp_api1"
API_BASE_URL = "https://api.brightdata.com"

# Test parameters
BASE_PARAMS = {
    "gl": "us",
    "hl": "en",
    "brd_json": "1"
}

# Output directory
RESULTS_DIR = Path(__file__).parent / "results"


# ============================================================================
# API Functions
# ============================================================================

async def make_serp_request(session: aiohttp.ClientSession, query: str, start: int = 0) -> dict:
    """Make a single SERP request and return the full response."""

    # Build URL with parameters
    params = {**BASE_PARAMS, "q": query, "start": str(start)}
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"https://www.google.com/search?{query_string}"

    headers = {
        "Authorization": f"Bearer {BRIGHT_DATA_API_KEY}",
        "Content-Type": "application/json"
    }

    body = {
        "zone": BRIGHT_DATA_ZONE,
        "url": url,
        "format": "raw"
    }

    # Step 1: Submit request
    async with session.post(
        f"{API_BASE_URL}/serp/req",
        headers=headers,
        json=body,
        timeout=aiohttp.ClientTimeout(total=30)
    ) as response:
        data = await response.json()
        response_id = data.get("response_id")

        if not response_id:
            return {"error": "No response_id", "raw": data}

    # Step 2: Poll for results
    for poll in range(20):  # Max 40 seconds
        await asyncio.sleep(2)

        async with session.get(
            f"{API_BASE_URL}/serp/get_result",
            headers=headers,
            params={"response_id": response_id},
            timeout=aiohttp.ClientTimeout(total=30)
        ) as poll_response:
            if poll_response.status == 200:
                content = await poll_response.text()
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return {"error": "Invalid JSON", "raw": content[:500]}
            elif poll_response.status in [102, 202]:
                continue
            else:
                return {"error": f"Poll failed: HTTP {poll_response.status}"}

    return {"error": "Polling timeout"}


def extract_organic_results(response: dict) -> list:
    """Extract organic search results from response."""
    if "error" in response:
        return []

    organic = response.get("organic", [])
    if not organic:
        # Try alternative structures
        organic = response.get("results", [])

    results = []
    for i, item in enumerate(organic):
        results.append({
            "position": i + 1,
            "title": item.get("title", "")[:60],
            "url": item.get("link", item.get("url", ""))[:80],
            "domain": extract_domain(item.get("link", item.get("url", "")))
        })

    return results


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "")
    except:
        return url[:30]


# ============================================================================
# Pagination Depth Test
# ============================================================================

async def test_pagination_depth(query: str = "python programming tutorial", max_pages: int = 12):
    """Test pagination depth - find max pages with results."""

    print(f"\n{'='*70}")
    print("PAGINATION DEPTH TEST")
    print(f"{'='*70}")
    print(f"Query: {query}")
    print(f"Testing pages: 1-{max_pages}")
    print(f"{'='*70}\n")

    # Create results directory
    output_dir = RESULTS_DIR / "pagination_depth"
    output_dir.mkdir(parents=True, exist_ok=True)

    results_summary = []

    async with aiohttp.ClientSession() as session:
        for page in range(1, max_pages + 1):
            start = (page - 1) * 10
            print(f"Fetching page {page} (start={start})...", end=" ", flush=True)

            start_time = time.time()
            response = await make_serp_request(session, query, start)
            duration = time.time() - start_time

            # Save raw response
            filename = output_dir / f"page_{page:02d}_start_{start}.json"
            with open(filename, "w") as f:
                json.dump(response, f, indent=2)

            # Extract results
            organic = extract_organic_results(response)

            page_summary = {
                "page": page,
                "start": start,
                "results_count": len(organic),
                "duration_s": round(duration, 1),
                "first_url": organic[0]["url"] if organic else None,
                "last_url": organic[-1]["url"] if organic else None,
            }
            results_summary.append(page_summary)

            if organic:
                print(f"OK - {len(organic)} results ({duration:.1f}s)")
            else:
                print(f"EMPTY - 0 results ({duration:.1f}s)")
                if "error" in response:
                    print(f"         Error: {response['error']}")

    # Print summary
    print(f"\n{'='*70}")
    print("PAGINATION SUMMARY")
    print(f"{'='*70}")
    print(f"{'Page':<6} {'Start':<8} {'Results':<10} {'Time':<8} {'Status'}")
    print("-" * 70)

    for p in results_summary:
        status = "OK" if p["results_count"] > 0 else "EMPTY"
        print(f"{p['page']:<6} {p['start']:<8} {p['results_count']:<10} {p['duration_s']:<8} {status}")

    # Save summary
    summary_file = output_dir / "summary.json"
    with open(summary_file, "w") as f:
        json.dump({
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "pages": results_summary
        }, f, indent=2)

    print(f"\nResults saved to: {output_dir}")

    # Find max page with results
    max_page_with_results = 0
    for p in results_summary:
        if p["results_count"] > 0:
            max_page_with_results = p["page"]

    print(f"\nMAX PAGE WITH RESULTS: {max_page_with_results}")

    return results_summary


# ============================================================================
# Consistency Test
# ============================================================================

async def test_consistency(query: str = "what is machine learning", pages: list = [1, 3]):
    """Test result consistency by running duplicate requests."""

    print(f"\n{'='*70}")
    print("CONSISTENCY TEST")
    print(f"{'='*70}")
    print(f"Query: {query}")
    print(f"Testing pages: {pages}")
    print(f"Running each request TWICE for comparison")
    print(f"{'='*70}\n")

    # Create results directory
    output_dir = RESULTS_DIR / "consistency"
    output_dir.mkdir(parents=True, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        for page in pages:
            start = (page - 1) * 10
            print(f"\n--- Page {page} (start={start}) ---")

            # Request 1
            print(f"  Request 1...", end=" ", flush=True)
            response1 = await make_serp_request(session, query, start)
            organic1 = extract_organic_results(response1)
            print(f"OK - {len(organic1)} results")

            # Small delay
            await asyncio.sleep(3)

            # Request 2
            print(f"  Request 2...", end=" ", flush=True)
            response2 = await make_serp_request(session, query, start)
            organic2 = extract_organic_results(response2)
            print(f"OK - {len(organic2)} results")

            # Save responses
            with open(output_dir / f"page{page}_req1.json", "w") as f:
                json.dump(response1, f, indent=2)
            with open(output_dir / f"page{page}_req2.json", "w") as f:
                json.dump(response2, f, indent=2)

            # Print comparison
            print(f"\n  COMPARISON (Page {page}):")
            print(f"  {'Pos':<5} {'Request 1 Domain':<35} {'Request 2 Domain':<35} {'Match'}")
            print(f"  {'-'*85}")

            max_len = max(len(organic1), len(organic2))
            matches = 0

            for i in range(max_len):
                r1 = organic1[i] if i < len(organic1) else {"domain": "---", "url": ""}
                r2 = organic2[i] if i < len(organic2) else {"domain": "---", "url": ""}

                match = "YES" if r1["domain"] == r2["domain"] else "NO"
                if r1["domain"] == r2["domain"]:
                    matches += 1

                print(f"  {i+1:<5} {r1['domain']:<35} {r2['domain']:<35} {match}")

            consistency = (matches / max_len * 100) if max_len > 0 else 0
            print(f"\n  CONSISTENCY: {matches}/{max_len} = {consistency:.1f}%")

    print(f"\nRaw responses saved to: {output_dir}")


# ============================================================================
# Single Page Test
# ============================================================================

async def test_single_page(query: str, page: int):
    """Test a single page and display results."""

    start = (page - 1) * 10
    print(f"\n{'='*70}")
    print(f"SINGLE PAGE TEST - Page {page} (start={start})")
    print(f"{'='*70}")
    print(f"Query: {query}")
    print(f"{'='*70}\n")

    async with aiohttp.ClientSession() as session:
        print("Fetching...", end=" ", flush=True)
        response = await make_serp_request(session, query, start)
        organic = extract_organic_results(response)
        print(f"Done - {len(organic)} results\n")

        # Display results
        print(f"{'Pos':<5} {'Title':<50} {'Domain'}")
        print("-" * 90)

        for r in organic:
            print(f"{r['position']:<5} {r['title']:<50} {r['domain']}")

        # Save response
        output_dir = RESULTS_DIR / "single"
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = output_dir / f"page_{page}__{datetime.now().strftime('%H%M%S')}.json"
        with open(filename, "w") as f:
            json.dump(response, f, indent=2)

        print(f"\nRaw response saved to: {filename}")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Google SERP Pagination & Consistency Tests")
    parser.add_argument("--pagination", action="store_true", help="Run pagination depth test")
    parser.add_argument("--consistency", action="store_true", help="Run consistency test")
    parser.add_argument("--page", type=int, help="Test single page")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--query", type=str, default="python programming tutorial", help="Search query")
    parser.add_argument("--max-pages", type=int, default=12, help="Max pages for pagination test")

    args = parser.parse_args()

    if args.all:
        asyncio.run(test_pagination_depth(args.query, args.max_pages))
        asyncio.run(test_consistency())
    elif args.pagination:
        asyncio.run(test_pagination_depth(args.query, args.max_pages))
    elif args.consistency:
        asyncio.run(test_consistency(args.query))
    elif args.page:
        asyncio.run(test_single_page(args.query, args.page))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
