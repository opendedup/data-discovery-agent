"""Unit tests for MCP configuration."""

from __future__ import annotations

import pytest

from data_discovery_agent.mcp.config import MCPConfig, load_config


@pytest.mark.unit
@pytest.mark.mcp
class TestMCPConfig:
    """Tests for MCP configuration."""

    def test_load_config_from_env(self, mock_env: dict[str, str]) -> None:
        """Test loading configuration from environment."""
        config = load_config()

        assert config.project_id == "test-project"
        assert config.vertex_datastore_id == "test-datastore"
        assert config.reports_bucket == "test-reports-bucket"

    def test_config_defaults(self, mock_env: dict[str, str]) -> None:
        """Test default configuration values."""
        config = load_config()

        assert config.mcp_server_name == "test-mcp-server"
        assert config.log_level == "INFO"

    def test_config_validation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test configuration validation."""
        # Remove required env var
        monkeypatch.delenv("GCP_PROJECT_ID", raising=False)

        # Should raise error for missing required field
        with pytest.raises(Exception):
            load_config()

    def test_custom_config_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test custom configuration values."""
        monkeypatch.setenv("GCP_PROJECT_ID", "custom-project")
        monkeypatch.setenv("VERTEX_DATASTORE_ID", "custom-datastore")
        monkeypatch.setenv("GCS_REPORTS_BUCKET", "custom-bucket")
        monkeypatch.setenv("VERTEX_LOCATION", "us-west1")
        monkeypatch.setenv("BQ_DATASET", "custom_dataset")
        monkeypatch.setenv("BQ_TABLE", "custom_table")

        config = load_config()

        assert config.project_id == "custom-project"
        assert config.vertex_datastore_id == "custom-datastore"
        assert config.vertex_location == "us-west1"

    def test_mcp_config_model(self) -> None:
        """Test MCPConfig model creation."""
        config = MCPConfig(
            project_id="test-project",
            vertex_datastore_id="test-datastore",
            vertex_location="global",
            reports_bucket="test-bucket",
            mcp_server_name="test-server",
            mcp_server_version="1.0.0",
        )

        assert config.project_id == "test-project"
        assert config.vertex_datastore_id == "test-datastore"

    def test_optional_fields(self, mock_env: dict[str, str]) -> None:
        """Test optional configuration fields."""
        config = load_config()

        # These may or may not be set
        assert hasattr(config, "log_level")
        assert hasattr(config, "mcp_server_version")

