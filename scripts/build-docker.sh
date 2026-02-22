#!/bin/bash
# Build and push Docker images for Agent_Guru Reasoning Engine
# Usage: ./scripts/build-docker.sh [version] [registry]

set -e

# Configuration
VERSION=${1:-"latest"}
REGISTRY=${2:-"ghcr.io/agent-guru"}
IMAGE_NAME="agent-guru"
FULL_IMAGE="${REGISTRY}/${IMAGE_NAME}:${VERSION}"

# Build arguments
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
VCS_REF=$(git rev-parse --short HEAD)

echo "Building Docker image..."
echo "  Image: ${FULL_IMAGE}"
echo "  Build Date: ${BUILD_DATE}"
echo "  VCS Ref: ${VCS_REF}"
echo "  Version: ${VERSION}"

# Build the image with layer caching
docker build \
  --build-arg BUILD_DATE="${BUILD_DATE}" \
  --build-arg VCS_REF="${VCS_REF}" \
  --build-arg VERSION="${VERSION}" \
  --cache-from "${FULL_IMAGE}" \
  --tag "${FULL_IMAGE}" \
  --tag "${REGISTRY}/${IMAGE_NAME}:latest" \
  --file Dockerfile \
  .

echo "Image built successfully!"

# Show image size
echo ""
echo "Image size:"
docker images "${FULL_IMAGE}" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"

# Push to registry if requested
if [ "${PUSH:-false}" = "true" ]; then
  echo ""
  echo "Pushing image to registry..."
  docker push "${FULL_IMAGE}"
  
  if [ "${VERSION}" != "latest" ]; then
    docker push "${REGISTRY}/${IMAGE_NAME}:latest"
  fi
  
  echo "Image pushed successfully!"
fi

echo ""
echo "Done!"
