# Vertex AI Search Infrastructure - Phase 1

This directory contains configuration for setting up Vertex AI Search, the core component of the cached discovery path.

## Overview

Vertex AI Search provides:
- **Semantic Search**: Natural language queries over metadata
- **Structured Filtering**: Exact matches on fields (project, dataset, has_pii, etc.)
- **Managed Service**: Google handles indexing, embeddings, and scaling
- **Sub-second Queries**: Fast responses for 90%+ of discovery queries

## Architecture

```
Discovery Agents → JSONL Files → GCS Bucket → Vertex AI Search
                                                      ↓
User Query → Smart Router → Vertex AI Search → Results with Citations
```

## Setup Instructions

### 1. Deploy Terraform

```bash
cd terraform/vertex-ai-search
terraform init
terraform apply \
  -var="project_id=lennyisagoodboy" \
  -var="jsonl_bucket_name=lennyisagoodboy-data-discovery-jsonl"
```

This creates:
- Service account for Vertex AI Search
- IAM bindings
- Enables Discovery Engine API

### 2. Create Data Store (Manual)

Currently, Vertex AI Search data stores need to be created via gcloud:

```bash
gcloud alpha discovery-engine data-stores create data-discovery-metadata \
  --project=lennyisagoodboy \
  --location=us-central1 \
  --collection=default_collection \
  --industry-vertical=GENERIC \
  --content-config=CONTENT_REQUIRED \
  --solution-type=SOLUTION_TYPE_SEARCH
```

**Parameters explained:**
- `data-discovery-metadata`: Data store ID
- `GENERIC`: Industry vertical (supports any data type)
- `CONTENT_REQUIRED`: Requires full content (not just URIs)
- `SOLUTION_TYPE_SEARCH`: Standard search (not recommendations)

### 3. Verify Data Store

```bash
gcloud alpha discovery-engine data-stores list \
  --project=lennyisagoodboy \
  --location=us-central1
```

## JSONL Schema

Documents ingested into Vertex AI Search use this schema:

```json
{
  "id": "project.dataset.table",
  "structData": {
    "project_id": "my-project",
    "dataset_id": "my_dataset",
    "table_id": "my_table",
    "data_source": "bigquery",
    "asset_type": "TABLE",
    "has_pii": true,
    "row_count": 1000000,
    "size_bytes": 500000000,
    "last_modified_timestamp": "2024-01-15T10:30:00Z",
    "monthly_cost_usd": 25.50,
    "indexed_at": "2024-01-15T12:00:00Z",
    "volatility": "low"
  },
  "content": {
    "mimeType": "text/plain",
    "text": "Rich searchable description including table name, purpose, columns, lineage, governance, and cost context"
  }
}
```

**structData**: Filterable fields for exact matching  
**content**: Semantically searchable text

## Ingesting Data

### Manual Ingestion

```bash
gcloud alpha discovery-engine data-stores import documents \
  --project=lennyisagoodboy \
  --location=us-central1 \
  --data-store=data-discovery-metadata \
  --gcs-uri=gs://lennyisagoodboy-data-discovery-jsonl/*.jsonl
```

### Programmatic Ingestion

Use the Python client (see `src/data_discovery_agent/clients/vertex_search_client.py`):

```python
from data_discovery_agent.clients.vertex_search_client import VertexSearchClient

client = VertexSearchClient(
    project_id="lennyisagoodboy",
    location="us-central1",
    datastore_id="data-discovery-metadata"
)

# Trigger ingestion from GCS
client.import_documents_from_gcs(
    gcs_uri="gs://lennyisagoodboy-data-discovery-jsonl/*.jsonl"
)
```

## Querying

### Semantic Search

```python
results = client.search(
    query="tables with customer PII",
    filter_expression='data_source="bigquery" AND has_pii=true'
)
```

### Structured Filtering

```python
results = client.search(
    query="",
    filter_expression='dataset_id="finance" AND row_count > 1000000'
)
```

### Hybrid (Semantic + Structured)

```python
results = client.search(
    query="high cost tables with quality issues",
    filter_expression='monthly_cost_usd > 100'
)
```

## Query Examples

| User Query | Vertex AI Search Query |
|------------|------------------------|
| "Find PII tables in finance" | `query="PII tables", filter='dataset_id="finance"'` |
| "Most expensive tables" | `query="expensive high cost", order_by="monthly_cost_usd DESC"` |
| "Tables modified today" | `query="", filter='last_modified_timestamp > "2024-01-15"'` |
| "Sales pipeline tables" | `query="sales pipeline customer funnel"` |

## Performance

- **Index Build Time**: 2-10 minutes for initial indexing
- **Query Latency**: 50-200ms for most queries
- **Throughput**: 100+ QPS supported
- **Index Updates**: Near real-time (1-5 minute delay)

## Cost

**Vertex AI Search Pricing (us-central1):**

| Component | Cost |
|-----------|------|
| **Storage** | $0.60/GB/month |
| **Queries** | $5.00 per 1000 queries |
| **Indexing** | $2.00 per 1000 documents |

**Example Monthly Cost:**
- 100,000 BigQuery tables @ 10KB each = 1GB storage = $0.60
- 100,000 queries/month = $500
- Re-indexing weekly (400K documents/month) = $800

**Total**: ~$1,300/month for moderate usage

**Cost Optimization:**
- Cache frequent queries in application layer
- Use incremental updates instead of full re-indexing
- Set appropriate TTLs for metadata freshness

## Monitoring

### Check Ingestion Status

```bash
gcloud alpha discovery-engine operations list \
  --project=lennyisagoodboy \
  --location=us-central1
```

### View Metrics

Navigate to Cloud Console:
1. Discovery Engine → Data Stores
2. Select `data-discovery-metadata`
3. View metrics: queries/sec, latency, error rate

### Logs

```bash
gcloud logging read 'resource.type="discoveryengine.googleapis.com/DataStore"' \
  --project=lennyisagoodboy \
  --limit=50
```

## Troubleshooting

### Data Store Not Found

```bash
# List all data stores
gcloud alpha discovery-engine data-stores list \
  --project=lennyisagoodboy \
  --location=global

# Try global location if not in us-central1
```

### Ingestion Failures

Check Cloud Logging for errors:
- Invalid JSONL format
- Missing required fields
- GCS bucket permissions

### Query Returns No Results

- Verify data has been ingested: Check document count in console
- Check filter syntax: Use exact field names from structData
- Test semantic search without filters first

## Integration with Discovery Agents

Once set up, discovery agents will:

1. **Background Indexers** (Phase 2):
   - Run scheduled discovery scans
   - Generate JSONL files
   - Upload to GCS bucket
   - Trigger Vertex AI Search ingestion

2. **Smart Query Router** (Phase 3):
   - Classify user queries
   - Route cached queries to Vertex AI Search
   - Parse and present results

## Next Steps

After Vertex AI Search is set up:

1. **Phase 1.3**: Implement metadata formatter (Python)
2. **Phase 1.4**: Implement search query builder
3. **Phase 2**: Create background discovery agents
4. **Phase 3**: Build Smart Query Router

## References

- [Vertex AI Search Documentation](https://cloud.google.com/generative-ai-app-builder/docs/enterprise-search-introduction)
- [Discovery Engine API](https://cloud.google.com/discovery-engine/docs)
- [JSONL Schema Reference](https://cloud.google.com/discovery-engine/docs/prepare-data)

