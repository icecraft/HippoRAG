#!/usr/bin/env python3
"""
Ingest novel chapters (list of strings) into HippoRAG with DGraph as graph storage.
Each element in the chapters list should be a chapter's content.

This version uses:
- DGraph for knowledge graph storage (distributed graph database)
- pgvector for embedding storage (PostgreSQL with pgvector extension)
- Supports multi-tenancy with book_id isolation

Prerequisites:
- DGraph server running (default: localhost:9080)
- PostgreSQL with pgvector extension installed
- Required Python packages: pydgraph, psycopg2-binary
"""

import os
import json
import argparse
import logging
from typing import List, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file if it exists
except ImportError:
    pass  # python-dotenv is optional

from hipporag import HippoRAG
from hipporag.utils.config_utils import BaseConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_chapters_from_file(filepath: str) -> List[str]:
    """
    Load chapters from a JSON file.
    Expected format: JSON array of strings, e.g., ["chapter1 text...", "chapter2 text..."]
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        chapters = json.load(f)
        if isinstance(chapters, list):
            return [str(ch) for ch in chapters if ch]
        else:
            raise ValueError("JSON file must contain an array of chapter strings")


def get_env_config():
    """Get configuration from environment variables (supports both new and legacy formats)."""
    # New standardized variables (preferred)
    llm_model = os.getenv('HIPPORAG_LLM_MODEL') or os.getenv('LLM_NAME', 'gpt-4o-mini')
    embedding_model = os.getenv('HIPPORAG_EMBEDDING_MODEL') or os.getenv('EMBEDDING_NAME', 'text-embedding-3-small')
    base_url = os.getenv('OPENAI_BASE_URL') or os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1')
    llm_base_url = os.getenv('HIPPORAG_LLM_BASE_URL') or os.getenv('LLM_BASE_URL') or base_url
    embedding_base_url = os.getenv('HIPPORAG_EMBEDDING_BASE_URL') or os.getenv('EMBEDDING_BASE_URL') or base_url

    return {
        'llm_model': llm_model,
        'embedding_model': embedding_model,
        'llm_base_url': llm_base_url,
        'embedding_base_url': embedding_base_url,
    }


def ingest_chapters(
    chapters: List[str],
    save_dir: str = 'outputs/novel',
    book_id: Optional[str] = None,
    llm_name: str = 'gpt-4o-mini',
    embedding_name: str = 'text-embedding-3-small',
    llm_base_url: str = 'https://api.openai.com/v1',
    embedding_base_url: str = None,
    force_index_from_scratch: bool = False,
    force_openie_from_scratch: bool = False,
    # DGraph configuration
    dgraph_host: str = 'localhost',
    dgraph_port: int = 9080,
    # pgvector configuration
    pgvector_host: str = 'localhost',
    pgvector_port: int = 5432,
    pgvector_database: str = 'hipporag',
    pgvector_user: str = 'postgres',
    pgvector_password: str = '',
    pgvector_index_type: str = 'ivfflat',
    pgvector_index_lists: int = 100
):
    """
    Ingest a list of chapter strings into HippoRAG with DGraph as graph storage.

    Args:
        chapters: List of strings, each element is a chapter's content
        save_dir: Directory to save the HippoRAG index
        book_id: Optional book identifier for multi-tenancy isolation
        llm_name: LLM model name
        embedding_name: Embedding model name
        llm_base_url: LLM API base URL
        embedding_base_url: Embedding API base URL (if not set, uses llm_base_url)
        force_index_from_scratch: If True, rebuild index from scratch
        force_openie_from_scratch: If True, rebuild OpenIE from scratch
        dgraph_host: DGraph server host (default: localhost)
        dgraph_port: DGraph server port (default: 9080)
        pgvector_host: PostgreSQL host
        pgvector_port: PostgreSQL port
        pgvector_database: PostgreSQL database name
        pgvector_user: PostgreSQL user
        pgvector_password: PostgreSQL password
        pgvector_index_type: Vector index type: 'ivfflat' or 'hnsw'
        pgvector_index_lists: Number of lists for IVFFlat index

    Returns:
        HippoRAG instance
    """
    logger.info(f"Number of chapters: {len(chapters)}")
    logger.info(f"Total characters: {sum(len(ch) for ch in chapters)}")

    # DGraph configuration
    dgraph_config = {
        "host": dgraph_host,
        "port": dgraph_port
    }

    logger.info("=" * 60)
    logger.info("Configuration:")
    logger.info("=" * 60)
    logger.info(f"  LLM: {llm_name}")
    logger.info(f"  Embedding: {embedding_name}")
    logger.info(f"  DGraph: {dgraph_host}:{dgraph_port}")
    logger.info(f"  PostgreSQL: {pgvector_user}@{pgvector_host}:{pgvector_port}/{pgvector_database}")
    if book_id:
        logger.info(f"  Book ID: {book_id}")
    logger.info("=" * 60)

    # Create config
    config = BaseConfig(
        save_dir=save_dir,
        llm_base_url=llm_base_url,
        embedding_base_url=embedding_base_url or llm_base_url,
        llm_name=llm_name,
        embedding_model_name=embedding_name,
        force_index_from_scratch=force_index_from_scratch,
        force_openie_from_scratch=force_openie_from_scratch,
        retrieval_top_k=200,
        linking_top_k=5,
        max_qa_steps=3,
        qa_top_k=5,
        graph_type="facts_and_sim_passage_node_unidirectional",
        embedding_batch_size=8,
        corpus_len=len(chapters),
        openie_mode="online",
        save_openie=True,
        # Graph library: use dgraph
        graph_library="dgraph",
        dgraph_config=dgraph_config,
        # pgvector configuration
        use_pgvector=True,
        pgvector_host=pgvector_host,
        pgvector_port=pgvector_port,
        pgvector_database=pgvector_database,
        pgvector_user=pgvector_user,
        pgvector_password=pgvector_password,
        pgvector_index_type=pgvector_index_type,
        pgvector_index_lists=pgvector_index_lists,
        # Multi-tenancy
        book_id=book_id
    )

    # Initialize HippoRAG
    logger.info("Initializing HippoRAG with DGraph...")
    hipporag = HippoRAG(global_config=config)

    # Index chapters
    logger.info("Starting indexing...")
    hipporag.index(docs=chapters)
    logger.info(f"Indexing complete! Index saved to: {save_dir}")
    logger.info(f"Graph stored in DGraph at {dgraph_host}:{dgraph_port}")

    return hipporag


def main():
    parser = argparse.ArgumentParser(
        description="Ingest novel chapters into HippoRAG with DGraph as graph storage"
    )
    parser.add_argument(
        '--chapters_file',
        type=str,
        default=None,
        help='Path to JSON file containing list of chapter strings. '
             'Format: ["chapter1 text...", "chapter2 text..."]'
    )
    parser.add_argument(
        '--save_dir',
        type=str,
        default='outputs/novel',
        help='Directory to save HippoRAG index (default: outputs/novel)'
    )
    parser.add_argument(
        '--book_id',
        type=str,
        default=None,
        help='Book identifier for multi-tenancy isolation (optional)'
    )
    parser.add_argument(
        '--force_index_from_scratch',
        action='store_true',
        help='Rebuild index from scratch (ignores existing index)'
    )
    parser.add_argument(
        '--force_openie_from_scratch',
        action='store_true',
        help='Rebuild OpenIE results from scratch'
    )

    # DGraph arguments
    parser.add_argument(
        '--dgraph_host',
        type=str,
        default=None,
        help='DGraph server host (default: from env or localhost)'
    )
    parser.add_argument(
        '--dgraph_port',
        type=int,
        default=None,
        help='DGraph server port (default: from env or 9080)'
    )

    # pgvector arguments
    parser.add_argument(
        '--pgvector_host',
        type=str,
        default=None,
        help='PostgreSQL host (default: from env or localhost)'
    )
    parser.add_argument(
        '--pgvector_port',
        type=int,
        default=None,
        help='PostgreSQL port (default: from env or 5432)'
    )
    parser.add_argument(
        '--pgvector_database',
        type=str,
        default=None,
        help='PostgreSQL database name (default: from env or hipporag)'
    )
    parser.add_argument(
        '--pgvector_user',
        type=str,
        default=None,
        help='PostgreSQL user (default: from env or postgres)'
    )
    parser.add_argument(
        '--pgvector_password',
        type=str,
        default=None,
        help='PostgreSQL password (default: from env)'
    )
    parser.add_argument(
        '--pgvector_index_type',
        type=str,
        choices=['ivfflat', 'hnsw'],
        default='ivfflat',
        help='Vector index type (default: ivfflat)'
    )
    parser.add_argument(
        '--pgvector_index_lists',
        type=int,
        default=100,
        help='Number of lists for IVFFlat index (default: 100)'
    )

    args = parser.parse_args()

    # Load configuration from environment
    env_config = get_env_config()

    # Parse DGraph config from env (format: host:port)
    dgraph_grpc = os.getenv('DGRAPH_GRPC', 'localhost:9080')
    dgraph_parts = dgraph_grpc.split(':')
    default_dgraph_host = dgraph_parts[0] if len(dgraph_parts) >= 1 else 'localhost'
    default_dgraph_port = int(dgraph_parts[1]) if len(dgraph_parts) >= 2 else 9080

    # Load chapters
    if args.chapters_file:
        logger.info(f"Loading chapters from: {args.chapters_file}")
        chapters = load_chapters_from_file(args.chapters_file)
    else:
        raise ValueError("Please provide chapters via --chapters_file. The file should contain a JSON array of chapter strings.")

    # Ingest chapters
    hipporag = ingest_chapters(
        chapters=chapters,
        save_dir=args.save_dir,
        book_id=args.book_id,
        llm_name=env_config['llm_model'],
        embedding_name=env_config['embedding_model'],
        llm_base_url=env_config['llm_base_url'],
        embedding_base_url=env_config['embedding_base_url'],
        force_index_from_scratch=args.force_index_from_scratch,
        force_openie_from_scratch=args.force_openie_from_scratch,
        # DGraph configuration
        dgraph_host=args.dgraph_host or default_dgraph_host,
        dgraph_port=args.dgraph_port or default_dgraph_port,
        # pgvector configuration
        pgvector_host=args.pgvector_host or os.getenv('PGVECTOR_HOST', 'localhost'),
        pgvector_port=args.pgvector_port or int(os.getenv('PGVECTOR_PORT', '5432')),
        pgvector_database=args.pgvector_database or os.getenv('PGVECTOR_DATABASE', 'hipporag'),
        pgvector_user=args.pgvector_user or os.getenv('PGVECTOR_USER', 'postgres'),
        pgvector_password=args.pgvector_password or os.getenv('PGVECTOR_PASSWORD', ''),
        pgvector_index_type=args.pgvector_index_type,
        pgvector_index_lists=args.pgvector_index_lists
    )

    logger.info("Done!")


if __name__ == "__main__":
    main()
