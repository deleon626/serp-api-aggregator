# SERP API Aggregator

A Python pipeline for fetching, aggregating, and deduplicating Google SERP results using the Bright Data API.

## Overview

This tool fetches multiple pages of Google search results for given queries, deduplicates organic results across pages, and outputs structured JSON matching the Bright Data API schema.

## Installation

```bash
# Create virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv pip install aiohttp
```

## Quick Start

```bash
# Single query (fetches 25 pages by default)
echo "python tutorial" | python query_processor.py | python deduplicator.py > output.json

# Multiple queries
echo -e "python tutorial\nmachine learning" | python query_processor.py | python deduplicator.py

# Quick test with fewer pages
echo "python tutorial" | python query_processor.py --max-pages 5 | python deduplicator.py
```

## Scripts

### query_processor.py

Fetches SERP results for one or more queries. Outputs NDJSON (one line per query).

```bash
# From stdin
echo "python tutorial" | python query_processor.py

# From file
python query_processor.py --file queries.txt

# With options
python query_processor.py --max-pages 10 --concurrency 30
```

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--file, -f` | stdin | File with queries (one per line) |
| `--max-pages, -p` | 25 | Max pages per query |
| `--concurrency, -c` | 50 | Max concurrent API requests |

### deduplicator.py

Processes query results. Per-query mode passes through (dedup already done). Cross-query mode merges multiple queries.

```bash
# Per-query mode (default) - passthrough
python deduplicator.py < results.ndjson

# Cross-query mode - merge all queries
python deduplicator.py --cross-query < results.ndjson

# Sort by frequency instead of position
python deduplicator.py --sort-by frequency

# Output as CSV
python deduplicator.py --format csv > results.csv

# Limit results
python deduplicator.py --limit 100 --min-frequency 2
```

**Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--cross-query, -x` | false | Merge all queries into single result |
| `--sort-by, -s` | best_position | Sort by: best_position, frequency, avg_position |
| `--limit, -l` | 0 (no limit) | Limit to top N organic results |
| `--min-frequency, -m` | 0 | Filter by minimum frequency |
| `--format, -o` | json | Output: json, ndjson, csv |

### run_parallel_queries.py

Runs multiple queries in parallel with timing metrics.

```bash
# Default test queries
python run_parallel_queries.py

# Custom queries
python run_parallel_queries.py --queries "python tutorial" "machine learning"

# From file
python run_parallel_queries.py --file queries.txt

# Quick test
python run_parallel_queries.py --max-pages 5
```

## Output Schema

Output matches the Bright Data API format with added deduplication metadata:

```json
{
  "url": "https://www.google.com/search?q=...",
  "keyword": null,
  "general": {
    "query": "python tutorial",
    "search_engine": "google",
    "search_type": "text",
    "language": "en",
    "timestamp": "2025-12-08T..."
  },
  "organic": [
    {
      "link": "https://example.com",
      "rank": 1,
      "title": "Example Title",
      "description": "Example description",
      "best_position": 1,
      "avg_position": 1.5,
      "frequency": 3,
      "pages_seen": [1, 2, 5]
    }
  ],
  "related": [
    {"text": "related search", "link": "...", "rank": 1}
  ],
  "people_also_ask": ["Question? Answer..."],
  "navigation": [
    {"title": "Images", "href": "..."}
  ],
  "pagination": [...],
  "aio_text": null,
  "language": null,
  "country": null
}
```

### Deduplication Fields

| Field | Description |
|-------|-------------|
| `best_position` | Minimum rank seen across all pages |
| `avg_position` | Average rank across occurrences |
| `frequency` | Number of times URL appeared |
| `pages_seen` | List of page numbers where URL was found |

## Configuration

Edit `config.py` to change defaults:

```python
# API credentials
BRIGHT_DATA_API_KEY = "your-api-key"
BRIGHT_DATA_ZONE = "serp_api1"

# Search parameters
BASE_PARAMS = {
    "gl": "us",      # Country
    "hl": "en",      # Language
    "brd_json": "1"  # JSON output
}

# Processing defaults
DEFAULT_MAX_PAGES = 25
DEFAULT_CONCURRENCY = 50
```

## Pipeline Examples

```bash
# Full pipeline with JSON output
echo "python tutorial" | python query_processor.py | python deduplicator.py > output.json

# Multiple queries with cross-query merge
echo -e "python\njava\nrust" | python query_processor.py | python deduplicator.py --cross-query > merged.json

# CSV export sorted by frequency
echo "machine learning" | python query_processor.py | python deduplicator.py --format csv --sort-by frequency > results.csv

# Top 50 most frequent URLs across queries
cat queries.txt | python query_processor.py | python deduplicator.py --cross-query --sort-by frequency --limit 50
```

## Performance

| Metric | Value |
|--------|-------|
| Avg response time | 3-5 seconds per page |
| Max pagination depth | ~22 pages (~200 results) |
| Optimal concurrency | 50-100 requests |
| API throughput | ~4-6 requests/second |

## Files

| File | Description |
|------|-------------|
| `config.py` | API credentials and defaults |
| `bright_data_client.py` | Async API client with deduplication |
| `query_processor.py` | Multi-query orchestrator |
| `deduplicator.py` | Result processor and merger |
| `run_parallel_queries.py` | Parallel runner with timing |
