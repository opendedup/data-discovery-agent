"""
MCP Service Package

Provides Model Context Protocol (MCP) interface for querying
indexed metadata from Vertex AI Search.
"""

from .config import MCPConfig
from .server import create_mcp_server

__all__ = ["MCPConfig", "create_mcp_server"]

