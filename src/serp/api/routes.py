"""FastAPI route handlers."""

import asyncio
from typing import AsyncIterator

try:
    from fastapi import APIRouter, Depends, HTTPException, Query
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("FastAPI not installed. Run: pip install serp-aggregator[api]")

from ..client import SerpAggregator
from ..models import SearchResult, BatchResult, SearchParams, BatchSearchParams
from ..exceptions import SerpError, SerpTimeoutError, SerpRateLimitError
from .deps import get_client

router = APIRouter(prefix="/api", tags=["search"])


# Request/Response models
class SearchRequest(BaseModel):
    """Search request body."""
    query: str = Field(..., min_length=1, max_length=500)
    max_pages: int = Field(default=25, ge=1, le=100)
    concurrency: int = Field(default=50, ge=1, le=200)
    country: str = Field(default="us", pattern=r"^[a-z]{2}$")
    language: str = Field(default="en", pattern=r"^[a-z]{2}(-[a-z]{2})?$")
    use_cache: bool = Field(default=True)


class BatchSearchRequest(BaseModel):
    """Batch search request body."""
    queries: list[str] = Field(..., min_length=1)
    max_pages: int = Field(default=25, ge=1, le=100)
    concurrency: int = Field(default=50, ge=1, le=200)
    country: str = Field(default="us")
    language: str = Field(default="en")
    use_cache: bool = Field(default=True)
    parallel: bool = Field(default=False)


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    detail: str | None = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    version: str


class StatsResponse(BaseModel):
    """Statistics response."""
    cache_hits: int
    cache_misses: int
    cache_size: int
    rate_limit_rps: float


@router.post("/search", response_model=SearchResult)
async def search(
    request: SearchRequest,
    client: SerpAggregator = Depends(get_client),
) -> SearchResult:
    """
    Execute a single search query.

    Returns SearchResult with deduplicated organic results.
    """
    try:
        result = await client.search(
            query=request.query,
            max_pages=request.max_pages,
            concurrency=request.concurrency,
            country=request.country,
            language=request.language,
            use_cache=request.use_cache,
        )
        return result

    except SerpRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except SerpTimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except SerpError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search", response_model=SearchResult)
async def search_get(
    query: str = Query(..., min_length=1, max_length=500),
    max_pages: int = Query(default=25, ge=1, le=100),
    concurrency: int = Query(default=50, ge=1, le=200),
    country: str = Query(default="us"),
    language: str = Query(default="en"),
    use_cache: bool = Query(default=True),
    client: SerpAggregator = Depends(get_client),
) -> SearchResult:
    """
    Execute a single search query (GET method).

    Convenience endpoint for simple searches via URL parameters.
    """
    try:
        result = await client.search(
            query=query,
            max_pages=max_pages,
            concurrency=concurrency,
            country=country,
            language=language,
            use_cache=use_cache,
        )
        return result

    except SerpRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except SerpTimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except SerpError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch", response_model=BatchResult)
async def batch_search(
    request: BatchSearchRequest,
    client: SerpAggregator = Depends(get_client),
) -> BatchResult:
    """
    Execute batch search queries.

    Set parallel=true to run queries in parallel.
    """
    try:
        if request.parallel:
            result = await client.search_parallel(
                queries=request.queries,
                max_pages=request.max_pages,
                concurrency=request.concurrency,
                country=request.country,
                language=request.language,
                use_cache=request.use_cache,
            )
        else:
            result = await client.search_batch(
                queries=request.queries,
                max_pages=request.max_pages,
                concurrency=request.concurrency,
                country=request.country,
                language=request.language,
                use_cache=request.use_cache,
            )
        return result

    except SerpRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except SerpTimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except SerpError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stream")
async def stream_search(
    query: str = Query(..., min_length=1, max_length=500),
    max_pages: int = Query(default=25, ge=1, le=100),
    concurrency: int = Query(default=50, ge=1, le=200),
    country: str = Query(default="us"),
    language: str = Query(default="en"),
    client: SerpAggregator = Depends(get_client),
) -> StreamingResponse:
    """
    Stream search results via Server-Sent Events (SSE).

    Results are streamed as NDJSON lines as each page completes.
    """
    async def event_generator() -> AsyncIterator[str]:
        try:
            result = await client.search(
                query=query,
                max_pages=max_pages,
                concurrency=concurrency,
                country=country,
                language=language,
                use_cache=False,  # Don't cache streaming results
            )
            # Stream final result
            yield f"data: {result.model_dump_json()}\n\n"
            yield "event: done\ndata: {}\n\n"

        except SerpError as e:
            yield f"event: error\ndata: {{\"error\": \"{str(e)}\"}}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    client: SerpAggregator = Depends(get_client),
) -> StatsResponse:
    """Get cache and rate limiter statistics."""
    cache_stats = client.cache.stats
    rate_stats = client.rate_limiter.stats

    return StatsResponse(
        cache_hits=cache_stats.hits,
        cache_misses=cache_stats.misses,
        cache_size=cache_stats.size,
        rate_limit_rps=rate_stats.current_rps,
    )


@router.delete("/cache")
async def clear_cache(
    client: SerpAggregator = Depends(get_client),
) -> dict:
    """Clear the result cache."""
    await client.cache.clear()
    return {"status": "ok", "message": "Cache cleared"}
