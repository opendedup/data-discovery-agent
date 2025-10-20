"""Unit tests for lineage tracking utilities."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest

from data_discovery_agent.utils.lineage import (
    format_bigquery_fqn,
    record_lineage,
)

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture


@pytest.mark.unit
@pytest.mark.lineage
class TestLineageUtils:
    """Tests for lineage utility functions."""

    def test_format_bigquery_fqn(self) -> None:
        """Test BigQuery FQN formatting."""
        fqn = format_bigquery_fqn("test-project", "test_dataset", "test_table")

        assert fqn == "bigquery:test-project.test_dataset.test_table"

    def test_format_bigquery_fqn_with_special_chars(self) -> None:
        """Test FQN formatting with special characters."""
        fqn = format_bigquery_fqn("my-project", "my_dataset", "my-table")

        assert ":" in fqn
        assert "bigquery:" in fqn
        assert "my-project" in fqn

    @patch(
        "data_discovery_agent.utils.lineage.datacatalog_lineage_v1.LineageClient"
    )
    def test_record_lineage_success(self, mock_lineage_client: Mock) -> None:
        """Test successful lineage recording."""
        mock_client_instance = Mock()
        mock_lineage_client.return_value = mock_client_instance

        # Mock process creation
        mock_process = Mock()
        mock_process.name = "projects/test/locations/us-central1/processes/test-process"
        mock_client_instance.create_process.return_value = mock_process

        # Mock run creation
        mock_run = Mock()
        mock_run.name = f"{mock_process.name}/runs/test-run"
        mock_client_instance.create_run.return_value = mock_run

        # Mock event creation
        mock_event = Mock()
        mock_client_instance.create_lineage_event.return_value = mock_event

        # Record lineage
        record_lineage(
            project_id="test-project",
            location="us-central1",
            process_name="test-dag",
            task_id="test-task",
            source_fqn="bigquery:test-project.source.table",
            target_fqn="bigquery:test-project.target.table",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            is_success=True,
        )

        # Verify all steps were called
        assert mock_client_instance.create_process.called
        assert mock_client_instance.create_run.called
        assert mock_client_instance.create_lineage_event.called

    @patch(
        "data_discovery_agent.utils.lineage.datacatalog_lineage_v1.LineageClient"
    )
    def test_record_lineage_failure_state(
        self, mock_lineage_client: Mock
    ) -> None:
        """Test lineage recording with failure state."""
        mock_client_instance = Mock()
        mock_lineage_client.return_value = mock_client_instance

        mock_process = Mock()
        mock_process.name = "test-process"
        mock_client_instance.create_process.return_value = mock_process

        mock_run = Mock()
        mock_client_instance.create_run.return_value = mock_run

        # Record failed operation
        record_lineage(
            project_id="test-project",
            location="us-central1",
            process_name="test-dag",
            task_id="test-task",
            source_fqn="bigquery:test-project.source.table",
            target_fqn="bigquery:test-project.target.table",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            is_success=False,  # Failed
        )

        # Should still record lineage with FAILED state
        assert mock_client_instance.create_run.called

    @patch(
        "data_discovery_agent.utils.lineage.datacatalog_lineage_v1.LineageClient"
    )
    def test_multiple_lineage_events(self, mock_lineage_client: Mock) -> None:
        """Test recording multiple lineage events."""
        mock_client_instance = Mock()
        mock_lineage_client.return_value = mock_client_instance

        mock_process = Mock()
        mock_process.name = "test-process"
        mock_client_instance.create_process.return_value = mock_process

        mock_run = Mock()
        mock_run.name = "test-run"
        mock_client_instance.create_run.return_value = mock_run

        # Record multiple events
        for i in range(3):
            record_lineage(
                project_id="test-project",
                location="us-central1",
                process_name="test-dag",
                task_id="test-task",
                source_fqn=f"bigquery:test-project.source.table{i}",
                target_fqn="bigquery:test-project.target.table",
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
                is_success=True,
            )

        # Should create multiple events
        assert mock_client_instance.create_lineage_event.call_count >= 3

    @patch(
        "data_discovery_agent.utils.lineage.datacatalog_lineage_v1.LineageClient"
    )
    def test_handles_lineage_api_errors(
        self, mock_lineage_client: Mock
    ) -> None:
        """Test handling of lineage API errors."""
        mock_client_instance = Mock()
        mock_lineage_client.return_value = mock_client_instance

        # Simulate API error
        mock_client_instance.create_process.side_effect = Exception("API Error")

        # Should handle error gracefully
        with pytest.raises(Exception):
            record_lineage(
                project_id="test-project",
                location="us-central1",
                process_name="test-dag",
                task_id="test-task",
                source_fqn="bigquery:test-project.source.table",
                target_fqn="bigquery:test-project.target.table",
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
                is_success=True,
            )

    def test_fqn_validation(self) -> None:
        """Test FQN format validation."""
        valid_fqn = format_bigquery_fqn("project", "dataset", "table")

        assert ":" in valid_fqn
        assert valid_fqn.startswith("bigquery:")
        assert "." in valid_fqn

    @patch(
        "data_discovery_agent.utils.lineage.datacatalog_lineage_v1.LineageClient"
    )
    def test_process_attributes(self, mock_lineage_client: Mock) -> None:
        """Test process attributes are set correctly."""
        mock_client_instance = Mock()
        mock_lineage_client.return_value = mock_client_instance

        mock_process = Mock()
        mock_client_instance.create_process.return_value = mock_process

        mock_run = Mock()
        mock_client_instance.create_run.return_value = mock_run

        record_lineage(
            project_id="test-project",
            location="us-central1",
            process_name="metadata_collection_dag",
            task_id="export_to_bigquery",
            source_fqn="bigquery:test-project.source.table",
            target_fqn="bigquery:test-project.target.table",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            is_success=True,
        )

        # Verify process was created
        assert mock_client_instance.create_process.called

