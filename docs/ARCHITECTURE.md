# Data Discovery Agent Architecture

## Overview

The Data Discovery Agent is a metadata discovery and search system that discovers, catalogs, and makes BigQuery metadata searchable through Vertex AI Search. The system provides both scheduled background indexing (via Cloud Composer) and on-demand CLI-based collection, with an operational MCP server for AI assistant integration.

This architecture prioritizes:
- **Automated metadata enrichment** using Dataplex profiling and Gemini AI
- **Direct BigQuery import** to Vertex AI Search for simplicity
- **Semantic search** via MCP protocol for AI assistants
- **Human-readable reports** alongside machine-readable data
- **Flexible deployment** (CLI, Cloud Composer, or containerized MCP server)

---

## Architectural Diagram

```mermaid
graph TB
    subgraph "Metadata Collection (Orchestrated or CLI)"
        A[Cloud Scheduler / Manual CLI] -->|triggers| B[Collection Process]
        B --> C[BigQueryCollector]
        C -->|multi-threaded| D[BigQuery APIs]
        C -->|optional| E[Dataplex Profiler]
        C -->|optional| F[Gemini AI Describer]
        D -->|schemas & stats| C
        E -->|column profiles| C
        F -->|AI descriptions| C
        
        C -->|assets| G[Parallel Export]
        
        G --> H[BigQueryWriter]
        H -->|writes with run_timestamp| I[(BigQuery: data_discovery.discovered_assets)]
        
        G --> J[MarkdownFormatter]
        J -->|generates reports| K[GCS: reports/{run_timestamp}/]
        
        I -->|direct import| L[Vertex AI Search Client]
        L -->|indexes| M[Vertex AI Search Datastore]
    end
    
    subgraph "MCP Server (Operational)"
        N[AI Assistant: Cursor/Claude] -->|stdio/http| O[MCP Server]
        O -->|semantic search| M
        M -->|search results| O
        O -->|fetch reports| K
        K -->|rich documentation| O
        O -->|structured responses| N
    end
    
    style B fill:#E1BEE7,stroke:#333
    style M fill:#C8E6C9,stroke:#333
    style O fill:#81C784,stroke:#333
    style I fill:#BBDEFB,stroke:#333
    style E fill:#FFE082,stroke:#333
    style F fill:#FFE082,stroke:#333
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
  - Data Catalog API for lineage information
  - **Dataplex Profiler** (optional): Column-level profiling, distributions, null rates, sample values
  - **Gemini AI** (optional): Auto-generated table and column descriptions, analytical insights
- **Threading**: Uses `ThreadPoolExecutor` 
  - Default: `max_workers=2` in code
  - CLI: Auto-detects CPU cores for optimal performance
  - Configurable via `--workers` parameter
- **Label-based Filtering**: Respects BigQuery labels (default: `ignore-discovery-scan: true`)
  - Dataset-level labels filter all tables in that dataset
  - Table-level labels override dataset settings
  - Configurable via `--filter-label-key` parameter
- Outputs rich `BigQueryAssetSchema` objects with complete metadata

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

#### 1.5 Dataplex Profiler (`src/data_discovery_agent/collectors/dataplex_profiler.py`)
- Integrates with Dataplex Data Profile Scans
- Extracts rich column-level statistics:
  - Null rates and completeness
  - Min/max/avg values for numeric columns
  - Top values and distributions
  - Sample values for documentation
- Detects PII/PHI indicators in column data
- Optional feature (enable with `--use-dataplex`)

#### 1.6 Gemini Describer (`src/data_discovery_agent/collectors/gemini_describer.py`)
- Uses Gemini AI to generate metadata descriptions
- Generates:
  - Table-level descriptions based on schema and statistics
  - Column-level descriptions explaining purpose and content
  - Analytical insights and data quality observations
- Includes retry logic for rate limiting
- Optional feature (enable with `--use-gemini`)

#### 1.7 Markdown Formatter (`src/data_discovery_agent/search/markdown_formatter.py`)
- Generates comprehensive human-readable markdown reports
- Organizes reports by: `{run_timestamp}/{project}/{dataset}/{table}.md`
- Uploads to GCS reports bucket
- Includes:
  - Table overview with AI-generated description
  - Complete schema with nested fields
  - Sample values and column profiles
  - Data quality metrics from Dataplex
  - Lineage information (upstream/downstream)
  - Analytical insights from Gemini

#### 1.8 Vertex AI Search Client (`src/data_discovery_agent/clients/vertex_search_client.py`)
- Triggers direct BigQuery → Vertex AI Search import
- Uses the `import_documents_from_bigquery` API
- Direct import eliminates need for intermediate JSONL files
- Handles import job monitoring and error reporting
- Supports incremental reconciliation mode for updates

### 2. MCP Server (Operational)

**Purpose**: Provide semantic search over discovered metadata via Model Context Protocol for AI assistants

**Status**: Fully implemented and operational

**Components**:

#### 2.1 MCP Server Implementations

**Stdio Server** (`src/data_discovery_agent/mcp/server.py`)
- Primary transport for local AI assistant integration
- Used by Cursor, Claude Desktop, and other MCP clients
- Subprocess-based communication via stdin/stdout
- Zero network exposure for enhanced security
- Configured via `MCP_TRANSPORT=stdio`

**HTTP Server** (`src/data_discovery_agent/mcp/http_server.py`)
- FastAPI-based REST/SSE server for remote clients
- Used for containerized deployments (Docker, Kubernetes)
- Supports multiple concurrent clients
- JSON-RPC 2.0 protocol for tool invocation
- Configured via `MCP_TRANSPORT=http`

#### 2.2 MCP Tools

The server exposes 4 tools for metadata discovery:

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `query_data_assets` | Semantic search over tables | `query` (natural language), `project_id`, `dataset_id`, `has_pii`, `has_phi`, `min_row_count`, `max_row_count`, `page_size` |
| `get_asset_details` | Fetch full documentation for a table | `asset_id` or `project_id`+`dataset_id`+`table_id` |
| `list_datasets` | Browse all datasets in a project | `project_id`, `page_size` |
| `get_datasets_for_query_generation` | Get schemas for SQL query building | `project_id`, filters |

#### 2.3 MCP Handlers (`src/data_discovery_agent/mcp/handlers.py`)
- Request handling and business logic
- Integrates with Vertex AI Search for semantic search
- Fetches markdown reports from GCS
- Formats responses for AI assistant consumption
- Error handling and validation

#### 2.4 Vertex AI Search Integration
- Queries the `data-discovery-metadata` datastore
- Supports:
  - Natural language semantic search
  - Structured filtering (project, dataset, PII/PHI, row counts, etc.)
  - Pagination for large result sets
  - Result ranking by relevance

#### 2.5 GCS Report Fetcher
- Retrieves comprehensive markdown reports from GCS
- Provides rich, human-readable context beyond search results
- Used by `get_asset_details` tool for detailed table documentation

### 3. CLI Script

**Purpose**: On-demand metadata collection without Cloud Composer

**Status**: Fully implemented and operational

**Components**:

#### 3.1 Collection Script (`scripts/collect-bigquery-metadata.py`)
- Direct execution of metadata discovery workflow
- Features:
  - Multi-threaded collection (auto-detects CPU cores by default)
  - Dataplex profiling integration (`--use-dataplex`)
  - Gemini AI description generation (`--use-gemini`)
  - Label-based filtering (`--filter-label-key`)
  - Project and dataset filtering
  - Direct BigQuery export with lineage tracking
  - Markdown report generation
  - Automatic Vertex AI Search import
- Useful for:
  - Testing and development
  - One-time metadata collection
  - Manual metadata refresh

#### 3.2 Configuration
- Uses same environment variables as Cloud Composer tasks
- Loads from `.env` file via python-dotenv
- Shares code with orchestration tasks for consistency

---

## Data Flow

### Discovery Pipeline

The system supports two execution modes with identical data flow:

#### Cloud Composer Mode (Scheduled)
1. **Trigger**: Cloud Scheduler triggers the DAG daily (or custom schedule)
2. **Discovery**: `collect_metadata_task` collects BigQuery metadata
   - Multi-threaded collection (configurable workers)
   - Optional Dataplex profiling for column statistics
   - Optional Gemini AI for auto-generated descriptions
   - Respects label-based filtering rules
3. **Export**: `export_to_bigquery_task` writes to BigQuery with `run_timestamp`
4. **Parallel Processing**:
   - **Path A**: `export_markdown_reports_task` generates reports → GCS
   - **Path B**: `import_to_vertex_ai_task` triggers direct BigQuery → Vertex AI Search import
5. **Indexing**: Vertex AI Search indexes the data for semantic search (5-10 minutes)

#### CLI Mode (On-Demand)
1. **Trigger**: Manual execution via `scripts/collect-bigquery-metadata.py`
2. **Discovery**: BigQueryCollector with same enrichment options
3. **Export**: Direct BigQuery write with `run_timestamp`
4. **Parallel**: Markdown generation to GCS
5. **Import**: Automatic Vertex AI Search import trigger
6. **Indexing**: Same as Composer mode

**Key Point**: Both modes use the same collectors, writers, and formatters, ensuring consistency.

### Query Pipeline (Operational)

1. **Query**: User asks question via MCP client (Cursor, Claude Desktop)
2. **Transport**: MCP client connects via stdio (subprocess) or HTTP
3. **Tool Selection**: AI assistant selects appropriate MCP tool
4. **Search**: MCP server queries Vertex AI Search for relevant tables
5. **Enrich**: MCP server fetches markdown reports from GCS for detailed context
6. **Respond**: Structured response with metadata, descriptions, and citations

---

## Key Design Decisions

### 1. Direct BigQuery → Vertex AI Search Import

**Decision**: Use direct BigQuery import as the only import method (JSONL code removed)

**Rationale**:
- Vertex AI Search natively supports BigQuery as a source
- Eliminates intermediate JSONL file generation and GCS staging
- Simpler architecture with fewer failure points
- Faster pipeline execution (one less step)
- Easier to maintain and debug
- Native BigQuery schema mapping
- Incremental updates via reconciliation mode

**Implementation**:
- Both CLI and Cloud Composer use `import_documents_from_bigquery` API
- Consistent import process across all execution modes
- Single source of truth (BigQuery table)

### 2. Separate Markdown Reports

**Decision**: Generate human-readable markdown reports alongside BigQuery export

**Rationale**:
- Provides rich, formatted documentation for humans
- Enables code review and audit workflows
- MCP service can return detailed context beyond search results
- Organized by `run_timestamp` for historical tracking

### 3. Configurable Multi-Threading

**Decision**: Use ThreadPoolExecutor with configurable workers

**Rationale**:
- Significantly improves collection performance (~5-10x faster)
- Balances speed with API quota limits
- Adaptable to different environments and workloads
- Prevents overwhelming BigQuery APIs

**Implementation**:
- **Default**: `max_workers=2` (conservative, safe for Composer)
- **CLI**: Auto-detects CPU cores for optimal local performance
- **Configurable**: `--workers` parameter for custom tuning
- **Performance**: 5 workers = ~5x speedup, 10 workers = ~8-10x speedup

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

### 6. Dataplex Integration for Column Profiling

**Decision**: Optional integration with Dataplex Data Profile Scans

**Rationale**:
- Provides rich column-level statistics beyond basic INFORMATION_SCHEMA
- Detects PII/PHI indicators automatically
- Offers sample values for better understanding
- Enterprise-grade data quality metrics
- Reduces need for custom profiling code

**Trade-offs**:
- Adds API call overhead (slower collection)
- Requires Dataplex API enabled and configured
- Additional GCP costs for profiling scans

**Usage**: Enable with `--use-dataplex` flag

### 7. Gemini AI for Automated Descriptions

**Decision**: Optional integration with Gemini API for auto-generated descriptions

**Rationale**:
- Eliminates manual documentation burden
- Provides consistent, high-quality descriptions
- Generates insights based on schema and statistics
- Improves metadata discoverability
- Descriptions improve Vertex AI Search relevance

**Trade-offs**:
- API costs for Gemini calls
- Requires API key management
- Rate limiting considerations
- Generated content may require human review

**Usage**: Enable with `--use-gemini` flag

### 8. Label-Based Filtering

**Decision**: Respect BigQuery labels for opt-out filtering

**Rationale**:
- Allows data owners to control discovery inclusion
- Hierarchical filtering (dataset-level and table-level)
- No code changes needed to exclude tables
- Follows BigQuery native labeling system
- Supports compliance requirements (exclude sensitive datasets)

**Implementation**:
- Default label: `ignore-discovery-scan: true`
- Dataset label filters all tables in dataset
- Table label can override dataset setting
- Configurable via `--filter-label-key`

### 9. Model Context Protocol (MCP) for AI Assistants

**Decision**: Implement MCP server with dual transports (stdio and HTTP)

**Rationale**:
- **MCP Protocol**: Open standard for AI assistant integration
- **Wide Compatibility**: Works with Cursor, Claude Desktop, and future MCP clients
- **Stdio Transport**: Zero-config subprocess integration for local use
- **HTTP Transport**: Enables remote/containerized deployments
- **Tool-based API**: Natural interface for LLM tool calling
- **Rich Context**: Can return both structured data and markdown documentation

**Benefits**:
- AI assistants can discover and understand data estate
- Natural language queries over metadata
- Seamless integration with developer workflows
- Future-proof with open standard

### 10. Environment Variables for Configuration

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

### Additional Data Sources
- Cloud Storage (bucket metadata, lifecycle policies)
- Cloud SQL (schema, query performance)
- Spanner (global distribution, schema evolution)
- Dataproc (cluster metadata, job history)

### Advanced Features
- ✅ Gemini-powered description generation (implemented)
- ✅ Data lineage tracking (implemented)
- Change detection and notifications
- Data lineage visualization UI
- Cost optimization recommendations
- Automated data quality rules
- Custom metadata enrichment workflows
- Query recommendation engine
- Automated data classification
- Cross-project data discovery

---

## MCP Server Architecture

The MCP (Model Context Protocol) server is a fully operational component that enables AI assistants to discover and query BigQuery metadata through a standardized protocol.

### Architecture Overview

```
┌─────────────────────────────────────────────────┐
│          AI Assistant (Cursor/Claude)           │
└────────────────┬────────────────────────────────┘
                 │
                 │ stdio (subprocess) or HTTP
                 │
┌────────────────▼────────────────────────────────┐
│              MCP Server                         │
│  ┌──────────────────────────────────────────┐  │
│  │  server.py (stdio) / http_server.py      │  │
│  └──────────────┬───────────────────────────┘  │
│                 │                               │
│  ┌──────────────▼───────────────────────────┐  │
│  │          handlers.py                     │  │
│  │  - Query handling                        │  │
│  │  - Result formatting                     │  │
│  │  - Error handling                        │  │
│  └──────┬────────────────────┬──────────────┘  │
│         │                    │                  │
└─────────┼────────────────────┼──────────────────┘
          │                    │
          │                    │
  ┌───────▼─────────┐   ┌─────▼──────────────┐
  │ Vertex AI Search│   │   GCS (Reports)    │
  │   (Datastore)   │   │   Markdown Files   │
  └─────────────────┘   └────────────────────┘
```

### Transport Modes

#### Stdio Transport
- **Primary use case**: Local AI assistant integration
- **Protocol**: JSON-RPC 2.0 over stdin/stdout
- **Security**: Process isolation, no network exposure
- **Lifecycle**: Managed by parent process (Cursor/Claude)
- **Configuration**: `MCP_TRANSPORT=stdio`
- **Implementation**: `src/data_discovery_agent/mcp/server.py`

**Example Cursor Configuration**:
```json
{
  "mcpServers": {
    "data-discovery": {
      "command": "poetry",
      "args": ["run", "python", "-m", "data_discovery_agent.mcp"],
      "env": {
        "GCP_PROJECT_ID": "your-project",
        "VERTEX_DATASTORE_ID": "data-discovery-metadata",
        "MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```

#### HTTP Transport
- **Primary use case**: Remote/containerized deployments
- **Protocol**: FastAPI + JSON-RPC 2.0 + SSE
- **Security**: Network-based, supports authentication
- **Lifecycle**: Long-running server process
- **Configuration**: `MCP_TRANSPORT=http`
- **Implementation**: `src/data_discovery_agent/mcp/http_server.py`

**HTTP Endpoints**:
- `GET /health` - Health check
- `GET /` - Service info (JSON) or SSE stream
- `POST /jsonrpc` - JSON-RPC 2.0 endpoint
- `GET /mcp/tools` - List available tools (legacy REST)
- `POST /mcp/call-tool` - Execute tool (legacy REST)

### MCP Tools

| Tool Name | Purpose | Input Parameters | Output |
|-----------|---------|------------------|--------|
| `query_data_assets` | Search tables by natural language | `query`, `project_id`, `dataset_id`, `has_pii`, `has_phi`, `min_row_count`, `max_row_count`, `page_size`, `page_token` | List of matching tables with metadata snippets |
| `get_asset_details` | Get full documentation for a table | `asset_id` OR (`project_id`, `dataset_id`, `table_id`) | Complete markdown documentation with schema, statistics, lineage |
| `list_datasets` | Browse datasets in a project | `project_id`, `page_size`, `page_token` | List of datasets with summary info |
| `get_datasets_for_query_generation` | Get schemas for SQL generation | `project_id`, filters | Dataset/table schemas optimized for query generation |

### Tool Invocation Flow

1. **AI Assistant** selects tool based on user query
2. **MCP Client** sends JSON-RPC request with tool name and parameters
3. **MCP Server** validates parameters against tool schema
4. **Handler** executes business logic:
   - For `query_data_assets`: Query Vertex AI Search
   - For `get_asset_details`: Fetch markdown from GCS + search metadata
   - For `list_datasets`: Query BigQuery INFORMATION_SCHEMA
5. **Formatter** structures response for AI consumption
6. **MCP Server** returns JSON-RPC response
7. **AI Assistant** processes response and answers user

### Configuration

**Required Environment Variables**:
- `GCP_PROJECT_ID`: GCP project containing data
- `VERTEX_DATASTORE_ID`: Vertex AI Search datastore ID
- `VERTEX_LOCATION`: Vertex AI location (usually `global`)
- `GCS_REPORTS_BUCKET`: GCS bucket with markdown reports

**Optional Environment Variables**:
- `MCP_TRANSPORT`: `stdio` (default) or `http`
- `MCP_HOST`: HTTP host (default: `0.0.0.0`)
- `MCP_PORT`: HTTP port (default: `8080`)
- `MCP_DEFAULT_PAGE_SIZE`: Results per page (default: `10`)
- `MCP_MAX_PAGE_SIZE`: Maximum page size (default: `50`)
- `MCP_QUERY_TIMEOUT`: Query timeout in seconds (default: `30.0`)

### Error Handling

The MCP server implements comprehensive error handling:
- **Validation Errors**: Invalid parameters, missing required fields
- **Not Found Errors**: Asset doesn't exist, report not found
- **Timeout Errors**: Query exceeded timeout limit
- **API Errors**: Vertex AI Search or GCS API failures
- **Rate Limiting**: Graceful handling of quota exhaustion

All errors return structured JSON-RPC error responses with:
- Error code (standard JSON-RPC codes)
- Human-readable message
- Additional context when helpful

### Performance Considerations

- **Caching**: No caching implemented (stateless design)
- **Pagination**: Supports pagination for large result sets
- **Timeouts**: Configurable query timeouts prevent hanging
- **Connection pooling**: HTTP mode uses connection pooling for GCP APIs
- **Concurrency**: HTTP mode supports multiple concurrent requests

### Security

**Stdio Mode**:
- Process-level isolation
- Inherits parent process permissions
- No network exposure
- Credentials from environment or gcloud

**HTTP Mode**:
- Authentication: Currently relies on network security
- Authorization: Uses GCP IAM for API access
- Encryption: HTTPS recommended for production
- CORS: Configurable for web clients

---

## Technology Stack

### Core Infrastructure
- **Cloud Composer** (optional): Managed Airflow for scheduled orchestration
- **Vertex AI Search**: Semantic search over metadata
- **BigQuery**: Structured metadata storage
- **Cloud Storage**: Markdown report storage
- **Dataplex**: Column profiling and data quality scans
- **Data Catalog**: Lineage tracking (optional)

### AI/ML Services
- **Gemini API**: AI-generated descriptions and insights
- **Vertex AI Search**: Neural search and ranking

### MCP Server
- **MCP SDK** (`mcp`): Model Context Protocol implementation
- **FastAPI**: HTTP server for MCP
- **Uvicorn**: ASGI server for FastAPI

### Python Libraries
- `google-cloud-bigquery`: BigQuery client
- `google-cloud-datacatalog-lineage`: Lineage tracking
- `google-cloud-dataplex`: Dataplex client
- `google-cloud-discoveryengine`: Vertex AI Search client
- `google-cloud-storage`: GCS client
- `google-generativeai`: Gemini API client
- `pydantic`: Data validation and schemas
- `python-dotenv`: Environment variable management
- `fastapi`: HTTP server framework
- `mcp`: Model Context Protocol SDK

### Development Tools
- **Poetry**: Dependency management
- **Ruff**: Code formatting and linting
- **pytest**: Testing framework
- **Black**: Code formatter

---

## Configuration Management

All configuration is managed through environment variables:

### Required Variables
- `GCP_PROJECT_ID`: GCP project ID
- `GCS_REPORTS_BUCKET`: Markdown reports bucket
- `VERTEX_DATASTORE_ID`: Vertex AI Search datastore ID
- `VERTEX_LOCATION`: Vertex AI location (usually `global`)
- `BQ_DATASET`: BigQuery dataset for metadata export
- `BQ_TABLE`: BigQuery table name for metadata export
- `BQ_LOCATION`: BigQuery dataset location

### Optional Variables
- `GEMINI_API_KEY`: Gemini API key for AI-generated descriptions
- `LINEAGE_ENABLED`: Enable lineage tracking (default: `true`)
- `LINEAGE_LOCATION`: Lineage API region (default: `us-central1`)
- `MCP_TRANSPORT`: MCP transport mode (`stdio` or `http`, default: `stdio`)
- `MCP_HOST`: MCP HTTP server host (default: `0.0.0.0`)
- `MCP_PORT`: MCP HTTP server port (default: `8080`)
- `LOG_LEVEL`: Logging verbosity (default: `INFO`)

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
