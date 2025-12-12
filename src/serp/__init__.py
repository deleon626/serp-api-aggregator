"""
SERP API Aggregator - Async Python library for search result aggregation.

A production-ready library for fetching, aggregating, and deduplicating
SERP results from Bright Data API.

Quick Start:
    import serp

    # Using async context manager (recommended)
    async with serp.SerpAggregator() as client:
        result = await client.search("python tutorial")
        for item in result.organic:
            print(f"{item.best_position}: {item.title}")

    # Convenience function for one-off searches
    result = await serp.search("python tutorial")

    # Batch search
    batch = await serp.search_batch(["query1", "query2"])

Configuration via environment variables:
    export SERP_BRIGHT_DATA_API_KEY="your-api-key"
    export SERP_BRIGHT_DATA_ZONE="serp_api1"
    export SERP_DEFAULT_MAX_PAGES=25
    export SERP_CACHE_TTL=3600
"""

from .client import SerpAggregator, search, search_batch
from .models import (
    BatchResult,
    BatchSearchParams,
    GeneralMetadata,
    NavigationItem,
    OrganicResult,
    PaginationItem,
    QueryTiming,
    RelatedSearch,
    SearchParams,
    SearchResult,
)
from .exceptions import (
    SerpAPIError,
    SerpCacheError,
    SerpConfigError,
    SerpError,
    SerpRateLimitError,
    SerpTimeoutError,
    SerpValidationError,
)
from .settings import SerpSettings, get_settings
from .progress import (
    AggregatingProgress,
    CallbackProgress,
    NullProgress,
    ProgressEvent,
    ProgressReporter,
    StderrProgress,
)
from .cache import (
    CacheStats,
    InMemoryCache,
    NullCache,
    RedisCache,
    ResultCache,
    generate_cache_key,
)
from .rate_limiter import (
    AdaptiveRateLimiter,
    NullRateLimiter,
    RateLimiter,
    RateLimiterStats,
    SemaphoreRateLimiter,
)

__version__ = "0.3.0"

__all__ = [
    # Main client
    "SerpAggregator",
    "search",
    "search_batch",
    # Models
    "SearchParams",
    "BatchSearchParams",
    "SearchResult",
    "BatchResult",
    "OrganicResult",
    "RelatedSearch",
    "GeneralMetadata",
    "PaginationItem",
    "NavigationItem",
    "QueryTiming",
    # Exceptions
    "SerpError",
    "SerpAPIError",
    "SerpTimeoutError",
    "SerpRateLimitError",
    "SerpConfigError",
    "SerpValidationError",
    "SerpCacheError",
    # Settings
    "SerpSettings",
    "get_settings",
    # Progress
    "ProgressReporter",
    "ProgressEvent",
    "NullProgress",
    "StderrProgress",
    "CallbackProgress",
    "AggregatingProgress",
    # Cache
    "ResultCache",
    "CacheStats",
    "NullCache",
    "InMemoryCache",
    "RedisCache",
    "generate_cache_key",
    # Rate Limiter
    "RateLimiter",
    "RateLimiterStats",
    "NullRateLimiter",
    "AdaptiveRateLimiter",
    "SemaphoreRateLimiter",
    # Version
    "__version__",
]
