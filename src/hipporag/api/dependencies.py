"""
Dependency injection for HippoRAG API.

Manages HippoRAG instance and indexing status.
"""

import os
import logging
from typing import Optional, Dict

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from ..HippoRAG import HippoRAG
from ..utils.config_utils import BaseConfig

logger = logging.getLogger(__name__)

# Global HippoRAG instance
_hipporag_instance: Optional[HippoRAG] = None

# Global indexing status
_indexing_status: Dict[str, str] = {"status": "idle", "message": ""}


def get_indexing_status() -> Dict[str, str]:
    """Get the current indexing status."""
    return _indexing_status.copy()


def set_indexing_status(status: str, message: str) -> None:
    """Set the indexing status."""
    global _indexing_status
    _indexing_status = {"status": status, "message": message}


def get_hipporag() -> HippoRAG:
    """
    Get or create the global HippoRAG instance.

    The instance is configured via environment variables:
    - HIPPORAG_SAVE_DIR: Directory to save data
    - HIPPORAG_LLM_MODEL: LLM model name
    - OPENAI_BASE_URL: Unified base URL for both LLM and Embedding
    - HIPPORAG_LLM_BASE_URL: LLM base URL (overrides OPENAI_BASE_URL)
    - HIPPORAG_EMBEDDING_MODEL: Embedding model name
    - HIPPORAG_EMBEDDING_BASE_URL: Embedding base URL (overrides OPENAI_BASE_URL)
    - DGRAPH_GRPC: DGraph connection (host:port)
    - PGVECTOR_*: PostgreSQL/pgvector configuration
    """
    global _hipporag_instance
    if _hipporag_instance is None:
        logger.info("Initializing HippoRAG instance...")

        # Get unified base URL first, then allow specific overrides
        unified_base_url = os.getenv("OPENAI_BASE_URL")
        llm_base_url = os.getenv("HIPPORAG_LLM_BASE_URL") or unified_base_url
        embedding_base_url = os.getenv("HIPPORAG_EMBEDDING_BASE_URL") or unified_base_url

        # Parse DGraph connection
        dgraph_grpc = os.getenv("DGRAPH_GRPC", "localhost:9080")
        dgraph_host, dgraph_port = dgraph_grpc.rsplit(":", 1)
        dgraph_config = {
            "host": dgraph_host,
            "port": int(dgraph_port)
        }

        # Create config with all environment variables
        config = BaseConfig(
            save_dir=os.getenv("HIPPORAG_SAVE_DIR", "./outputs"),
            llm_base_url=llm_base_url,
            llm_name=os.getenv("HIPPORAG_LLM_MODEL", "gpt-4o-mini"),
            embedding_model_name=os.getenv("HIPPORAG_EMBEDDING_MODEL", "text-embedding-3-small"),
            embedding_base_url=embedding_base_url,
            # DGraph configuration
            graph_library="dgraph",
            dgraph_config=dgraph_config,
            # pgvector configuration
            use_pgvector=os.getenv("USE_PGVECTOR", "true").lower() == "true",
            pgvector_host=os.getenv("PGVECTOR_HOST", "localhost"),
            pgvector_port=int(os.getenv("PGVECTOR_PORT", "5432")),
            pgvector_database=os.getenv("PGVECTOR_DATABASE", "hipporag"),
            pgvector_user=os.getenv("PGVECTOR_USER", "postgres"),
            pgvector_password=os.getenv("PGVECTOR_PASSWORD", ""),
            # Force rebuild index if dimension mismatch
            force_index_from_scratch=os.getenv("FORCE_INDEX_FROM_SCRATCH", "false").lower() == "true",
            # Embedding batch size (阿里云限制为10)
            embedding_batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "10")),
        )

        _hipporag_instance = HippoRAG(global_config=config)
        logger.info("HippoRAG instance initialized successfully")
    return _hipporag_instance


def is_hipporag_initialized() -> bool:
    """Check if HippoRAG instance is initialized."""
    return _hipporag_instance is not None


def reset_hipporag() -> None:
    """
    Reset the HippoRAG instance.

    This is useful for testing or when configuration needs to be reloaded.
    """
    global _hipporag_instance
    _hipporag_instance = None
    logger.info("HippoRAG instance reset")
