#!/bin/bash
IMAGE_NAME="hipporag-frontend"
DEFAULT_API_URL="http://localhost:8000"

if [[ $# -eq 0 ]]; then
    echo "Usage: $0 <tag> [api_url]"
    echo ""
    echo "Arguments:"
    echo "  tag      - Docker image tag (required)"
    echo "  api_url  - Backend API URL (default: $DEFAULT_API_URL)"
    echo ""
    echo "Examples:"
    echo "  $0 v1.0.0"
    echo "  $0 v1.0.0 http://192.168.1.100:8000"
    echo ""
    echo "Current images:"
    docker images | grep "$IMAGE_NAME"
    exit 1
fi

TAG=$1
API_URL=${2:-$DEFAULT_API_URL}

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Building $IMAGE_NAME:$TAG"
echo "Backend API URL: $API_URL"
echo ""

# Build Docker image with build args
docker build \
    -f "$SCRIPT_DIR/Dockerfile" \
    -t "$IMAGE_NAME:$TAG" \
    --build-arg REACT_APP_API_URL="$API_URL" \
    "$SCRIPT_DIR"
