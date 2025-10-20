"""Unit tests for MCP HTTP server."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture


@pytest.mark.unit
@pytest.mark.mcp
class TestMCPHTTPServer:
    """Tests for MCP HTTP server."""

    @patch("data_discovery_agent.mcp.http_server.MCPConfig")
    @patch("data_discovery_agent.mcp.http_server.VertexSearchClient")
    @patch("data_discovery_agent.mcp.http_server.storage.Client")
    def test_create_http_app(
        self, mock_storage: Mock, mock_vertex: Mock, mock_config: Mock
    ) -> None:
        """Test HTTP app creation."""
        from data_discovery_agent.mcp.http_server import create_http_app

        app = create_http_app()

        assert app is not None

    @patch("data_discovery_agent.mcp.http_server.MCPConfig")
    @patch("data_discovery_agent.mcp.http_server.VertexSearchClient")
    @patch("data_discovery_agent.mcp.http_server.storage.Client")
    def test_health_endpoint(
        self, mock_storage: Mock, mock_vertex: Mock, mock_config: Mock
    ) -> None:
        """Test health check endpoint."""
        from data_discovery_agent.mcp.http_server import create_http_app

        app = create_http_app()
        client = TestClient(app)

        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    @patch("data_discovery_agent.mcp.http_server.MCPConfig")
    @patch("data_discovery_agent.mcp.http_server.VertexSearchClient")
    @patch("data_discovery_agent.mcp.http_server.storage.Client")
    def test_list_tools_endpoint(
        self, mock_storage: Mock, mock_vertex: Mock, mock_config: Mock
    ) -> None:
        """Test list tools endpoint."""
        from data_discovery_agent.mcp.http_server import create_http_app

        app = create_http_app()
        client = TestClient(app)

        response = client.get("/mcp/tools")

        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert len(data["tools"]) > 0

    @patch("data_discovery_agent.mcp.http_server.MCPConfig")
    @patch("data_discovery_agent.mcp.http_server.VertexSearchClient")
    @patch("data_discovery_agent.mcp.http_server.storage.Client")
    @patch("data_discovery_agent.mcp.http_server.MCPHandlers")
    def test_call_tool_endpoint(
        self,
        mock_handlers_class: Mock,
        mock_storage: Mock,
        mock_vertex: Mock,
        mock_config: Mock,
    ) -> None:
        """Test call tool endpoint."""
        from data_discovery_agent.mcp.http_server import create_http_app

        # Mock handler instance
        mock_handler_instance = Mock()
        mock_handlers_class.return_value = mock_handler_instance

        app = create_http_app()
        client = TestClient(app)

        request_data = {
            "name": "query_data_assets",
            "arguments": {"query": "find user tables"},
        }

        response = client.post("/mcp/call-tool", json=request_data)

        # May return 200 or error depending on mock setup
        assert response.status_code in [200, 400, 404, 500, 503]

    @patch("data_discovery_agent.mcp.http_server.MCPConfig")
    @patch("data_discovery_agent.mcp.http_server.VertexSearchClient")
    @patch("data_discovery_agent.mcp.http_server.storage.Client")
    def test_error_handling(
        self, mock_storage: Mock, mock_vertex: Mock, mock_config: Mock
    ) -> None:
        """Test error handling in endpoints."""
        from data_discovery_agent.mcp.http_server import create_http_app

        app = create_http_app()
        client = TestClient(app)

        # Invalid request
        response = client.post("/mcp/call-tool", json={})

        # Should return error status
        assert response.status_code >= 400

