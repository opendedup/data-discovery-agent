from __future__ import annotations

import pendulum  # type: ignore

from airflow.models.dag import DAG  # type: ignore
from airflow.operators.python import PythonOperator  # type: ignore

# Add src to path to allow for absolute imports of the agent modules
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_discovery_agent.orchestration.tasks import (
    collect_metadata_task,
    export_to_bigquery_task,
    export_markdown_reports_task,
    import_to_vertex_ai_task,
)

with DAG(
    dag_id="bigquery_metadata_collection",
    start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
    catchup=False,
    schedule="@daily",
    tags=["data-discovery-agent"],
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

    # DAG flow: collect metadata -> export to BigQuery -> generate markdown reports + import to Vertex AI
    # Markdown reports use the same run_timestamp as BigQuery for correlation
    collect_metadata >> export_to_bigquery >> [export_markdown_reports, import_to_vertex_ai]
