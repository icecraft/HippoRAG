
#!/bin/bash 
IMAGE_NAME="hipporag"

if [[ $# -eq 0 ]]; then
    echo "Usage: $0 <tag>"
    docker images | grep "$IMAGE_NAME"
    exit 1
fi

TAG=$1

# Get the directory where this script is located


# Build Docker image from project root with Dockerfile path
docker build -f Dockerfile -t "$IMAGE_NAME:$TAG" .

