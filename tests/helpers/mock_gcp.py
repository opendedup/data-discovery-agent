"""Mock GCP service clients for unit testing.

These mocks are ONLY used for unit tests. Integration tests use real GCP services.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import Mock

from google.cloud import bigquery, storage


class MockBigQueryClient:
    """Mock BigQuery client for unit tests."""

    def __init__(self, project_id: str = "test-project") -> None:
        """Initialize mock BigQuery client."""
        self.project = project_id
        self._datasets: Dict[str, Any] = {}
        self._tables: Dict[str, Any] = {}

    def list_datasets(self) -> List[Mock]:
        """Mock list datasets."""
        return list(self._datasets.values())

    def get_dataset(self, dataset_id: str) -> Mock:
        """Mock get dataset."""
        if dataset_id not in self._datasets:
            raise Exception(f"Dataset {dataset_id} not found")
        return self._datasets[dataset_id]

    def list_tables(self, dataset_id: str) -> List[Mock]:
        """Mock list tables."""
        return [t for t in self._tables.values() if t.dataset_id == dataset_id]

    def get_table(self, table_ref: str) -> Mock:
        """Mock get table."""
        if table_ref not in self._tables:
            raise Exception(f"Table {table_ref} not found")
        return self._tables[table_ref]

    def query(self, query: str) -> Mock:
        """Mock query execution."""
        mock_job = Mock()
        mock_job.result.return_value = []
        return mock_job

    def add_mock_dataset(
        self, dataset_id: str, location: str = "US", description: str = ""
    ) -> Mock:
        """Add a mock dataset."""
        mock_dataset = Mock(spec=bigquery.Dataset)
        mock_dataset.dataset_id = dataset_id
        mock_dataset.project = self.project
        mock_dataset.location = location
        mock_dataset.description = description
        self._datasets[dataset_id] = mock_dataset
        return mock_dataset

    def add_mock_table(
        self,
        dataset_id: str,
        table_id: str,
        table_type: str = "TABLE",
        num_rows: int = 1000,
        num_bytes: int = 50000,
        description: str = "",
        schema: Optional[List[Dict[str, Any]]] = None,
    ) -> Mock:
        """Add a mock table."""
        mock_table = Mock(spec=bigquery.Table)
        mock_table.table_id = table_id
        mock_table.dataset_id = dataset_id
        mock_table.project = self.project
        mock_table.table_type = table_type
        mock_table.num_rows = num_rows
        mock_table.num_bytes = num_bytes
        mock_table.description = description
        mock_table.created = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_table.modified = datetime.now(timezone.utc)

        # Mock schema
        if schema:
            mock_schema = []
            for field in schema:
                mock_field = Mock(spec=bigquery.SchemaField)
                mock_field.name = field.get("name", "")
                mock_field.field_type = field.get("type", "STRING")
                mock_field.mode = field.get("mode", "NULLABLE")
                mock_field.description = field.get("description", "")
                mock_schema.append(mock_field)
            mock_table.schema = mock_schema
        else:
            mock_table.schema = []

        table_ref = f"{self.project}.{dataset_id}.{table_id}"
        self._tables[table_ref] = mock_table
        return mock_table


class MockStorageClient:
    """Mock GCS Storage client for unit tests."""

    def __init__(self, project_id: str = "test-project") -> None:
        """Initialize mock storage client."""
        self.project = project_id
        self._buckets: Dict[str, Any] = {}
        self._blobs: Dict[str, Dict[str, Any]] = {}

    def bucket(self, bucket_name: str) -> Mock:
        """Mock get bucket."""
        if bucket_name not in self._buckets:
            mock_bucket = Mock(spec=storage.Bucket)
            mock_bucket.name = bucket_name
            mock_bucket.blob = lambda name: self._get_or_create_blob(bucket_name, name)
            self._buckets[bucket_name] = mock_bucket
            self._blobs[bucket_name] = {}
        return self._buckets[bucket_name]

    def _get_or_create_blob(self, bucket_name: str, blob_name: str) -> Mock:
        """Get or create a mock blob."""
        if blob_name not in self._blobs[bucket_name]:
            mock_blob = Mock(spec=storage.Blob)
            mock_blob.name = blob_name
            mock_blob.download_as_text = Mock(return_value="")
            mock_blob.upload_from_string = Mock()
            self._blobs[bucket_name][blob_name] = mock_blob
        return self._blobs[bucket_name][blob_name]

    def set_blob_content(
        self, bucket_name: str, blob_name: str, content: str
    ) -> None:
        """Set content for a mock blob."""
        blob = self._get_or_create_blob(bucket_name, blob_name)
        blob.download_as_text.return_value = content


class MockVertexClient:
    """Mock Vertex AI Search client for unit tests."""

    def __init__(
        self,
        project_id: str = "test-project",
        location: str = "global",
        datastore_id: str = "test-datastore",
    ) -> None:
        """Initialize mock Vertex AI client."""
        self.project_id = project_id
        self.location = location
        self.datastore_id = datastore_id
        self._documents: List[Dict[str, Any]] = []

    def search(self, query: str, **kwargs: Any) -> List[Dict[str, Any]]:
        """Mock search."""
        return self._documents[:10]  # Return first 10 documents

    def import_documents(self, source: str) -> Mock:
        """Mock document import."""
        mock_operation = Mock()
        mock_operation.result.return_value = Mock(
            error_count=0, total_document_count=len(self._documents)
        )
        return mock_operation

    def add_mock_document(self, document: Dict[str, Any]) -> None:
        """Add a mock document to the datastore."""
        self._documents.append(document)


class MockDataplexClient:
    """Mock Dataplex client for unit tests."""

    def __init__(self, project_id: str = "test-project") -> None:
        """Initialize mock Dataplex client."""
        self.project_id = project_id
        self._scans: Dict[str, Any] = {}

    def get_data_scan(self, scan_name: str) -> Mock:
        """Mock get data scan."""
        if scan_name not in self._scans:
            raise Exception(f"Data scan {scan_name} not found")
        return self._scans[scan_name]

    def add_mock_scan(
        self, scan_name: str, profile_result: Optional[Dict[str, Any]] = None
    ) -> Mock:
        """Add a mock data scan."""
        mock_scan = Mock()
        mock_scan.name = scan_name
        mock_scan.data_profile_result = profile_result or {}
        self._scans[scan_name] = mock_scan
        return mock_scan


class MockLineageClient:
    """Mock Data Catalog Lineage client for unit tests."""

    def __init__(self, project_id: str = "test-project") -> None:
        """Initialize mock lineage client."""
        self.project_id = project_id
        self._processes: Dict[str, Any] = {}
        self._runs: Dict[str, Any] = {}
        self._events: List[Any] = []

    def create_process(self, request: Any) -> Mock:
        """Mock create process."""
        mock_process = Mock()
        mock_process.name = f"projects/{self.project_id}/locations/us-central1/processes/test-process"
        self._processes[mock_process.name] = mock_process
        return mock_process

    def create_run(self, request: Any) -> Mock:
        """Mock create run."""
        mock_run = Mock()
        mock_run.name = f"{request.parent}/runs/test-run"
        self._runs[mock_run.name] = mock_run
        return mock_run

    def create_lineage_event(self, request: Any) -> Mock:
        """Mock create lineage event."""
        mock_event = Mock()
        mock_event.name = f"{request.parent}/lineageEvents/test-event"
        self._events.append(mock_event)
        return mock_event

    def search_links(self, request: Any) -> Mock:
        """Mock search links."""
        mock_response = Mock()
        mock_response.links = []
        return mock_response

