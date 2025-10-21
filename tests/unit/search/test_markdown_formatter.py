"""Unit tests for MarkdownFormatter."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from data_discovery_agent.search.markdown_formatter import MarkdownFormatter
from tests.helpers.assertions import assert_valid_markdown
from tests.helpers.fixtures import create_sample_asset_schema


@pytest.mark.unit
@pytest.mark.formatters
class TestMarkdownFormatter:
    """Tests for MarkdownFormatter class."""

    def test_init(self) -> None:
        """Test formatter initialization."""
        formatter = MarkdownFormatter(project_id="test-project")

        assert formatter is not None
        assert formatter.project_id == "test-project"

    def test_format_table_markdown(self, sample_table_metadata: dict) -> None:
        """Test markdown generation for a table."""
        formatter = MarkdownFormatter(project_id="test-project")
        asset = create_sample_asset_schema()

        markdown = formatter.generate_table_report(asset)

        assert markdown is not None
        assert isinstance(markdown, str)
        assert len(markdown) > 0

    def test_markdown_structure(self, sample_table_metadata: dict) -> None:
        """Test markdown has correct structure."""
        formatter = MarkdownFormatter(project_id="test-project")
        asset = create_sample_asset_schema()

        markdown = formatter.generate_table_report(asset)

        # Should have main sections
        assert "# " in markdown  # H1 header
        assert "## Overview" in markdown
        assert "## Schema" in markdown
        assert "## Key Metrics" in markdown

    def test_schema_table_formatting(self, sample_table_metadata: dict) -> None:
        """Test that schema is formatted as a table."""
        formatter = MarkdownFormatter(project_id="test-project")
        asset = create_sample_asset_schema()

        markdown = formatter.generate_table_report(asset)

        # Should contain markdown table syntax
        assert "|" in markdown
        assert "Column" in markdown or "column" in markdown.lower()
        assert "Type" in markdown or "type" in markdown.lower()
        assert "Description" in markdown or "description" in markdown.lower()

    def test_includes_table_metadata(self, sample_table_metadata: dict) -> None:
        """Test that table metadata is included."""
        formatter = MarkdownFormatter(project_id="test-project")
        asset = create_sample_asset_schema()

        markdown = formatter.generate_table_report(asset)

        # Should include project, dataset, table IDs
        assert "test_dataset" in markdown
        assert "test_table" in markdown

    def test_includes_statistics(self, sample_table_metadata: dict) -> None:
        """Test that statistics are included."""
        formatter = MarkdownFormatter(project_id="test-project")
        asset = create_sample_asset_schema()

        markdown = formatter.generate_table_report(asset)

        # Should include statistics
        assert "Row" in markdown or "row" in markdown.lower()
        assert "Size" in markdown or "size" in markdown.lower()

    def test_markdown_syntax_validity(self, sample_table_metadata: dict) -> None:
        """Test that generated markdown is syntactically valid."""
        formatter = MarkdownFormatter(project_id="test-project")
        asset = create_sample_asset_schema()

        markdown = formatter.generate_table_report(asset)

        # Use our custom assertion
        assert_valid_markdown(
            markdown, f"{asset.get('dataset_id')}.{asset.get('table_id')}"
        )

    @patch("data_discovery_agent.search.markdown_formatter.storage.Client")
    def test_upload_to_gcs(self, mock_storage_client: Mock) -> None:
        """Test uploading markdown to GCS."""
        mock_client_instance = mock_storage_client.return_value

        mock_bucket = Mock()
        mock_blob = Mock()
        mock_bucket.blob.return_value = mock_blob
        mock_client_instance.bucket.return_value = mock_bucket

        formatter = MarkdownFormatter(project_id="test-project")
        asset = create_sample_asset_schema()

        markdown = formatter.generate_table_report(asset)
        
        gcs_uri = formatter.export_to_gcs(markdown, "test-bucket", "test-path.md")

        assert mock_blob.upload_from_string.called
        assert gcs_uri == "gs://test-bucket/test-path.md"

    def test_handles_view_formatting(self, sample_view_metadata: dict) -> None:
        """Test formatting a view differently from a table."""
        formatter = MarkdownFormatter(project_id="test-project")
        
        view_asset = create_sample_asset_schema()
        view_asset["table_type"] = "VIEW"
        view_asset["row_count"] = 0
        view_asset["size_bytes"] = 0

        markdown = formatter.generate_table_report(view_asset)

        assert markdown is not None
        assert "[VIEW]" in markdown

    def test_includes_column_descriptions(self, sample_table_metadata: dict) -> None:
        """Test that column descriptions are included."""
        formatter = MarkdownFormatter(project_id="test-project")
        asset = create_sample_asset_schema()

        markdown = formatter.generate_table_report(asset)

        # Should include column descriptions
        schema = asset.get("schema", [])
        for field in schema:
            column_name = field.get("name")
            if column_name:
                assert column_name in markdown

    def test_formatting_with_special_characters(self) -> None:
        """Test markdown generation with special characters."""
        formatter = MarkdownFormatter(project_id="test-project")
        asset = create_sample_asset_schema()
        
        # Add special characters to description
        asset["description"] = "Table with | pipes and `backticks`"

        markdown = formatter.generate_table_report(asset)

        assert markdown is not None
        # Special characters should be handled properly
        assert "Table with | pipes and `backticks`" in markdown

    def test_empty_schema_handling(self) -> None:
        """Test handling of tables with empty schema."""
        formatter = MarkdownFormatter(project_id="test-project")
        asset = create_sample_asset_schema()
        asset["schema"] = []

        markdown = formatter.generate_table_report(asset)

        assert markdown is not None
        # Should still generate valid markdown

