#!/usr/bin/env python3
"""
HippoRAG Storage Initialization Script

Initializes all required storage backends:
1. PostgreSQL with pgvector extension (embedding tables + multi-tenancy tables)
2. DGraph (graph schema)

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

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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
        'database': os.getenv('PGVECTOR_DATABASE', 'test'),
        'user': os.getenv('PGVECTOR_USER', 'admin'),
        'password': os.getenv('PGVECTOR_PASSWORD', 'admin'),
    }


def init_pgvector(embedding_dim: int = 1536) -> bool:
    """
    Initialize PostgreSQL with pgvector extension.

    Args:
        embedding_dim: Embedding vector dimension

    Returns:
        True if successful, False otherwise
    """
    try:
        import psycopg2
        from hipporag.database import DatabaseManager

        logger.info("=" * 60)
        logger.info("Initializing PostgreSQL with pgvector")
        logger.info("=" * 60)

        db_config = get_pgvector_config()
        logger.info(f"Connecting to PostgreSQL at {db_config['host']}:{db_config['port']}/{db_config['database']}")

        db = DatabaseManager(db_config)
        db.init_all_tables(embedding_dim)

        # Verify tables
        with db.conn.cursor() as cur:
            cur.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            tables = [row[0] for row in cur.fetchall()]
            logger.info(f"Created tables: {tables}")

        db.close()

        logger.info("PostgreSQL initialization completed successfully!")
        return True

    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        logger.error("Please install psycopg2: pip install psycopg2-binary")
        return False
    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL: {e}")
        return False


def init_dgraph() -> bool:
    """
    Initialize DGraph schema.

    Returns:
        True if successful, False otherwise
    """
    try:
        import pydgraph
        from hipporag.graph.graph_adapter_dgraph import DGraphAdapter

        logger.info("=" * 60)
        logger.info("Initializing DGraph")
        logger.info("=" * 60)

        dgraph_grpc = os.getenv('DGRAPH_GRPC', 'localhost:19081')
        logger.info(f"Connecting to DGraph at {dgraph_grpc}")

        # Create adapter which initializes schema automatically
        adapter = DGraphAdapter(
            connection_config={'grpc': dgraph_grpc},
            directed=True,
            schema_initialized=False  # Force schema initialization
        )

        # Verify connection by getting node count
        count = adapter.vcount()
        logger.info(f"DGraph connection verified. Current node count: {count}")

        logger.info("DGraph initialization completed successfully!")
        return True

    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        logger.error("Please install pydgraph: pip install pydgraph")
        return False
    except Exception as e:
        logger.error(f"Failed to initialize DGraph: {e}")
        logger.error("Make sure DGraph is running and accessible")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Initialize HippoRAG storage backends',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Initialize all storage backends
    python scripts/init_storage.py

    # Initialize only PostgreSQL
    python scripts/init_storage.py --skip-dgraph

    # Initialize with custom embedding dimension
    python scripts/init_storage.py --embedding-dim 3072
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
