# BigQuery Data Estate Discovery System

A dual-mode AI-powered discovery system for BigQuery metadata, combining cached semantic search with live agent-based discovery.

## 🎯 Project Status

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 0** | ✅ Complete | Infrastructure (GKE, GCS, Service Accounts) |
| **Phase 1** | ✅ Complete | Vertex AI Search (Cached Discovery Path) |
| **Phase 2.1** | ✅ Complete | BigQuery Metadata Collector (Multi-threaded, Dataplex, Gemini) |
| **Phase 2.2+** | ⏳ Pending | Cost Analysis, Advanced Lineage |
| **Phase 3** | ⏳ Pending | Smart Query Router |
| **Phase 4+** | ⏳ Pending | Live Agents & Advanced Features |

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                  Dual-Mode Architecture                     │
└─────────────────────────────────────────────────────────────┘

Cached Path (90%+ of queries, <200ms):
  User Query → Router → Vertex AI Search → Results

Live Path (Complex queries, 5-30s):
  User Query → Router → GenAI Toolbox Agents → Results

Background:
  Discovery Agents → JSONL → GCS → Vertex AI Search (1-5 min)
```

## 🚀 Quick Start

### Prerequisites

- GCP Project with required APIs enabled
- Region: `us-central1` (or your preferred region)
- Shared VPC (optional, or use default VPC)
- `gcloud` CLI with alpha components
- Terraform >= 1.0
- Python >= 3.9
- Poetry for dependency management

### 1. Deploy Infrastructure (Phase 0)

```bash
# Navigate to terraform directory
cd terraform

# Create terraform.tfvars
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values

# Deploy
terraform init
terraform apply

# Configure kubectl
gcloud container clusters get-credentials data-discovery-cluster \
    --region=us-central1 \
    --project=YOUR_PROJECT_ID
```

### 2. Deploy Vertex AI Search (Phase 1)

```bash
# Run automated setup
./scripts/setup-vertex-search.sh

# Or manually:
cd terraform/vertex-ai-search
terraform init
terraform apply -var="project_id=YOUR_PROJECT_ID"

# Create data store
gcloud alpha discovery-engine data-stores create data-discovery-metadata \
    --project=YOUR_PROJECT_ID \
    --location=global \
    --collection=default_collection \
    --industry-vertical=GENERIC \
    --content-config=CONTENT_REQUIRED \
    --solution-type=SOLUTION_TYPE_SEARCH
```

### 3. Test Phase 1 Components

```bash
# Install dependencies
poetry install

# Run example script
python examples/phase1_complete_example.py
```

## 📦 What's Included

### Phase 0: Infrastructure ✅

**GKE Cluster:**
- Private cluster (no external IPs)
- Machine type: `e2-standard-2`
- Autoscaling: 2-5 nodes
- Workload Identity enabled
- Network: Shared VPC `ula`

**GCS Buckets:**
- `{project-id}-data-discovery-jsonl` (JSONL metadata)
- `{project-id}-data-discovery-reports` (Markdown reports)

**Service Accounts:**
- `data-discovery-agent`: Read-only access to BigQuery, Dataplex
- `data-discovery-metadata`: Metadata write access (approval required)
- `data-discovery-gke`: GKE node service account

**GenAI Toolbox (Phase 0.2):**
- Deployed on GKE with Internal LoadBalancer
- MCP protocol for agent communication
- BigQuery, Dataplex, Data Catalog tools
- Read-only with query validation

### Phase 1: Vertex AI Search ✅

**Infrastructure:**
- Vertex AI Search data store
- Service account for ingestion
- IAM bindings

**Python Components:**

1. **JSONL Schema** (`search/jsonl_schema.py`)
   - Document structure for Vertex AI Search
   - Filterable fields + searchable content
   - Volatility-based caching

2. **Metadata Formatter** (`search/metadata_formatter.py`)
   - Transforms discovery outputs to JSONL
   - Generates rich searchable content
   - Exports to GCS

3. **Markdown Formatter** (`search/markdown_formatter.py`)
   - Creates comprehensive reports
   - Executive summaries, metrics, cost analysis
   - Exports to GCS

4. **Query Builder** (`search/query_builder.py`)
   - Parses natural language queries
   - Extracts structured filters
   - Builds hybrid queries

5. **Result Parser** (`search/result_parser.py`)
   - Formats search results
   - Generates console links
   - Provides suggestions

6. **Vertex Search Client** (`clients/vertex_search_client.py`)
   - High-level API wrapper
   - Query building and parsing
   - Document ingestion

**Data Models:**
- Search request/response models
- Discovery request/response models
- Asset metadata models

### Phase 2.1: BigQuery Metadata Collector ✅

**BigQuery Collector** (`collectors/bigquery_collector.py`):
- Project/dataset/table scanning
- Schema extraction (nested fields)
- Statistics collection (rows, size, timestamps)
- Basic cost estimation
- PII/PHI indicator detection
- Progress tracking and error handling

**Collection Script** (`scripts/collect-bigquery-metadata.py`):
- CLI interface for metadata collection
- Flexible filtering (projects, datasets, table limits)
- GCS upload automation
- Vertex AI Search import triggering
- Comprehensive logging and statistics

**Features:**
- ✅ Automated collection from multiple datasets
- ✅ **Multi-threaded processing** (5x faster with default 5 workers)
- ✅ **Dataplex Data Profile Scan integration** (column profiling, sample values)
- ✅ **Gemini AI integration** (auto-descriptions, analytical insights)
- ✅ JSONL export for Vertex AI Search
- ✅ Markdown reports for documentation
- ✅ Vertex AI Search import automation
- ✅ Error handling and progress tracking

## 💡 Usage Examples

### Collect BigQuery Metadata

```bash
# Collect all tables from current project (default: auto-detect CPU cores)
poetry run python scripts/collect-bigquery-metadata.py --import

# Test with limited tables
poetry run python scripts/collect-bigquery-metadata.py --max-tables 10 --skip-gcs

# Fast collection with more workers (10 threads)
poetry run python scripts/collect-bigquery-metadata.py --workers 10 --import

# Collect from specific projects with multi-threading
poetry run python scripts/collect-bigquery-metadata.py \
  --projects proj1 proj2 \
  --exclude-datasets "_staging" "temp_" \
  --workers 8 \
  --import

# With Dataplex profiling and Gemini insights
poetry run python scripts/collect-bigquery-metadata.py \
  --use-dataplex \
  --use-gemini \
  --workers 5 \
  --import
```

**Performance**: Multi-threading provides **~5x speedup** (auto-scaled to CPU cores).  
See [`MULTITHREADING.md`](MULTITHREADING.md) for detailed performance tuning.

### Search for Tables with PII

```python
from data_discovery_agent.clients import VertexSearchClient
from data_discovery_agent.models import SearchRequest

client = VertexSearchClient(
    project_id="YOUR_PROJECT_ID",
    location="global",
    datastore_id="data-discovery-metadata",
)

response = client.search(SearchRequest(
    query="customer tables with PII",
    has_pii=True,
    page_size=10,
))

for result in response.results:
    print(f"{result.title}: {result.metadata.row_count:,} rows")
```

### Format and Export Metadata

```python
from data_discovery_agent.search import MetadataFormatter

formatter = MetadataFormatter(project_id="YOUR_PROJECT_ID")

asset = formatter.format_bigquery_table(
    table_metadata={...},
    cost_info={"monthly_cost_usd": 125.50},
    security_info={"has_pii": True},
)

gcs_uri = formatter.export_batch_to_gcs(
    documents=[asset],
    gcs_bucket="YOUR_PROJECT_ID-data-discovery-jsonl",
)
```

### Generate Markdown Report

```python
from data_discovery_agent.search import MarkdownFormatter

formatter = MarkdownFormatter(project_id="YOUR_PROJECT_ID")
report = formatter.generate_table_report(asset)

formatter.export_to_gcs(
    markdown=report,
    gcs_bucket="YOUR_PROJECT_ID-data-discovery-reports",
    gcs_path="finance/transactions.md",
)
```

## 📊 Performance

| Metric | Target | Status |
|--------|--------|--------|
| Cached Query Latency | <200ms | ✅ Designed |
| Live Query Latency | 5-30s | ✅ Designed |
| Cache Hit Rate | >90% | ⏳ Phase 3 |
| Concurrent Users | 100+ | ✅ Designed |

## 💰 Cost Estimate

**Monthly Cost (us-central1):**

| Component | Cost |
|-----------|------|
| GKE Cluster (2x e2-standard-2) | ~$100 |
| GCS Storage (50GB) | ~$1 |
| Vertex AI Search (100K docs, 100K queries) | ~$1,300 |
| BigQuery queries (agent reads) | ~$50 |
| **Total** | **~$1,450/month** |

## 🔒 Security & Compliance

**SR-2A Compliance:**
- ✅ Read-only access to source data
- ✅ Metadata writes require approval
- ✅ Audit logging enabled
- ✅ Workload Identity for service accounts
- ✅ Private GKE cluster (no external IPs)
- ✅ Encryption at rest and in transit

**PII/PHI Handling:**
- ✅ Automatic classification via DLP
- ✅ Never stores actual data values
- ✅ Metadata-only approach

## 📚 Documentation

- **[Phase 1 Architecture](docs/PHASE1_VERTEX_SEARCH.md)**: Detailed Phase 1 documentation
- **[Phase 1 Summary](PHASE1_SUMMARY.md)**: Phase 1 completion summary
- **[Phase 2.1 Metadata Collection](docs/PHASE2_METADATA_COLLECTION.md)**: BigQuery collector documentation
- **[Architecture](docs/ARCHITECTURE.md)**: Overall system architecture
- **[Project Plan](.cursor/plans/bigquery-discovery-system-217d0748.plan.md)**: Complete project plan
- **[Terraform README](terraform/README.md)**: Infrastructure documentation
- **[GenAI Toolbox README](terraform/genai-toolbox/README.md)**: Agent deployment docs

## 🗂️ Project Structure

```
data-discovery-agent/
├── src/data_discovery_agent/
│   ├── search/              # Phase 1: Search components
│   │   ├── jsonl_schema.py
│   │   ├── metadata_formatter.py
│   │   ├── markdown_formatter.py
│   │   ├── query_builder.py
│   │   └── result_parser.py
│   ├── collectors/          # Phase 2: Metadata collectors
│   │   └── bigquery_collector.py
│   ├── models/              # Data models
│   │   ├── search_models.py
│   │   ├── discovery_request.py
│   │   └── discovery_response.py
│   └── clients/             # API clients
│       └── vertex_search_client.py
├── terraform/
│   ├── main.tf              # Phase 0: GKE cluster
│   ├── storage.tf           # GCS buckets
│   ├── service-accounts.tf  # IAM
│   ├── genai-toolbox/       # Phase 0.2: GenAI Toolbox
│   └── vertex-ai-search/    # Phase 1: Vertex AI Search
├── config/
│   └── genai-toolbox/       # GenAI Toolbox configuration
├── scripts/
│   ├── setup-infrastructure.sh
│   ├── setup-vertex-search.sh
│   ├── deploy-genai-toolbox.sh
│   ├── validate-setup.sh
│   └── collect-bigquery-metadata.py  # Phase 2.1
├── examples/
│   └── phase1_complete_example.py
└── docs/
    ├── ARCHITECTURE.md
    ├── PHASE1_VERTEX_SEARCH.md
    └── PHASE2_METADATA_COLLECTION.md
```

## 🛠️ Development

### Install Dependencies

```bash
# Using poetry
poetry install

# Or using pip
pip install -r requirements.txt
```

### Run Tests

```bash
pytest
```

### Code Formatting

```bash
black src/
ruff check src/
```

## 🚦 Next Steps

### Immediate
1. ✅ Complete Phase 1 (DONE!)
2. ✅ Complete Phase 2.1 (DONE!)
3. **Wait 5-10 minutes** for Vertex AI Search indexing
4. **Test search** with your BigQuery metadata

### Phase 2.2+ (Enhanced Discovery)
1. Add Dataplex metadata integration
2. Build Data Catalog lineage analyzer
3. Add Cloud Billing API for precise costs
4. Create scheduled collection (Cloud Scheduler)
5. Set up incremental updates

### Phase 3 (Smart Router)
1. Build query classifier
2. Implement routing logic
3. Integrate cached and live paths
4. Add result merging

### Phase 4+ (Live Agents)
1. Deep inspection agent
2. Data profiling agent
3. Query analysis agent
4. Cost optimization agent

## 🤝 Contributing

This is an internal project for BigQuery data discovery. For questions or issues:
- Review documentation in `docs/`
- Check project plan in `.cursor/plans/`
- Contact the development team

## 📄 License

Internal use only.

## 🎉 Acknowledgments

Built with:
- Google Cloud Platform (GKE, BigQuery, Vertex AI Search)
- Google GenAI Toolbox (MCP agents)
- Terraform (Infrastructure as Code)
- Python + Pydantic (Data models)
- Vertex AI Search (Semantic search)

---

**Current Status**: Phase 0, Phase 1, and Phase 2.1 Complete ✅  
**Production Ready**: Automated BigQuery metadata discovery  
**Ready for**: Natural language metadata search and Phase 2.2+ 🚀
