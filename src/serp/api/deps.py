"""FastAPI dependency injection utilities."""

from typing import AsyncIterator

from ..client import SerpAggregator
from ..cache import ResultCache
from ..settings import SerpSettings, get_settings

# Global client instance (initialized on startup)
_client: SerpAggregator | None = None


async def get_client() -> SerpAggregator:
    """
    Get the global SERP client instance.

    The client is initialized on application startup.
    """
    if _client is None:
        raise RuntimeError("Client not initialized. Application startup failed.")
    return _client


async def get_cache() -> ResultCache:
    """Get the cache instance from the client."""
    client = await get_client()
    return client.cache


def get_settings_dep() -> SerpSettings:
    """Get settings instance."""
    return get_settings()


async def init_client() -> None:
    """Initialize the global client on startup."""
    global _client
    _client = SerpAggregator()
    await _client.connect()


async def close_client() -> None:
    """Close the global client on shutdown."""
    global _client
    if _client:
        await _client.close()
        _client = None
