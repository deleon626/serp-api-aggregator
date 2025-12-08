#!/usr/bin/env python3
"""
SERP Query Processor - Fetch Google SERP results for multiple queries.

Outputs NDJSON (one query result per line) to stdout for piping to deduplicator.

Output format matches Bright Data schema with deduplication metadata:
{
    "url": "...",
    "keyword": null,
    "general": {...},
    "related": [...],
    "pagination": [...],
    "organic": [...],  # deduplicated with best_position, avg_position, frequency, pages_seen
    "people_also_ask": [...],
    "navigation": [...],
    "language": null,
    "country": null,
    "page_html": null,
    "aio_text": null
}

Usage:
    # From stdin
    echo -e "query1\\nquery2" | python query_processor.py

    # From file
    python query_processor.py --file queries.txt

    # With options
    python query_processor.py --max-pages 20 --concurrency 30
"""

import asyncio
import aiohttp
import argparse
import json
import sys
from datetime import datetime

from config import DEFAULT_MAX_PAGES, DEFAULT_CONCURRENCY
from bright_data_client import fetch_all_pages


def log(message: str) -> None:
    """Log message to stderr (doesn't pollute stdout pipeline)."""
    print(message, file=sys.stderr, flush=True)


async def process_query(
    session: aiohttp.ClientSession,
    query: str,
    query_num: int,
    total_queries: int,
    max_pages: int,
    concurrency: int,
) -> dict:
    """Process a single query and return complete result structure."""
    log(f"[{query_num}/{total_queries}] Query: \"{query}\" - Fetching up to {max_pages} pages...")

    def progress_callback(page, total, count):
        status = f"{count} results" if count >= 0 else "error"
        log(f"  Page {page}/{total}: {status}")

    result = await fetch_all_pages(
        session=session,
        query=query,
        max_pages=max_pages,
        concurrency=concurrency,
        progress_callback=None,  # Disable per-page progress for cleaner output
    )

    organic_count = len(result.get("organic", []))
    related_count = len(result.get("related", []))
    paa_count = len(result.get("people_also_ask", []))

    log(f"[{query_num}/{total_queries}] Query: \"{query}\" - Done: {organic_count} organic, {related_count} related, {paa_count} PAA")
    return result


async def main(queries: list[str], max_pages: int, concurrency: int) -> None:
    """Process all queries and output NDJSON to stdout."""
    log(f"\n{'='*60}")
    log(f"SERP Query Processor")
    log(f"{'='*60}")
    log(f"Queries: {len(queries)}")
    log(f"Max pages per query: {max_pages}")
    log(f"Concurrency: {concurrency}")
    log(f"Timestamp: {datetime.now().isoformat()}")
    log(f"{'='*60}\n")

    total_organic = 0

    async with aiohttp.ClientSession() as session:
        for i, query in enumerate(queries, 1):
            query = query.strip()
            if not query:
                continue

            result = await process_query(
                session=session,
                query=query,
                query_num=i,
                total_queries=len(queries),
                max_pages=max_pages,
                concurrency=concurrency,
            )

            # Output entire query result as single NDJSON line
            print(json.dumps(result, ensure_ascii=False))

            total_organic += len(result.get("organic", []))

            # Brief pause between queries to avoid overwhelming the API
            if i < len(queries):
                await asyncio.sleep(1)

    log(f"\n{'='*60}")
    log(f"COMPLETE: {total_organic} total organic results from {len(queries)} queries")
    log(f"{'='*60}")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Fetch Google SERP results and output as NDJSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Single query from stdin
    echo "python tutorial" | python query_processor.py

    # Multiple queries from stdin
    echo -e "python tutorial\\nmachine learning" | python query_processor.py

    # Queries from file
    python query_processor.py --file queries.txt

    # With custom options
    python query_processor.py --max-pages 20 --concurrency 30 < queries.txt

    # Full pipeline
    echo "python tutorial" | python query_processor.py | python deduplicator.py
        """
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
    return parser.parse_args()


def read_queries(args: argparse.Namespace) -> list[str]:
    """Read queries from file or stdin."""
    if args.file:
        with open(args.file, "r") as f:
            return [line.strip() for line in f if line.strip()]
    else:
        # Read from stdin
        if sys.stdin.isatty():
            log("ERROR: No input provided. Pipe queries or use --file")
            log("Usage: echo 'query' | python query_processor.py")
            sys.exit(1)
        return [line.strip() for line in sys.stdin if line.strip()]


if __name__ == "__main__":
    args = parse_args()
    queries = read_queries(args)

    if not queries:
        log("ERROR: No queries provided")
        sys.exit(1)

    asyncio.run(main(queries, args.max_pages, args.concurrency))
