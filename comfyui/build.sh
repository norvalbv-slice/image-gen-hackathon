#!/bin/bash
# Build and push ComfyUI + Flux 2.0 Docker image to Docker Hub

set -e

# Configuration - UPDATE THESE
DOCKER_USERNAME="${DOCKER_USERNAME:-your-dockerhub-username}"
IMAGE_NAME="comfyui-flux2"
IMAGE_TAG="latest"
FULL_IMAGE="${DOCKER_USERNAME}/${IMAGE_NAME}:${IMAGE_TAG}"

echo "Building Docker image: ${FULL_IMAGE}"
echo "This will take 20-40 minutes due to model downloads..."

# Build the image
docker build --platform linux/amd64 -t ${FULL_IMAGE} .

echo "Build complete!"
echo ""
echo "To push to Docker Hub:"
echo "  docker login"
echo "  docker push ${FULL_IMAGE}"
echo ""
echo "Image SHA for RunPod template:"
docker inspect --format='{{index .RepoDigests 0}}' ${FULL_IMAGE} 2>/dev/null || echo "(push first to get SHA)"

