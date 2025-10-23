"""
Airflow Task Functions for Metadata Collection

This module contains the core logic for each step of the metadata collection
process, designed to be called by an Airflow DAG.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any

from google.cloud import storage
from data_discovery_agent.collectors import BigQueryCollector
from data_discovery_agent.search import MarkdownFormatter
from data_discovery_agent.clients import VertexSearchClient
from data_discovery_agent.writers.bigquery_writer import BigQueryWriter
from data_discovery_agent.utils.lineage import record_lineage, format_bigquery_fqn
from data_discovery_agent.orchestration.gcs_scratch import (
    write_scratch_json,
    read_scratch_json,
    cleanup_old_scratch_files,
)

logger = logging.getLogger(__name__)


def collect_metadata_task(**context: Any) -> None:
    """
    Airflow task to collect metadata from BigQuery.
    
    Configuration is read from environment variables (set in Composer),
    with optional overrides from dag_run.conf for manual runs.
    
    Records lineage showing BigQuery tables → GCS scratch file as an intermediate
    step in the metadata collection pipeline.
    
    Args:
        **context: Airflow context with dag_run and task instance info
        
    Raises:
        ValueError: If no assets are collected or required env vars are missing
    """
    # Track start time for lineage
    start_time = datetime.now(timezone.utc)
    is_success = False
    gcs_path = None
    collected_tables = []
    
    # Get configuration early for finally block
    project_id = os.getenv('GCP_PROJECT_ID', '')
    lineage_location = os.getenv('LINEAGE_LOCATION', 'us-central1')
    
    try:
        # Get configuration from environment variables (primary source)
        if not project_id:
            raise ValueError("GCP_PROJECT_ID environment variable is required")
        
        filter_label_key = os.getenv('DISCOVERY_FILTER_LABEL_KEY', 'ignore-gmcp-discovery-scan')
        
        # Get default params from DAG definition, then override with dag_run.conf if provided
        default_params = context.get('params', {})
        dag_run_conf = context.get('dag_run', {}).conf if context.get('dag_run') else {}
        
        # Merge: DAG params as base, override with manual trigger config
        conf_args = {**default_params.get('collector_args', {}), **dag_run_conf.get('collector_args', {})}
        
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
            filter_label_key=conf_args.get('filter_label_key', filter_label_key),
        )
        
        assets = collector.collect_all(
            max_tables=conf_args.get('max_tables'),
            include_views=not conf_args.get('skip_views', False),
        )
        
        if not assets:
            raise ValueError("No assets found or collected.")
            
        logger.info(f"Collected {len(assets)} assets.")
        
        # Track collected tables for lineage
        for asset in assets:
            table_full_name = f"{asset.get('project_id', project_id)}.{asset.get('dataset_id')}.{asset.get('table_id')}"
            collected_tables.append(table_full_name)
        
        # Write assets to GCS scratch storage instead of XCom for better scalability
        reports_bucket = os.getenv('GCS_REPORTS_BUCKET')
        if not reports_bucket:
            raise ValueError("GCS_REPORTS_BUCKET environment variable is required")
        
        run_id = context['run_id']
        gcs_path = write_scratch_json(
            data=assets,
            bucket=reports_bucket,
            run_id=run_id,
            filename='assets'
        )
        
        # Push only the GCS path to XCom (tiny string instead of large data)
        context['ti'].xcom_push(key='assets_gcs_path', value=gcs_path)
        logger.info(f"Assets written to GCS scratch: {gcs_path}")
        
        # Mark success
        is_success = True
        
    finally:
        # Record lineage regardless of success/failure
        end_time = datetime.now(timezone.utc)
        if project_id and gcs_path and collected_tables:
            dag_id = context.get('dag', {}).dag_id if context.get('dag') else 'metadata_collection'
            task_id = context.get('task', {}).task_id if context.get('task') else 'collect_metadata'
            
            # Build source-target pairs for lineage (BigQuery tables → GCS scratch file)
            # Multiple source tables are collected into a single scratch file
            source_targets = []
            for table_name in collected_tables:
                if '.' in table_name:
                    source_fqn = format_bigquery_fqn(*table_name.split('.'))
                    source_targets.append((source_fqn, gcs_path))
            
            record_lineage(
                project_id=project_id,
                location=lineage_location,
                process_name=dag_id,
                task_id=task_id,
                source_targets=source_targets,
                start_time=start_time,
                end_time=end_time,
                is_success=is_success,
                source_system="bigquery",
                source_type="metadata_collection",
                extraction_method="scratch_storage"
            )


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
    
    # Read assets from GCS scratch storage
    assets_gcs_path = context['ti'].xcom_pull(key='assets_gcs_path', task_ids='collect_metadata')
    
    if not assets_gcs_path:
        logger.warning("No assets GCS path found in XCom.")
        return
    
    logger.info(f"Reading assets from GCS scratch: {assets_gcs_path}")
    assets = read_scratch_json(assets_gcs_path)
    
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
        reconciliation_mode="FULL",
    )
    logger.info(f"Vertex AI Search import started. Operation: {operation_name}")


def export_markdown_reports_task(**context: Any) -> None:
    """
    Airflow task to generate and export Markdown reports to GCS.
    
    Configuration is read from environment variables (set in Composer),
    with optional overrides from dag_run.conf for manual runs.
    
    Records lineage showing data flow from discovered BigQuery tables to GCS markdown files.
    
    Args:
        **context: Airflow context with dag_run and task instance info
        
    Raises:
        ValueError: If required environment variables are missing
    """
    # Track start time for lineage
    start_time = datetime.now(timezone.utc)
    is_success = False
    source_tables = []
    gcs_uris = []
    
    # Get configuration early for finally block
    project_id = os.getenv('GCP_PROJECT_ID', '')
    lineage_location = os.getenv('LINEAGE_LOCATION', 'us-central1')
    
    try:
        # Get full configuration from environment variables (primary source)
        reports_bucket = os.getenv('GCS_REPORTS_BUCKET')
        
        if not project_id:
            raise ValueError("GCP_PROJECT_ID environment variable is required")
        if not reports_bucket:
            raise ValueError("GCS_REPORTS_BUCKET environment variable is required")
        
        # Allow manual override via dag_run.conf for testing/manual runs
        args = context.get('dag_run', {}).conf if context.get('dag_run') else {}
        
        # Read assets from GCS scratch storage
        assets_gcs_path = context['ti'].xcom_pull(key='assets_gcs_path', task_ids='collect_metadata')
        
        if not assets_gcs_path:
            logger.warning("No assets GCS path found in XCom.")
            return
        
        logger.info(f"Reading assets from GCS scratch: {assets_gcs_path}")
        asset_dicts = read_scratch_json(assets_gcs_path)
        
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
                # Generate markdown report (asset_dict is already a plain dict)
                markdown = formatter.generate_table_report(asset_dict)
                
                # Construct GCS path
                table_id = asset_dict.get("table_id", "unknown")
                dataset_id = asset_dict.get("dataset_id", "unknown")
                project = asset_dict.get("project_id", project_id)
                gcs_path = f"reports/{run_timestamp}/{project}/{dataset_id}/{table_id}.md"
                
                # Upload to GCS
                gcs_uri = formatter.export_to_gcs(
                    markdown=markdown,
                    gcs_bucket=reports_bucket,
                    gcs_path=gcs_path
                )
                
                # Track for lineage
                table_full_name = f"{project}.{dataset_id}.{table_id}"
                source_tables.append(table_full_name)
                gcs_uris.append(gcs_uri)
                
                reports_generated += 1
                
                if reports_generated % 10 == 0:
                    logger.info(f"Generated {reports_generated}/{len(asset_dicts)} reports...")
                    
            except Exception as e:
                logger.error(f"Failed to generate report for asset {asset_dict.get('id', 'unknown')}: {e}")
                continue
        
        logger.info(f"Finished Markdown report generation. Generated {reports_generated}/{len(asset_dicts)} reports.")
        logger.info(f"Reports available in gs://{reports_bucket}/reports/{run_timestamp}/")
        
        # Mark success
        is_success = True
        
    finally:
        # Record lineage regardless of success/failure
        end_time = datetime.now(timezone.utc)
        if project_id and source_tables and gcs_uris:
            dag_id = context.get('dag', {}).dag_id if context.get('dag') else 'metadata_collection'
            task_id = context.get('task', {}).task_id if context.get('task') else 'export_markdown_reports'
            
            # Build source-target pairs for lineage (BigQuery tables → GCS markdown files)
            source_targets = []
            for i, source_table in enumerate(source_tables):
                if i < len(gcs_uris) and '.' in source_table:
                    source_fqn = format_bigquery_fqn(*source_table.split('.'))
                    target_fqn = gcs_uris[i]
                    source_targets.append((source_fqn, target_fqn))
            
            record_lineage(
                project_id=project_id,
                location=lineage_location,
                process_name=dag_id,
                task_id=task_id,
                source_targets=source_targets,
                start_time=start_time,
                end_time=end_time,
                is_success=is_success,
                source_system="bigquery",
                source_type="report_generation",
                extraction_method="markdown_export"
            )


def cleanup_scratch_files_task(**context: Any) -> None:
    """
    Airflow task to clean up old scratch files from GCS.
    
    Deletes scratch files older than the configured retention period to save storage costs.
    This task runs at the end of the DAG with trigger_rule='all_done' so it executes
    even if upstream tasks fail.
    
    Configuration is read from environment variables:
    - GCS_REPORTS_BUCKET: Bucket containing scratch files
    - SCRATCH_RETENTION_DAYS: Number of days to retain files (default: 7)
    
    Args:
        **context: Airflow context with dag_run and task instance info
    """
    try:
        # Get configuration from environment variables
        reports_bucket = os.getenv('GCS_REPORTS_BUCKET')
        retention_days = int(os.getenv('SCRATCH_RETENTION_DAYS', '7'))
        
        if not reports_bucket:
            logger.warning(
                "GCS_REPORTS_BUCKET not configured, skipping scratch file cleanup"
            )
            return
        
        logger.info(
            f"Starting scratch file cleanup in gs://{reports_bucket}/airflow-scratch/"
        )
        logger.info(f"Retention period: {retention_days} days")
        
        # Clean up old files
        files_deleted, files_failed = cleanup_old_scratch_files(
            bucket=reports_bucket,
            days_to_keep=retention_days
        )
        
        logger.info(
            f"Scratch file cleanup complete: {files_deleted} files deleted, "
            f"{files_failed} files failed"
        )
        
    except ValueError as e:
        logger.error(f"Configuration error in cleanup task: {e}")
        # Non-fatal: log error but don't fail the task
        
    except Exception as e:
        logger.error(f"Error during scratch file cleanup: {e}")
        # Non-fatal: cleanup failures shouldn't fail the DAG
