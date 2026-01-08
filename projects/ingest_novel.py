#!/usr/bin/env python3
"""
Ingest novel chapters (list of strings) into HippoRAG for character/event/instrument analysis.
Each element in the chapters list should be a chapter's content.
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
    force_openie_from_scratch: bool = False
):
    """
    Ingest a list of chapter strings into HippoRAG.
    
    Args:
        chapters: List of strings, each element is a chapter's content
        save_dir: Directory to save the HippoRAG index
        llm_name: LLM model name
        embedding_name: Embedding model name
        llm_base_url: LLM API base URL (e.g., https://dashscope.aliyuncs.com/compatible-mode/v1 for DashScope)
        embedding_base_url: Embedding API base URL (if not set, uses llm_base_url)
        force_index_from_scratch: If True, rebuild index from scratch
        force_openie_from_scratch: If True, rebuild OpenIE from scratch
    
    Returns:
        HippoRAG instance
    """
    logger.info(f"Number of chapters: {len(chapters)}")
    logger.info(f"Total characters: {sum(len(ch) for ch in chapters)}")
    
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
        save_openie=True
    )
    
    # Initialize HippoRAG
    hipporag = HippoRAG(global_config=config)
    
    # Index chapters
    logger.info("Starting indexing...")
    hipporag.index(docs=chapters)
    logger.info(f"Indexing complete! Index saved to: {save_dir}")
    
    return hipporag


def main():
    parser = argparse.ArgumentParser(
        description="Ingest novel chapters into HippoRAG"
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
        force_openie_from_scratch=args.force_openie_from_scratch
    )
    
    logger.info("Done!")


if __name__ == "__main__":
    main()

