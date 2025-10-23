"""
Entry point for running the MCP server via python -m data_discovery_agent.mcp

Routes to either HTTP or stdio transport based on MCP_TRANSPORT environment variable.
"""

from .server import run_server

if __name__ == "__main__":
    run_server()

