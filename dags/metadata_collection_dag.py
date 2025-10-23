from __future__ import annotations

import pendulum  # type: ignore

from airflow.models.dag import DAG  # type: ignore
from airflow.operators.python import PythonOperator  # type: ignore

# Add src to path to allow for absolute imports of the agent modules
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from data_discovery_agent.orchestration.tasks import (
    collect_metadata_task,
    export_to_bigquery_task,
    export_markdown_reports_task,
    import_to_vertex_ai_task,
    cleanup_scratch_files_task,
)

with DAG(
    dag_id="bigquery_metadata_collection",
    start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
    catchup=False,
    schedule="@daily",
    tags=["data-discovery-agent"],
    params={
        "collector_args": {
            "use_dataplex": True,  # Enable Dataplex profiling (avoids SQL MIN/MAX errors on complex types)
            "dataplex_location": "us-central1",
            "use_gemini": True,  # Enable Gemini-generated descriptions
            "workers": 2,  # Parallel workers for collection
            "max_tables": None,  # Set to None to collect all tables (or set a specific limit for testing)
            # Uncomment to override defaults:
            # "skip_views": False,  # Include/exclude views
            # "exclude_datasets": ["_staging", "temp_", "tmp_"],
        }
    },
) as dag:
    collect_metadata = PythonOperator(
        task_id="collect_metadata",
        python_callable=collect_metadata_task,
    )

    export_to_bigquery = PythonOperator(
        task_id="export_to_bigquery",
        python_callable=export_to_bigquery_task,
    )

    export_markdown_reports = PythonOperator(
        task_id="export_markdown_reports",
        python_callable=export_markdown_reports_task,
    )

    import_to_vertex_ai = PythonOperator(
        task_id="import_to_vertex_ai",
        python_callable=import_to_vertex_ai_task,
    )

    cleanup_scratch = PythonOperator(
        task_id="cleanup_scratch_files",
        python_callable=cleanup_scratch_files_task,
        trigger_rule='all_done',  # Run even if upstream tasks fail
    )

    # DAG flow: collect metadata -> export to BigQuery -> generate markdown reports + import to Vertex AI -> cleanup scratch files
    # Markdown reports use the same run_timestamp as BigQuery for correlation
    # Cleanup runs at the end to remove old scratch files, regardless of upstream task status
    collect_metadata >> export_to_bigquery >> [export_markdown_reports, import_to_vertex_ai] >> cleanup_scratch
