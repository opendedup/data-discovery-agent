#!/bin/bash
# ==============================================================================
# Deploy Data Discovery Agent to Cloud Composer
# ==============================================================================
#
# This script copies the updated discovery agent code to the Cloud Composer
# GCS bucket, making it available to Airflow DAGs.
#
# Usage:
#   ./scripts/deploy-to-composer.sh
#
# ==============================================================================

set -euo pipefail

# Configuration
COMPOSER_ENV_NAME="${COMPOSER_ENV_NAME:-data-discovery-agent-composer}"
COMPOSER_LOCATION="${COMPOSER_LOCATION:-us-central1}"
PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}===================================================================${NC}"
echo -e "${GREEN}  Deploying Data Discovery Agent to Cloud Composer${NC}"
echo -e "${GREEN}===================================================================${NC}"
echo ""

# Step 1: Get Composer bucket
echo -e "${YELLOW}[1/4] Getting Composer DAG bucket...${NC}"
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: GCP_PROJECT_ID not set and unable to get from gcloud config${NC}"
    echo "Please set GCP_PROJECT_ID environment variable or run: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

COMPOSER_BUCKET=$(gcloud composer environments describe "$COMPOSER_ENV_NAME" \
  --location "$COMPOSER_LOCATION" \
  --project "$PROJECT_ID" \
  --format="value(config.dagGcsPrefix)" 2>&1)

if [ $? -ne 0 ] || [ -z "$COMPOSER_BUCKET" ]; then
    echo -e "${RED}Error: Failed to get Composer bucket${NC}"
    echo "Output: $COMPOSER_BUCKET"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Check if Composer environment exists:"
    echo "     gcloud composer environments list --project=$PROJECT_ID --location=$COMPOSER_LOCATION"
    echo "  2. Verify you have permissions to access the environment"
    echo "  3. Check if the environment name is correct: $COMPOSER_ENV_NAME"
    exit 1
fi

echo -e "${GREEN}✓ Found Composer bucket: $COMPOSER_BUCKET${NC}"
echo ""

# Step 2: Copy DAG file
echo -e "${YELLOW}[2/4] Copying DAG file to Composer...${NC}"
if [ ! -d "dags" ]; then
    echo -e "${RED}Error: dags/ directory not found${NC}"
    exit 1
fi

gsutil cp dags/metadata_collection_dag.py "$COMPOSER_BUCKET/"
echo -e "${GREEN}✓ DAG file copied${NC}"
echo ""

# Step 3: Copy source code
echo -e "${YELLOW}[3/4] Copying source code to Composer...${NC}"
if [ ! -d "src/data_discovery_agent" ]; then
    echo -e "${RED}Error: src/data_discovery_agent/ directory not found${NC}"
    exit 1
fi

# Clean up __pycache__ directories before deployment
echo "  Cleaning up __pycache__ directories..."
find src/data_discovery_agent -type d -name "__pycache__" -prune -exec rm -rf {} \; 2>/dev/null || true
echo -e "${GREEN}  ✓ Cleaned up Python cache files${NC}"

# Remove old version first (optional, but ensures clean deployment)
echo "  Removing old source code..."
gsutil -m rm -r "$COMPOSER_BUCKET/src/data_discovery_agent/" 2>/dev/null || true

echo "  Copying new source code..."
gsutil -m cp -r src/data_discovery_agent "$COMPOSER_BUCKET/src/"
echo -e "${GREEN}✓ Source code copied${NC}"
echo ""

# Step 4: Copy .airflowignore if it exists
echo -e "${YELLOW}[4/4] Copying .airflowignore (if exists)...${NC}"
if [ -f ".airflowignore" ]; then
    gsutil cp .airflowignore "$COMPOSER_BUCKET/"
    echo -e "${GREEN}✓ .airflowignore copied${NC}"
else
    echo "  .airflowignore not found, skipping..."
fi
echo ""

# Verification
echo -e "${YELLOW}Verifying deployment...${NC}"
echo "  Checking DAG file:"
gsutil ls "$COMPOSER_BUCKET/metadata_collection_dag.py" && echo -e "${GREEN}  ✓ DAG file present${NC}"

echo "  Checking source code:"
gsutil ls "$COMPOSER_BUCKET/src/data_discovery_agent/" | head -5
echo ""

# Summary
echo -e "${GREEN}===================================================================${NC}"
echo -e "${GREEN}  Deployment Complete!${NC}"
echo -e "${GREEN}===================================================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Wait 1-2 minutes for Composer to detect the new DAG"
echo "  2. Check DAG status in Airflow UI:"
echo "     gcloud composer environments run $COMPOSER_ENV_NAME \\"
echo "       --location $COMPOSER_LOCATION dags list"
echo "  3. Trigger the DAG manually (if needed):"
echo "     gcloud composer environments run $COMPOSER_ENV_NAME \\"
echo "       --location $COMPOSER_LOCATION dags trigger -- metadata_collection_dag"
echo ""
echo "To view Airflow UI:"
echo "  gcloud composer environments describe $COMPOSER_ENV_NAME \\"
echo "    --location $COMPOSER_LOCATION --format='value(config.airflowUri)'"
echo ""
echo -e "${GREEN}Deployment completed successfully!${NC}"

