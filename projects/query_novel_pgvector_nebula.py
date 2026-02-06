#!/usr/bin/env python3
"""
Query HippoRAG index for character, event, and instrument relations in the novel.
This version uses:
- pgvector for embedding storage (PostgreSQL with pgvector extension)
- Nebula Graph for knowledge graph storage

Prerequisites:
- PostgreSQL with pgvector extension installed
- Nebula Graph server running
- Required Python packages: psycopg2-binary, nebula3-python
"""

import os
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


def load_hipporag(
    save_dir: str,
    llm_name: str = 'gpt-4o-mini',
    embedding_name: str = 'text-embedding-3-small',
    llm_base_url: str = 'https://api.openai.com/v1',
    embedding_base_url: Optional[str] = None,
    # pgvector configuration
    use_pgvector: bool = True,
    pgvector_host: str = 'localhost',
    pgvector_port: int = 5432,
    pgvector_database: str = 'hipporag',
    pgvector_user: str = 'admin',
    pgvector_password: str = 'admin',
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
    """Load existing HippoRAG instance with pgvector and Nebula Graph."""
    config = BaseConfig(
        save_dir=save_dir,
        llm_base_url=llm_base_url,
        embedding_base_url=embedding_base_url or llm_base_url,
        llm_name=llm_name,
        embedding_model_name=embedding_name,
        force_index_from_scratch=False,  # Don't rebuild, use existing
        retrieval_top_k=200,
        linking_top_k=5,
        max_qa_steps=3,
        qa_top_k=5,
        graph_type="facts_and_sim_passage_node_unidirectional",
        openie_mode="online",
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
    logger.info(f"  - Using Nebula Graph: {use_nebula_graph}")
    if use_nebula_graph:
        logger.info(f"    Nebula Graph: {nebula_user}@{nebula_host}:{nebula_port}")
        logger.info(f"    Space name: {nebula_space_name}")
    
    return HippoRAG(global_config=config)


def interactive_query(hipporag: HippoRAG):
    """Interactive query mode."""
    print("\n" + "="*60)
    print("Novel Analysis Query Interface")
    print("="*60)
    print("\nExample queries:")
    print("  - What instruments did [character name] use?")
    print("  - What events involved [character name]?")
    print("  - How are [character1] and [character2] related?")
    print("  - What happened with [instrument/object name]?")
    print("\nType 'exit' or 'quit' to end.\n")
    
    while True:
        query = input("\nEnter your query: ").strip()
        
        if query.lower() in ['exit', 'quit', 'q']:
            print("Goodbye!")
            break
        
        if not query:
            continue
        
        try:
            print("\nProcessing query...")
            results = hipporag.rag_qa(queries=[query])
            
            # Results format: (queries_solutions, all_response_message, all_metadata)
            if results and len(results) >= 1:
                queries_solutions = results[0]
                if queries_solutions and len(queries_solutions) > 0:
                    solution = queries_solutions[0]
                    print("\n" + "="*60)
                    print("Answer:")
                    print("="*60)
                    print(solution.answer if hasattr(solution, 'answer') else solution)
                    
                    if hasattr(solution, 'docs') and solution.docs:
                        print("\n" + "-"*60)
                        print("Retrieved passages:")
                        print("-"*60)
                        for i, doc in enumerate(solution.docs[:3], 1):  # Show top 3
                            print(f"\n[{i}] {doc[:200]}..." if len(doc) > 200 else f"\n[{i}] {doc}")
                else:
                    print("No answer found.")
            else:
                print("No results returned.")
                
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            print(f"Error: {e}")


def batch_query(hipporag: HippoRAG, queries: List[str], output_file: Optional[str] = None):
    """Process multiple queries at once."""
    print(f"\nProcessing {len(queries)} queries...")
    
    results = hipporag.rag_qa(queries=queries)
    
    queries_solutions = results[0] if results else []
    
    output_lines = []
    for i, (query, solution) in enumerate(zip(queries, queries_solutions), 1):
        answer = solution.answer if hasattr(solution, 'answer') else str(solution)
        output_lines.append(f"\n{'='*60}")
        output_lines.append(f"Query {i}: {query}")
        output_lines.append(f"{'='*60}")
        output_lines.append(f"Answer: {answer}")
        output_lines.append("")
        
        print(f"\nQuery {i}: {query}")
        print(f"Answer: {answer}")
    
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(output_lines))
        print(f"\nResults saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Query HippoRAG index for novel analysis using pgvector and Nebula Graph"
    )
    parser.add_argument(
        '--save_dir',
        type=str,
        default='outputs/novel',
        help='Directory where HippoRAG metadata is saved (default: outputs/novel)'
    )
    parser.add_argument(
        '--query',
        type=str,
        default=None,
        help='Single query to execute'
    )
    parser.add_argument(
        '--query_file',
        type=str,
        default=None,
        help='File containing queries (one per line)'
    )
    parser.add_argument(
        '--output_file',
        type=str,
        default=None,
        help='Output file for batch query results'
    )
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Run in interactive mode'
    )
    
    # pgvector arguments
    parser.add_argument(
        '--pgvector_host',
        type=str,
        default=None,
        help='PostgreSQL host (default: from env PGVECTOR_HOST or localhost)'
    )
    parser.add_argument(
        '--pgvector_port',
        type=int,
        default=None,
        help='PostgreSQL port (default: from env PGVECTOR_PORT or 5432)'
    )
    parser.add_argument(
        '--pgvector_database',
        type=str,
        default=None,
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
        default=None,
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
        default=None,
        help='Nebula Graph graphd host (default: from env NEBULA_HOST or 127.0.0.1)'
    )
    parser.add_argument(
        '--nebula_port',
        type=int,
        default=None,
        help='Nebula Graph graphd port (default: from env NEBULA_PORT or 9669)'
    )
    parser.add_argument(
        '--nebula_user',
        type=str,
        default=None,
        help='Nebula Graph user (default: from env NEBULA_USER or root)'
    )
    parser.add_argument(
        '--nebula_password',
        type=str,
        default=None,
        help='Nebula Graph password (default: from env NEBULA_PASSWORD or nebula)'
    )
    parser.add_argument(
        '--nebula_space_name',
        type=str,
        default=None,
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
    
    # pgvector configuration (from args, env, or defaults)
    use_pgvector = not args.no_pgvector
    pgvector_host = args.pgvector_host or os.getenv('PGVECTOR_HOST', 'localhost')
    pgvector_port = args.pgvector_port or int(os.getenv('PGVECTOR_PORT', '5432'))
    pgvector_database = args.pgvector_database or os.getenv('PGVECTOR_DATABASE', 'hipporag')
    pgvector_user = args.pgvector_user or os.getenv('PGVECTOR_USER', 'postgres')
    pgvector_password = args.pgvector_password or os.getenv('PGVECTOR_PASSWORD', '')
    pgvector_index_type = args.pgvector_index_type or os.getenv('PGVECTOR_INDEX_TYPE', 'ivfflat')
    pgvector_index_lists = args.pgvector_index_lists or int(os.getenv('PGVECTOR_INDEX_LISTS', '100'))
    
    # Nebula Graph configuration (from args, env, or defaults)
    use_nebula_graph = not args.no_nebula
    nebula_host = args.nebula_host or os.getenv('NEBULA_HOST', '127.0.0.1')
    nebula_port = args.nebula_port or int(os.getenv('NEBULA_PORT', '9669'))
    nebula_user = args.nebula_user or os.getenv('NEBULA_USER', 'root')
    nebula_password = args.nebula_password or os.getenv('NEBULA_PASSWORD', 'nebula')
    nebula_space_name = args.nebula_space_name or os.getenv('NEBULA_SPACE_NAME', 'hipporag')
    
    # Load HippoRAG
    logger.info(f"Loading HippoRAG index from: {args.save_dir}")
    hipporag = load_hipporag(
        save_dir=args.save_dir,
        llm_name=llm_name,
        embedding_name=embedding_name,
        llm_base_url=llm_base_url,
        embedding_base_url=embedding_base_url,
        use_pgvector=use_pgvector,
        pgvector_host=pgvector_host,
        pgvector_port=pgvector_port,
        pgvector_database=pgvector_database,
        pgvector_user=pgvector_user,
        pgvector_password=pgvector_password,
        pgvector_index_type=pgvector_index_type,
        pgvector_index_lists=pgvector_index_lists,
        use_nebula_graph=use_nebula_graph,
        nebula_host=nebula_host,
        nebula_port=nebula_port,
        nebula_user=nebula_user,
        nebula_password=nebula_password,
        nebula_space_name=nebula_space_name
    )
    logger.info("Index loaded successfully!")
    
    # Execute queries
    if args.interactive:
        interactive_query(hipporag)
    elif args.query_file:
        with open(args.query_file, 'r', encoding='utf-8') as f:
            queries = [line.strip() for line in f if line.strip()]
        batch_query(hipporag, queries, args.output_file)
    elif args.query:
        batch_query(hipporag, [args.query], args.output_file)
    else:
        # Default to interactive mode
        interactive_query(hipporag)


if __name__ == "__main__":
    main()

