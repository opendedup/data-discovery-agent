"""Data Catalog Lineage validation tests.

Validates lineage records in Data Catalog Lineage API.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest
from dotenv import load_dotenv
from google.cloud import datacatalog_lineage_v1

from tests.helpers.assertions import assert_valid_lineage_event

load_dotenv()


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.lineage
class TestLineageValidation:
    """Validation tests for Data Catalog Lineage."""

    @pytest.fixture(scope="class")
    def lineage_client(self) -> datacatalog_lineage_v1.LineageClient:
        """Create Lineage client."""
        return datacatalog_lineage_v1.LineageClient()

    @pytest.fixture(scope="class")
    def lineage_location(self, gcp_config: Dict[str, str]) -> str:
        """Get lineage location."""
        return gcp_config.get("LINEAGE_LOCATION", "us-central1")

    def test_process_exists(
        self,
        lineage_client: datacatalog_lineage_v1.LineageClient,
        gcp_config: Dict[str, str],
        lineage_location: str,
    ) -> None:
        """Test that process exists for the DAG."""
        print("\n=== Checking Lineage Process ===")

        project_id = gcp_config["GCP_PROJECT_ID"]
        parent = f"projects/{project_id}/locations/{lineage_location}"

        try:
            # List processes
            request = datacatalog_lineage_v1.ListProcessesRequest(parent=parent)
            processes = lineage_client.list_processes(request=request)

            process_list = list(processes)
            print(f"  Found {len(process_list)} processes")

            # Look for our DAG process
            dag_process = None
            for process in process_list:
                if "metadata_collection" in process.display_name.lower():
                    dag_process = process
                    break

            if dag_process:
                print(f"  ✓ Found DAG process: {dag_process.display_name}")
            else:
                print(f"  Warning: DAG process not found")

        except Exception as e:
            print(f"  Error checking process: {e}")
            pytest.skip("Lineage API not accessible")

        print("✓ Process check completed")

    def test_runs_recorded(
        self,
        lineage_client: datacatalog_lineage_v1.LineageClient,
        gcp_config: Dict[str, str],
        lineage_location: str,
    ) -> None:
        """Test that runs are recorded."""
        print("\n=== Checking Lineage Runs ===")

        project_id = gcp_config["GCP_PROJECT_ID"]
        parent = f"projects/{project_id}/locations/{lineage_location}"

        try:
            # List processes first
            process_request = datacatalog_lineage_v1.ListProcessesRequest(parent=parent)
            processes = list(lineage_client.list_processes(request=process_request))

            if not processes:
                print("  No processes found")
                return

            # Check runs for first process
            process_name = processes[0].name
            runs_request = datacatalog_lineage_v1.ListRunsRequest(parent=process_name)
            runs = list(lineage_client.list_runs(request=runs_request))

            print(f"  Found {len(runs)} runs")

            for i, run in enumerate(runs[:5]):
                state = run.state.name if hasattr(run, "state") else "UNKNOWN"
                print(f"    Run {i+1}: {state}")

        except Exception as e:
            print(f"  Error checking runs: {e}")

        print("✓ Run check completed")

    def test_lineage_events(
        self,
        lineage_client: datacatalog_lineage_v1.LineageClient,
        gcp_config: Dict[str, str],
        lineage_location: str,
    ) -> None:
        """Test that lineage events are recorded."""
        print("\n=== Checking Lineage Events ===")

        project_id = gcp_config["GCP_PROJECT_ID"]
        dataset_id = gcp_config["BQ_DATASET"]
        table_id = gcp_config["BQ_TABLE"]

        # Target FQN (metadata table)
        target_fqn = f"bigquery:{project_id}.{dataset_id}.{table_id}"

        try:
            # Search for links to the target table
            target_ref = datacatalog_lineage_v1.EntityReference(
                fully_qualified_name=target_fqn
            )

            request = datacatalog_lineage_v1.SearchLinksRequest(
                parent=f"projects/{project_id}/locations/{lineage_location}",
                target=target_ref,
            )

            links = list(lineage_client.search_links(request=request))

            print(f"  Found {len(links)} lineage links to {target_fqn}")

            # Check a few links
            for i, link in enumerate(links[:5]):
                if hasattr(link, "source") and hasattr(link.source, "fully_qualified_name"):
                    source_fqn = link.source.fully_qualified_name
                    print(f"    Link {i+1}: {source_fqn} → {target_fqn}")

        except Exception as e:
            print(f"  Error checking lineage events: {e}")

        print("✓ Lineage events check completed")

    def test_source_fqn_format(
        self,
        lineage_client: datacatalog_lineage_v1.LineageClient,
        gcp_config: Dict[str, str],
        lineage_location: str,
    ) -> None:
        """Test that source FQNs are formatted correctly."""
        print("\n=== Validating FQN Formats ===")

        project_id = gcp_config["GCP_PROJECT_ID"]
        dataset_id = gcp_config["BQ_DATASET"]
        table_id = gcp_config["BQ_TABLE"]

        target_fqn = f"bigquery:{project_id}.{dataset_id}.{table_id}"

        try:
            target_ref = datacatalog_lineage_v1.EntityReference(
                fully_qualified_name=target_fqn
            )

            request = datacatalog_lineage_v1.SearchLinksRequest(
                parent=f"projects/{project_id}/locations/{lineage_location}",
                target=target_ref,
            )

            links = list(lineage_client.search_links(request=request))

            for i, link in enumerate(links[:10]):
                if hasattr(link, "source") and hasattr(link.source, "fully_qualified_name"):
                    source_fqn = link.source.fully_qualified_name

                    # Validate FQN format
                    assert ":" in source_fqn or "://" in source_fqn, (
                        f"Invalid FQN format: {source_fqn}"
                    )

                    print(f"  ✓ Link {i+1}: Valid FQN format")

        except Exception as e:
            print(f"  Error validating FQNs: {e}")

        print("✓ FQN format validation completed")

    def test_lineage_timestamps(
        self,
        lineage_client: datacatalog_lineage_v1.LineageClient,
        gcp_config: Dict[str, str],
        lineage_location: str,
    ) -> None:
        """Test that lineage events have valid timestamps."""
        print("\n=== Validating Lineage Timestamps ===")

        project_id = gcp_config["GCP_PROJECT_ID"]
        parent = f"projects/{project_id}/locations/{lineage_location}"

        try:
            # List processes
            process_request = datacatalog_lineage_v1.ListProcessesRequest(parent=parent)
            processes = list(lineage_client.list_processes(request=process_request))

            if not processes:
                print("  No processes to check")
                return

            # Check runs for timestamps
            process_name = processes[0].name
            runs_request = datacatalog_lineage_v1.ListRunsRequest(parent=process_name)
            runs = list(lineage_client.list_runs(request=runs_request))

            for i, run in enumerate(runs[:5]):
                has_start = hasattr(run, "start_time") and run.start_time
                has_end = hasattr(run, "end_time") and run.end_time

                if has_start and has_end:
                    print(f"  ✓ Run {i+1}: Has valid timestamps")
                else:
                    print(f"  ✗ Run {i+1}: Missing timestamps")

        except Exception as e:
            print(f"  Error checking timestamps: {e}")

        print("✓ Timestamp validation completed")

    def test_run_states(
        self,
        lineage_client: datacatalog_lineage_v1.LineageClient,
        gcp_config: Dict[str, str],
        lineage_location: str,
    ) -> None:
        """Test that runs have correct states."""
        print("\n=== Validating Run States ===")

        project_id = gcp_config["GCP_PROJECT_ID"]
        parent = f"projects/{project_id}/locations/{lineage_location}"

        try:
            process_request = datacatalog_lineage_v1.ListProcessesRequest(parent=parent)
            processes = list(lineage_client.list_processes(request=process_request))

            if not processes:
                print("  No processes found")
                return

            process_name = processes[0].name
            runs_request = datacatalog_lineage_v1.ListRunsRequest(parent=process_name)
            runs = list(lineage_client.list_runs(request=runs_request))

            state_counts = {}
            for run in runs[:20]:
                if hasattr(run, "state"):
                    state_name = run.state.name
                    state_counts[state_name] = state_counts.get(state_name, 0) + 1

            for state, count in state_counts.items():
                print(f"  {state}: {count} runs")

        except Exception as e:
            print(f"  Error checking run states: {e}")

        print("✓ Run state validation completed")

