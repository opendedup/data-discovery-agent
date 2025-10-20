"""Shared pytest fixtures for all tests."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Generator
from unittest.mock import MagicMock, Mock

import pytest
from dotenv import load_dotenv
from google.cloud import bigquery, storage


@pytest.fixture(scope="session", autouse=True)
def load_env() -> None:
    """Load environment variables from .env file for all tests."""
    load_dotenv()


@pytest.fixture
def mock_env(monkeypatch: pytest.MonkeyPatch) -> Dict[str, str]:
    """
    Mock environment variables for unit tests.
    
    Returns:
        Dictionary of mocked environment variables
    """
    env_vars = {
        "GCP_PROJECT_ID": "test-project",
        "GCS_JSONL_BUCKET": "test-jsonl-bucket",
        "GCS_REPORTS_BUCKET": "test-reports-bucket",
        "VERTEX_DATASTORE_ID": "test-datastore",
        "VERTEX_LOCATION": "global",
        "BQ_DATASET": "test_dataset",
        "BQ_TABLE": "test_table",
        "BQ_LOCATION": "US",
        "LINEAGE_ENABLED": "true",
        "LINEAGE_LOCATION": "us-central1",
        "MCP_SERVER_NAME": "test-mcp-server",
        "MCP_SERVER_VERSION": "1.0.0",
        "LOG_LEVEL": "INFO",
    }
    
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    
    return env_vars


@pytest.fixture(scope="session")
def gcp_config() -> Dict[str, str]:
    """
    Load real GCP configuration from .env for integration tests.
    
    Returns:
        Dictionary of GCP configuration values
    """
    required_vars = [
        "GCP_PROJECT_ID",
        "GCS_REPORTS_BUCKET",
        "VERTEX_DATASTORE_ID",
        "VERTEX_LOCATION",
        "BQ_DATASET",
        "BQ_TABLE",
    ]
    
    config = {}
    missing = []
    
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing.append(var)
        config[var] = value
    
    if missing:
        pytest.skip(f"Missing required environment variables: {', '.join(missing)}")
    
    return config


@pytest.fixture
def mock_bigquery_client() -> Generator[Mock, None, None]:
    """
    Mock BigQuery client for unit tests.
    
    Yields:
        Mocked BigQuery client
    """
    mock_client = Mock(spec=bigquery.Client)
    mock_client.project = "test-project"
    
    # Mock dataset
    mock_dataset = Mock(spec=bigquery.Dataset)
    mock_dataset.dataset_id = "test_dataset"
    mock_dataset.project = "test-project"
    
    # Mock table
    mock_table = Mock(spec=bigquery.Table)
    mock_table.table_id = "test_table"
    mock_table.dataset_id = "test_dataset"
    mock_table.project = "test-project"
    mock_table.num_rows = 1000
    mock_table.num_bytes = 50000
    
    mock_client.get_dataset.return_value = mock_dataset
    mock_client.get_table.return_value = mock_table
    mock_client.list_datasets.return_value = [mock_dataset]
    mock_client.list_tables.return_value = [mock_table]
    
    yield mock_client


@pytest.fixture
def mock_storage_client() -> Generator[Mock, None, None]:
    """
    Mock GCS storage client for unit tests.
    
    Yields:
        Mocked storage client
    """
    mock_client = Mock(spec=storage.Client)
    mock_client.project = "test-project"
    
    # Mock bucket
    mock_bucket = Mock(spec=storage.Bucket)
    mock_bucket.name = "test-bucket"
    
    # Mock blob
    mock_blob = Mock(spec=storage.Blob)
    mock_blob.name = "test-file.md"
    mock_blob.download_as_text.return_value = "# Test Markdown"
    
    mock_bucket.blob.return_value = mock_blob
    mock_client.bucket.return_value = mock_bucket
    
    yield mock_client


@pytest.fixture
def mock_vertex_client() -> Generator[Mock, None, None]:
    """
    Mock Vertex AI Search client for unit tests.
    
    Yields:
        Mocked Vertex AI client
    """
    mock_client = Mock()
    mock_client.project_id = "test-project"
    mock_client.location = "global"
    mock_client.datastore_id = "test-datastore"
    
    yield mock_client


@pytest.fixture
def sample_table_metadata() -> Dict[str, Any]:
    """
    Sample BigQuery table metadata for testing.
    
    Returns:
        Dictionary with sample table metadata
    """
    return {
        "project_id": "test-project",
        "dataset_id": "test_dataset",
        "table_id": "test_table",
        "table_type": "TABLE",
        "description": "Test table description",
        "created": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "modified": datetime(2024, 10, 20, tzinfo=timezone.utc),
        "num_rows": 1000,
        "num_bytes": 50000,
        "schema": [
            {
                "name": "id",
                "type": "STRING",
                "mode": "REQUIRED",
                "description": "Unique identifier",
            },
            {
                "name": "name",
                "type": "STRING",
                "mode": "NULLABLE",
                "description": "Name field",
            },
            {
                "name": "created_at",
                "type": "TIMESTAMP",
                "mode": "NULLABLE",
                "description": "Creation timestamp",
            },
        ],
    }


@pytest.fixture
def sample_view_metadata() -> Dict[str, Any]:
    """
    Sample BigQuery view metadata for testing.
    
    Returns:
        Dictionary with sample view metadata
    """
    return {
        "project_id": "test-project",
        "dataset_id": "test_dataset",
        "table_id": "test_view",
        "table_type": "VIEW",
        "description": "Test view description",
        "created": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "modified": datetime(2024, 10, 20, tzinfo=timezone.utc),
        "num_rows": 0,  # Views may have 0 rows
        "num_bytes": 0,  # Views may have 0 bytes
        "schema": [
            {
                "name": "id",
                "type": "STRING",
                "mode": "REQUIRED",
                "description": "Unique identifier",
            },
        ],
        "view_query": "SELECT id FROM test_table",
    }


@pytest.fixture
def mock_airflow_context() -> Dict[str, Any]:
    """
    Mock Airflow context for testing task functions.
    
    Returns:
        Dictionary with Airflow context structure
    """
    mock_ti = Mock()
    mock_ti.xcom_push = Mock()
    mock_ti.xcom_pull = Mock()
    
    mock_dag_run = Mock()
    mock_dag_run.conf = {}
    
    return {
        "ti": mock_ti,
        "dag_run": mock_dag_run,
        "task": Mock(),
        "dag": Mock(),
    }


@pytest.fixture
def sample_bigquery_asset() -> Dict[str, Any]:
    """
    Sample BigQueryAssetSchema data for testing.
    
    Returns:
        Dictionary representing a BigQueryAssetSchema
    """
    return {
        "id": "test-project.test_dataset.test_table",
        "content": {
            "mimeType": "text/plain",
            "representation": "document",
        },
        "structData": {
            "project_id": "test-project",
            "dataset_id": "test_dataset",
            "table_id": "test_table",
            "table_type": "TABLE",
            "description": "Test table for unit tests",
            "row_count": 1000,
            "size_bytes": 50000,
            "created_time": "2024-01-01T00:00:00Z",
            "modified_time": "2024-10-20T00:00:00Z",
            "schema": [
                {
                    "column_name": "id",
                    "column_type": "STRING",
                    "column_mode": "REQUIRED",
                    "column_description": "Unique identifier",
                }
            ],
        },
    }

