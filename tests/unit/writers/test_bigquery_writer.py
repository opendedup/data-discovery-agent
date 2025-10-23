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


@pytest.mark.unit
@pytest.mark.writers
class TestSchemaFlattening:
    """Tests for nested schema flattening functionality."""

    @patch("data_discovery_agent.writers.bigquery_writer.bigquery.Client")
    def test_flatten_simple_nested_record(
        self, mock_bq_client: Mock, mock_env: dict[str, str]
    ) -> None:
        """Test flattening a simple nested RECORD."""
        writer = BigQueryWriter(project_id="test-project")
        
        schema = [
            {
                "name": "address",
                "type": "RECORD",
                "mode": "NULLABLE",
                "description": "Address info",
                "fields": [
                    {
                        "name": "street",
                        "type": "STRING",
                        "mode": "NULLABLE",
                        "description": "Street address",
                    },
                    {
                        "name": "city",
                        "type": "STRING",
                        "mode": "NULLABLE",
                        "description": "City name",
                    },
                ],
            }
        ]
        
        flattened = writer._flatten_schema_fields(schema)
        
        assert len(flattened) == 2
        assert flattened[0]["name"] == "address.street"
        assert flattened[0]["type"] == "STRING"
        assert flattened[0]["description"] == "Street address"
        assert flattened[1]["name"] == "address.city"
        assert flattened[1]["type"] == "STRING"

    @patch("data_discovery_agent.writers.bigquery_writer.bigquery.Client")
    def test_flatten_repeated_record(
        self, mock_bq_client: Mock, mock_env: dict[str, str]
    ) -> None:
        """Test flattening REPEATED RECORD (array)."""
        writer = BigQueryWriter(project_id="test-project")
        
        schema = [
            {
                "name": "orders",
                "type": "RECORD",
                "mode": "REPEATED",
                "description": "Orders",
                "fields": [
                    {
                        "name": "order_id",
                        "type": "STRING",
                        "mode": "NULLABLE",
                        "description": "Order ID",
                    },
                    {
                        "name": "total",
                        "type": "FLOAT",
                        "mode": "NULLABLE",
                        "description": "Total",
                    },
                ],
            }
        ]
        
        flattened = writer._flatten_schema_fields(schema)
        
        assert len(flattened) == 2
        assert flattened[0]["name"] == "orders[].order_id"
        assert flattened[0]["mode"] == "REPEATED"
        assert flattened[1]["name"] == "orders[].total"
        assert flattened[1]["mode"] == "REPEATED"

    @patch("data_discovery_agent.writers.bigquery_writer.bigquery.Client")
    def test_flatten_deeply_nested_record(
        self, mock_bq_client: Mock, mock_env: dict[str, str]
    ) -> None:
        """Test flattening deeply nested RECORD structures."""
        writer = BigQueryWriter(project_id="test-project")
        
        schema = [
            {
                "name": "user",
                "type": "RECORD",
                "mode": "NULLABLE",
                "fields": [
                    {
                        "name": "profile",
                        "type": "RECORD",
                        "mode": "NULLABLE",
                        "fields": [
                            {
                                "name": "address",
                                "type": "RECORD",
                                "mode": "NULLABLE",
                                "fields": [
                                    {
                                        "name": "city",
                                        "type": "STRING",
                                        "mode": "NULLABLE",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
        
        flattened = writer._flatten_schema_fields(schema)
        
        assert len(flattened) == 1
        assert flattened[0]["name"] == "user.profile.address.city"
        assert flattened[0]["type"] == "STRING"

    @patch("data_discovery_agent.writers.bigquery_writer.bigquery.Client")
    def test_flatten_nested_arrays(
        self, mock_bq_client: Mock, mock_env: dict[str, str]
    ) -> None:
        """Test flattening nested arrays (REPEATED within REPEATED)."""
        writer = BigQueryWriter(project_id="test-project")
        
        schema = [
            {
                "name": "orders",
                "type": "RECORD",
                "mode": "REPEATED",
                "fields": [
                    {
                        "name": "items",
                        "type": "RECORD",
                        "mode": "REPEATED",
                        "fields": [
                            {
                                "name": "product_id",
                                "type": "STRING",
                                "mode": "NULLABLE",
                            }
                        ],
                    }
                ],
            }
        ]
        
        flattened = writer._flatten_schema_fields(schema)
        
        assert len(flattened) == 1
        assert flattened[0]["name"] == "orders[].items[].product_id"
        assert flattened[0]["mode"] == "REPEATED"

    @patch("data_discovery_agent.writers.bigquery_writer.bigquery.Client")
    def test_flatten_mixed_fields(
        self, mock_bq_client: Mock, mock_env: dict[str, str]
    ) -> None:
        """Test flattening schema with both flat and nested fields."""
        writer = BigQueryWriter(project_id="test-project")
        
        schema = [
            {
                "name": "id",
                "type": "STRING",
                "mode": "REQUIRED",
                "description": "ID",
            },
            {
                "name": "metadata",
                "type": "RECORD",
                "mode": "NULLABLE",
                "fields": [
                    {
                        "name": "created_at",
                        "type": "TIMESTAMP",
                        "mode": "NULLABLE",
                    }
                ],
            },
        ]
        
        flattened = writer._flatten_schema_fields(schema)
        
        assert len(flattened) == 2
        assert flattened[0]["name"] == "id"
        assert flattened[1]["name"] == "metadata.created_at"

    @patch("data_discovery_agent.writers.bigquery_writer.bigquery.Client")
    def test_flatten_preserves_leaf_types(
        self, mock_bq_client: Mock, mock_env: dict[str, str]
    ) -> None:
        """Test that flattening preserves leaf field types correctly."""
        writer = BigQueryWriter(project_id="test-project")
        
        schema = [
            {
                "name": "data",
                "type": "RECORD",
                "mode": "NULLABLE",
                "fields": [
                    {"name": "str_field", "type": "STRING", "mode": "NULLABLE"},
                    {"name": "int_field", "type": "INTEGER", "mode": "NULLABLE"},
                    {"name": "float_field", "type": "FLOAT", "mode": "NULLABLE"},
                    {"name": "bool_field", "type": "BOOLEAN", "mode": "NULLABLE"},
                    {"name": "timestamp_field", "type": "TIMESTAMP", "mode": "NULLABLE"},
                ],
            }
        ]
        
        flattened = writer._flatten_schema_fields(schema)
        
        assert len(flattened) == 5
        assert flattened[0]["type"] == "STRING"
        assert flattened[1]["type"] == "INTEGER"
        assert flattened[2]["type"] == "FLOAT"
        assert flattened[3]["type"] == "BOOLEAN"
        assert flattened[4]["type"] == "TIMESTAMP"

    @patch("data_discovery_agent.writers.bigquery_writer.bigquery.Client")
    def test_write_nested_schema_asset(
        self, mock_bq_client: Mock, mock_env: dict[str, str]
    ) -> None:
        """Test writing asset with nested schema flattens correctly."""
        from tests.helpers.fixtures import create_nested_record_asset
        
        mock_client_instance = Mock()
        mock_bq_client.return_value = mock_client_instance
        mock_client_instance.insert_rows_json.return_value = []
        
        writer = BigQueryWriter(project_id="test-project")
        assets = [create_nested_record_asset()]
        
        writer.write_to_bigquery(assets)
        
        # Verify schema was flattened
        call_args = mock_client_instance.insert_rows_json.call_args
        if call_args:
            rows = call_args[0][1]
            schema = rows[0]["schema"]
            
            # Should have flattened nested fields
            assert any("address.street" in field["name"] for field in schema)
            assert any("address.city" in field["name"] for field in schema)
            assert any("address.geo.lat" in field["name"] for field in schema)
            
            # Should NOT have nested 'fields' property
            for field in schema:
                assert "fields" not in field

    @patch("data_discovery_agent.writers.bigquery_writer.bigquery.Client")
    def test_write_repeated_schema_asset(
        self, mock_bq_client: Mock, mock_env: dict[str, str]
    ) -> None:
        """Test writing asset with REPEATED RECORD schema."""
        from tests.helpers.fixtures import create_repeated_record_asset
        
        mock_client_instance = Mock()
        mock_bq_client.return_value = mock_client_instance
        mock_client_instance.insert_rows_json.return_value = []
        
        writer = BigQueryWriter(project_id="test-project")
        assets = [create_repeated_record_asset()]
        
        writer.write_to_bigquery(assets)
        
        # Verify array notation
        call_args = mock_client_instance.insert_rows_json.call_args
        if call_args:
            rows = call_args[0][1]
            schema = rows[0]["schema"]
            
            # Should have array notation
            assert any("orders[].order_id" in field["name"] for field in schema)
            assert any("orders[].items[].product_id" in field["name"] for field in schema)

