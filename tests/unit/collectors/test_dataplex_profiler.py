"""Unit tests for DataplexProfiler."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest
from google.api_core.exceptions import NotFound

from data_discovery_agent.collectors.dataplex_profiler import DataplexProfiler
from tests.helpers.fixtures import create_sample_profile_result

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture


@pytest.mark.unit
@pytest.mark.collectors
class TestDataplexProfiler:
    """Tests for DataplexProfiler class."""

    def test_init(self) -> None:
        """Test profiler initialization."""
        profiler = DataplexProfiler(
            project_id="test-project", location="us-central1"
        )

        assert profiler.project_id == "test-project"
        assert profiler.location == "us-central1"
        assert profiler.client is not None

    @patch(
        "data_discovery_agent.collectors.dataplex_profiler.dataplex_v1.DataScanServiceClient"
    )
    def test_get_profile_scan_success(self, mock_client_class: Mock) -> None:
        """Test successful profile scan retrieval."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Create mock scan response
        mock_scan = Mock()
        mock_scan.name = "test-scan"
        mock_scan.data_profile_result = create_sample_profile_result()
        mock_client.get_data_scan.return_value = mock_scan

        profiler = DataplexProfiler(project_id="test-project")
        result = profiler.get_profile_scan_for_table("test_dataset", "test_table")

        assert result is not None
        assert "row_count" in result

    @patch(
        "data_discovery_agent.collectors.dataplex_profiler.dataplex_v1.DataScanServiceClient"
    )
    def test_get_profile_scan_not_found(self, mock_client_class: Mock) -> None:
        """Test profile scan retrieval when scan doesn't exist."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Simulate NotFound error
        mock_client.get_data_scan.side_effect = NotFound("Scan not found")

        profiler = DataplexProfiler(project_id="test-project")
        result = profiler.get_profile_scan_for_table("test_dataset", "test_table")

        assert result is None

    @patch(
        "data_discovery_agent.collectors.dataplex_profiler.dataplex_v1.DataScanServiceClient"
    )
    def test_parse_profile_result(self, mock_client_class: Mock) -> None:
        """Test parsing of profile results."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_scan = Mock()
        profile_data = create_sample_profile_result()
        mock_scan.data_profile_result = profile_data
        mock_client.get_data_scan.return_value = mock_scan

        profiler = DataplexProfiler(project_id="test-project")
        result = profiler.get_profile_scan_for_table("test_dataset", "test_table")

        assert result is not None
        assert result["row_count"] == 1000
        assert "profile" in result
        assert "fields" in result["profile"]

    @patch(
        "data_discovery_agent.collectors.dataplex_profiler.dataplex_v1.DataScanServiceClient"
    )
    def test_extract_column_statistics(self, mock_client_class: Mock) -> None:
        """Test extraction of column statistics from profile."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_scan = Mock()
        profile_data = create_sample_profile_result()
        mock_scan.data_profile_result = profile_data
        mock_client.get_data_scan.return_value = mock_scan

        profiler = DataplexProfiler(project_id="test-project")
        result = profiler.get_profile_scan_for_table("test_dataset", "test_table")

        assert result is not None
        fields = result["profile"]["fields"]
        assert len(fields) > 0

        # Check first field
        id_field = fields[0]
        assert id_field["name"] == "id"
        assert id_field["profile"]["null_ratio"] == 0.0
        assert id_field["profile"]["distinct_ratio"] == 1.0

    @patch(
        "data_discovery_agent.collectors.dataplex_profiler.dataplex_v1.DataScanServiceClient"
    )
    def test_pii_detection(self, mock_client_class: Mock) -> None:
        """Test PII detection in profile results."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_scan = Mock()
        profile_data = create_sample_profile_result()
        mock_scan.data_profile_result = profile_data
        mock_client.get_data_scan.return_value = mock_scan

        profiler = DataplexProfiler(project_id="test-project")
        result = profiler.get_profile_scan_for_table("test_dataset", "test_table")

        assert result is not None
        fields = result["profile"]["fields"]

        # Find email field which should have PII detected
        email_field = next((f for f in fields if f["name"] == "email"), None)
        assert email_field is not None
        assert "info_types" in email_field
        assert email_field["info_types"][0]["name"] == "EMAIL_ADDRESS"

    @patch(
        "data_discovery_agent.collectors.dataplex_profiler.dataplex_v1.DataScanServiceClient"
    )
    def test_handles_api_errors(self, mock_client_class: Mock) -> None:
        """Test handling of API errors."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Simulate generic API error
        mock_client.get_data_scan.side_effect = Exception("API Error")

        profiler = DataplexProfiler(project_id="test-project")

        # Should not crash, should return None or handle gracefully
        with pytest.raises(Exception):
            profiler.get_profile_scan_for_table("test_dataset", "test_table")

