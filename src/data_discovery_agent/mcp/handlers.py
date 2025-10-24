"""
MCP Request Handlers

Implements the business logic for handling MCP tool calls.
"""

import json
import logging
from typing import Any, Dict, List
from google.cloud import storage

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

