"""Adaptive rate limiter with circuit breaker pattern."""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class RateLimiterStats:
    """Rate limiter statistics."""

    requests_total: int = 0
    requests_allowed: int = 0
    requests_throttled: int = 0
    rate_limit_hits: int = 0
    errors_total: int = 0
    circuit_opens: int = 0
    current_rps: float = 0.0
    circuit_state: CircuitState = CircuitState.CLOSED


@runtime_checkable
class RateLimiter(Protocol):
    """Protocol for rate limiters."""

    async def acquire(self) -> None:
        """Wait until a request is allowed."""
        ...

    async def on_success(self) -> None:
        """Called on successful request."""
        ...

    async def on_rate_limit(self) -> None:
        """Called when rate limit is hit (429)."""
        ...

    async def on_error(self) -> None:
        """Called on request error."""
        ...

    @property
    def stats(self) -> RateLimiterStats:
        """Get current statistics."""
        ...


class NullRateLimiter:
    """No-op rate limiter (no throttling)."""

    def __init__(self):
        self._stats = RateLimiterStats()

    async def acquire(self) -> None:
        self._stats.requests_total += 1
        self._stats.requests_allowed += 1

    async def on_success(self) -> None:
        pass

    async def on_rate_limit(self) -> None:
        self._stats.rate_limit_hits += 1

    async def on_error(self) -> None:
        self._stats.errors_total += 1

    @property
    def stats(self) -> RateLimiterStats:
        return self._stats


@dataclass
class AdaptiveRateLimiter:
    """
    Adaptive rate limiter with circuit breaker.

    Features:
    - Token bucket algorithm for smooth rate limiting
    - Automatic rate reduction on 429 responses
    - Gradual rate increase on success
    - Circuit breaker for failure protection
    """

    # Configuration
    initial_rps: float = 5.0
    min_rps: float = 0.5
    max_rps: float = 20.0
    burst_size: int = 10

    # Circuit breaker settings
    error_threshold: int = 5  # Errors before opening circuit
    recovery_timeout: float = 30.0  # Seconds before trying half-open
    success_threshold: int = 3  # Successes in half-open before closing

    # Internal state
    _current_rps: float = field(init=False)
    _tokens: float = field(init=False)
    _last_update: float = field(init=False)
    _lock: asyncio.Lock = field(init=False, default_factory=asyncio.Lock)

    # Circuit breaker state
    _circuit_state: CircuitState = field(init=False, default=CircuitState.CLOSED)
    _consecutive_errors: int = field(init=False, default=0)
    _consecutive_successes: int = field(init=False, default=0)
    _circuit_opened_at: float = field(init=False, default=0.0)

    # Stats
    _stats: RateLimiterStats = field(init=False, default_factory=RateLimiterStats)

    def __post_init__(self):
        self._current_rps = self.initial_rps
        self._tokens = float(self.burst_size)
        self._last_update = time.monotonic()
        self._lock = asyncio.Lock()
        self._stats.current_rps = self._current_rps

    async def acquire(self) -> None:
        """
        Wait until a request is allowed.

        Raises:
            RuntimeError: If circuit is open
        """
        async with self._lock:
            self._stats.requests_total += 1

            # Check circuit breaker
            if self._circuit_state == CircuitState.OPEN:
                if time.monotonic() - self._circuit_opened_at > self.recovery_timeout:
                    self._circuit_state = CircuitState.HALF_OPEN
                    self._consecutive_successes = 0
                else:
                    self._stats.requests_throttled += 1
                    raise RuntimeError("Circuit breaker is open")

            # Refill tokens based on time elapsed
            now = time.monotonic()
            elapsed = now - self._last_update
            self._tokens = min(
                float(self.burst_size),
                self._tokens + elapsed * self._current_rps,
            )
            self._last_update = now

            # Wait if no tokens available
            if self._tokens < 1.0:
                wait_time = (1.0 - self._tokens) / self._current_rps
                self._stats.requests_throttled += 1
                await asyncio.sleep(wait_time)
                self._tokens = 0.0
            else:
                self._tokens -= 1.0

            self._stats.requests_allowed += 1

    async def on_success(self) -> None:
        """Called on successful request - gradually increase rate."""
        async with self._lock:
            self._consecutive_errors = 0
            self._consecutive_successes += 1

            # Check if we can close circuit
            if self._circuit_state == CircuitState.HALF_OPEN:
                if self._consecutive_successes >= self.success_threshold:
                    self._circuit_state = CircuitState.CLOSED
                    self._consecutive_successes = 0

            # Gradually increase rate (10% per success, capped)
            if self._current_rps < self.max_rps:
                self._current_rps = min(self.max_rps, self._current_rps * 1.1)
                self._stats.current_rps = self._current_rps

    async def on_rate_limit(self) -> None:
        """Called when rate limit is hit (429) - halve the rate."""
        async with self._lock:
            self._stats.rate_limit_hits += 1
            self._consecutive_errors += 1

            # Halve the rate, respect minimum
            self._current_rps = max(self.min_rps, self._current_rps * 0.5)
            self._stats.current_rps = self._current_rps

            # Check if we should open circuit
            await self._check_circuit()

    async def on_error(self) -> None:
        """Called on request error - reduce rate and check circuit."""
        async with self._lock:
            self._stats.errors_total += 1
            self._consecutive_errors += 1
            self._consecutive_successes = 0

            # Reduce rate by 20%
            self._current_rps = max(self.min_rps, self._current_rps * 0.8)
            self._stats.current_rps = self._current_rps

            # Check if we should open circuit
            await self._check_circuit()

    async def _check_circuit(self) -> None:
        """Check if circuit breaker should open."""
        if self._consecutive_errors >= self.error_threshold:
            if self._circuit_state != CircuitState.OPEN:
                self._circuit_state = CircuitState.OPEN
                self._circuit_opened_at = time.monotonic()
                self._stats.circuit_opens += 1
                self._stats.circuit_state = CircuitState.OPEN

    @property
    def stats(self) -> RateLimiterStats:
        """Get current statistics."""
        self._stats.circuit_state = self._circuit_state
        return self._stats

    @property
    def current_rps(self) -> float:
        """Get current rate limit."""
        return self._current_rps

    @property
    def is_circuit_open(self) -> bool:
        """Check if circuit is open."""
        return self._circuit_state == CircuitState.OPEN


class SemaphoreRateLimiter:
    """Simple semaphore-based concurrency limiter."""

    def __init__(self, max_concurrent: int = 50):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._stats = RateLimiterStats()

    async def acquire(self) -> None:
        self._stats.requests_total += 1
        await self._semaphore.acquire()
        self._stats.requests_allowed += 1

    async def release(self) -> None:
        self._semaphore.release()

    async def on_success(self) -> None:
        self.release()

    async def on_rate_limit(self) -> None:
        self._stats.rate_limit_hits += 1
        self.release()

    async def on_error(self) -> None:
        self._stats.errors_total += 1
        self.release()

    @property
    def stats(self) -> RateLimiterStats:
        return self._stats

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.release()
