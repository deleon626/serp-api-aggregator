"""SERP API exception hierarchy."""

from typing import Any


class SerpError(Exception):
    """Base exception for all SERP operations."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class SerpConfigError(SerpError):
    """Configuration or settings error."""

    pass


class SerpValidationError(SerpError):
    """Input validation error."""

    def __init__(self, message: str, field: str | None = None, value: Any = None):
        super().__init__(message, {"field": field, "value": value})
        self.field = field
        self.value = value


class SerpAPIError(SerpError):
    """API communication error."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_id: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, details)
        self.status_code = status_code
        self.response_id = response_id


class SerpTimeoutError(SerpAPIError):
    """Request or polling timeout."""

    def __init__(
        self,
        message: str = "Request timed out",
        response_id: str | None = None,
        elapsed_seconds: float | None = None,
    ):
        super().__init__(message, response_id=response_id)
        self.elapsed_seconds = elapsed_seconds


class SerpRateLimitError(SerpAPIError):
    """Rate limit exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        status_code: int = 429,
        retry_after: float | None = None,
    ):
        super().__init__(message, status_code=status_code)
        self.retry_after = retry_after


class SerpCacheError(SerpError):
    """Cache operation error."""

    pass
