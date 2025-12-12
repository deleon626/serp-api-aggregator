#!/usr/bin/env python3
"""SERP Aggregator Test Suite - Uses refactored serp library."""

import asyncio
import argparse
import time
from dataclasses import dataclass
from datetime import datetime

import serp
from serp import SerpAggregator


@dataclass
class TestResult:
    name: str
    passed: bool
    duration: float
    message: str = ""


# ============================================================================
# BASIC TESTS
# ============================================================================

async def test_basic() -> list[TestResult]:
    """Basic search functionality."""
    results = []

    # Test 1: Single search with defaults
    async with SerpAggregator() as client:
        start = time.time()
        result = await client.search("python tutorial", max_pages=3, use_cache=False)
        duration = time.time() - start

        passed = result.organic_count > 0 and not result.has_errors
        results.append(TestResult(
            name="Single search (3 pages)",
            passed=passed,
            duration=duration,
            message=f"{result.organic_count} results, {result.pages_fetched} pages"
        ))

    # Test 2: Search with localization
    async with SerpAggregator() as client:
        start = time.time()
        result = await client.search("news", max_pages=1, country="uk", language="en", use_cache=False)
        duration = time.time() - start

        passed = result.organic_count > 0
        results.append(TestResult(
            name="Search with country=uk",
            passed=passed,
            duration=duration,
            message=f"{result.organic_count} results"
        ))

    # Test 3: Result structure validation
    async with SerpAggregator() as client:
        result = await client.search("test", max_pages=1, use_cache=False)

        if result.organic:
            item = result.organic[0]
            has_fields = all([
                hasattr(item, 'link'),
                hasattr(item, 'title'),
                hasattr(item, 'best_position'),
                hasattr(item, 'frequency'),
            ])
            results.append(TestResult(
                name="OrganicResult fields",
                passed=has_fields,
                duration=0,
                message="All required fields present" if has_fields else "Missing fields"
            ))

    return results


# ============================================================================
# BATCH TESTS
# ============================================================================

async def test_batch() -> list[TestResult]:
    """Batch and parallel search tests."""
    results = []
    queries = ["python", "javascript", "rust"]

    # Test 1: Sequential batch
    async with SerpAggregator() as client:
        start = time.time()
        batch = await client.search_batch(queries, max_pages=2, use_cache=False)
        duration = time.time() - start

        passed = batch.success_count == len(queries)
        results.append(TestResult(
            name=f"search_batch ({len(queries)} queries)",
            passed=passed,
            duration=duration,
            message=f"{batch.total_organic} total results"
        ))

    # Test 2: Parallel batch
    async with SerpAggregator() as client:
        start = time.time()
        batch = await client.search_parallel(queries, max_pages=2, max_parallel_queries=3, use_cache=False)
        duration = time.time() - start

        passed = batch.success_count == len(queries)
        results.append(TestResult(
            name=f"search_parallel ({len(queries)} queries)",
            passed=passed,
            duration=duration,
            message=f"{batch.total_organic} total results"
        ))

    return results


# ============================================================================
# PAGINATION TESTS
# ============================================================================

async def test_pagination() -> list[TestResult]:
    """Pagination depth discovery."""
    results = []

    async with SerpAggregator() as client:
        start = time.time()
        result = await client.search(
            "machine learning tutorial",
            max_pages=30,
            use_cache=False
        )
        duration = time.time() - start

        passed = result.pages_fetched >= 15
        results.append(TestResult(
            name="Max pagination depth",
            passed=passed,
            duration=duration,
            message=f"{result.pages_fetched} pages, {result.organic_count} results"
        ))

    return results


# ============================================================================
# CONCURRENCY TESTS
# ============================================================================

async def test_concurrency() -> list[TestResult]:
    """Throughput and concurrency tests."""
    results = []

    # Test 1: Sequential baseline
    queries = [f"test query {i}" for i in range(5)]

    async with SerpAggregator() as client:
        start = time.time()
        for q in queries:
            await client.search(q, max_pages=1, use_cache=False)
        duration = time.time() - start

        throughput = len(queries) / duration
        results.append(TestResult(
            name="Sequential (5 queries)",
            passed=True,
            duration=duration,
            message=f"{throughput:.2f} queries/sec"
        ))

    # Test 2: Parallel
    queries = [f"concurrent test {i}" for i in range(10)]

    async with SerpAggregator() as client:
        start = time.time()
        batch = await client.search_parallel(queries, max_pages=1, max_parallel_queries=10, use_cache=False)
        duration = time.time() - start

        throughput = batch.success_count / duration
        passed = batch.success_count >= 8
        results.append(TestResult(
            name="Parallel (10 queries)",
            passed=passed,
            duration=duration,
            message=f"{throughput:.2f} queries/sec, {batch.success_count}/{len(queries)} success"
        ))

    return results


# ============================================================================
# CONSISTENCY TESTS
# ============================================================================

async def test_consistency() -> list[TestResult]:
    """Result consistency between duplicate requests."""
    results = []

    async with SerpAggregator() as client:
        query = "what is machine learning"

        result1 = await client.search(query, max_pages=1, use_cache=False)
        await asyncio.sleep(2)
        result2 = await client.search(query, max_pages=1, use_cache=False)

        domains1 = [r.link.split('/')[2] if '/' in r.link else r.link for r in result1.organic[:5]]
        domains2 = [r.link.split('/')[2] if '/' in r.link else r.link for r in result2.organic[:5]]

        matches = sum(1 for d1, d2 in zip(domains1, domains2) if d1 == d2)
        consistency = matches / min(len(domains1), len(domains2), 5) * 100 if domains1 else 0

        passed = consistency >= 50
        results.append(TestResult(
            name="Page 1 consistency",
            passed=passed,
            duration=0,
            message=f"{consistency:.0f}% position match (top 5)"
        ))

    return results


# ============================================================================
# MAIN
# ============================================================================

def print_results(category: str, results: list[TestResult]):
    print(f"\n{category.upper()}")
    print("-" * 60)
    for r in results:
        status = "[PASS]" if r.passed else "[FAIL]"
        print(f"  {status} {r.name} ({r.duration:.1f}s)")
        if r.message:
            print(f"         {r.message}")


async def main():
    parser = argparse.ArgumentParser(description="SERP Aggregator Test Suite")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--basic", action="store_true", help="Basic search tests")
    parser.add_argument("--batch", action="store_true", help="Batch/parallel tests")
    parser.add_argument("--pagination", action="store_true", help="Pagination tests")
    parser.add_argument("--concurrency", action="store_true", help="Concurrency tests")
    parser.add_argument("--consistency", action="store_true", help="Consistency tests")
    parser.add_argument("--list", action="store_true", help="List test categories")
    args = parser.parse_args()

    if args.list:
        print("Available test categories:")
        print("  --basic        Basic search functionality")
        print("  --batch        Batch and parallel search")
        print("  --pagination   Max pagination depth")
        print("  --concurrency  Throughput measurements")
        print("  --consistency  Result stability")
        print("  --all          Run all tests")
        return

    print("=" * 60)
    print("SERP AGGREGATOR TEST SUITE")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Version: {serp.__version__}")
    print("=" * 60)

    all_results = []
    run_all = args.all or not any([args.basic, args.batch, args.pagination, args.concurrency, args.consistency])

    if run_all or args.basic:
        results = await test_basic()
        print_results("Basic Tests", results)
        all_results.extend(results)

    if run_all or args.batch:
        results = await test_batch()
        print_results("Batch Tests", results)
        all_results.extend(results)

    if run_all or args.pagination:
        results = await test_pagination()
        print_results("Pagination Tests", results)
        all_results.extend(results)

    if run_all or args.concurrency:
        results = await test_concurrency()
        print_results("Concurrency Tests", results)
        all_results.extend(results)

    if run_all or args.consistency:
        results = await test_consistency()
        print_results("Consistency Tests", results)
        all_results.extend(results)

    passed = sum(1 for r in all_results if r.passed)
    total = len(all_results)
    total_time = sum(r.duration for r in all_results)

    print("\n" + "=" * 60)
    print(f"SUMMARY: {passed}/{total} passed ({passed/total*100:.1f}%)")
    print(f"Total time: {total_time:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
