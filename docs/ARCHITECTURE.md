# Data Discovery Agent Architecture

## Overview

The Data Discovery Agent is a background indexing system that continuously discovers, catalogs, and makes BigQuery metadata searchable through Vertex AI Search. The system focuses on providing fast, semantic search over comprehensive metadata with rich markdown documentation.

This architecture prioritizes:
- **Background indexing** over live queries
- **Cached, fast search** over real-time polling
- **Semantic search** over exact matching
- **Human-readable reports** alongside machine-readable data

---

## Architectural Diagram

```mermaid
graph TB
    subgraph "Background Indexer (Cloud Composer)"
        A[Cloud Scheduler] -->|triggers @daily| B[metadata_collection_dag]
        B --> C[collect_metadata_task]
        C -->|2 threads| D[BigQueryCollector]
        D -->|discovers| E[BigQuery APIs]
        E -->|metadata| D
        
        C -->|XCom: assets| F[export_to_bigquery_task]
        F --> G[BigQueryWriter]
        G -->|writes with run_timestamp| H[(BigQuery: data_discovery.discovered_assets)]
        
        F -->|XCom: run_timestamp| I[export_markdown_reports_task]
        C -->|XCom: assets| I
        I --> J[MarkdownFormatter]
        J -->|writes reports| K[GCS: reports/{run_timestamp}/]
        
        F -->|XCom: run_timestamp| L[import_to_vertex_ai_task]
        L -->|triggers direct import| M[Vertex AI Search Client]
        M -->|imports from BigQuery| N[Vertex AI Search Datastore]
        H -->|source| N
    end
    
    subgraph "Query Interface (Future: MCP Service on GKE)"
        O[MCP Server] -->|semantic search| N
        N -->|results with metadata| O
        O -->|fetch markdown reports| K
        K -->|rich documentation| O
        O -->|structured responses| P[Claude Desktop / Clients]
    end
    
    subgraph "Local Testing (CLI)"
        Q[CLI: discovery run] -->|same logic as DAG| D
        Q -->|local testing| G
        Q -->|local testing| J
    end
    
    style B fill:#E1BEE7,stroke:#333
    style N fill:#C8E6C9,stroke:#333
    style O fill:#FFF9C4,stroke:#333
    style H fill:#BBDEFB,stroke:#333
```

---

## Component Breakdown

### 1. Background Indexer System (Cloud Composer)

**Purpose**: Scheduled, comprehensive metadata discovery and indexing

**Components**:

#### 1.1 Cloud Scheduler
- Triggers the metadata collection DAG on a schedule (`@daily`, configurable)
- Ensures regular updates to the metadata index
- No catchup to avoid duplicate processing

#### 1.2 Metadata Collection DAG (`dags/metadata_collection_dag.py`)
- Orchestrates the entire discovery and indexing pipeline
- Task flow:
  ```
  collect_metadata
      ↓
  export_to_bigquery
      ↓
  ┌────────────────────┬─────────────────────┐
  ↓                    ↓                     ↓
  export_markdown    import_to_vertex_ai    (parallel)
  ```
- Uses XCom for data passing between tasks
- All outputs share the same `run_timestamp` for correlation

#### 1.3 BigQuery Collector (`src/data_discovery_agent/collectors/bigquery_collector.py`)
- Discovers BigQuery metadata using multiple APIs:
  - `INFORMATION_SCHEMA` for schemas and statistics
  - Data Catalog API for tags and policy tags
  - Dataplex API for data profiling scans
  - DLP API for sensitive data findings
- **Threading**: Uses `ThreadPoolExecutor` with 2 workers for parallel discovery
- Outputs rich `BigQueryAssetSchema` objects

#### 1.4 BigQuery Writer (`src/data_discovery_agent/writers/bigquery_writer.py`)
- Writes discovered metadata to `data_discovery.discovered_assets` table
- Creates dataset and table if they don't exist
- Adds `run_timestamp` to all records for versioning
- Schema includes:
  - Asset identification (project, dataset, table)
  - Schema information (columns, types)
  - Statistics (row counts, size, last modified)
  - Security (policy tags, DLP findings)
  - Data quality (Dataplex scan results)

#### 1.5 Markdown Formatter (`src/data_discovery_agent/writers/markdown_formatter.py`)
- Generates human-readable markdown reports from metadata
- Organizes reports by: `{run_timestamp}/{project}/{dataset}/{table}.md`
- Uploads to GCS reports bucket
- Includes:
  - Table overview and description
  - Full schema with data types
  - Security and governance information
  - Data quality metrics
  - Usage statistics

#### 1.6 Vertex AI Search Client (`src/data_discovery_agent/clients/vertex_search_client.py`)
- Triggers direct BigQuery → Vertex AI Search import
- Uses the `import_documents` API with BigQuery source
- No intermediate JSONL files needed (direct import)
- Handles import job monitoring and error reporting

### 2. Query Interface (Future: MCP Service)

**Purpose**: Provide semantic search over discovered metadata

**Status**: Planned, not yet implemented

**Components**:

#### 2.1 MCP Server
- Model Context Protocol server deployed on GKE
- Exposes tools for semantic metadata search
- Key operations:
  - `query_data_assets`: Semantic search over Vertex AI Search
  - `get_table_details`: Fetch full markdown report from GCS
  - `list_datasets`: Browse available datasets
  - `get_data_lineage`: Query lineage information

#### 2.2 Vertex AI Search Integration
- Queries the `data-discovery-metadata` datastore
- Supports:
  - Semantic search over descriptions and metadata
  - Structured filtering (by project, dataset, tags, etc.)
  - Faceted results
  - Citation and source tracking

#### 2.3 GCS Report Fetcher
- Retrieves markdown reports from GCS for detailed views
- Uses `run_timestamp` to ensure consistency
- Provides rich, human-readable context

### 3. Local Testing CLI

**Purpose**: Test indexing logic locally without Cloud Composer

**Status**: Planned, not yet implemented

**Components**:

#### 3.1 CLI Entry Point (`src/data_discovery_agent/cli/main.py`)
- Click/Typer-based CLI
- Commands:
  - `discovery run`: Execute full discovery locally
  - `discovery export`: Export to BigQuery
  - `discovery markdown`: Generate markdown reports
  - `discovery import`: Import to Vertex AI Search
  - `discovery test`: Validate configuration

#### 3.2 Configuration
- Uses same environment variables as DAG
- Loads from `.env` file
- Same task functions as Cloud Composer

---

## Data Flow

### Discovery Pipeline

1. **Trigger**: Cloud Scheduler triggers the DAG daily
2. **Discovery**: `collect_metadata_task` discovers BigQuery metadata (2 concurrent threads)
3. **Export**: `export_to_bigquery_task` writes to BigQuery with `run_timestamp`
4. **Parallel Processing**:
   - **Path A**: `export_markdown_reports_task` generates reports → GCS
   - **Path B**: `import_to_vertex_ai_task` imports BigQuery → Vertex AI Search
5. **Indexing**: Vertex AI Search indexes the data for semantic search

### Query Pipeline (Future)

1. **Query**: User asks question via MCP client (e.g., Claude Desktop)
2. **Search**: MCP server queries Vertex AI Search for relevant assets
3. **Enrich**: MCP server fetches markdown reports from GCS for details
4. **Respond**: Structured response with citations and rich context

---

## Key Design Decisions

### 1. Direct BigQuery → Vertex AI Search Import

**Decision**: Skip intermediate JSONL file generation

**Rationale**:
- Vertex AI Search supports direct BigQuery import
- Reduces complexity (no GCS staging, no JSONL formatting)
- Faster pipeline (one less step)
- Easier to maintain (fewer moving parts)
- Native BigQuery schema mapping

**Trade-offs**:
- Less control over indexing format
- Relies on Vertex AI Search's BigQuery schema interpretation

### 2. Separate Markdown Reports

**Decision**: Generate human-readable markdown reports alongside BigQuery export

**Rationale**:
- Provides rich, formatted documentation for humans
- Enables code review and audit workflows
- MCP service can return detailed context beyond search results
- Organized by `run_timestamp` for historical tracking

### 3. Threading with Limited Concurrency

**Decision**: Use 2 threads for BigQuery discovery

**Rationale**:
- Balance between speed and API quota limits
- Composer worker has limited resources
- Prevents rate limiting errors
- Good enough for daily batch processing

**Configuration**: Adjustable via `max_workers` parameter

### 4. Cloud Composer for Orchestration

**Decision**: Use Cloud Composer (managed Airflow) instead of Cloud Functions, Cloud Run, or custom orchestration

**Rationale**:
- Built-in scheduling, retries, and monitoring
- Airflow's rich UI for debugging
- XCom for task data passing
- Environment variable management
- Scales to complex multi-task workflows

### 5. run_timestamp for Correlation

**Decision**: Use shared `run_timestamp` across all outputs

**Rationale**:
- Links BigQuery records with corresponding GCS reports
- Enables time-travel queries ("show me metadata as of X date")
- Supports incremental processing and change detection
- Audit trail for compliance

**Format**: `YYYYMMDD_HHMMSS` (e.g., `20251019_143052`)

### 6. Environment Variables for Configuration

**Decision**: Use environment variables (via `.env` and Composer config) instead of hardcoded values

**Rationale**:
- Security: No credentials in code
- Flexibility: Easy to change per environment
- Follows 12-factor app principles
- Composer natively supports environment variables

**See**: `.env.example` for all configuration options

---

## Security Architecture

### Service Accounts

#### 1. Composer Service Account (`data-discovery-composer`)
- **Purpose**: Run Composer environment and execute DAG tasks
- **Permissions**:
  - `composer.worker`: Manage Composer environment
  - `bigquery.dataViewer`: Query BigQuery tables
  - `bigquery.dataEditor`: Write to discovery dataset
  - `bigquery.jobUser`: Execute BigQuery jobs
  - `bigquery.metadataViewer`: Read table metadata
  - `datacatalog.viewer`: Read Data Catalog tags
  - `dataplex.viewer`: Read Dataplex metadata
  - `dataplex.dataScanAdmin`: Create data profiling scans
  - `dlp.reader`: Read DLP findings
  - `aiplatform.user`: Use Vertex AI services
  - `storage.objectAdmin`: Write to GCS buckets (scoped to specific buckets)
  - `logging.logWriter`: Write logs
  - `monitoring.metricWriter`: Write metrics

#### 2. Discovery Service Account (`data-discovery-agent`)
- **Purpose**: Future MCP service authentication
- **Permissions**:
  - `discoveryengine.viewer`: Query Vertex AI Search
  - `storage.objectViewer`: Read markdown reports from GCS

#### 3. Metadata Write Service Account (`data-discovery-metadata`)
- **Purpose**: Future metadata enrichment (if needed)
- **Permissions**: (Currently unused, reserved for future features)

**See**: `docs/ACLS.md` for full permission documentation

### Security Principles

1. **Least Privilege**: Each service account has minimal permissions
2. **Read-Only Discovery**: All discovery operations are read-only
3. **Scoped Storage Access**: Storage permissions limited to specific buckets
4. **No Source Data Access**: Only metadata, never actual table data
5. **Audit Logging**: All operations logged to Cloud Logging

---

## Scalability & Performance

### Current Scale
- **Data Source**: BigQuery (single project, expandable to multi-project)
- **Discovery Frequency**: Daily (configurable)
- **Concurrency**: 2 threads
- **Datastore Size**: ~18MB (50KB structured, 18MB unstructured)

### Scaling Strategies

#### Vertical Scaling
- Increase Composer worker size (more CPU/memory)
- Increase thread count for discovery (requires quota increases)
- Use larger node types for GKE (future MCP service)

#### Horizontal Scaling
- Partition by project (separate DAG runs per project)
- Parallel dataset processing (dynamic task generation)
- Multi-region Composer environments

#### Performance Optimization
- Incremental discovery (only changed tables)
- Caching of expensive API calls
- Batch API requests where possible
- Async/await for I/O-bound operations

---

## Monitoring & Observability

### Cloud Composer Monitoring
- Airflow UI: Task logs, execution history, DAG visualization
- Cloud Logging: Structured logs from all tasks
- Cloud Monitoring: DAG duration, success/failure rates

### Custom Metrics
- Number of tables discovered per run
- Discovery duration per table
- BigQuery export row counts
- Vertex AI Search import status
- Markdown report generation success rates

### Alerting
- DAG failure notifications
- API quota exhaustion warnings
- BigQuery export errors
- Vertex AI Search import failures

---

## Future Enhancements

### Phase 3: MCP Service Implementation
- Implement MCP server with Vertex AI Search integration
- Deploy to GKE cluster
- Create Docker image and Kubernetes manifests
- Build query tools for semantic search
- Integrate markdown report fetching

### Phase 4: Additional Data Sources
- Cloud Storage (bucket metadata, lifecycle policies)
- Cloud SQL (schema, query performance)
- Spanner (global distribution, schema evolution)
- Dataproc (cluster metadata, job history)

### Phase 5: Advanced Features
- Gemini-powered description generation
- Change detection and notifications
- Data lineage visualization
- Cost optimization recommendations
- Automated data quality rules
- Custom metadata enrichment workflows

### Phase 6: Testing & Documentation
- Comprehensive unit tests (pytest)
- Integration tests with real GCP resources
- Local CLI for development and testing
- API documentation
- User guides and tutorials

---

## Technology Stack

### Core Infrastructure
- **Cloud Composer 3**: Managed Airflow for orchestration
- **Vertex AI Search**: Semantic search over metadata
- **BigQuery**: Structured metadata storage
- **Cloud Storage**: Markdown report storage
- **GKE**: Future MCP service deployment

### Python Libraries
- `google-cloud-bigquery`: BigQuery client
- `google-cloud-datacatalog`: Data Catalog client
- `google-cloud-dataplex`: Dataplex client
- `google-cloud-dlp`: DLP client
- `google-cloud-discoveryengine`: Vertex AI Search client
- `google-cloud-storage`: GCS client
- `pydantic`: Data validation and schemas
- `python-dotenv`: Environment variable management

### Development Tools
- **Poetry/uv**: Dependency management
- **Ruff**: Code formatting and linting
- **pytest**: Testing framework
- **Terraform**: Infrastructure as code

---

## Configuration Management

All configuration is managed through environment variables:

### Required Variables
- `GCP_PROJECT_ID`: GCP project ID
- `GCS_JSONL_BUCKET`: JSONL staging bucket (legacy, unused)
- `GCS_REPORTS_BUCKET`: Markdown reports bucket
- `VERTEX_DATASTORE_ID`: Vertex AI Search datastore ID
- `VERTEX_LOCATION`: Vertex AI location (usually `global`)
- `BQ_DATASET`: BigQuery dataset for metadata
- `BQ_TABLE`: BigQuery table name
- `BQ_LOCATION`: BigQuery location

### Optional Variables
- `LOG_LEVEL`: Logging verbosity (default: `INFO`)
- `GOOGLE_API_KEY`: API key for Google services
- `GEMINI_API_KEY`: Gemini API key (future use)

**See**: `.env.example` for complete list and descriptions

---

## Development Workflow

1. **Local Development**:
   - Clone repository
   - Copy `.env.example` to `.env` and configure
   - Install dependencies: `uv sync`
   - Run tests: `pytest tests/`

2. **Testing**:
   - Unit tests: `pytest tests/unit/`
   - Integration tests: `pytest tests/integration/`
   - Local CLI testing: `discovery run` (future)

3. **Deployment**:
   - Infrastructure: `cd terraform && terraform apply`
   - DAG deployment: Upload `dags/` to Composer DAGs bucket
   - Code deployment: Package installed in Composer environment

4. **Monitoring**:
   - Check Airflow UI for task status
   - View logs in Cloud Logging
   - Query `data_discovery.discovered_assets` in BigQuery
   - Browse markdown reports in GCS

---

## Related Documentation

- **[ACLS.md](./ACLS.md)**: Complete IAM permissions and justifications
- **[../terraform/README.md](../terraform/README.md)**: Infrastructure setup guide
- **[../.env.example](../.env.example)**: Environment variable reference
- **[../README.md](../README.md)**: Project overview and quick start
- **[../.cursor/plans/bigquery-discovery-mcp-beb6d83e.plan.md](../.cursor/plans/bigquery-discovery-mcp-beb6d83e.plan.md)**: Detailed project plan
