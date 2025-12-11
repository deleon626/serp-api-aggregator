"""Pydantic models for SERP data structures."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


class SearchParams(BaseModel):
    """Search request parameters."""

    query: str = Field(..., min_length=1, max_length=500, description="Search query string")
    country: str = Field(default="us", pattern=r"^[a-z]{2}$", description="Country code (gl)")
    language: str = Field(
        default="en", pattern=r"^[a-z]{2}(-[a-z]{2})?$", description="Language code (hl)"
    )
    max_pages: int = Field(default=25, ge=1, le=100, description="Maximum pages to fetch")
    concurrency: int = Field(default=50, ge=1, le=200, description="Concurrent requests")
    search_type: Literal["web", "images", "news", "shopping", "videos"] = Field(
        default="web", description="Type of search"
    )

    @field_validator("query")
    @classmethod
    def strip_query(cls, v: str) -> str:
        return v.strip()


class OrganicResult(BaseModel):
    """Single organic search result with deduplication metadata."""

    link: str = Field(..., description="URL of the result")
    title: str = Field(default="", description="Title of the result")
    description: str | None = Field(default=None, description="Snippet/description")
    rank: int = Field(default=0, description="Original rank position")
    best_position: int = Field(default=0, description="Best position seen across pages")
    avg_position: float = Field(default=0.0, description="Average position across pages")
    frequency: int = Field(default=1, description="Times URL appeared across pages")
    pages_seen: list[int] = Field(default_factory=list, description="Pages where URL was found")

    model_config = {"extra": "allow"}


class RelatedSearch(BaseModel):
    """Related search suggestion."""

    text: str = Field(..., description="Related search text")
    link: str = Field(default="", description="Search URL")
    rank: int = Field(default=0, description="Rank in related searches")


class PaginationItem(BaseModel):
    """Pagination link."""

    link: str = Field(default="", description="Pagination URL")
    page: str = Field(default="", description="Page number")
    page_html: str | None = Field(default=None)


class NavigationItem(BaseModel):
    """Navigation tab (Images, Videos, etc.)."""

    title: str = Field(default="", description="Tab title")
    link: str = Field(default="", description="Tab URL")


class GeneralMetadata(BaseModel):
    """Search metadata from Bright Data response."""

    query: str = Field(default="", description="Search query")
    datetime: str | None = Field(default=None, description="Search timestamp")
    language: str | None = Field(default=None, description="Result language")
    location: str | None = Field(default=None, description="Geographic location")
    search_engine: str = Field(default="google", description="Search engine used")
    search_type: str = Field(default="text", description="Type of search")
    page_title: str | None = Field(default=None, description="SERP page title")

    model_config = {"extra": "allow"}


class SearchResult(BaseModel):
    """Complete search result matching Bright Data schema with dedup metadata."""

    # Bright Data fields
    url: str | None = Field(default=None, description="Search URL")
    keyword: str | None = Field(default=None)
    general: GeneralMetadata = Field(default_factory=GeneralMetadata)
    organic: list[OrganicResult] = Field(default_factory=list)
    related: list[RelatedSearch | dict[str, Any]] = Field(default_factory=list)
    people_also_ask: list[str] = Field(default_factory=list)
    pagination: list[PaginationItem | dict[str, Any]] = Field(default_factory=list)
    navigation: list[NavigationItem | dict[str, Any]] = Field(default_factory=list)
    language: str | None = Field(default=None)
    country: str | None = Field(default=None)
    page_html: str | None = Field(default=None)
    aio_text: str | None = Field(default=None, description="AI Overview text")

    # Aggregation metadata
    pages_fetched: int = Field(default=0, description="Number of pages fetched")
    errors: list[str] = Field(default_factory=list, description="Errors during fetch")

    model_config = {"extra": "allow"}

    @property
    def organic_count(self) -> int:
        """Number of organic results."""
        return len(self.organic)

    @property
    def has_errors(self) -> bool:
        """Whether any errors occurred."""
        return len(self.errors) > 0


class BatchSearchParams(BaseModel):
    """Batch search request parameters."""

    queries: list[str] = Field(..., min_length=1, description="List of search queries")
    country: str = Field(default="us", pattern=r"^[a-z]{2}$")
    language: str = Field(default="en", pattern=r"^[a-z]{2}(-[a-z]{2})?$")
    max_pages: int = Field(default=25, ge=1, le=100)
    concurrency: int = Field(default=50, ge=1, le=200)


class QueryTiming(BaseModel):
    """Timing information for a single query."""

    query: str
    elapsed_seconds: float
    result_count: int
    pages_fetched: int
    errors: int = 0


class BatchResult(BaseModel):
    """Result of batch search operation."""

    queries: list[str] = Field(default_factory=list)
    results: dict[str, SearchResult] = Field(default_factory=dict)
    timing: dict[str, float] = Field(default_factory=dict)
    total_organic: int = Field(default=0)
    total_elapsed_seconds: float = Field(default=0.0)
    query_timings: list[QueryTiming] = Field(default_factory=list)

    model_config = {"extra": "allow"}

    @property
    def success_count(self) -> int:
        """Number of successful queries."""
        return sum(1 for r in self.results.values() if not r.has_errors)

    @property
    def error_count(self) -> int:
        """Number of queries with errors."""
        return sum(1 for r in self.results.values() if r.has_errors)
