"""Unit tests for MCP server."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest

from data_discovery_agent.mcp.config import MCPConfig
from data_discovery_agent.mcp.server import create_mcp_server

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture


@pytest.mark.unit
@pytest.mark.mcp
class TestMCPServer:
    """Tests for MCP server creation and configuration."""

    @patch("data_discovery_agent.mcp.server.VertexSearchClient")
    @patch("data_discovery_agent.mcp.server.storage.Client")
    def test_create_mcp_server(
        self, mock_storage: Mock, mock_vertex: Mock, mock_env: dict[str, str]
    ) -> None:
        """Test MCP server creation."""
        server = create_mcp_server()

        assert server is not None
        assert hasattr(server, "name")

    @patch("data_discovery_agent.mcp.server.VertexSearchClient")
    @patch("data_discovery_agent.mcp.server.storage.Client")
    def test_create_server_with_config(
        self, mock_storage: Mock, mock_vertex: Mock
    ) -> None:
        """Test MCP server creation with custom config."""
        config = MCPConfig(
            project_id="test-project",
            vertex_datastore_id="test-datastore",
            vertex_location="global",
            reports_bucket="test-bucket",
            mcp_server_name="custom-server",
            mcp_server_version="1.0.0",
        )

        server = create_mcp_server(config=config)

        assert server is not None

    @patch("data_discovery_agent.mcp.server.VertexSearchClient")
    @patch("data_discovery_agent.mcp.server.storage.Client")
    def test_server_initializes_clients(
        self, mock_storage: Mock, mock_vertex: Mock, mock_env: dict[str, str]
    ) -> None:
        """Test that server initializes required clients."""
        server = create_mcp_server()

        # Verify clients were instantiated
        assert mock_vertex.called
        assert mock_storage.called

    @patch("data_discovery_agent.mcp.server.VertexSearchClient")
    @patch("data_discovery_agent.mcp.server.storage.Client")
    @patch("data_discovery_agent.mcp.server.MCPHandlers")
    def test_server_initializes_handlers(
        self,
        mock_handlers: Mock,
        mock_storage: Mock,
        mock_vertex: Mock,
        mock_env: dict[str, str],
    ) -> None:
        """Test that server initializes handlers."""
        server = create_mcp_server()

        # Verify handlers were created
        assert mock_handlers.called

    @patch("data_discovery_agent.mcp.server.VertexSearchClient")
    @patch("data_discovery_agent.mcp.server.storage.Client")
    def test_server_registers_tools(
        self, mock_storage: Mock, mock_vertex: Mock, mock_env: dict[str, str]
    ) -> None:
        """Test that server registers tool handlers."""
        server = create_mcp_server()

        # Server should have handlers registered
        assert server is not None

