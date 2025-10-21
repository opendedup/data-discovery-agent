"""
Tests for label-based filtering in BigQueryCollector.

Tests hierarchical filtering logic where table labels override dataset labels.
"""

from typing import TYPE_CHECKING

import pytest
from unittest.mock import Mock, patch, MagicMock

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture

from data_discovery_agent.collectors.bigquery_collector import BigQueryCollector


class TestLabelFiltering:
    """Test label-based filtering functionality."""
    
    def test_should_filter_by_label_with_true_value(self) -> None:
        """Test that label with 'true' value triggers filtering."""
        collector = BigQueryCollector(project_id="test-project")
        
        labels = {"ignore-gmcp-discovery-scan": "true"}
        assert collector._should_filter_by_label(labels) is True
    
    def test_should_filter_by_label_with_uppercase_true(self) -> None:
        """Test that label value is case-insensitive."""
        collector = BigQueryCollector(project_id="test-project")
        
        # Test various capitalizations
        assert collector._should_filter_by_label({"ignore-gmcp-discovery-scan": "TRUE"}) is True
        assert collector._should_filter_by_label({"ignore-gmcp-discovery-scan": "True"}) is True
        assert collector._should_filter_by_label({"ignore-gmcp-discovery-scan": "tRuE"}) is True
    
    def test_should_filter_by_label_with_false_value(self) -> None:
        """Test that label with 'false' value does not trigger filtering."""
        collector = BigQueryCollector(project_id="test-project")
        
        labels = {"ignore-gmcp-discovery-scan": "false"}
        assert collector._should_filter_by_label(labels) is False
    
    def test_should_filter_by_label_with_missing_label(self) -> None:
        """Test that missing label does not trigger filtering."""
        collector = BigQueryCollector(project_id="test-project")
        
        labels = {"some-other-label": "true"}
        assert collector._should_filter_by_label(labels) is False
    
    def test_should_filter_by_label_with_empty_labels(self) -> None:
        """Test that empty labels dict does not trigger filtering."""
        collector = BigQueryCollector(project_id="test-project")
        
        assert collector._should_filter_by_label({}) is False
    
    def test_should_filter_by_label_custom_key(self) -> None:
        """Test filtering with custom label key."""
        collector = BigQueryCollector(
            project_id="test-project",
            filter_label_key="custom-filter-key"
        )
        
        labels = {"custom-filter-key": "true"}
        assert collector._should_filter_by_label(labels) is True
        
        # Other label should not trigger filtering
        labels = {"ignore-gmcp-discovery-scan": "true"}
        assert collector._should_filter_by_label(labels) is False
    
    def test_should_filter_by_label_case_sensitive_key(self) -> None:
        """Test that label key is case-sensitive."""
        collector = BigQueryCollector(project_id="test-project")
        
        # Wrong case for key - should not filter
        labels = {"IGNORE-GMCP-DISCOVERY-SCAN": "true"}
        assert collector._should_filter_by_label(labels) is False
        
        # Correct case - should filter
        labels = {"ignore-gmcp-discovery-scan": "true"}
        assert collector._should_filter_by_label(labels) is True
    
    def test_get_dataset_labels_success(self, mocker: "MockerFixture") -> None:
        """Test successfully retrieving dataset labels."""
        collector = BigQueryCollector(project_id="test-project")
        
        # Mock dataset with labels
        mock_dataset = Mock()
        mock_dataset.labels = {"env": "prod", "ignore-gmcp-discovery-scan": "true"}
        
        mocker.patch.object(collector.client, 'get_dataset', return_value=mock_dataset)
        
        labels = collector._get_dataset_labels("test-project", "test_dataset")
        
        assert labels == {"env": "prod", "ignore-gmcp-discovery-scan": "true"}
        collector.client.get_dataset.assert_called_once_with("test-project.test_dataset")
    
    def test_get_dataset_labels_no_labels(self, mocker: "MockerFixture") -> None:
        """Test retrieving dataset with no labels."""
        collector = BigQueryCollector(project_id="test-project")
        
        # Mock dataset without labels
        mock_dataset = Mock()
        mock_dataset.labels = None
        
        mocker.patch.object(collector.client, 'get_dataset', return_value=mock_dataset)
        
        labels = collector._get_dataset_labels("test-project", "test_dataset")
        
        assert labels == {}
    
    def test_get_dataset_labels_error(self, mocker: "MockerFixture") -> None:
        """Test handling error when retrieving dataset labels."""
        collector = BigQueryCollector(project_id="test-project")
        
        mocker.patch.object(
            collector.client, 
            'get_dataset', 
            side_effect=Exception("Dataset not found")
        )
        
        labels = collector._get_dataset_labels("test-project", "test_dataset")
        
        assert labels == {}


class TestHierarchicalFiltering:
    """Test hierarchical filtering logic (table labels override dataset labels)."""
    
    @patch('data_discovery_agent.collectors.bigquery_collector.bigquery.Client')
    def test_dataset_filtered_blocks_all_tables(self, mock_client_class: Mock) -> None:
        """Test that dataset with filter=true blocks all tables without explicit labels."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock dataset with filter label
        mock_dataset = Mock()
        mock_dataset.dataset_id = "filtered_dataset"
        mock_dataset.labels = {"ignore-gmcp-discovery-scan": "true"}
        
        # Mock list_datasets
        mock_client.list_datasets.return_value = [mock_dataset]
        mock_client.get_dataset.return_value = mock_dataset
        
        # Mock table without explicit label
        mock_table_ref = Mock()
        mock_table_ref.table_id = "table1"
        mock_table_ref.table_type = "TABLE"
        
        mock_table = Mock()
        mock_table.labels = None  # No explicit label on table
        
        mock_client.list_tables.return_value = [mock_table_ref]
        mock_client.get_table.return_value = mock_table
        
        collector = BigQueryCollector(project_id="test-project")
        assets = collector.collect_all()
        
        # Table should be filtered (no assets collected)
        assert len(assets) == 0
        assert collector.stats['tables_filtered_by_label'] == 1
    
    @patch('data_discovery_agent.collectors.bigquery_collector.bigquery.Client')
    def test_table_label_false_overrides_dataset_filter(self, mock_client_class: Mock) -> None:
        """Test that table with filter=false overrides dataset filter=true."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock dataset with filter label
        mock_dataset = Mock()
        mock_dataset.dataset_id = "filtered_dataset"
        mock_dataset.labels = {"ignore-gmcp-discovery-scan": "true"}
        
        mock_client.list_datasets.return_value = [mock_dataset]
        mock_client.get_dataset.return_value = mock_dataset
        
        # Mock table with explicit filter=false label
        mock_table_ref = Mock()
        mock_table_ref.table_id = "table1"
        mock_table_ref.table_type = "TABLE"
        
        # Setup complete mock table
        mock_table = Mock()
        mock_table.labels = {"ignore-gmcp-discovery-scan": "false"}
        
        mock_client.list_tables.return_value = [mock_table_ref]
        mock_client.get_table.return_value = mock_table
        
        collector = BigQueryCollector(project_id="test-project")
        
        # Mock _collect_table_metadata to avoid complex dependencies
        mock_asset = Mock()
        mock_asset.struct_data = Mock()
        mock_asset.struct_data.table_id = "table1"
        collector._collect_table_metadata = Mock(return_value=mock_asset)
        
        assets = collector.collect_all()
        
        # Table should be included (overrides dataset filter)
        assert len(assets) == 1
        assert collector.stats['tables_filtered_by_label'] == 0
        # Verify _collect_table_metadata was called (table was processed)
        collector._collect_table_metadata.assert_called_once()
    
    @patch('data_discovery_agent.collectors.bigquery_collector.bigquery.Client')
    def test_table_label_true_filters_even_with_dataset_allowed(
        self, 
        mock_client_class: Mock
    ) -> None:
        """Test that table with filter=true is filtered even if dataset allows it."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock dataset WITHOUT filter label (should allow tables)
        mock_dataset = Mock()
        mock_dataset.dataset_id = "normal_dataset"
        mock_dataset.labels = None
        
        mock_client.list_datasets.return_value = [mock_dataset]
        mock_client.get_dataset.return_value = mock_dataset
        
        # Mock table with explicit filter=true label
        mock_table_ref = Mock()
        mock_table_ref.table_id = "filtered_table"
        mock_table_ref.table_type = "TABLE"
        
        mock_table = Mock()
        mock_table.labels = {"ignore-gmcp-discovery-scan": "true"}
        
        mock_client.list_tables.return_value = [mock_table_ref]
        mock_client.get_table.return_value = mock_table
        
        collector = BigQueryCollector(project_id="test-project")
        assets = collector.collect_all()
        
        # Table should be filtered
        assert len(assets) == 0
        assert collector.stats['tables_filtered_by_label'] == 1
    
    @patch('data_discovery_agent.collectors.bigquery_collector.bigquery.Client')
    def test_dataset_not_filtered_includes_tables_without_labels(
        self, 
        mock_client_class: Mock
    ) -> None:
        """Test that tables without labels are included when dataset is not filtered."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock dataset WITHOUT filter label
        mock_dataset = Mock()
        mock_dataset.dataset_id = "normal_dataset"
        mock_dataset.labels = None
        
        mock_client.list_datasets.return_value = [mock_dataset]
        mock_client.get_dataset.return_value = mock_dataset
        
        # Mock table without explicit label
        mock_table_ref = Mock()
        mock_table_ref.table_id = "table1"
        mock_table_ref.table_type = "TABLE"
        
        mock_table = Mock()
        mock_table.labels = None
        
        mock_client.list_tables.return_value = [mock_table_ref]
        mock_client.get_table.return_value = mock_table
        
        collector = BigQueryCollector(project_id="test-project")
        
        # Mock _collect_table_metadata to avoid complex dependencies
        mock_asset = Mock()
        mock_asset.struct_data = Mock()
        mock_asset.struct_data.table_id = "table1"
        collector._collect_table_metadata = Mock(return_value=mock_asset)
        
        assets = collector.collect_all()
        
        # Table should be included
        assert len(assets) == 1
        assert collector.stats['tables_filtered_by_label'] == 0
        # Verify _collect_table_metadata was called (table was processed)
        collector._collect_table_metadata.assert_called_once()
    
    @patch('data_discovery_agent.collectors.bigquery_collector.bigquery.Client')
    def test_mixed_tables_in_filtered_dataset(self, mock_client_class: Mock) -> None:
        """Test mix of filtered and allowed tables in a filtered dataset."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock dataset with filter label
        mock_dataset = Mock()
        mock_dataset.dataset_id = "filtered_dataset"
        mock_dataset.labels = {"ignore-gmcp-discovery-scan": "true"}
        
        mock_client.list_datasets.return_value = [mock_dataset]
        mock_client.get_dataset.return_value = mock_dataset
        
        # Mock 3 tables:
        # 1. No label (should be filtered by dataset)
        # 2. filter=false (should be included, overrides dataset)
        # 3. filter=true (should be filtered)
        
        mock_table_ref1 = Mock()
        mock_table_ref1.table_id = "table_no_label"
        mock_table_ref1.table_type = "TABLE"
        
        mock_table_ref2 = Mock()
        mock_table_ref2.table_id = "table_explicit_false"
        mock_table_ref2.table_type = "TABLE"
        
        mock_table_ref3 = Mock()
        mock_table_ref3.table_id = "table_explicit_true"
        mock_table_ref3.table_type = "TABLE"
        
        mock_client.list_tables.return_value = [
            mock_table_ref1, 
            mock_table_ref2, 
            mock_table_ref3
        ]
        
        # Setup get_table to return different labels for each
        def get_table_side_effect(table_ref: str) -> Mock:
            mock_table = Mock()
            
            # Determine table ID from reference
            if "table_no_label" in table_ref:
                mock_table.labels = None
            elif "table_explicit_false" in table_ref:
                mock_table.labels = {"ignore-gmcp-discovery-scan": "false"}
            elif "table_explicit_true" in table_ref:
                mock_table.labels = {"ignore-gmcp-discovery-scan": "true"}
            
            return mock_table
        
        mock_client.get_table.side_effect = get_table_side_effect
        
        collector = BigQueryCollector(project_id="test-project")
        
        # Mock _collect_table_metadata to track which tables get processed
        def mock_collect_metadata(proj_id: str, dataset_id: str, table_id: str) -> Mock:
            mock_asset = Mock()
            mock_asset.struct_data = Mock()
            mock_asset.struct_data.table_id = table_id
            return mock_asset
        
        collector._collect_table_metadata = Mock(side_effect=mock_collect_metadata)
        
        assets = collector.collect_all()
        
        # Only table_explicit_false should be included
        assert len(assets) == 1
        assert assets[0].struct_data.table_id == "table_explicit_false"
        assert collector.stats['tables_filtered_by_label'] == 2
        # Verify _collect_table_metadata was called only once for the allowed table
        assert collector._collect_table_metadata.call_count == 1


class TestFilteringStatistics:
    """Test that filtering statistics are correctly tracked."""
    
    @patch('data_discovery_agent.collectors.bigquery_collector.bigquery.Client')
    def test_statistics_tracking(self, mock_client_class: Mock) -> None:
        """Test that filtering statistics are correctly updated."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock dataset with filter label
        mock_dataset = Mock()
        mock_dataset.dataset_id = "test_dataset"
        mock_dataset.labels = {"ignore-gmcp-discovery-scan": "true"}
        
        mock_client.list_datasets.return_value = [mock_dataset]
        mock_client.get_dataset.return_value = mock_dataset
        
        # Mock 5 tables, all should be filtered
        mock_tables = []
        for i in range(5):
            mock_table_ref = Mock()
            mock_table_ref.table_id = f"table{i}"
            mock_table_ref.table_type = "TABLE"
            mock_tables.append(mock_table_ref)
        
        mock_client.list_tables.return_value = mock_tables
        
        mock_table = Mock()
        mock_table.labels = None  # No explicit label, inherit from dataset
        mock_client.get_table.return_value = mock_table
        
        collector = BigQueryCollector(project_id="test-project")
        assets = collector.collect_all()
        
        # Verify statistics
        assert len(assets) == 0
        assert collector.stats['tables_filtered_by_label'] == 5
        assert collector.stats['tables_scanned'] == 0
        assert collector.stats['datasets_scanned'] == 1

