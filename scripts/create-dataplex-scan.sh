#!/bin/bash
#
# Helper script to create a single Dataplex Data Profile Scan
# Usage: ./scripts/create-dataplex-scan.sh PROJECT_ID DATASET_ID TABLE_ID [LOCATION]
#

set -e

PROJECT_ID="${1}"
DATASET_ID="${2}"
TABLE_ID="${3}"
LOCATION="${4:-us-central1}"

if [ -z "$PROJECT_ID" ] || [ -z "$DATASET_ID" ] || [ -z "$TABLE_ID" ]; then
    echo "Usage: $0 PROJECT_ID DATASET_ID TABLE_ID [LOCATION]"
    echo ""
    echo "Example:"
    echo "  $0 my-gcp-project lfndata post_game_summaries us-central1"
    exit 1
fi

SCAN_ID="profile-${DATASET_ID}-${TABLE_ID}"
TABLE_RESOURCE="//bigquery.googleapis.com/projects/${PROJECT_ID}/datasets/${DATASET_ID}/tables/${TABLE_ID}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Creating Dataplex Data Profile Scan"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Project:  ${PROJECT_ID}"
echo "Location: ${LOCATION}"
echo "Table:    ${DATASET_ID}.${TABLE_ID}"
echo "Scan ID:  ${SCAN_ID}"
echo ""

# Check if scan already exists
if gcloud dataplex datascans describe "${SCAN_ID}" \
    --project="${PROJECT_ID}" \
    --location="${LOCATION}" \
    &>/dev/null; then
    echo "✓ Scan already exists: ${SCAN_ID}"
    echo ""
    echo "To run the scan:"
    echo "  gcloud dataplex datascans run ${SCAN_ID} --project=${PROJECT_ID} --location=${LOCATION}"
    exit 0
fi

# Create the data profile scan
echo "Creating scan..."
gcloud dataplex datascans create "${SCAN_ID}" \
    --project="${PROJECT_ID}" \
    --location="${LOCATION}" \
    --data-profile-spec-sampling-percent=100 \
    --data-source-resource="${TABLE_RESOURCE}" \
    --display-name="Profile: ${DATASET_ID}.${TABLE_ID}" \
    --labels="managed_by=script,purpose=data-discovery,dataset=${DATASET_ID}"

echo ""
echo "✓ Scan created successfully!"
echo ""
echo "Next steps:"
echo "1. Run the scan:"
echo "   gcloud dataplex datascans run ${SCAN_ID} --project=${PROJECT_ID} --location=${LOCATION}"
echo ""
echo "2. Check scan status:"
echo "   gcloud dataplex datascans jobs list --datascan=${SCAN_ID} --project=${PROJECT_ID} --location=${LOCATION}"
echo ""
echo "3. Use in metadata collector:"
echo "   poetry run python scripts/collect-bigquery-metadata.py --use-dataplex --dataplex-location ${LOCATION}"

