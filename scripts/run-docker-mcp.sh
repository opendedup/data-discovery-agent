#!/bin/bash
# =============================================================================
# Run Data Discovery MCP Service in Docker
# =============================================================================
# This script runs the MCP service in a Docker container with proper
# environment variables loaded from .env
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

echo "================================================================================"
echo "Starting Data Discovery MCP Service in Docker"
echo "================================================================================"
echo ""
echo "Configuration:"
echo "  Project ID: ${GCP_PROJECT_ID}"
echo "  Reports Bucket: ${GCS_REPORTS_BUCKET}"
echo "  Datastore: ${VERTEX_DATASTORE_ID}"
echo "  Transport: HTTP"
echo "  Port: 8080"
echo ""
echo "================================================================================"

# Stop and remove existing container if running
docker stop data-discovery-mcp 2>/dev/null || true
docker rm data-discovery-mcp 2>/dev/null || true

# Run the container
docker run -d \
  --name data-discovery-mcp \
  -p 8080:8080 \
  -e GCP_PROJECT_ID="${GCP_PROJECT_ID}" \
  -e GCS_REPORTS_BUCKET="${GCS_REPORTS_BUCKET}" \
  -e VERTEX_DATASTORE_ID="${VERTEX_DATASTORE_ID}" \
  -e VERTEX_LOCATION="${VERTEX_LOCATION:-global}" \
  -e BQ_DATASET="${BQ_DATASET:-data_discovery}" \
  -e LOG_LEVEL="${LOG_LEVEL:-INFO}" \
  -e MCP_SERVER_NAME="${MCP_SERVER_NAME:-data-discovery-agent}" \
  -e MCP_SERVER_VERSION="${MCP_SERVER_VERSION:-1.0.0}" \
  -e MCP_TRANSPORT=http \
  -e MCP_HOST=0.0.0.0 \
  -e MCP_PORT=8080 \
  -v ~/.config/gcloud:/home/mcp/.config/gcloud:ro \
  --restart unless-stopped \
  data-discovery-mcp:latest

echo ""
echo "================================================================================"
echo "Container started successfully!"
echo "================================================================================"
echo ""
echo "Commands:"
echo "  View logs:       docker logs -f data-discovery-mcp"
echo "  Stop container:  docker stop data-discovery-mcp"
echo "  Remove container: docker rm data-discovery-mcp"
echo ""
echo "Testing:"
echo "  Health check:    curl http://localhost:8080/health"
echo "  List tools:      curl http://localhost:8080/mcp/tools"
echo ""
echo "Waiting for service to start..."
sleep 5

# Test health check
if curl -s http://localhost:8080/health > /dev/null 2>&1; then
    echo "✅ Service is healthy!"
    curl -s http://localhost:8080/health | jq .
else
    echo "⚠️  Service health check failed. Check logs with: docker logs data-discovery-mcp"
    exit 1
fi

echo ""
echo "================================================================================"
echo "MCP Service is running!"
echo "================================================================================"

