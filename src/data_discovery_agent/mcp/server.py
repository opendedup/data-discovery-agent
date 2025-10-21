"""
MCP Server Implementation

Main MCP server that exposes data discovery tools via the
Model Context Protocol.
"""

import asyncio
import logging
from typing import Any, Dict, Sequence
from google.cloud import storage

from mcp.server.models import InitializationOptions
from mcp.server import Server, NotificationOptions
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from ..clients.vertex_search_client import VertexSearchClient
from .config import MCPConfig, load_config
from .tools import (
    get_available_tools,
    validate_query_params,
    QUERY_DATA_ASSETS_TOOL,
    GET_ASSET_DETAILS_TOOL,
    LIST_DATASETS_TOOL,
    GET_DATASETS_FOR_QUERY_GENERATION_TOOL,
)
from .handlers import MCPHandlers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_mcp_server(config: MCPConfig | None = None) -> Server:
    """
    Create and configure MCP server.
    
    Args:
        config: MCP configuration (loads from env if not provided)
        
    Returns:
        Configured MCP Server instance
    """
    # Load config if not provided
    if config is None:
        config = load_config()
    
    # Set logging level
    logging.getLogger().setLevel(config.log_level)
    
    # Initialize clients
    logger.info("Initializing Vertex AI Search client...")
    vertex_client = VertexSearchClient(
        project_id=config.project_id,
        location=config.vertex_location,
        datastore_id=config.vertex_datastore_id,
        reports_bucket=config.reports_bucket,
    )
    
    logger.info("Initializing GCS storage client...")
    storage_client = storage.Client(project=config.project_id)
    
    # Initialize handlers
    logger.info("Initializing MCP handlers...")
    handlers = MCPHandlers(
        config=config,
        vertex_client=vertex_client,
        storage_client=storage_client,
    )
    
    # Create MCP server
    server = Server(config.mcp_server_name)
    
    logger.info(f"MCP Server '{config.mcp_server_name}' v{config.mcp_server_version} initialized")
    
    # Register list_tools handler
    @server.list_tools()
    async def handle_list_tools() -> list[Tool]:
        """
        List available MCP tools.
        
        Returns:
            List of available tools
        """
        logger.debug("Listing available tools")
        return get_available_tools()
    
    # Register call_tool handler
    @server.call_tool()
    async def handle_call_tool(
        name: str,
        arguments: Dict[str, Any] | None,
    ) -> Sequence[TextContent]:
        """
        Handle tool invocation.
        
        Args:
            name: Tool name
            arguments: Tool arguments
            
        Returns:
            Sequence of TextContent responses
        """
        logger.info(f"Tool called: {name}")
        
        # Default to empty dict if no arguments
        if arguments is None:
            arguments = {}
        
        try:
            # Validate parameters
            validate_query_params(arguments, name)
            
            # Route to appropriate handler
            if name == QUERY_DATA_ASSETS_TOOL:
                return await handlers.handle_query_data_assets(arguments)
            
            elif name == GET_ASSET_DETAILS_TOOL:
                return await handlers.handle_get_asset_details(arguments)
            
            elif name == LIST_DATASETS_TOOL:
                return await handlers.handle_list_datasets(arguments)
            
            elif name == GET_DATASETS_FOR_QUERY_GENERATION_TOOL:
                return await handlers.handle_get_datasets_for_query_generation(arguments)
            
            else:
                error_msg = f"Unknown tool: {name}"
                logger.error(error_msg)
                return [TextContent(type="text", text=f"Error: {error_msg}")]
        
        except Exception as e:
            logger.error(f"Error handling tool {name}: {e}", exc_info=True)
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    return server


async def main() -> None:
    """
    Main entry point for MCP server (stdio mode only).
    
    Runs the server using stdio transport for local development
    and subprocess communication.
    """
    try:
        # Load configuration
        logger.info("Loading MCP configuration from environment...")
        config = load_config()
        
        logger.info(f"Starting MCP server: {config.mcp_server_name} v{config.mcp_server_version}")
        logger.info("Transport: stdio")
        logger.info(f"Project: {config.project_id}")
        logger.info(f"Vertex AI Datastore: {config.vertex_datastore_id}")
        logger.info(f"Reports Bucket: {config.reports_bucket}")
        
        # Create server
        server = create_mcp_server(config)
        
        # Run server with stdio transport
        async with stdio_server() as (read_stream, write_stream):
            logger.info("MCP server running on stdio...")
            
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name=config.mcp_server_name,
                    server_version=config.mcp_server_version,
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
    
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        raise


def run_server() -> None:
    """
    Synchronous wrapper for running the server.
    
    Determines transport mode and runs appropriate server:
    - stdio: For local development (asyncio)
    - http: For containerized deployment (uvicorn)
    """
    # Load config to determine transport mode
    config = load_config()
    
    logger.info(f"Starting MCP server: {config.mcp_server_name} v{config.mcp_server_version}")
    logger.info(f"Transport: {config.mcp_transport}")
    logger.info(f"Project: {config.project_id}")
    logger.info(f"Vertex AI Datastore: {config.vertex_datastore_id}")
    logger.info(f"Reports Bucket: {config.reports_bucket}")
    
    if config.mcp_transport.lower() == "http":
        # HTTP transport - run uvicorn server
        from .http_server import run_http_server
        
        logger.info(f"Starting HTTP server on {config.mcp_host}:{config.mcp_port}")
        run_http_server(host=config.mcp_host, port=config.mcp_port)
    else:
        # stdio transport - run async server
        logger.info("Using stdio transport (for local/subprocess communication)")
        asyncio.run(main())


if __name__ == "__main__":
    run_server()

