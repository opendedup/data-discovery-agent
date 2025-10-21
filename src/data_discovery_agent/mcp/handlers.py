"""
MCP Request Handlers

Implements the business logic for handling MCP tool calls.
Queries Vertex AI Search and retrieves Markdown documentation from GCS.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from google.cloud import storage
from datetime import datetime, timezone

from ..clients.vertex_search_client import VertexSearchClient
from ..models.search_models import SearchRequest, SortOrder
from ..schemas.asset_schema import (
    DiscoveredAssetDict,
    SchemaFieldDict,
    LabelDict,
    LineageDict,
)
from .config import MCPConfig
from .tools import format_tool_response, format_error_response

logger = logging.getLogger(__name__)


class MCPHandlers:
    """
    Handlers for MCP tool requests.
    
    Orchestrates queries to Vertex AI Search and retrieves
    Markdown documentation from GCS.
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
            config: MCP configuration
            vertex_client: Vertex AI Search client
            storage_client: GCS storage client
        """
        self.config = config
        self.vertex_client = vertex_client
        self.storage_client = storage_client
        self.reports_bucket = storage_client.bucket(config.reports_bucket)
        
        logger.info("Initialized MCP handlers")
    
    async def handle_query_data_assets(
        self,
        arguments: Dict[str, Any],
    ) -> List[Any]:
        """
        Handle query_data_assets tool call.
        
        Searches Vertex AI Search for matching assets and retrieves
        their Markdown documentation.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            List of TextContent objects
        """
        try:
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
                page_size=min(
                    arguments.get("page_size", self.config.default_page_size),
                    self.config.max_page_size
                ),
                page_token=arguments.get("page_token"),
                include_full_content=arguments.get("include_full_content", True),
            )
            
            logger.info(f"Executing search: query='{search_request.query}'")
            
            # Execute search (run in thread pool to avoid blocking async event loop)
            import asyncio
            logger.info("About to get event loop...")
            loop = asyncio.get_running_loop()  # Use get_running_loop() for async context
            logger.info("Got event loop, submitting search to thread pool...")
            
            search_response = await loop.run_in_executor(
                None,  # Use default ThreadPoolExecutor
                lambda: self.vertex_client.search(
                    request=search_request,
                    timeout=self.config.query_timeout,
                ),
            )
            
            logger.info(
                f"Search completed: found {len(search_response.results)} results "
                f"in {search_response.query_time_ms:.0f}ms"
            )
            
            # Check output format preference
            output_format = arguments.get("output_format", "markdown")
            
            # Build response based on format
            if output_format == "json":
                response_data = await self._format_search_results_json(
                    search_response,
                    include_full_content=search_request.include_full_content,
                )
                return format_tool_response(json.dumps(response_data, indent=2))
            else:
                # Default to markdown
                if not search_response.results:
                    response_md = self._format_no_results_response(search_request)
                else:
                    response_md = await self._format_search_results(
                        search_response,
                        include_full_content=search_request.include_full_content,
                    )
                
                return format_tool_response(response_md)
            
        except Exception as e:
            logger.error(f"Error handling query_data_assets: {e}", exc_info=True)
            return format_error_response(str(e), "query_data_assets")
    
    async def handle_get_asset_details(
        self,
        arguments: Dict[str, Any],
    ) -> List[Any]:
        """
        Handle get_asset_details tool call.
        
        Retrieves full Markdown documentation for a specific asset.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            List of TextContent objects
        """
        try:
            project_id = arguments["project_id"]
            dataset_id = arguments["dataset_id"]
            table_id = arguments["table_id"]
            
            logger.info(f"Getting asset details: {project_id}.{dataset_id}.{table_id}")
            
            # Fetch markdown from GCS
            markdown_content = await self._fetch_markdown_from_gcs(
                dataset_id=dataset_id,
                table_id=table_id,
            )
            
            if not markdown_content:
                # Try searching for the asset
                search_request = SearchRequest(
                    query=f"{dataset_id}.{table_id}",
                    project_id=project_id,
                    dataset_id=dataset_id,
                    page_size=1,
                    include_full_content=True,
                )
                
                # Run search in thread pool to avoid blocking event loop
                import asyncio
                loop = asyncio.get_event_loop()
                search_response = await loop.run_in_executor(
                    None,
                    lambda: self.vertex_client.search(search_request),
                )
                
                if search_response.results:
                    result = search_response.results[0]
                    if result.full_content:
                        markdown_content = result.full_content
                    elif result.report_link:
                        # Try fetching from report link
                        markdown_content = await self._fetch_markdown_from_uri(
                            result.report_link
                        )
                
                if not markdown_content:
                    return format_error_response(
                        f"Asset not found: {project_id}.{dataset_id}.{table_id}",
                        "get_asset_details"
                    )
            
            logger.info(f"Retrieved asset documentation ({len(markdown_content)} chars)")
            
            return format_tool_response(markdown_content)
            
        except Exception as e:
            logger.error(f"Error handling get_asset_details: {e}", exc_info=True)
            return format_error_response(str(e), "get_asset_details")
    
    async def handle_get_datasets_for_query_generation(
        self,
        arguments: Dict[str, Any],
    ) -> List[Any]:
        """
        Handle get_datasets_for_query_generation tool call.
        
        Searches for BigQuery datasets and returns structured metadata
        in the format required by the Query Generation Agent.
        
        Args:
            arguments: Tool arguments (same as query_data_assets)
            
        Returns:
            List of TextContent objects containing JSON data
        """
        try:
            # Build search request (similar to query_data_assets)
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
                page_size=min(
                    arguments.get("page_size", self.config.default_page_size),
                    self.config.max_page_size
                ),
                page_token=arguments.get("page_token"),
                include_full_content=True,  # Always include full content for query generation
            )
            
            logger.info(
                f"Executing search for query generation: query='{search_request.query}'"
            )
            
            # Execute search in thread pool
            import asyncio
            loop = asyncio.get_running_loop()
            
            search_response = await loop.run_in_executor(
                None,
                lambda: self.vertex_client.search(
                    request=search_request,
                    timeout=self.config.query_timeout,
                ),
            )
            
            logger.info(
                f"Search completed: found {len(search_response.results)} results "
                f"in {search_response.query_time_ms:.0f}ms"
            )
            
            # Format results for query generation
            datasets = await self._format_for_query_generation(search_response)
            
            # Build response
            response_data = {
                "query": search_response.query,
                "total_count": len(datasets),
                "datasets": datasets,
                "has_more_results": search_response.has_more_results,
                "next_page_token": search_response.next_page_token,
            }
            
            return format_tool_response(json.dumps(response_data, indent=2))
            
        except Exception as e:
            logger.error(
                f"Error handling get_datasets_for_query_generation: {e}", 
                exc_info=True
            )
            return format_error_response(str(e), "get_datasets_for_query_generation")
    
    async def handle_list_datasets(
        self,
        arguments: Dict[str, Any],
    ) -> List[Any]:
        """
        Handle list_datasets tool call.
        
        Lists all datasets with summary information. Supports pagination.
        
        Args:
            arguments: Tool arguments including:
                - project_id: GCP project ID (optional)
                - include_table_counts: Include table counts (default: True)
                - include_costs: Include cost estimates (default: True)
                - page_size: Number of results per page (default: 50)
                - page_token: Token for next page (optional)
            
        Returns:
            List of TextContent objects
        """
        try:
            project_id = arguments.get("project_id", self.config.project_id)
            include_table_counts = arguments.get("include_table_counts", True)
            include_costs = arguments.get("include_costs", True)
            page_size = arguments.get("page_size", 50)
            page_token = arguments.get("page_token")
            
            logger.info(f"Listing datasets for project: {project_id} (page_size={page_size})")
            
            # Search for all assets and group by dataset
            search_request = SearchRequest(
                query="",  # Empty string returns all results (wildcard)
                project_id=project_id,
                page_size=min(page_size, self.config.max_page_size),
                page_token=page_token,
                include_full_content=False,
            )
            
            # Run search in thread pool to avoid blocking event loop
            import asyncio
            loop = asyncio.get_event_loop()
            search_response = await loop.run_in_executor(
                None,
                lambda: self.vertex_client.search(search_request),
            )
            
            # Group results by dataset
            datasets = self._group_by_dataset(
                search_response.results,
                include_table_counts=include_table_counts,
                include_costs=include_costs,
            )
            
            # Format response with pagination info
            response_md = self._format_datasets_list(
                datasets, 
                project_id,
                search_response=search_response
            )
            
            logger.info(
                f"Listed {len(datasets)} datasets "
                f"(has_more={search_response.has_more_results})"
            )
            
            return format_tool_response(response_md)
            
        except Exception as e:
            logger.error(f"Error handling list_datasets: {e}", exc_info=True)
            return format_error_response(str(e), "list_datasets")
    
    async def _format_search_results(
        self,
        search_response: Any,
        include_full_content: bool = True,
    ) -> str:
        """
        Format search results as Markdown.
        
        Args:
            search_response: SearchResponse object
            include_full_content: Whether to include full markdown content
            
        Returns:
            Formatted markdown string
        """
        lines = []
        
        # Header
        lines.append(f"# Search Results: {search_response.query}")
        lines.append("")
        lines.append(f"Found **{len(search_response.results)}** matching assets")
        lines.append(f"*(Query time: {search_response.query_time_ms:.0f}ms)*")
        lines.append("")
        
        if search_response.filters_applied:
            lines.append(f"**Filters**: `{search_response.filters_applied}`")
            lines.append("")
        
        lines.append("---")
        lines.append("")
        
        # Results
        for i, result in enumerate(search_response.results, 1):
            lines.append(f"## {i}. {result.title}")
            lines.append("")
            
            # Metadata summary
            metadata = result.metadata
            
            # Basic info
            info_items = []
            if metadata.asset_type:
                info_items.append(f"**Type**: {metadata.asset_type}")
            if metadata.row_count is not None:
                info_items.append(f"**Rows**: {metadata.row_count:,}")
            if metadata.size_bytes is not None:
                size_gb = metadata.size_bytes / (1024**3)
                info_items.append(f"**Size**: {size_gb:.2f} GB")
            if metadata.monthly_cost_usd is not None:
                info_items.append(f"**Cost**: ${metadata.monthly_cost_usd:.2f}/mo")
            
            if info_items:
                lines.append(" | ".join(info_items))
                lines.append("")
            
            # Security badges
            badges = []
            if metadata.has_pii:
                badges.append("🔒 PII")
            if metadata.has_phi:
                badges.append("🏥 PHI")
            if metadata.environment:
                badges.append(f"🌍 {metadata.environment.upper()}")
            
            if badges:
                lines.append(" ".join(badges))
                lines.append("")
            
            # Snippet
            if result.snippet:
                lines.append("### Description")
                lines.append("")
                lines.append(result.snippet)
                lines.append("")
            
            # Links
            if self.config.enable_console_links and result.console_link:
                lines.append(f"[Open in BigQuery Console]({result.console_link})")
                lines.append("")
            
            # Full content
            if include_full_content:
                if result.full_content:
                    lines.append("### Full Documentation")
                    lines.append("")
                    lines.append(result.full_content)
                    lines.append("")
                elif result.report_link:
                    # Try to fetch from GCS
                    try:
                        markdown = await self._fetch_markdown_from_uri(result.report_link)
                        if markdown:
                            lines.append("### Full Documentation")
                            lines.append("")
                            lines.append(markdown)
                            lines.append("")
                    except Exception as e:
                        logger.warning(f"Failed to fetch markdown from {result.report_link}: {e}")
            
            lines.append("---")
            lines.append("")
        
        # Pagination info
        if search_response.has_more_results:
            lines.append("📄 **More results available!**")
            lines.append("")
            lines.append(f"To get the next page, use `page_token`: `{search_response.next_page_token}`")
            lines.append("")
        
        return "\n".join(lines)
    
    async def _format_search_results_json(
        self,
        search_response: Any,
        include_full_content: bool = True,
    ) -> Dict[str, Any]:
        """
        Format search results as JSON.
        
        Args:
            search_response: SearchResponse object
            include_full_content: Whether to include full markdown content
            
        Returns:
            Dictionary with structured search results
        """
        results = []
        
        for result in search_response.results:
            metadata = result.metadata
            
            # Build result object
            result_obj = {
                "id": result.id,
                "title": result.title,
                "score": result.score,
                "metadata": {
                    "project_id": metadata.project_id,
                    "dataset_id": metadata.dataset_id,
                    "table_id": metadata.table_id,
                    "asset_type": metadata.asset_type,
                    "row_count": metadata.row_count,
                    "size_bytes": metadata.size_bytes,
                    "column_count": metadata.column_count,
                    "has_pii": metadata.has_pii,
                    "has_phi": metadata.has_phi,
                    "encryption_type": metadata.encryption_type,
                    "monthly_cost_usd": metadata.monthly_cost_usd,
                    "created_at": metadata.created_at,
                    "last_modified": metadata.last_modified,
                    "last_accessed": metadata.last_accessed,
                    "indexed_at": metadata.indexed_at,
                    "completeness_score": metadata.completeness_score,
                    "freshness_score": metadata.freshness_score,
                    "owner_email": metadata.owner_email,
                    "team": metadata.team,
                    "environment": metadata.environment,
                    "tags": metadata.tags,
                },
                "snippet": result.snippet,
            }
            
            # Add optional fields
            if self.config.enable_console_links and result.console_link:
                result_obj["console_link"] = result.console_link
            
            if result.report_link:
                result_obj["report_link"] = result.report_link
            
            # Add full content if requested
            if include_full_content:
                if result.full_content:
                    result_obj["full_content"] = result.full_content
                elif result.report_link:
                    # Try to fetch from GCS
                    try:
                        markdown = await self._fetch_markdown_from_uri(result.report_link)
                        if markdown:
                            result_obj["full_content"] = markdown
                    except Exception as e:
                        logger.warning(f"Failed to fetch markdown from {result.report_link}: {e}")
            
            results.append(result_obj)
        
        # Build response object
        return {
            "query": search_response.query,
            "filters_applied": search_response.filters_applied,  # Already a dict now
            "total_count": search_response.total_count,
            "results_count": len(results),
            "query_time_ms": search_response.query_time_ms,
            "page_size": search_response.page_size,
            "has_more_results": search_response.has_more_results,
            "next_page_token": search_response.next_page_token,
            "results": results,
        }
    
    async def _format_for_query_generation(
        self,
        search_response: Any,
    ) -> List[DiscoveredAssetDict]:
        """
        Format search results for Query Generation Agent.
        
        Transforms search results into the BigQuery writer schema format,
        which is the canonical format for discovered assets.
        
        Args:
            search_response: SearchResponse object
            
        Returns:
            List of DiscoveredAssetDict objects matching BigQuery schema
        """
        datasets = []
        run_timestamp = datetime.now(timezone.utc).isoformat()
        
        for result in search_response.results:
            metadata = result.metadata
            
            # Fetch full markdown content if not already included
            full_markdown = result.full_content
            if not full_markdown and result.report_link:
                try:
                    full_markdown = await self._fetch_markdown_from_uri(result.report_link)
                except Exception as e:
                    logger.warning(
                        f"Failed to fetch markdown for {metadata.table_id}: {e}"
                    )
                    full_markdown = result.snippet or ""
            
            # Parse schema fields from markdown or metadata
            schema_fields = await self._extract_schema_fields(
                full_markdown, 
                metadata
            )
            
            # Parse labels from metadata if available
            labels: List[LabelDict] = []
            if hasattr(metadata, 'labels') and metadata.labels:
                if isinstance(metadata.labels, dict):
                    labels = [
                        LabelDict(key=k, value=v) 
                        for k, v in metadata.labels.items()
                    ]
            
            # Parse tags
            tags = metadata.tags if metadata.tags else []
            
            # Build dataset object in BigQuery schema format
            asset_type = metadata.asset_type or "TABLE"
            dataset_obj: DiscoveredAssetDict = {
                # Core identifiers
                "table_id": metadata.table_id or "",
                "project_id": metadata.project_id or "",
                "dataset_id": metadata.dataset_id or "",
                
                # Metadata
                "description": result.snippet or full_markdown[:500] if full_markdown else "",
                "table_type": asset_type,
                "asset_type": asset_type,  # For backwards compatibility with query generation agent
                
                # Timestamps (ISO format)
                "created": metadata.created_at if metadata.created_at else None,
                "last_modified": metadata.last_modified if metadata.last_modified else None,
                "last_accessed": metadata.last_accessed if metadata.last_accessed else None,
                
                # Statistics
                "row_count": metadata.row_count,
                "column_count": metadata.column_count,
                "size_bytes": metadata.size_bytes,
                
                # Security & Governance
                "has_pii": metadata.has_pii or False,
                "has_phi": metadata.has_phi or False,
                "environment": metadata.environment,
                
                # Labels and tags
                "labels": labels,
                
                # Schema
                "schema": schema_fields,
                
                # AI-generated insights (empty for now, can be populated later)
                "analytical_insights": [],
                
                # Lineage (empty for now, would need separate lineage query)
                "lineage": [],
                
                # Profiling (empty for now, would need separate profiling)
                "column_profiles": [],
                
                # Metrics
                "key_metrics": self._extract_key_metrics(metadata),
                
                # Run metadata
                "run_timestamp": run_timestamp,
                "insert_timestamp": "AUTO",
                
                # Additional fields for MCP/query generation
                "full_markdown": full_markdown or "",
                "owner_email": metadata.owner_email,
                "tags": tags,
            }
            
            datasets.append(dataset_obj)
        
        return datasets
    
    def _extract_key_metrics(self, metadata: Any) -> List[Dict[str, str]]:
        """
        Extract key metrics from metadata.
        
        Args:
            metadata: Asset metadata object
            
        Returns:
            List of key metric dictionaries
        """
        metrics = []
        
        if hasattr(metadata, 'completeness_score') and metadata.completeness_score is not None:
            metrics.append({
                "metric_name": "completeness_score",
                "metric_value": str(metadata.completeness_score)
            })
        
        if hasattr(metadata, 'freshness_score') and metadata.freshness_score is not None:
            metrics.append({
                "metric_name": "freshness_score",
                "metric_value": str(metadata.freshness_score)
            })
        
        if hasattr(metadata, 'monthly_cost_usd') and metadata.monthly_cost_usd is not None:
            metrics.append({
                "metric_name": "monthly_cost_usd",
                "metric_value": str(metadata.monthly_cost_usd)
            })
        
        return metrics
    
    async def _extract_schema_fields(
        self,
        markdown_content: Optional[str],
        metadata: Any,
    ) -> List[SchemaFieldDict]:
        """
        Extract schema fields from markdown documentation.
        
        Parses the Schema section of the markdown documentation to extract
        field names, types, and descriptions.
        
        Args:
            markdown_content: Full markdown documentation
            metadata: Asset metadata
            
        Returns:
            List of SchemaFieldDict objects matching BigQuery schema
        """
        schema_fields: List[SchemaFieldDict] = []
        
        if not markdown_content:
            return schema_fields
        
        try:
            # Look for Schema section in markdown
            # Common format: ## Schema or ### Schema
            lines = markdown_content.split('\n')
            in_schema_section = False
            in_table = False
            
            for i, line in enumerate(lines):
                # Detect schema section header
                if line.strip().lower() in ['## schema', '### schema', '#### schema']:
                    in_schema_section = True
                    continue
                
                # Exit schema section on next header
                if in_schema_section and line.strip().startswith('#'):
                    break
                
                # Look for table header (markdown table format)
                if in_schema_section and '|' in line:
                    if 'Field' in line or 'Column' in line or 'Name' in line:
                        in_table = True
                        continue
                    
                    # Skip separator line
                    if in_table and line.strip().startswith('|---') or line.strip().startswith('| ---'):
                        continue
                    
                    # Parse table row
                    if in_table:
                        parts = [p.strip() for p in line.split('|')]
                        # Remove empty first/last elements from split
                        parts = [p for p in parts if p]
                        
                        if len(parts) >= 2:
                            field_name = parts[0].strip()
                            field_type = parts[1].strip() if len(parts) > 1 else "STRING"
                            field_mode = parts[2].strip() if len(parts) > 2 else None
                            field_desc = parts[3].strip() if len(parts) > 3 else ""
                            
                            # Skip if looks like header row
                            if field_name.lower() in ['field', 'column', 'name']:
                                continue
                            
                            # If only 3 columns, assume format is: name | type | description
                            if len(parts) == 3:
                                field_mode = None
                                field_desc = parts[2].strip()
                            
                            schema_fields.append(SchemaFieldDict(
                                name=field_name,
                                type=field_type,
                                mode=field_mode,
                                description=field_desc,
                                sample_values=None  # Could be extracted later
                            ))
            
            logger.debug(
                f"Extracted {len(schema_fields)} schema fields from markdown"
            )
            
        except Exception as e:
            logger.warning(f"Error extracting schema fields: {e}")
        
        # If no fields extracted, return at least empty structure
        if not schema_fields:
            logger.warning(
                f"No schema fields extracted for {metadata.table_id}, "
                "returning empty schema"
            )
        
        return schema_fields
    
    def _format_no_results_response(
        self,
        search_request: SearchRequest,
    ) -> str:
        """
        Format response when no results are found.
        
        Args:
            search_request: Original search request
            
        Returns:
            Formatted markdown string
        """
        lines = []
        lines.append(f"# Search Results: {search_request.query}")
        lines.append("")
        lines.append("No matching assets found.")
        lines.append("")
        lines.append("## Suggestions")
        lines.append("")
        lines.append("- Try a broader search query")
        lines.append("- Check your filter parameters")
        lines.append("- Verify the project and dataset names")
        lines.append("- Try searching without filters first")
        lines.append("")
        
        return "\n".join(lines)
    
    async def _fetch_markdown_from_gcs(
        self,
        dataset_id: str,
        table_id: str,
    ) -> Optional[str]:
        """
        Fetch Markdown report from GCS.
        
        Args:
            dataset_id: Dataset ID
            table_id: Table ID
            
        Returns:
            Markdown content or None if not found
        """
        try:
            blob_path = f"{dataset_id}/{table_id}.md"
            blob = self.reports_bucket.blob(blob_path)
            
            if not blob.exists():
                logger.debug(f"Markdown not found in GCS: {blob_path}")
                return None
            
            content = blob.download_as_text(encoding='utf-8')
            logger.debug(f"Fetched markdown from GCS: {blob_path} ({len(content)} chars)")
            
            return content
            
        except Exception as e:
            logger.warning(f"Error fetching markdown from GCS: {e}")
            return None
    
    async def _fetch_markdown_from_uri(
        self,
        gcs_uri: str,
    ) -> Optional[str]:
        """
        Fetch Markdown from GCS URI.
        
        Args:
            gcs_uri: GCS URI (gs://bucket/path)
            
        Returns:
            Markdown content or None if not found
        """
        try:
            # Parse GCS URI
            if not gcs_uri.startswith("gs://"):
                return None
            
            parts = gcs_uri[5:].split("/", 1)
            if len(parts) != 2:
                return None
            
            bucket_name, blob_path = parts
            
            # Run GCS operations in thread pool to avoid blocking event loop
            import asyncio
            loop = asyncio.get_event_loop()
            
            def fetch_blob_content():
                bucket = self.storage_client.bucket(bucket_name)
                blob = bucket.blob(blob_path)
                
                if not blob.exists():
                    return None
                
                return blob.download_as_text(encoding='utf-8')
            
            content = await loop.run_in_executor(None, fetch_blob_content)
            
            return content
            
        except Exception as e:
            logger.warning(f"Error fetching markdown from URI {gcs_uri}: {e}")
            return None
    
    def _group_by_dataset(
        self,
        results: List[Any],
        include_table_counts: bool = True,
        include_costs: bool = True,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Group search results by dataset.
        
        Args:
            results: List of SearchResultItem objects
            include_table_counts: Include table counts
            include_costs: Include cost estimates
            
        Returns:
            Dictionary of dataset summaries
        """
        datasets: Dict[str, Dict[str, Any]] = {}
        
        for result in results:
            dataset_id = result.metadata.dataset_id
            if not dataset_id:
                continue
            
            if dataset_id not in datasets:
                datasets[dataset_id] = {
                    "dataset_id": dataset_id,
                    "project_id": result.metadata.project_id,
                    "table_count": 0,
                    "total_rows": 0,
                    "total_size_bytes": 0,
                    "total_cost": 0.0,
                    "has_pii": False,
                    "has_phi": False,
                    "tables": [],
                }
            
            ds = datasets[dataset_id]
            
            # Update counts
            if include_table_counts:
                ds["table_count"] += 1
                ds["tables"].append(result.metadata.table_id)
            
            # Update metrics
            if result.metadata.row_count:
                ds["total_rows"] += result.metadata.row_count
            
            if result.metadata.size_bytes:
                ds["total_size_bytes"] += result.metadata.size_bytes
            
            if include_costs and result.metadata.monthly_cost_usd:
                ds["total_cost"] += result.metadata.monthly_cost_usd
            
            # Update flags
            if result.metadata.has_pii:
                ds["has_pii"] = True
            if result.metadata.has_phi:
                ds["has_phi"] = True
        
        return datasets
    
    def _format_datasets_list(
        self,
        datasets: Dict[str, Dict[str, Any]],
        project_id: str,
        search_response: Optional[Any] = None,
    ) -> str:
        """
        Format datasets list as Markdown with pagination info.
        
        Args:
            datasets: Dataset summaries
            project_id: Project ID
            search_response: Optional search response with pagination info
            
        Returns:
            Formatted markdown string
        """
        lines = []
        
        lines.append(f"# Datasets in Project: {project_id}")
        lines.append("")
        lines.append(f"Found **{len(datasets)}** datasets")
        
        # Add pagination info if available
        if search_response:
            lines.append("")
            lines.append(f"*Results based on {len(search_response.results)} assets*")
            if search_response.has_more_results:
                lines.append("")
                lines.append("📄 **More results available!**")
                lines.append(f"To get the next page, use `page_token`: `{search_response.next_page_token}`")
        
        lines.append("")
        lines.append("---")
        lines.append("")
        
        # Sort by dataset ID
        for dataset_id in sorted(datasets.keys()):
            ds = datasets[dataset_id]
            
            lines.append(f"## {dataset_id}")
            lines.append("")
            
            # Metrics
            size_gb = ds["total_size_bytes"] / (1024**3)
            
            metrics = [
                f"**Tables**: {ds['table_count']}",
                f"**Rows**: {ds['total_rows']:,}",
                f"**Size**: {size_gb:.2f} GB",
            ]
            
            if ds["total_cost"] > 0:
                metrics.append(f"**Cost**: ${ds['total_cost']:.2f}/mo")
            
            lines.append(" | ".join(metrics))
            lines.append("")
            
            # Security
            if ds["has_pii"] or ds["has_phi"]:
                badges = []
                if ds["has_pii"]:
                    badges.append("🔒 Contains PII")
                if ds["has_phi"]:
                    badges.append("🏥 Contains PHI")
                lines.append(" ".join(badges))
                lines.append("")
            
            lines.append("---")
            lines.append("")
        
        return "\n".join(lines)

