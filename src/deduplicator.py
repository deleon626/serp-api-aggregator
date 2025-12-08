#!/usr/bin/env python3
"""
SERP Results Deduplicator - Deduplicate organic results by URL.

Reads NDJSON from stdin (output of query_processor.py) and outputs
deduplicated results with aggregated metadata.

Modes:
- Per-query (default): Each query's results deduplicated separately across its pages
- Cross-query: All queries merged, URLs deduplicated across all queries

Usage:
    # Per-query deduplication (default)
    echo -e "query1\\nquery2" | python query_processor.py | python deduplicator.py

    # Cross-query deduplication
    python deduplicator.py --cross-query < results.ndjson

    # Full pipeline
    echo "python tutorial" | python query_processor.py | python deduplicator.py
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from statistics import mean
from typing import Any


def log(message: str) -> None:
    """Log message to stderr."""
    print(message, file=sys.stderr, flush=True)


def deduplicate_single_query(results: list[dict], query: str) -> list[dict]:
    """
    Deduplicate results for a single query across its pages.
    """
    url_data: dict[str, dict[str, Any]] = {}
    url_positions: dict[str, list[int]] = defaultdict(list)
    url_pages: dict[str, set[int]] = defaultdict(set)

    for result in results:
        url = result.get("url", "")
        if not url:
            continue

        # Store first occurrence data
        if url not in url_data:
            url_data[url] = {
                "url": url,
                "domain": result.get("domain", ""),
                "title": result.get("title", ""),
                "description": result.get("description", ""),
                "source": result.get("source", ""),
                "display_link": result.get("display_link", ""),
                "extensions": result.get("extensions", []),
            }

        position = result.get("position", result.get("global_rank", 0))
        if position:
            url_positions[url].append(position)

        page = result.get("page", 0)
        if page:
            url_pages[url].add(page)

    # Build deduplicated results for this query
    deduplicated = []
    for url, data in url_data.items():
        positions = url_positions[url]
        deduplicated.append({
            "query": query,
            **data,
            "best_position": min(positions) if positions else 0,
            "avg_position": round(mean(positions), 2) if positions else 0,
            "frequency": len(positions),
            "pages_seen": sorted(url_pages[url]),
        })

    return deduplicated


def deduplicate_per_query(lines: list[str]) -> dict[str, list[dict]]:
    """
    Deduplicate results per query - each query gets its own deduplicated set.

    Returns dict: {query_string: [deduplicated_results]}
    """
    # Group results by query
    query_results: dict[str, list[dict]] = defaultdict(list)
    processed = 0
    errors = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue

        try:
            result = json.loads(line)
        except json.JSONDecodeError:
            errors += 1
            continue

        query = result.get("query", "unknown")
        query_results[query].append(result)
        processed += 1

    log(f"  Processed: {processed} results, {errors} parse errors")
    log(f"  Queries found: {len(query_results)}")

    # Deduplicate each query separately
    deduplicated_by_query = {}
    for query, results in query_results.items():
        deduped = deduplicate_single_query(results, query)
        deduplicated_by_query[query] = deduped
        log(f"  Query '{query}': {len(results)} -> {len(deduped)} unique URLs")

    return deduplicated_by_query


def deduplicate_cross_query(lines: list[str]) -> list[dict]:
    """
    Deduplicate results across all queries - URLs merged globally.

    For each unique URL, tracks:
    - First occurrence data (title, description, source, etc.)
    - Best position (minimum position seen)
    - Average position across all occurrences
    - Frequency (how many times seen)
    - All queries it appeared for
    - All pages it appeared on
    """
    url_data: dict[str, dict[str, Any]] = {}
    url_positions: dict[str, list[int]] = defaultdict(list)
    url_queries: dict[str, set[str]] = defaultdict(set)
    url_pages: dict[str, set[int]] = defaultdict(set)

    processed = 0
    errors = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue

        try:
            result = json.loads(line)
        except json.JSONDecodeError:
            errors += 1
            continue

        url = result.get("url", "")
        if not url:
            continue

        processed += 1

        # Store first occurrence data
        if url not in url_data:
            url_data[url] = {
                "url": url,
                "domain": result.get("domain", ""),
                "title": result.get("title", ""),
                "description": result.get("description", ""),
                "source": result.get("source", ""),
                "display_link": result.get("display_link", ""),
                "extensions": result.get("extensions", []),
            }

        # Track aggregation data
        position = result.get("position", result.get("global_rank", 0))
        if position:
            url_positions[url].append(position)

        query = result.get("query", "")
        if query:
            url_queries[url].add(query)

        page = result.get("page", 0)
        if page:
            url_pages[url].add(page)

    log(f"  Processed: {processed} results, {errors} errors")
    log(f"  Unique URLs: {len(url_data)}")

    # Build final deduplicated results
    deduplicated = []
    for url, data in url_data.items():
        positions = url_positions[url]
        deduplicated.append({
            **data,
            "best_position": min(positions) if positions else 0,
            "avg_position": round(mean(positions), 2) if positions else 0,
            "frequency": len(positions),
            "queries": list(url_queries[url]),
            "pages_seen": sorted(url_pages[url]),
        })

    return deduplicated


def sort_results(results: list[dict], sort_by: str) -> list[dict]:
    """Sort results by specified field."""
    if sort_by == "frequency":
        return sorted(results, key=lambda x: -x["frequency"])
    elif sort_by == "avg_position":
        return sorted(results, key=lambda x: x["avg_position"])
    else:  # best_position (default)
        return sorted(results, key=lambda x: x["best_position"])


def filter_results(
    results: list[dict],
    min_frequency: int = 0,
    limit: int = 0,
) -> list[dict]:
    """Apply filters to results."""
    if min_frequency > 0:
        results = [r for r in results if r["frequency"] >= min_frequency]

    if limit > 0:
        results = results[:limit]

    return results


def output_json(results: list[dict]) -> None:
    """Output as JSON array."""
    print(json.dumps(results, indent=2, ensure_ascii=False))


def output_ndjson(results: list[dict]) -> None:
    """Output as NDJSON (one result per line)."""
    for result in results:
        print(json.dumps(result, ensure_ascii=False))


def output_csv(results: list[dict]) -> None:
    """Output as CSV."""
    if not results:
        return

    # Define column order
    columns = [
        "url", "domain", "title", "description", "source",
        "best_position", "avg_position", "frequency",
        "queries", "pages_seen",
    ]

    writer = csv.DictWriter(sys.stdout, fieldnames=columns, extrasaction='ignore')
    writer.writeheader()

    for result in results:
        row = {**result}
        # Convert lists to comma-separated strings for CSV
        row["queries"] = "; ".join(result.get("queries", []))
        row["pages_seen"] = ", ".join(map(str, result.get("pages_seen", [])))
        writer.writerow(row)


def main(args: argparse.Namespace) -> None:
    """Main deduplication pipeline."""
    log("\n" + "=" * 60)
    log("SERP Results Deduplicator")
    log("=" * 60)
    log(f"Mode: {'cross-query' if args.cross_query else 'per-query'}")

    # Read all lines from stdin
    if sys.stdin.isatty():
        log("ERROR: No input provided. Pipe NDJSON from query_processor.py")
        log("Usage: python query_processor.py | python deduplicator.py")
        sys.exit(1)

    lines = sys.stdin.readlines()
    log(f"Input: {len(lines)} lines")

    if args.cross_query:
        # Cross-query mode: merge all queries, dedupe globally
        results = deduplicate_cross_query(lines)
        results = sort_results(results, args.sort_by)

        if args.min_frequency > 0:
            before = len(results)
            results = filter_results(results, min_frequency=args.min_frequency)
            log(f"Filtered by min_frequency >= {args.min_frequency}: {before} -> {len(results)}")

        if args.limit > 0:
            results = filter_results(results, limit=args.limit)
            log(f"Limited to: {args.limit} results")

        log(f"Output: {len(results)} unique URLs")
        log("=" * 60 + "\n")

        # Output
        if args.format == "ndjson":
            output_ndjson(results)
        elif args.format == "csv":
            output_csv(results)
        else:
            output_json(results)

    else:
        # Per-query mode (default): dedupe within each query
        results_by_query = deduplicate_per_query(lines)

        # Apply sorting and filtering to each query's results
        output_data = {}
        total_urls = 0
        for query, results in results_by_query.items():
            results = sort_results(results, args.sort_by)

            if args.min_frequency > 0:
                results = filter_results(results, min_frequency=args.min_frequency)

            if args.limit > 0:
                results = filter_results(results, limit=args.limit)

            output_data[query] = results
            total_urls += len(results)

        log(f"Sorted by: {args.sort_by}")
        log(f"Output: {total_urls} unique URLs across {len(output_data)} queries")
        log("=" * 60 + "\n")

        # Output per-query results
        if args.format == "ndjson":
            for query, results in output_data.items():
                output_ndjson(results)
        elif args.format == "csv":
            # Flatten all queries for CSV
            all_results = []
            for results in output_data.values():
                all_results.extend(results)
            output_csv(all_results)
        else:
            # JSON: output as dict with query keys
            print(json.dumps(output_data, indent=2, ensure_ascii=False))


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Deduplicate SERP results by URL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Per-query deduplication (default)
    echo -e "query1\\nquery2" | python query_processor.py | python deduplicator.py

    # Cross-query deduplication (merge all queries)
    python deduplicator.py --cross-query < results.ndjson

    # Sort by frequency (most common URLs first)
    python deduplicator.py --sort-by frequency < results.ndjson

    # Top 100 results per query
    python deduplicator.py --limit 100 < results.ndjson

    # Output as CSV
    python deduplicator.py --format csv > results.csv

    # Full pipeline
    echo "python" | python query_processor.py | python deduplicator.py
        """
    )
    parser.add_argument(
        "--cross-query", "-x",
        action="store_true",
        help="Merge all queries and dedupe globally (default: per-query dedup)",
    )
    parser.add_argument(
        "--sort-by", "-s",
        choices=["best_position", "frequency", "avg_position"],
        default="best_position",
        help="Sort results by field (default: best_position)",
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=0,
        help="Limit to top N results (default: no limit)",
    )
    parser.add_argument(
        "--min-frequency", "-m",
        type=int,
        default=0,
        help="Filter by minimum frequency (default: no filter)",
    )
    parser.add_argument(
        "--format", "-o",
        choices=["json", "ndjson", "csv"],
        default="json",
        help="Output format (default: json)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args)
