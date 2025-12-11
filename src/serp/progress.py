"""Progress reporting protocol and implementations."""

import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Protocol, runtime_checkable


@dataclass
class ProgressEvent:
    """Progress event data."""

    query: str
    page: int
    total_pages: int
    results_count: int
    status: str  # "fetching", "complete", "error", "cached"
    message: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def progress_pct(self) -> float:
        """Progress percentage (0-100)."""
        if self.total_pages == 0:
            return 0.0
        return (self.page / self.total_pages) * 100


@runtime_checkable
class ProgressReporter(Protocol):
    """Protocol for progress reporting during search operations."""

    def on_query_start(self, query: str, total_pages: int) -> None:
        """Called when a query starts processing."""
        ...

    def on_page_complete(self, event: ProgressEvent) -> None:
        """Called when a page fetch completes."""
        ...

    def on_query_complete(self, query: str, total_results: int, elapsed_seconds: float) -> None:
        """Called when a query completes all pages."""
        ...

    def on_error(self, query: str, error: str, page: int | None = None) -> None:
        """Called on error."""
        ...

    def on_cache_hit(self, query: str) -> None:
        """Called when result is returned from cache."""
        ...


class NullProgress:
    """No-op progress reporter (silent)."""

    def on_query_start(self, query: str, total_pages: int) -> None:
        pass

    def on_page_complete(self, event: ProgressEvent) -> None:
        pass

    def on_query_complete(self, query: str, total_results: int, elapsed_seconds: float) -> None:
        pass

    def on_error(self, query: str, error: str, page: int | None = None) -> None:
        pass

    def on_cache_hit(self, query: str) -> None:
        pass


class StderrProgress:
    """Progress reporter that writes to stderr."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def _log(self, message: str) -> None:
        print(message, file=sys.stderr, flush=True)

    def on_query_start(self, query: str, total_pages: int) -> None:
        self._log(f"[SERP] Query: '{query}' - Fetching up to {total_pages} pages...")

    def on_page_complete(self, event: ProgressEvent) -> None:
        if self.verbose:
            status = f"{event.results_count} results" if event.status == "complete" else event.status
            self._log(f"[SERP]   Page {event.page}/{event.total_pages}: {status}")

    def on_query_complete(self, query: str, total_results: int, elapsed_seconds: float) -> None:
        self._log(f"[SERP] Query: '{query}' - Done: {total_results} results in {elapsed_seconds:.1f}s")

    def on_error(self, query: str, error: str, page: int | None = None) -> None:
        if page:
            self._log(f"[SERP] Query: '{query}' - Page {page} ERROR: {error}")
        else:
            self._log(f"[SERP] Query: '{query}' - ERROR: {error}")

    def on_cache_hit(self, query: str) -> None:
        self._log(f"[SERP] Query: '{query}' - Cache hit")


class CallbackProgress:
    """Progress reporter that calls user-provided callbacks."""

    def __init__(
        self,
        on_start: Callable | None = None,
        on_page: Callable | None = None,
        on_complete: Callable | None = None,
        on_error: Callable | None = None,
    ):
        self._on_start = on_start
        self._on_page = on_page
        self._on_complete = on_complete
        self._on_error = on_error

    def on_query_start(self, query: str, total_pages: int) -> None:
        if self._on_start:
            self._on_start(query, total_pages)

    def on_page_complete(self, event: ProgressEvent) -> None:
        if self._on_page:
            self._on_page(event)

    def on_query_complete(self, query: str, total_results: int, elapsed_seconds: float) -> None:
        if self._on_complete:
            self._on_complete(query, total_results, elapsed_seconds)

    def on_error(self, query: str, error: str, page: int | None = None) -> None:
        if self._on_error:
            self._on_error(query, error, page)

    def on_cache_hit(self, query: str) -> None:
        pass


class AggregatingProgress:
    """Progress reporter that aggregates events for batch operations."""

    def __init__(self):
        self.events: list[ProgressEvent] = []
        self.query_starts: dict[str, datetime] = {}
        self.query_results: dict[str, int] = {}
        self.errors: list[tuple[str, str, int | None]] = []

    def on_query_start(self, query: str, total_pages: int) -> None:
        self.query_starts[query] = datetime.now()

    def on_page_complete(self, event: ProgressEvent) -> None:
        self.events.append(event)

    def on_query_complete(self, query: str, total_results: int, elapsed_seconds: float) -> None:
        self.query_results[query] = total_results

    def on_error(self, query: str, error: str, page: int | None = None) -> None:
        self.errors.append((query, error, page))

    def on_cache_hit(self, query: str) -> None:
        pass

    @property
    def total_pages_fetched(self) -> int:
        return len(self.events)

    @property
    def total_results(self) -> int:
        return sum(self.query_results.values())

    @property
    def error_count(self) -> int:
        return len(self.errors)
