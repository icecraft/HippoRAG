#!/bin/bash
#
# HippoRAG Storage Initialization Script
#
# This script initializes all required storage backends for HippoRAG:
# - PostgreSQL with pgvector extension
# - DGraph graph database
#
# Usage:
#   ./scripts/init_storage.sh [options]
#
# Options:
#   --embedding-dim DIM    Set embedding dimension (default: 1536)
#   --skip-pgvector        Skip PostgreSQL initialization
#   --skip-dgraph          Skip DGraph initialization
#   --help                 Show this help message
#
# Environment Variables:
#   PGVECTOR_HOST          PostgreSQL host (default: localhost)
#   PGVECTOR_PORT          PostgreSQL port (default: 5432)
#   PGVECTOR_DATABASE      Database name (default: hipporag)
#   PGVECTOR_USER          Database user (default: postgres)
#   PGVECTOR_PASSWORD      Database password
#   DGRAPH_GRPC            DGraph gRPC address (default: localhost:9080)
#

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Default values
EMBEDDING_DIM=1536
SKIP_PGVECTOR=false
SKIP_DGRAPH=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --embedding-dim)
            EMBEDDING_DIM="$2"
            shift 2
            ;;
        --skip-pgvector)
            SKIP_PGVECTOR=true
            shift
            ;;
        --skip-dgraph)
            SKIP_DGRAPH=true
            shift
            ;;
        --help)
            head -30 "$0" | tail -28
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Change to project directory
cd "$PROJECT_DIR"

# Load environment variables from .env file if it exists
if [ -f "projects/.env" ]; then
    echo "Loading environment variables from projects/.env"
    export $(grep -v '^#' projects/.env | xargs)
elif [ -f ".env" ]; then
    echo "Loading environment variables from .env"
    export $(grep -v '^#' .env | xargs)
fi

# Build command
CMD="python scripts/init_storage.py --embedding-dim $EMBEDDING_DIM"

if [ "$SKIP_PGVECTOR" = true ]; then
    CMD="$CMD --skip-pgvector"
fi

if [ "$SKIP_DGRAPH" = true ]; then
    CMD="$CMD --skip-dgraph"
fi

# Run initialization
echo "Running: $CMD"
echo ""
exec $CMD
