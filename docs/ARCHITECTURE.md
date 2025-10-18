### Finalized: The Dual-Mode Discovery Architecture

This architecture creates a sophisticated, multi-agent data discovery system that is both powerful and practical. It solves the critical trade-off between data freshness, query performance, and operational cost by intelligently routing requests along two distinct paths: a high-speed, cached path powered by Vertex AI Search, and a real-time path using live agents.

This design provides two primary interfaces to the data estate's metadata:
1.  **The Library (Vertex AI Search):** A comprehensive, managed, and semantically searchable knowledge base. It contains a rich snapshot of the data estate's metadata, optimized for fast, analytical, and complex queries.
2.  **The Field Agent (Live Agents):** On-demand specialists dispatched to get immediate, up-to-the-second answers for highly volatile or mission-critical questions.

---

### Final Architectural Diagram

```mermaid
graph TD
    subgraph "User Interaction"
        A[User] -->|Natural Language Query| B{Orchestrator Agent (Smart Query Router)};
    end

    subgraph "Path 1: Cached Discovery (The Library)"
        B --"Is query about stable/historical data?"--> C{Vertex AI Search API};
        C -->|"search('customer PII', filter='data_source=bigquery')"| D[Managed Vertex AI Search Data Store];
        D --"Grounded, relevant results with citations"--> C;
        C -->|Fast, Comprehensive Answer| B;
    end

    subgraph "Path 2: Live Discovery (The Field Agent)"
        B --"Is query about volatile/real-time data?"--> F{Live Agent};
        F -->|GenAI Toolbox Tools + Custom Tools| G[GCP Client Wrappers];
        G -->|Direct API Call| H[Live GCP APIs];
        H --"Current State"--> G;
        G --> F;
        F -->|Up-to-the-minute Answer| B;
    end

    subgraph "Background Process: The Indexer & Reporter"
        I[Cloud Scheduler] --triggers nightly/hourly--> J(Core Discovery Agents);
        J -->|Rich, Structured Results| K{Data Aggregator};
        
        subgraph "Output for the Machine (The Library's Content)"
            K --> L(Metadata Formatter);
            L -->|Generates JSONL| M[Cloud Storage Bucket (for ingestion)];
            M --triggers ingestion--> D;
        end

        subgraph "Output for Humans (Reports)"
             K --> N(Report Generator);
             N -->|Generates Markdown| O[Cloud Storage Bucket (for reports)];
        end
    end

    style J fill:#D1C4E9,stroke:#333
    style I fill:#E0E0E0,stroke:#333
    style B fill:#FFF9C4,stroke:#333
    style D fill:#C8E6C9,stroke:#333
```

---

### Component Breakdown & Data Flow

#### 1. The "Indexer & Reporter" Subsystem (Background Process)

This offline process is responsible for populating both the machine-readable library and human-readable reports.

*   **Trigger & Execution:** A `Cloud Scheduler` job periodically runs the full suite of **Core Discovery Agents** (Schema, Cost, Lineage, Security, Governance, Glossary, Data Quality, etc.) to perform a comprehensive scan of the data estate.
*   **Agent Specialization:** Each indexer agent focuses on a specific domain:
    *   **Schema Indexer:** Uses `INFORMATION_SCHEMA` for efficient schema discovery
    *   **Lineage Indexer:** Prioritizes Dataplex Data Lineage API with audit log fallback
    *   **Security Indexer:** Discovers IAM policies, row/column-level security, policy tags
    *   **Cost Indexer:** Analyzes historical costs, storage patterns, slot usage
    *   **Governance Indexer:** Collects labels, tags, retention policies, DLP findings
    *   **Glossary Indexer:** Uses LLM to generate rich descriptions and business terms
    *   **Data Quality Indexer:** Integrates with Dataplex Data Quality for automated checks
*   **Aggregation:** The results from all agents are collected by a **Data Aggregator**, which consolidates and normalizes the metadata.
*   **Dual Output Generation (Parallel):**
    1.  **For the Machine (Vertex AI Search):** The aggregated data is passed to the **Metadata Formatter**. This component transforms discovery results into **JSONL files** with two key parts:
        *   `structData`: Filterable structured fields (project_id, has_pii, cost, timestamps, etc.)
        *   `content`: Rich, semantically searchable text descriptions
        These files are saved to a GCS bucket dedicated to ingestion.
    2.  **For Humans (Reports):** The same aggregated data is simultaneously passed to the **Markdown Report Generator**. This component uses templates to create comprehensive **Markdown documentation** organized by asset type and discovery domain. These reports are saved to a separate GCS bucket for stakeholder access, code review, and audit purposes.
*   **Ingestion:** The **Vertex AI Search Data Store** is configured to automatically watch the JSONL bucket and ingest new files, managing the entire pipeline of chunking, embedding, and indexing as a fully managed service.
*   **Efficiency:** Both outputs are generated in a single discovery run, ensuring consistency and minimizing API calls to source systems.

#### 2. The "Orchestrator" Agent (The Smart Query Router)

This is the central brain of the system and the primary user interface.

*   **Logic:** It uses an LLM to analyze the intent behind a user's query and determines the optimal strategy:
    *   **Route to Cache (Vertex AI Search):** For questions about stable, historical, or summary information (e.g., schemas, lineage, cost trends, governance policies). This is the default path for most queries.
    *   **Route to Live Agent:** For questions demanding real-time accuracy about volatile state (e.g., "does this user have access *right now*?", "what is the exact row count at this moment?").
    *   **Decompose for Hybrid:** For complex queries, it breaks the request down, queries both the cache and live agents, and synthesizes the results into a single, cohesive answer.

#### 3. The "Live Agent" Subsystem (The Field Agent)

These are lightweight, specialized agents designed for targeted, on-demand tasks.

*   **Scope:** They are not for discovery. They are equipped with a minimal set of tools that make fast, direct GCP API calls.
*   **Purpose:** To provide guaranteed-fresh data for a specific resource when the cache is not sufficient.
*   **Hybrid Tooling Approach:**
    *   **GenAI Toolbox Integration:** Live agents leverage Google's pre-built GenAI Toolbox tools where appropriate:
        *   `bigquery-get-table-info`: Quick table metadata retrieval
        *   `bigquery-execute-sql`: Real-time analytical queries
        *   Dataplex tools: Live lineage and quality checks
    *   **Custom Tools:** For specialized operations:
        *   Real-time IAM permission checks (`test_iam_permissions`)
        *   Security-sensitive metadata queries
        *   Cost and performance metrics requiring custom logic
        *   Operations requiring read-only validation (SR-2A compliance)
*   **Security:** All tools (GenAI Toolbox and custom) are audited to ensure read-only compliance with no source data modifications.

---

### Example Walkthroughs

*   **Query 1 (Cached): "Give me an overview of all tables tagged with PII."**
    1.  **Orchestrator:** Decides this is stable data, perfect for the cache. Routes to **Vertex AI Search**.
    2.  **Execution:** Calls the Search API: `search(query="tables with PII", filter="has_pii = true")`.
    3.  **Result:** Instantly gets a list of relevant assets and their descriptions from the managed index, which is then formatted for the user.

*   **Query 2 (Live): "What is the status of the `daily_load_job`?"**
    1.  **Orchestrator:** Decides job status is highly volatile. Routes to a **Live Agent**.
    2.  **Execution:** A `LiveStatusAgent` is dispatched, which uses a `get_bigquery_job_status` tool to make a real-time API call.
    3.  **Result:** Returns the current status (e.g., "RUNNING", "DONE").

*   **Query 3 (Hybrid): "Summarize the lineage for the `quarterly_sales` table and confirm its last update time."**
    1.  **Orchestrator:** Decides this is a hybrid query.
    2.  **Step 1 (Cached):** Queries Vertex AI Search for the `quarterly_sales` table to retrieve its detailed lineage description from the `content` field.
    3.  **Step 2 (Live):** Dispatches a `LiveSchemaAgent` to call a `get_table_last_modified_time` tool for that specific table.
    4.  **Step 3 (Synthesis):** The LLM combines the rich lineage context from the cache with the up-to-the-second timestamp from the live agent to provide a complete answer.

### Final Architectural Advantages

*   **Optimal Performance & Cost:** Serves most queries (90%+) from a fast, cost-effective managed cache while reserving expensive live calls for when they are truly necessary.
*   **Radical Simplicity:** Leverages a managed GCP service (Vertex AI Search) to handle the immense complexity of building and maintaining a RAG pipeline—no custom vector databases, embedding pipelines, or indexing infrastructure needed.
*   **Powerful, Precise Search:** The JSONL ingestion format allows for a powerful combination of semantic search on text and exact filtering on structured metadata, enabling far more intelligent queries than pure vector search.
*   **Dual-Purpose Output:** The system produces both machine-readable indexes for agents and human-readable Markdown reports for stakeholders, all from a single discovery run—maximizing efficiency and ensuring consistency.
*   **Reliability & Freshness by Design:** Provides the speed of a cache for general queries and the guaranteed accuracy of live calls for critical ones, ensuring users can trust the results.
*   **Accelerated Development:** Leverages Google's GenAI Toolbox for pre-built data source connectors, reducing development time while maintaining custom capabilities for specialized operations.
*   **Enterprise-Grade Security:** Read-only by design with explicit metadata-only write constraints (SR-2A), comprehensive audit logging, and least-privilege service account architecture.
*   **Extensibility:** Abstract base layer and plugin architecture enable seamless addition of new data sources (GCS, Cloud SQL, Spanner) without re-architecting the core system.

---

### Architecture Principles

**1. Read-Only First (SR-2A Compliance)**
*   All discovery and indexing operations are strictly read-only to source systems
*   No DDL (CREATE, ALTER, DROP) or DML (INSERT, UPDATE, DELETE) operations on data sources
*   Write operations limited to metadata systems only (Data Catalog, resource labels)
*   All metadata writes require explicit approval with preview and audit trail

**2. Cache-First with Live Fallback**
*   Default to cached Vertex AI Search for 90%+ of queries (sub-second response)
*   Use live agents only when data freshness is critical (permissions, current status)
*   Hybrid mode intelligently combines both approaches for complex queries

**3. Separation of Concerns**
*   **Background Indexers:** Comprehensive, scheduled discovery (nightly/hourly)
*   **Live Agents:** Lightweight, targeted queries (on-demand)
*   **Smart Router:** Intelligent query classification and orchestration
*   Each component has a single, well-defined responsibility

**4. Dual Output Generation**
*   Every discovery run produces both machine-readable (JSONL) and human-readable (Markdown) outputs
*   Ensures consistency between what agents search and what humans review
*   Supports both automated workflows and manual audits

**5. Extensible by Design**
*   Abstract base classes for data sources, discovery interfaces, and metadata models
*   Plugin registry system for adding new data sources at runtime
*   Consistent patterns across all data source implementations
*   Future sources (GCS, Cloud SQL) follow the same architectural blueprint

**6. Hybrid Tooling Strategy**
*   Leverage pre-built GenAI Toolbox tools where they provide value (speed, maintenance)
*   Build custom tools for specialized, security-sensitive, or unique operations
*   All tools (both sources) are audited for security compliance
*   Best of both worlds: accelerated development + full control

**7. Security in Depth**
*   Application Default Credentials (ADC) for authentication
*   Least-privilege service accounts (separate read-only and metadata-write accounts)
*   Comprehensive audit logging of all operations
*   Input validation and protection against injection attacks
*   Regular security scanning of dependencies and infrastructure

---

### Extensibility: Adding New Data Sources

The architecture is designed for easy extension to additional data sources:

**Example: Adding GCS Bucket Discovery**

1.  **Implement Base Abstractions:** Create `GCSDataSource` extending the abstract `DataSource` class
2.  **Create Indexer Agents:** Build GCS-specific indexer agents (object inventory, access logs, lifecycle policies)
3.  **Create Live Agents:** Build lightweight live agents for real-time GCS operations
4.  **Define JSONL Schema:** Extend the JSONL schema for GCS assets (bucket, object metadata)
5.  **Register in System:** Add to data source registry for automatic discovery
6.  **Leverage GenAI Toolbox:** Use pre-built GCS tools from GenAI Toolbox where available
7.  **Single Vertex AI Search:** All data sources feed into the same unified search index

The Smart Router automatically handles multi-source queries, filtering by `structData.data_source` field.

**Future Data Sources:**
*   Cloud SQL (schema discovery, query performance, replication status)
*   AlloyDB (similar to Cloud SQL with specialized features)
*   Spanner (global distribution, schema evolution)
*   Cloud Storage (object metadata, lifecycle, access patterns)
*   dbt (transformation lineage) - via custom integration

> **Note**: Looker integration disabled for initial deployment. Can be added later via GenAI Toolbox.

Each follows the same pattern: indexers → aggregator → dual output → unified search + specialized live agents.