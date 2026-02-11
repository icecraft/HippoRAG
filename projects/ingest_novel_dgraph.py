#!/usr/bin/env python3
"""
Ingest novel chapters (list of strings) into HippoRAG with DGraph as graph storage.
Each element in the chapters list should be a chapter's content.

This version uses:
- DGraph for knowledge graph storage (distributed graph database)
- Optional: pgvector for embedding storage (PostgreSQL with pgvector extension)

Prerequisites:
- DGraph server running (default: localhost:9080)
- Optional: PostgreSQL with pgvector extension installed
- Required Python packages: pydgraph, psycopg2-binary (if using pgvector)
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


def ingest_chapters(
    chapters: List[str],
    save_dir: str = 'outputs/novel',
    llm_name: str = 'gpt-4o-mini',
    embedding_name: str = 'text-embedding-3-small',
    llm_base_url: str = 'https://api.openai.com/v1',
    embedding_base_url: str = None,
    force_index_from_scratch: bool = False,
    force_openie_from_scratch: bool = False,
    # DGraph configuration
    dgraph_host: str = 'localhost',
    dgraph_port: int = 9080,
    # Optional: pgvector configuration
    use_pgvector: bool = False,
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
        llm_name: LLM model name
        embedding_name: Embedding model name
        llm_base_url: LLM API base URL (e.g., https://dashscope.aliyuncs.com/compatible-mode/v1 for DashScope)
        embedding_base_url: Embedding API base URL (if not set, uses llm_base_url)
        force_index_from_scratch: If True, rebuild index from scratch
        force_openie_from_scratch: If True, rebuild OpenIE from scratch
        dgraph_host: DGraph server host (default: localhost)
        dgraph_port: DGraph server port (default: 9080)
        use_pgvector: Whether to use pgvector for embedding storage
        pgvector_host: PostgreSQL host (if using pgvector)
        pgvector_port: PostgreSQL port (if using pgvector)
        pgvector_database: PostgreSQL database name (if using pgvector)
        pgvector_user: PostgreSQL user (if using pgvector)
        pgvector_password: PostgreSQL password (if using pgvector)
        pgvector_index_type: Vector index type: 'ivfflat' or 'hnsw' (if using pgvector)
        pgvector_index_lists: Number of lists for IVFFlat index (if using pgvector)
    
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
    
    logger.info("DGraph configuration:")
    logger.info(f"  Host: {dgraph_host}")
    logger.info(f"  Port: {dgraph_port}")
    
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
        # Optional: pgvector configuration
        use_pgvector=use_pgvector,
        pgvector_host=pgvector_host if use_pgvector else '',
        pgvector_port=pgvector_port if use_pgvector else 5432,
        pgvector_database=pgvector_database if use_pgvector else '',
        pgvector_user=pgvector_user if use_pgvector else '',
        pgvector_password=pgvector_password if use_pgvector else '',
        pgvector_index_type=pgvector_index_type if use_pgvector else 'ivfflat',
        pgvector_index_lists=pgvector_index_lists if use_pgvector else 100
    )
    
    if use_pgvector:
        logger.info("pgvector configuration:")
        logger.info(f"  PostgreSQL: {pgvector_user}@{pgvector_host}:{pgvector_port}/{pgvector_database}")
        logger.info(f"  Index type: {pgvector_index_type}")
    
    print(config)
    
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
        default='localhost',
        help='DGraph server host (default: localhost)'
    )
    parser.add_argument(
        '--dgraph_port',
        type=int,
        default=19081,
        help='DGraph server port (default: 9080)'
    )
    
    # Optional pgvector arguments
    parser.add_argument(
        '--use_pgvector',
        action='store_true',
        help='Use pgvector for embedding storage (PostgreSQL with pgvector extension)'
    )
    parser.add_argument(
        '--pgvector_host',
        type=str,
        default='localhost',
        help='PostgreSQL host (default: localhost, only used with --use_pgvector)'
    )
    parser.add_argument(
        '--pgvector_port',
        type=int,
        default=5432,
        help='PostgreSQL port (default: 5432, only used with --use_pgvector)'
    )
    parser.add_argument(
        '--pgvector_database',
        type=str,
        default='test',
        help='PostgreSQL database name (default: hipporag, only used with --use_pgvector)'
    )
    parser.add_argument(
        '--pgvector_user',
        type=str,
        default='admin',
        help='PostgreSQL user (default: postgres, only used with --use_pgvector)'
    )
    parser.add_argument(
        '--pgvector_password',
        type=str,
        default='admin',
        help='PostgreSQL password (default: empty, only used with --use_pgvector)'
    )
    parser.add_argument(
        '--pgvector_index_type',
        type=str,
        choices=['ivfflat', 'hnsw'],
        default='ivfflat',
        help='Vector index type: ivfflat (memory-efficient) or hnsw (faster) (default: ivfflat)'
    )
    parser.add_argument(
        '--pgvector_index_lists',
        type=int,
        default=100,
        help='Number of lists for IVFFlat index (default: 100, only used with --pgvector_index_type=ivfflat)'
    )
    
    args = parser.parse_args()
    
    # Load configuration from .env file (with defaults if not set)
    llm_name = os.getenv('LLM_NAME', 'gpt-4o-mini')
    embedding_name = os.getenv('EMBEDDING_NAME', 'text-embedding-3-small')
    llm_base_url = os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1')
    embedding_base_url = os.getenv('EMBEDDING_BASE_URL') or llm_base_url
    
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
        llm_name=llm_name,
        embedding_name=embedding_name,
        llm_base_url=llm_base_url,
        embedding_base_url=embedding_base_url,
        force_index_from_scratch=args.force_index_from_scratch,
        force_openie_from_scratch=args.force_openie_from_scratch,
        # DGraph configuration
        dgraph_host=args.dgraph_host,
        dgraph_port=args.dgraph_port,
        # Optional pgvector configuration
        use_pgvector=args.use_pgvector,
        pgvector_host=args.pgvector_host,
        pgvector_port=args.pgvector_port,
        pgvector_database=args.pgvector_database,
        pgvector_user=args.pgvector_user,
        pgvector_password=args.pgvector_password,
        pgvector_index_type=args.pgvector_index_type,
        pgvector_index_lists=args.pgvector_index_lists
    )
    
    logger.info("Done!")


if __name__ == "__main__":
    main()

