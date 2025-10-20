#!/bin/bash
# =============================================================================
# Push Data Discovery MCP Image to Artifact Registry
# =============================================================================
# This script builds, tags, and pushes the MCP Docker image to Artifact Registry
# =============================================================================

set -e

# Change to project root
cd "$(dirname "$0")/.."

# Check if .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found. Please copy .env.example to .env and configure it."
    exit 1
fi

# Load environment variables from .env
export $(cat .env | grep -v '^#' | xargs)

# Default values
VERSION=${1:-latest}
PROJECT_ID=${GCP_PROJECT_ID}
LOCATION=${ARTIFACT_REGISTRY_LOCATION:-us-central1}
REPOSITORY=${ARTIFACT_REGISTRY_REPOSITORY:-data-discovery}
IMAGE_NAME="mcp"

# Construct the full image path
ARTIFACT_REGISTRY_URL="${LOCATION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}"
FULL_IMAGE_PATH="${ARTIFACT_REGISTRY_URL}/${IMAGE_NAME}:${VERSION}"

echo "================================================================================"
echo "Pushing Data Discovery MCP Image to Artifact Registry"
echo "================================================================================"
echo ""
echo "Configuration:"
echo "  Project ID: ${PROJECT_ID}"
echo "  Location: ${LOCATION}"
echo "  Repository: ${REPOSITORY}"
echo "  Image: ${IMAGE_NAME}"
echo "  Version: ${VERSION}"
echo "  Full Path: ${FULL_IMAGE_PATH}"
echo ""
echo "================================================================================"

# Step 1: Configure Docker authentication for Artifact Registry
echo ""
echo "Step 1/4: Configuring Docker authentication..."
gcloud auth configure-docker ${LOCATION}-docker.pkg.dev --quiet

# Step 2: Build the Docker image
echo ""
echo "Step 2/4: Building Docker image..."
docker build -t data-discovery-mcp:${VERSION} -f Dockerfile .

# Step 3: Tag for Artifact Registry
echo ""
echo "Step 3/4: Tagging image for Artifact Registry..."
docker tag data-discovery-mcp:${VERSION} ${FULL_IMAGE_PATH}

# Also tag as latest if version is not 'latest'
if [ "${VERSION}" != "latest" ]; then
    LATEST_IMAGE_PATH="${ARTIFACT_REGISTRY_URL}/${IMAGE_NAME}:latest"
    echo "  Also tagging as: ${LATEST_IMAGE_PATH}"
    docker tag data-discovery-mcp:${VERSION} ${LATEST_IMAGE_PATH}
fi

# Step 4: Push to Artifact Registry
echo ""
echo "Step 4/4: Pushing image to Artifact Registry..."
docker push ${FULL_IMAGE_PATH}

if [ "${VERSION}" != "latest" ]; then
    docker push ${LATEST_IMAGE_PATH}
fi

echo ""
echo "================================================================================"
echo "✅ Image pushed successfully!"
echo "================================================================================"
echo ""
echo "Image paths:"
echo "  ${FULL_IMAGE_PATH}"
if [ "${VERSION}" != "latest" ]; then
    echo "  ${LATEST_IMAGE_PATH}"
fi
echo ""
echo "To pull this image:"
echo "  docker pull ${FULL_IMAGE_PATH}"
echo ""
echo "To deploy to GKE:"
echo "  kubectl set image deployment/data-discovery-mcp \\"
echo "    mcp=${FULL_IMAGE_PATH}"
echo ""
echo "================================================================================"

