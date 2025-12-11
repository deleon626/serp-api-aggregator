"""Configuration via pydantic-settings with environment variable support."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class SerpSettings(BaseSettings):
    """
    SERP Aggregator configuration.

    All settings can be configured via environment variables with SERP_ prefix.

    Example:
        export SERP_BRIGHT_DATA_API_KEY="your-key"
        export SERP_DEFAULT_MAX_PAGES=10
    """

    model_config = SettingsConfigDict(
        env_prefix="SERP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Configuration
    bright_data_api_key: SecretStr = Field(
        ...,
        description="Bright Data API key (required)",
    )
    bright_data_zone: str = Field(
        default="serp_api1",
        description="Bright Data zone name",
    )
    api_base_url: str = Field(
        default="https://api.brightdata.com",
        description="Bright Data API base URL",
    )

    # Search defaults
    default_country: str = Field(
        default="us",
        description="Default country code (gl parameter)",
        pattern=r"^[a-z]{2}$",
    )
    default_language: str = Field(
        default="en",
        description="Default language code (hl parameter)",
        pattern=r"^[a-z]{2}(-[a-z]{2})?$",
    )

    # Processing defaults
    default_max_pages: int = Field(
        default=25,
        ge=1,
        le=100,
        description="Default maximum pages per query",
    )
    default_concurrency: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Default concurrent requests",
    )

    # API polling configuration
    poll_interval: float = Field(
        default=2.0,
        ge=0.5,
        le=10.0,
        description="Seconds between poll attempts",
    )
    max_polls: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum poll attempts before timeout",
    )
    request_timeout: float = Field(
        default=30.0,
        ge=5.0,
        le=120.0,
        description="HTTP request timeout in seconds",
    )

    # Retry configuration
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts on failure",
    )
    retry_backoff: float = Field(
        default=2.0,
        ge=1.0,
        le=5.0,
        description="Exponential backoff multiplier",
    )

    # Rate limiting
    rate_limit_enabled: bool = Field(
        default=True,
        description="Enable adaptive rate limiting",
    )
    rate_limit_rps: float = Field(
        default=5.0,
        ge=0.1,
        le=50.0,
        description="Initial requests per second limit",
    )
    rate_limit_burst: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum burst size",
    )

    # Caching
    cache_enabled: bool = Field(
        default=True,
        description="Enable result caching",
    )
    cache_ttl: int = Field(
        default=3600,
        ge=0,
        le=86400,
        description="Cache TTL in seconds (0 = no expiry)",
    )
    cache_backend: Literal["memory", "redis"] = Field(
        default="memory",
        description="Cache backend type",
    )
    redis_url: str | None = Field(
        default=None,
        description="Redis URL for cache (if cache_backend=redis)",
    )

    # Early termination
    consecutive_empty_limit: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Stop after N consecutive empty pages",
    )

    @property
    def max_poll_time(self) -> float:
        """Maximum total polling time in seconds."""
        return self.poll_interval * self.max_polls


@lru_cache
def get_settings() -> SerpSettings:
    """
    Get cached settings singleton.

    Settings are loaded from environment variables and .env file.

    Returns:
        SerpSettings instance

    Raises:
        ValidationError: If required settings are missing or invalid
    """
    return SerpSettings()


def get_settings_uncached() -> SerpSettings:
    """
    Get fresh settings without caching.

    Useful for testing or when settings may have changed.
    """
    return SerpSettings()
