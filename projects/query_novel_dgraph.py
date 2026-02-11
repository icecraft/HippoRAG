#!/usr/bin/env python3
"""
Query HippoRAG index for character, event, and instrument relations in the novel.
This version uses:
- DGraph for knowledge graph storage (distributed graph database)
- pgvector for embedding storage (PostgreSQL with pgvector extension)

Prerequisites:
- DGraph server running (default: localhost:9080)
- PostgreSQL with pgvector extension installed
- Required Python packages: pydgraph, psycopg2-binary
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
    # DGraph configuration
    dgraph_host: str = 'localhost',
    dgraph_port: int = 9080,
    # pgvector configuration
    use_pgvector: bool = True,
    pgvector_host: str = 'localhost',
    pgvector_port: int = 5432,
    pgvector_database: str = 'hipporag',
    pgvector_user: str = 'postgres',
    pgvector_password: str = '',
    pgvector_index_type: str = 'ivfflat',
    pgvector_index_lists: int = 100
):
    """Load existing HippoRAG instance with DGraph and pgvector."""
    # DGraph configuration
    dgraph_config = {
        "host": dgraph_host,
        "port": dgraph_port
    }
    
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
        # Graph library: use dgraph
        graph_library="dgraph",
        dgraph_config=dgraph_config,
        # pgvector configuration
        use_pgvector=use_pgvector,
        pgvector_host=pgvector_host if use_pgvector else '',
        pgvector_port=pgvector_port if use_pgvector else 5432,
        pgvector_database=pgvector_database if use_pgvector else '',
        pgvector_user=pgvector_user if use_pgvector else '',
        pgvector_password=pgvector_password if use_pgvector else '',
        pgvector_index_type=pgvector_index_type if use_pgvector else 'ivfflat',
        pgvector_index_lists=pgvector_index_lists if use_pgvector else 100
    )
    
    logger.info("Configuration:")
    logger.info(f"  - Using DGraph: {dgraph_host}:{dgraph_port}")
    logger.info(f"  - Using pgvector: {use_pgvector}")
    if use_pgvector:
        logger.info(f"    PostgreSQL: {pgvector_user}@{pgvector_host}:{pgvector_port}/{pgvector_database}")
    
    return HippoRAG(global_config=config)


def interactive_query(hipporag: HippoRAG):
    """Interactive query mode."""
    print("\n" + "="*60)
    print("Novel Analysis Query Interface (DGraph + pgvector)")
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
        description="Query HippoRAG index for novel analysis (DGraph + pgvector)"
    )
    parser.add_argument(
        '--save_dir',
        type=str,
        default='outputs/novel',
        help='Directory where HippoRAG index is saved (default: outputs/novel)'
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
        help='DGraph server port (default: 19081)'
    )
    
    # pgvector arguments
    parser.add_argument(
        '--use_pgvector',
        action='store_true',
        default=True,
        help='Use pgvector for embedding storage (default: True)'
    )
    parser.add_argument(
        '--no_pgvector',
        action='store_false',
        dest='use_pgvector',
        help='Disable pgvector (use Parquet files instead)'
    )
    parser.add_argument(
        '--pgvector_host',
        type=str,
        default='localhost',
        help='PostgreSQL host (default: localhost)'
    )
    parser.add_argument(
        '--pgvector_port',
        type=int,
        default=5432,
        help='PostgreSQL port (default: 5432)'
    )
    parser.add_argument(
        '--pgvector_database',
        type=str,
        default='test',
        help='PostgreSQL database name (default: test)'
    )
    parser.add_argument(
        '--pgvector_user',
        type=str,
        default='admin',
        help='PostgreSQL user (default: admin)'
    )
    parser.add_argument(
        '--pgvector_password',
        type=str,
        default='admin',
        help='PostgreSQL password (default: admin)'
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
    
    # Load HippoRAG
    logger.info(f"Loading HippoRAG index from: {args.save_dir}")
    logger.info(f"Using DGraph at {args.dgraph_host}:{args.dgraph_port}")
    if args.use_pgvector:
        logger.info(f"Using pgvector at {args.pgvector_user}@{args.pgvector_host}:{args.pgvector_port}/{args.pgvector_database}")
    
    hipporag = load_hipporag(
        save_dir=args.save_dir,
        llm_name=llm_name,
        embedding_name=embedding_name,
        llm_base_url=llm_base_url,
        embedding_base_url=embedding_base_url,
        # DGraph configuration
        dgraph_host=args.dgraph_host,
        dgraph_port=args.dgraph_port,
        # pgvector configuration
        use_pgvector=args.use_pgvector,
        pgvector_host=args.pgvector_host,
        pgvector_port=args.pgvector_port,
        pgvector_database=args.pgvector_database,
        pgvector_user=args.pgvector_user,
        pgvector_password=args.pgvector_password,
        pgvector_index_type=args.pgvector_index_type,
        pgvector_index_lists=args.pgvector_index_lists
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

