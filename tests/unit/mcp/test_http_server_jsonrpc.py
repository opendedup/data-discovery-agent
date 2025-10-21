"""Tests for MCP HTTP Server JSON-RPC Implementation."""

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from data_discovery_agent.mcp.http_server import create_http_app


@pytest.fixture
def mock_config() -> MagicMock:
    """
    Mock MCP configuration.
    
    Returns:
        Mock config object
    """
    config = MagicMock()
    config.project_id = "test-project"
    config.vertex_datastore_id = "test-datastore"
    config.reports_bucket = "test-bucket"
    config.vertex_location = "us-central1"
    config.mcp_server_version = "1.0.0"
    config.log_level = "INFO"
    return config


@pytest.fixture
def mock_handlers() -> MagicMock:
    """
    Mock MCP handlers.
    
    Returns:
        Mock handlers instance
    """
    handlers = MagicMock()
    
    # Mock async methods
    handlers.handle_query_data_assets = AsyncMock()
    handlers.handle_get_asset_details = AsyncMock()
    handlers.handle_list_datasets = AsyncMock()
    
    return handlers


@pytest.fixture
def app(mock_config: MagicMock, mock_handlers: MagicMock) -> TestClient:
    """
    Create FastAPI test client with mocked dependencies.
    
    Args:
        mock_config: Mock configuration
        mock_handlers: Mock handlers
        
    Returns:
        FastAPI test client
    """
    with patch("data_discovery_agent.mcp.http_server.load_config", return_value=mock_config):
        with patch("data_discovery_agent.mcp.http_server.VertexSearchClient"):
            with patch("data_discovery_agent.mcp.http_server.storage.Client"):
                with patch("data_discovery_agent.mcp.http_server.MCPHandlers", return_value=mock_handlers):
                    app = create_http_app()
                    # Inject mocked instances into global variables
                    import data_discovery_agent.mcp.http_server as http_server_module
                    http_server_module.config_instance = mock_config
                    http_server_module.handlers_instance = mock_handlers
                    
                    yield TestClient(app)


class TestHealthEndpoint:
    """Tests for health check endpoint."""
    
    def test_health_check(self, app: TestClient) -> None:
        """Test health check endpoint returns correct status."""
        response = app.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "data-discovery-mcp"
        assert data["transport"] == "http"


class TestRootEndpoint:
    """Tests for root endpoint."""
    
    def test_root_returns_service_info(self, app: TestClient) -> None:
        """Test root endpoint returns service information."""
        response = app.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "data-discovery-mcp"
        assert data["protocol"] == "MCP JSON-RPC 2.0"
        assert "endpoints" in data


class TestJSONRPCInitialize:
    """Tests for JSON-RPC initialize method."""
    
    def test_initialize_request(self, app: TestClient) -> None:
        """Test JSON-RPC initialize method."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "test-client", "version": "1.0.0"}
            }
        }
        
        response = app.post("/", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert "result" in data
        assert data["result"]["protocolVersion"] == "2025-06-18"
        assert "capabilities" in data["result"]
        assert "tools" in data["result"]["capabilities"]
        assert "serverInfo" in data["result"]
        assert data["result"]["serverInfo"]["name"] == "data-discovery-mcp"


class TestJSONRPCToolsList:
    """Tests for JSON-RPC tools/list method."""
    
    def test_tools_list_request(self, app: TestClient) -> None:
        """Test JSON-RPC tools/list method."""
        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list"
        }
        
        response = app.post("/", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 2
        assert "result" in data
        assert "tools" in data["result"]
        assert isinstance(data["result"]["tools"], list)
        assert len(data["result"]["tools"]) > 0
        
        # Verify tool structure
        tool = data["result"]["tools"][0]
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool


class TestJSONRPCToolsCall:
    """Tests for JSON-RPC tools/call method."""
    
    def test_tools_call_query_data_assets(
        self,
        app: TestClient,
        mock_handlers: MagicMock
    ) -> None:
        """Test calling query_data_assets tool via JSON-RPC."""
        # Mock tool response
        mock_content = MagicMock()
        mock_content.type = "text"
        mock_content.text = "Test search results"
        mock_handlers.handle_query_data_assets.return_value = [mock_content]
        
        payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "query_data_assets",
                "arguments": {
                    "query": "test query"
                }
            }
        }
        
        response = app.post("/", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 3
        assert "result" in data
        assert "content" in data["result"]
        assert len(data["result"]["content"]) == 1
        assert data["result"]["content"][0]["type"] == "text"
        assert data["result"]["content"][0]["text"] == "Test search results"
        
        # Verify handler was called
        mock_handlers.handle_query_data_assets.assert_called_once()
    
    def test_tools_call_get_asset_details(
        self,
        app: TestClient,
        mock_handlers: MagicMock
    ) -> None:
        """Test calling get_asset_details tool via JSON-RPC."""
        # Mock tool response
        mock_content = MagicMock()
        mock_content.type = "text"
        mock_content.text = "Asset details"
        mock_handlers.handle_get_asset_details.return_value = [mock_content]
        
        payload = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "get_asset_details",
                "arguments": {
                    "project_id": "test-project",
                    "dataset_id": "test-dataset",
                    "table_id": "test-table"
                }
            }
        }
        
        response = app.post("/", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        
        # Verify handler was called
        mock_handlers.handle_get_asset_details.assert_called_once()
    
    def test_tools_call_list_datasets(
        self,
        app: TestClient,
        mock_handlers: MagicMock
    ) -> None:
        """Test calling list_datasets tool via JSON-RPC."""
        # Mock tool response
        mock_content = MagicMock()
        mock_content.type = "text"
        mock_content.text = "Dataset list"
        mock_handlers.handle_list_datasets.return_value = [mock_content]
        
        payload = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "list_datasets",
                "arguments": {
                    "project_id": "test-project"
                }
            }
        }
        
        response = app.post("/", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        
        # Verify handler was called
        mock_handlers.handle_list_datasets.assert_called_once()
    
    def test_tools_call_unknown_tool(self, app: TestClient) -> None:
        """Test calling unknown tool returns error."""
        payload = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "unknown_tool",
                "arguments": {}
            }
        }
        
        response = app.post("/", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        # Validation catches unknown tool before routing, returns -32602
        assert data["error"]["code"] == -32602
        assert "Unknown tool" in data["error"]["message"]
    
    def test_tools_call_missing_name(self, app: TestClient) -> None:
        """Test calling tool without name returns error."""
        payload = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "arguments": {}
            }
        }
        
        response = app.post("/", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32602


class TestJSONRPCNotifications:
    """Tests for JSON-RPC notifications."""
    
    def test_initialized_notification(self, app: TestClient) -> None:
        """Test initialized notification (no response expected)."""
        payload = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
            # No id field for notifications
        }
        
        response = app.post("/", json=payload)
        
        assert response.status_code == 200
        # Notifications return empty response
        assert response.json() == {}


class TestJSONRPCErrors:
    """Tests for JSON-RPC error handling."""
    
    def test_unknown_method(self, app: TestClient) -> None:
        """Test unknown JSON-RPC method returns error."""
        payload = {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "unknown/method",
            "params": {}
        }
        
        response = app.post("/", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32601
        assert "Method not found" in data["error"]["message"]
    
    def test_invalid_json(self, app: TestClient) -> None:
        """Test invalid JSON returns parse error."""
        response = app.post(
            "/",
            content="{invalid json}",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32700
        assert "Parse error" in data["error"]["message"]


class TestLegacyRESTEndpoints:
    """Tests for legacy REST endpoints (backwards compatibility)."""
    
    def test_legacy_list_tools(self, app: TestClient) -> None:
        """Test legacy /mcp/tools endpoint."""
        response = app.get("/mcp/tools")
        
        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert isinstance(data["tools"], list)
    
    def test_legacy_call_tool(
        self,
        app: TestClient,
        mock_handlers: MagicMock
    ) -> None:
        """Test legacy /mcp/call-tool endpoint."""
        # Mock tool response
        mock_content = MagicMock()
        mock_content.type = "text"
        mock_content.text = "Legacy response"
        mock_handlers.handle_query_data_assets.return_value = [mock_content]
        
        payload = {
            "name": "query_data_assets",
            "arguments": {"query": "test"}
        }
        
        response = app.post("/mcp/call-tool", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert isinstance(data["result"], list)

