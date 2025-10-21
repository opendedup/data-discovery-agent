#!/bin/bash
# Helper script to check the lineage results after DAG completes

set -euo pipefail

echo "========================================"
echo "Checking Lineage Results"
echo "========================================"
echo ""

# Get the latest report timestamp
echo "1. Finding latest report run..."
LATEST_RUN=$(gsutil ls gs://lennyisagoodboy-data-discovery-reports/reports/ | sort | tail -1)
echo "   Latest run: $LATEST_RUN"
echo ""

# Check the odds.md file
echo "2. Checking odds table lineage in markdown..."
ODDS_MD="${LATEST_RUN}lennyisagoodboy/lfndata/odds.md"
echo "   Report: $ODDS_MD"
echo ""

gsutil cat "$ODDS_MD" | grep -A 25 "## Data Lineage"
echo ""

# Check BigQuery data
echo "3. Checking lineage in BigQuery..."
bq query --nouse_legacy_sql --format=prettyjson "
SELECT 
  table_id,
  ARRAY_LENGTH(lineage) as lineage_count,
  lineage
FROM \`lennyisagoodboy.data_discovery.discovered_assets\`
WHERE table_id = 'odds'
  AND insert_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 MINUTE)
ORDER BY insert_timestamp DESC
LIMIT 1
" 2>&1 | head -100

echo ""
echo "========================================"
echo "Check complete!"
echo "========================================"

