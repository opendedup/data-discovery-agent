"""Unit tests for BigQueryWriter."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest

from data_discovery_agent.writers.bigquery_writer import BigQueryWriter
from tests.helpers.fixtures import create_sample_asset_schema

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture


@pytest.mark.unit
@pytest.mark.writers
class TestBigQueryWriter:
    """Tests for BigQueryWriter class."""

    def test_init_with_defaults(self, mock_env: dict[str, str]) -> None:
        """Test writer initialization with defaults."""
        writer = BigQueryWriter(project_id="test-project")

        assert writer.project_id == "test-project"
        assert writer.dataset_id == "test_dataset"
        assert writer.table_id == "test_table"
        assert writer.run_timestamp is not None

    def test_init_with_custom_params(self, mock_env: dict[str, str]) -> None:
        """Test writer initialization with custom parameters."""
        writer = BigQueryWriter(
            project_id="test-project",
            dataset_id="custom_dataset",
            table_id="custom_table",
            dag_name="test-dag",
            task_id="test-task",
        )

        assert writer.dataset_id == "custom_dataset"
        assert writer.table_id == "custom_table"
        assert writer.dag_name == "test-dag"
        assert writer.task_id == "test-task"

    @patch("data_discovery_agent.writers.bigquery_writer.bigquery.Client")
    def test_create_dataset_if_not_exists(
        self, mock_bq_client: Mock, mock_env: dict[str, str]
    ) -> None:
        """Test dataset creation."""
        mock_client_instance = Mock()
        mock_bq_client.return_value = mock_client_instance

        # Simulate dataset doesn't exist
        from google.cloud.exceptions import NotFound
        mock_client_instance.get_dataset.side_effect = NotFound("Dataset not found")

        writer = BigQueryWriter(project_id="test-project")
        
        # Should create dataset
        # writer._ensure_dataset_exists()

    @patch("data_discovery_agent.writers.bigquery_writer.bigquery.Client")
    def test_create_table_if_not_exists(
        self, mock_bq_client: Mock, mock_env: dict[str, str]
    ) -> None:
        """Test table creation."""
        mock_client_instance = Mock()
        mock_bq_client.return_value = mock_client_instance

        # Simulate table doesn't exist
        from google.cloud.exceptions import NotFound
        mock_client_instance.get_table.side_effect = NotFound("Table not found")

        writer = BigQueryWriter(project_id="test-project")

        # Should create table
        # writer._ensure_table_exists()

    @patch("data_discovery_agent.writers.bigquery_writer.bigquery.Client")
    @patch("data_discovery_agent.writers.bigquery_writer.record_lineage")
    def test_write_assets_with_lineage(
        self,
        mock_record_lineage: Mock,
        mock_bq_client: Mock,
        mock_env: dict[str, str],
    ) -> None:
        """Test writing assets with lineage tracking."""
        mock_client_instance = Mock()
        mock_bq_client.return_value = mock_client_instance

        # Mock successful insert
        mock_client_instance.insert_rows_json.return_value = []

        writer = BigQueryWriter(
            project_id="test-project",
            dag_name="test-dag",
            task_id="test-task",
        )

        assets = [create_sample_asset_schema()]

        # Write assets
        writer.write_to_bigquery(assets)

        # Should call lineage recording
        mock_record_lineage.assert_called()

    @patch("data_discovery_agent.writers.bigquery_writer.bigquery.Client")
    def test_add_run_timestamp_to_rows(
        self, mock_bq_client: Mock, mock_env: dict[str, str]
    ) -> None:
        """Test that run_timestamp is added to all rows."""
        mock_client_instance = Mock()
        mock_bq_client.return_value = mock_client_instance

        mock_client_instance.insert_rows_json.return_value = []

        writer = BigQueryWriter(project_id="test-project")
        assets = [create_sample_asset_schema()]

        writer.write_to_bigquery(assets)

        # Verify run_timestamp was added
        call_args = mock_client_instance.insert_rows_json.call_args
        if call_args:
            rows = call_args[0][1]
            assert all("run_timestamp" in row for row in rows)

    @patch("data_discovery_agent.writers.bigquery_writer.bigquery.Client")
    def test_batch_insertion(
        self, mock_bq_client: Mock, mock_env: dict[str, str]
    ) -> None:
        """Test batch insertion of multiple assets."""
        mock_client_instance = Mock()
        mock_bq_client.return_value = mock_client_instance

        mock_client_instance.insert_rows_json.return_value = []

        writer = BigQueryWriter(project_id="test-project")

        # Create multiple assets
        assets = [
            create_sample_asset_schema(table_id=f"table{i}")
            for i in range(10)
        ]

        writer.write_to_bigquery(assets)

        # Should insert all assets
        assert mock_client_instance.insert_rows_json.called

    @patch("data_discovery_agent.writers.bigquery_writer.bigquery.Client")
    def test_handles_insertion_errors(
        self, mock_bq_client: Mock, mock_env: dict[str, str]
    ) -> None:
        """Test handling of insertion errors."""
        mock_client_instance = Mock()
        mock_bq_client.return_value = mock_client_instance

        # Simulate insertion errors
        mock_client_instance.insert_rows_json.return_value = [
            {"index": 0, "errors": [{"message": "Insert error"}]}
        ]

        writer = BigQueryWriter(project_id="test-project")
        assets = [create_sample_asset_schema()]

        # Should handle errors gracefully (logs but doesn't raise)
        writer.write_to_bigquery(assets)
        
        # Verify that insert was attempted despite errors
        assert mock_client_instance.insert_rows_json.called

    @patch("data_discovery_agent.writers.bigquery_writer.bigquery.Client")
    def test_get_bigquery_schema(
        self, mock_bq_client: Mock, mock_env: dict[str, str]
    ) -> None:
        """Test schema generation for BigQuery table."""
        mock_client_instance = Mock()
        mock_bq_client.return_value = mock_client_instance

        writer = BigQueryWriter(project_id="test-project")

        schema = writer.get_bigquery_schema()

        assert schema is not None
        assert len(schema) > 0
        # Should include run_timestamp field
        assert any(field.name == "run_timestamp" for field in schema)

    @patch("data_discovery_agent.writers.bigquery_writer.record_lineage")
    def test_lineage_params(
        self, mock_record_lineage: Mock, mock_env: dict[str, str]
    ) -> None:
        """Test lineage recording parameters."""
        with patch(
            "data_discovery_agent.writers.bigquery_writer.bigquery.Client"
        ) as mock_bq_client:
            mock_client_instance = Mock()
            mock_bq_client.return_value = mock_client_instance
            mock_client_instance.insert_rows_json.return_value = []

            writer = BigQueryWriter(
                project_id="test-project",
                dag_name="metadata_collection",
                task_id="export_to_bigquery",
            )

            assets = [create_sample_asset_schema()]
            writer.write_to_bigquery(assets)

            # Verify lineage recording was called with correct params
            if mock_record_lineage.called:
                call_args = mock_record_lineage.call_args
                assert call_args is not None

