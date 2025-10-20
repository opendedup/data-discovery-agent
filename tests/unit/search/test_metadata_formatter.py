"""Unit tests for MetadataFormatter."""

from __future__ import annotations

import pytest

from data_discovery_agent.search.metadata_formatter import MetadataFormatter
from data_discovery_agent.search.jsonl_schema import BigQueryAssetSchema
from tests.helpers.assertions import assert_valid_bigquery_asset


@pytest.mark.unit
@pytest.mark.formatters
class TestMetadataFormatter:
    """Tests for MetadataFormatter class."""

    def test_init(self) -> None:
        """Test formatter initialization."""
        formatter = MetadataFormatter(project_id="test-project")

        assert formatter.project_id == "test-project"

    def test_format_bigquery_table_basic(
        self, sample_table_metadata: dict
    ) -> None:
        """Test basic BigQuery table formatting."""
        formatter = MetadataFormatter(project_id="test-project")

        asset = formatter.format_bigquery_table(table_metadata=sample_table_metadata)

        assert isinstance(asset, BigQueryAssetSchema)
        assert asset.id == "test-project.test_dataset.test_table"
        assert asset.structData["table_type"] == "TABLE"
        assert asset.structData["description"] == "Test table description"

    def test_format_bigquery_table_with_schema(
        self, sample_table_metadata: dict
    ) -> None:
        """Test formatting with schema information."""
        formatter = MetadataFormatter(project_id="test-project")

        schema_info = {
            "fields": sample_table_metadata["schema"],
        }

        asset = formatter.format_bigquery_table(
            table_metadata=sample_table_metadata, schema_info=schema_info
        )

        assert asset.structData.get("schema") is not None
        schema = asset.structData["schema"]
        assert len(schema) == 3
        assert schema[0]["column_name"] == "id"

    def test_format_bigquery_view(self, sample_view_metadata: dict) -> None:
        """Test formatting a BigQuery view."""
        formatter = MetadataFormatter(project_id="test-project")

        asset = formatter.format_bigquery_table(table_metadata=sample_view_metadata)

        assert isinstance(asset, BigQueryAssetSchema)
        assert asset.structData["table_type"] == "VIEW"
        # Views may have 0 rows/bytes
        assert asset.structData.get("row_count") == 0
        assert asset.structData.get("size_bytes") == 0

    def test_content_text_generation(self, sample_table_metadata: dict) -> None:
        """Test that content text is generated for search."""
        formatter = MetadataFormatter(project_id="test-project")

        asset = formatter.format_bigquery_table(table_metadata=sample_table_metadata)

        # Content should be generated for search indexing
        assert asset.content is not None
        assert asset.content.get("mimeType") == "text/plain"

    def test_handles_missing_optional_fields(self) -> None:
        """Test handling of missing optional fields."""
        formatter = MetadataFormatter(project_id="test-project")

        minimal_metadata = {
            "project_id": "test-project",
            "dataset_id": "test_dataset",
            "table_id": "test_table",
            "table_type": "TABLE",
            "description": "Minimal table",
            "created": "2024-01-01T00:00:00Z",
            "modified": "2024-10-20T00:00:00Z",
            "schema": [],
        }

        asset = formatter.format_bigquery_table(table_metadata=minimal_metadata)

        assert asset.id == "test-project.test_dataset.test_table"
        assert asset.structData["description"] == "Minimal table"

    def test_id_generation(self, sample_table_metadata: dict) -> None:
        """Test ID generation format."""
        formatter = MetadataFormatter(project_id="test-project")

        asset = formatter.format_bigquery_table(table_metadata=sample_table_metadata)

        expected_id = "test-project.test_dataset.test_table"
        assert asset.id == expected_id

    def test_format_with_security_info(self, sample_table_metadata: dict) -> None:
        """Test formatting with security information."""
        formatter = MetadataFormatter(project_id="test-project")

        security_info = {
            "has_policy_tags": True,
            "policy_tags": ["sensitive_data"],
        }

        asset = formatter.format_bigquery_table(
            table_metadata=sample_table_metadata, security_info=security_info
        )

        # Security info should be included in structData
        assert asset.structData is not None

    def test_format_with_quality_info(self, sample_table_metadata: dict) -> None:
        """Test formatting with data quality information."""
        formatter = MetadataFormatter(project_id="test-project")

        quality_info = {
            "null_ratio": 0.05,
            "completeness_score": 0.95,
        }

        asset = formatter.format_bigquery_table(
            table_metadata=sample_table_metadata, quality_info=quality_info
        )

        assert asset.structData is not None

    def test_validates_output_schema(self, sample_table_metadata: dict) -> None:
        """Test that output follows BigQueryAssetSchema."""
        formatter = MetadataFormatter(project_id="test-project")

        asset = formatter.format_bigquery_table(table_metadata=sample_table_metadata)

        # Use our custom assertion
        assert_valid_bigquery_asset(asset, table_type="TABLE")

    def test_nested_schema_formatting(self) -> None:
        """Test formatting of nested/complex schemas."""
        formatter = MetadataFormatter(project_id="test-project")

        metadata_with_nested = {
            "project_id": "test-project",
            "dataset_id": "test_dataset",
            "table_id": "test_table",
            "table_type": "TABLE",
            "description": "Table with nested schema",
            "created": "2024-01-01T00:00:00Z",
            "modified": "2024-10-20T00:00:00Z",
            "schema": [
                {
                    "name": "user",
                    "type": "RECORD",
                    "mode": "NULLABLE",
                    "description": "User information",
                    "fields": [
                        {
                            "name": "id",
                            "type": "STRING",
                            "mode": "REQUIRED",
                            "description": "User ID",
                        },
                        {
                            "name": "email",
                            "type": "STRING",
                            "mode": "NULLABLE",
                            "description": "User email",
                        },
                    ],
                }
            ],
        }

        asset = formatter.format_bigquery_table(table_metadata=metadata_with_nested)

        assert asset.structData is not None
        # Should handle nested fields appropriately

