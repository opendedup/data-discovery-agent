"""
Airflow Task Functions for Metadata Collection

This module contains the core logic for each step of the metadata collection
process, designed to be called by an Airflow DAG.
"""

import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Any

from data_discovery_agent.collectors import BigQueryCollector
from data_discovery_agent.search import MetadataFormatter, MarkdownFormatter
from data_discovery_agent.search.jsonl_schema import BigQueryAssetSchema
from data_discovery_agent.clients import VertexSearchClient
from data_discovery_agent.writers.bigquery_writer import BigQueryWriter

logger = logging.getLogger(__name__)

def collect_metadata_task(**context: Any) -> None:
    """
    Airflow task to collect metadata from BigQuery.
    
    Configuration is read from environment variables (set in Composer),
    with optional overrides from dag_run.conf for manual runs.
    
    Args:
        **context: Airflow context with dag_run and task instance info
        
    Raises:
        ValueError: If no assets are collected or required env vars are missing
    """
    # Get configuration from environment variables (primary source)
    project_id = os.getenv('GCP_PROJECT_ID')
    if not project_id:
        raise ValueError("GCP_PROJECT_ID environment variable is required")
    
    # Allow manual override via dag_run.conf for testing/manual runs
    args = context.get('dag_run', {}).conf if context.get('dag_run') else {}
    conf_args = args.get('collector_args', {}) if args else {}
    
    logger.info("Starting metadata collection task.")
    collector = BigQueryCollector(
        project_id=conf_args.get('project', project_id),
        target_projects=conf_args.get('projects', [project_id]),
        exclude_datasets=conf_args.get('exclude_datasets', ['_staging', 'temp_', 'tmp_']),
        use_dataplex_profiling=conf_args.get('use_dataplex', False),
        dataplex_location=conf_args.get('dataplex_location', 'us-central1'),
        use_gemini_descriptions=conf_args.get('use_gemini', True),
        gemini_api_key=conf_args.get('gemini_api_key', os.getenv('GEMINI_API_KEY')),
        max_workers=conf_args.get('workers', 2),
    )
    
    assets = collector.collect_all(
        max_tables=conf_args.get('max_tables'),
        include_views=not conf_args.get('skip_views', False),
    )
    
    if not assets:
        raise ValueError("No assets found or collected.")
        
    logger.info(f"Collected {len(assets)} assets.")
    
    # Push assets to XComs for downstream tasks
    # Pydantic models need to be converted to dicts for XCom serialization
    asset_dicts = [asset.model_dump() for asset in assets]
    context['ti'].xcom_push(key='assets', value=asset_dicts)


def export_to_bigquery_task(**context: Any) -> None:
    """
    Airflow task to export metadata to a BigQuery table.
    
    Configuration is read from environment variables (set in Composer),
    with optional overrides from dag_run.conf for manual runs.
    
    Args:
        **context: Airflow context with dag_run and task instance info
        
    Raises:
        ValueError: If required environment variables are missing
    """
    # Get configuration from environment variables (primary source)
    project_id = os.getenv('GCP_PROJECT_ID')
    bq_dataset = os.getenv('BQ_DATASET', 'data_discovery')
    bq_table = os.getenv('BQ_TABLE', 'discovered_assets')
    
    if not project_id:
        raise ValueError("GCP_PROJECT_ID environment variable is required")
    
    # Allow manual override via dag_run.conf for testing/manual runs
    args = context.get('dag_run', {}).conf if context.get('dag_run') else {}
    conf_args = args.get('bq_writer_args', {}) if args else {}
    
    assets = context['ti'].xcom_pull(key='assets', task_ids='collect_metadata')
    
    if not assets:
        logger.warning("No assets to export to BigQuery.")
        return

    logger.info("Starting BigQuery export task.")
    bq_writer = BigQueryWriter(
        project_id=conf_args.get('project', project_id),
        dataset_id=conf_args.get('bq_dataset', bq_dataset),
        table_id=conf_args.get('bq_table', bq_table)
    )
    
    bq_writer.write_to_bigquery(assets=assets)
    
    # Push run_timestamp to XCom for use by other tasks (e.g., markdown reports)
    run_timestamp = bq_writer.run_timestamp.strftime("%Y%m%d_%H%M%S")
    context['ti'].xcom_push(key='run_timestamp', value=run_timestamp)
    
    logger.info(f"Finished BigQuery export task. Run timestamp: {run_timestamp}")


def import_to_vertex_ai_task(**context: Any) -> None:
    """
    Airflow task to trigger Vertex AI Search import from BigQuery.
    
    Configuration is read from environment variables (set in Composer),
    with optional overrides from dag_run.conf for manual runs.
    
    Args:
        **context: Airflow context with dag_run and task instance info
        
    Raises:
        ValueError: If required environment variables are missing
    """
    # Get configuration from environment variables (primary source)
    project_id = os.getenv('GCP_PROJECT_ID')
    datastore_id = os.getenv('VERTEX_DATASTORE_ID')
    vertex_location = os.getenv('VERTEX_LOCATION', 'global')
    bq_dataset = os.getenv('BQ_DATASET', 'data_discovery')
    bq_table = os.getenv('BQ_TABLE', 'discovered_assets')
    
    if not project_id:
        raise ValueError("GCP_PROJECT_ID environment variable is required")
    if not datastore_id:
        raise ValueError("VERTEX_DATASTORE_ID environment variable is required")
    
    # Allow manual override via dag_run.conf for testing/manual runs
    args = context.get('dag_run', {}).conf if context.get('dag_run') else {}
    conf_args = args.get('vertex_ai_args', {}) if args else {}

    logger.info("Starting Vertex AI Search import task.")
    client = VertexSearchClient(
        project_id=conf_args.get('project', project_id),
        location=conf_args.get('location', vertex_location),
        datastore_id=conf_args.get('datastore', datastore_id),
    )
    
    operation_name = client.import_documents_from_bigquery(
        dataset_id=conf_args.get('bq_dataset', bq_dataset),
        table_id=conf_args.get('bq_table', bq_table),
        reconciliation_mode="INCREMENTAL",
    )
    logger.info(f"Vertex AI Search import started. Operation: {operation_name}")


def export_markdown_reports_task(**context: Any) -> None:
    """
    Airflow task to generate and export Markdown reports to GCS.
    
    Configuration is read from environment variables (set in Composer),
    with optional overrides from dag_run.conf for manual runs.
    
    Args:
        **context: Airflow context with dag_run and task instance info
        
    Raises:
        ValueError: If required environment variables are missing
    """
    # Get configuration from environment variables (primary source)
    project_id = os.getenv('GCP_PROJECT_ID')
    reports_bucket = os.getenv('GCS_REPORTS_BUCKET')
    
    if not project_id:
        raise ValueError("GCP_PROJECT_ID environment variable is required")
    if not reports_bucket:
        raise ValueError("GCS_REPORTS_BUCKET environment variable is required")
    
    # Allow manual override via dag_run.conf for testing/manual runs
    args = context.get('dag_run', {}).conf if context.get('dag_run') else {}
    conf_args = args.get('markdown_args', {}) if args else {}
    
    # Get assets from XCom
    asset_dicts = context['ti'].xcom_pull(key='assets', task_ids='collect_metadata')
    
    # Get run_timestamp from BigQuery export task (or generate if not available)
    run_timestamp = context['ti'].xcom_pull(key='run_timestamp', task_ids='export_to_bigquery')
    if not run_timestamp:
        # Fallback: generate timestamp if BigQuery task didn't run or failed
        run_timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        logger.warning(f"No run_timestamp from BigQuery export, using generated: {run_timestamp}")
    
    if not asset_dicts:
        logger.warning("No assets to generate markdown reports for.")
        return
    
    logger.info(f"Starting Markdown report generation for {len(asset_dicts)} assets.")
    logger.info(f"Using run_timestamp: {run_timestamp}")
    
    # Initialize formatter
    formatter = MarkdownFormatter(project_id=project_id)
    
    # Generate and upload reports
    reports_generated = 0
    for asset_dict in asset_dicts:
        try:
            # Convert dict back to BigQueryAssetSchema
            asset = BigQueryAssetSchema(**asset_dict)
            
            # Generate markdown report
            markdown = formatter.generate_table_report(asset)
            
            # Construct GCS path
            table_id = asset.struct_data.table_id
            dataset_id = asset.struct_data.dataset_id
            project = asset.struct_data.project_id
            gcs_path = f"reports/{run_timestamp}/{project}/{dataset_id}/{table_id}.md"
            
            # Upload to GCS
            gcs_uri = formatter.export_to_gcs(
                markdown=markdown,
                gcs_bucket=reports_bucket,
                gcs_path=gcs_path
            )
            
            reports_generated += 1
            
            if reports_generated % 10 == 0:
                logger.info(f"Generated {reports_generated}/{len(asset_dicts)} reports...")
                
        except Exception as e:
            logger.error(f"Failed to generate report for asset {asset_dict.get('id', 'unknown')}: {e}")
            continue
    
    logger.info(f"Finished Markdown report generation. Generated {reports_generated}/{len(asset_dicts)} reports.")
    logger.info(f"Reports available in gs://{reports_bucket}/reports/{run_timestamp}/")
