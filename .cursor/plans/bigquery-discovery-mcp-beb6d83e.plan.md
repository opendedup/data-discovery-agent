<!-- beb6d83e-19f3-4fcf-8082-7f1f93ee34ad e06be243-1285-4f90-94c1-81f06f99a7e1 -->
# BigQuery Data Discovery System with MCP Interface

## Architecture Overview

A streamlined data discovery system with three main components:

1. **Background Indexers** - Seven specialized agents collect comprehensive BigQuery metadata on schedule
2. **Vertex AI Search** - Indexed metadata enables fast semantic search over the data estate
3. **MCP Service** - Container-based service exposing MCP tools that query Vertex AI Search and return markdown documentation

All discovery agents run as background indexers on Cloud Composer schedule, with local CLI available for testing. The MCP service runs in containers (local development) and GKE (production).

## Phase 0: Infrastructure Setup (Terraform)

**0.1 Core GCP Infrastructure**

- Create `terraform/` directory:
  - `main.tf`: Main Terraform configuration
  - `variables.tf`: Input variables (project_id, region, etc.)
  - `outputs.tf`: Output values (endpoints, service URLs)
  - `versions.tf`: Terraform and provider versions
  - `terraform.tfvars.example`: Example configuration

**0.2 Vertex AI Search & Storage**

- Create `terraform/`:
  - `vertex-ai-search/vertex-search.tf`: Vertex AI Search data store for metadata indexing
  - `storage.tf`: GCS buckets for JSONL ingestion and Markdown reports
  - BigQuery dataset `data_discovery` for storing discovered metadata (created by DAG)

**0.3 Service Accounts & IAM**

- ✅ **COMPLETED** - Create `terraform/service-accounts.tf`:
  - **Composer service account** (for orchestration):
    - BigQuery: metadataViewer, dataViewer, dataEditor, jobUser
    - Data Catalog: viewer
    - Vertex AI: user
    - Dataplex: viewer, dataScanAdmin
    - DLP: reader
    - Storage: bucket-specific objectAdmin (JSONL + Reports buckets)
  - **Discovery service account** (read-only for GKE workloads):
    - BigQuery metadataViewer and jobUser
    - Data Catalog viewer
    - Cloud Logging viewer
    - DLP reader
  - **MCP service account** (future - for MCP queries):
    - Vertex AI Search user
    - GCS object viewer (for markdown files)
  - **Metadata write service account** (Data Catalog only)
  - **GKE service account** (minimal node permissions)
  - Workload Identity bindings for GKE pods

**0.4 Cloud Composer**

- ✅ **COMPLETED** - Create `terraform/composer.tf`:
  - Cloud Composer 3 environment with Airflow 2.10.5
  - Environment variables configured (GCP_PROJECT_ID, buckets, Vertex AI datastore)
  - PyPI packages: google-cloud-*, pydantic, python-dotenv
  - Service account with all necessary permissions
  - Small environment size for cost-effectiveness
  - Depends on service account and IAM bindings

**0.5 GKE Cluster (for MCP Service)**

- ✅ **COMPLETED** - Create `terraform/main.tf`:
  - GKE Standard cluster for MCP service (currently used for other workloads)
  - Workload Identity enabled for secure service account impersonation
  - VPC-native cluster with custom networking
  - Will be repurposed for MCP service deployment in Phase 3

**0.6 Monitoring & Security**

- Create `terraform/monitoring.tf`:
  - Cloud Monitoring dashboards
  - Alert policies for indexer failures
- Create `terraform/secrets.tf`:
  - Secret Manager for sensitive config
- Network policies and security configuration

**0.7 Deployment Scripts**

- Create `scripts/`:
  - `setup-infrastructure.sh`: Terraform init, plan, apply wrapper
  - `validate-setup.sh`: Health checks and validation
  - `teardown.sh`: Clean infrastructure destruction

## Phase 1: Core Infrastructure & Application Foundation

**1.1 Abstract Base Layer**

- Create `src/data_discovery_agent/core/` directory:
  - `data_source.py`: Abstract base class for all data sources (BigQuery, future GCS, Cloud SQL)
  - `metadata.py`: Base Pydantic models (schema, security, lineage, quality, cost, governance)
  - `registry.py`: Data source registry/plugin system
  - `discovery_interface.py`: Abstract interfaces for discovery operations

**1.2 GCP Client Integration**

- Add GCP libraries to `pyproject.toml`:
  - `google-cloud-bigquery`, `google-cloud-datacatalog`, `google-cloud-dlp`
  - `google-cloud-logging`, `google-cloud-monitoring`, `google-cloud-storage`
  - `google-cloud-aiplatform` (for Vertex AI Search)
- Create `src/data_discovery_agent/clients/`:
  - `base_client.py`: Shared authentication (ADC) and configuration
  - `bigquery_client.py`: BigQuery wrapper with read-only methods
  - `datacatalog_client.py`: Data Catalog wrapper (read + metadata writes)
  - `logging_client.py`: Audit log wrapper
  - `vertex_search_client.py`: Vertex AI Search API wrapper

**1.3 Vertex AI Search Infrastructure**

- Create `src/data_discovery_agent/search/`:
  - `search_datastore.py`: Manages Vertex AI Search data store lifecycle
  - `jsonl_schema.py`: Defines JSONL schema for asset indexing
  - `metadata_formatter.py`: Transforms agent outputs to JSONL
  - `markdown_formatter.py`: Generates human-readable Markdown documentation
  - `query_builder.py`: Builds Vertex AI Search queries with semantic search + filters
  - `result_parser.py`: Parses search results and extracts markdown references

**1.4 JSONL Schema Design**

```python
# Schema for BigQuery assets in Vertex AI Search
{
  "id": "project.dataset.table",
  "structData": {  # Filterable structured fields
    "project_id": str,
    "dataset_id": str,
    "table_id": str,
    "data_source": "bigquery",
    "asset_type": "TABLE|VIEW|MATERIALIZED_VIEW",
    "has_pii": bool,
    "row_count": int,
    "size_bytes": int,
    "last_modified_timestamp": ISO8601,
    "monthly_cost_usd": float,
    "indexed_at": ISO8601,
    "run_timestamp": ISO8601,  # When discovery job ran
  },
  "content": {  # Semantically searchable text
    "mimeType": "text/plain",
    "uri": "gs://bucket/markdown/project.dataset.table.md",  # Link to full markdown
    "text": "Rich description including: table name, description, column details, governance info, lineage, cost context"
  }
}
```

**1.5 Data Models**

- Create `src/data_discovery_agent/models/`:
  - `base_models.py`: Common metadata models (abstract)
  - `bigquery_models.py`: BigQuery-specific models
  - `search_models.py`: Models for Vertex AI Search requests/responses
  - Future: `gcs_models.py`, `cloudsql_models.py`

**1.6 Configuration Management**

- Create `config/` directory with YAML configuration:
  - `discovery_config.yaml`: Schedule, agent settings, data sources
  - `search_config.yaml`: Vertex AI Search data store settings
  - `mcp_config.yaml`: MCP service configuration
  - `alerts_config.yaml`: Alert thresholds and channels
- Use `pydantic-settings` for config validation

## Phase 2: Background Discovery Indexers

All agents run as background indexers on schedule and output formatted metadata for Vertex AI Search.

Create agents under `src/data_discovery_agent/agents/bigquery/indexers/`:

**2.1 Schema Indexer Agent** (`schema_indexer/`)

- Discovers: schemas, columns, types, partitioning, clustering, views, materialized views, UDFs
- Tools: `get_table_schema` (via INFORMATION_SCHEMA), `get_view_definition`, `list_routines`
- Output: Structured schema data → Metadata Formatter → JSONL + Markdown
- Uses `INFORMATION_SCHEMA` views for efficiency

**2.2 Data Quality Indexer Agent** (`data_quality_indexer/`)

- Discovers: row counts, null percentages, distributions, freshness, completeness
- Tools: `get_table_stats`, `analyze_column_distribution` (aggregated only)
- Output: Quality metrics → Metadata Formatter → JSONL + Markdown
- Integrates with Dataplex Data Quality when available

**2.3 Security Indexer Agent** (`security_indexer/`)

- Discovers: IAM policies, RLS policies, CLS policy tags, encryption, authorized views
- Tools: `get_iam_policy`, `list_row_access_policies`, `get_policy_tags`
- Output: Security metadata → Metadata Formatter → JSONL + Markdown

**2.4 Lineage Indexer Agent** (`lineage_indexer/`)

- Discovers: table dependencies, view lineage, job lineage
- Tools: `get_dataplex_lineage` (primary), `query_audit_logs_for_lineage` (fallback)
- Output: Lineage graph data → Metadata Formatter → JSONL + Markdown
- Uses Dataplex Data Lineage API as primary source

**2.5 Cost Indexer Agent** (`cost_indexer/`)

- Discovers: storage costs, historical query costs, expensive tables, slot usage patterns
- Tools: `get_storage_cost`, `analyze_query_costs`, `get_slot_usage`
- Output: Cost analysis → Metadata Formatter → JSONL + Markdown

**2.6 Governance Indexer Agent** (`governance_indexer/`)

- Discovers: labels, tags, retention policies, expirations, DLP findings, compliance status
- Tools: `get_labels`, `get_retention_policies`, `get_dlp_findings`
- Output: Governance metadata → Metadata Formatter → JSONL + Markdown

**2.7 Glossary Indexer Agent** (`glossary_indexer/`)

- Discovers: table/column descriptions, Data Catalog entries
- Uses LLM: Generate missing documentation, suggest business terms
- Tools: `get_table_description`, `get_datacatalog_entries`, `generate_glossary_terms`
- Output: Enriched descriptions → Metadata Formatter → JSONL + Markdown

**2.8 Indexer Orchestrator & Data Aggregator**

- ✅ **COMPLETED** - Create `src/data_discovery_agent/orchestration/`:
  - `tasks.py`: Airflow task functions for DAG execution
    - `collect_metadata_task()`: Runs BigQueryCollector with 2 threads
    - `export_to_bigquery_task()`: Writes to BigQuery, pushes run_timestamp to XCom
    - `export_markdown_reports_task()`: Generates and uploads Markdown to GCS
    - `import_to_vertex_ai_task()`: Triggers Vertex AI Search import from BigQuery
  - **Dual Output Generation**:
    - **Path 1 (Structured)**: BigQueryCollector → BigQueryWriter → `data_discovery.discovered_assets` → Vertex AI Search
    - **Path 2 (Human-readable)**: BigQueryCollector → MarkdownFormatter → GCS reports bucket
  - All outputs use same `run_timestamp` for correlation
  - Environment variable driven configuration

**2.9 Markdown Report Generation**

- Create `src/data_discovery_agent/writers/`:
  - `markdown_writer.py`: Generates comprehensive Markdown reports from aggregated data
  - `report_templates.py`: Jinja2 templates for different report types (schema summary, security audit, cost analysis, etc.)
  - Templates organized by: asset type, discovery domain, data source
  - Output: Rich Markdown documentation stored in GCS for MCP service retrieval

**2.10 Cloud Composer Orchestration**

- ✅ **COMPLETED** - Create `dags/metadata_collection_dag.py`:
  - Airflow DAG for metadata collection and indexing
  - **Task Flow**:
    1. `collect_metadata` → Discovers BigQuery metadata (2 concurrent threads)
    2. `export_to_bigquery` → Writes to `data_discovery.discovered_assets` table
    3. `export_markdown_reports` → Generates Markdown reports in GCS (parallel with Vertex import)
    4. `import_to_vertex_ai` → Imports from BigQuery to Vertex AI Search (parallel with markdown)
  - Schedule: `@daily` with no catchup
  - Uses environment variables from Composer config
  - All tasks use XCom for data passing
  - **run_timestamp** tracking for correlation between BigQuery and GCS reports

**2.11 Local CLI for Testing**

- ⏳ **TODO** - Create `src/data_discovery_agent/cli/`:
  - `main.py`: CLI entry point using Click or Typer
  - Commands:
    - `discovery run`: Run collector locally with same logic as DAG
    - `discovery run --max-tables 10`: Limit for testing
    - `discovery validate`: Validate setup and credentials
    - `discovery export --bigquery`: Write to BigQuery
    - `discovery export --markdown`: Generate markdown reports
    - `discovery ingest`: Trigger Vertex AI Search import
  - Uses same task functions as Composer DAG
  - Useful for local testing before deploying to Composer

## Phase 3: MCP Service Implementation

**Status**: ⏳ **TODO** - MCP service for querying indexed metadata

**Architecture**: Container-based MCP server queries Vertex AI Search and returns Markdown documentation

**3.1 MCP Service Foundation**

- ⏳ Create `src/data_discovery_agent/mcp/`:
  - `server.py`: MCP server implementation using `mcp` library
  - `tools.py`: MCP tool definitions
  - `handlers.py`: Request handlers for MCP tools
  - `config.py`: MCP-specific configuration
  - Uses existing `VertexSearchClient` and `MarkdownFormatter`

**3.2 MCP Tool: query_data_assets**

- Tool definition:
  - Name: `query_data_assets`
  - Input: `query` (string) - natural language question about data assets
  - Optional filters: `project_id`, `dataset_id`, `asset_type`, etc.
  - Output: List of markdown file contents relevant to the query

- Implementation in `handlers.py`:

  1. Parse user query
  2. Build Vertex AI Search query using `query_builder.py`
  3. Execute search via `vertex_search_client.py`
  4. Parse results using `result_parser.py`
  5. Fetch markdown files from GCS based on search results
  6. Return markdown content to MCP client

**3.3 Container Setup**

- Create `Dockerfile`:
  - Base image: Python 3.11+
  - Install dependencies from `pyproject.toml`
  - Copy MCP service code
  - Expose MCP port
  - Entry point: `python -m data_discovery_agent.mcp.server`

- Create `docker-compose.yml`:
  - Service definition for local development
  - Volume mounts for code changes
  - Environment variable configuration

**3.4 Kubernetes Deployment**

- Create `k8s/`:
  - `deployment.yaml`: MCP service deployment
  - `service.yaml`: Service exposure (ClusterIP or LoadBalancer)
  - `configmap.yaml`: Configuration
  - `secret.yaml`: Secrets (reference Secret Manager)
  - `hpa.yaml`: Horizontal Pod Autoscaler (optional)

**3.5 MCP Service Testing**

- Create `tests/mcp/`:
  - `test_server.py`: Test MCP server initialization
  - `test_tools.py`: Test tool definitions and responses
  - `test_handlers.py`: Test query handling and markdown retrieval
  - `test_integration.py`: End-to-end MCP client tests

## Phase 4: Output & Reporting

**4.1 Report Generators** (`src/data_discovery_agent/writers/`)

- `base_writer.py`: Abstract writer interface
- `markdown_writer.py`: Generate markdown reports (already in Phase 2.9)
- `json_writer.py`: Structured JSON output (for programmatic access)
- `datacatalog_writer.py`: Write enriched metadata back to Data Catalog (with approval)

**4.2 Export & Metadata Write-Back**

- Export to: GCS, Data Catalog
- **Metadata writes only** (no source data writes per security requirements)
- Approval workflow for metadata updates:
  - Preview changes
  - Show before/after state
  - Require explicit confirmation
  - Audit all writes

**4.3 Templates**

- Create `src/data_discovery_agent/writers/templates/`:
  - JSONL templates for different asset types
  - Markdown templates for various report types
  - Organized by data source type

## Phase 5: Testing & Examples

**5.1 Integration Tests** (`tests/integration/`)

- Test Vertex AI Search data store creation and querying
- Test background indexer agents against mocked BigQuery
- Test MCP service end-to-end (query → search → markdown retrieval)
- Test metadata formatter JSONL output
- End-to-end tests (indexing → search → MCP response)

**5.2 Unit Tests** (`tests/unit/`)

- Mock GCP clients for unit tests
- Test core abstractions and registry
- Test JSONL schema validation
- Test markdown formatting
- Test approval workflows

**5.3 Example Scripts**

- Update `example_usage.py`:
  - Example 1: Run background indexing job locally
  - Example 2: Query Vertex AI Search programmatically
  - Example 3: Test MCP service with sample queries
  - Example 4: Write enriched metadata to Data Catalog

- Create `examples/`:
  - `setup_vertex_search.py`: Initialize Vertex AI Search data store
  - `run_indexer_local.py`: Run discovery indexers manually
  - `query_examples.py`: Various query patterns
  - `mcp_client_example.py`: Example MCP client usage

## Phase 6: Proactive Monitoring & Anomaly Detection

**6.1 Metrics Collection & Storage**

- Create `src/data_discovery_agent/storage/`:
  - `timeseries_store.py`: Store historical metrics in BigQuery
  - `baseline_manager.py`: Establish and update baselines
- Metrics: row counts, null percentages, query costs, table sizes
- Integrated with background indexers

**6.2 Anomaly Detection Indexer** (`agents/bigquery/indexers/anomaly_indexer/`)

- Background process: Runs with other indexers, compares current state to baselines
- Detects: data quality drift, cost anomalies, security anomalies
- Tools: `establish_baseline`, `detect_statistical_drift`, `analyze_access_deviations`
- Output: Anomaly findings → Indexed in Vertex AI Search + real-time alerts

**6.3 Alerting**

- Create `src/data_discovery_agent/monitoring/`:
  - `alert_manager.py`: Send alerts via email, Slack, PubSub
  - Integration with Cloud Monitoring
  - Severity-based routing

## Phase 7: Automated Remediation & Action Engine

**7.1 Action Framework**

- Create `src/data_discovery_agent/actions/`:
  - `action_base.py`: Abstract base class for actions
  - `action_executor.py`: Execute with approval workflows
  - `approval_manager.py`: Manage approvals (CLI, webhook, UI)
  - `risk_assessor.py`: Assess risk levels

**7.2 Metadata Remediation Actions**

- Create `src/data_discovery_agent/actions/remediations/`:
  - `governance_actions.py`: Apply labels, update descriptions (Data Catalog only)
  - `security_actions.py`: Suggest IAM policy changes (no automatic writes)
  - `cost_actions.py`: Generate partitioning/clustering DDL (for review, not execution)
  - `quality_actions.py`: Suggest data quality rules

**7.3 Critical Constraint (Security)**

- **NO SOURCE DATA WRITES**: Actions can only:

  1. Write to Data Catalog (descriptions, tags, business metadata)
  2. Apply resource labels/tags
  3. Generate recommendations (DDL, policy changes) for manual review

- **NEVER**: Execute DDL, modify schemas, change IAM policies automatically
- All actions require: preview, detailed explanation, explicit approval

## Phase 8: Enhanced FinOps & Cost Intelligence

**8.1 Advanced Cost Attribution**

- Enhance Cost Indexer with:
  - `cost_attribution.py`: Attribute costs to teams via labels
  - `chargeback_reporter.py`: Generate chargeback reports
  - `budget_tracker.py`: Track against budgets

**8.2 Cost Analysis via MCP**

- Add additional MCP tool (optional):
  - `analyze_costs`: Specialized cost queries and analysis
  - Returns cost breakdowns, trends, recommendations

## Phase 9: Cross-Platform Lineage & Impact Analysis

**9.1 Extended Lineage Collection**

- Dataplex Data Lineage API as primary source (background indexer)
- Audit log parsing as fallback
- Create `src/data_discovery_agent/lineage/`:
  - `dataplex_lineage.py`: Primary collection
  - `audit_lineage.py`: Supplementary
  - `lineage_graph.py`: Build graph (NetworkX)

**9.2 External Tool Integration**

- Create `src/data_discovery_agent/integrations/`:
  - `dataflow_integration.py`: Dataflow job lineage
  - `composer_integration.py`: Airflow/Composer DAG lineage
  - `openlineage_adapter.py`: OpenLineage standard support
- Future: dbt, Tableau, Power BI

**9.3 Impact Analysis**

- Query "What breaks if I change column X?" returns:
  - Lineage graph from Vertex AI Search
  - Blast radius report in markdown

## Phase 10: Native GCP Feature Integration

**10.1 Dataplex Integration**

- Use Dataplex Data Lineage (primary lineage source)
- Integrate Dataplex Data Quality (automated checks)
- Leverage Dataplex Data Profiling (enhanced statistics)

**10.2 Authentication & Security**

- Use Application Default Credentials (ADC) in `base_client.py`
- Implement least-privilege service accounts:
  - Read-only account for discovery/indexing
  - Separate metadata-write account (Data Catalog only)
  - MCP service account (Vertex AI Search + GCS read)
- Document required IAM roles

**10.3 INFORMATION_SCHEMA Optimization**

- Use `INFORMATION_SCHEMA` views in Schema Indexer
- `INFORMATION_SCHEMA.TABLE_OPTIONS` for partition/cluster info
- `INFORMATION_SCHEMA.COLUMN_FIELD_PATHS` for nested schemas

## Phase 11: Future Extensibility

**11.1 GCS Bucket Discovery**

- Implement `GCSDataSource` extending `DataSource`
- Create GCS indexer agents
- Add GCS JSONL schema for Vertex AI Search
- MCP service queries both BigQuery and GCS metadata

**11.2 Cloud SQL Discovery**

- Implement `CloudSQLDataSource` extending `DataSource`
- Similar pattern: indexers, JSONL schema, markdown output

**11.3 Multi-Source Search**

- Single Vertex AI Search data store indexes multiple source types
- Use `structData.data_source` filter for source-specific queries
- MCP service transparently queries all indexed sources

## Key Files to Create/Modify

**New Core Files:**

- `src/data_discovery_agent/core/data_source.py`
- `src/data_discovery_agent/core/metadata.py`
- `src/data_discovery_agent/core/registry.py`
- `src/data_discovery_agent/core/discovery_interface.py`

**New Vertex AI Search Files:**

- `src/data_discovery_agent/search/search_datastore.py`
- `src/data_discovery_agent/search/jsonl_schema.py`
- `src/data_discovery_agent/search/metadata_formatter.py`
- `src/data_discovery_agent/search/markdown_formatter.py`
- `src/data_discovery_agent/search/query_builder.py`
- `src/data_discovery_agent/search/result_parser.py`

**New Client Files:**

- `src/data_discovery_agent/clients/base_client.py`
- `src/data_discovery_agent/clients/bigquery_client.py`
- `src/data_discovery_agent/clients/datacatalog_client.py`
- `src/data_discovery_agent/clients/logging_client.py`
- `src/data_discovery_agent/clients/vertex_search_client.py`

**New Indexer Agent Files:**

- `src/data_discovery_agent/agents/bigquery/indexers/schema_indexer/agent.py`
- `src/data_discovery_agent/agents/bigquery/indexers/data_quality_indexer/agent.py`
- `src/data_discovery_agent/agents/bigquery/indexers/security_indexer/agent.py`
- `src/data_discovery_agent/agents/bigquery/indexers/lineage_indexer/agent.py`
- `src/data_discovery_agent/agents/bigquery/indexers/cost_indexer/agent.py`
- `src/data_discovery_agent/agents/bigquery/indexers/governance_indexer/agent.py`
- `src/data_discovery_agent/agents/bigquery/indexers/glossary_indexer/agent.py`
- `src/data_discovery_agent/orchestration/orchestrator.py`
- `src/data_discovery_agent/orchestration/data_aggregator.py`

**New MCP Service Files:**

- `src/data_discovery_agent/mcp/server.py`
- `src/data_discovery_agent/mcp/tools.py`
- `src/data_discovery_agent/mcp/handlers.py`
- `src/data_discovery_agent/mcp/config.py`

**New CLI Files:**

- `src/data_discovery_agent/cli/main.py`

**New Writer Files:**

- `src/data_discovery_agent/writers/markdown_writer.py`
- `src/data_discovery_agent/writers/base_writer.py`
- `src/data_discovery_agent/writers/json_writer.py`
- `src/data_discovery_agent/writers/datacatalog_writer.py`

**Deployment Files:**

- `Dockerfile`
- `docker-compose.yml`
- `k8s/deployment.yaml`
- `k8s/service.yaml`
- `k8s/configmap.yaml`
- `k8s/secret.yaml`

**Orchestration Files:**

- `dags/metadata_collection_dag.py`

**Configuration Files:**

- `config/discovery_config.yaml`
- `config/search_config.yaml`
- `config/mcp_config.yaml`
- `config/alerts_config.yaml`

**Modified Files:**

- `pyproject.toml`: Add GCP dependencies + MCP library
- `.env.example`: Add GCP configuration, Vertex AI Search settings, MCP settings
- `example_usage.py`: Update with architecture examples
- `README.md`: Update with architecture, setup guide, usage

## Security Requirements

**Critical Constraints:**

- **READ-ONLY SOURCE ACCESS**: All indexer agents have read-only access to BigQuery
- **METADATA WRITES ONLY**: Actions can only write to Data Catalog, labels, tags (never source data)
- **NO DDL/DML OPERATIONS**: Never execute DDL/DML on source systems
- **ADC AUTHENTICATION**: Use Application Default Credentials throughout
- **LEAST PRIVILEGE**: Service accounts have minimum required permissions
- **AUDIT LOGGING**: All operations logged to Cloud Logging
- **SECRET MANAGEMENT**: Sensitive config in Secret Manager, never in code
- **INPUT VALIDATION**: MCP service validates all user inputs

## Implementation Strategy

1. **Phase 0-1**: Infrastructure and foundation (Terraform, core abstractions, GCP clients, Vertex AI Search setup)
2. **Phase 2**: Background indexers (start with Schema Indexer, then add others, orchestration, CLI)
3. **Phase 3**: MCP service (server, tools, container, K8s deployment)
4. **Phase 4-5**: Reporting and testing (writers, examples, comprehensive tests)
5. **Phases 6-11**: Advanced features (anomaly detection, actions, cost intelligence, lineage, extensibility)

## Query Flow Example

**User Query**: "Find all tables with PII data in the finance dataset"

1. MCP client sends query to MCP service via `query_data_assets` tool
2. MCP service parses query and builds Vertex AI Search query: `search(query="tables with PII", filter="dataset_id='finance'")`
3. Vertex AI Search returns matching results with markdown URIs
4. MCP service fetches markdown files from GCS
5. MCP service returns markdown content to client
6. Client displays comprehensive documentation for matching tables

This architecture provides fast semantic search over comprehensive metadata with rich markdown documentation for end users.

### To-dos

#### Phase 0: Infrastructure ✅ COMPLETE
- [x] Set up Terraform infrastructure: GCP resources, GCS buckets, service accounts
- [x] Configure Cloud Composer 3 with environment variables and permissions
- [x] Create service accounts with least-privilege permissions
- [x] Document all ACLs and IAM roles in docs/ACLS.md
- [x] Create Vertex AI Search data store (`data-discovery-metadata`, created Oct 18, has ~18MB data)
- [x] GKE cluster exists (repurpose for MCP service)

#### Phase 1-2: Background Indexers ✅ COMPLETE
- [x] Build BigQueryCollector with threading (2 concurrent threads)
- [x] Implement metadata collection with Dataplex profiling support
- [x] Create BigQueryWriter for structured data export
- [x] Implement MarkdownFormatter for human-readable reports
- [x] Build VertexSearchClient for Vertex AI Search operations
- [x] Create Airflow DAG with 4 tasks (collect → export_bq + export_md → import_vertex)
- [x] Implement run_timestamp tracking for correlation
- [x] Configure environment variables in Composer
- [ ] Build local CLI for testing (uses same task functions)
- [ ] Add Gemini description generation (optional enhancement)
- [ ] Add more specialized indexers (security, lineage, cost - future)

#### Phase 3: MCP Service ✅ COMPLETE
- [x] Implement MCP server using existing VertexSearchClient
- [x] Create query_data_assets tool for semantic search
- [x] Create get_asset_details tool for specific assets
- [x] Create list_datasets tool for dataset browsing
- [x] Build handlers that fetch markdown from GCS
- [x] Create Dockerfile for MCP service
- [x] Create docker-compose.yml for local development
- [x] Create Kubernetes manifests for GKE deployment
- [x] Create comprehensive documentation and examples
- [x] Add MCP configuration to .env.example
- [ ] Deploy MCP service to GKE cluster (ready for deployment)
- [ ] Test MCP service end-to-end with real data

#### Phase 4-5: Testing & Documentation 📝 ONGOING
- [x] Document architecture in docs/ARCHITECTURE.md
- [x] Document ACLs in docs/ACLS.md
- [x] Document MCP service in docs/MCP_SERVICE.md
- [x] Create example scripts for MCP client usage
- [ ] Build comprehensive tests: unit tests, integration tests
- [ ] Update README.md with setup and usage guides (partial)