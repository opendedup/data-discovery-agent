# MCP Client Usage Guide

## Table of Contents

1. [Overview](#overview)
2. [Transport Modes](#transport-modes)
3. [Available Tools](#available-tools)
4. [Query Patterns & Best Practices](#query-patterns--best-practices)
5. [Filtering Guidelines](#filtering-guidelines)
6. [Pagination](#pagination)
7. [Output Formats](#output-formats)
8. [Common Use Cases](#common-use-cases)
9. [Code Examples](#code-examples)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The Data Discovery MCP (Model Context Protocol) service provides AI assistants and applications with powerful tools to discover, search, and explore BigQuery data assets. The service exposes three main tools:

- **`query_data_assets`** - Search for tables using natural language queries and filters
- **`get_asset_details`** - Get comprehensive documentation for a specific table
- **`list_datasets`** - Browse all datasets in a project with summary information

### Key Features

- 🔍 **Natural Language Search** - Query using plain English (e.g., "tables with customer data")
- 🏷️ **Rich Metadata** - Schema, security classifications, costs, quality metrics, lineage
- 🔐 **Security Aware** - Filter by PII, PHI, and other sensitivity markers
- 💰 **Cost Tracking** - Monthly cost estimates and query cost analysis
- 📊 **Quality Metrics** - Completeness, freshness, and usage statistics
- 🔗 **Lineage Tracking** - Upstream and downstream dependencies
- 📄 **Pagination Support** - Handle large result sets efficiently

---

## Transport Modes

The MCP service supports two transport modes:

### 1. Stdio Transport (Local/Subprocess)

**Use when:**
- Running the MCP server as a subprocess from your application
- Local development and testing
- Direct integration with MCP-compatible tools

**Configuration:**
```bash
MCP_TRANSPORT=stdio
```

**Example:**
See [examples/mcp_client_example.py](../examples/mcp_client_example.py) for a complete stdio client implementation.

### 2. HTTP Transport (Network/Container)

**Use when:**
- Deploying the MCP service in a container (Docker/Kubernetes)
- Remote access from multiple clients
- Production deployments

**Configuration:**
```bash
MCP_TRANSPORT=http
MCP_HOST=0.0.0.0
MCP_PORT=8080
```

**Endpoints:**
- `GET /health` - Health check
- `GET /` - Service information
- `GET /mcp/tools` - List available tools
- `POST /mcp/call-tool` - Execute a tool

**Example:**
See [examples/http_client_example.py](../examples/http_client_example.py) for a complete HTTP client implementation.

---

## Available Tools

### 1. `query_data_assets`

Search for BigQuery tables, views, and datasets using natural language queries.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Natural language search query |
| `project_id` | string | No | Filter by specific GCP project |
| `dataset_id` | string | No | Filter by specific dataset |
| `has_pii` | boolean | No | Filter tables with PII data |
| `has_phi` | boolean | No | Filter tables with PHI data |
| `environment` | string | No | Filter by environment (prod, staging, dev) |
| `min_row_count` | integer | No | Minimum number of rows |
| `max_row_count` | integer | No | Maximum number of rows |
| `min_cost` | number | No | Minimum monthly cost (USD) |
| `max_cost` | number | No | Maximum monthly cost (USD) |
| `sort_by` | string | No | Sort field (row_count, size_bytes, monthly_cost_usd) |
| `sort_order` | string | No | Sort order: 'asc' or 'desc' (default: desc) |
| `page_size` | integer | No | Results per page (1-50, default: 10) |
| `page_token` | string | No | Token for next page |
| `include_full_content` | boolean | No | Include full Markdown docs (default: true) |
| `output_format` | string | No | 'markdown' or 'json' (default: markdown) |

#### Example Queries

**Natural Language:**
```json
{
  "query": "tables with customer data"
}
```

**With PII Filter:**
```json
{
  "query": "analytics tables",
  "has_pii": true
}
```

**Large Tables Only:**
```json
{
  "query": "production tables",
  "min_row_count": 1000000,
  "environment": "production"
}
```

**Cost Analysis:**
```json
{
  "query": "expensive tables",
  "min_cost": 10.0,
  "sort_by": "monthly_cost_usd",
  "sort_order": "desc"
}
```

### 2. `get_asset_details`

Get comprehensive documentation for a specific BigQuery table or view.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | string | Yes | GCP project ID |
| `dataset_id` | string | Yes | BigQuery dataset ID |
| `table_id` | string | Yes | BigQuery table/view ID |
| `include_lineage` | boolean | No | Include lineage info (default: true) |
| `include_usage` | boolean | No | Include usage stats (default: true) |

#### Example

```json
{
  "project_id": "my-project",
  "dataset_id": "analytics",
  "table_id": "user_events"
}
```

**Returns:** Full Markdown documentation including:
- Executive summary with key metrics
- Detailed schema with descriptions
- Security and compliance information
- Cost analysis and trends
- Quality scores
- Lineage (upstream/downstream dependencies)
- Usage patterns and recommendations
- Sample analytical queries

### 3. `list_datasets`

List all BigQuery datasets in a project with summary information.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | string | No | GCP project (uses default if omitted) |
| `include_table_counts` | boolean | No | Include table counts (default: true) |
| `include_costs` | boolean | No | Include cost estimates (default: true) |
| `page_size` | integer | No | Results per page (1-50, default: 50) |
| `page_token` | string | No | Token for next page |

#### Example

```json
{
  "project_id": "my-project",
  "page_size": 20
}
```

**Returns:** Dataset-level summary with:
- Dataset name and description
- Number of tables/views
- Total row count and size
- Aggregate cost estimates
- PII/PHI indicators

---

## Query Patterns & Best Practices

### Effective Natural Language Queries

#### ✅ Good Query Patterns

**Be Specific:**
```
❌ "data"
✅ "customer transaction tables"
✅ "tables containing order history"
```

**Use Domain Language:**
```
✅ "sales analytics tables"
✅ "user behavior datasets"
✅ "financial reporting tables"
```

**Describe Purpose or Content:**
```
✅ "tables for fraud detection"
✅ "tables with player statistics"
✅ "marketing campaign performance data"
```

**Time-based Queries:**
```
✅ "recently modified tables"
✅ "tables updated in the last week"
✅ "stale tables not accessed recently"
```

#### ❌ Query Anti-Patterns

**Too Vague:**
```
❌ "tables"
❌ "data"
❌ "info"
```

**Too Technical (use filters instead):**
```
❌ "tables where has_pii=true"
✅ Use filter: {"has_pii": true}
```

**Overly Complex (break into multiple queries):**
```
❌ "tables with PII in production or staging with more than 1M rows sorted by cost"
✅ Use multiple queries or combine query + filters
```

### Query + Filter Combinations

Combine natural language queries with structured filters for precise results:

```json
{
  "query": "customer analytics",
  "environment": "production",
  "has_pii": true,
  "min_row_count": 100000,
  "sort_by": "monthly_cost_usd",
  "sort_order": "desc"
}
```

This finds customer analytics tables in production with PII data and at least 100K rows, sorted by cost.

---

## Filtering Guidelines

### Boolean Filters (PII/PHI)

**Filter tables with sensitive data:**
```json
{
  "query": "user tables",
  "has_pii": true
}
```

**Filter out sensitive data:**
```json
{
  "query": "analytics tables",
  "has_pii": false
}
```

**Combine both:**
```json
{
  "query": "healthcare data",
  "has_pii": true,
  "has_phi": true
}
```

### Size Filters

**Small tables (< 1M rows):**
```json
{
  "query": "lookup tables",
  "max_row_count": 1000000
}
```

**Large tables (> 100M rows):**
```json
{
  "query": "event logs",
  "min_row_count": 100000000
}
```

**Size range:**
```json
{
  "query": "medium tables",
  "min_row_count": 1000000,
  "max_row_count": 10000000
}
```

### Cost Filters

**Expensive tables (> $10/month):**
```json
{
  "query": "production tables",
  "min_cost": 10.0,
  "sort_by": "monthly_cost_usd"
}
```

**Free tier tables:**
```json
{
  "query": "test tables",
  "max_cost": 0.0
}
```

**Cost optimization candidates:**
```json
{
  "query": "rarely accessed tables",
  "min_cost": 5.0
}
```

### Environment Filters

```json
{
  "query": "user tables",
  "environment": "production"
}
```

Common values: `production`, `staging`, `development`, `test`

### Combining Filters

**Best Practice:** Combine filters to narrow results:

```json
{
  "query": "analytics tables",
  "environment": "production",
  "has_pii": false,
  "min_row_count": 10000,
  "max_cost": 5.0,
  "page_size": 20
}
```

This finds non-PII production analytics tables with at least 10K rows and monthly cost under $5.

---

## Pagination

The MCP service uses cursor-based pagination for handling large result sets.

### Initial Request

```json
{
  "query": "all tables",
  "page_size": 10
}
```

### Response Includes Next Page Token

```markdown
**More results available!**
To get the next page, use `page_token`: `AOkNWZlFWOyQjM4UTLjNDMh1SZxEmMtADMwATL2YDNhV2YiZDJaoygfOOEGc85hOMCLIBMxIgC`
```

### Subsequent Request

```json
{
  "query": "all tables",
  "page_size": 10,
  "page_token": "AOkNWZlFWOyQjM4UTLjNDMh1SZxEmMtADMwATL2YDNhV2YiZDJaoygfOOEGc85hOMCLIBMxIgC"
}
```

### Pagination Best Practices

1. **Start with reasonable page size** (10-20 for exploration, 50 for bulk processing)
2. **Use consistent page_size** across paginated requests
3. **Keep the same query and filters** when paginating
4. **Don't modify filters mid-pagination** (results may be inconsistent)
5. **Check `has_more_results`** to know when pagination is complete

### Example: Paginate Through All Results

```python
async def get_all_results(client, query):
    all_results = []
    page_token = None
    
    while True:
        args = {"query": query, "page_size": 50}
        if page_token:
            args["page_token"] = page_token
        
        response = await client.call_tool("query_data_assets", args)
        
        # Parse results (implementation depends on your client)
        results = parse_response(response)
        all_results.extend(results)
        
        # Check for more results
        if not has_more_results(response):
            break
        
        page_token = extract_next_page_token(response)
    
    return all_results
```

---

## Output Formats

### Markdown Format (Default)

Human-readable format with rich formatting, perfect for:
- AI assistants reading and presenting information
- Interactive dashboards
- Documentation generation
- Reports

**Example:**
```json
{
  "query": "customer tables",
  "output_format": "markdown"
}
```

**Returns:**
```markdown
# Search Results: customer tables

Found **5** matching assets
*(Query time: 123ms)*

---

## 1. analytics.customers

**Type**: TABLE | **Rows**: 1,234,567 | **Size**: 2.5 GB | **Cost**: $1.25/mo

🔒 PII 🌍 PRODUCTION

[Open in BigQuery Console](https://console.cloud.google.com/bigquery?...)

---
```

### JSON Format

Structured format for programmatic access:
- API integrations
- Data processing pipelines
- Custom visualizations
- Machine-readable formats

**Example:**
```json
{
  "query": "customer tables",
  "output_format": "json"
}
```

**Returns:**
```json
{
  "query": "customer tables",
  "total_count": 5,
  "query_time_ms": 123,
  "filters_applied": {},
  "results": [
    {
      "id": "projects/my-project/locations/us/datastores/...",
      "project_id": "my-project",
      "dataset_id": "analytics",
      "table_id": "customers",
      "asset_type": "TABLE",
      "row_count": 1234567,
      "size_bytes": 2684354560,
      "has_pii": true,
      "environment": "production",
      "monthly_cost_usd": 1.25,
      ...
    }
  ]
}
```

---

## Common Use Cases

### 1. Finding Tables with Specific Data

**Use Case:** "I need tables containing NFL player statistics"

```json
{
  "query": "NFL player statistics",
  "page_size": 10
}
```

### 2. Data Security Audit

**Use Case:** "Find all production tables with PII that cost more than $10/month"

```json
{
  "query": "production tables",
  "has_pii": true,
  "environment": "production",
  "min_cost": 10.0,
  "sort_by": "monthly_cost_usd",
  "sort_order": "desc"
}
```

### 3. Cost Optimization

**Use Case:** "Identify expensive tables for cost reduction"

```json
{
  "query": "expensive tables",
  "min_cost": 20.0,
  "sort_by": "monthly_cost_usd",
  "sort_order": "desc",
  "page_size": 20
}
```

### 4. Schema Exploration

**Use Case:** "Get detailed schema and documentation for a specific table"

```json
{
  "project_id": "my-project",
  "dataset_id": "analytics",
  "table_id": "user_events"
}
```

### 5. Dataset Discovery

**Use Case:** "What datasets are available in my project?"

```json
{
  "project_id": "my-project",
  "include_table_counts": true,
  "include_costs": true
}
```

### 6. Data Quality Assessment

**Use Case:** "Find tables that haven't been accessed recently"

```json
{
  "query": "stale tables not accessed in 90 days",
  "environment": "production"
}
```

### 7. Compliance Reporting

**Use Case:** "Generate a report of all tables with PHI"

```json
{
  "query": "tables with protected health information",
  "has_phi": true,
  "output_format": "json",
  "page_size": 50
}
```

### 8. Development Environment Setup

**Use Case:** "Find small test tables for development"

```json
{
  "query": "test tables",
  "environment": "development",
  "max_row_count": 10000,
  "max_cost": 0.0
}
```

---

## Code Examples

### Python HTTP Client

```python
import asyncio
import httpx
from dotenv import load_dotenv
import os

load_dotenv()

class MCPHttpClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def close(self):
        await self.client.aclose()
    
    async def call_tool(self, tool_name: str, arguments: dict):
        response = await self.client.post(
            f"{self.base_url}/mcp/call-tool",
            json={"name": tool_name, "arguments": arguments}
        )
        response.raise_for_status()
        return response.json().get("result", [])

async def main():
    # Connect to service
    client = MCPHttpClient("http://localhost:8080")
    
    try:
        # Example 1: Search for tables
        result = await client.call_tool(
            "query_data_assets",
            {
                "query": "customer analytics tables",
                "has_pii": true,
                "page_size": 10
            }
        )
        
        for item in result:
            print(item.get("text"))
        
        # Example 2: Get specific table details
        result = await client.call_tool(
            "get_asset_details",
            {
                "project_id": "my-project",
                "dataset_id": "analytics",
                "table_id": "customers"
            }
        )
        
        for item in result:
            print(item.get("text"))
        
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### Python Stdio Client

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "data_discovery_agent.mcp.server"],
        env={
            "GCP_PROJECT_ID": os.getenv("GCP_PROJECT_ID"),
            "GCS_REPORTS_BUCKET": os.getenv("GCS_REPORTS_BUCKET"),
            "VERTEX_DATASTORE_ID": os.getenv("VERTEX_DATASTORE_ID"),
            "LOG_LEVEL": "INFO",
        }
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # List available tools
            tools = await session.list_tools()
            print(f"Available tools: {len(tools.tools)}")
            
            # Call a tool
            result = await session.call_tool(
                "query_data_assets",
                arguments={
                    "query": "customer tables",
                    "has_pii": True,
                    "page_size": 10
                }
            )
            
            for content in result.content:
                if content.type == "text":
                    print(content.text)

if __name__ == "__main__":
    asyncio.run(main())
```

### cURL Examples

**List tools:**
```bash
curl http://localhost:8080/mcp/tools | jq
```

**Search for tables:**
```bash
curl -X POST http://localhost:8080/mcp/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "name": "query_data_assets",
    "arguments": {
      "query": "customer tables",
      "has_pii": true,
      "page_size": 10
    }
  }' | jq
```

**Get table details:**
```bash
curl -X POST http://localhost:8080/mcp/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "name": "get_asset_details",
    "arguments": {
      "project_id": "my-project",
      "dataset_id": "analytics",
      "table_id": "customers"
    }
  }' | jq
```

**List datasets:**
```bash
curl -X POST http://localhost:8080/mcp/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "name": "list_datasets",
    "arguments": {
      "project_id": "my-project",
      "page_size": 20
    }
  }' | jq
```

---

## Troubleshooting

### Common Issues

#### 1. Empty Results

**Problem:** Query returns 0 results

**Solutions:**
- Make query less specific: "tables" instead of "customer_analytics_tables_v2"
- Remove restrictive filters: Check `has_pii`, `min_row_count`, `environment`
- Verify data has been indexed: Run metadata collection pipeline
- Check project_id is correct

#### 2. Too Many Results

**Problem:** Query returns too many irrelevant results

**Solutions:**
- Make query more specific: Add domain context
- Add filters: `has_pii`, `environment`, `dataset_id`
- Use size/cost filters to narrow scope
- Reduce `page_size` for initial exploration

#### 3. Slow Queries

**Problem:** Queries take a long time

**Solutions:**
- Reduce `page_size` (default: 10)
- Use more specific queries
- Add filters to narrow search space
- Check Vertex AI Search service status

#### 4. Connection Errors (HTTP)

**Problem:** Cannot connect to MCP service

**Solutions:**
- Verify service is running: `curl http://localhost:8080/health`
- Check firewall rules and network connectivity
- Verify `MCP_SERVICE_URL` environment variable
- Check logs: `docker logs <container-id>` or `kubectl logs <pod>`

#### 5. Authentication Errors

**Problem:** 403 Forbidden or 401 Unauthorized

**Solutions:**
- Verify GCP credentials are configured
- Check service account has required permissions:
  - `roles/discoveryengine.viewer` for Vertex AI Search
  - `roles/storage.objectViewer` for GCS
  - `roles/bigquery.metadataViewer` for BigQuery
- Ensure Application Default Credentials are set

#### 6. Missing Metadata

**Problem:** Table exists but not found by MCP service

**Solutions:**
- Verify table is indexed in Vertex AI Search
- Run metadata collection pipeline
- Check table is not excluded in `bigquery_collector.py`
- Verify data was written to GCS and indexed

#### 7. Validation Errors

**Problem:** "Parameter validation failed"

**Solutions:**
- Check required parameters are provided
- Verify parameter types (string, boolean, integer)
- Ensure `page_size` is between 1 and 50
- Ensure `sort_order` is 'asc' or 'desc'

### Debug Mode

Enable debug logging for troubleshooting:

```bash
# Stdio mode
LOG_LEVEL=DEBUG poetry run python -m data_discovery_agent.mcp.server

# HTTP mode
MCP_TRANSPORT=http LOG_LEVEL=DEBUG poetry run python -m data_discovery_agent.mcp.server
```

### Health Check

**HTTP Transport:**
```bash
curl http://localhost:8080/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "service": "data-discovery-mcp",
  "transport": "http"
}
```

### Verify Configuration

Check environment variables are loaded:

```python
from dotenv import load_dotenv
import os

load_dotenv()

print(f"Project: {os.getenv('GCP_PROJECT_ID')}")
print(f"Bucket: {os.getenv('GCS_REPORTS_BUCKET')}")
print(f"Datastore: {os.getenv('VERTEX_DATASTORE_ID')}")
```

---

## Additional Resources

- **Architecture Documentation**: [docs/ARCHITECTURE.md](ARCHITECTURE.md)
- **Pipeline Setup Guide**: [docs/PIPELINE_SETUP.md](PIPELINE_SETUP.md)
- **Stdio Client Example**: [examples/mcp_client_example.py](../examples/mcp_client_example.py)
- **HTTP Client Example**: [examples/http_client_example.py](../examples/http_client_example.py)
- **MCP Protocol Specification**: https://modelcontextprotocol.io

---

## Support

For issues, questions, or feature requests:

1. Check this guide first
2. Review example implementations
3. Enable debug logging
4. Check service health endpoint
5. Review application logs

**Happy Data Discovering! 🚀**

