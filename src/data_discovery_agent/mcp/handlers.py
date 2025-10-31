"""
MCP Request Handlers

Implements the business logic for handling MCP tool calls.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from google.cloud import storage, bigquery

from ..clients.vertex_search_client import VertexSearchClient
from ..clients.search_planner import SearchPlanner
from ..models.search_models import SearchRequest, SortOrder
from .config import MCPConfig
from .tools import format_tool_response, format_error_response
from ..clients.schema_validator import SchemaValidator
from ..clients.prp_requirement_discovery import PRPRequirementDiscovery

logger = logging.getLogger(__name__)


class MCPHandlers:
    """
    Handlers for MCP tool requests.
    
    Orchestrates the strategy-driven discovery workflow.
    """
    
    def __init__(
        self,
        config: MCPConfig,
        vertex_client: VertexSearchClient,
        storage_client: storage.Client,
    ):
        """
        Initialize MCP handlers.
        
        Args:
            config: MCP configuration.
            vertex_client: Vertex AI Search client.
            storage_client: GCS storage client (currently unused but kept for future use).
        """
        self.config = config
        self.vertex_client = vertex_client
        self.storage_client = storage_client
        
        # Initialize the clients for the new discovery workflow
        self.search_planner = SearchPlanner(gemini_api_key=self.config.gemini_api_key)
        self.schema_validator = SchemaValidator(gemini_api_key=self.config.gemini_api_key)
        self.discovery_client = PRPRequirementDiscovery(
            vertex_client=self.vertex_client,
            search_planner=self.search_planner,
            schema_validator=self.schema_validator,
        )
        
        logger.info("Initialized MCP handlers with strategy-driven discovery components.")
    
    async def handle_query_data_assets(
        self,
        arguments: Dict[str, Any],
    ) -> List[Any]:
        """
        Handle query_data_assets tool call.
        
        Searches for BigQuery tables using natural language and filters.
        
        Args:
            arguments: Tool arguments including query, filters, pagination, etc.
            
        Returns:
            List of TextContent objects with search results
        """
        try:
            logger.info(f"Handling query_data_assets with query: {arguments.get('query')}")
            
            # Build search request
            search_request = SearchRequest(
                query=arguments["query"],
                project_id=arguments.get("project_id"),
                dataset_id=arguments.get("dataset_id"),
                has_pii=arguments.get("has_pii"),
                has_phi=arguments.get("has_phi"),
                environment=arguments.get("environment"),
                min_row_count=arguments.get("min_row_count"),
                max_row_count=arguments.get("max_row_count"),
                min_cost=arguments.get("min_cost"),
                max_cost=arguments.get("max_cost"),
                sort_by=arguments.get("sort_by"),
                sort_order=SortOrder(arguments.get("sort_order", "desc")),
                page_size=arguments.get("page_size", 10),
                page_token=arguments.get("page_token"),
            )
            
            # Execute search
            search_response = self.vertex_client.search(search_request)
            
            # Format response based on output_format
            output_format = arguments.get("output_format", "json")
            include_full_content = arguments.get("include_full_content", True)
            
            if output_format == "json":
                # Return JSON format
                response_data = {
                    "results": [
                        {
                            "id": result.id,
                            "title": result.title,
                            "score": result.score,
                            "project_id": result.metadata.project_id,
                            "dataset_id": result.metadata.dataset_id,
                            "table_id": result.metadata.table_id,
                            "description": result.metadata.description,
                            "asset_type": result.metadata.asset_type,
                            "row_count": result.metadata.row_count,
                            "size_bytes": result.metadata.size_bytes,
                            "created": result.metadata.created,
                            "last_modified": result.metadata.last_modified,
                            "has_pii": result.metadata.has_pii,
                            "has_phi": result.metadata.has_phi,
                            "schema": result.metadata.schema,
                            "snippet": result.snippet,
                        }
                        for result in search_response.results
                    ],
                    "total_count": search_response.total_count,
                    "next_page_token": search_response.next_page_token,
                    "query_time_ms": search_response.query_time_ms,
                }
                response = json.dumps(response_data, indent=2)
            else:
                # Return markdown format
                response = f"# Search Results\n\n"
                response += f"Found {len(search_response.results)} result(s) for query: **{arguments['query']}**\n\n"
                
                for i, result in enumerate(search_response.results, 1):
                    response += f"## {i}. {result.title}\n\n"
                    response += f"- **ID**: `{result.id}`\n"
                    response += f"- **Type**: {result.metadata.asset_type}\n"
                    response += f"- **Description**: {result.metadata.description or 'No description'}\n"
                    
                    # Handle potential None values for row_count and size_bytes
                    row_count = result.metadata.row_count or 0
                    size_bytes = result.metadata.size_bytes or 0
                    response += f"- **Rows**: {row_count:,} | **Size**: {size_bytes / (1024**3):.2f} GB\n"
                    
                    if result.metadata.has_pii or result.metadata.has_phi:
                        classifications = []
                        if result.metadata.has_pii:
                            classifications.append("PII")
                        if result.metadata.has_phi:
                            classifications.append("PHI")
                        response += f"- **Contains**: {', '.join(classifications)}\n"
                    
                    if include_full_content and result.metadata.schema:
                        response += f"\n**Schema** ({len(result.metadata.schema)} columns):\n"
                        for field in result.metadata.schema[:10]:  # Show first 10 columns
                            response += f"  - `{field.get('name')}` ({field.get('type')})\n"
                        if len(result.metadata.schema) > 10:
                            response += f"  - ... and {len(result.metadata.schema) - 10} more columns\n"
                    
                    response += "\n"
                
                if search_response.next_page_token:
                    response += f"\n*More results available. Use page_token: `{search_response.next_page_token}`*\n"
            
            return format_tool_response(response)
            
        except Exception as e:
            logger.error(f"Error in handle_query_data_assets: {e}", exc_info=True)
            return format_error_response(str(e), "query_data_assets")
    
    async def handle_get_asset_details(
        self,
        arguments: Dict[str, Any],
    ) -> List[Any]:
        """
        Handle get_asset_details tool call.
        
        Gets detailed metadata for a specific BigQuery table.
        
        Args:
            arguments: Tool arguments with project_id, dataset_id, table_id
            
        Returns:
            List of TextContent objects with detailed asset information
        """
        try:
            project_id = arguments["project_id"]
            dataset_id = arguments["dataset_id"]
            table_id = arguments["table_id"]
            
            logger.info(f"Getting asset details for {project_id}.{dataset_id}.{table_id}")
            
            # Search for the specific table
            search_request = SearchRequest(
                query=f"{table_id}",
                project_id=project_id,
                dataset_id=dataset_id,
                page_size=1,
            )
            
            search_response = self.vertex_client.search(search_request)
            
            if not search_response.results:
                return format_error_response(
                    f"Table not found: {project_id}.{dataset_id}.{table_id}",
                    "get_asset_details"
                )
            
            # Get the first result (should be exact match)
            result = search_response.results[0]
            asset = result.metadata
            
            # Format as detailed markdown
            response = f"""# {result.title}

**Full ID**: `{result.id}`
**Type**: {asset.asset_type}
**Description**: {asset.description or 'No description available'}

## Statistics

- **Row Count**: {asset.row_count or 0:,} rows
- **Size**: {(asset.size_bytes or 0) / (1024**3):.2f} GB
- **Created**: {asset.created or 'Unknown'}
- **Last Modified**: {asset.last_modified or 'Unknown'}

## Data Classification

- **Contains PII**: {'Yes' if asset.has_pii else 'No'}
- **Contains PHI**: {'Yes' if asset.has_phi else 'No'}
- **Environment**: {asset.environment or 'Not specified'}

## Schema

"""
            
            if asset.schema:
                response += "| Column | Type | Mode | Description |\n"
                response += "|--------|------|------|-------------|\n"
                for field in asset.schema:
                    field_name = field.get('name', 'unknown')
                    field_type = field.get('type', 'unknown')
                    field_mode = field.get('mode', 'NULLABLE')
                    field_desc = field.get('description', '')
                    response += f"| `{field_name}` | {field_type} | {field_mode} | {field_desc} |\n"
            else:
                response += "*No schema information available*\n"
            
            # Add lineage if requested
            include_lineage = arguments.get("include_lineage", True)
            if include_lineage and asset.lineage:
                response += "\n## Lineage\n\n"
                # asset.lineage is a list of dicts with 'source' and 'target' keys
                # Get the full qualified name for this asset
                asset_fqn = f"{asset.project_id}.{asset.dataset_id}.{asset.table_id}"
                
                # Filter upstream (sources) and downstream (targets)
                upstream = [rel for rel in asset.lineage if rel.get("target") == asset_fqn]
                downstream = [rel for rel in asset.lineage if rel.get("source") == asset_fqn]
                
                response += f"- **Upstream Sources**: {len(upstream)}\n"
                if upstream:
                    for rel in upstream[:5]:  # Show first 5
                        response += f"  - {rel.get('source', 'unknown')}\n"
                    if len(upstream) > 5:
                        response += f"  - ... and {len(upstream) - 5} more\n"
                
                response += f"- **Downstream Targets**: {len(downstream)}\n"
                if downstream:
                    for rel in downstream[:5]:  # Show first 5
                        response += f"  - {rel.get('target', 'unknown')}\n"
                    if len(downstream) > 5:
                        response += f"  - ... and {len(downstream) - 5} more\n"
            
            # Add usage if requested
            include_usage = arguments.get("include_usage", True)
            if include_usage and hasattr(asset, 'usage_stats'):
                response += "\n## Usage Statistics\n\n"
                response += "*Usage statistics available*\n"
            
            return format_tool_response(response)
            
        except Exception as e:
            logger.error(f"Error in handle_get_asset_details: {e}", exc_info=True)
            return format_error_response(str(e), "get_asset_details")
    
    async def handle_list_datasets(
        self,
        arguments: Dict[str, Any],
    ) -> List[Any]:
        """
        Handle list_datasets tool call.
        
        Lists all datasets in a project with summary information.
        
        Args:
            arguments: Tool arguments with optional project_id and pagination
            
        Returns:
            List of TextContent objects with dataset listing
        """
        try:
            project_id = arguments.get("project_id", self.config.gcp_project_id)
            page_size = arguments.get("page_size", 50)
            
            logger.info(f"Listing datasets for project: {project_id}")
            
            # Use BigQuery client to list datasets
            bq_client = bigquery.Client(project=project_id)
            datasets = list(bq_client.list_datasets(max_results=page_size))
            
            # Format response
            response = f"# Datasets in {project_id}\n\n"
            response += f"Found {len(datasets)} dataset(s)\n\n"
            
            for dataset_ref in datasets:
                dataset = bq_client.get_dataset(dataset_ref.dataset_id)
                response += f"## {dataset.dataset_id}\n\n"
                response += f"- **Full ID**: `{dataset.project}.{dataset.dataset_id}`\n"
                response += f"- **Location**: {dataset.location}\n"
                response += f"- **Description**: {dataset.description or 'No description'}\n"
                response += f"- **Created**: {dataset.created.strftime('%Y-%m-%d') if dataset.created else 'Unknown'}\n"
                response += f"- **Modified**: {dataset.modified.strftime('%Y-%m-%d') if dataset.modified else 'Unknown'}\n"
                
                # Count tables if requested
                if arguments.get("include_table_counts", True):
                    tables = list(bq_client.list_tables(dataset, max_results=1000))
                    response += f"- **Table Count**: {len(tables)}\n"
                
                response += "\n"
            
            return format_tool_response(response)
            
        except Exception as e:
            logger.error(f"Error in handle_list_datasets: {e}", exc_info=True)
            return format_error_response(str(e), "list_datasets")
    
    async def handle_get_datasets_for_query_generation(
        self,
        arguments: Dict[str, Any],
    ) -> List[Any]:
        """
        Handle get_datasets_for_query_generation tool call.
        
        Returns structured metadata in BigQuery writer schema format for query generation.
        
        Args:
            arguments: Tool arguments including query and filters
            
        Returns:
            List of TextContent objects with structured JSON data
        """
        try:
            logger.info(f"Handling get_datasets_for_query_generation with query: {arguments.get('query')}")
            
            # Build search request (same as query_data_assets)
            search_request = SearchRequest(
                query=arguments["query"],
                project_id=arguments.get("project_id"),
                dataset_id=arguments.get("dataset_id"),
                has_pii=arguments.get("has_pii"),
                has_phi=arguments.get("has_phi"),
                environment=arguments.get("environment"),
                min_row_count=arguments.get("min_row_count"),
                max_row_count=arguments.get("max_row_count"),
                min_cost=arguments.get("min_cost"),
                max_cost=arguments.get("max_cost"),
                sort_by=arguments.get("sort_by"),
                sort_order=SortOrder(arguments.get("sort_order", "desc")),
                page_size=arguments.get("page_size", 10),
                page_token=arguments.get("page_token"),
            )
            
            # Execute search
            search_response = self.vertex_client.search(search_request)
            
            # Format in DiscoveredAssetDict schema for query generation
            discovered_assets = []
            for result in search_response.results:
                asset = result.metadata
                asset_dict = {
                    "table_id": result.id,
                    "project_id": asset.project_id,
                    "dataset_id": asset.dataset_id,
                    "table_name": asset.table_id,
                    "display_name": result.title,
                    "description": asset.description,
                    "asset_type": asset.asset_type,
                    "schema": asset.schema or [],
                    "row_count": asset.row_count,
                    "size_bytes": asset.size_bytes,
                    "created_time": asset.created,
                    "modified_time": asset.last_modified,
                    "has_pii": asset.has_pii,
                    "has_phi": asset.has_phi,
                    "environment": asset.environment,
                    "tags": asset.tags or [],
                    "lineage": asset.lineage or {},
                    "profiling": getattr(asset, 'column_profiles', {}),
                }
                discovered_assets.append(asset_dict)
            
            response_data = {
                "discovered_assets": discovered_assets,
                "total_count": search_response.total_count,
                "next_page_token": search_response.next_page_token,
                "query": arguments["query"],
                "filters": {k: v for k, v in arguments.items() if k != "query" and v is not None},
            }
            
            response = json.dumps(response_data, indent=2)
            return format_tool_response(response)
            
        except Exception as e:
            logger.error(f"Error in handle_get_datasets_for_query_generation: {e}", exc_info=True)
            return format_error_response(str(e), "get_datasets_for_query_generation")
    
    async def handle_discover_datasets_for_prp(
        self,
        arguments: Dict[str, Any],
    ) -> List[Any]:
        """
        Handle discover_datasets_for_prp tool call.
        
        Analyzes a PRP and discovers relevant datasets using AI-powered search planning.
        
        Args:
            arguments: Tool arguments with prp_text and max_results
            
        Returns:
            List of TextContent objects with discovered datasets
        """
        try:
            prp_text = arguments["prp_text"]
            max_results = arguments.get("max_results", 10)
            
            logger.info(f"Analyzing PRP ({len(prp_text)} chars) to discover datasets")
            
            # Use search planner to generate targeted queries from PRP
            search_queries = await self.search_planner.plan_searches_from_text(prp_text)
            
            logger.info(f"Generated {len(search_queries)} search queries from PRP")
            
            # Execute all searches and collect results
            all_results = []
            for i, query in enumerate(search_queries, 1):
                logger.info(f"Executing search {i}/{len(search_queries)}: {query}")
                
                search_request = SearchRequest(
                    query=query,
                    page_size=max_results,
                )
                
                search_response = self.vertex_client.search(search_request)
                all_results.extend(search_response.results)
            
            # Deduplicate and rank results by relevance
            seen_ids = set()
            unique_results = []
            for result in all_results:
                if result.id not in seen_ids:
                    seen_ids.add(result.id)
                    unique_results.append(result)
            
            # Limit to max_results
            unique_results = unique_results[:max_results]
            
            logger.info(f"Found {len(unique_results)} unique datasets from PRP analysis")
            
            # Format as structured JSON
            discovered_datasets = []
            for result in unique_results:
                asset = result.metadata
                discovered_datasets.append({
                    "table_id": result.id,
                    "project_id": asset.project_id,
                    "dataset_id": asset.dataset_id,
                    "table_name": asset.table_id,
                    "display_name": result.title,
                    "description": asset.description,
                    "asset_type": asset.asset_type,
                    "schema": asset.schema or [],
                    "row_count": asset.row_count,
                    "size_bytes": asset.size_bytes,
                })
            
            response_data = {
                "discovered_datasets": discovered_datasets,
                "total_discovered": len(discovered_datasets),
                "search_queries_used": search_queries,
                "prp_length": len(prp_text),
            }
            
            response = json.dumps(response_data, indent=2)
            return format_tool_response(response)
            
        except Exception as e:
            logger.error(f"Error in handle_discover_datasets_for_prp: {e}", exc_info=True)
            return format_error_response(str(e), "discover_datasets_for_prp")
    
    async def handle_discover_from_prp(
        self,
        arguments: Dict[str, Any],
        request: Any = None,
    ) -> List[Any]:
        """
        Handle discover_from_prp tool call using the new strategy-driven workflow.
        
        Args:
            arguments: Tool arguments including:
                - prp_markdown: The full PRP markdown content.
                - target_schema: The JSON schema of the final target view.
                - max_results_per_query: Max results for each targeted search (default: 5).
            
        Returns:
            A list of TextContent objects containing the structured JSON response.
        """
        try:
            
            logger.debug("=" * 80)
            logger.debug(f"Received arguments for discover_from_prp: {json.dumps(arguments, indent=2)}")
            logger.debug("=" * 80)

            prp_markdown = arguments["prp_markdown"]
            target_schema = arguments["target_schema"]
            max_results_per_query = arguments.get("max_results_per_query", 5)
            
            logger.info("=" * 80)
            logger.info("NEW DISCOVER FROM PRP REQUEST RECEIVED")
            logger.info("=" * 80)
            logger.info(f"PRP length: {len(prp_markdown)} characters")
            logger.info(f"Max results per query: {max_results_per_query}")
            
            # Execute the new discovery workflow
            results = await self.discovery_client.discover_for_prp(
                prp_markdown=prp_markdown,
                target_schema=target_schema,
                max_results_per_query=max_results_per_query,
                request=request,
            )
            
            # Build the final response
            response = {
                "search_plan_results": results,
                "total_steps": len(results),
                "total_discovered": sum(len(r.get("discovered_tables", [])) for r in results)
            }
            
            logger.info("=" * 80)
            logger.info(
                f"DISCOVERY COMPLETE: {response['total_steps']} search step(s) executed, "
                f"{response['total_discovered']} total source table(s) found."
            )
            logger.info("=" * 80)
            
            response_json = json.dumps(response, indent=2)
            return format_tool_response(response_json)
            
        except Exception as e:
            logger.error(f"Error in handle_discover_from_prp: {e}", exc_info=True)
            return format_error_response(str(e), "discover_from_prp")

