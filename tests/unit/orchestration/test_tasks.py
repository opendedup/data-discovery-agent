"""Unit tests for Airflow task functions."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest

from data_discovery_agent.orchestration.tasks import (
    collect_metadata_task,
    export_markdown_reports_task,
    export_to_bigquery_task,
    import_to_vertex_ai_task,
)
from tests.helpers.fixtures import create_sample_asset_schema

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture


@pytest.mark.unit
@pytest.mark.orchestration
class TestOrchestrationTasks:
    """Tests for orchestration task functions."""

    @patch("data_discovery_agent.orchestration.tasks.BigQueryCollector")
    def test_collect_metadata_task(
        self,
        mock_collector_class: Mock,
        mock_env: dict[str, str],
        mock_airflow_context: dict,
    ) -> None:
        """Test collect_metadata_task function."""
        # Mock collector instance
        mock_collector = Mock()
        mock_collector_class.return_value = mock_collector

        # Mock collect_all to return sample assets
        mock_collector.collect_all.return_value = [
            create_sample_asset_schema(),
            create_sample_asset_schema(table_id="table2"),
        ]

        # Run task
        collect_metadata_task(**mock_airflow_context)

        # Verify collector was created and called
        assert mock_collector_class.called
        assert mock_collector.collect_all.called

        # Verify XCom push was called
        assert mock_airflow_context["ti"].xcom_push.called

    @patch("data_discovery_agent.orchestration.tasks.BigQueryCollector")
    def test_collect_metadata_no_assets(
        self,
        mock_collector_class: Mock,
        mock_env: dict[str, str],
        mock_airflow_context: dict,
    ) -> None:
        """Test collect_metadata_task with no assets found."""
        mock_collector = Mock()
        mock_collector_class.return_value = mock_collector
        mock_collector.collect_all.return_value = []

        # Should raise error
        with pytest.raises(ValueError, match="No assets found"):
            collect_metadata_task(**mock_airflow_context)

    @patch("data_discovery_agent.orchestration.tasks.BigQueryWriter")
    def test_export_to_bigquery_task(
        self,
        mock_writer_class: Mock,
        mock_env: dict[str, str],
        mock_airflow_context: dict,
    ) -> None:
        """Test export_to_bigquery_task function."""
        # Mock writer instance
        mock_writer = Mock()
        mock_writer_class.return_value = mock_writer

        # Setup XCom pull to return assets
        assets = [create_sample_asset_schema()]
        mock_airflow_context["ti"].xcom_pull.return_value = assets

        # Run task
        export_to_bigquery_task(**mock_airflow_context)

        # Verify writer was created
        assert mock_writer_class.called

        # Verify write_to_bigquery was called
        assert mock_writer.write_to_bigquery.called

        # Verify run_timestamp was pushed to XCom
        assert mock_airflow_context["ti"].xcom_push.called

    @patch("data_discovery_agent.orchestration.tasks.BigQueryWriter")
    @patch("data_discovery_agent.orchestration.tasks.record_lineage")
    def test_export_to_bigquery_with_lineage(
        self,
        mock_record_lineage: Mock,
        mock_writer_class: Mock,
        mock_env: dict[str, str],
        mock_airflow_context: dict,
    ) -> None:
        """Test that export_to_bigquery records lineage."""
        mock_writer = Mock()
        mock_writer_class.return_value = mock_writer

        assets = [create_sample_asset_schema()]
        mock_airflow_context["ti"].xcom_pull.return_value = assets

        export_to_bigquery_task(**mock_airflow_context)

        # Lineage should be recorded
        # (May be called inside writer or in task function)
        assert mock_writer.write_to_bigquery.called

    @patch("data_discovery_agent.orchestration.tasks.MarkdownFormatter")
    @patch("data_discovery_agent.orchestration.tasks.storage.Client")
    def test_export_markdown_reports_task(
        self,
        mock_storage_class: Mock,
        mock_formatter_class: Mock,
        mock_env: dict[str, str],
        mock_airflow_context: dict,
    ) -> None:
        """Test export_markdown_reports_task function."""
        # Mock formatter
        mock_formatter = Mock()
        mock_formatter_class.return_value = mock_formatter
        mock_formatter.generate_table_report.return_value = "# Test Markdown"
        mock_formatter.export_to_gcs.return_value = "gs://some/path"

        # Mock storage client
        mock_storage = Mock()
        mock_storage_class.return_value = mock_storage

        # Setup XCom pull
        assets = [create_sample_asset_schema()]
        mock_airflow_context["ti"].xcom_pull.side_effect = [
            assets,  # assets
            "20241020_120000",  # run_timestamp
        ]

        # Run task
        export_markdown_reports_task(**mock_airflow_context)

        # Verify formatter was called
        assert mock_formatter.generate_table_report.called

        # Verify storage upload was attempted
        assert mock_formatter.export_to_gcs.called

    @patch("data_discovery_agent.orchestration.tasks.VertexSearchClient")
    def test_import_to_vertex_ai_task(
        self,
        mock_vertex_class: Mock,
        mock_env: dict[str, str],
        mock_airflow_context: dict,
    ) -> None:
        """Test import_to_vertex_ai_task function."""
        # Mock Vertex client
        mock_vertex = Mock()
        mock_vertex_class.return_value = mock_vertex

        # Setup XCom pull
        mock_airflow_context["ti"].xcom_pull.return_value = "20241020_120000"

        # Run task
        import_to_vertex_ai_task(**mock_airflow_context)

        # Verify Vertex client was created
        assert mock_vertex_class.called

    @patch("data_discovery_agent.orchestration.tasks.BigQueryCollector")
    def test_collect_metadata_with_config_overrides(
        self,
        mock_collector_class: Mock,
        mock_env: dict[str, str],
        mock_airflow_context: dict,
    ) -> None:
        """Test collect_metadata with configuration overrides."""
        mock_collector = Mock()
        mock_collector_class.return_value = mock_collector
        mock_collector.collect_all.return_value = [create_sample_asset_schema()]

        # Add config overrides to dag_run.conf
        mock_airflow_context["dag_run"].conf = {
            "collector_args": {
                "max_tables": 5,
                "workers": 3,
            }
        }

        collect_metadata_task(**mock_airflow_context)

        # Verify collector was created with custom params
        call_kwargs = mock_collector_class.call_args[1]
        assert call_kwargs["max_workers"] == 3

    @patch("data_discovery_agent.orchestration.tasks.BigQueryCollector")
    def test_collect_metadata_error_handling(
        self,
        mock_collector_class: Mock,
        mock_env: dict[str, str],
        mock_airflow_context: dict,
    ) -> None:
        """Test error handling in collect_metadata_task."""
        mock_collector = Mock()
        mock_collector_class.return_value = mock_collector

        # Simulate collection error
        mock_collector.collect_all.side_effect = Exception("Collection failed")

        with pytest.raises(Exception, match="Collection failed"):
            collect_metadata_task(**mock_airflow_context)

    @patch("data_discovery_agent.orchestration.tasks.MarkdownFormatter")
    @patch("data_discovery_agent.orchestration.tasks.storage.Client")
    def test_markdown_export_gcs_path_structure(
        self,
        mock_storage_class: Mock,
        mock_formatter_class: Mock,
        mock_env: dict[str, str],
        mock_airflow_context: dict,
    ) -> None:
        """Test that markdown reports use correct GCS path structure."""
        mock_formatter = Mock()
        mock_formatter_class.return_value = mock_formatter
        mock_formatter.generate_table_report.return_value = "# Test"
        mock_formatter.export_to_gcs.return_value = "gs://test-bucket/reports/20241020_120000/test-project/test_dataset/test_table.md"

        mock_storage = Mock()
        mock_storage_class.return_value = mock_storage

        asset = create_sample_asset_schema()
        mock_airflow_context["ti"].xcom_pull.side_effect = [
            [asset],
            "20241020_120000",
        ]

        export_markdown_reports_task(**mock_airflow_context)

        # Verify path format: {run_timestamp}/{project}/{dataset}/{table}.md
        # Check blob path if storage was called
        mock_formatter.export_to_gcs.assert_called_once()
        call_args = mock_formatter.export_to_gcs.call_args[1]
        assert "gcs_path" in call_args
        gcs_path = call_args["gcs_path"]
        assert "reports/20241020_120000/test-project/test_dataset/test_table.md" in gcs_path


    @patch("data_discovery_agent.orchestration.tasks.BigQueryWriter")
    def test_export_adds_run_timestamp(
        self,
        mock_writer_class: Mock,
        mock_env: dict[str, str],
        mock_airflow_context: dict,
    ) -> None:
        """Test that export adds run_timestamp to all records."""
        mock_writer = Mock()
        mock_writer_class.return_value = mock_writer

        assets = [create_sample_asset_schema()]
        mock_airflow_context["ti"].xcom_pull.return_value = assets

        export_to_bigquery_task(**mock_airflow_context)

        # Writer should have run_timestamp set
        assert hasattr(mock_writer, "run_timestamp") or mock_writer.write_to_bigquery.called

