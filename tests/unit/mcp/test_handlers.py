"""Unit tests for MCP handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch

import pytest

from data_discovery_agent.mcp.config import MCPConfig
from data_discovery_agent.mcp.handlers import MCPHandlers

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture


@pytest.mark.unit
@pytest.mark.mcp
@pytest.mark.asyncio
class TestMCPHandlers:
    """Tests for MCP handlers."""

    @pytest.fixture
    def mock_config(self) -> MCPConfig:
        """Create mock MCP configuration."""
        return MCPConfig(
            project_id="test-project",
            vertex_datastore_id="test-datastore",
            vertex_location="global",
            reports_bucket="test-reports-bucket",
            mcp_server_name="test-server",
            mcp_server_version="1.0.0",
        )

    @pytest.fixture
    def mock_handlers(
        self, mock_config: MCPConfig, mock_vertex_client: Mock, mock_storage_client: Mock
    ) -> MCPHandlers:
        """Create MCP handlers with mocked dependencies."""
        return MCPHandlers(
            config=mock_config,
            vertex_client=mock_vertex_client,
            storage_client=mock_storage_client,
        )

    def test_init(
        self, mock_config: MCPConfig, mock_vertex_client: Mock, mock_storage_client: Mock
    ) -> None:
        """Test handlers initialization."""
        handlers = MCPHandlers(
            config=mock_config,
            vertex_client=mock_vertex_client,
            storage_client=mock_storage_client,
        )

        assert handlers.config == mock_config
        assert handlers.vertex_client == mock_vertex_client
        assert handlers.storage_client == mock_storage_client

    async def test_handle_query_data_assets(self, mock_handlers: MCPHandlers) -> None:
        """Test query data assets handler."""
        arguments = {
            "query": "find user tables",
            "page_size": 10,
        }

        # Mock vertex client search
        mock_handlers.vertex_client.search = AsyncMock(return_value=[])

        result = await mock_handlers.handle_query_data_assets(arguments)

        assert result is not None
        assert isinstance(result, list)

    async def test_handle_get_asset_details(self, mock_handlers: MCPHandlers) -> None:
        """Test get asset details handler."""
        arguments = {
            "project_id": "test-project",
            "dataset_id": "test_dataset",
            "table_id": "test_table",
        }

        result = await mock_handlers.handle_get_asset_details(arguments)

        assert result is not None
        assert isinstance(result, list)

    async def test_handle_list_datasets(self, mock_handlers: MCPHandlers) -> None:
        """Test list datasets handler."""
        arguments = {}

        result = await mock_handlers.handle_list_datasets(arguments)

        assert result is not None
        assert isinstance(result, list)

    async def test_handle_query_with_filters(self, mock_handlers: MCPHandlers) -> None:
        """Test query handler with filters."""
        arguments = {
            "query": "find tables",
            "project_id": "test-project",
            "dataset_id": "test_dataset",
        }

        mock_handlers.vertex_client.search = AsyncMock(return_value=[])

        result = await mock_handlers.handle_query_data_assets(arguments)

        assert result is not None

    async def test_handle_error_in_query(self, mock_handlers: MCPHandlers) -> None:
        """Test error handling in query handler."""
        arguments = {
            "query": "find tables",
        }

        # Simulate error
        mock_handlers.vertex_client.search = AsyncMock(
            side_effect=Exception("Search error")
        )

        result = await mock_handlers.handle_query_data_assets(arguments)

        # Should return error response
        assert result is not None
        assert any("error" in str(r).lower() for r in result)

    async def test_fetch_markdown_report(self, mock_handlers: MCPHandlers) -> None:
        """Test fetching markdown report from GCS."""
        arguments = {
            "project_id": "test-project",
            "dataset_id": "test_dataset",
            "table_id": "test_table",
            "run_timestamp": "20241020_120000",
        }

        result = await mock_handlers.handle_get_asset_details(arguments)

        assert result is not None

    async def test_handle_missing_report(self, mock_handlers: MCPHandlers) -> None:
        """Test handling of missing markdown report."""
        arguments = {
            "project_id": "test-project",
            "dataset_id": "test_dataset",
            "table_id": "nonexistent_table",
        }

        # Should handle gracefully
        result = await mock_handlers.handle_get_asset_details(arguments)

        assert result is not None

    async def test_pagination_support(self, mock_handlers: MCPHandlers) -> None:
        """Test pagination in query results."""
        arguments = {
            "query": "find tables",
            "page_size": 5,
            "page_token": "token123",
        }

        mock_handlers.vertex_client.search = AsyncMock(return_value=[])

        result = await mock_handlers.handle_query_data_assets(arguments)

        assert result is not None

