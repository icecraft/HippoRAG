#!/usr/bin/env python3
"""
Ingest novel chapters (list of strings) into HippoRAG using pgvector and Nebula Graph.
Each element in the chapters list should be a chapter's content.

This version uses:
- pgvector for embedding storage (PostgreSQL with pgvector extension)
- Nebula Graph for knowledge graph storage

Prerequisites:
- PostgreSQL with pgvector extension installed
- Nebula Graph server running
- Required Python packages: psycopg2-binary, nebula3-python
"""

import os
import json
import argparse
import logging
from typing import List

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
    # pgvector configuration
    use_pgvector: bool = True,
    pgvector_host: str = 'localhost',
    pgvector_port: int = 5432,
    pgvector_database: str = 'hipporag',
    pgvector_user: str = 'postgres',
    pgvector_password: str = '',
    pgvector_index_type: str = 'ivfflat',
    pgvector_index_lists: int = 100,
    # Nebula Graph configuration
    use_nebula_graph: bool = True,
    nebula_host: str = '127.0.0.1',
    nebula_port: int = 9669,
    nebula_user: str = 'root',
    nebula_password: str = 'nebula',
    nebula_space_name: str = 'hipporag'
):
    """
    Ingest a list of chapter strings into HippoRAG using pgvector and Nebula Graph.
    
    Args:
        chapters: List of strings, each element is a chapter's content
        save_dir: Directory to save the HippoRAG index (still used for some metadata)
        llm_name: LLM model name
        embedding_name: Embedding model name
        llm_base_url: LLM API base URL (e.g., https://dashscope.aliyuncs.com/compatible-mode/v1 for DashScope)
        embedding_base_url: Embedding API base URL (if not set, uses llm_base_url)
        force_index_from_scratch: If True, rebuild index from scratch
        force_openie_from_scratch: If True, rebuild OpenIE from scratch
        # pgvector parameters
        use_pgvector: Whether to use pgvector for embedding storage
        pgvector_host: PostgreSQL host
        pgvector_port: PostgreSQL port
        pgvector_database: PostgreSQL database name
        pgvector_user: PostgreSQL user
        pgvector_password: PostgreSQL password
        pgvector_index_type: Vector index type ('ivfflat' or 'hnsw')
        pgvector_index_lists: Number of lists for IVFFlat index
        # Nebula Graph parameters
        use_nebula_graph: Whether to use Nebula Graph for graph storage
        nebula_host: Nebula Graph graphd host
        nebula_port: Nebula Graph graphd port
        nebula_user: Nebula Graph user
        nebula_password: Nebula Graph password
        nebula_space_name: Nebula Graph space name
    
    Returns:
        HippoRAG instance
    """
    logger.info(f"Number of chapters: {len(chapters)}")
    logger.info(f"Total characters: {sum(len(ch) for ch in chapters)}")
    
    # Create config with pgvector and Nebula Graph enabled
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
        # pgvector configuration
        use_pgvector=use_pgvector,
        pgvector_host=pgvector_host,
        pgvector_port=pgvector_port,
        pgvector_database=pgvector_database,
        pgvector_user=pgvector_user,
        pgvector_password=pgvector_password,
        pgvector_index_type=pgvector_index_type,
        pgvector_index_lists=pgvector_index_lists,
        # Nebula Graph configuration
        use_nebula_graph=use_nebula_graph,
        nebula_host=nebula_host,
        nebula_port=nebula_port,
        nebula_user=nebula_user,
        nebula_password=nebula_password,
        nebula_space_name=nebula_space_name
    )
    
    logger.info("Configuration:")
    logger.info(f"  - Using pgvector: {use_pgvector}")
    if use_pgvector:
        logger.info(f"    PostgreSQL: {pgvector_user}@{pgvector_host}:{pgvector_port}/{pgvector_database}")
        logger.info(f"    Index type: {pgvector_index_type}")
    logger.info(f"  - Using Nebula Graph: {use_nebula_graph}")
    if use_nebula_graph:
        logger.info(f"    Nebula Graph: {nebula_user}@{nebula_host}:{nebula_port}")
        logger.info(f"    Space name: {nebula_space_name}")
    
    # Initialize HippoRAG
    logger.info("Initializing HippoRAG with pgvector and Nebula Graph...")
    hipporag = HippoRAG(global_config=config)
    
    # Index chapters
    logger.info("Starting indexing...")
    logger.info("Embeddings will be stored in pgvector, graph will be stored in Nebula Graph")
    hipporag.index(docs=chapters)
    logger.info(f"Indexing complete!")
    if use_pgvector:
        logger.info(f"Embeddings stored in PostgreSQL database: {pgvector_database}")
    if use_nebula_graph:
        logger.info(f"Knowledge graph stored in Nebula Graph space: {nebula_space_name}")
    
    return hipporag


def main():
    parser = argparse.ArgumentParser(
        description="Ingest novel chapters into HippoRAG using pgvector and Nebula Graph"
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
        help='Directory to save HippoRAG metadata (default: outputs/novel)'
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
    
    # pgvector arguments
    parser.add_argument(
        '--pgvector_host',
        type=str,
        default='127.0.0.1',
        help='PostgreSQL host (default: from env PGVECTOR_HOST or localhost)'
    )
    parser.add_argument(
        '--pgvector_port',
        type=int,
        default='5432',
        help='PostgreSQL port (default: from env PGVECTOR_PORT or 5432)'
    )
    parser.add_argument(
        '--pgvector_database',
        type=str,
        default='hipporag',
        help='PostgreSQL database name (default: from env PGVECTOR_DATABASE or hipporag)'
    )
    parser.add_argument(
        '--pgvector_user',
        type=str,
        default='admin',
        help='PostgreSQL user (default: from env PGVECTOR_USER or postgres)'
    )
    parser.add_argument(
        '--pgvector_password',
        type=str,
        default='admin',
        help='PostgreSQL password (default: from env PGVECTOR_PASSWORD or empty)'
    )
    parser.add_argument(
        '--pgvector_index_type',
        type=str,
        choices=['ivfflat', 'hnsw'],
        default='ivfflat',
        help='Vector index type: ivfflat (memory-efficient) or hnsw (faster) (default: from env or ivfflat)'
    )
    parser.add_argument(
        '--pgvector_index_lists',
        type=int,
        default=None,
        help='Number of lists for IVFFlat index (default: from env or 100)'
    )
    parser.add_argument(
        '--no_pgvector',
        action='store_true',
        help='Disable pgvector (use Parquet files instead)'
    )
    
    # Nebula Graph arguments
    parser.add_argument(
        '--nebula_host',
        type=str,
        default='127.0.0.1',
        help='Nebula Graph graphd host (default: from env NEBULA_HOST or 127.0.0.1)'
    )
    parser.add_argument(
        '--nebula_port',
        type=int,
        default='9669',
        help='Nebula Graph graphd port (default: from env NEBULA_PORT or 9669)'
    )
    parser.add_argument(
        '--nebula_user',
        type=str,
        default='root',
        help='Nebula Graph user (default: from env NEBULA_USER or root)'
    )
    parser.add_argument(
        '--nebula_password',
        type=str,
        default='any',
        help='Nebula Graph password (default: from env NEBULA_PASSWORD or nebula)'
    )
    parser.add_argument(
        '--nebula_space_name',
        type=str,
        default='hipporag',
        help='Nebula Graph space name (default: from env NEBULA_SPACE_NAME or hipporag)'
    )
    parser.add_argument(
        '--no_nebula',
        action='store_true',
        help='Disable Nebula Graph (use pickle files instead)'
    )
    
    args = parser.parse_args()
    
    # Load configuration from .env file (with defaults if not set)
    llm_name = os.getenv('LLM_NAME', 'gpt-4o-mini')
    embedding_name = os.getenv('EMBEDDING_NAME', 'text-embedding-3-small')
    llm_base_url = os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1')
    embedding_base_url = os.getenv('EMBEDDING_BASE_URL') or llm_base_url
    
    # pgvector configuration
    use_pgvector = not args.no_pgvector
    pgvector_host = args.pgvector_host or os.getenv('PGVECTOR_HOST', 'localhost')
    pgvector_port = args.pgvector_port or int(os.getenv('PGVECTOR_PORT', '5432'))
    pgvector_database = args.pgvector_database or os.getenv('PGVECTOR_DATABASE', 'hipporag')
    pgvector_user = args.pgvector_user or os.getenv('PGVECTOR_USER', 'postgres')
    pgvector_password = args.pgvector_password or os.getenv('PGVECTOR_PASSWORD', '')
    pgvector_index_type = args.pgvector_index_type or os.getenv('PGVECTOR_INDEX_TYPE', 'ivfflat')
    pgvector_index_lists = args.pgvector_index_lists or int(os.getenv('PGVECTOR_INDEX_LISTS', '100'))
    
    # Nebula Graph configuration
    use_nebula_graph = not args.no_nebula
    nebula_host = args.nebula_host or os.getenv('NEBULA_HOST', '127.0.0.1')
    nebula_port = args.nebula_port or int(os.getenv('NEBULA_PORT', '9669'))
    nebula_user = args.nebula_user or os.getenv('NEBULA_USER', 'root')
    nebula_password = args.nebula_password or os.getenv('NEBULA_PASSWORD', 'nebula')
    nebula_space_name = args.nebula_space_name or os.getenv('NEBULA_SPACE_NAME', 'hipporag')
    
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
        # pgvector parameters
        use_pgvector=use_pgvector,
        pgvector_host=pgvector_host,
        pgvector_port=pgvector_port,
        pgvector_database=pgvector_database,
        pgvector_user=pgvector_user,
        pgvector_password=pgvector_password,
        pgvector_index_type=pgvector_index_type,
        pgvector_index_lists=pgvector_index_lists,
        # Nebula Graph parameters
        use_nebula_graph=use_nebula_graph,
        nebula_host=nebula_host,
        nebula_port=nebula_port,
        nebula_user=nebula_user,
        nebula_password=nebula_password,
        nebula_space_name=nebula_space_name
    )
    
    logger.info("Done!")


if __name__ == "__main__":
    main()

