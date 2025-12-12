"""Typer CLI for SERP Aggregator."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

try:
    import typer
    from rich.console import Console
    from rich.table import Table
except ImportError:
    print("CLI dependencies not installed. Run: pip install serp-aggregator[cli]")
    sys.exit(1)

from .. import (
    SerpAggregator,
    SerpSettings,
    StderrProgress,
    NullProgress,
)
from ..exceptions import SerpError
from .debug import save_debug_json, save_debug_csv, save_debug_raw

app = typer.Typer(
    name="serp",
    help="SERP API Aggregator - Search result collection and deduplication",
    no_args_is_help=True,
)
console = Console(stderr=True)


def get_progress(quiet: bool, verbose: bool) -> StderrProgress | NullProgress:
    """Get progress reporter based on flags."""
    if quiet:
        return NullProgress()
    return StderrProgress(verbose=verbose)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    max_pages: int = typer.Option(25, "--max-pages", "-p", help="Maximum pages to fetch"),
    concurrency: int = typer.Option(50, "--concurrency", "-c", help="Concurrent requests"),
    country: str = typer.Option("us", "--country", "-g", help="Country code (gl)"),
    language: str = typer.Option("en", "--language", "-l", help="Language code (hl)"),
    output_format: str = typer.Option("json", "--format", "-f", help="Output format: json, ndjson, csv"),
    output_file: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Disable cache"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress progress output"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose progress output"),
    debug_json: bool = typer.Option(False, "--debug-json", help="Save JSON to ./debug/"),
    debug_csv: bool = typer.Option(False, "--debug-csv", help="Save CSV to ./debug/"),
    debug_raw: bool = typer.Option(False, "--debug-raw", help="Save raw API responses to ./debug/"),
):
    """
    Execute a single search query.

    Examples:
        serp search "python tutorial" --max-pages 10
        serp search "machine learning" -p 5 -o results.json
        serp search "data science" --format csv
    """
    async def run():
        progress = get_progress(quiet, verbose)
        raw_collector: list[dict] = [] if debug_raw else []

        async with SerpAggregator(progress=progress) as client:
            result = await client.search(
                query,
                max_pages=max_pages,
                concurrency=concurrency,
                country=country,
                language=language,
                use_cache=not no_cache,
                raw_collector=raw_collector if debug_raw else None,
            )
            return result, raw_collector

    try:
        result, raw_collector = asyncio.run(run())

        # Save debug outputs
        if debug_json:
            debug_path = save_debug_json(result, query)
            console.print(f"[dim]Debug JSON: {debug_path}[/dim]")
        if debug_csv:
            debug_path = save_debug_csv(result, query)
            console.print(f"[dim]Debug CSV: {debug_path}[/dim]")
        if debug_raw and raw_collector:
            debug_path = save_debug_raw(raw_collector, query)
            console.print(f"[dim]Debug raw: {debug_path}[/dim]")

        # Format output
        if output_format == "json":
            output = result.model_dump_json(indent=2)
        elif output_format == "ndjson":
            output = result.model_dump_json()
        elif output_format == "csv":
            import csv
            import io
            buffer = io.StringIO()
            writer = csv.DictWriter(
                buffer,
                fieldnames=["link", "title", "description", "best_position", "frequency"],
            )
            writer.writeheader()
            for item in result.organic:
                writer.writerow({
                    "link": str(item.link),
                    "title": item.title,
                    "description": item.description or "",
                    "best_position": item.best_position,
                    "frequency": item.frequency,
                })
            output = buffer.getvalue()
        else:
            output = result.model_dump_json(indent=2)

        # Write output
        if output_file:
            output_file.write_text(output)
            console.print(f"[green]Results saved to {output_file}[/green]")
        else:
            print(output)

        if not quiet:
            console.print(f"\n[dim]Found {len(result.organic)} organic results[/dim]")

    except SerpError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def batch(
    queries: Optional[list[str]] = typer.Argument(None, help="Queries to search"),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="File with queries (one per line)"),
    max_pages: int = typer.Option(25, "--max-pages", "-p"),
    concurrency: int = typer.Option(50, "--concurrency", "-c"),
    country: str = typer.Option("us", "--country", "-g"),
    language: str = typer.Option("en", "--language", "-l"),
    output_format: str = typer.Option("json", "--format", "-o", help="Output format: json, ndjson"),
    output_file: Optional[Path] = typer.Option(None, "--output", help="Output file path"),
    parallel: bool = typer.Option(False, "--parallel", help="Run queries in parallel"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    quiet: bool = typer.Option(False, "--quiet", "-q"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    debug_json: bool = typer.Option(False, "--debug-json", help="Save JSON to ./debug/"),
    debug_csv: bool = typer.Option(False, "--debug-csv", help="Save CSV to ./debug/"),
    debug_raw: bool = typer.Option(False, "--debug-raw", help="Save raw API responses to ./debug/"),
):
    """
    Execute batch search queries.

    Examples:
        serp batch "query1" "query2" --max-pages 10
        serp batch --file queries.txt --parallel
        echo -e "query1\\nquery2" | serp batch
    """
    # Collect queries from various sources
    query_list: list[str] = []

    if queries:
        query_list = list(queries)
    elif file:
        query_list = [line.strip() for line in file.read_text().splitlines() if line.strip()]
    elif not sys.stdin.isatty():
        query_list = [line.strip() for line in sys.stdin if line.strip()]

    if not query_list:
        console.print("[red]Error:[/red] No queries provided")
        console.print("Usage: serp batch \"query1\" \"query2\" or serp batch --file queries.txt")
        raise typer.Exit(1)

    async def run():
        progress = get_progress(quiet, verbose)
        raw_collector: list[dict] = [] if debug_raw else []

        async with SerpAggregator(progress=progress) as client:
            if parallel:
                result = await client.search_parallel(
                    query_list,
                    max_pages=max_pages,
                    concurrency=concurrency,
                    country=country,
                    language=language,
                    use_cache=not no_cache,
                    raw_collector=raw_collector if debug_raw else None,
                )
            else:
                result = await client.search_batch(
                    query_list,
                    max_pages=max_pages,
                    concurrency=concurrency,
                    country=country,
                    language=language,
                    use_cache=not no_cache,
                    raw_collector=raw_collector if debug_raw else None,
                )
            return result, raw_collector

    try:
        result, raw_collector = asyncio.run(run())

        # Save debug outputs for each query
        if debug_json or debug_csv:
            for query, search_result in result.results.items():
                if debug_json:
                    debug_path = save_debug_json(search_result, query)
                    console.print(f"[dim]Debug JSON ({query}): {debug_path}[/dim]")
                if debug_csv:
                    debug_path = save_debug_csv(search_result, query)
                    console.print(f"[dim]Debug CSV ({query}): {debug_path}[/dim]")
        if debug_raw and raw_collector:
            # For batch, save all raw responses together
            # Use first query as filename base
            first_query = query_list[0] if query_list else "batch"
            debug_path = save_debug_raw(raw_collector, first_query)
            console.print(f"[dim]Debug raw (all queries): {debug_path}[/dim]")

        # Format output
        if output_format == "json":
            output = result.model_dump_json(indent=2)
        elif output_format == "ndjson":
            lines = []
            for query, search_result in result.results.items():
                lines.append(search_result.model_dump_json())
            output = "\n".join(lines)
        else:
            output = result.model_dump_json(indent=2)

        # Write output
        if output_file:
            output_file.write_text(output)
            console.print(f"[green]Results saved to {output_file}[/green]")
        else:
            print(output)

        if not quiet:
            console.print(f"\n[dim]Completed {len(result.results)} queries, {result.total_organic} total results in {result.total_elapsed_seconds}s[/dim]")

    except SerpError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
    workers: int = typer.Option(1, "--workers", "-w", help="Number of workers"),
):
    """
    Start the REST API server.

    Examples:
        serp serve --port 8080
        serp serve --reload  # Development mode
    """
    try:
        import uvicorn
    except ImportError:
        console.print("[red]API dependencies not installed. Run: pip install serp-aggregator[api][/red]")
        raise typer.Exit(1)

    console.print(f"[green]Starting SERP API server on {host}:{port}[/green]")

    uvicorn.run(
        "serp.api.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,
    )


@app.command()
def stats():
    """
    Show cache and rate limiter statistics.
    """
    # This would require a running client, so just show info
    console.print("[yellow]Statistics are only available during runtime.[/yellow]")
    console.print("\nUse the following in your code:")
    console.print("  client.cache.stats       # Cache statistics")
    console.print("  client.rate_limiter.stats  # Rate limiter statistics")


@app.command()
def version():
    """Show version information."""
    from .. import __version__
    console.print(f"serp-aggregator v{__version__}")


def main():
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
