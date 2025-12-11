"""FastAPI application factory."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
except ImportError:
    raise ImportError("FastAPI not installed. Run: pip install serp-aggregator[api]")

from .. import __version__
from .routes import router
from .deps import init_client, close_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler."""
    # Startup
    await init_client()
    yield
    # Shutdown
    await close_client()


def create_app(
    title: str = "SERP Aggregator API",
    cors_origins: list[str] | None = None,
) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        title: API title for OpenAPI docs
        cors_origins: Allowed CORS origins. None for no CORS.

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title=title,
        description="Search Engine Results Page aggregation API with deduplication",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Add CORS middleware if origins specified
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Include API routes
    app.include_router(router)

    # Health check at root
    @app.get("/health")
    async def health_check() -> dict:
        """Health check endpoint."""
        return {"status": "ok", "version": __version__}

    return app


# Default app instance for uvicorn
app = create_app()
