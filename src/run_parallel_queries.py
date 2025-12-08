#!/usr/bin/env python3
"""
Parallel Query Runner - Execute multiple SERP queries in parallel with timing.

Runs queries concurrently and measures execution time for each query
as well as total wall-clock time.

Usage:
    # Run with default queries
    python run_parallel_queries.py

    # Custom queries
    python run_parallel_queries.py --queries "python tutorial" "machine learning"

    # From file
    python run_parallel_queries.py --file queries.txt

    # With options
    python run_parallel_queries.py --max-pages 10 --concurrency 30
"""

import asyncio
import aiohttp
import argparse
import json
import sys
import time
from datetime import datetime
from typing import Optional

from config import DEFAULT_MAX_PAGES, DEFAULT_CONCURRENCY
from bright_data_client import fetch_all_pages


def log(message: str) -> None:
    """Log message to stderr."""
    print(message, file=sys.stderr, flush=True)


async def process_single_query(
    session: aiohttp.ClientSession,
    query: str,
    max_pages: int,
    concurrency: int,
) -> dict:
    """
    Process a single query and return results with timing.

    Returns:
        dict with query, results, timing info
    """
    start_time = time.time()

    results = await fetch_all_pages(
        session=session,
        query=query,
        max_pages=max_pages,
        concurrency=concurrency,
    )

    elapsed = time.time() - start_time

    return {
        "query": query,
        "results": results,
        "result_count": len(results),
        "elapsed_seconds": round(elapsed, 2),
    }


async def run_queries_parallel(
    queries: list[str],
    max_pages: int,
    concurrency: int,
) -> dict:
    """
    Run multiple queries in parallel and collect timing metrics.
    """
    log(f"\n{'='*70}")
    log("PARALLEL QUERY RUNNER")
    log(f"{'='*70}")
    log(f"Queries: {len(queries)}")
    log(f"Max pages per query: {max_pages}")
    log(f"Concurrency per query: {concurrency}")
    log(f"Timestamp: {datetime.now().isoformat()}")
    log(f"{'='*70}\n")

    total_start = time.time()

    async with aiohttp.ClientSession() as session:
        # Create tasks for all queries
        tasks = [
            process_single_query(session, query.strip(), max_pages, concurrency)
            for query in queries if query.strip()
        ]

        log(f"Launching {len(tasks)} queries in parallel...")

        # Run all queries concurrently
        query_results = await asyncio.gather(*tasks, return_exceptions=True)

    total_elapsed = time.time() - total_start

    # Process results
    successful = []
    failed = []

    for result in query_results:
        if isinstance(result, Exception):
            failed.append({"error": str(result)})
        else:
            successful.append(result)

    # Print per-query timing
    log(f"\n{'='*70}")
    log("QUERY TIMING RESULTS")
    log(f"{'='*70}")
    log(f"{'Query':<40} {'Results':<10} {'Time (s)':<10}")
    log("-" * 70)

    total_results = 0
    for r in successful:
        log(f"{r['query'][:39]:<40} {r['result_count']:<10} {r['elapsed_seconds']:<10}")
        total_results += r["result_count"]

    for f in failed:
        log(f"FAILED: {f['error'][:60]}")

    log("-" * 70)
    log(f"{'TOTAL':<40} {total_results:<10} {round(total_elapsed, 2):<10}")
    log(f"{'='*70}\n")

    # Calculate metrics
    if successful:
        query_times = [r["elapsed_seconds"] for r in successful]
        metrics = {
            "min_query_time": min(query_times),
            "max_query_time": max(query_times),
            "avg_query_time": round(sum(query_times) / len(query_times), 2),
            "total_wall_time": round(total_elapsed, 2),
            "parallelism_speedup": round(sum(query_times) / total_elapsed, 2) if total_elapsed > 0 else 0,
        }
    else:
        metrics = {}

    log("PERFORMANCE METRICS:")
    log(f"  Total wall-clock time: {round(total_elapsed, 2)}s")
    if metrics:
        log(f"  Sum of individual query times: {round(sum(query_times), 2)}s")
        log(f"  Parallelism speedup: {metrics['parallelism_speedup']}x")
        log(f"  Min query time: {metrics['min_query_time']}s")
        log(f"  Max query time: {metrics['max_query_time']}s")
        log(f"  Avg query time: {metrics['avg_query_time']}s")
    log(f"{'='*70}\n")

    return {
        "timestamp": datetime.now().isoformat(),
        "config": {
            "queries": queries,
            "max_pages": max_pages,
            "concurrency": concurrency,
        },
        "timing": {
            "total_wall_time_seconds": round(total_elapsed, 2),
            "total_results": total_results,
            **metrics,
        },
        "queries": successful,
        "errors": failed if failed else None,
    }


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run SERP queries in parallel with timing metrics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Default test queries
    python run_parallel_queries.py

    # Custom queries
    python run_parallel_queries.py --queries "python tutorial" "machine learning"

    # From file
    python run_parallel_queries.py --file queries.txt

    # Limit pages for faster testing
    python run_parallel_queries.py --max-pages 5

    # Output JSON results
    python run_parallel_queries.py 2>/dev/null > results.json
        """
    )
    parser.add_argument(
        "--queries", "-q",
        nargs="+",
        help="Queries to run (space-separated)",
    )
    parser.add_argument(
        "--file", "-f",
        type=str,
        help="File containing queries (one per line)",
    )
    parser.add_argument(
        "--max-pages", "-p",
        type=int,
        default=DEFAULT_MAX_PAGES,
        help=f"Maximum pages per query (default: {DEFAULT_MAX_PAGES})",
    )
    parser.add_argument(
        "--concurrency", "-c",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"Max concurrent requests (default: {DEFAULT_CONCURRENCY})",
    )
    parser.add_argument(
        "--output", "-o",
        choices=["json", "summary"],
        default="json",
        help="Output format (default: json)",
    )
    return parser.parse_args()


def get_queries(args: argparse.Namespace) -> list[str]:
    """Get queries from args, file, or defaults."""
    if args.queries:
        return args.queries
    elif args.file:
        with open(args.file, "r") as f:
            return [line.strip() for line in f if line.strip()]
    else:
        # Default test queries
        return [
            "python programming tutorial",
            "machine learning basics",
        ]


def main():
    args = parse_args()
    queries = get_queries(args)

    if not queries:
        log("ERROR: No queries provided")
        sys.exit(1)

    results = asyncio.run(run_queries_parallel(
        queries=queries,
        max_pages=args.max_pages,
        concurrency=args.concurrency,
    ))

    # Output results
    if args.output == "json":
        # Output full results as JSON to stdout
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        # Summary already printed to stderr
        pass


if __name__ == "__main__":
    main()
