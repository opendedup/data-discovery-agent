"""
MCP Client Example

Demonstrates how to connect to and use the Data Discovery MCP service.

This example shows:
1. Connecting to the MCP server
2. Listing available tools
3. Querying for data assets
4. Getting detailed asset information
5. Listing datasets
"""

import asyncio
import os
import sys
from typing import Any, Dict

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Load environment variables from .env file
load_dotenv()


async def main(custom_query: str | None = None) -> None:
    """
    Main example function.
    
    Args:
        custom_query: Optional custom search query to execute
    
    Note:
        The client automatically launches the MCP server as a subprocess.
        For debugging, use --server-only flag to run just the server.
    """
    
    # Configure server parameters
    # The MCP service runs as a subprocess communicating via stdio
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "data_discovery_agent.mcp.server"],
        env={
            # Pass required environment variables
            "GCP_PROJECT_ID": os.getenv("GCP_PROJECT_ID", ""),
            "GCS_REPORTS_BUCKET": os.getenv("GCS_REPORTS_BUCKET", ""),
            "VERTEX_DATASTORE_ID": os.getenv("VERTEX_DATASTORE_ID", "data-discovery-metadata"),
            "VERTEX_LOCATION": os.getenv("VERTEX_LOCATION", "global"),
            "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
        }
    )
    
    print("Connecting to Data Discovery MCP service...")
    print("(Server will be launched as subprocess)\n")
    
    # Connect to the MCP server
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the session
            await session.initialize()
            print("✓ Connected to MCP server\n")
            
            # If custom query provided, run it first
            if custom_query:
                print("=" * 70)
                print("CUSTOM QUERY SEARCH")
                print("=" * 70)
                print(f"\nQuery: '{custom_query}'\n")
                
                result = await session.call_tool(
                    "query_data_assets",
                    arguments={
                        "query": custom_query,
                        "page_size": 10,
                        "include_full_content": False,
                    }
                )
                
                print("Search Results:")
                for content in result.content:
                    if hasattr(content, 'text'):
                        print(content.text)
                
                print("\n" + "=" * 70)
                print("Continuing with standard examples...")
                print("=" * 70)
                print()
            
            # Example 1: List available tools
            print("=" * 70)
            print("EXAMPLE 1: List Available Tools")
            print("=" * 70)
            
            tools = await session.list_tools()
            print(f"\nAvailable tools: {len(tools.tools)}")
            for tool in tools.tools:
                print(f"\n• {tool.name}")
                print(f"  {tool.description[:100]}...")
            
            # Example 2: Query for tables with PII
            print("\n\n")
            print("=" * 70)
            print("EXAMPLE 2: Search for Tables with PII")
            print("=" * 70)
            
            result = await session.call_tool(
                "query_data_assets",
                arguments={
                    "query": "tables with PII data",
                    "has_pii": True,
                    "page_size": 3,
                    "include_full_content": False,  # Just snippets for this example
                }
            )
            
            print("\nSearch Results:")
            for content in result.content:
                if hasattr(content, 'text'):
                    # Print first 500 chars of response
                    print(content.text[:500])
                    if len(content.text) > 500:
                        print("... (truncated)")
            
            # Example 3: Get details for a specific table
            print("\n\n")
            print("=" * 70)
            print("EXAMPLE 3: Get Asset Details")
            print("=" * 70)
            
            # You'll need to adjust these values to match an actual table in your project
            project_id = os.getenv("GCP_PROJECT_ID", "")
            dataset_id = "data_discovery"  # Example dataset
            table_id = "discovered_assets"  # Example table
            
            try:
                result = await session.call_tool(
                    "get_asset_details",
                    arguments={
                        "project_id": project_id,
                        "dataset_id": dataset_id,
                        "table_id": table_id,
                        "include_lineage": True,
                        "include_usage": True,
                    }
                )
                
                print(f"\nAsset: {project_id}.{dataset_id}.{table_id}")
                for content in result.content:
                    if hasattr(content, 'text'):
                        # Print first 1000 chars of response
                        print(content.text[:1000])
                        if len(content.text) > 1000:
                            print("... (truncated)")
            
            except Exception as e:
                print(f"Error: {e}")
                print("(This is expected if the table doesn't exist in your project)")
            
            # Example 4: List all datasets
            print("\n\n")
            print("=" * 70)
            print("EXAMPLE 4: List Datasets")
            print("=" * 70)
            
            result = await session.call_tool(
                "list_datasets",
                arguments={
                    "project_id": project_id,
                    "include_table_counts": True,
                    "include_costs": True,
                }
            )
            
            print("\nDatasets:")
            for content in result.content:
                if hasattr(content, 'text'):
                    # Print first 1000 chars of response
                    print(content.text[:1000])
                    if len(content.text) > 1000:
                        print("... (truncated)")
            
            # Example 5: Search with filters
            print("\n\n")
            print("=" * 70)
            print("EXAMPLE 5: Search with Filters")
            print("=" * 70)
            
            result = await session.call_tool(
                "query_data_assets",
                arguments={
                    "query": "large tables",
                    "min_row_count": 1000000,
                    "sort_by": "row_count",
                    "sort_order": "desc",
                    "page_size": 5,
                    "include_full_content": False,
                }
            )
            
            print("\nLarge Tables (sorted by row count):")
            for content in result.content:
                if hasattr(content, 'text'):
                    print(content.text[:500])
                    if len(content.text) > 500:
                        print("... (truncated)")
            
            # Example 6: Search by environment
            print("\n\n")
            print("=" * 70)
            print("EXAMPLE 6: Search by Environment")
            print("=" * 70)
            
            result = await session.call_tool(
                "query_data_assets",
                arguments={
                    "query": "production tables",
                    "environment": "production",
                    "page_size": 5,
                    "include_full_content": False,
                }
            )
            
            print("\nProduction Tables:")
            for content in result.content:
                if hasattr(content, 'text'):
                    print(content.text[:500])
                    if len(content.text) > 500:
                        print("... (truncated)")
    
    print("\n\nDisconnected from MCP server")


def print_tool_info(tool: Any) -> None:
    """Print detailed information about a tool."""
    print(f"\nTool: {tool.name}")
    print(f"Description: {tool.description}")
    
    if hasattr(tool, 'inputSchema'):
        schema = tool.inputSchema
        if 'properties' in schema:
            print("\nParameters:")
            for param_name, param_info in schema['properties'].items():
                required = param_name in schema.get('required', [])
                required_str = " (required)" if required else " (optional)"
                print(f"  • {param_name}{required_str}")
                if 'description' in param_info:
                    print(f"    {param_info['description']}")


async def run_server_only() -> None:
    """
    Run only the MCP server for debugging purposes.
    
    This allows you to:
    1. Attach a debugger to the server process
    2. See server logs in real-time
    3. Test server behavior independently
    """
    print("=" * 70)
    print("MCP SERVER - DEBUG MODE")
    print("=" * 70)
    print("\nStarting MCP server in standalone mode...")
    print("Press Ctrl+C to stop\n")
    print("The server is now listening on stdin/stdout.")
    print("You can send MCP protocol messages via stdin.\n")
    print("=" * 70 + "\n")
    
    # Import and run the server directly
    from data_discovery_agent.mcp.server import main as server_main
    await server_main()


if __name__ == "__main__":
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Data Discovery MCP Client Example",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all examples
  python examples/mcp_client_example.py
  
  # Run with custom query
  python examples/mcp_client_example.py "find tables with customer data"
  
  # Run server only (for debugging)
  python examples/mcp_client_example.py --server-only
  
  # Run with debug logging
  LOG_LEVEL=DEBUG python examples/mcp_client_example.py
        """
    )
    
    parser.add_argument(
        "--server-only",
        action="store_true",
        help="Run only the MCP server (for debugging). Server listens on stdin/stdout."
    )
    
    parser.add_argument(
        "query",
        nargs="*",
        help="Custom search query to execute before running examples"
    )
    
    args = parser.parse_args()
    
    # Check environment variables
    required_vars = ["GCP_PROJECT_ID", "GCS_REPORTS_BUCKET"]
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        print("Error: Missing required environment variables:")
        for var in missing:
            print(f"  - {var}")
        print("\nPlease set these in your .env file or environment")
        exit(1)
    
    # Server-only mode
    if args.server_only:
        asyncio.run(run_server_only())
        exit(0)
    
    # Get custom query if provided
    custom_query = None
    if args.query:
        custom_query = " ".join(args.query)
        print(f"Custom query provided: '{custom_query}'\n")
    
    # Run the example
    asyncio.run(main(custom_query))

