"""Result caching with in-memory and Redis backends."""

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from .models import SearchResult


def generate_cache_key(query: str, country: str, language: str, max_pages: int) -> str:
    """Generate a deterministic cache key for search parameters."""
    key_data = f"{query}|{country}|{language}|{max_pages}"
    return hashlib.sha256(key_data.encode()).hexdigest()[:32]


@dataclass
class CacheStats:
    """Cache statistics."""

    hits: int = 0
    misses: int = 0
    sets: int = 0
    evictions: int = 0
    size: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


@runtime_checkable
class ResultCache(Protocol):
    """Protocol for result caching."""

    async def get(self, key: str) -> SearchResult | None:
        """Get result from cache."""
        ...

    async def set(self, key: str, value: SearchResult, ttl: int | None = None) -> None:
        """Store result in cache."""
        ...

    async def delete(self, key: str) -> bool:
        """Delete result from cache."""
        ...

    async def clear(self) -> None:
        """Clear all cached results."""
        ...

    @property
    def stats(self) -> CacheStats:
        """Get cache statistics."""
        ...


class NullCache:
    """No-op cache (caching disabled)."""

    def __init__(self):
        self._stats = CacheStats()

    async def get(self, key: str) -> SearchResult | None:
        self._stats.misses += 1
        return None

    async def set(self, key: str, value: SearchResult, ttl: int | None = None) -> None:
        pass

    async def delete(self, key: str) -> bool:
        return False

    async def clear(self) -> None:
        pass

    @property
    def stats(self) -> CacheStats:
        return self._stats


@dataclass
class CacheEntry:
    """Cache entry with TTL support."""

    value: SearchResult
    created_at: float
    ttl: int | None = None

    @property
    def is_expired(self) -> bool:
        if self.ttl is None or self.ttl == 0:
            return False
        return time.time() - self.created_at > self.ttl


@dataclass
class InMemoryCache:
    """
    In-memory cache with TTL and LRU eviction.

    Thread-safe for asyncio concurrent access.
    """

    default_ttl: int = 3600  # 1 hour
    max_size: int = 1000  # Maximum entries

    _cache: dict[str, CacheEntry] = field(default_factory=dict)
    _access_order: list[str] = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _stats: CacheStats = field(default_factory=CacheStats)

    async def get(self, key: str) -> SearchResult | None:
        """Get result from cache."""
        async with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._stats.misses += 1
                return None

            if entry.is_expired:
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                self._stats.misses += 1
                self._stats.evictions += 1
                return None

            # Update access order (LRU)
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)

            self._stats.hits += 1
            return entry.value

    async def set(self, key: str, value: SearchResult, ttl: int | None = None) -> None:
        """Store result in cache."""
        async with self._lock:
            # Evict if at capacity
            while len(self._cache) >= self.max_size:
                if self._access_order:
                    oldest_key = self._access_order.pop(0)
                    if oldest_key in self._cache:
                        del self._cache[oldest_key]
                        self._stats.evictions += 1
                else:
                    break

            self._cache[key] = CacheEntry(
                value=value,
                created_at=time.time(),
                ttl=ttl if ttl is not None else self.default_ttl,
            )

            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)

            self._stats.sets += 1
            self._stats.size = len(self._cache)

    async def delete(self, key: str) -> bool:
        """Delete result from cache."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                self._stats.size = len(self._cache)
                return True
            return False

    async def clear(self) -> None:
        """Clear all cached results."""
        async with self._lock:
            self._cache.clear()
            self._access_order.clear()
            self._stats.size = 0

    @property
    def stats(self) -> CacheStats:
        """Get cache statistics."""
        self._stats.size = len(self._cache)
        return self._stats

    async def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count of removed entries."""
        async with self._lock:
            expired_keys = [k for k, v in self._cache.items() if v.is_expired]
            for key in expired_keys:
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                self._stats.evictions += 1

            self._stats.size = len(self._cache)
            return len(expired_keys)


class RedisCache:
    """
    Redis-backed cache for distributed deployments.

    Requires redis package: pip install redis
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        default_ttl: int = 3600,
        key_prefix: str = "serp:",
    ):
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self.key_prefix = key_prefix
        self._client: Any = None
        self._stats = CacheStats()

    async def _get_client(self):
        """Lazy initialization of Redis client."""
        if self._client is None:
            try:
                import redis.asyncio as redis

                self._client = redis.from_url(self.redis_url)
            except ImportError:
                raise ImportError("Redis package required. Install with: pip install redis")
        return self._client

    def _make_key(self, key: str) -> str:
        return f"{self.key_prefix}{key}"

    async def get(self, key: str) -> SearchResult | None:
        """Get result from Redis."""
        try:
            client = await self._get_client()
            data = await client.get(self._make_key(key))

            if data is None:
                self._stats.misses += 1
                return None

            self._stats.hits += 1
            result_dict = json.loads(data)
            return SearchResult.model_validate(result_dict)

        except Exception:
            self._stats.misses += 1
            return None

    async def set(self, key: str, value: SearchResult, ttl: int | None = None) -> None:
        """Store result in Redis."""
        try:
            client = await self._get_client()
            data = value.model_dump_json()
            ttl = ttl if ttl is not None else self.default_ttl

            if ttl > 0:
                await client.setex(self._make_key(key), ttl, data)
            else:
                await client.set(self._make_key(key), data)

            self._stats.sets += 1

        except Exception:
            pass  # Fail silently on cache errors

    async def delete(self, key: str) -> bool:
        """Delete result from Redis."""
        try:
            client = await self._get_client()
            result = await client.delete(self._make_key(key))
            return result > 0
        except Exception:
            return False

    async def clear(self) -> None:
        """Clear all cached results with prefix."""
        try:
            client = await self._get_client()
            keys = await client.keys(f"{self.key_prefix}*")
            if keys:
                await client.delete(*keys)
        except Exception:
            pass

    @property
    def stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._stats

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
