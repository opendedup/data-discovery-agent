"""
MCP Tool Definitions

Defines the MCP tools exposed by the service for querying
indexed metadata.
"""

from typing import Any, Dict, List
from mcp.types import Tool, TextContent


# Tool name constants
QUERY_DATA_ASSETS_TOOL = "query_data_assets"
GET_ASSET_DETAILS_TOOL = "get_asset_details"
LIST_DATASETS_TOOL = "list_datasets"
GET_DATASETS_FOR_QUERY_GENERATION_TOOL = "get_datasets_for_query_generation"


def get_available_tools() -> List[Tool]:
    """
    Get list of available MCP tools.
    
    Returns:
        List of Tool objects
    """
    return [
        Tool(
            name=QUERY_DATA_ASSETS_TOOL,
            description=(
                "Search for BigQuery tables, views, and datasets using natural language queries. "
                "Returns comprehensive metadata documentation including schema, security, cost, "
                "quality metrics, and more. Use this to find tables based on their content, "
                "purpose, or characteristics. Supports filtering by project, dataset, data sensitivity, "
                "size, cost, and other attributes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Natural language search query. Examples: "
                            "'tables with PII data', "
                            "'customer analytics tables', "
                            "'tables modified in the last week', "
                            "'expensive tables with high query costs'"
                        )
                    },
                    "project_id": {
                        "type": "string",
                        "description": "Filter by specific GCP project ID"
                    },
                    "dataset_id": {
                        "type": "string",
                        "description": "Filter by specific BigQuery dataset"
                    },
                    "has_pii": {
                        "type": "boolean",
                        "description": "Filter tables containing PII (Personally Identifiable Information)"
                    },
                    "has_phi": {
                        "type": "boolean",
                        "description": "Filter tables containing PHI (Protected Health Information)"
                    },
                    "environment": {
                        "type": "string",
                        "description": "Filter by environment (e.g., 'production', 'staging', 'development')"
                    },
                    "min_row_count": {
                        "type": "integer",
                        "description": "Filter tables with at least this many rows"
                    },
                    "max_row_count": {
                        "type": "integer",
                        "description": "Filter tables with at most this many rows"
                    },
                    "min_cost": {
                        "type": "number",
                        "description": "Filter tables with monthly cost >= this value (USD)"
                    },
                    "max_cost": {
                        "type": "number",
                        "description": "Filter tables with monthly cost <= this value (USD)"
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Sort results by field (e.g., 'row_count', 'size_bytes', 'monthly_cost_usd', 'last_modified_timestamp')"
                    },
                    "sort_order": {
                        "type": "string",
                        "enum": ["asc", "desc"],
                        "description": "Sort order: 'asc' (ascending) or 'desc' (descending)",
                        "default": "desc"
                    },
                    "page_size": {
                        "type": "integer",
                        "description": "Number of results to return (max 50)",
                        "minimum": 1,
                        "maximum": 50,
                        "default": 10
                    },
                    "page_token": {
                        "type": "string",
                        "description": "Token from previous response to get next page of results"
                    },
                    "include_full_content": {
                        "type": "boolean",
                        "description": "Include full Markdown documentation in response",
                        "default": True
                    },
                    "output_format": {
                        "type": "string",
                        "enum": ["markdown", "json"],
                        "description": "Output format: 'markdown' (default, human-readable) or 'json' (structured data)",
                        "default": "markdown"
                    }
                },
                "required": ["query"]
            }
        ),
        
        Tool(
            name=GET_ASSET_DETAILS_TOOL,
            description=(
                "Get detailed metadata documentation for a specific BigQuery table or view. "
                "Returns the complete Markdown report with schema, security, lineage, cost analysis, "
                "quality metrics, and usage patterns. Use this when you know the exact table name "
                "and want comprehensive documentation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "GCP project ID"
                    },
                    "dataset_id": {
                        "type": "string",
                        "description": "BigQuery dataset ID"
                    },
                    "table_id": {
                        "type": "string",
                        "description": "BigQuery table or view ID"
                    },
                    "include_lineage": {
                        "type": "boolean",
                        "description": "Include lineage information (upstream and downstream dependencies)",
                        "default": True
                    },
                    "include_usage": {
                        "type": "boolean",
                        "description": "Include usage statistics and patterns",
                        "default": True
                    }
                },
                "required": ["project_id", "dataset_id", "table_id"]
            }
        ),
        
        Tool(
            name=LIST_DATASETS_TOOL,
            description=(
                "List all BigQuery datasets in a project with summary information. "
                "Returns dataset-level metadata including table counts, total size, "
                "cost estimates, and data classification. Use this to explore what "
                "datasets are available in a project. Supports pagination for large result sets."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "GCP project ID (optional - uses default project if not specified)"
                    },
                    "include_table_counts": {
                        "type": "boolean",
                        "description": "Include count of tables in each dataset",
                        "default": True
                    },
                    "include_costs": {
                        "type": "boolean",
                        "description": "Include cost estimates for each dataset",
                        "default": True
                    },
                    "page_size": {
                        "type": "integer",
                        "description": "Number of results to return per page (max 50)",
                        "minimum": 1,
                        "maximum": 50,
                        "default": 50
                    },
                    "page_token": {
                        "type": "string",
                        "description": "Token from previous response to get next page of results"
                    }
                },
                "required": []
            }
        ),
        
        Tool(
            name=GET_DATASETS_FOR_QUERY_GENERATION_TOOL,
            description=(
                "Search for BigQuery datasets and return structured metadata in the BigQuery "
                "writer schema format. Returns comprehensive JSON data including schema fields, "
                "table metadata, security classifications, lineage, profiling, and complete "
                "documentation. Output matches the canonical DiscoveredAssetDict schema used "
                "by the BigQuery writer. Use this when you need to prepare dataset metadata "
                "for automated query generation or other downstream processing."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Natural language search query. Examples: "
                            "'tables with PII data', "
                            "'customer analytics tables', "
                            "'tables modified in the last week', "
                            "'expensive tables with high query costs'"
                        )
                    },
                    "project_id": {
                        "type": "string",
                        "description": "Filter by specific GCP project ID"
                    },
                    "dataset_id": {
                        "type": "string",
                        "description": "Filter by specific BigQuery dataset"
                    },
                    "has_pii": {
                        "type": "boolean",
                        "description": "Filter tables containing PII (Personally Identifiable Information)"
                    },
                    "has_phi": {
                        "type": "boolean",
                        "description": "Filter tables containing PHI (Protected Health Information)"
                    },
                    "environment": {
                        "type": "string",
                        "description": "Filter by environment (e.g., 'production', 'staging', 'development')"
                    },
                    "min_row_count": {
                        "type": "integer",
                        "description": "Filter tables with at least this many rows"
                    },
                    "max_row_count": {
                        "type": "integer",
                        "description": "Filter tables with at most this many rows"
                    },
                    "min_cost": {
                        "type": "number",
                        "description": "Filter tables with monthly cost >= this value (USD)"
                    },
                    "max_cost": {
                        "type": "number",
                        "description": "Filter tables with monthly cost <= this value (USD)"
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Sort results by field (e.g., 'row_count', 'size_bytes', 'monthly_cost_usd', 'last_modified_timestamp')"
                    },
                    "sort_order": {
                        "type": "string",
                        "enum": ["asc", "desc"],
                        "description": "Sort order: 'asc' (ascending) or 'desc' (descending)",
                        "default": "desc"
                    },
                    "page_size": {
                        "type": "integer",
                        "description": "Number of results to return (max 50)",
                        "minimum": 1,
                        "maximum": 50,
                        "default": 10
                    },
                    "page_token": {
                        "type": "string",
                        "description": "Token from previous response to get next page of results"
                    }
                },
                "required": ["query"]
            }
        ),
    ]


def format_tool_response(
    content: str,
    is_error: bool = False,
) -> List[TextContent]:
    """
    Format tool response as MCP TextContent.
    
    Args:
        content: Response content (usually Markdown)
        is_error: Whether this is an error response
        
    Returns:
        List of TextContent objects
    """
    return [
        TextContent(
            type="text",
            text=content
        )
    ]


def format_error_response(
    error_message: str,
    tool_name: str,
) -> List[TextContent]:
    """
    Format error response for MCP.
    
    Args:
        error_message: Error message
        tool_name: Name of the tool that encountered the error
        
    Returns:
        List of TextContent objects
    """
    formatted_error = f"""# Error: {tool_name}

An error occurred while processing your request:

```
{error_message}
```

Please check your query parameters and try again. If the problem persists, contact support.
"""
    
    return format_tool_response(formatted_error, is_error=True)


def validate_query_params(
    arguments: Dict[str, Any],
    tool_name: str,
) -> None:
    """
    Validate query parameters for a tool.
    
    Args:
        arguments: Tool arguments to validate
        tool_name: Name of the tool
        
    Raises:
        ValueError: If validation fails
    """
    if tool_name == QUERY_DATA_ASSETS_TOOL:
        # Validate query
        if not arguments.get("query"):
            raise ValueError("'query' parameter is required")
        
        # Validate page_size
        page_size = arguments.get("page_size", 10)
        if not isinstance(page_size, int) or page_size < 1 or page_size > 50:
            raise ValueError("'page_size' must be between 1 and 50")
        
        # Validate sort_order
        sort_order = arguments.get("sort_order", "desc")
        if sort_order not in ["asc", "desc"]:
            raise ValueError("'sort_order' must be 'asc' or 'desc'")
    
    elif tool_name == GET_ASSET_DETAILS_TOOL:
        # Validate required fields
        required = ["project_id", "dataset_id", "table_id"]
        for field in required:
            if not arguments.get(field):
                raise ValueError(f"'{field}' parameter is required")
    
    elif tool_name == LIST_DATASETS_TOOL:
        # No required parameters, just validate types if provided
        pass
    
    elif tool_name == GET_DATASETS_FOR_QUERY_GENERATION_TOOL:
        # Validate query
        if not arguments.get("query"):
            raise ValueError("'query' parameter is required")
        
        # Validate page_size
        page_size = arguments.get("page_size", 10)
        if not isinstance(page_size, int) or page_size < 1 or page_size > 50:
            raise ValueError("'page_size' must be between 1 and 50")
        
        # Validate sort_order
        sort_order = arguments.get("sort_order", "desc")
        if sort_order not in ["asc", "desc"]:
            raise ValueError("'sort_order' must be 'asc' or 'desc'")
    
    else:
        raise ValueError(f"Unknown tool: {tool_name}")

