#!/usr/bin/env python3
"""
SERP Results Deduplicator - Process and optionally merge query results.

Reads NDJSON from stdin (output of query_processor.py) where each line
is a complete query result matching the Bright Data schema.

Input format (one JSON object per line):
{
    "url": "...",
    "general": {...},
    "related": [...],
    "pagination": [...],
    "organic": [...],  # already deduplicated with best_position, avg_position, frequency, pages_seen
    "people_also_ask": [...],
    "navigation": [...],
    ...
}

Modes:
- Per-query (default): Pass through each query result (already deduplicated by bright_data_client)
- Cross-query: Merge all queries, dedupe organic URLs across queries, aggregate related/PAA

Usage:
    # Per-query passthrough (default)
    echo -e "query1\\nquery2" | python query_processor.py | python deduplicator.py

    # Cross-query merge
    python deduplicator.py --cross-query < results.ndjson

    # Full pipeline
    echo "python tutorial" | python query_processor.py | python deduplicator.py
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from typing import Any


def log(message: str) -> None:
    """Log message to stderr."""
    print(message, file=sys.stderr, flush=True)


def parse_query_results(lines: list[str]) -> list[dict]:
    """
    Parse NDJSON lines into query result objects.

    Each line is a complete query result (Bright Data schema).
    """
    results = []
    errors = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue

        try:
            result = json.loads(line)
            results.append(result)
        except json.JSONDecodeError:
            errors += 1
            continue

    log(f"  Parsed: {len(results)} query results, {errors} parse errors")
    return results


def process_per_query(results: list[dict]) -> dict[str, dict]:
    """
    Per-query mode: pass through results (already deduplicated by bright_data_client).

    Returns dict: {query: query_result}
    """
    query_results = {}

    for result in results:
        query = result.get("general", {}).get("query", "unknown")
        query_results[query] = result

    log(f"  Queries: {len(query_results)}")
    for query, result in query_results.items():
        organic_count = len(result.get("organic", []))
        related_count = len(result.get("related", []))
        paa_count = len(result.get("people_also_ask", []))
        log(f"    '{query}': {organic_count} organic, {related_count} related, {paa_count} PAA")

    return query_results


def merge_cross_query(results: list[dict]) -> dict:
    """
    Cross-query mode: merge all queries into single result.

    - organic: dedupe by link, aggregate positions and queries
    - related: dedupe by text, track frequency across queries
    - people_also_ask: dedupe (first occurrence wins)
    - navigation: dedupe by title
    - general: merge datetime range, combine queries
    """
    merged = {
        "url": None,
        "keyword": None,
        "general": {
            "queries": [],
            "datetime_range": {"earliest": None, "latest": None},
            "language": None,
            "location": None,
            "search_engine": "google",
            "search_type": "text",
        },
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

    # Tracking structures for deduplication
    organic_by_url: dict[str, dict[str, Any]] = {}
    related_by_text: dict[str, dict[str, Any]] = {}
    paa_seen: set[str] = set()
    nav_by_title: dict[str, dict] = {}
    aio_texts: list[str] = []
    datetimes: list[str] = []

    for result in results:
        query = result.get("general", {}).get("query", "unknown")
        merged["general"]["queries"].append(query)

        # Capture first response metadata
        if merged["url"] is None:
            merged["url"] = result.get("url")
            merged["keyword"] = result.get("keyword")
            merged["language"] = result.get("language")
            merged["country"] = result.get("country")
            merged["general"]["language"] = result.get("general", {}).get("language")
            merged["general"]["location"] = result.get("general", {}).get("location")

        # Track datetime range
        dt = result.get("general", {}).get("datetime")
        if dt:
            datetimes.append(dt)

        # Capture AI overview text
        aio = result.get("aio_text")
        if aio and aio not in aio_texts:
            aio_texts.append(aio)

        # Merge organic results by URL
        for org in result.get("organic", []):
            url = org.get("link", "")
            if not url:
                continue

            if url not in organic_by_url:
                organic_by_url[url] = {
                    "link": url,
                    "rank": org.get("rank", 0),
                    "title": org.get("title", ""),
                    "description": org.get("description"),
                    "url": org.get("url", ""),
                    "positions": [org.get("best_position", 0)],
                    "pages": list(org.get("pages_seen", [])),
                    "queries": [query],
                    "frequency": org.get("frequency", 1),
                }
            else:
                organic_by_url[url]["positions"].append(org.get("best_position", 0))
                organic_by_url[url]["pages"].extend(org.get("pages_seen", []))
                organic_by_url[url]["queries"].append(query)
                organic_by_url[url]["frequency"] += org.get("frequency", 1)

        # Merge related searches by text
        for rel in result.get("related", []):
            text = rel.get("text", "")
            if not text:
                continue

            if text not in related_by_text:
                related_by_text[text] = {
                    "text": text,
                    "link": rel.get("link", ""),
                    "rank": rel.get("rank", 0),
                    "queries": [query],
                    "frequency": 1,
                }
            else:
                related_by_text[text]["queries"].append(query)
                related_by_text[text]["frequency"] += 1

        # Collect unique PAA questions (first occurrence wins)
        for paa in result.get("people_also_ask", []):
            # PAA are strings, use first 100 chars as key to avoid duplicates
            paa_key = paa[:100] if isinstance(paa, str) else str(paa)[:100]
            if paa_key not in paa_seen:
                paa_seen.add(paa_key)
                merged["people_also_ask"].append(paa)

        # Merge navigation by title
        for nav in result.get("navigation", []):
            title = nav.get("title", "")
            if title and title not in nav_by_title:
                nav_by_title[title] = nav

    # Build final organic array with cross-query aggregation
    for url, data in organic_by_url.items():
        positions = [p for p in data.pop("positions") if p > 0]
        pages = data.pop("pages")
        queries = list(set(data.pop("queries")))

        merged["organic"].append({
            "link": data["link"],
            "rank": data["rank"],
            "title": data["title"],
            "description": data["description"],
            "url": data["url"],
            "best_position": min(positions) if positions else 0,
            "avg_position": round(sum(positions) / len(positions), 2) if positions else 0,
            "frequency": data["frequency"],
            "pages_seen": sorted(set(pages)),
            "queries": queries,
        })

    # Sort organic by best_position
    merged["organic"].sort(key=lambda x: x["best_position"])

    # Build final related array with frequency
    for text, data in related_by_text.items():
        data["queries"] = list(set(data["queries"]))
        merged["related"].append(data)

    # Sort related by frequency (most common first)
    merged["related"].sort(key=lambda x: -x["frequency"])

    # Add navigation
    merged["navigation"] = list(nav_by_title.values())

    # Set datetime range
    if datetimes:
        merged["general"]["datetime_range"]["earliest"] = min(datetimes)
        merged["general"]["datetime_range"]["latest"] = max(datetimes)

    # Set AI overview (join multiple if present)
    if aio_texts:
        merged["aio_text"] = aio_texts[0] if len(aio_texts) == 1 else aio_texts

    log(f"  Merged {len(results)} queries:")
    log(f"    Organic: {len(merged['organic'])} unique URLs")
    log(f"    Related: {len(merged['related'])} unique searches")
    log(f"    PAA: {len(merged['people_also_ask'])} unique questions")
    log(f"    Navigation: {len(merged['navigation'])} tabs")

    return merged


def sort_organic(results: dict, sort_by: str) -> dict:
    """Sort organic results by specified field."""
    organic = results.get("organic", [])

    if sort_by == "frequency":
        organic = sorted(organic, key=lambda x: -x.get("frequency", 0))
    elif sort_by == "avg_position":
        organic = sorted(organic, key=lambda x: x.get("avg_position", 0))
    else:  # best_position (default)
        organic = sorted(organic, key=lambda x: x.get("best_position", 0))

    results["organic"] = organic
    return results


def filter_organic(results: dict, min_frequency: int = 0, limit: int = 0) -> dict:
    """Apply filters to organic results."""
    organic = results.get("organic", [])

    if min_frequency > 0:
        organic = [r for r in organic if r.get("frequency", 0) >= min_frequency]

    if limit > 0:
        organic = organic[:limit]

    results["organic"] = organic
    return results


def output_json(data: Any) -> None:
    """Output as pretty JSON."""
    print(json.dumps(data, indent=2, ensure_ascii=False))


def output_ndjson(data: Any) -> None:
    """Output as NDJSON."""
    if isinstance(data, dict):
        # Check if it's a query-keyed dict or single result
        if "organic" in data:
            # Single result
            print(json.dumps(data, ensure_ascii=False))
        else:
            # Query-keyed dict
            for query, result in data.items():
                print(json.dumps(result, ensure_ascii=False))
    elif isinstance(data, list):
        for item in data:
            print(json.dumps(item, ensure_ascii=False))


def output_csv(data: Any) -> None:
    """Output organic results as CSV."""
    # Extract organic results
    if isinstance(data, dict):
        if "organic" in data:
            organic = data.get("organic", [])
        else:
            # Query-keyed dict - flatten all organic
            organic = []
            for result in data.values():
                for org in result.get("organic", []):
                    org["query"] = result.get("general", {}).get("query", "")
                    organic.append(org)
    else:
        organic = []

    if not organic:
        return

    # Define column order matching Bright Data schema
    columns = [
        "link", "rank", "title", "description",
        "best_position", "avg_position", "frequency", "pages_seen",
        "queries",
    ]

    writer = csv.DictWriter(sys.stdout, fieldnames=columns, extrasaction='ignore')
    writer.writeheader()

    for result in organic:
        row = {**result}
        # Convert lists to comma-separated strings for CSV
        if "pages_seen" in row:
            row["pages_seen"] = ", ".join(map(str, row.get("pages_seen", [])))
        if "queries" in row:
            row["queries"] = "; ".join(row.get("queries", []))
        writer.writerow(row)


def main(args: argparse.Namespace) -> None:
    """Main processing pipeline."""
    log("\n" + "=" * 60)
    log("SERP Results Processor")
    log("=" * 60)
    log(f"Mode: {'cross-query merge' if args.cross_query else 'per-query passthrough'}")

    # Read all lines from stdin
    if sys.stdin.isatty():
        log("ERROR: No input provided. Pipe NDJSON from query_processor.py")
        log("Usage: python query_processor.py | python deduplicator.py")
        sys.exit(1)

    lines = sys.stdin.readlines()
    log(f"Input: {len(lines)} lines")

    # Parse query results
    results = parse_query_results(lines)

    if not results:
        log("ERROR: No valid query results found")
        sys.exit(1)

    if args.cross_query:
        # Cross-query mode: merge all queries
        merged = merge_cross_query(results)
        merged = sort_organic(merged, args.sort_by)

        if args.min_frequency > 0:
            before = len(merged.get("organic", []))
            merged = filter_organic(merged, min_frequency=args.min_frequency)
            after = len(merged.get("organic", []))
            log(f"Filtered by min_frequency >= {args.min_frequency}: {before} -> {after}")

        if args.limit > 0:
            merged = filter_organic(merged, limit=args.limit)
            log(f"Limited to: {args.limit} organic results")

        log(f"Output: {len(merged.get('organic', []))} organic URLs")
        log("=" * 60 + "\n")

        # Output
        if args.format == "ndjson":
            output_ndjson(merged)
        elif args.format == "csv":
            output_csv(merged)
        else:
            output_json(merged)

    else:
        # Per-query mode: passthrough (already deduplicated)
        query_results = process_per_query(results)

        # Apply sorting and filtering to each query's organic results
        total_organic = 0
        for query, result in query_results.items():
            result = sort_organic(result, args.sort_by)

            if args.min_frequency > 0:
                result = filter_organic(result, min_frequency=args.min_frequency)

            if args.limit > 0:
                result = filter_organic(result, limit=args.limit)

            query_results[query] = result
            total_organic += len(result.get("organic", []))

        log(f"Sorted by: {args.sort_by}")
        log(f"Output: {total_organic} organic URLs across {len(query_results)} queries")
        log("=" * 60 + "\n")

        # Output
        if args.format == "ndjson":
            output_ndjson(query_results)
        elif args.format == "csv":
            output_csv(query_results)
        else:
            # JSON: output based on number of queries
            if len(query_results) == 1:
                # Single query: output just the result
                output_json(list(query_results.values())[0])
            else:
                # Multiple queries: output dict keyed by query
                output_json(query_results)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Process and optionally merge SERP query results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Per-query passthrough (default)
    echo -e "query1\\nquery2" | python query_processor.py | python deduplicator.py

    # Cross-query merge (combine all queries)
    python deduplicator.py --cross-query < results.ndjson

    # Sort by frequency (most common URLs first)
    python deduplicator.py --sort-by frequency < results.ndjson

    # Top 100 organic results per query
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
        help="Merge all queries into single result (default: per-query passthrough)",
    )
    parser.add_argument(
        "--sort-by", "-s",
        choices=["best_position", "frequency", "avg_position"],
        default="best_position",
        help="Sort organic results by field (default: best_position)",
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=0,
        help="Limit to top N organic results (default: no limit)",
    )
    parser.add_argument(
        "--min-frequency", "-m",
        type=int,
        default=0,
        help="Filter organic by minimum frequency (default: no filter)",
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
