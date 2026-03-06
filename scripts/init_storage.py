#!/usr/bin/env python3
"""
HippoRAG Storage Initialization Script

Initializes all required storage backends:
1. PostgreSQL with pgvector extension (embedding tables + multi-tenancy tables)
2. DGraph (graph schema)

This script is STANDALONE and does NOT depend on hipporag package.
It should be run BEFORE installing/starting HippoRAG.

Usage:
    python scripts/init_storage.py [--embedding-dim 1536] [--skip-dgraph] [--skip-pgvector]

Environment Variables:
    PGVECTOR_HOST      - PostgreSQL host (default: localhost)
    PGVECTOR_PORT      - PostgreSQL port (default: 5432)
    PGVECTOR_DATABASE  - Database name (default: hipporag)
    PGVECTOR_USER      - Database user (default: postgres)
    PGVECTOR_PASSWORD  - Database password (default: empty)
    DGRAPH_GRPC        - DGraph gRPC address (default: localhost:9080)
"""

import os
import sys
import argparse
import logging

# This script is standalone - does NOT import from hipporag

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_pgvector_config() -> dict:
    """Get PostgreSQL configuration from environment."""
    return {
        'host': os.getenv('PGVECTOR_HOST', 'localhost'),
        'port': int(os.getenv('PGVECTOR_PORT', '5432')),
        'database': os.getenv('PGVECTOR_DATABASE', 'hipporag'),
        'user': os.getenv('PGVECTOR_USER', 'postgres'),
        'password': os.getenv('PGVECTOR_PASSWORD', ''),
    }


def init_pgvector(embedding_dim: int = 1536) -> bool:
    """
    Initialize PostgreSQL with pgvector extension (standalone, no hipporag dependency).

    Args:
        embedding_dim: Embedding vector dimension

    Returns:
        True if successful, False otherwise
    """
    try:
        import psycopg2
    except ImportError:
        logger.error("Missing dependency: psycopg2")
        logger.error("Please install: pip install psycopg2-binary")
        return False

    try:
        db_config = get_pgvector_config()
        logger.info("=" * 60)
        logger.info("Initializing PostgreSQL with pgvector")
        logger.info("=" * 60)
        logger.info(f"Connecting to PostgreSQL at {db_config['host']}:{db_config['port']}/{db_config['database']}")

        conn = psycopg2.connect(**db_config)
        conn.autocommit = False

        with conn.cursor() as cur:
            # Enable pgvector extension
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            conn.commit()
            logger.info("pgvector extension enabled")

            # Create embedding tables
            for namespace in ['chunk', 'entity', 'fact']:
                table_name = f"embeddings_{namespace}"
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        hash_id TEXT PRIMARY KEY,
                        content TEXT NOT NULL,
                        embedding vector({embedding_dim}),
                        book_id VARCHAR(64),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{table_name}_book_id
                    ON {table_name}(book_id);
                """)
                logger.info(f"Created table {table_name}")

            # Create books table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS books (
                    book_id VARCHAR(64) PRIMARY KEY,
                    name VARCHAR(256),
                    description TEXT,
                    doc_count INT DEFAULT 0,
                    status VARCHAR(16) DEFAULT 'ready',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """)
            logger.info("Created table books")

            # Create businesses table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS businesses (
                    business_id VARCHAR(64) PRIMARY KEY,
                    name VARCHAR(256),
                    description TEXT,
                    status VARCHAR(16) DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """)
            logger.info("Created table businesses")

            # Create book_bindings table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS book_bindings (
                    id SERIAL PRIMARY KEY,
                    business_id VARCHAR(64) NOT NULL REFERENCES businesses(business_id) ON DELETE CASCADE,
                    book_id VARCHAR(64) NOT NULL REFERENCES books(book_id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(business_id, book_id)
                );
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_book_bindings_business
                ON book_bindings(business_id);
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_book_bindings_book
                ON book_bindings(book_id);
            """)
            logger.info("Created table book_bindings")

            conn.commit()

        conn.close()
        logger.info("PostgreSQL initialization completed successfully!")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL: {e}")
        return False


def init_dgraph() -> bool:
    """
    Initialize DGraph schema (standalone, no hipporag dependency).

    Returns:
        True if successful, False otherwise
    """
    try:
        import pydgraph
    except ImportError:
        logger.error("Missing dependency: pydgraph")
        logger.error("Please install: pip install pydgraph")
        return False

    try:
        logger.info("=" * 60)
        logger.info("Initializing DGraph")
        logger.info("=" * 60)

        dgraph_grpc = os.getenv('DGRAPH_GRPC', 'localhost:9080')
        logger.info(f"Connecting to DGraph at {dgraph_grpc}")

        # Create client
        client_stub = pydgraph.DgraphClientStub(dgraph_grpc)
        client = pydgraph.DgraphClient(client_stub)

        # Define schema
        schema = """
        name: string @index(exact) .
        node_type: string @index(exact) .
        content: string .
        properties: string .
        weight: float .
        edge_type: string .
        book_id: string @index(exact) .

        type Node {
            name
            node_type
            content
            properties
            book_id
        }
        """

        # Set schema
        op = pydgraph.Operation(schema=schema)
        client.alter(op)

        logger.info("DGraph schema initialized successfully!")
        logger.info("DGraph initialization completed successfully!")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize DGraph: {e}")
        logger.error("Make sure DGraph is running and accessible")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Initialize HippoRAG storage backends (standalone, no hipporag dependency)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Initialize all storage backends
    python scripts/init_storage.py

    # Initialize only PostgreSQL
    python scripts/init_storage.py --skip-dgraph

    # Initialize with custom embedding dimension
    python scripts/init_storage.py --embedding-dim 3072

NOTE: This script does NOT require hipporag package to be installed.
It uses only psycopg2 and pydgraph directly.
        """
    )
    parser.add_argument(
        '--embedding-dim',
        type=int,
        default=1536,
        help='Embedding vector dimension (default: 1536)'
    )
    parser.add_argument(
        '--skip-pgvector',
        action='store_true',
        help='Skip PostgreSQL initialization'
    )
    parser.add_argument(
        '--skip-dgraph',
        action='store_true',
        help='Skip DGraph initialization'
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("HippoRAG Storage Initialization")
    logger.info("=" * 60)
    logger.info("NOTE: This script is standalone and does not require hipporag package")

    results = {}

    # Initialize PostgreSQL
    if not args.skip_pgvector:
        results['pgvector'] = init_pgvector(args.embedding_dim)
    else:
        logger.info("Skipping PostgreSQL initialization")
        results['pgvector'] = None

    # Initialize DGraph
    if not args.skip_dgraph:
        results['dgraph'] = init_dgraph()
    else:
        logger.info("Skipping DGraph initialization")
        results['dgraph'] = None

    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("Initialization Summary")
    logger.info("=" * 60)

    if results['pgvector'] is not None:
        status = "SUCCESS" if results['pgvector'] else "FAILED"
        logger.info(f"  PostgreSQL/pgvector: {status}")

    if results['dgraph'] is not None:
        status = "SUCCESS" if results['dgraph'] else "FAILED"
        logger.info(f"  DGraph:              {status}")

    # Exit with error code if any initialization failed
    failed = any(v is False for v in results.values())
    if failed:
        logger.error("Some initializations failed!")
        sys.exit(1)
    else:
        logger.info("All initializations completed successfully!")
        sys.exit(0)


if __name__ == '__main__':
    main()
