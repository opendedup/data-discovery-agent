#!/bin/bash

# Setup Vertex AI Search Infrastructure - Phase 1
# This script deploys Vertex AI Search data store and related infrastructure

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Vertex AI Search Setup - Phase 1${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v terraform &> /dev/null; then
    echo -e "${RED}ERROR: terraform not found${NC}"
    exit 1
fi

if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}ERROR: gcloud not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites met${NC}"
echo ""

# Set variables
PROJECT_ID="${PROJECT_ID:-lennyisagoodboy}"
REGION="${REGION:-us-central1}"
DATASTORE_ID="${DATASTORE_ID:-data-discovery-metadata}"
JSONL_BUCKET="${JSONL_BUCKET:-${PROJECT_ID}-data-discovery-jsonl}"

echo "Configuration:"
echo "  Project ID: ${PROJECT_ID}"
echo "  Region: ${REGION}"
echo "  Data Store ID: ${DATASTORE_ID}"
echo "  JSONL Bucket: ${JSONL_BUCKET}"
echo ""

read -p "Continue with this configuration? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

# Step 1: Deploy Terraform
echo ""
echo -e "${YELLOW}Step 1: Deploying Terraform infrastructure...${NC}"

cd "${PROJECT_ROOT}/terraform/vertex-ai-search"

terraform init

terraform plan \
    -var="project_id=${PROJECT_ID}" \
    -var="region=${REGION}" \
    -var="datastore_id=${DATASTORE_ID}" \
    -var="jsonl_bucket_name=${JSONL_BUCKET}" \
    -out=tfplan

echo ""
read -p "Apply Terraform plan? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

terraform apply tfplan

echo -e "${GREEN}✓ Terraform infrastructure deployed${NC}"

# Step 2: Create Vertex AI Search Data Store
echo ""
echo -e "${YELLOW}Step 2: Creating Vertex AI Search data store...${NC}"

# Check if data store already exists
if gcloud alpha discovery-engine data-stores describe ${DATASTORE_ID} \
    --project=${PROJECT_ID} \
    --location=${REGION} &> /dev/null; then
    echo -e "${YELLOW}⚠ Data store already exists, skipping creation${NC}"
else
    echo "Creating data store: ${DATASTORE_ID}"
    
    gcloud alpha discovery-engine data-stores create ${DATASTORE_ID} \
        --project=${PROJECT_ID} \
        --location=${REGION} \
        --collection=default_collection \
        --industry-vertical=GENERIC \
        --content-config=CONTENT_REQUIRED \
        --solution-type=SOLUTION_TYPE_SEARCH
    
    echo -e "${GREEN}✓ Data store created${NC}"
fi

# Step 3: Verify setup
echo ""
echo -e "${YELLOW}Step 3: Verifying setup...${NC}"

echo "Checking data store..."
if gcloud alpha discovery-engine data-stores describe ${DATASTORE_ID} \
    --project=${PROJECT_ID} \
    --location=${REGION} > /dev/null; then
    echo -e "${GREEN}✓ Data store verified${NC}"
else
    echo -e "${RED}✗ Data store verification failed${NC}"
    exit 1
fi

echo "Checking GCS bucket..."
if gsutil ls -b gs://${JSONL_BUCKET} > /dev/null 2>&1; then
    echo -e "${GREEN}✓ GCS bucket verified${NC}"
else
    echo -e "${RED}✗ GCS bucket verification failed${NC}"
    exit 1
fi

# Step 4: Display next steps
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Next steps:"
echo ""
echo "1. Run discovery agents to generate JSONL metadata:"
echo "   python -m data_discovery_agent.discovery.bigquery_discovery"
echo ""
echo "2. Import data into Vertex AI Search:"
echo "   gcloud alpha discovery-engine data-stores import documents \\"
echo "     --project=${PROJECT_ID} \\"
echo "     --location=${REGION} \\"
echo "     --data-store=${DATASTORE_ID} \\"
echo "     --gcs-uri=gs://${JSONL_BUCKET}/*.jsonl"
echo ""
echo "3. Test search:"
echo "   python -m data_discovery_agent.clients.vertex_search_client"
echo ""
echo "For more information, see:"
echo "  terraform/vertex-ai-search/README.md"
echo ""

