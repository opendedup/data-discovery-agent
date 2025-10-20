"""GCS markdown report validation tests.

Validates markdown reports stored in GCS for syntax and content correctness.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

import pytest
from dotenv import load_dotenv
from google.cloud import bigquery, storage

from tests.helpers.assertions import assert_valid_markdown

load_dotenv()


@pytest.mark.integration
@pytest.mark.slow
class TestMarkdownValidation:
    """Validation tests for GCS markdown reports."""

    @pytest.fixture(scope="class")
    def storage_client(self, gcp_config: Dict[str, str]) -> storage.Client:
        """Create GCS storage client."""
        return storage.Client(project=gcp_config["GCP_PROJECT_ID"])

    @pytest.fixture(scope="class")
    def bq_client(self, gcp_config: Dict[str, str]) -> bigquery.Client:
        """Create BigQuery client."""
        return bigquery.Client(project=gcp_config["GCP_PROJECT_ID"])

    @pytest.fixture(scope="class")
    def latest_run_timestamp(
        self, bq_client: bigquery.Client, gcp_config: Dict[str, str]
    ) -> str:
        """Get the latest run timestamp."""
        query = f"""
        SELECT MAX(run_timestamp) as latest_timestamp
        FROM `{gcp_config['GCP_PROJECT_ID']}.{gcp_config['BQ_DATASET']}.{gcp_config['BQ_TABLE']}`
        """

        result = bq_client.query(query).result()
        row = next(result)
        return str(row.latest_timestamp)

    @pytest.fixture(scope="class")
    def sample_tables(
        self, bq_client: bigquery.Client, gcp_config: Dict[str, str]
    ) -> List[Dict[str, str]]:
        """Get sample tables to validate."""
        query = f"""
        SELECT project_id, dataset_id, table_id
        FROM `{gcp_config['GCP_PROJECT_ID']}.{gcp_config['BQ_DATASET']}.{gcp_config['BQ_TABLE']}`
        WHERE run_timestamp = (
            SELECT MAX(run_timestamp)
            FROM `{gcp_config['GCP_PROJECT_ID']}.{gcp_config['BQ_DATASET']}.{gcp_config['BQ_TABLE']}`
        )
        LIMIT 10
        """

        result = bq_client.query(query).result()
        return [
            {
                "project_id": row.project_id,
                "dataset_id": row.dataset_id,
                "table_id": row.table_id,
            }
            for row in result
        ]

    def test_file_existence(
        self,
        storage_client: storage.Client,
        gcp_config: Dict[str, str],
        latest_run_timestamp: str,
        sample_tables: List[Dict[str, str]],
    ) -> None:
        """Test that markdown files exist for collected tables."""
        print(f"\n=== Testing Markdown File Existence ===")
        print(f"Run timestamp: {latest_run_timestamp}")

        bucket = storage_client.bucket(gcp_config["GCS_REPORTS_BUCKET"])

        existing_files = 0
        missing_files = []

        for table in sample_tables:
            blob_path = (
                f"{latest_run_timestamp}/"
                f"{table['project_id']}/"
                f"{table['dataset_id']}/"
                f"{table['table_id']}.md"
            )

            blob = bucket.blob(blob_path)

            if blob.exists():
                existing_files += 1
                print(f"  ✓ Found: {blob_path}")
            else:
                missing_files.append(blob_path)
                print(f"  ✗ Missing: {blob_path}")

        print(f"\n✓ Found {existing_files}/{len(sample_tables)} markdown files")

        if missing_files:
            print(f"Warning: {len(missing_files)} files missing")

    def test_markdown_syntax_validation(
        self,
        storage_client: storage.Client,
        gcp_config: Dict[str, str],
        latest_run_timestamp: str,
        sample_tables: List[Dict[str, str]],
    ) -> None:
        """Test that markdown files have valid syntax."""
        print(f"\n=== Validating Markdown Syntax ===")

        bucket = storage_client.bucket(gcp_config["GCS_REPORTS_BUCKET"])

        for table in sample_tables[:5]:  # Test first 5
            blob_path = (
                f"{latest_run_timestamp}/"
                f"{table['project_id']}/"
                f"{table['dataset_id']}/"
                f"{table['table_id']}.md"
            )

            blob = bucket.blob(blob_path)

            if not blob.exists():
                print(f"  Skipping: {blob_path} (not found)")
                continue

            markdown_content = blob.download_as_text()

            # Use our custom assertion
            assert_valid_markdown(markdown_content, table["table_id"])

            print(f"  ✓ Valid syntax: {table['table_id']}.md")

        print("✓ Markdown syntax validation passed")

    def test_content_completeness(
        self,
        storage_client: storage.Client,
        gcp_config: Dict[str, str],
        latest_run_timestamp: str,
        sample_tables: List[Dict[str, str]],
    ) -> None:
        """Test that markdown files have complete content."""
        print(f"\n=== Validating Content Completeness ===")

        bucket = storage_client.bucket(gcp_config["GCS_REPORTS_BUCKET"])

        for table in sample_tables[:5]:
            blob_path = (
                f"{latest_run_timestamp}/"
                f"{table['project_id']}/"
                f"{table['dataset_id']}/"
                f"{table['table_id']}.md"
            )

            blob = bucket.blob(blob_path)

            if not blob.exists():
                continue

            markdown = blob.download_as_text()

            # Check for required sections
            required_sections = [
                "## Overview",
                "## Schema",
                "## Statistics",
            ]

            missing_sections = []
            for section in required_sections:
                if section not in markdown:
                    missing_sections.append(section)

            if missing_sections:
                print(f"  ✗ {table['table_id']}: Missing {missing_sections}")
            else:
                print(f"  ✓ {table['table_id']}: All sections present")

        print("✓ Content completeness check completed")

    def test_schema_table_present(
        self,
        storage_client: storage.Client,
        gcp_config: Dict[str, str],
        latest_run_timestamp: str,
        sample_tables: List[Dict[str, str]],
    ) -> None:
        """Test that schema table is present in markdown."""
        print(f"\n=== Validating Schema Tables ===")

        bucket = storage_client.bucket(gcp_config["GCS_REPORTS_BUCKET"])

        for table in sample_tables[:5]:
            blob_path = (
                f"{latest_run_timestamp}/"
                f"{table['project_id']}/"
                f"{table['dataset_id']}/"
                f"{table['table_id']}.md"
            )

            blob = bucket.blob(blob_path)

            if not blob.exists():
                continue

            markdown = blob.download_as_text()

            # Check for table syntax
            has_table = "|" in markdown
            has_column_header = "Column" in markdown or "column" in markdown.lower()

            if has_table and has_column_header:
                print(f"  ✓ {table['table_id']}: Schema table present")
            else:
                print(f"  ✗ {table['table_id']}: Schema table missing")

        print("✓ Schema table validation completed")

    def test_no_broken_markdown(
        self,
        storage_client: storage.Client,
        gcp_config: Dict[str, str],
        latest_run_timestamp: str,
        sample_tables: List[Dict[str, str]],
    ) -> None:
        """Test for broken markdown syntax."""
        print(f"\n=== Checking for Broken Markdown ===")

        bucket = storage_client.bucket(gcp_config["GCS_REPORTS_BUCKET"])

        broken_files = []

        for table in sample_tables[:5]:
            blob_path = (
                f"{latest_run_timestamp}/"
                f"{table['project_id']}/"
                f"{table['dataset_id']}/"
                f"{table['table_id']}.md"
            )

            blob = bucket.blob(blob_path)

            if not blob.exists():
                continue

            markdown = blob.download_as_text()

            # Check for broken links
            broken_link_pattern = r'\[.*?\]\(\s*\)'
            broken_links = re.findall(broken_link_pattern, markdown)

            # Check for unclosed code blocks
            code_block_count = markdown.count("```")
            unclosed_blocks = code_block_count % 2 != 0

            if broken_links or unclosed_blocks:
                broken_files.append(table["table_id"])
                print(f"  ✗ {table['table_id']}: Has broken markdown")
            else:
                print(f"  ✓ {table['table_id']}: Clean markdown")

        if broken_files:
            print(f"\nWarning: {len(broken_files)} files with broken markdown")
        else:
            print("\n✓ No broken markdown found")

    def test_path_structure(
        self,
        storage_client: storage.Client,
        gcp_config: Dict[str, str],
        latest_run_timestamp: str,
    ) -> None:
        """Test that GCS path structure is correct."""
        print(f"\n=== Validating GCS Path Structure ===")

        bucket = storage_client.bucket(gcp_config["GCS_REPORTS_BUCKET"])

        # List blobs with the run_timestamp prefix
        blobs = list(bucket.list_blobs(prefix=latest_run_timestamp, max_results=10))

        print(f"Found {len(blobs)} blobs with prefix {latest_run_timestamp}")

        for blob in blobs[:5]:
            # Path should be: {run_timestamp}/{project}/{dataset}/{table}.md
            parts = blob.name.split("/")

            assert len(parts) == 4, f"Invalid path structure: {blob.name}"
            assert parts[0] == latest_run_timestamp
            assert parts[3].endswith(".md")

            print(f"  ✓ Valid path: {blob.name}")

        print("✓ GCS path structure is correct")

    def test_lineage_documentation(
        self,
        storage_client: storage.Client,
        gcp_config: Dict[str, str],
        latest_run_timestamp: str,
        sample_tables: List[Dict[str, str]],
    ) -> None:
        """Test that lineage information is documented in markdown reports."""
        print(f"\n=== Validating Lineage Documentation ===")

        bucket = storage_client.bucket(gcp_config["GCS_REPORTS_BUCKET"])

        tables_with_upstream = 0
        tables_with_downstream = 0
        tables_checked = 0
        missing_lineage_section = []

        for table in sample_tables:
            blob_path = (
                f"{latest_run_timestamp}/"
                f"{table['project_id']}/"
                f"{table['dataset_id']}/"
                f"{table['table_id']}.md"
            )

            blob = bucket.blob(blob_path)

            if not blob.exists():
                continue

            markdown = blob.download_as_text()
            tables_checked += 1

            # MUST have Data Lineage section
            if "## Data Lineage" not in markdown:
                missing_lineage_section.append(table['table_id'])
                print(f"  ✗ {table['table_id']}: Missing Data Lineage section!")
                continue
            
            # MUST have both Upstream and Downstream subsections
            has_upstream_section = "### Upstream Sources" in markdown
            has_downstream_section = "### Downstream Dependencies" in markdown
            
            if not has_upstream_section:
                print(f"  ✗ {table['table_id']}: Missing Upstream Sources section!")
            if not has_downstream_section:
                print(f"  ✗ {table['table_id']}: Missing Downstream Dependencies section!")

            # Look for actual lineage content
            upstream_has_content = False
            downstream_has_content = False

            if has_upstream_section:
                # Check if there's actual content (not just "No upstream sources found")
                upstream_pattern = r'### Upstream Sources\s*\n+(.*?)(?=###|##|$)'
                upstream_match = re.search(upstream_pattern, markdown, re.DOTALL)
                if upstream_match:
                    content = upstream_match.group(1).strip()
                    # Check if there are actual table references (not just "No ... found")
                    if '`' in content and 'No upstream' not in content:
                        upstream_has_content = True
                        tables_with_upstream += 1
                        print(f"  ✓ {table['table_id']}: Has upstream lineage")

            if has_downstream_section:
                # Check if there's actual content
                downstream_pattern = r'### Downstream Dependencies\s*\n+(.*?)(?=###|##|$)'
                downstream_match = re.search(downstream_pattern, markdown, re.DOTALL)
                if downstream_match:
                    content = downstream_match.group(1).strip()
                    # Check if there are actual table references
                    if '`' in content and 'No downstream' not in content:
                        downstream_has_content = True
                        tables_with_downstream += 1
                        print(f"  ✓ {table['table_id']}: Has downstream lineage")

        print(f"\n  Summary:")
        print(f"    Tables checked: {tables_checked}")
        print(f"    Tables with upstream documentation: {tables_with_upstream}")
        print(f"    Tables with downstream documentation: {tables_with_downstream}")

        # ASSERT that lineage section exists in all markdown files
        if missing_lineage_section:
            pytest.fail(f"❌ {len(missing_lineage_section)} tables missing Data Lineage section: {missing_lineage_section}")

        if tables_checked > 0:
            upstream_rate = tables_with_upstream / tables_checked
            downstream_rate = tables_with_downstream / tables_checked
            print(f"    Upstream documentation rate: {upstream_rate:.1%}")
            print(f"    Downstream documentation rate: {downstream_rate:.1%}")

            # WARNING if no lineage found
            if tables_with_upstream == 0:
                print("\n⚠️  WARNING: No upstream lineage found in ANY markdown reports!")
                print("  This indicates upstream lineage is not being captured or documented")
            
            if tables_with_downstream == 0:
                print("\n⚠️  WARNING: No downstream lineage found in ANY markdown reports!")
                print("  This indicates downstream lineage is not being captured or documented")

        print("✓ Lineage documentation validation completed")

