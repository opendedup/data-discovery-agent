"""
MCP HTTP Client Example

Demonstrates how to connect to the Data Discovery MCP service over HTTP.
This is used when the MCP service is deployed in a container (Docker/Kubernetes).

Usage:
    # Connect to local container
    python examples/http_client_example.py

    # Connect to remote service
    MCP_SERVICE_URL=http://mcp-service.example.com python examples/http_client_example.py
"""

import asyncio
import os
from typing import Any, Dict, List

import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class MCPHttpClient:
    """
    HTTP client for MCP service.
    
    Connects to MCP service over HTTP (for containerized deployments).
    """
    
    def __init__(self, base_url: str):
        """
        Initialize HTTP client.
        
        Args:
            base_url: Base URL of MCP service (e.g., http://localhost:8080)
        """
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check service health.
        
        Returns:
            Health status
        """
        response = await self.client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        List available MCP tools.
        
        Returns:
            List of available tools
        """
        response = await self.client.get(f"{self.base_url}/mcp/tools")
        response.raise_for_status()
        data = response.json()
        return data.get("tools", [])
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Call an MCP tool.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool execution results
        """
        payload = {
            "name": tool_name,
            "arguments": arguments or {}
        }
        
        response = await self.client.post(
            f"{self.base_url}/mcp/call-tool",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("result", [])


async def main(custom_query: str | None = None) -> None:
    """
    Main example function.
    
    Args:
        custom_query: Optional custom search query to execute
    """
    
    # Get service URL from environment or use default
    service_url = os.getenv("MCP_SERVICE_URL", "http://localhost:8080")
    
    print("=" * 70)
    print("MCP HTTP Client Example")
    print("=" * 70)
    print(f"\nConnecting to: {service_url}\n")
    
    # Create client
    client = MCPHttpClient(service_url)
    
    try:
        # If custom query provided, run it first
        if custom_query:
            print("=" * 70)
            print("CUSTOM QUERY SEARCH")
            print("=" * 70)
            print(f"\nQuery: '{custom_query}'\n")
            
            result = await client.call_tool(
                "query_data_assets",
                {
                    "query": custom_query,
                    "page_size": 10,
                    "include_full_content": False,
                }
            )
            
            print("Search Results:")
            for item in result:
                text = item.get("text", "")
                print(text)
            
            print("\n" + "=" * 70)
            print("Continuing with standard examples...")
            print("=" * 70)
            print()
        
        # Example 1: Health check
        print("=" * 70)
        print("EXAMPLE 1: Health Check")
        print("=" * 70)
        
        health = await client.health_check()
        print(f"\nService Status: {health}")
        
        # Example 2: List tools
        print("\n\n" + "=" * 70)
        print("EXAMPLE 2: List Available Tools")
        print("=" * 70)
        
        tools = await client.list_tools()
        print(f"\nAvailable tools: {len(tools)}\n")
        for tool in tools:
            print(f"• {tool['name']}")
            print(f"  {tool['description'][:80]}...")
            print()
        
        # Example 3: Search for tables
        print("=" * 70)
        print("EXAMPLE 3: Search for Tables with PII")
        print("=" * 70)
        
        result = await client.call_tool(
            "query_data_assets",
            {
                "query": "tables with PII data",
                "has_pii": True,
                "page_size": 3,
                "include_full_content": False,
            }
        )
        
        print("\nSearch Results:")
        for item in result:
            text = item.get("text", "")
            print(text[:500])
            if len(text) > 500:
                print("... (truncated)")
        
        # Example 4: List datasets
        print("\n\n" + "=" * 70)
        print("EXAMPLE 4: List Datasets")
        print("=" * 70)
        
        project_id = os.getenv("GCP_PROJECT_ID", "")
        result = await client.call_tool(
            "list_datasets",
            {
                "project_id": project_id,
                "include_table_counts": True,
                "include_costs": True,
                "page_size": 10,
            }
        )
        
        print("\nDatasets:")
        for item in result:
            text = item.get("text", "")
            print(text[:1000])
            if len(text) > 1000:
                print("... (truncated)")
        
        # Example 5: Get specific table details
        print("\n\n" + "=" * 70)
        print("EXAMPLE 5: Get Asset Details")
        print("=" * 70)
        
        try:
            result = await client.call_tool(
                "get_asset_details",
                {
                    "project_id": project_id,
                    "dataset_id": "data_discovery",
                    "table_id": "discovered_assets",
                    "include_lineage": True,
                    "include_usage": True,
                }
            )
            
            print(f"\nAsset Details:")
            for item in result:
                text = item.get("text", "")
                print(text[:1000])
                if len(text) > 1000:
                    print("... (truncated)")
        
        except Exception as e:
            print(f"Error: {e}")
            print("(This is expected if the table doesn't exist)")
    
    finally:
        # Clean up
        await client.close()
    
    print("\n\n" + "=" * 70)
    print("Examples Complete!")
    print("=" * 70)


if __name__ == "__main__":
    import sys
    
    # Check environment
    if not os.getenv("GCP_PROJECT_ID"):
        print("Warning: GCP_PROJECT_ID not set. Some examples may fail.")
        print("Set it in .env or environment variables.\n")
    
    # Check for custom query from command line
    custom_query = None
    if len(sys.argv) > 1:
        custom_query = " ".join(sys.argv[1:])
        print(f"Custom query provided: '{custom_query}'\n")
    
    # Run examples
    asyncio.run(main(custom_query))

