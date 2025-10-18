# Phase 2.1: BigQuery Metadata Collection

Automated metadata collection from BigQuery for Vertex AI Search indexing.

## Overview

The BigQuery Metadata Collector scans your BigQuery projects, datasets, and tables to extract comprehensive metadata that is then indexed in Vertex AI Search for natural language discovery.

## Architecture

```
┌─────────────────┐
│   BigQuery      │
│  (Data Source)  │
└────────┬────────┘
         │
         │ Scan
         ▼
┌──────────────────────────┐
│  BigQuery Collector      │
│  - List projects         │
│  - List datasets         │
│  - Extract table metadata│
│  - Schema analysis       │
│  - Cost estimation       │
│  - PII detection         │
└──────────┬───────────────┘
           │
           │ Format to JSONL
           ▼
┌──────────────────────────┐
│  Metadata Formatter      │
│  - Structured metadata   │
│  - Markdown content      │
│  - JSONL output          │
└──────────┬───────────────┘
           │
           │ Upload
           ▼
┌──────────────────────────┐
│  GCS Bucket              │
│  (JSONL Storage)         │
└──────────┬───────────────┘
           │
           │ Import
           ▼
┌──────────────────────────┐
│  Vertex AI Search        │
│  (Searchable Index)      │
└──────────────────────────┘
```

## Components

### 1. BigQueryCollector (`src/data_discovery_agent/collectors/bigquery_collector.py`)

Main collector class that orchestrates the metadata collection process.

**Key Features:**
- Project-level scanning
- Dataset filtering (exclude temp/staging datasets)
- Table and view collection
- Schema extraction with nested field support
- Basic cost estimation
- PII indicator detection (heuristic-based)
- Progress tracking and statistics
- Error handling and retry logic

**Usage:**
```python
from data_discovery_agent.collectors import BigQueryCollector

collector = BigQueryCollector(
    project_id="lennyisagoodboy",
    target_projects=["lennyisagoodboy"],  # Optional, defaults to current project
    exclude_datasets=["_staging", "temp_"],  # Optional patterns to exclude
)

# Collect all tables
assets = collector.collect_all(
    max_tables=None,  # None = unlimited
    include_views=True,
)

# Get statistics
stats = collector.get_stats()
```

### 2. Collection Script (`scripts/collect-bigquery-metadata.py`)

Command-line interface for running metadata collection.

**Basic Usage:**
```bash
# Collect from current project
poetry run python scripts/collect-bigquery-metadata.py

# Collect from specific projects
poetry run python scripts/collect-bigquery-metadata.py \
  --projects proj1 proj2

# Test with limited tables
poetry run python scripts/collect-bigquery-metadata.py \
  --max-tables 10 \
  --skip-gcs

# Full collection with import
poetry run python scripts/collect-bigquery-metadata.py --import
```

**All Options:**
```
Collection Options:
  --project PROJECT          GCP project ID (default: lennyisagoodboy)
  --projects PROJ1 PROJ2...  Target projects to scan
  --max-tables N             Maximum tables to collect (for testing)
  --exclude-datasets PATTERNS Dataset patterns to exclude
  --skip-views               Skip views, collect tables only

Export Options:
  --output PATH              Local output path for JSONL
  --gcs-bucket BUCKET        GCS bucket for JSONL export (default: lennyisagoodboy-data-discovery-jsonl)
  --reports-bucket BUCKET    GCS bucket for Markdown reports (default: lennyisagoodboy-data-discovery-reports)
  --skip-gcs                 Skip GCS upload
  --skip-markdown            Skip Markdown report generation

Import Options:
  --import                   Trigger Vertex AI Search import
  --datastore ID             Vertex AI Search data store ID

Other:
  -v, --verbose              Verbose logging
```

## Collected Metadata

For each BigQuery table, the collector extracts:

### Core Metadata
- Project, dataset, and table IDs
- Table type (TABLE, VIEW, EXTERNAL, MATERIALIZED_VIEW)
- Description
- Row count and size in bytes
- Created and modified timestamps

### Schema Information
- Column names, types, modes (REQUIRED, NULLABLE, REPEATED)
- Column descriptions
- Nested field structures (STRUCT, ARRAY)
- Column count

### Cost Estimation (Basic)
- Storage cost (active vs long-term)
- Estimated query cost
- Total monthly cost estimate

> **Note**: Phase 2.1 provides basic cost estimates based on storage size. Phase 2.2 will add precise billing data from Cloud Billing API.

### Security & Governance
- **PII Detection**: Heuristic-based detection of potential PII columns
  - Keywords: email, phone, ssn, address, name, dob, etc.
- **PHI Detection**: Healthcare-related data detection
  - Keywords: diagnosis, medical, patient, prescription, etc.
- **Labels**: BigQuery labels as tags
- **Classification**: Automatic tagging (PII, PHI, etc.)

> **Note**: Phase 2.1 uses keyword-based heuristics. Future phases will integrate DLP API for precise PII/PHI detection.

### Output Format
Each table is exported as JSONL with two main sections:

1. **Structured Data** (`structData`): Queryable metadata fields
2. **Content** (`content`): Human-readable Markdown report

Example:
```json
{
  "id": "project.dataset.table",
  "structData": {
    "project_id": "project",
    "dataset_id": "dataset",
    "table_id": "table",
    "asset_type": "TABLE",
    "has_pii": true,
    "row_count": 1000,
    "size_bytes": 50000,
    "monthly_cost_usd": 0.001,
    "tags": ["production", "finance"]
  },
  "content": {
    "mime_type": "text/plain",
    "text": "# dataset.table\n\n**Type**: TABLE\n..."
  }
}
```

## Performance

**Collection Speed:**
- ~30-40 tables per minute (average)
- Depends on:
  - Network latency
  - Schema complexity
  - BigQuery API rate limits

**Resource Usage:**
- Minimal CPU/memory (metadata only, no data scanned)
- No BigQuery query costs (uses Information Schema APIs)
- Only GCS storage costs for JSONL files

**Scalability:**
- Tested: 34 tables in ~4 seconds
- Can handle 1000+ tables per run
- Progress tracking every 10 tables
- Automatic error recovery

## Error Handling

The collector includes comprehensive error handling:

1. **Project-level errors**: Continue to next project
2. **Dataset-level errors**: Continue to next dataset
3. **Table-level errors**: Skip table, continue collection
4. **Statistics tracking**: Count errors for monitoring

All errors are logged with context:
```python
logger.error(f"Error scanning dataset {dataset_id}: {e}")
```

## Dataset Filtering

By default, the collector excludes:
- `_staging`: Staging/temporary datasets
- `temp_`: Temporary prefixes
- `tmp_`: Temporary prefixes

Override with:
```bash
poetry run python scripts/collect-bigquery-metadata.py \
  --exclude-datasets "_test" "sandbox"
```

## Integration with Vertex AI Search

The collected metadata is automatically imported into Vertex AI Search:

1. **Export**: Formatted as JSONL per Vertex AI Search schema
2. **Upload**: Stored in GCS bucket (`lennyisagoodboy-data-discovery-jsonl`)
3. **Import**: Triggered via Discovery Engine API
4. **Indexing**: Takes 2-10 minutes to complete

**Check Import Status:**
```bash
gcloud alpha discovery-engine operations describe OPERATION_NAME \
  --project=lennyisagoodboy \
  --location=global
```

Or in Cloud Console:
https://console.cloud.google.com/gen-app-builder/engines?project=lennyisagoodboy

## Scheduling

To run collection on a schedule:

### Option 1: Cloud Scheduler + Cloud Run Jobs
```yaml
# Cloud Run Job (recommended)
gcloud run jobs create bigquery-collector \
  --image=gcr.io/lennyisagoodboy/data-discovery-collector:latest \
  --region=us-central1 \
  --service-account=data-discovery-agent@lennyisagoodboy.iam.gserviceaccount.com

# Cloud Scheduler
gcloud scheduler jobs create http bigquery-daily-scan \
  --schedule="0 2 * * *" \
  --uri="https://us-central1-run.googleapis.com/v1/projects/lennyisagoodboy/locations/us-central1/jobs/bigquery-collector:run" \
  --http-method=POST
```

### Option 2: GKE CronJob
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: bigquery-metadata-collector
  namespace: data-discovery
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: collector
            image: gcr.io/lennyisagoodboy/data-discovery-collector:latest
            command:
            - python
            - scripts/collect-bigquery-metadata.py
            - --import
          restartPolicy: OnFailure
          serviceAccountName: discovery-agent
```

## Testing

### Test with Limited Tables
```bash
poetry run python scripts/collect-bigquery-metadata.py \
  --max-tables 10 \
  --skip-gcs \
  --verbose
```

### Test GCS Upload Only
```bash
poetry run python scripts/collect-bigquery-metadata.py \
  --max-tables 5 \
  --skip-import
```

### Test Full Pipeline
```bash
poetry run python scripts/collect-bigquery-metadata.py \
  --max-tables 5 \
  --import \
  --verbose
```

## Monitoring

The collector provides statistics:
```
Statistics:
  Projects scanned:  1
  Datasets scanned:  2
  Tables scanned:    34
  Assets exported:   34
  Errors:            0
```

In production, send these to Cloud Monitoring:
```python
from google.cloud import monitoring_v3

client = monitoring_v3.MetricServiceClient()
# Write custom metrics...
```

## Troubleshooting

### No Tables Found
**Issue**: `⚠️  No tables found or collected`

**Solutions:**
1. Check project permissions:
   ```bash
   gcloud projects get-iam-policy lennyisagoodboy
   ```
2. Verify dataset access:
   ```bash
   bq ls --project_id=lennyisagoodboy
   ```
3. Check exclusion patterns

### Import Fails
**Issue**: `⚠️  Import trigger failed`

**Solutions:**
1. Verify Discovery Engine API is enabled
2. Check service account permissions
3. Manually trigger:
   ```bash
   gcloud alpha discovery-engine data-stores import documents \
     --project=lennyisagoodboy \
     --location=global \
     --data-store=data-discovery-metadata \
     --gcs-uri=gs://lennyisagoodboy-data-discovery-jsonl/metadata/*.jsonl
   ```

### GCS Upload Fails
**Issue**: `⚠️  GCS upload failed`

**Solutions:**
1. Check bucket permissions:
   ```bash
   gsutil iam get gs://lennyisagoodboy-data-discovery-jsonl
   ```
2. Verify service account has `roles/storage.objectCreator`

## Next Steps

With Phase 2.1 complete, you can:

1. **Phase 2.2**: Add Dataplex metadata integration
2. **Phase 2.3**: Add Data Catalog lineage tracking
3. **Phase 2.4**: Add Cloud Billing API for precise costs
4. **Phase 3**: Build the Live Agent for natural language queries

## Example Output

```bash
$ poetry run python scripts/collect-bigquery-metadata.py --import

======================================================================
BigQuery Metadata Collection - Phase 2.1
======================================================================

Project: lennyisagoodboy
Target projects: ['lennyisagoodboy']
Max tables: unlimited

Step 1: Collecting BigQuery metadata...
----------------------------------------------------------------------
Found 2 datasets in lennyisagoodboy
Found 9 tables in lennyisagoodboy.abndata
Found 25 tables in lennyisagoodboy.lfndata
✓ Collected 34 assets

Step 2: Exporting to JSONL...
----------------------------------------------------------------------
✓ Exported 34 documents to /tmp/bigquery_metadata_20251018_204244.jsonl
  File size: 66,971 bytes

Step 3: Uploading to GCS...
----------------------------------------------------------------------
✓ Uploaded to gs://lennyisagoodboy-data-discovery-jsonl/metadata/bigquery_metadata_20251018_204244.jsonl

Step 4: Triggering Vertex AI Search import...
----------------------------------------------------------------------
✓ Import triggered: projects/.../operations/import-documents-...
  This will take 2-10 minutes to complete

======================================================================
Collection Complete!
======================================================================

Statistics:
  Projects scanned:  1
  Datasets scanned:  2
  Tables scanned:    34
  Assets exported:   34
  Errors:            0
```

