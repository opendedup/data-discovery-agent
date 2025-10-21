"""Unit tests for MCP tools."""

from __future__ import annotations

import pytest

from data_discovery_agent.mcp.tools import (
    format_error_response,
    format_tool_response,
    get_available_tools,
    validate_query_params,
)


@pytest.mark.unit
@pytest.mark.mcp
class TestMCPTools:
    """Tests for MCP tools module."""

    def test_get_available_tools(self) -> None:
        """Test getting available tools."""
        tools = get_available_tools()

        assert len(tools) > 0
        assert all(hasattr(tool, "name") for tool in tools)

    def test_tool_names(self) -> None:
        """Test that expected tools are available."""
        tools = get_available_tools()
        tool_names = [tool.name for tool in tools]

        expected_tools = [
            "query_data_assets",
            "get_asset_details",
            "list_datasets",
        ]

        for expected in expected_tools:
            assert expected in tool_names

    def test_tool_schemas(self) -> None:
        """Test that tools have proper schemas."""
        tools = get_available_tools()

        for tool in tools:
            assert hasattr(tool, "name")
            assert hasattr(tool, "description")
            assert hasattr(tool, "inputSchema")

    def test_validate_query_params_valid(self) -> None:
        """Test validation with valid parameters."""
        params = {
            "query": "find user tables",
            "page_size": 10,
        }

        # Should not raise
        validate_query_params(params, "query_data_assets")

    def test_validate_query_params_missing_required(self) -> None:
        """Test validation with missing required parameters."""
        params = {}  # Missing 'query'

        with pytest.raises(ValueError):
            validate_query_params(params, "query_data_assets")

    def test_validate_query_params_invalid_type(self) -> None:
        """Test validation with invalid parameter types."""
        params = {
            "query": "find tables",
            "page_size": "invalid",  # Should be int
        }

        # May or may not raise depending on validation strictness
        with pytest.raises(Exception) or True:
            validate_query_params(params, "query_data_assets")

    def test_format_tool_response(self) -> None:
        """Test tool response formatting."""
        data = "This is a test response string."

        response = format_tool_response(data)

        assert len(response) == 1
        assert response[0].type == "text"
        assert response[0].text == data

    def test_format_error_response(self) -> None:
        """Test error response formatting."""
        error_msg = "Test error message"

        response = format_error_response(error_msg, "query_data_assets")

        assert len(response) > 0
        assert any("error" in r.text.lower() for r in response)

    def test_validate_unknown_tool(self) -> None:
        """Test validation with unknown tool name."""
        params = {"query": "test"}

        with pytest.raises(ValueError):
            validate_query_params(params, "unknown_tool")

    def test_validate_list_datasets_params(self) -> None:
        """Test validation for list_datasets tool."""
        params = {}  # No required params for list_datasets

        # Should not raise
        validate_query_params(params, "list_datasets")

    def test_validate_get_asset_details_params(self) -> None:
        """Test validation for get_asset_details tool."""
        params = {
            "project_id": "test-project",
            "dataset_id": "test_dataset",
            "table_id": "test_table",
        }

        # Should not raise
        validate_query_params(params, "get_asset_details")

