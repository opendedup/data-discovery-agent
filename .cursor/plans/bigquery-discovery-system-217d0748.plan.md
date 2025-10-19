<!-- 217d0748-0518-499c-9621-66ec0e6823c4 8c57e32c-8f3e-4e61-9de4-7f514cc93fcc -->
# BigQuery Data Estate Discovery System (Dual-Mode Architecture)

## Architecture Overview

Build a dual-mode discovery system that combines high-speed cached queries with real-time status checks:

**Path 1: Cached Discovery (Vertex AI Search)** - Serves 90% of queries instantly from pre-indexed metadata

**Path 2: Live Discovery (Real-time Agents)** - Provides up-to-the-second data for volatile information

Discovery agents run as **background indexers** on a schedule, feeding enriched metadata into Vertex AI Search. A **Smart Query Router** determines whether to use cached data, live queries, or both. This architecture is extensible to support future data sources (GCS, Cloud SQL, etc.).

## Phase 0: Infrastructure Setup (Terraform)

**0.1 GKE Cluster Provisioning**

- Create `terraform/` directory:
  - `main.tf`: Main Terraform configuration
  - `variables.tf`: Input variables (project_id, region, cluster_name, etc.)
  - `outputs.tf`: Output values (cluster endpoint, service URLs)
  - `versions.tf`: Terraform and provider versions
  - `terraform.tfvars.example`: Example configuration
- GKE cluster configuration:
  - Autopilot or Standard mode (recommend Autopilot for simplicity)
  - Workload Identity enabled
  - VPC-native cluster
  - Private cluster option for security
  - Node pools with appropriate machine types

**0.2 GenAI Toolbox Deployment**

- Create `terraform/genai-toolbox/`:
  - `genai-toolbox.tf`: GenAI Toolbox deployment on GKE
  - `kubernetes-manifests.tf`: K8s resources (Deployment, Service, ConfigMap, Secret)
  - Configure GenAI Toolbox tools:
    - BigQuery tools (`bigquery-get-table-info`, `bigquery-execute-sql`)
    - Dataplex tools (lineage, data quality)
    - Cloud SQL, AlloyDB tools (for future extensibility)
- Service exposure:
  - Internal LoadBalancer or ClusterIP + Ingress
  - MCP protocol endpoint configuration
  - Health check endpoints

**0.3 Supporting Infrastructure**

- Create `terraform/infrastructure/`:
  - `vertex-ai-search.tf`: Vertex AI Search data store
  - `gcs-buckets.tf`: GCS buckets for JSONL ingestion and Markdown reports
  - `service-accounts.tf`: Service accounts with least-privilege IAM roles:
    - Discovery service account (read-only)
    - Metadata write service account (Data Catalog only)
    - GenAI Toolbox service account
  - `secrets.tf`: Secret Manager for sensitive config
  - `composer.tf`: Cloud Composer environment for Airflow-based orchestration
  - `monitoring.tf`: Cloud Monitoring dashboards and alerts
  - `vpc.tf`: VPC and networking (if using private cluster)

**0.4 Security Configuration**

- Workload Identity binding (GKE → GCP service accounts)
- IAM role assignments per SR-2 requirements:
  - BigQuery metadataViewer and jobUser
  - Data Catalog viewer and entryGroupOwner
  - Cloud Logging viewer
  - DLP reader
- Network policies for GKE cluster
- Secret rotation configuration

**0.5 GenAI Toolbox Configuration**

- Create `config/genai-toolbox/`:
  - `toolbox-config.yaml`: GenAI Toolbox configuration
  - Data source connections (BigQuery, Dataplex)
  - Tool enablement and security settings
  - Connection pooling and timeout settings
  - Read-only mode enforcement (SR-2A validation)

**0.6 Deployment Scripts**

- Create `scripts/`:
  - `setup-infrastructure.sh`: Terraform init, plan, apply wrapper
  - `deploy-genai-toolbox.sh`: Deploy GenAI Toolbox to GKE
  - `validate-setup.sh`: Health checks and validation
  - `teardown.sh`: Clean infrastructure destruction

## Phase 1: Core Infrastructure & Application Foundation

**1.1 Abstract Base Layer**

- Create `src/data_discovery_agent/core/` directory:
  - `data_source.py`: Abstract base class `DataSource` for all data sources
  - `metadata.py`: Base Pydantic models (schema, security, lineage, quality, cost, governance)
  - `registry.py`: Data source registry/plugin system
  - `discovery_interface.py`: Abstract interfaces for discovery operations
  - `query_mode.py`: Enum and logic for routing (CACHED, LIVE, HYBRID)
- Enables future addition of GCS, Cloud SQL, Spanner

**1.2 GCP Client Integration**

- Add GCP libraries to `pyproject.toml`: 
  - `google-cloud-bigquery`, `google-cloud-datacatalog`, `google-cloud-dlp`
  - `google-cloud-logging`, `google-cloud-monitoring`, `google-cloud-storage`
  - `google-cloud-aiplatform` (for Vertex AI Search)
  - **`genai-toolbox`** (Google's pre-built GenAI tools for data sources)
- Create `src/data_discovery_agent/clients/`:
  - `base_client.py`: Shared authentication (ADC) and configuration
  - `bigquery_client.py`: BigQuery wrapper with read-only + lightweight live query methods
  - `datacatalog_client.py`: Data Catalog wrapper (read + metadata writes)
  - `logging_client.py`: Audit log wrapper
  - `vertex_search_client.py`: Vertex AI Search API wrapper
  - `genai_toolbox_client.py`: GenAI Toolbox integration wrapper

**1.2a GenAI Toolbox Integration Strategy**

- **Hybrid Approach**: Use GenAI Toolbox where appropriate, custom tools for specialized discovery
- **GenAI Toolbox Usage**:
  - Live agents: `bigquery-get-table-info`, `bigquery-execute-sql` (for real-time queries)
  - Dataplex integration: Pre-built Dataplex tools for lineage and quality
  - Future data sources: Cloud SQL, AlloyDB, Spanner tools
- **Custom Tools for**:
  - Specialized metadata discovery (IAM policies, DLP findings, cost analysis)
  - Background indexing (comprehensive, scheduled scans)
  - Security-sensitive operations (validate read-only compliance with SR-2A)
- **Security Validation**: Audit all GenAI Toolbox tools to ensure read-only compliance

**1.3 Vertex AI Search Infrastructure**

- Create `src/data_discovery_agent/search/`:
  - `search_datastore.py`: Manages Vertex AI Search data store lifecycle
  - `jsonl_schema.py`: Defines JSONL schema for asset indexing (structData + content)
  - `metadata_formatter.py`: **Critical component** - transforms agent outputs to JSONL and Markdown
  - `markdown_formatter.py`: Generates human-readable Markdown documentation from agent outputs
  - `query_builder.py`: Builds Vertex AI Search queries with semantic search + filters
  - `result_parser.py`: Parses and presents search results with citations

**1.4 JSONL Schema Design**

```python
# Example schema for BigQuery assets
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
    "cache_ttl": str,  # e.g., "24h"
    "volatility": "low|medium|high"
  },
  "content": {  # Semantically searchable text
    "mimeType": "text/plain",
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
  - `alerts_config.yaml`: Alert thresholds and channels
  - `actions_config.yaml`: Approval workflows for metadata writes
- Use `pydantic-settings` for config validation

## Phase 2: Background Discovery Indexers (BigQuery Agents)

All agents become **background indexers** that run on schedule and output formatted metadata for Vertex AI Search.

Create agents under `src/data_discovery_agent/agents/bigquery/indexers/`:

**2.1 Schema Indexer Agent** (`schema_indexer/`)

- Discovers: schemas, columns, types, partitioning, clustering, views, materialized views, UDFs
- Tools: `get_table_schema` (via INFORMATION_SCHEMA), `get_view_definition`, `list_routines`
- Output: Structured schema data → Metadata Formatter → JSONL
- Uses `INFORMATION_SCHEMA` views for efficiency

**2.2 Data Quality Indexer Agent** (`data_quality_indexer/`)

- Discovers: row counts, null percentages, distributions, freshness, completeness
- Tools: `get_table_stats`, `analyze_column_distribution` (aggregated only)
- Output: Quality metrics → Metadata Formatter → JSONL
- Integrates with Dataplex Data Quality when available

**2.3 Security Indexer Agent** (`security_indexer/`)

- Discovers: IAM policies (stable parts), RLS policies, CLS policy tags, encryption, authorized views
- Tools: `get_iam_policy`, `list_row_access_policies`, `get_policy_tags`
- Output: Security metadata → Metadata Formatter → JSONL
- Note: Real-time permission checks use live agents

**2.4 Lineage Indexer Agent** (`lineage_indexer/`)

- Discovers: table dependencies, view lineage, job lineage
- Tools: `get_dataplex_lineage` (primary), `query_audit_logs_for_lineage` (fallback)
- Output: Lineage graph data → Metadata Formatter → JSONL
- Uses Dataplex Data Lineage API as primary source (24hr delay acceptable for cache)

**2.5 Cost Indexer Agent** (`cost_indexer/`)

- Discovers: storage costs, historical query costs, expensive tables, slot usage patterns
- Tools: `get_storage_cost`, `analyze_query_costs`, `get_slot_usage`
- Output: Cost analysis → Metadata Formatter → JSONL

**2.6 Governance Indexer Agent** (`governance_indexer/`)

- Discovers: labels, tags, retention policies, expirations, DLP findings, compliance status
- Tools: `get_labels`, `get_retention_policies`, `get_dlp_findings`
- Output: Governance metadata → Metadata Formatter → JSONL

**2.7 Glossary Indexer Agent** (`glossary_indexer/`)

- Discovers: table/column descriptions, Data Catalog entries
- Uses LLM: Generate missing documentation, suggest business terms
- Tools: `get_table_description`, `get_datacatalog_entries`, `generate_glossary_terms`
- Output: Enriched descriptions → Metadata Formatter → JSONL

**2.8 Indexer Orchestrator & Data Aggregator**

- Create `src/data_discovery_agent/indexer/`:
  - `orchestrator.py`: Runs all indexer agents sequentially or in parallel
  - `data_aggregator.py`: Collects and consolidates outputs from all agents
  - **Dual Output Generation** (parallel):
    - **Path 1 (Machine)**: Data Aggregator → Metadata Formatter → JSONL files → GCS bucket (for Vertex AI Search ingestion)
    - **Path 2 (Human)**: Data Aggregator → Markdown Formatter → Markdown reports → GCS bucket (for human access)
  - Triggers Vertex AI Search ingestion from JSONL bucket
  - Tracks indexing job status and errors
  - Both outputs generated from same discovery run (efficiency)

**2.9 Background Report Generation**

- Create `src/data_discovery_agent/reports/background/`:
  - `markdown_generator.py`: Generates comprehensive Markdown reports from aggregated data
  - `report_templates.py`: Templates for different report types (schema summary, security audit, cost analysis, etc.)
  - Templates organized by: asset type, discovery domain, data source
  - Output: Rich Markdown documentation stored in GCS for stakeholder access

**2.9 Scheduling**

- Create `dags/` directory for Airflow DAGs.
- Create `dags/metadata_collection_dag.py`:
  - Define an Airflow DAG to orchestrate the discovery and indexing process.
  - Use the `PythonOperator` to execute each step of the collection process.
  - The DAG will manage dependencies between tasks (e.g., collection must finish before formatting and exporting).
- The schedule will be defined in the DAG (e.g., `schedule_interval="@daily"`).
- Remove `src/data_discovery_agent/scheduler/` in favor of Airflow's built-in scheduling.

## Phase 3: Live Query Agents & Smart Router

**3.1 Live Agent Framework**

- Create `src/data_discovery_agent/agents/bigquery/live/`:
  - `base_live_agent.py`: Lightweight base class for real-time queries
  - Each live agent has 2-5 focused tools (not comprehensive)

**3.2 Live Agent Implementations**

- `live_security_agent.py`: Real-time IAM checks (`test_iam_permissions`, `get_current_policy`)
- `live_schema_agent.py`: Current row counts, latest modification times
- `live_cost_agent.py`: Active query jobs, current slot usage
- `live_quality_agent.py`: Real-time freshness checks, streaming buffer status

**3.3 Smart Query Router (Orchestrator)**

- Create `src/data_discovery_agent/agents/coordinator/smart_router.py`:
  - **Main user-facing entry point**
  - Accepts: natural language query, data source type, optional filters
  - **Query Classification**: Uses LLM to classify query intent:
    - CACHED: Stable metadata (schemas, descriptions, historical costs, lineage)
    - LIVE: Volatile status (current permissions, real-time row counts, active jobs)
    - HYBRID: Combination (e.g., "find expensive tables and check current job status")
  - **Route Execution**:
    - CACHED → Vertex AI Search query
    - LIVE → Instantiate appropriate live agent
    - HYBRID → Decompose, execute both, synthesize results
  - **Response Synthesis**: LLM combines results into coherent answer with citations

**3.4 Router Decision Logic**

```python
# Heuristics for routing decisions
CACHED_KEYWORDS = ["find", "list", "describe", "what tables", "history", "lineage", "cost over time"]
LIVE_KEYWORDS = ["current", "right now", "can I access", "latest", "real-time", "active"]
HYBRID_KEYWORDS = ["check current", "verify and show", "latest status of"]

# Example routing
"Find tables with PII" → CACHED (Vertex AI Search)
"Can user X access table Y right now?" → LIVE (LiveSecurityAgent)
"Show expensive tables and check their current job status" → HYBRID
```

## Phase 4: Output & Reporting

**4.1 Report Generators** (`src/data_discovery_agent/reports/`)

- `base_reporter.py`: Abstract reporter interface
- `markdown_reporter.py`: Generate markdown reports from search results or live data
- `json_reporter.py`: Structured JSON output
- `html_reporter.py`: Interactive HTML dashboards (optional)
- `datacatalog_writer.py`: Write enriched metadata back to Data Catalog (with approval)

**4.2 Export & Metadata Write-Back**

- Export to: local files, GCS, Data Catalog
- **Metadata writes only** (SR-2A: no source data writes)
- Approval workflow for metadata updates:
  - Preview changes
  - Show before/after state
  - Require explicit confirmation
  - Audit all writes

**4.3 Templates**

- Create `src/data_discovery_agent/reports/templates/`:
  - JSONL templates for different asset types
  - Report templates for various use cases
  - Organized by data source type

## Phase 5: Testing & Examples

**5.1 Integration Tests** (`tests/integration/`)

- Test Vertex AI Search data store creation and querying
- Test background indexer agents against mocked BigQuery
- Test live agents with real-time queries
- Test smart router decision logic
- Test metadata formatter JSONL output
- End-to-end tests (indexing → search → response)

**5.2 Unit Tests** (`tests/unit/`)

- Mock GCP clients for unit tests
- Test core abstractions and registry
- Test query routing logic
- Test JSONL schema validation
- Test approval workflows

**5.3 Example Scripts**

- Update `example_usage.py`:
  - Example 1: Run background indexing job
  - Example 2: Query cached metadata (Vertex AI Search)
  - Example 3: Real-time permission check (live agent)
  - Example 4: Hybrid query (cached + live)
  - Example 5: Write enriched metadata to Data Catalog
- Create `examples/`:
  - `setup_vertex_search.py`: Initialize Vertex AI Search data store
  - `run_indexer.py`: Run discovery indexers manually
  - `query_examples.py`: Various query patterns
  - `extensibility_example.py`: Add new data source

## Phase 6: Proactive Monitoring & Anomaly Detection

**6.1 Metrics Collection & Storage**

- Create `src/data_discovery_agent/storage/`:
  - `timeseries_store.py`: Store historical metrics in BigQuery or Cloud Monitoring
  - `baseline_manager.py`: Establish and update baselines
- Metrics: row counts, null percentages, query costs, access patterns, table sizes
- Integrated with background indexers

**6.2 Anomaly Detection Indexer** (`agents/bigquery/indexers/anomaly_indexer/`)

- **Background Process**: Runs with other indexers, compares current state to baselines
- Detects: data quality drift, cost anomalies, security anomalies
- Tools: `establish_baseline`, `detect_statistical_drift`, `analyze_access_deviations`
- Output: Anomaly findings → Indexed in Vertex AI Search + real-time alerts

**6.3 Live Anomaly Agent**

- For real-time anomaly verification when alerts triggered
- Checks current state to confirm anomaly

**6.4 Alerting**

- Create `src/data_discovery_agent/scheduler/alert_manager.py`:
  - Send alerts via email, Slack, PubSub
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
  - `security_actions.py`: **Suggest** IAM policy changes (no automatic writes)
  - `cost_actions.py`: **Generate** partitioning/clustering DDL (for review, not execution)
  - `quality_actions.py`: Suggest data quality rules

**7.3 Critical Constraint (SR-2A)**

- **NO SOURCE DATA WRITES**: Actions can only:

  1. Write to Data Catalog (descriptions, tags, business metadata)
  2. Apply resource labels/tags
  3. Generate recommendations (DDL, policy changes) for manual review

- **NEVER**: Execute DDL, modify schemas, change IAM policies automatically
- All actions require: preview, detailed explanation, explicit approval

## Phase 8: Enhanced FinOps & Cost Intelligence

**8.1 Advanced Cost Attribution** (indexed)

- Enhance Cost Indexer with:
  - `cost_attribution.py`: Attribute costs to teams via labels
  - `chargeback_reporter.py`: Generate chargeback reports
  - `budget_tracker.py`: Track against budgets

**8.2 Cost Simulation & What-If Analysis** (live)

- Create `src/data_discovery_agent/simulation/`:
  - `partition_simulator.py`: Estimate partition cost savings
  - `clustering_simulator.py`: Simulate clustering impact
  - `storage_tier_simulator.py`: Calculate long-term storage savings
  - `slot_optimizer.py`: Recommend slot allocation
- Live agent performs simulations on-demand based on cached cost data

**8.3 Integration with Router**

- Queries like "What's the cost impact of partitioning table X?" → HYBRID:
  - Get historical cost data from Vertex AI Search
  - Run simulation via live agent
  - Synthesize results

## Phase 9: Cross-Platform Lineage & Impact Analysis

**9.1 Extended Lineage Collection** (indexed)

- Dataplex Data Lineage API as primary source (background indexer)
- Audit log parsing as fallback
- Create `src/data_discovery_agent/lineage/`:
  - `dataplex_lineage.py`: Primary collection
  - `audit_lineage.py`: Supplementary
  - `lineage_graph.py`: Build graph (NetworkX)

**9.2 External Tool Integration** (indexed)

- Create `src/data_discovery_agent/integrations/`:
  - `dataflow_integration.py`: Dataflow job lineage
  - `composer_integration.py`: Airflow/Composer DAG lineage
  - `openlineage_adapter.py`: OpenLineage standard support
- Future: dbt, Tableau, Power BI (Looker integration disabled)

**9.3 Impact Analysis** (hybrid)

- Queries like "What breaks if I change column X?" → HYBRID:
  - Get lineage graph from Vertex AI Search
  - Verify current dependencies via live agent
  - Generate blast radius report

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
- Document required IAM roles

**10.3 INFORMATION_SCHEMA Optimization**

- Use `INFORMATION_SCHEMA` views in Schema Indexer
- `INFORMATION_SCHEMA.TABLE_OPTIONS` for partition/cluster info
- `INFORMATION_SCHEMA.COLUMN_FIELD_PATHS` for nested schemas

## Phase 11: Future Extensibility & Additional Data Sources

**11.1 GCS Bucket Discovery**

- Implement `GCSDataSource` extending `DataSource`
- Create GCS indexer agents and live agents
- Add GCS JSONL schema for Vertex AI Search
- Semantic search over GCS objects

**11.2 Cloud SQL Discovery**

- Implement `CloudSQLDataSource` extending `DataSource`
- Similar pattern: indexers, live agents, JSONL schema

**11.3 Multi-Source Search**

- Single Vertex AI Search data store can index multiple source types
- Use `structData.data_source` filter for source-specific queries

## Phase 12: Optional Web UI

**12.1 Streamlit Dashboard** (`ui/`)

- Discovery job launcher and status
- Natural language query interface (calls Smart Router)
- Interactive reports and visualizations
- Anomaly alert dashboard
- Metadata write approval interface
- Deploy as Cloud Run service

## Key Files to Create/Modify

**New Core Files:**

- `src/data_discovery_agent/core/data_source.py`
- `src/data_discovery_agent/core/metadata.py`
- `src/data_discovery_agent/core/registry.py`
- `src/data_discovery_agent/core/discovery_interface.py`
- `src/data_discovery_agent/core/query_mode.py`

**New Vertex AI Search Files:**

- `src/data_discovery_agent/search/search_datastore.py`
- `src/data_discovery_agent/search/jsonl_schema.py`
- `src/data_discovery_agent/search/metadata_formatter.py` ⭐ **Critical**
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
- `src/data_discovery_agent/indexer/orchestrator.py`

**New Live Agent Files:**

- `src/data_discovery_agent/agents/bigquery/live/base_live_agent.py`
- `src/data_discovery_agent/agents/bigquery/live/live_security_agent.py`
- `src/data_discovery_agent/agents/bigquery/live/live_schema_agent.py`
- `src/data_discovery_agent/agents/bigquery/live/live_cost_agent.py`

**New Smart Router:**

- `src/data_discovery_agent/agents/coordinator/smart_router.py` ⭐ **Main entry point**

**Modified Files:**

- `pyproject.toml`: Add GCP dependencies including `google-cloud-aiplatform`
- `env_template.txt`: Add GCP configuration, Vertex AI Search settings
- `example_usage.py`: Update with dual-mode architecture examples
- `README.md`: Update with architecture, dual-mode explanation, usage

**Configuration Files:**

- `config/discovery_config.yaml`
- `config/search_config.yaml`
- `config/alerts_config.yaml`
- `config/actions_config.yaml`

## Security Requirements

[All security requirements from SR-1 through SR-11 remain the same]

**SR-2A: Source Data Write Protection (CRITICAL)** - emphasized throughout implementation:

- Indexer agents: read-only
- Live agents: read-only
- Action engine: metadata writes only (Data Catalog, labels)
- **NO DDL/DML operations** on source systems

## Implementation Strategy

1. **Phase 1**: Build Vertex AI Search foundation and core infrastructure

   - **Security Focus**: SR-1, SR-2, SR-2A, SR-5 (ADC, IAM, no data writes, secrets)
   - Set up Vertex AI Search data store
   - Implement Metadata Formatter (critical for JSONL generation)
   - Establish abstract base layer

2. **Phase 2**: Implement background indexer agents

   - **Security Focus**: SR-3, SR-4 (data handling, audit logging)
   - Start with Schema Indexer as template
   - Each agent outputs to Metadata Formatter → JSONL → GCS → Vertex AI Search
   - Set up scheduling (Cloud Scheduler)

3. **Phase 3**: Build Smart Query Router and live agents

   - **Security Focus**: SR-7, SR-8 (input validation, access control)
   - Implement query classification logic
   - Create lightweight live agents for real-time queries
   - Test dual-mode routing

4. **Phase 4**: Add reporting and metadata write-back

   - **Security Focus**: SR-2A enforcement (metadata writes only)
   - Approval workflows for any writes
   - Data Catalog integration

5. **Phase 5**: Testing and examples

   - **Security Focus**: SR-11 (security testing)
   - End-to-end tests of dual-mode architecture
   - Performance benchmarks

6. **Phases 6-12**: Advanced features

   - **Security Focus**: SR-9, SR-10, SR-11 (anomaly detection, deployment, monitoring)
   - Each phase builds on dual-mode foundation
   - Anomaly detection integrates with both paths
   - Cost simulation uses hybrid approach

## Dual-Mode Query Flow Examples

**Example 1: "Find all tables with PII data in finance dataset"**

1. Smart Router classifies: CACHED
2. Vertex AI Search: `search(query="tables with PII", filter="dataset_id='finance'")`
3. Returns results in milliseconds with citations
4. Router synthesizes response

**Example 2: "Can user john@company.com access transactions_2024 right now?"**

1. Smart Router classifies: LIVE
2. Instantiate LiveSecurityAgent
3. Call `test_iam_permissions('transactions_2024', 'john@company.com')`
4. Return real-time yes/no with current policy

**Example 3: "Show me the most expensive tables and check their current query jobs"**

1. Smart Router classifies: HYBRID
2. Step 1 (CACHED): Query Vertex AI Search for cost analysis
3. Step 2 (LIVE): For top expensive tables, call LiveCostAgent to check active jobs
4. Router synthesizes combined report

This architecture provides the best of both worlds: speed of cached search and accuracy of real-time checks.

### To-dos

- [ ] Set up Vertex AI Search data store infrastructure and JSONL schema design
- [ ] Build critical Metadata Formatter to transform agent outputs into optimized JSONL for Vertex AI Search
- [ ] Implement core abstractions (DataSource, metadata models, registry, query_mode enum)
- [ ] Add all GCP client libraries including google-cloud-aiplatform to pyproject.toml
- [ ] Build base authentication (ADC) and GCP client wrappers including Vertex AI Search client
- [ ] Build Schema Indexer Agent as first background indexer template using INFORMATION_SCHEMA
- [ ] Build remaining indexer agents (Quality, Security, Lineage, Cost, Governance, Glossary)
- [ ] Create orchestrator to run all indexers and upload JSONL to GCS for Vertex AI Search ingestion
- [ ] Implement Cloud Scheduler integration for periodic background indexing
- [ ] Build lightweight live agents for real-time queries (Security, Schema, Cost)
- [ ] Build Smart Query Router with classification logic for CACHED/LIVE/HYBRID routing
- [ ] Create Vertex AI Search query builder and result parser
- [ ] Integrate Smart Router with Vertex AI Search for cached path
- [ ] Build report generators and Data Catalog writer with approval workflows
- [ ] Implement YAML-based configuration management for all components
- [ ] Create comprehensive tests for dual-mode architecture, indexers, and live agents
- [ ] Build examples demonstrating indexing, cached queries, live queries, and hybrid queries
- [ ] Add anomaly detection as background indexer with real-time alerting
- [ ] Build action engine with metadata-only writes and approval workflows (SR-2A compliance)
- [ ] Add cost simulation and what-if analysis using hybrid approach
- [ ] Integrate Dataplex lineage and external tool integrations
- [ ] Update README with dual-mode architecture explanation, setup guide, and usage examples