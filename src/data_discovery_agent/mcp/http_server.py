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

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from google.cloud import storage

from ..clients.vertex_search_client import VertexSearchClient
from .config import load_config
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
    
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """
        Middleware to log incoming requests.
        
        Args:
            request: The incoming request
            call_next: Next middleware/handler
            
        Returns:
            Response from next handler
        """
        # Log request summary
        logger.debug(f"{request.method} {request.url.path}")
        
        # Process request
        response = await call_next(request)
        
        # Log response status
        if response.status_code >= 400:
            logger.warning(f"{request.method} {request.url.path} -> {response.status_code}")
        else:
            logger.debug(f"{request.method} {request.url.path} -> {response.status_code}")
        
        return response
    
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
    async def root(request: Request) -> Any:
        """
        Root endpoint with service information or SSE stream for notifications.
        
        If client accepts text/event-stream, returns an SSE stream for MCP notifications.
        Otherwise returns service information as JSON.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Service information JSON or SSE stream
        """
        # Check if client wants SSE
        accept_header = request.headers.get("accept", "")
        if "text/event-stream" in accept_header:
            logger.debug("Opening SSE stream for MCP notifications")
            
            async def event_stream():
                """Generate SSE events for MCP notifications."""
                try:
                    # Immediately yield to establish connection
                    yield ":"  # Empty comment to flush connection
                    
                    # Keep connection alive with periodic comments (not events)
                    while True:
                        await asyncio.sleep(15)  # Send ping every 15 seconds
                        yield ": ping\n\n"
                except asyncio.CancelledError:
                    logger.debug("SSE stream closed")
                    raise
            
            return StreamingResponse(
                event_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
        
        # Return service info for regular requests
        return {
            "service": "data-discovery-mcp",
            "version": config_instance.mcp_server_version if config_instance else "unknown",
            "protocol": "MCP JSON-RPC 2.0",
            "transport": "HTTP",
            "endpoints": {
                "health": "/health",
                "jsonrpc": "/ (POST for JSON-RPC)",
                "sse": "/ (GET with Accept: text/event-stream)",
                "tools": "/mcp/tools (legacy REST)",
                "call_tool": "/mcp/call-tool (legacy REST)"
            },
            "documentation": "https://github.com/your-org/data-discovery-agent"
        }
    
    @app.post("/")
    async def jsonrpc_handler(request: Request) -> Dict[str, Any]:
        """
        JSON-RPC 2.0 endpoint for MCP protocol.
        
        Handles MCP JSON-RPC requests from clients like Cursor.
        
        Args:
            request: FastAPI request object
            
        Returns:
            JSON-RPC 2.0 response
        """
        if not handlers_instance:
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": "MCP server not initialized"
                }
            }
        
        try:
            body = await request.json()
            rpc_id = body.get("id")
            method = body.get("method")
            params = body.get("params", {})
            
            logger.debug(f"JSON-RPC method: {method}")
            
            # Handle notifications (no id field, no response expected)
            if rpc_id is None:
                if method == "notifications/initialized":
                    logger.debug("Client sent initialized notification")
                    return {}  # No response for notifications
                else:
                    logger.warning(f"Unknown notification method: {method}")
                    return {}  # No response for notifications
            
            # Handle initialize
            if method == "initialize":
                logger.info("MCP client initializing connection")
                return {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "result": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {
                            "tools": {},  # Empty object to indicate tools are supported
                            "prompts": {},  # Empty object
                            "resources": {},  # Empty object
                            "logging": {}  # Empty object
                        },
                        "serverInfo": {
                            "name": "data-discovery-mcp",
                            "version": config_instance.mcp_server_version if config_instance else "1.0.0"
                        }
                    }
                }
            
            # Handle tools/list
            elif method == "tools/list":
                logger.debug("Listing available tools")
                from .tools import get_available_tools
                tools = get_available_tools()
                
                return {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "result": {
                        "tools": [
                            {
                                "name": tool.name,
                                "description": tool.description,
                                "inputSchema": tool.inputSchema
                            }
                            for tool in tools
                        ]
                    }
                }
            
            # Handle tools/call
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                
                if not tool_name:
                    return {
                        "jsonrpc": "2.0",
                        "id": rpc_id,
                        "error": {
                            "code": -32602,
                            "message": "Missing 'name' parameter"
                        }
                    }
                
                logger.info(f"Calling tool via JSON-RPC: {tool_name}")
                
                # Import tool names
                from .tools import (
                    QUERY_DATA_ASSETS_TOOL,
                    GET_ASSET_DETAILS_TOOL,
                    LIST_DATASETS_TOOL,
                    GET_DATASETS_FOR_QUERY_GENERATION_TOOL,
                    DISCOVER_DATASETS_FOR_PRP_TOOL,
                    DISCOVER_FROM_PRP_TOOL,
                    validate_query_params,
                )
                
                # Validate parameters
                try:
                    validate_query_params(arguments, tool_name)
                except Exception as e:
                    return {
                        "jsonrpc": "2.0",
                        "id": rpc_id,
                        "error": {
                            "code": -32602,
                            "message": f"Invalid parameters: {str(e)}"
                        }
                    }
                
                # Route to appropriate handler
                if tool_name == QUERY_DATA_ASSETS_TOOL:
                    result = await handlers_instance.handle_query_data_assets(arguments)
                elif tool_name == GET_ASSET_DETAILS_TOOL:
                    result = await handlers_instance.handle_get_asset_details(arguments)
                elif tool_name == LIST_DATASETS_TOOL:
                    result = await handlers_instance.handle_list_datasets(arguments)
                elif tool_name == GET_DATASETS_FOR_QUERY_GENERATION_TOOL:
                    result = await handlers_instance.handle_get_datasets_for_query_generation(arguments)
                elif tool_name == DISCOVER_DATASETS_FOR_PRP_TOOL:
                    result = await handlers_instance.handle_discover_datasets_for_prp(arguments)
                elif tool_name == DISCOVER_FROM_PRP_TOOL:
                    result = await handlers_instance.handle_discover_from_prp(arguments)
                else:
                    return {
                        "jsonrpc": "2.0",
                        "id": rpc_id,
                        "error": {
                            "code": -32601,
                            "message": f"Unknown tool: {tool_name}"
                        }
                    }
                
                # Format response
                return {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "result": {
                        "content": [
                            {
                                "type": content.type,
                                "text": content.text
                            }
                            for content in result
                        ]
                    }
                }
            
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
        
        except json.JSONDecodeError:
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": "Parse error"
                }
            }
        except Exception as e:
            logger.error(f"JSON-RPC error: {e}", exc_info=True)
            return {
                "jsonrpc": "2.0",
                "id": rpc_id if 'rpc_id' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
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
            logger.debug(f"Arguments received: {json.dumps(arguments, indent=2)}")
            
            # Import tool names
            from .tools import (
                QUERY_DATA_ASSETS_TOOL,
                GET_ASSET_DETAILS_TOOL,
                LIST_DATASETS_TOOL,
                GET_DATASETS_FOR_QUERY_GENERATION_TOOL,
                DISCOVER_DATASETS_FOR_PRP_TOOL,
                DISCOVER_FROM_PRP_TOOL,
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
            elif tool_name == GET_DATASETS_FOR_QUERY_GENERATION_TOOL:
                result = await handlers_instance.handle_get_datasets_for_query_generation(arguments)
            elif tool_name == DISCOVER_DATASETS_FOR_PRP_TOOL:
                result = await handlers_instance.handle_discover_datasets_for_prp(arguments)
            elif tool_name == DISCOVER_FROM_PRP_TOOL:
                result = await handlers_instance.handle_discover_from_prp(arguments, request=request)
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

