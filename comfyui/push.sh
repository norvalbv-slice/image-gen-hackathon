#!/bin/bash
# Push ComfyUI + Flux 2.0 image to Docker Hub
# Usage: DOCKER_USERNAME=yourusername ./push.sh

set -e

if [ -z "$DOCKER_USERNAME" ]; then
    echo "Please set DOCKER_USERNAME environment variable"
    echo "Usage: DOCKER_USERNAME=yourusername ./push.sh"
    exit 1
fi

IMAGE_NAME="comfyui-flux2"
IMAGE_TAG="latest"
LOCAL_IMAGE="comfyui-flux2:latest"
REMOTE_IMAGE="${DOCKER_USERNAME}/${IMAGE_NAME}:${IMAGE_TAG}"

echo "Tagging image as ${REMOTE_IMAGE}..."
docker tag ${LOCAL_IMAGE} ${REMOTE_IMAGE}

echo "Pushing to Docker Hub..."
docker push ${REMOTE_IMAGE}

echo ""
echo "✓ Image pushed successfully!"
echo ""
echo "Image: ${REMOTE_IMAGE}"
echo ""
echo "Use this image name when creating the RunPod template."



