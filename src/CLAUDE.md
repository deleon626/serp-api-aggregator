# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Bash commands

- `source .venv/bin/activate`: Activate Python virtual environment
- `uv venv`: Create virtual environment using uv
- `uv pip install aiohttp`: Install dependencies (no requirements.txt yet)

### Pipeline commands
- `echo "python tutorial" | python src/query_processor.py | python src/deduplicator.py`: Full pipeline
- `python src/query_processor.py --file queries.txt`: Fetch SERP results for multiple queries
- `python src/deduplicator.py < results.ndjson`: Pass through results (per-query mode)
- `python src/deduplicator.py --cross-query < results.ndjson`: Merge all queries into single result

### Parallel query runner
- `python src/run_parallel_queries.py --queries "q1" "q2"`: Run queries in parallel with timing
- `python src/run_parallel_queries.py --max-pages 5`: Quick test with fewer pages
- `python src/run_parallel_queries.py --file queries.txt`: Load queries from file

### Test commands
- `python tests/test_bright_data_serp.py --all`: Run full test suite
- `python tests/test_concurrency.py`: Test concurrent request performance
- `python tests/test_max_pages.py`: Test pagination depth limits

## Code style

- Use async/await for all Bright Data API calls
- Prefer aiohttp over requests for async HTTP
- Log to stderr, output data to stdout (Unix pipeline pattern)
- Use NDJSON (newline-delimited JSON) for streaming data between pipeline stages
- Keep configuration centralized in `src/config.py`

## Output Schema

Output matches Bright Data API response structure with added deduplication metadata:

```json
{
  "url": "https://www.google.com/search?q=...",
  "keyword": null,
  "general": {
    "datetime": "2025-12-08T...",
    "language": "en",
    "location": "United States",
    "page_title": "query - Google Search",
    "query": "actual query",
    "search_engine": "google",
    "search_type": "text"
  },
  "related": [
    {"link": "...", "rank": 1, "text": "related search"}
  ],
  "pagination": [
    {"link": "...", "page": "2", "page_html": null}
  ],
  "organic": [
    {
      "link": "https://example.com",
      "rank": 1,
      "title": "Example Title",
      "description": "Example description",
      "url": "https://www.google.com/...",
      "best_position": 1,
      "avg_position": 1.5,
      "frequency": 3,
      "pages_seen": [1, 2, 5]
    }
  ],
  "people_also_ask": [
    "Question? Answer snippet... source.com"
  ],
  "navigation": [
    {"link": "...", "title": "Images"}
  ],
  "language": null,
  "country": null,
  "page_html": null,
  "aio_text": null
}
```

### Organic Result Deduplication Fields
- `best_position`: Minimum rank position seen across all pages
- `avg_position`: Average rank position across occurrences
- `frequency`: Number of times URL appeared across pages
- `pages_seen`: List of page numbers where URL was found

## Project architecture

### High-level flow
```
Client → query_processor.py → Bright Data SERP API → deduplicator.py → Aggregated Results
```

### Key components

1. **bright_data_client.py**: Core async API client
   - `make_serp_request()`: Submit request, poll for results with retry logic
   - `fetch_all_pages()`: Returns complete Bright Data schema with deduplicated organic results
   - Extracts: organic, related, people_also_ask, navigation, general metadata, aio_text
   - Implements semaphore-based concurrency control
   - Early termination on 3 consecutive empty pages

2. **query_processor.py**: Multi-query orchestrator
   - Reads queries from stdin or file
   - Fetches all pages for each query concurrently
   - Outputs one NDJSON line per query (complete result structure)
   - Default: 25 pages, 50 concurrent requests

3. **deduplicator.py**: Query result processor
   - Reads NDJSON from stdin (one complete query result per line)
   - **Per-query mode (default)**: Passthrough (dedup already done in bright_data_client)
   - **Cross-query mode** (`--cross-query`): Merges all queries, dedupes organic/related/PAA
   - Outputs JSON, NDJSON, or CSV

4. **run_parallel_queries.py**: Parallel query runner with timing
   - Runs multiple queries concurrently
   - Measures per-query and total execution time
   - Reports parallelism speedup factor
   - Outputs JSON with full timing metrics

5. **config.py**: Centralized configuration
   - Bright Data API credentials
   - Default parameters (gl=us, hl=en, brd_json=1)
   - Polling and retry settings

### API integration pattern

**Bright Data async flow:**
```
1. POST /serp/req → returns response_id
2. Poll GET /serp/get_result?response_id=xxx until HTTP 200
3. Typical: 1-8 poll attempts at 2-second intervals
```

### Performance characteristics

- **Optimal concurrency:** 50-100 concurrent requests (see `tests/GOOGLE_SERP_FINDINGS.md`)
- **API throughput:** ~4-6 requests/second sustained
- **Response time:** 3-5 seconds average (2.6s-16s range)
- **Pagination depth:** ~22 pages (200-240 results) depending on query type
- **Result consistency:** 78% page 1, 10% page 3 (proxy rotation affects ordering)

## Workflow

### Adding new search parameters
1. Update `BASE_PARAMS` in `src/config.py`
2. Modify `make_serp_request()` in `bright_data_client.py` to include new params
3. Test with `tests/test_bright_data_serp.py`

### Adding new result fields
1. Modify `fetch_all_pages()` in `src/bright_data_client.py` to extract new fields
2. Update aggregation logic if needed
3. Ensure deduplicator handles new fields in cross-query merge

### Testing new features
1. Design test cases in `tests/BRIGHT_DATA_SERP_TEST_DESIGN.md`
2. Implement in `tests/test_*.py` using async test pattern
3. Update findings in `tests/GOOGLE_SERP_FINDINGS.md`

## Project notes

- **API Key:** Hardcoded in `src/config.py` (c69f9a87-ded2-4064-a901-5439af92bb54)
- **Zone:** serp_api1 (Google only, Bing not supported)
- **No REST API yet:** Currently Unix pipeline tools only (PRD.md defines future REST API)
- **Testing completed:** 92 test cases designed, 31 executed, 83.9% pass rate
- **Known limitations:**
  - Bing search times out (zone not configured)
  - Jobs search times out
  - Parsed light format returns HTTP 202
  - Result ordering inconsistent due to proxy rotation (10-78% position match depending on page depth)
- **Early termination:** Pagination stops after 3 consecutive empty pages to save API calls

## Important files

- `PRD.md`: Product requirements for future REST API service
- `tests/GOOGLE_SERP_FINDINGS.md`: Comprehensive test results and performance metrics
- `tests/BRIGHT_DATA_SERP_TEST_DESIGN.md`: Test case catalog
- `output_example.json`: Reference for Bright Data API response structure
