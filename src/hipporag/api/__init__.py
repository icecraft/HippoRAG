"""
HippoRAG RESTful API Module.

This module provides a FastAPI-based REST API for HippoRAG.

Usage:
    # Start the server with uvicorn
    uvicorn hipporag.api:app --host 0.0.0.0 --port 8000

    # Or run directly
    python -m hipporag.api --host 0.0.0.0 --port 8000

Environment Variables:
    HIPPORAG_SAVE_DIR: Directory to save data (default: ./outputs)
    HIPPORAG_LLM_MODEL: LLM model name (default: gpt-4o-mini)
    HIPPORAG_LLM_BASE_URL: LLM base URL for custom endpoints
    HIPPORAG_EMBEDDING_MODEL: Embedding model name (default: text-embedding-3-small)
    HIPPORAG_EMBEDDING_BASE_URL: Embedding base URL for custom endpoints

API Endpoints:
    GET  /              - API information
    GET  /health        - Health check
    GET  /status        - Indexing status
    POST /index         - Index documents (async)
    POST /index/sync    - Index documents (sync)
    POST /retrieve      - HippoRAG retrieval
    POST /retrieve/dpr  - DPR retrieval
    POST /qa            - HippoRAG QA
    POST /qa/dpr        - DPR QA
"""

from .app import app, create_app, run_server

__all__ = ["app", "create_app", "run_server"]
