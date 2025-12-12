# SERP API Aggregator

Async Python library for SERP data aggregation via Bright Data API.

## Bash commands

- `source .venv/bin/activate`: Activate virtual environment
- `uv pip install -e ".[all]"`: Install with all dependencies
- `serp search "query"`: Single search
- `serp batch "q1" "q2" --parallel`: Batch search
- `serp serve --port 8000`: Start REST API server

## Versioning

Uses `bump2version` for automated versioning.

```bash
bump2version patch   # 0.2.0 → 0.2.1 (bug fixes)
bump2version minor   # 0.2.0 → 0.3.0 (new features)
bump2version major   # 0.2.0 → 1.0.0 (breaking changes)
```

Each bump updates:
- `pyproject.toml`
- `src/serp/__init__.py`
- Creates git commit + tag

Push tags: `git push origin --tags`

## Test findings

@tests/GOOGLE_SERP_FINDINGS.md

