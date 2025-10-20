"""
MCP HTTP Server Implementation

Network-based MCP server using FastAPI and SSE for remote client connections.
This is used for containerized deployments where clients connect over HTTP.
"""

import asyncio
import json
import logging
from typing import Any, Dict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import StreamingResponse
from google.cloud import storage

from ..clients.vertex_search_client import VertexSearchClient
from .config import MCPConfig, load_config
from .server import create_mcp_server
from .handlers import MCPHandlers

logger = logging.getLogger(__name__)


# Global instances
config_instance = None
handlers_instance = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> None:
    """
    FastAPI lifespan context manager for startup/shutdown.
    
    Args:
        app: FastAPI application instance
        
    Yields:
        Control to the application
    """
    global config_instance, handlers_instance
    
    # Startup
    logger.info("Starting MCP HTTP server...")
    config_instance = load_config()
    
    logger.info(f"Project: {config_instance.project_id}")
    logger.info(f"Vertex AI Datastore: {config_instance.vertex_datastore_id}")
    logger.info(f"Reports Bucket: {config_instance.reports_bucket}")
    
    # Initialize clients and handlers
    logger.info("Initializing Vertex AI Search client...")
    vertex_client = VertexSearchClient(
        project_id=config_instance.project_id,
        location=config_instance.vertex_location,
        datastore_id=config_instance.vertex_datastore_id,
        reports_bucket=config_instance.reports_bucket,
    )
    
    logger.info("Initializing GCS storage client...")
    storage_client = storage.Client(project=config_instance.project_id)
    
    logger.info("Initializing MCP handlers...")
    handlers_instance = MCPHandlers(
        config=config_instance,
        vertex_client=vertex_client,
        storage_client=storage_client,
    )
    
    logger.info("MCP HTTP server initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down MCP HTTP server...")


def create_http_app() -> FastAPI:
    """
    Create FastAPI application for MCP HTTP server.
    
    Returns:
        FastAPI application instance
    """
    app = FastAPI(
        title="Data Discovery MCP Service",
        description="Model Context Protocol service for BigQuery data discovery",
        version="1.0.0",
        lifespan=lifespan,
    )
    
    @app.get("/health")
    async def health_check() -> Dict[str, str]:
        """
        Health check endpoint for container orchestration.
        
        Returns:
            Health status
        """
        return {
            "status": "healthy",
            "service": "data-discovery-mcp",
            "transport": "http"
        }
    
    @app.get("/")
    async def root() -> Dict[str, Any]:
        """
        Root endpoint with service information.
        
        Returns:
            Service information
        """
        return {
            "service": "data-discovery-mcp",
            "version": config_instance.mcp_server_version if config_instance else "unknown",
            "protocol": "MCP",
            "transport": "HTTP",
            "endpoints": {
                "health": "/health",
                "tools": "/mcp/tools",
                "call_tool": "/mcp/call-tool"
            },
            "documentation": "https://github.com/your-org/data-discovery-agent"
        }
    
    @app.get("/mcp/tools")
    async def list_tools() -> Dict[str, Any]:
        """
        List available MCP tools.
        
        Returns:
            List of available tools with their schemas
        """
        if not handlers_instance:
            raise HTTPException(status_code=503, detail="MCP server not initialized")
        
        try:
            # Import and get available tools
            from .tools import get_available_tools
            
            tools = get_available_tools()
            
            return {
                "tools": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.inputSchema
                    }
                    for tool in tools
                ]
            }
        except Exception as e:
            logger.error(f"Error listing tools: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/mcp/call-tool")
    async def call_tool(request: Request) -> Dict[str, Any]:
        """
        Call an MCP tool.
        
        Request body should contain:
        {
            "name": "tool_name",
            "arguments": {...}
        }
        
        Returns:
            Tool execution results
        """
        if not handlers_instance:
            raise HTTPException(status_code=503, detail="MCP server not initialized")
        
        try:
            # Parse request
            body = await request.json()
            tool_name = body.get("name")
            arguments = body.get("arguments", {})
            
            if not tool_name:
                raise HTTPException(status_code=400, detail="Missing 'name' in request")
            
            logger.info(f"Tool called: {tool_name}")
            
            # Import tool names
            from .tools import (
                QUERY_DATA_ASSETS_TOOL,
                GET_ASSET_DETAILS_TOOL,
                LIST_DATASETS_TOOL,
                validate_query_params,
            )
            
            # Validate parameters
            validate_query_params(arguments, tool_name)
            
            # Route to appropriate handler
            if tool_name == QUERY_DATA_ASSETS_TOOL:
                result = await handlers_instance.handle_query_data_assets(arguments)
            elif tool_name == GET_ASSET_DETAILS_TOOL:
                result = await handlers_instance.handle_get_asset_details(arguments)
            elif tool_name == LIST_DATASETS_TOOL:
                result = await handlers_instance.handle_list_datasets(arguments)
            else:
                raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_name}")
            
            # Format response
            return {
                "result": [
                    {
                        "type": content.type,
                        "text": content.text
                    }
                    for content in result
                ]
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error calling tool: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    return app


def run_http_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    """
    Run the MCP HTTP server.
    
    Args:
        host: Host address to bind to
        port: Port to listen on
    """
    import uvicorn
    
    app = create_http_app()
    
    logger.info(f"Starting MCP HTTP server on {host}:{port}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    # Load config
    config = load_config()
    
    # Set logging level
    logging.getLogger().setLevel(config.log_level)
    
    # Run HTTP server
    run_http_server(host=config.mcp_host, port=config.mcp_port)

