# Tests

Test suite for the SERP Aggregator library.

## Bash Commands

- `python tests/test_serp.py --all`: Run all tests
- `python tests/test_serp.py --basic`: Basic search tests
- `python tests/test_serp.py --batch`: Batch/parallel tests
- `python tests/test_serp.py --pagination`: Pagination depth tests
- `python tests/test_serp.py --concurrency`: Throughput tests
- `python tests/test_serp.py --consistency`: Result stability tests
- `python tests/test_serp.py --list`: List available tests

## Test Categories

| Category | Description | ~Duration |
|----------|-------------|-----------|
| `--basic` | Single search, localization, field validation | 15s |
| `--batch` | search_batch, search_parallel | 30s |
| `--pagination` | Max pages discovery (up to 30 pages) | 90s |
| `--concurrency` | Sequential baseline, parallel throughput | 60s |
| `--consistency` | Duplicate request comparison | 10s |

## Requirements

- `SERP_BRIGHT_DATA_API_KEY` environment variable set
- Network access to Bright Data API
- Tests make real API calls (not mocked)

## Archived Tests

Deprecated tests that directly called Bright Data API are in `tests/archive/`:

| File | Purpose |
|------|---------|
| test_bright_data_serp.py | Comprehensive API test suite (92 tests) |
| test_concurrency.py | Concurrency/throughput benchmarking |
| test_high_concurrency.py | Stress testing (100-200 concurrent) |
| test_max_pages.py | Pagination depth discovery |
| test_pagination_manual.py | Manual CLI testing tool |
| BRIGHT_DATA_SERP_TEST_DESIGN.md | Test design document |

## Reference

- `GOOGLE_SERP_FINDINGS.md`: API behavior findings and test results
