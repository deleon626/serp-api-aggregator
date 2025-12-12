"""Main SERP Aggregator client."""

import asyncio
import time
from typing import AsyncIterator

import aiohttp

from .cache import InMemoryCache, NullCache, ResultCache, generate_cache_key
from .exceptions import SerpConfigError
from .models import BatchResult, QueryTiming, SearchResult
from .progress import NullProgress, ProgressReporter
from .rate_limiter import AdaptiveRateLimiter, NullRateLimiter, RateLimiter
from .settings import SerpSettings, get_settings
from ._internal.bright_data import fetch_all_pages


class SerpAggregator:
    """
    Async SERP aggregator client.

    Provides a clean interface for searching and aggregating SERP results
    from Bright Data API with caching, rate limiting, and progress reporting.

    Usage with context manager (recommended):
        async with SerpAggregator() as client:
            result = await client.search("python tutorial")
            print(f"Found {len(result.organic)} results")

    Usage with explicit session management:
        client = SerpAggregator()
        await client.connect()
        try:
            result = await client.search("python tutorial")
        finally:
            await client.close()

    Configuration via environment:
        export SERP_BRIGHT_DATA_API_KEY="your-key"
        export SERP_DEFAULT_MAX_PAGES=10
    """

    def __init__(
        self,
        settings: SerpSettings | None = None,
        progress: ProgressReporter | None = None,
        cache: ResultCache | None = None,
        rate_limiter: RateLimiter | None = None,
    ):
        """
        Initialize SERP Aggregator.

        Args:
            settings: Configuration settings. Uses environment if not provided.
            progress: Progress reporter for status updates.
            cache: Result cache. Uses InMemoryCache if caching enabled in settings.
            rate_limiter: Rate limiter. Uses AdaptiveRateLimiter if enabled in settings.
        """
        self._settings = settings or get_settings()
        self._progress = progress or NullProgress()

        # Initialize cache
        if cache is not None:
            self._cache = cache
        elif self._settings.cache_enabled:
            self._cache = InMemoryCache(
                default_ttl=self._settings.cache_ttl,
            )
        else:
            self._cache = NullCache()

        # Initialize rate limiter
        if rate_limiter is not None:
            self._rate_limiter = rate_limiter
        elif self._settings.rate_limit_enabled:
            self._rate_limiter = AdaptiveRateLimiter(
                initial_rps=self._settings.rate_limit_rps,
                burst_size=self._settings.rate_limit_burst,
            )
        else:
            self._rate_limiter = NullRateLimiter()

        self._session: aiohttp.ClientSession | None = None
        self._owns_session = False

    async def connect(self) -> None:
        """Open HTTP session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._owns_session = True

    async def close(self) -> None:
        """Close HTTP session and cleanup resources."""
        if self._session and self._owns_session:
            await self._session.close()
            self._session = None
            self._owns_session = False

    async def __aenter__(self) -> "SerpAggregator":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure session is connected."""
        if self._session is None:
            raise SerpConfigError(
                "Client not connected. Use 'async with SerpAggregator()' "
                "or call connect() first."
            )
        return self._session

    async def search(
        self,
        query: str,
        *,
        max_pages: int | None = None,
        concurrency: int | None = None,
        country: str | None = None,
        language: str | None = None,
        use_cache: bool = True,
        raw_collector: list[dict] | None = None,
    ) -> SearchResult:
        """
        Execute a single search query.

        Args:
            query: Search query string
            max_pages: Maximum pages to fetch (default from settings)
            concurrency: Concurrent requests (default from settings)
            country: Country code (default from settings)
            language: Language code (default from settings)
            use_cache: Whether to use cache (default True)

        Returns:
            SearchResult with deduplicated organic results

        Raises:
            SerpConfigError: If client not connected
            SerpAPIError: On API errors
            SerpTimeoutError: On timeout
            SerpValidationError: On invalid input
        """
        session = self._ensure_session()

        # Apply defaults
        max_pages = max_pages or self._settings.default_max_pages
        concurrency = concurrency or self._settings.default_concurrency
        country = country or self._settings.default_country
        language = language or self._settings.default_language

        # Check cache
        if use_cache:
            cache_key = generate_cache_key(query, country, language, max_pages)
            cached_result = await self._cache.get(cache_key)
            if cached_result is not None:
                self._progress.on_cache_hit(query)
                return cached_result

        # Create settings override for this request
        request_settings = SerpSettings(
            bright_data_api_key=self._settings.bright_data_api_key,
            bright_data_zone=self._settings.bright_data_zone,
            api_base_url=self._settings.api_base_url,
            default_country=country,
            default_language=language,
            default_max_pages=max_pages,
            default_concurrency=concurrency,
            poll_interval=self._settings.poll_interval,
            max_polls=self._settings.max_polls,
            request_timeout=self._settings.request_timeout,
            max_retries=self._settings.max_retries,
            retry_backoff=self._settings.retry_backoff,
            rate_limit_enabled=self._settings.rate_limit_enabled,
            rate_limit_rps=self._settings.rate_limit_rps,
            consecutive_empty_limit=self._settings.consecutive_empty_limit,
        )

        # Fetch results
        result = await fetch_all_pages(
            session=session,
            settings=request_settings,
            query=query,
            max_pages=max_pages,
            concurrency=concurrency,
            progress=self._progress,
            rate_limiter=self._rate_limiter,
            raw_collector=raw_collector,
        )

        # Cache result
        if use_cache and not result.has_errors:
            cache_key = generate_cache_key(query, country, language, max_pages)
            await self._cache.set(cache_key, result)

        return result

    async def search_batch(
        self,
        queries: list[str],
        *,
        max_pages: int | None = None,
        concurrency: int | None = None,
        country: str | None = None,
        language: str | None = None,
        use_cache: bool = True,
        raw_collector: list[dict] | None = None,
    ) -> BatchResult:
        """
        Execute multiple search queries sequentially.

        For truly parallel execution, use search_parallel().

        Args:
            queries: List of search queries
            max_pages: Maximum pages per query
            concurrency: Concurrent requests per query
            country: Country code
            language: Language code
            use_cache: Whether to use cache

        Returns:
            BatchResult with all query results
        """
        start_time = time.time()

        results: dict[str, SearchResult] = {}
        timing: dict[str, float] = {}
        query_timings: list[QueryTiming] = []
        total_organic = 0

        for query in queries:
            query = query.strip()
            if not query:
                continue

            query_start = time.time()
            result = await self.search(
                query,
                max_pages=max_pages,
                concurrency=concurrency,
                country=country,
                language=language,
                use_cache=use_cache,
                raw_collector=raw_collector,
            )

            elapsed = time.time() - query_start
            results[query] = result
            timing[query] = round(elapsed, 2)
            total_organic += len(result.organic)

            query_timings.append(
                QueryTiming(
                    query=query,
                    elapsed_seconds=round(elapsed, 2),
                    result_count=len(result.organic),
                    pages_fetched=result.pages_fetched,
                    errors=len(result.errors),
                )
            )

        return BatchResult(
            queries=queries,
            results=results,
            timing=timing,
            total_organic=total_organic,
            total_elapsed_seconds=round(time.time() - start_time, 2),
            query_timings=query_timings,
        )

    async def search_parallel(
        self,
        queries: list[str],
        *,
        max_pages: int | None = None,
        concurrency: int | None = None,
        country: str | None = None,
        language: str | None = None,
        use_cache: bool = True,
        max_parallel_queries: int = 5,
        raw_collector: list[dict] | None = None,
    ) -> BatchResult:
        """
        Execute multiple search queries in parallel.

        Args:
            queries: List of search queries
            max_pages: Maximum pages per query
            concurrency: Concurrent requests per query
            country: Country code
            language: Language code
            use_cache: Whether to use cache
            max_parallel_queries: Maximum queries to run in parallel

        Returns:
            BatchResult with all query results
        """
        start_time = time.time()

        # Create semaphore for parallel query limit
        query_semaphore = asyncio.Semaphore(max_parallel_queries)

        async def search_with_timing(query: str) -> tuple[str, SearchResult, float]:
            async with query_semaphore:
                query_start = time.time()
                result = await self.search(
                    query,
                    max_pages=max_pages,
                    concurrency=concurrency,
                    country=country,
                    language=language,
                    use_cache=use_cache,
                    raw_collector=raw_collector,
                )
                elapsed = time.time() - query_start
                return query, result, elapsed

        # Run all queries in parallel
        tasks = [search_with_timing(q.strip()) for q in queries if q.strip()]
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        results: dict[str, SearchResult] = {}
        timing: dict[str, float] = {}
        query_timings: list[QueryTiming] = []
        total_organic = 0

        for item in completed:
            if isinstance(item, Exception):
                continue  # Skip failed queries

            query, result, elapsed = item
            results[query] = result
            timing[query] = round(elapsed, 2)
            total_organic += len(result.organic)

            query_timings.append(
                QueryTiming(
                    query=query,
                    elapsed_seconds=round(elapsed, 2),
                    result_count=len(result.organic),
                    pages_fetched=result.pages_fetched,
                    errors=len(result.errors),
                )
            )

        return BatchResult(
            queries=queries,
            results=results,
            timing=timing,
            total_organic=total_organic,
            total_elapsed_seconds=round(time.time() - start_time, 2),
            query_timings=query_timings,
        )

    async def search_stream(
        self,
        queries: list[str],
        *,
        max_pages: int | None = None,
        concurrency: int | None = None,
        country: str | None = None,
        language: str | None = None,
        use_cache: bool = True,
    ) -> AsyncIterator[tuple[str, SearchResult]]:
        """
        Stream search results as each query completes.

        Yields:
            Tuple of (query, SearchResult) as each query completes
        """
        for query in queries:
            query = query.strip()
            if not query:
                continue

            result = await self.search(
                query,
                max_pages=max_pages,
                concurrency=concurrency,
                country=country,
                language=language,
                use_cache=use_cache,
            )
            yield query, result

    @property
    def cache(self) -> ResultCache:
        """Get the cache instance."""
        return self._cache

    @property
    def rate_limiter(self) -> RateLimiter:
        """Get the rate limiter instance."""
        return self._rate_limiter

    @property
    def settings(self) -> SerpSettings:
        """Get the settings instance."""
        return self._settings


# Convenience function for one-off searches
async def search(
    query: str,
    *,
    settings: SerpSettings | None = None,
    **kwargs,
) -> SearchResult:
    """
    Convenience function for single search.

    Creates a temporary client and executes one search.

    Usage:
        result = await serp.search("python tutorial")

    Args:
        query: Search query string
        settings: Optional settings override
        **kwargs: Additional arguments passed to SerpAggregator.search()

    Returns:
        SearchResult with deduplicated organic results
    """
    async with SerpAggregator(settings=settings) as client:
        return await client.search(query, **kwargs)


async def search_batch(
    queries: list[str],
    *,
    settings: SerpSettings | None = None,
    **kwargs,
) -> BatchResult:
    """
    Convenience function for batch search.

    Creates a temporary client and executes batch search.

    Usage:
        result = await serp.search_batch(["query1", "query2"])

    Args:
        queries: List of search queries
        settings: Optional settings override
        **kwargs: Additional arguments passed to SerpAggregator.search_batch()

    Returns:
        BatchResult with all query results
    """
    async with SerpAggregator(settings=settings) as client:
        return await client.search_batch(queries, **kwargs)
