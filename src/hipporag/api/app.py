"""
FastAPI application for HippoRAG API.

Creates and configures the FastAPI app with CORS middleware and lifespan management.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router
from .dependencies import get_hipporag

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler for startup and shutdown events.

    Initializes HippoRAG on startup and cleans up on shutdown.
    """
    # Startup: Initialize HippoRAG
    logger.info("Starting HippoRAG API...")
    try:
        get_hipporag()
        logger.info("HippoRAG initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize HippoRAG: {e}")
    yield
    # Shutdown: Cleanup if needed
    logger.info("Shutting down HippoRAG API")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        FastAPI: Configured FastAPI application instance
    """
    app = FastAPI(
        title="HippoRAG API",
        description="""
RESTful API for HippoRAG - A graph-based RAG framework.

## Features
- **Document Indexing**: Index documents into the knowledge graph
- **Graph-based Retrieval**: Multi-hop reasoning with HippoRAG
- **Standard DPR Retrieval**: Dense passage retrieval
- **Question Answering**: RAG-based QA with LLM

## Usage
1. Index documents using `/index` or `/index/sync`
2. Query using `/retrieve` or `/qa` endpoints
        """,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root():
        """Root endpoint returning API information."""
        return {
            "name": "HippoRAG API",
            "version": "1.0.0",
            "docs": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json"
        }

    # Include API routes
    app.include_router(router)

    return app


# Create the application instance
app = create_app()


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """
    Run the API server.

    Args:
        host: Host to bind to (default: "0.0.0.0")
        port: Port to bind to (default: 8000)
    """
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="HippoRAG API Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")

    args = parser.parse_args()
    run_server(host=args.host, port=args.port)
