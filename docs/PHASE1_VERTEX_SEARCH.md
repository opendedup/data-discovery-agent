# Phase 1: Vertex AI Search Infrastructure

**Status**: ✅ **COMPLETE**

## Overview

Phase 1 establishes the **cached discovery path** using Vertex AI Search. This is the core of the dual-mode architecture, enabling sub-second responses for 90%+ of discovery queries.

## What Was Built

### 1. Infrastructure (Terraform)

**Location**: `terraform/vertex-ai-search/`

- **Vertex AI Search Data Store**: Managed search index for metadata
- **Service Accounts**: Dedicated SA for search ingestion
- **IAM Bindings**: Permissions for discovery agents to use search
- **API Enablement**: Discovery Engine API

### 2. Data Models (Python/Pydantic)

**Location**: `src/data_discovery_agent/`

#### JSONL Schema (`search/jsonl_schema.py`)
- `BigQueryAssetSchema`: Document structure for Vertex AI Search
- `StructData`: Filterable fields (project, dataset, has_pii, cost, etc.)
- `ContentData`: Semantically searchable text
- `JSONLDocument`: Export format for ingestion

#### Search Models (`models/search_models.py`)
- `SearchRequest`: High-level search interface
- `SearchResponse`: Structured results with metadata
- `SearchResultItem`: Single search result
- `AggregationRequest/Response`: Faceted search and statistics

#### Discovery Models (`models/`)
- `DiscoveryRequest`: Universal request for all query types
- `DiscoveryResponse`: Universal response wrapper
- `InspectRequest/Response`: Deep asset inspection
- `LineageRequest/Response`: Dependency graphs
- `ProfileRequest/Response`: Data profiling

### 3. Core Components

#### Metadata Formatter (`search/metadata_formatter.py`)
**Critical component** that transforms raw discovery outputs to JSONL.

Features:
- Aggregates metadata from multiple sources
- Generates rich, searchable content text
- Creates structured filterable fields
- Handles incremental updates
- Manages cache TTLs based on volatility

#### Markdown Formatter (`search/markdown_formatter.py`)
Generates human-readable reports from metadata.

Features:
- Beautiful, comprehensive reports
- Executive summaries with key metrics
- Schema tables, cost analysis, quality scores
- Export to GCS for sharing

#### Query Builder (`search/query_builder.py`)
Translates natural language to Vertex AI Search queries.

Features:
- Parses user queries into semantic + structured components
- Extracts filters (project, dataset, has_pii, cost, etc.)
- Builds hybrid queries (semantic + structured)
- Adds boost factors for relevance ranking

#### Result Parser (`search/result_parser.py`)
Parses and enriches search results.

Features:
- Formats results for display (text, markdown, JSON)
- Generates console links to BigQuery
- Creates suggested queries
- Handles pagination

#### Vertex Search Client (`clients/vertex_search_client.py`)
High-level client wrapping Discovery Engine API.

Features:
- Search with our data models
- Document ingestion from GCS
- Batch operations
- Health checks and monitoring

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Discovery Flow                          │
└─────────────────────────────────────────────────────────────┘

1. Background Indexing (Scheduled):
   
   Discovery Agents → MetadataFormatter → JSONL Files → GCS
                                                          ↓
                                        Vertex AI Search Ingestion
                                                          ↓
                                          Search Index (Cached)

2. User Queries (Real-time):

   User Query → QueryBuilder → Vertex AI Search → ResultParser
                                                          ↓
                                               Formatted Results

3. Dual-Mode Routing (Phase 3):

   User Query → Smart Router → [Cached Path] OR [Live Agent Path]
```

## Data Flow

### Indexing Flow

1. **Discovery Agent** scans BigQuery tables
2. **MetadataFormatter** transforms to `BigQueryAssetSchema`
3. Export as JSONL to GCS bucket
4. Vertex AI Search ingests JSONL files
5. **Search index** is updated (1-5 min delay)

### Query Flow

1. User submits natural language query
2. **QueryBuilder** parses into semantic + structured components
3. **VertexSearchClient** executes search
4. **ResultParser** formats results
5. Results returned with citations and console links

## Example Usage

### 1. Format and Export Metadata

```python
from data_discovery_agent.search import MetadataFormatter

formatter = MetadataFormatter(project_id="lennyisagoodboy")

# Format BigQuery table metadata
asset = formatter.format_bigquery_table(
    table_metadata={
        "dataset_id": "finance",
        "table_id": "transactions",
        "num_rows": 5000000,
        "num_bytes": 2500000000,
    },
    cost_info={"monthly_cost_usd": 125.50},
    security_info={"has_pii": True},
)

# Export to GCS for ingestion
gcs_uri = formatter.export_batch_to_gcs(
    documents=[asset],
    gcs_bucket="lennyisagoodboy-data-discovery-jsonl",
    batch_id="20240115_120000",
)

print(f"Exported to: {gcs_uri}")
```

### 2. Search Metadata

```python
from data_discovery_agent.clients import VertexSearchClient
from data_discovery_agent.models import SearchRequest

client = VertexSearchClient(
    project_id="lennyisagoodboy",
    location="us-central1",
    datastore_id="data-discovery-metadata",
)

# Search for PII tables
request = SearchRequest(
    query="customer tables with PII",
    has_pii=True,
    page_size=10,
    sort_by="monthly_cost_usd",
    sort_order="desc",
)

response = client.search(request)

print(response.get_summary())

for result in response.results:
    print(f"\n{result.title}")
    print(f"  Type: {result.metadata.asset_type}")
    print(f"  Rows: {result.metadata.row_count:,}")
    print(f"  Cost: ${result.metadata.monthly_cost_usd:.2f}/month")
    print(f"  {result.snippet[:100]}...")
```

### 3. Generate Markdown Report

```python
from data_discovery_agent.search import MarkdownFormatter

formatter = MarkdownFormatter(project_id="lennyisagoodboy")

# Generate report from asset
report = formatter.generate_table_report(
    asset=asset,
    extended_metadata={
        "schema": {"fields": [...]},
        "lineage": {"upstream_tables": [...], "downstream_tables": [...]},
        "usage": {"query_count_30d": 1250},
    }
)

# Export to GCS
formatter.export_to_gcs(
    markdown=report,
    gcs_bucket="lennyisagoodboy-data-discovery-reports",
    gcs_path="finance/transactions.md",
)
```

## Deployment

### Prerequisites

- GKE cluster deployed (Phase 0)
- GCS buckets created (Phase 0)
- Service accounts configured (Phase 0)
- `gcloud` CLI with alpha components
- Terraform

### Deploy Vertex AI Search

```bash
cd /home/user/git/data-discovery-agent

# Run setup script
./scripts/setup-vertex-search.sh

# Or manually:
cd terraform/vertex-ai-search
terraform init
terraform apply \
    -var="project_id=lennyisagoodboy" \
    -var="region=us-central1" \
    -var="datastore_id=data-discovery-metadata" \
    -var="jsonl_bucket_name=lennyisagoodboy-data-discovery-jsonl"

# Create data store
gcloud alpha discovery-engine data-stores create data-discovery-metadata \
    --project=lennyisagoodboy \
    --location=us-central1 \
    --collection=default_collection \
    --industry-vertical=GENERIC \
    --content-config=CONTENT_REQUIRED \
    --solution-type=SOLUTION_TYPE_SEARCH
```

### Import Data

```bash
# Import JSONL files from GCS
gcloud alpha discovery-engine data-stores import documents \
    --project=lennyisagoodboy \
    --location=us-central1 \
    --data-store=data-discovery-metadata \
    --gcs-uri=gs://lennyisagoodboy-data-discovery-jsonl/*.jsonl
```

## Query Examples

| User Query | How It Works |
|------------|--------------|
| "Find PII tables in finance" | Semantic: "PII tables" + Filter: `dataset_id="finance"` |
| "Most expensive tables" | Semantic: "expensive high cost" + Sort: `monthly_cost_usd DESC` |
| "Tables modified today" | Filter: `last_modified_timestamp > "2024-01-15"` |
| "Sales pipeline tables" | Semantic: "sales pipeline customer funnel" |
| "Large tables with quality issues" | Semantic: "quality issues" + Filter: `row_count > 1000000` |

## Performance

- **Query Latency**: 50-200ms for most queries
- **Throughput**: 100+ QPS supported
- **Index Build Time**: 2-10 minutes for initial indexing
- **Index Updates**: Near real-time (1-5 minute delay)

## Cost

**Vertex AI Search Pricing (us-central1):**

| Component | Cost |
|-----------|------|
| Storage | $0.60/GB/month |
| Queries | $5.00 per 1000 queries |
| Indexing | $2.00 per 1000 documents |

**Example Monthly Cost:**
- 100,000 BigQuery tables @ 10KB each = 1GB storage = $0.60
- 100,000 queries/month = $500
- Weekly re-indexing (400K documents/month) = $800

**Total**: ~$1,300/month

**Cost Optimization:**
- Cache frequent queries
- Use incremental updates
- Set appropriate TTLs for metadata freshness

## Monitoring

### Check Data Store Status

```bash
gcloud alpha discovery-engine data-stores describe data-discovery-metadata \
    --project=lennyisagoodboy \
    --location=us-central1
```

### View Import Operations

```bash
gcloud alpha discovery-engine operations list \
    --project=lennyisagoodboy \
    --location=us-central1
```

### Check Logs

```bash
gcloud logging read 'resource.type="discoveryengine.googleapis.com/DataStore"' \
    --project=lennyisagoodboy \
    --limit=50
```

## Integration Points

### With Phase 0 (Infrastructure)
- Uses GCS buckets created in Phase 0
- Uses service accounts configured in Phase 0
- Runs discovery agents on GKE cluster

### With Phase 2 (Background Agents)
- Discovery agents generate JSONL files
- MetadataFormatter transforms agent outputs
- Scheduled ingestion keeps index fresh

### With Phase 3 (Smart Router)
- Router sends cached queries to Vertex AI Search
- Router sends live queries to GenAI Toolbox
- Hybrid queries use both paths

## Next Steps

After Phase 1 is complete:

1. **Phase 2**: Build background discovery agents
   - BigQuery metadata collector
   - Lineage analyzer
   - Cost analyzer
   - Scheduled indexing pipeline

2. **Phase 3**: Build Smart Query Router
   - Classify user queries (cached vs. live)
   - Route to appropriate backend
   - Merge results from both paths

3. **Phase 4**: Build discovery agents for live queries
   - Deep inspection agent
   - Lineage agent
   - Data profiling agent
   - Query analysis agent

## Troubleshooting

### Data Store Not Found

```bash
# List all data stores
gcloud alpha discovery-engine data-stores list \
    --project=lennyisagoodboy \
    --location=global

# Try global location if not in us-central1
```

### Import Failures

Check Cloud Logging for errors:
- Invalid JSONL format
- Missing required fields (`id`, `structData`, `content`)
- GCS bucket permissions

### Query Returns No Results

1. Verify data has been ingested
2. Check filter syntax
3. Test semantic search without filters
4. Check index build status

## Files Created

```
terraform/vertex-ai-search/
├── vertex-search.tf              # Terraform configuration
└── README.md                     # Infrastructure documentation

src/data_discovery_agent/
├── search/
│   ├── __init__.py
│   ├── jsonl_schema.py           # JSONL schema definitions
│   ├── metadata_formatter.py     # Metadata to JSONL transformer
│   ├── markdown_formatter.py     # Markdown report generator
│   ├── query_builder.py          # Query builder
│   └── result_parser.py          # Result parser
├── models/
│   ├── __init__.py
│   ├── search_models.py          # Search request/response models
│   ├── discovery_request.py      # Discovery request models
│   └── discovery_response.py     # Discovery response models
└── clients/
    ├── __init__.py
    └── vertex_search_client.py   # Vertex AI Search client

scripts/
└── setup-vertex-search.sh        # Automated setup script

docs/
└── PHASE1_VERTEX_SEARCH.md       # This document
```

## References

- [Vertex AI Search Documentation](https://cloud.google.com/generative-ai-app-builder/docs/enterprise-search-introduction)
- [Discovery Engine API](https://cloud.google.com/discovery-engine/docs)
- [JSONL Schema Reference](https://cloud.google.com/discovery-engine/docs/prepare-data)
- [Project Plan](.cursor/plans/bigquery-discovery-system-217d0748.plan.md)
- [Architecture Documentation](docs/ARCHITECTURE.md)

---

**Phase 1 Status**: ✅ Complete  
**Next Phase**: Phase 2 - Background Discovery Agents

