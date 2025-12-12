#!/usr/bin/env python3
"""
Bright Data SERP API - Concurrency & Speed Test
================================================
Tests:
1. How fast are individual requests?
2. How many concurrent requests can we execute?
3. What's the throughput at different concurrency levels?
"""

import asyncio
import aiohttp
import time
from datetime import datetime

# Configuration
BRIGHT_DATA_API_KEY = "c69f9a87-ded2-4064-a901-5439af92bb54"
BRIGHT_DATA_ZONE = "serp_api1"
API_BASE_URL = "https://api.brightdata.com"

BASE_PARAMS = {"gl": "us", "hl": "en", "brd_json": "1"}


async def make_serp_request(session: aiohttp.ClientSession, query: str, request_id: int) -> dict:
    """Make a single SERP request and track timing."""

    start_time = time.time()
    submit_time = None
    first_poll_time = None
    result_time = None
    polls = 0

    params = {**BASE_PARAMS, "q": query}
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"https://www.google.com/search?{query_string}"

    headers = {
        "Authorization": f"Bearer {BRIGHT_DATA_API_KEY}",
        "Content-Type": "application/json"
    }

    body = {"zone": BRIGHT_DATA_ZONE, "url": url, "format": "raw"}

    try:
        # Step 1: Submit request
        async with session.post(
            f"{API_BASE_URL}/serp/req",
            headers=headers,
            json=body,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            data = await response.json()
            response_id = data.get("response_id")
            submit_time = time.time() - start_time

            if not response_id:
                return {
                    "request_id": request_id,
                    "status": "error",
                    "error": "No response_id",
                    "submit_time": submit_time
                }

        # Step 2: Poll for results
        for poll in range(20):
            polls += 1
            await asyncio.sleep(2)

            if first_poll_time is None:
                first_poll_time = time.time() - start_time

            async with session.get(
                f"{API_BASE_URL}/serp/get_result",
                headers=headers,
                params={"response_id": response_id},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as poll_response:
                if poll_response.status == 200:
                    result_time = time.time() - start_time
                    return {
                        "request_id": request_id,
                        "status": "success",
                        "submit_time": round(submit_time, 3),
                        "total_time": round(result_time, 3),
                        "polls": polls
                    }
                elif poll_response.status in [102, 202]:
                    continue
                else:
                    return {
                        "request_id": request_id,
                        "status": "error",
                        "error": f"HTTP {poll_response.status}",
                        "submit_time": submit_time,
                        "polls": polls
                    }

        return {
            "request_id": request_id,
            "status": "timeout",
            "submit_time": submit_time,
            "polls": polls
        }

    except Exception as e:
        return {
            "request_id": request_id,
            "status": "exception",
            "error": str(e),
            "total_time": time.time() - start_time
        }


async def test_sequential_speed(num_requests: int = 5):
    """Test sequential request speed."""

    print(f"\n{'='*70}")
    print("SEQUENTIAL SPEED TEST")
    print(f"{'='*70}")
    print(f"Requests: {num_requests} (one at a time)")
    print(f"{'='*70}\n")

    queries = [
        "python tutorial",
        "machine learning",
        "web development",
        "data science",
        "artificial intelligence"
    ]

    results = []

    async with aiohttp.ClientSession() as session:
        for i in range(num_requests):
            query = queries[i % len(queries)]
            print(f"Request {i+1}: '{query}'...", end=" ", flush=True)

            result = await make_serp_request(session, query, i+1)
            results.append(result)

            if result["status"] == "success":
                print(f"OK ({result['total_time']}s, {result['polls']} polls)")
            else:
                print(f"FAILED: {result.get('error', result['status'])}")

    # Summary
    successful = [r for r in results if r["status"] == "success"]
    if successful:
        times = [r["total_time"] for r in successful]
        print(f"\n--- Sequential Summary ---")
        print(f"Success: {len(successful)}/{num_requests}")
        print(f"Min time: {min(times):.2f}s")
        print(f"Max time: {max(times):.2f}s")
        print(f"Avg time: {sum(times)/len(times):.2f}s")
        print(f"Total time: {sum(times):.2f}s")

    return results


async def test_concurrent_speed(num_requests: int = 10):
    """Test concurrent request speed."""

    print(f"\n{'='*70}")
    print("CONCURRENT SPEED TEST")
    print(f"{'='*70}")
    print(f"Requests: {num_requests} (all at once)")
    print(f"{'='*70}\n")

    queries = [
        "python programming",
        "javascript frameworks",
        "react tutorial",
        "nodejs backend",
        "database design",
        "api development",
        "cloud computing",
        "devops practices",
        "software testing",
        "agile methodology",
        "microservices architecture",
        "docker containers",
        "kubernetes deployment",
        "ci cd pipeline",
        "code review",
        "git workflow",
        "system design",
        "algorithms",
        "data structures",
        "web security"
    ]

    start_time = time.time()

    async with aiohttp.ClientSession() as session:
        tasks = [
            make_serp_request(session, queries[i % len(queries)], i+1)
            for i in range(num_requests)
        ]

        print(f"Launching {num_requests} concurrent requests...")
        results = await asyncio.gather(*tasks)

    total_wall_time = time.time() - start_time

    # Analyze results
    successful = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] != "success"]

    print(f"\n--- Concurrent Results ---")
    for r in sorted(results, key=lambda x: x["request_id"]):
        status = "OK" if r["status"] == "success" else r["status"].upper()
        time_str = f"{r.get('total_time', 'N/A')}s" if r.get("total_time") else "N/A"
        print(f"  Request {r['request_id']:2d}: {status:8s} {time_str}")

    print(f"\n--- Concurrent Summary ---")
    print(f"Success: {len(successful)}/{num_requests}")
    print(f"Failed: {len(failed)}/{num_requests}")
    print(f"Wall clock time: {total_wall_time:.2f}s")

    if successful:
        times = [r["total_time"] for r in successful]
        print(f"Individual times: {min(times):.2f}s - {max(times):.2f}s")
        print(f"Avg individual time: {sum(times)/len(times):.2f}s")
        print(f"Throughput: {len(successful)/total_wall_time:.2f} requests/sec")

    if failed:
        print(f"\nFailed requests:")
        for r in failed:
            print(f"  Request {r['request_id']}: {r.get('error', r['status'])}")

    return results, total_wall_time


async def test_concurrency_limits():
    """Test different concurrency levels to find optimal throughput."""

    print(f"\n{'='*70}")
    print("CONCURRENCY LIMIT TEST")
    print(f"{'='*70}")
    print("Testing: 1, 2, 5, 10, 20, 50 concurrent requests")
    print(f"{'='*70}\n")

    concurrency_levels = [1, 2, 5, 10, 20, 50]
    results_summary = []

    for level in concurrency_levels:
        print(f"\n--- Testing {level} concurrent requests ---")

        queries = [f"test query {i}" for i in range(level)]

        start_time = time.time()

        async with aiohttp.ClientSession() as session:
            tasks = [
                make_serp_request(session, queries[i], i+1)
                for i in range(level)
            ]
            results = await asyncio.gather(*tasks)

        wall_time = time.time() - start_time
        successful = len([r for r in results if r["status"] == "success"])
        failed = len([r for r in results if r["status"] != "success"])

        throughput = successful / wall_time if wall_time > 0 else 0

        summary = {
            "concurrency": level,
            "successful": successful,
            "failed": failed,
            "wall_time": round(wall_time, 2),
            "throughput": round(throughput, 2)
        }
        results_summary.append(summary)

        print(f"  Success: {successful}/{level}")
        print(f"  Failed: {failed}/{level}")
        print(f"  Wall time: {wall_time:.2f}s")
        print(f"  Throughput: {throughput:.2f} req/s")

        # Add delay between tests
        if level < max(concurrency_levels):
            print("  Waiting 5s before next test...")
            await asyncio.sleep(5)

    # Final summary
    print(f"\n{'='*70}")
    print("CONCURRENCY TEST SUMMARY")
    print(f"{'='*70}")
    print(f"{'Concurrency':<12} {'Success':<10} {'Failed':<10} {'Time (s)':<10} {'Throughput'}")
    print("-" * 60)

    for s in results_summary:
        print(f"{s['concurrency']:<12} {s['successful']:<10} {s['failed']:<10} {s['wall_time']:<10} {s['throughput']} req/s")

    return results_summary


async def main():
    print(f"\n{'#'*70}")
    print("# BRIGHT DATA SERP API - CONCURRENCY & SPEED TEST")
    print(f"# Timestamp: {datetime.now().isoformat()}")
    print(f"{'#'*70}")

    # Test 1: Sequential speed
    await test_sequential_speed(5)

    # Small delay
    await asyncio.sleep(3)

    # Test 2: Concurrent speed (10 requests)
    await test_concurrent_speed(10)

    # Small delay
    await asyncio.sleep(3)

    # Test 3: Find concurrency limits
    await test_concurrency_limits()


if __name__ == "__main__":
    asyncio.run(main())
