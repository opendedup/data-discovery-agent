# BigQuery Data Discovery Agent

An automated BigQuery metadata discovery system that makes your data estate searchable through natural language. Scan BigQuery datasets, enrich metadata with AI-generated descriptions, and query your data catalog using AI assistants like Cursor or Claude Desktop.

## What Does This Do?

This tool automates BigQuery metadata collection and makes it searchable:

1. **Scans BigQuery** - Collects table schemas, statistics, descriptions, and lineage
2. **Enriches Metadata** - Uses Dataplex profiling and Gemini AI to generate descriptions and insights
3. **Indexes for Search** - Exports to Vertex AI Search for semantic search capabilities
4. **Provides MCP Interface** - Exposes data discovery through Model Context Protocol for AI assistants

**Use Cases:**
- Find tables by natural language queries ("customer transaction data with PII")
- Discover upstream/downstream dependencies
- Track data lineage and governance
- Generate automated documentation
- Enable AI assistants to understand your data estate

## Key Features

- **Automated BigQuery Scanning** - Multi-threaded collection from multiple projects and datasets
- **AI-Powered Descriptions** - Gemini generates table and column descriptions automatically
- **Rich Column Profiling** - Dataplex integration provides statistics, distributions, and sample values
- **Data Lineage Tracking** - Captures upstream and downstream dependencies via Data Catalog Lineage API
- **Semantic Search** - Vertex AI Search enables natural language queries over metadata
- **MCP Server** - Integrates with Cursor, Claude Desktop, and other MCP-compatible AI assistants
- **Automated Reports** - Generates markdown documentation for each table
- **Label-Based Filtering** - Exclude tables using BigQuery labels (e.g., `ignore-discovery-scan: true`)

## Prerequisites

### Required GCP Resources

You need the following GCP resources provisioned (infrastructure deployment is handled separately):

- **BigQuery** datasets to scan
- **Vertex AI Search** datastore (global location recommended)
- **GCS Buckets**:
  - JSONL bucket for Vertex AI Search import
  - Reports bucket for markdown documentation
- **Dataplex** - For rich column profiling and data quality statistics
- **Gemini API** - For AI-generated table and column descriptions
- **Cloud Composer** (optional) - For scheduled, production-grade metadata collection via Airflow
- **Service Account** with permissions:
  - BigQuery Data Viewer
  - Storage Object Admin (for buckets)
  - Vertex AI Search Editor
  - Dataplex Data Reader (for column profiling)
  - Data Catalog LineageAdmin (optional, for lineage tracking)
  - Composer Worker (optional, if using Cloud Composer)

### Local Requirements

- Python >= 3.10
- Poetry (for dependency management)
- gcloud CLI (authenticated)

## Quick Start

### 1. Install Dependencies

```bash
git clone <repository-url>
cd data-discovery-agent
poetry install
```

### 2. Configure Environment

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env` with your GCP project and resource details:

```bash
GCP_PROJECT_ID=your-project-id
GCS_JSONL_BUCKET=your-jsonl-bucket
GCS_REPORTS_BUCKET=your-reports-bucket
VERTEX_DATASTORE_ID=data-discovery-metadata
VERTEX_LOCATION=global
GEMINI_API_KEY=your-gemini-api-key  # Optional, for AI descriptions
```

### 3. Run Your First Scan

Test with a limited number of tables:

```bash
poetry run python scripts/collect-bigquery-metadata.py --max-tables 10
```

This will:
1. Scan up to 10 BigQuery tables from your project
2. Collect schemas, statistics, and metadata
3. Generate JSONL documents for Vertex AI Search
4. Upload to GCS and trigger Vertex AI Search import
5. Create markdown reports for each table

## Usage

### Command Line Scanning

#### Basic Scan

Scan all tables in your project and import to Vertex AI Search:

```bash
poetry run python scripts/collect-bigquery-metadata.py
```

#### Scan with Enhanced Features

Use Dataplex profiling and Gemini AI descriptions for richer metadata:

```bash
poetry run python scripts/collect-bigquery-metadata.py \
  --use-dataplex \
  --use-gemini \
  --workers 5
```

#### Multi-Project Scan

Scan specific projects with filtering:

```bash
poetry run python scripts/collect-bigquery-metadata.py \
  --projects prod-project-1 prod-project-2 \
  --exclude-datasets "_staging" "temp_" \
  --workers 10
```

#### Test Scan (No Import)

Collect metadata without uploading to GCS or triggering Vertex AI Search:

```bash
poetry run python scripts/collect-bigquery-metadata.py \
  --max-tables 5 \
  --skip-gcs \
  --skip-import
```

#### Export to BigQuery

Store collected metadata in a BigQuery table for analysis:

```bash
poetry run python scripts/collect-bigquery-metadata.py \
  --export-to-bigquery \
  --bq-dataset data_discovery \
  --bq-table discovered_assets
```

### CLI Options Reference

| Option | Description | Default |
|--------|-------------|---------|
| `--project` | GCP project to scan | From `GCP_PROJECT_ID` env var |
| `--projects` | Multiple projects to scan | Current project only |
| `--max-tables` | Limit number of tables to scan | Unlimited |
| `--exclude-datasets` | Dataset name patterns to skip | `_staging`, `temp_`, `tmp_` |
| `--skip-views` | Skip views, scan only tables | Include views |
| `--use-dataplex` | Enable Dataplex column profiling | Disabled |
| `--dataplex-location` | Dataplex region | `us-central1` |
| `--use-gemini` | Enable Gemini AI descriptions | Disabled |
| `--skip-gemini` | Disable Gemini (overrides --use-gemini) | Enabled if API key set |
| `--workers` | Number of parallel threads | Auto-detect CPU cores |
| `--skip-gcs` | Don't upload to GCS | Upload enabled |
| `--skip-markdown` | Don't generate markdown reports | Reports enabled |
| `--import` | Trigger Vertex AI Search import | Import by default |
| `--skip-import` | Don't import to Vertex AI Search | Import enabled |
| `--export-to-bigquery` | Export metadata to BigQuery table | Disabled |
| `--bq-dataset` | BigQuery dataset for export | `data_discovery` |
| `--bq-table` | BigQuery table for export | `discovered_assets` |
| `-v, --verbose` | Enable debug logging | Info level |

### Label-Based Filtering

Exclude specific datasets or tables from scans using BigQuery labels:

```bash
# Add label to a dataset
bq update --set_label ignore-discovery-scan:true your_project:your_dataset

# Add label to a specific table
bq update --set_label ignore-discovery-scan:true \
  your_project:your_dataset.your_table
```

The scanner respects this label by default. Use `--filter-label-key` to customize the label name.

### Cloud Composer / Airflow DAG

For scheduled, production-grade metadata collection, use the provided Airflow orchestration tasks.

#### Example DAG

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

from data_discovery_agent.orchestration.tasks import (
    collect_metadata_task,
    export_to_bigquery_task,
    export_markdown_reports_task,
    import_to_vertex_ai_task,
)

default_args = {
    'owner': 'data-engineering',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'bigquery_metadata_collection',
    default_args=default_args,
    description='Collect BigQuery metadata and index in Vertex AI Search',
    schedule_interval='0 2 * * *',  # Daily at 2 AM
    start_date=datetime(2024, 1, 1),
    catchup=False,
    params={
        'collector_args': {
            'use_dataplex': True,
            'use_gemini': True,
            'workers': 5,
            'exclude_datasets': ['_staging', 'temp_', 'tmp_'],
        }
    },
) as dag:

    collect_metadata = PythonOperator(
        task_id='collect_metadata',
        python_callable=collect_metadata_task,
        provide_context=True,
    )

    export_to_bigquery = PythonOperator(
        task_id='export_to_bigquery',
        python_callable=export_to_bigquery_task,
        provide_context=True,
    )

    export_markdown = PythonOperator(
        task_id='export_markdown_reports',
        python_callable=export_markdown_reports_task,
        provide_context=True,
    )

    import_to_vertex = PythonOperator(
        task_id='import_to_vertex_ai',
        python_callable=import_to_vertex_ai_task,
        provide_context=True,
    )

    # Task dependencies
    collect_metadata >> [export_to_bigquery, export_markdown]
    export_to_bigquery >> import_to_vertex
```

#### Configure in Cloud Composer

1. Set environment variables in your Cloud Composer environment:
   - `GCP_PROJECT_ID`
   - `GCS_JSONL_BUCKET`
   - `GCS_REPORTS_BUCKET`
   - `VERTEX_DATASTORE_ID`
   - `GEMINI_API_KEY` (optional)
   - `BQ_DATASET` (optional, default: `data_discovery`)
   - `BQ_TABLE` (optional, default: `discovered_assets`)

2. Deploy the DAG to your Cloud Composer DAGs folder

3. Trigger manually or let it run on schedule

See [`src/data_discovery_agent/orchestration/tasks.py`](src/data_discovery_agent/orchestration/tasks.py) for complete task documentation.

### MCP Server for AI Assistants

The MCP (Model Context Protocol) server enables AI assistants like Cursor and Claude Desktop to discover and understand your BigQuery data estate.

#### What is MCP?

MCP is an open standard that allows AI assistants to securely access tools and context from external systems. This project implements an MCP server that exposes BigQuery metadata discovery as tools for AI assistants.

#### Available MCP Tools

1. **`query_data_assets`** - Search for tables using natural language
2. **`get_asset_details`** - Get comprehensive documentation for a specific table
3. **`list_datasets`** - Browse all datasets in a project

#### Setup for Cursor

Add to your Cursor MCP configuration file (`~/.cursor/mcp.json` or `<project>/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "data-discovery": {
      "command": "poetry",
      "args": ["run", "python", "-m", "data_discovery_agent.mcp"],
      "env": {
        "GCP_PROJECT_ID": "your-project-id",
        "VERTEX_DATASTORE_ID": "data-discovery-metadata",
        "VERTEX_LOCATION": "global",
        "GCS_REPORTS_BUCKET": "your-reports-bucket",
        "MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```

#### Setup for Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "data-discovery": {
      "command": "/path/to/poetry",
      "args": ["run", "python", "-m", "data_discovery_agent.mcp"],
      "env": {
        "GCP_PROJECT_ID": "your-project-id",
        "VERTEX_DATASTORE_ID": "data-discovery-metadata",
        "VERTEX_LOCATION": "global",
        "GCS_REPORTS_BUCKET": "your-reports-bucket",
        "MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```

#### Example Queries Through AI Assistant

Once configured, you can ask your AI assistant questions like:

- "Find tables with customer PII data"
- "Show me all tables in the analytics dataset"
- "What are the most expensive tables to query?"
- "Get details for project.dataset.table_name"
- "Find tables updated in the last 7 days"
- "Show tables with more than 1 million rows"

The AI assistant will use the MCP tools to search your BigQuery metadata and provide comprehensive answers.

#### HTTP Mode (Remote/Container Deployment)

For containerized deployments, run the MCP server in HTTP mode:

```bash
# Set environment
export MCP_TRANSPORT=http
export MCP_HOST=0.0.0.0
export MCP_PORT=8080

# Run server
poetry run python -m data_discovery_agent.mcp.http_server
```

Then configure clients to connect via HTTP:

```json
{
  "mcpServers": {
    "data-discovery": {
      "url": "http://localhost:8080"
    }
  }
}
```

See [`docs/MCP_CLIENT_GUIDE.md`](docs/MCP_CLIENT_GUIDE.md) for detailed MCP usage documentation.

## Configuration Reference

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `GCP_PROJECT_ID` | Your GCP project ID | Yes | - |
| `GCS_JSONL_BUCKET` | GCS bucket for JSONL exports | Yes | - |
| `GCS_REPORTS_BUCKET` | GCS bucket for markdown reports | Yes | - |
| `VERTEX_DATASTORE_ID` | Vertex AI Search datastore ID | Yes | - |
| `VERTEX_LOCATION` | Vertex AI Search location | No | `global` |
| `GEMINI_API_KEY` | Gemini API key for AI descriptions | No | - |
| `BQ_DATASET` | BigQuery dataset for metadata export | No | `data_discovery` |
| `BQ_TABLE` | BigQuery table for metadata export | No | `discovered_assets` |
| `BQ_LOCATION` | BigQuery dataset location | No | `US` |
| `LINEAGE_ENABLED` | Enable lineage tracking | No | `true` |
| `LINEAGE_LOCATION` | Lineage API region | No | `us-central1` |
| `MCP_TRANSPORT` | MCP transport mode (`stdio` or `http`) | No | `stdio` |
| `MCP_HOST` | MCP HTTP server host | No | `0.0.0.0` |
| `MCP_PORT` | MCP HTTP server port | No | `8080` |

See [`.env.example`](.env.example) for the complete configuration template.

### Performance Tuning

#### Multi-Threading

The scanner uses multi-threading for parallel table collection. By default, it auto-detects the number of CPU cores. Adjust with `--workers`:

```bash
# Use 10 worker threads
poetry run python scripts/collect-bigquery-metadata.py --workers 10

# Use 1 worker (sequential processing)
poetry run python scripts/collect-bigquery-metadata.py --workers 1
```

**Performance Impact:**
- 5 workers (default on most systems): ~5x faster than sequential
- 10 workers: ~8-10x faster (diminishing returns beyond CPU count)
- Consider BigQuery quota limits when increasing workers

#### Dataplex Profiling

Dataplex provides richer column statistics but adds API calls:

```bash
# Without Dataplex: Faster, basic stats only
poetry run python scripts/collect-bigquery-metadata.py

# With Dataplex: Slower, detailed profiling
poetry run python scripts/collect-bigquery-metadata.py --use-dataplex
```

## Output

### JSONL Documents

Structured metadata exported to GCS for Vertex AI Search ingestion:

- **Location:** `gs://{GCS_JSONL_BUCKET}/batch_{timestamp}.jsonl`
- **Format:** One JSON document per table with schema, stats, lineage, security metadata
- **Auto-imported** to Vertex AI Search (indexing takes 5-10 minutes)

### Markdown Reports

Human-readable documentation generated for each table:

- **Location:** `gs://{GCS_REPORTS_BUCKET}/reports/{timestamp}/{project}/{dataset}/{table}.md`
- **Contents:** Schema, statistics, sample values, lineage, quality metrics, insights
- **Accessible** via MCP `get_asset_details` tool

### BigQuery Export (Optional)

Metadata can be exported to a BigQuery table for analysis:

```bash
poetry run python scripts/collect-bigquery-metadata.py --export-to-bigquery
```

Table schema includes:
- All metadata fields (schema, statistics, lineage)
- `run_timestamp` for tracking collection runs
- Enables SQL queries over your metadata catalog

### Lineage Tracking (Automatic)

Data Catalog Lineage API automatically tracks:
- **BigQuery → BigQuery export:** Collection process → Metadata table
- **BigQuery → GCS reports:** Table → Markdown documentation
- Enables lineage visualization in Data Catalog

## Documentation

- **[MCP Client Guide](docs/MCP_CLIENT_GUIDE.md)** - Detailed MCP server usage and integration
- **[Architecture](docs/ARCHITECTURE.md)** - System design and components
- **[Pipeline Setup](docs/PIPELINE_SETUP.md)** - Cloud Composer and Airflow configuration
- **[Docker Deployment](docs/DOCKER_DEPLOYMENT.md)** - Container deployment guide

## Development

### Install Development Dependencies

```bash
poetry install
```

### Run Tests

```bash
poetry run pytest
```

### Code Formatting

```bash
poetry run black src/
poetry run ruff check src/
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

Built with:
- **Google Cloud Platform** - BigQuery, Vertex AI Search, Dataplex, Data Catalog
- **Gemini AI** - Automated table and column descriptions
- **Model Context Protocol (MCP)** - AI assistant integration
- **Poetry** - Dependency management
- **Python** - Core implementation
