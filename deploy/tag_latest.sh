#!/bin/bash

# Script to tag the latest images with 'latest' tag
# This script finds the highest version number and tags it as 'latest'
# Uses semantic version sorting (e.g., 0.6 > 0.5)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Image names to process
IMAGES=("hipporag" "hipporag-frontend")

echo -e "${GREEN}Starting to tag latest images...${NC}\n"

for IMAGE_NAME in "${IMAGES[@]}"; do
    echo -e "${YELLOW}Processing ${IMAGE_NAME}...${NC}"
    
    # Get all images matching the name (excluding 'latest' tag)
    IMAGE_LIST=$(docker images "${IMAGE_NAME}" --format "{{.Repository}}:{{.Tag}}" | grep -v "latest")
    
    if [ -z "$IMAGE_LIST" ]; then
        # If no image found (excluding latest), check if there's any image at all
        ANY_IMAGE=$(docker images "${IMAGE_NAME}" --format "{{.Repository}}:{{.Tag}}" | head -n1)
        
        if [ -z "$ANY_IMAGE" ]; then
            echo -e "${RED}  ✗ No image found for ${IMAGE_NAME}${NC}"
            continue
        else
            # Only latest tag exists, skip
            echo -e "${YELLOW}  Only 'latest' tag exists for ${IMAGE_NAME}, skipping${NC}"
            continue
        fi
    fi
    
    # Sort by version number (semantic versioning)
    # Extract tags, sort by version, then get the latest
    LATEST_TAG=$(echo "$IMAGE_LIST" | cut -d':' -f2 | sort -V -r | head -n1)
    LATEST_IMAGE="${IMAGE_NAME}:${LATEST_TAG}"
    
    if [ -z "$LATEST_IMAGE" ]; then
        echo -e "${RED}  ✗ Could not determine latest image for ${IMAGE_NAME}${NC}"
        continue
    fi
    
    # Extract repository and tag
    REPO=$(echo "$LATEST_IMAGE" | cut -d':' -f1)
    TAG=$(echo "$LATEST_IMAGE" | cut -d':' -f2)
    
    echo -e "  Found latest image: ${GREEN}${LATEST_IMAGE}${NC}"
    
    # Remove existing 'latest' tag if it exists (only the tag, not the image)
    EXISTING_LATEST="${REPO}:latest"
    if docker images "${EXISTING_LATEST}" --format "{{.Repository}}:{{.Tag}}" 2>/dev/null | grep -q "${EXISTING_LATEST}"; then
        echo -e "  Removing existing 'latest' tag..."
        docker rmi "${EXISTING_LATEST}" 2>/dev/null || true
    fi
    
    # Tag the latest image as 'latest'
    echo -e "  Tagging ${LATEST_IMAGE} as ${GREEN}${REPO}:latest${NC}"
    docker tag "${LATEST_IMAGE}" "${REPO}:latest"
    
    echo -e "  ${GREEN}✓ Successfully tagged ${REPO}:latest${NC}\n"
done

echo -e "${GREEN}All images have been tagged with 'latest'!${NC}\n"
echo -e "Tagged images:"
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.CreatedAt}}" | grep -E "REPOSITORY|hipporag|hipporag-frontend" | grep -E "REPOSITORY|latest"
