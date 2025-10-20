"""
Shared utilities for Data Catalog Lineage tracking.

This module provides a centralized interface for recording lineage across
different components (BigQuery writes, GCS writes, etc.).
"""

import logging
import os
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from google.cloud import datacatalog_lineage_v1

logger = logging.getLogger(__name__)


def is_lineage_enabled() -> bool:
    """
    Check if lineage tracking is enabled via environment variable.
    
    Returns:
        True if lineage is enabled, False otherwise
    """
    return os.getenv("LINEAGE_ENABLED", "true").lower() == "true"


def get_or_create_lineage_process(
    project_id: str,
    location: str,
    process_name: str,
    source_system: str = "bigquery",
    source_type: str = "metadata_extraction",
    extraction_method: str = "discovery",
    owner: str = "data-engineering-team"
) -> Optional[str]:
    """
    Creates or retrieves a lineage process.
    
    Args:
        project_id: GCP project ID
        location: GCP location for lineage API (e.g., 'us-central1')
        process_name: Human-readable process name (e.g., DAG name)
        source_system: Name of source system (e.g., "bigquery", "api")
        source_type: Type of source (e.g., "metadata_extraction", "report_generation")
        extraction_method: Method used (e.g., "discovery", "full", "incremental")
        owner: Team or person responsible
    
    Returns:
        Process resource name, or None if lineage is disabled or creation fails
    """
    if not is_lineage_enabled():
        return None
        
    try:
        client = datacatalog_lineage_v1.LineageClient()
        parent = f"projects/{project_id}/locations/{location}"
        
        process = datacatalog_lineage_v1.Process(
            display_name=process_name,
            attributes={
                "framework": "data_discovery_agent",
                "owner": owner,
                "source_system": source_system,
                "source_type": source_type,
                "extraction_method": extraction_method,
            }
        )
        
        request = datacatalog_lineage_v1.CreateProcessRequest(
            parent=parent,
            process=process,
        )
        
        response = client.create_process(request=request)
        logger.info(f"Created lineage process: {response.name}")
        return response.name
        
    except Exception as e:
        logger.warning(f"Failed to create lineage process (non-fatal): {e}")
        return None


def create_lineage_run(
    process_resource_name: str,
    task_id: str,
    start_time: datetime,
    end_time: datetime,
    is_success: bool
) -> Optional[str]:
    """
    Creates a lineage run representing a task execution.
    
    Args:
        process_resource_name: Parent process resource name
        task_id: Human-readable task identifier
        start_time: UTC datetime when task started
        end_time: UTC datetime when task ended
        is_success: Whether the operation succeeded
    
    Returns:
        Run resource name, or None if creation fails
    """
    if not is_lineage_enabled():
        return None
        
    try:
        client = datacatalog_lineage_v1.LineageClient()
        
        state = (datacatalog_lineage_v1.Run.State.COMPLETED 
                 if is_success 
                 else datacatalog_lineage_v1.Run.State.FAILED)
        
        run = datacatalog_lineage_v1.Run(
            start_time=start_time.astimezone(timezone.utc),
            end_time=end_time.astimezone(timezone.utc),
            state=state,
            display_name=task_id
        )
        
        request = datacatalog_lineage_v1.CreateRunRequest(
            parent=process_resource_name,
            run=run
        )
        
        response = client.create_run(request=request)
        logger.info(f"Created lineage run: {response.name}")
        return response.name
        
    except Exception as e:
        logger.warning(f"Failed to create lineage run (non-fatal): {e}")
        return None


def create_lineage_event(
    run_resource_name: str,
    source_fqn: str,
    target_fqn: str,
    start_time: datetime,
    end_time: datetime
) -> bool:
    """
    Creates a lineage event linking source to target.
    
    Args:
        run_resource_name: Parent run resource name
        source_fqn: Source asset FQN (e.g., "bigquery:project.dataset.table")
        target_fqn: Target asset FQN (e.g., "gs://bucket/path/file.md")
        start_time: UTC datetime
        end_time: UTC datetime
    
    Returns:
        True if event was created successfully, False otherwise
    """
    if not is_lineage_enabled():
        return False
        
    try:
        client = datacatalog_lineage_v1.LineageClient()
        
        source = datacatalog_lineage_v1.EntityReference(
            fully_qualified_name=source_fqn
        )
        target = datacatalog_lineage_v1.EntityReference(
            fully_qualified_name=target_fqn
        )
        
        links = [datacatalog_lineage_v1.EventLink(source=source, target=target)]
        
        lineage_event = datacatalog_lineage_v1.LineageEvent(
            links=links,
            start_time=start_time.astimezone(timezone.utc),
            end_time=end_time.astimezone(timezone.utc)
        )
        
        request = datacatalog_lineage_v1.CreateLineageEventRequest(
            parent=run_resource_name,
            lineage_event=lineage_event
        )
        
        client.create_lineage_event(request=request)
        return True
        
    except Exception as e:
        logger.warning(f"Failed to create lineage event from {source_fqn} to {target_fqn}: {e}")
        return False


def record_lineage(
    project_id: str,
    location: str,
    process_name: str,
    task_id: str,
    source_targets: List[tuple[str, str]],
    start_time: datetime,
    end_time: datetime,
    is_success: bool,
    source_system: str = "bigquery",
    source_type: str = "metadata_extraction",
    extraction_method: str = "discovery"
) -> int:
    """
    Records lineage for a data operation (high-level function).
    
    Creates a process, run, and multiple lineage events linking sources to targets.
    
    Args:
        project_id: GCP project ID
        location: GCP location for lineage API
        process_name: Human-readable process name
        task_id: Task identifier
        source_targets: List of (source_fqn, target_fqn) tuples
        start_time: UTC datetime when operation started
        end_time: UTC datetime when operation ended
        is_success: Whether the operation succeeded
        source_system: Name of source system
        source_type: Type of source operation
        extraction_method: Method used for extraction
    
    Returns:
        Number of lineage events successfully created
    """
    if not is_lineage_enabled() or not source_targets:
        return 0
        
    try:
        # Get or create process
        process_resource_name = get_or_create_lineage_process(
            project_id=project_id,
            location=location,
            process_name=process_name,
            source_system=source_system,
            source_type=source_type,
            extraction_method=extraction_method
        )
        
        if not process_resource_name:
            return 0
        
        # Create run
        run_resource_name = create_lineage_run(
            process_resource_name=process_resource_name,
            task_id=task_id,
            start_time=start_time,
            end_time=end_time,
            is_success=is_success
        )
        
        if not run_resource_name:
            return 0
        
        # Create lineage events
        events_created = 0
        for source_fqn, target_fqn in source_targets:
            if create_lineage_event(
                run_resource_name=run_resource_name,
                source_fqn=source_fqn,
                target_fqn=target_fqn,
                start_time=start_time,
                end_time=end_time
            ):
                events_created += 1
        
        logger.info(f"Successfully recorded lineage for {events_created}/{len(source_targets)} events")
        return events_created
        
    except Exception as e:
        logger.warning(f"Failed to record lineage (non-fatal): {e}")
        return 0


def format_bigquery_fqn(project_id: str, dataset_id: str, table_id: str) -> str:
    """
    Formats a BigQuery table FQN for lineage.
    
    Args:
        project_id: GCP project ID
        dataset_id: BigQuery dataset ID
        table_id: BigQuery table ID
    
    Returns:
        Properly formatted FQN (e.g., "bigquery:project.dataset.table")
    """
    return f"bigquery:{project_id}.{dataset_id}.{table_id}"


def format_gcs_fqn(bucket: str, path: str) -> str:
    """
    Formats a GCS file FQN for lineage.
    
    Args:
        bucket: GCS bucket name
        path: File path within bucket
    
    Returns:
        Properly formatted FQN (e.g., "gs://bucket/path/file.md")
    """
    # Remove leading slash if present
    path = path.lstrip('/')
    return f"gs://{bucket}/{path}"

