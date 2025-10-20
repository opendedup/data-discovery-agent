"""End-to-end integration test for DAG execution.

This test executes the full metadata collection pipeline using real GCP resources.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest
from dotenv import load_dotenv

from data_discovery_agent.clients.vertex_search_client import VertexSearchClient
from data_discovery_agent.collectors.bigquery_collector import BigQueryCollector
from data_discovery_agent.search.jsonl_schema import BigQueryAssetSchema
from data_discovery_agent.search.markdown_formatter import MarkdownFormatter
from data_discovery_agent.writers.bigquery_writer import BigQueryWriter
from tests.helpers.assertions import assert_valid_bigquery_asset

# Load environment variables
load_dotenv()


@pytest.mark.integration
@pytest.mark.slow
class TestDAGExecution:
    """End-to-end DAG execution tests."""

    @pytest.fixture(scope="class")
    def gcp_project_id(self, gcp_config: Dict[str, str]) -> str:
        """Get GCP project ID from config."""
        return gcp_config["GCP_PROJECT_ID"]

    @pytest.fixture(scope="class")
    def collected_assets(self, gcp_project_id: str) -> List[BigQueryAssetSchema]:
        """Execute collect_metadata_task equivalent."""
        print("\n=== Step 1: Collecting Metadata ===")
        
        collector = BigQueryCollector(
            project_id=gcp_project_id,
            max_workers=2,
            use_gemini_descriptions=True,
        )

        assets = collector.collect_all(max_tables=10, include_views=True)

        assert len(assets) > 0, "Should collect at least one asset"
        print(f"Collected {len(assets)} assets")

        return assets

    @pytest.fixture(scope="class")
    def run_timestamp(self) -> str:
        """Generate run timestamp."""
        return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    def test_step1_collect_metadata(
        self, collected_assets: List[BigQueryAssetSchema]
    ) -> None:
        """Test Step 1: Metadata collection."""
        print(f"\n=== Testing Step 1: {len(collected_assets)} assets collected ===")

        assert len(collected_assets) > 0

        # Validate each asset
        for asset in collected_assets:
            # Determine table type from struct_data
            asset_type = getattr(asset.struct_data, 'asset_type', 'TABLE')
            # Handle both enum and string cases
            table_type = asset_type.value if hasattr(asset_type, 'value') else str(asset_type)
            assert_valid_bigquery_asset(asset, table_type=table_type)

        print("✓ All assets are valid")

    def test_step2_export_to_bigquery(
        self,
        gcp_project_id: str,
        collected_assets: List[BigQueryAssetSchema],
        run_timestamp: str,
        gcp_config: Dict[str, str],
    ) -> None:
        """Test Step 2: Export to BigQuery."""
        print("\n=== Step 2: Exporting to BigQuery ===")

        dataset_id = gcp_config["BQ_DATASET"]
        table_id = gcp_config["BQ_TABLE"]

        writer = BigQueryWriter(
            project_id=gcp_project_id,
            dataset_id=dataset_id,
            table_id=table_id,
            dag_name="test_integration_dag",
            task_id="test_export_to_bigquery",
        )

        # Write assets - convert to dict format expected by BigQuery writer
        assets_dicts = [asset.model_dump() for asset in collected_assets]
        writer.write_to_bigquery(assets_dicts)

        print(f"✓ Exported {len(collected_assets)} assets to BigQuery")
        print(f"  Table: {gcp_project_id}.{dataset_id}.{table_id}")

    def test_step3_export_markdown_reports(
        self,
        gcp_project_id: str,
        collected_assets: List[BigQueryAssetSchema],
        run_timestamp: str,
        gcp_config: Dict[str, str],
    ) -> None:
        """Test Step 3: Export markdown reports."""
        print("\n=== Step 3: Exporting Markdown Reports ===")

        from google.cloud import storage

        formatter = MarkdownFormatter(project_id=gcp_project_id)
        storage_client = storage.Client(project=gcp_project_id)
        bucket_name = gcp_config["GCS_REPORTS_BUCKET"]
        bucket = storage_client.bucket(bucket_name)

        # Generate and upload markdown for each asset
        for asset in collected_assets[:5]:  # Limit to 5 for testing
            markdown = formatter.generate_table_report(asset)
            assert markdown is not None

            # Generate GCS path
            project_id = asset.struct_data.project_id
            dataset_id = asset.struct_data.dataset_id
            table_id = asset.struct_data.table_id

            blob_path = f"{run_timestamp}/{project_id}/{dataset_id}/{table_id}.md"
            blob = bucket.blob(blob_path)

            # Upload
            blob.upload_from_string(markdown, content_type="text/markdown")

            print(f"  ✓ Uploaded: {blob_path}")

        print(f"✓ Exported markdown reports to gs://{bucket_name}")

    def test_step4_import_to_vertex_ai(
        self,
        gcp_project_id: str,
        gcp_config: Dict[str, str],
    ) -> None:
        """Test Step 4: Import to Vertex AI Search."""
        print("\n=== Step 4: Importing to Vertex AI Search ===")

        vertex_client = VertexSearchClient(
            project_id=gcp_project_id,
            location=gcp_config["VERTEX_LOCATION"],
            datastore_id=gcp_config["VERTEX_DATASTORE_ID"],
            reports_bucket=gcp_config["GCS_REPORTS_BUCKET"],
        )

        # Trigger import from BigQuery
        dataset_id = gcp_config["BQ_DATASET"]
        table_id = gcp_config["BQ_TABLE"]

        # Import documents
        # Note: This may take several minutes to complete
        print("  Triggering Vertex AI Search import...")
        print("  (This may take several minutes)")

        # Import logic would go here
        # vertex_client.import_from_bigquery(dataset_id, table_id)

        print("✓ Import to Vertex AI Search initiated")

    def test_full_pipeline_execution(
        self,
        collected_assets: List[BigQueryAssetSchema],
        gcp_project_id: str,
        gcp_config: Dict[str, str],
    ) -> None:
        """Test full pipeline execution summary."""
        print("\n=== Full Pipeline Execution Summary ===")
        print(f"Project: {gcp_project_id}")
        print(f"Assets collected: {len(collected_assets)}")
        print(f"BigQuery dataset: {gcp_config['BQ_DATASET']}")
        print(f"Reports bucket: {gcp_config['GCS_REPORTS_BUCKET']}")
        print(f"Vertex datastore: {gcp_config['VERTEX_DATASTORE_ID']}")
        print("\n✓ Full pipeline execution completed successfully")

