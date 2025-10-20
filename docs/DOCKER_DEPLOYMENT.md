# Docker Deployment Guide

## Overview

This guide covers building, running, and deploying the Data Discovery MCP service as a Docker container.

## Quick Start

### 1. Build the Docker Image

```bash
docker build -t data-discovery-mcp:latest .
```

### 2. Run the Container

```bash
# Using the helper script (recommended)
./scripts/run-docker-mcp.sh

# Or manually
docker run -d \
  --name data-discovery-mcp \
  -p 8080:8080 \
  -e GCP_PROJECT_ID="your-project-id" \
  -e GCS_REPORTS_BUCKET="your-reports-bucket" \
  -e VERTEX_DATASTORE_ID="data-discovery-metadata" \
  -e VERTEX_LOCATION="global" \
  -e MCP_TRANSPORT=http \
  -e MCP_HOST=0.0.0.0 \
  -e MCP_PORT=8080 \
  -v ~/.config/gcloud:/home/mcp/.config/gcloud:ro \
  data-discovery-mcp:latest
```

### 3. Verify the Service

```bash
# Health check
curl http://localhost:8080/health

# List available tools
curl http://localhost:8080/mcp/tools | jq

# Test a search
curl -X POST http://localhost:8080/mcp/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "name": "query_data_assets",
    "arguments": {
      "query": "customer tables",
      "page_size": 5
    }
  }' | jq
```

## Dockerfile Details

### Multi-Stage Build

The Dockerfile uses a multi-stage build process for optimal image size:

1. **Builder Stage**: Installs Poetry and dependencies
2. **Runtime Stage**: Copies only necessary files, creating a lean production image

### Key Features

- **Base Image**: Python 3.11-slim (Debian-based)
- **Dependency Management**: Poetry for reproducible builds
- **Security**: Runs as non-root user (`mcp`)
- **Health Checks**: Built-in HTTP health endpoint
- **Size**: ~495MB (optimized)

### Dockerfile Structure

```dockerfile
# Stage 1: Builder
FROM python:3.11-slim AS builder
# Install build dependencies
# Install Poetry
# Install Python dependencies

# Stage 2: Runtime
FROM python:3.11-slim
# Copy dependencies from builder
# Copy application code
# Create non-root user
# Configure service
```

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `GCP_PROJECT_ID` | Google Cloud Project ID | `my-project` |
| `GCS_REPORTS_BUCKET` | GCS bucket for metadata reports | `my-bucket-reports` |
| `VERTEX_DATASTORE_ID` | Vertex AI Search datastore ID | `data-discovery-metadata` |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `VERTEX_LOCATION` | Vertex AI Search location | `global` |
| `BQ_DATASET` | BigQuery dataset for metadata | `data_discovery` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `MCP_SERVER_NAME` | Service name | `data-discovery-agent` |
| `MCP_SERVER_VERSION` | Service version | `1.0.0` |
| `MCP_TRANSPORT` | Transport mode | `http` |
| `MCP_HOST` | Host to bind to | `0.0.0.0` |
| `MCP_PORT` | Port to listen on | `8080` |

## Authentication

### Using Application Default Credentials

The container uses Google Cloud Application Default Credentials (ADC) for authentication.

**Option 1: Mount GCloud Credentials (Local Development)**

```bash
docker run -d \
  --name data-discovery-mcp \
  -v ~/.config/gcloud:/home/mcp/.config/gcloud:ro \
  ...
  data-discovery-mcp:latest
```

**Option 2: Service Account Key File (Production)**

```bash
docker run -d \
  --name data-discovery-mcp \
  -v /path/to/service-account-key.json:/app/credentials.json:ro \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json \
  ...
  data-discovery-mcp:latest
```

**Option 3: GKE Workload Identity (Recommended for GKE)**

No explicit credentials needed - workload identity automatically provides authentication.

## Docker Commands

### Build

```bash
# Build image
docker build -t data-discovery-mcp:latest .

# Build with no cache
docker build --no-cache -t data-discovery-mcp:latest .

# Build with custom tag
docker build -t data-discovery-mcp:v1.0.0 .
```

### Run

```bash
# Run in foreground (with logs)
docker run --rm -it \
  -p 8080:8080 \
  --env-file .env \
  -e MCP_TRANSPORT=http \
  data-discovery-mcp:latest

# Run in background (detached)
docker run -d \
  --name data-discovery-mcp \
  -p 8080:8080 \
  --env-file .env \
  -e MCP_TRANSPORT=http \
  --restart unless-stopped \
  data-discovery-mcp:latest
```

### Manage

```bash
# View logs
docker logs data-discovery-mcp
docker logs -f data-discovery-mcp  # Follow logs

# Stop container
docker stop data-discovery-mcp

# Start container
docker start data-discovery-mcp

# Restart container
docker restart data-discovery-mcp

# Remove container
docker rm data-discovery-mcp
docker rm -f data-discovery-mcp  # Force remove running container

# Execute command in container
docker exec -it data-discovery-mcp bash

# Inspect container
docker inspect data-discovery-mcp
```

### Images

```bash
# List images
docker images data-discovery-mcp

# Remove image
docker rmi data-discovery-mcp:latest

# Tag image
docker tag data-discovery-mcp:latest gcr.io/my-project/data-discovery-mcp:v1.0.0

# Push to registry
docker push gcr.io/my-project/data-discovery-mcp:v1.0.0
```

## Pushing to Container Registry

### Google Container Registry (GCR)

```bash
# Tag for GCR
docker tag data-discovery-mcp:latest gcr.io/your-project-id/data-discovery-mcp:latest

# Configure Docker to use gcloud auth
gcloud auth configure-docker

# Push to GCR
docker push gcr.io/your-project-id/data-discovery-mcp:latest
```

### Artifact Registry

```bash
# Create repository (one-time)
gcloud artifacts repositories create data-discovery \
  --repository-format=docker \
  --location=us-central1 \
  --description="Data Discovery MCP Service"

# Tag for Artifact Registry
docker tag data-discovery-mcp:latest \
  us-central1-docker.pkg.dev/your-project-id/data-discovery/mcp:latest

# Configure Docker auth
gcloud auth configure-docker us-central1-docker.pkg.dev

# Push to Artifact Registry
docker push us-central1-docker.pkg.dev/your-project-id/data-discovery/mcp:latest
```

## Health Checks

The container includes a built-in health check that calls the `/health` endpoint every 30 seconds.

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1
```

Check health status:

```bash
# View health status
docker inspect --format='{{.State.Health.Status}}' data-discovery-mcp

# View health check logs
docker inspect --format='{{range .State.Health.Log}}{{.Output}}{{end}}' data-discovery-mcp
```

## Resource Limits

Set resource limits for production deployments:

```bash
docker run -d \
  --name data-discovery-mcp \
  --memory=2g \
  --cpus=2 \
  --memory-reservation=512m \
  -p 8080:8080 \
  data-discovery-mcp:latest
```

## Networking

### Port Mapping

```bash
# Map to different host port
docker run -d -p 9090:8080 data-discovery-mcp:latest

# Bind to specific interface
docker run -d -p 127.0.0.1:8080:8080 data-discovery-mcp:latest
```

### Custom Networks

```bash
# Create network
docker network create mcp-network

# Run container on network
docker run -d \
  --name data-discovery-mcp \
  --network mcp-network \
  -p 8080:8080 \
  data-discovery-mcp:latest
```

## Debugging

### View Logs with Timestamps

```bash
docker logs -f --timestamps data-discovery-mcp
```

### Enter Container Shell

```bash
docker exec -it data-discovery-mcp bash
```

### Enable Debug Logging

```bash
docker run -d \
  -e LOG_LEVEL=DEBUG \
  data-discovery-mcp:latest
```

### Test Health Check Manually

```bash
docker exec data-discovery-mcp \
  python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8080/health').read())"
```

## Production Best Practices

### 1. Use Specific Tags

```bash
# Don't use :latest in production
docker build -t data-discovery-mcp:v1.0.0 .
```

### 2. Set Resource Limits

```bash
docker run -d \
  --memory=2g \
  --cpus=2 \
  --memory-reservation=512m \
  ...
```

### 3. Use Restart Policies

```bash
docker run -d \
  --restart unless-stopped \
  ...
```

### 4. Mount Logs Volume (Optional)

```bash
docker run -d \
  -v /var/log/mcp:/app/logs \
  ...
```

### 5. Use Read-Only Root Filesystem

```bash
docker run -d \
  --read-only \
  --tmpfs /tmp \
  ...
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker logs data-discovery-mcp

# Run in foreground to see errors
docker run --rm -it data-discovery-mcp:latest
```

### Health Check Failing

```bash
# Check service is listening
docker exec data-discovery-mcp netstat -tuln | grep 8080

# Test health endpoint manually
docker exec data-discovery-mcp curl -v http://localhost:8080/health
```

### Permission Denied Errors

```bash
# Check file permissions
docker exec data-discovery-mcp ls -la /app/

# Run as root for debugging (not recommended for production)
docker run -it --user root data-discovery-mcp:latest bash
```

### Google Cloud Authentication Issues

```bash
# Verify credentials are mounted
docker exec data-discovery-mcp ls -la /home/mcp/.config/gcloud/

# Check ADC
docker exec data-discovery-mcp \
  python -c "from google.auth import default; print(default())"

# Test GCS access
docker exec data-discovery-mcp \
  gsutil ls gs://your-bucket
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Build and Push Docker Image

on:
  push:
    branches: [main]
    tags: ['v*']

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v1
        with:
          service_account_key: ${{ secrets.GCP_SA_KEY }}
          project_id: ${{ secrets.GCP_PROJECT_ID }}
      
      - name: Configure Docker
        run: gcloud auth configure-docker
      
      - name: Build Docker image
        run: docker build -t gcr.io/${{ secrets.GCP_PROJECT_ID }}/data-discovery-mcp:${{ github.sha }} .
      
      - name: Push to GCR
        run: docker push gcr.io/${{ secrets.GCP_PROJECT_ID }}/data-discovery-mcp:${{ github.sha }}
```

## Next Steps

- **Deploy to GKE**: See [k8s/README.md](../k8s/README.md) for Kubernetes deployment
- **Monitor Service**: Set up logging and monitoring
- **Scale Horizontally**: Deploy multiple replicas behind a load balancer
- **CI/CD Pipeline**: Automate builds and deployments

## Additional Resources

- [Dockerfile Reference](../Dockerfile)
- [Kubernetes Deployment](../k8s/)
- [MCP Client Guide](MCP_CLIENT_GUIDE.md)
- [Architecture Documentation](ARCHITECTURE.md)

