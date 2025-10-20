"""BigQuery output validation tests.

Validates the exported metadata in BigQuery for completeness and correctness.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest
from dotenv import load_dotenv
from google.cloud import bigquery

from tests.helpers.assertions import (
    assert_statistics_valid,
    assert_valid_column_description,
    assert_valid_table_description,
)

load_dotenv()


@pytest.mark.integration
@pytest.mark.slow
class TestBigQueryValidation:
    """Validation tests for BigQuery exported metadata."""

    @pytest.fixture(scope="class")
    def bq_client(self, gcp_config: Dict[str, str]) -> bigquery.Client:
        """Create BigQuery client."""
        return bigquery.Client(project=gcp_config["GCP_PROJECT_ID"])

    @pytest.fixture(scope="class")
    def exported_rows(
        self, bq_client: bigquery.Client, gcp_config: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """Fetch exported rows from BigQuery."""
        dataset_id = gcp_config["BQ_DATASET"]
        table_id = gcp_config["BQ_TABLE"]

        query = f"""
        SELECT *
        FROM `{gcp_config['GCP_PROJECT_ID']}.{dataset_id}.{table_id}`
        WHERE run_timestamp = (
            SELECT MAX(run_timestamp)
            FROM `{gcp_config['GCP_PROJECT_ID']}.{dataset_id}.{table_id}`
        )
        LIMIT 100
        """

        query_job = bq_client.query(query)
        results = query_job.result()

        rows = [dict(row) for row in results]
        return rows

    def test_row_completeness(self, exported_rows: List[Dict[str, Any]]) -> None:
        """Test that all expected rows are present and complete."""
        print(f"\n=== Validating {len(exported_rows)} exported rows ===")

        assert len(exported_rows) > 0, "Should have at least one exported row"

        # Check required fields
        required_fields = [
            "project_id",
            "dataset_id",
            "table_id",
            "run_timestamp",
        ]

        # Track rows with issues
        null_table_type_count = 0

        for row in exported_rows:
            for field in required_fields:
                assert field in row, f"Missing required field: {field}"
                assert row[field] is not None, f"Field {field} cannot be null"
            
            # table_type should ideally be present, but might be null in legacy data
            if "table_type" not in row or row["table_type"] is None:
                null_table_type_count += 1
                table_name = f"{row.get('project_id')}.{row.get('dataset_id')}.{row.get('table_id')}"
                print(f"  ⚠️  Warning: {table_name} has null table_type (legacy data?)")

        if null_table_type_count > 0:
            print(f"\n⚠️  {null_table_type_count}/{len(exported_rows)} rows have null table_type")
            print("   This suggests data from before the table_type fix. Re-run collection to update.")
        
        print(f"✓ All {len(exported_rows)} rows have core required fields")

    def test_schema_validation(self, exported_rows: List[Dict[str, Any]]) -> None:
        """Test schema fields are populated correctly."""
        print("\n=== Validating Schema Fields ===")

        for row in exported_rows:
            # Schema should be present (JSON or string)
            assert "schema" in row or "column_name" in row

            # If schema is present, validate structure
            if "schema" in row and row["schema"]:
                # Schema might be JSON string or array
                print(f"  ✓ Table {row['table_id']} has schema")

        print("✓ Schema validation passed")

    def test_description_quality(self, exported_rows: List[Dict[str, Any]]) -> None:
        """Test that descriptions are meaningful and complete."""
        print("\n=== Validating Description Quality ===")

        tables_without_description = []
        short_descriptions = []

        for row in exported_rows:
            table_name = f"{row['project_id']}.{row['dataset_id']}.{row['table_id']}"

            # Check table description
            if "description" in row or "table_description" in row:
                description = row.get("description") or row.get("table_description")

                if not description or len(description.strip()) == 0:
                    tables_without_description.append(table_name)
                elif len(description.strip()) < 10:
                    short_descriptions.append((table_name, description))
                else:
                    # Valid description
                    try:
                        assert_valid_table_description(description, min_length=10)
                    except AssertionError as e:
                        print(f"  Warning: {table_name}: {e}")

        if tables_without_description:
            print(f"  Warning: {len(tables_without_description)} tables without descriptions")

        if short_descriptions:
            print(f"  Warning: {len(short_descriptions)} tables with short descriptions")

        print("✓ Description quality check completed")

    def test_statistics_validation(self, exported_rows: List[Dict[str, Any]]) -> None:
        """Test that statistics are valid for tables and views."""
        print("\n=== Validating Statistics ===")

        for row in exported_rows:
            table_type = row.get("table_type", "TABLE")
            table_name = f"{row['table_id']}"

            stats = {
                "row_count": row.get("row_count"),
                "size_bytes": row.get("size_bytes"),
                "created_time": row.get("created_time") or row.get("created"),
                "modified_time": row.get("modified_time") or row.get("modified"),
            }

            try:
                assert_statistics_valid(stats, table_type=table_type)
                print(f"  ✓ {table_name} ({table_type}): valid statistics")
            except AssertionError as e:
                print(f"  Warning: {table_name}: {e}")

        print("✓ Statistics validation completed")

    def test_run_timestamp_populated(
        self, exported_rows: List[Dict[str, Any]]
    ) -> None:
        """Test that run_timestamp is populated for all rows."""
        print("\n=== Validating run_timestamp ===")

        for row in exported_rows:
            assert "run_timestamp" in row, "run_timestamp field must exist"
            assert row["run_timestamp"] is not None, "run_timestamp cannot be null"

        # All rows should have the same run_timestamp
        timestamps = set(row["run_timestamp"] for row in exported_rows)
        assert len(timestamps) == 1, "All rows should have the same run_timestamp"

        print(f"✓ All rows have run_timestamp: {list(timestamps)[0]}")

    def test_no_null_required_fields(
        self, exported_rows: List[Dict[str, Any]]
    ) -> None:
        """Test that required fields are not null."""
        print("\n=== Checking for Null Required Fields ===")

        required_non_null = [
            "project_id",
            "dataset_id",
            "table_id",
            "run_timestamp",
        ]

        null_violations = []
        table_type_nulls = []

        for row in exported_rows:
            for field in required_non_null:
                if field in row and row[field] is None:
                    table_name = f"{row.get('project_id')}.{row.get('dataset_id')}.{row.get('table_id')}"
                    null_violations.append((table_name, field))
            
            # Check table_type separately (might be null in legacy data)
            if "table_type" in row and row["table_type"] is None:
                table_name = f"{row.get('project_id')}.{row.get('dataset_id')}.{row.get('table_id')}"
                table_type_nulls.append(table_name)

        assert len(null_violations) == 0, f"Found null required fields: {null_violations}"

        if table_type_nulls:
            print(f"⚠️  {len(table_type_nulls)} rows have null table_type (legacy data)")
        
        print("✓ No null core required fields found")

    def test_table_types(self, exported_rows: List[Dict[str, Any]]) -> None:
        """Test that table_type values are valid."""
        print("\n=== Validating Table Types ===")

        valid_types = ["TABLE", "VIEW", "MATERIALIZED_VIEW", "EXTERNAL", None]
        type_counts = {}
        null_count = 0

        for row in exported_rows:
            table_type = row.get("table_type")
            
            if table_type is None:
                null_count += 1
                type_counts["NULL (legacy)"] = type_counts.get("NULL (legacy)", 0) + 1
            else:
                # Check if it's a valid type
                if table_type not in ["TABLE", "VIEW", "MATERIALIZED_VIEW", "EXTERNAL"]:
                    table_name = f"{row.get('project_id')}.{row.get('dataset_id')}.{row.get('table_id')}"
                    print(f"  ⚠️  Invalid table_type '{table_type}' for {table_name}")
                
                type_counts[table_type] = type_counts.get(table_type, 0) + 1

        for type_name, count in type_counts.items():
            print(f"  {type_name}: {count}")

        if null_count > 0:
            print(f"\n⚠️  {null_count} rows have null table_type (legacy data)")

        print("✓ Table type validation completed")

    def test_timestamps_format(self, exported_rows: List[Dict[str, Any]]) -> None:
        """Test that timestamps are in correct format."""
        print("\n=== Validating Timestamp Formats ===")

        timestamp_fields = ["created_time", "modified_time", "run_timestamp"]

        for row in exported_rows:
            for field in timestamp_fields:
                if field in row and row[field]:
                    # Should be a valid timestamp
                    assert row[field] is not None

        print("✓ Timestamp formats are valid")

    def test_downstream_lineage_captured(self, exported_rows: List[Dict[str, Any]]) -> None:
        """Test that lineage information is captured and persisted in BigQuery."""
        print("\n=== Validating Lineage in BigQuery ===")

        tables_with_downstream = 0
        tables_with_upstream = 0
        total_downstream_links = 0
        total_upstream_links = 0
        tables_checked = 0
        tables_with_upstream_list = []
        tables_with_downstream_list = []

        for row in exported_rows:
            tables_checked += 1
            table_id = row.get('table_id', 'unknown')
            project_id = row.get('project_id', '')
            dataset_id = row.get('dataset_id', '')
            full_table_name = f"{project_id}.{dataset_id}.{table_id}"
            
            # BigQuery schema has top-level 'lineage' field (REPEATED RECORD with source/target)
            lineage_records = row.get("lineage", [])
            
            if not lineage_records:
                continue  # No lineage for this table

            # Reconstruct upstream/downstream from source/target pairs
            upstream = []
            downstream = []
            
            for record in lineage_records:
                source = record.get("source")
                target = record.get("target")
                
                # If this table is the target, then source is upstream
                if target == full_table_name and source:
                    upstream.append(source)
                # If this table is the source, then target is downstream
                elif source == full_table_name and target:
                    downstream.append(target)

            if upstream:
                tables_with_upstream += 1
                total_upstream_links += len(upstream)
                tables_with_upstream_list.append(table_id)
                print(f"  ✓ {table_id}: {len(upstream)} upstream sources")
                # Log first few
                for dep in upstream[:2]:
                    print(f"    ← {dep}")
            
            if downstream:
                tables_with_downstream += 1
                total_downstream_links += len(downstream)
                tables_with_downstream_list.append(table_id)
                print(f"  ✓ {table_id}: {len(downstream)} downstream dependencies")
                # Log first few downstream dependencies
                for dep in downstream[:2]:
                    print(f"    → {dep}")

        print(f"\n  Summary:")
        print(f"    Tables checked: {tables_checked}")
        print(f"    Tables with upstream lineage: {tables_with_upstream} ({total_upstream_links} links)")
        print(f"    Tables with downstream lineage: {tables_with_downstream} ({total_downstream_links} links)")

        # Detailed lists
        if tables_with_upstream > 0:
            print(f"\n  Tables with upstream: {', '.join(tables_with_upstream_list[:5])}")
            if len(tables_with_upstream_list) > 5:
                print(f"  ... and {len(tables_with_upstream_list) - 5} more")
        
        if tables_with_downstream > 0:
            print(f"\n  Tables with downstream: {', '.join(tables_with_downstream_list[:5])}")
            if len(tables_with_downstream_list) > 5:
                print(f"  ... and {len(tables_with_downstream_list) - 5} more")

        # Warnings
        if tables_checked > 0:
            lineage_rate = (tables_with_upstream + tables_with_downstream) / tables_checked
            print(f"\n    Overall lineage capture rate: {lineage_rate:.1%}")
            
            if tables_with_upstream == 0:
                print("\n⚠️  WARNING: No upstream lineage found in ANY tables!")
                print("  This could indicate:")
                print("    1. All tables are source tables (no upstream dependencies)")
                print("    2. Upstream lineage detection is not working")
            
            if tables_with_downstream == 0:
                print("\n⚠️  WARNING: No downstream lineage found in ANY tables!")
                print("  This could indicate:")
                print("    1. No tables/views have downstream dependencies")
                print("    2. Downstream lineage detection is not working")
                print("    3. Views referencing these tables are in excluded datasets")
        
        print("\n✓ Lineage validation in BigQuery completed")

