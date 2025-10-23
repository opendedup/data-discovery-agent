"""
GCS Scratch File Utilities

Helper functions for managing intermediate data storage in GCS during Airflow DAG execution.
Uses GCS instead of XCom for large data transfers between tasks to improve scalability and performance.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from google.cloud import storage
from google.cloud.exceptions import NotFound

logger = logging.getLogger(__name__)


def get_scratch_path(bucket: str, run_id: str, filename: str) -> str:
    """
    Generate a consistent GCS path for scratch files.
    
    Args:
        bucket: GCS bucket name (without gs:// prefix)
        run_id: Airflow run_id for uniqueness
        filename: Name of the file (without extension)
        
    Returns:
        Full GCS URI in format: gs://bucket/airflow-scratch/run_id/filename.json
    """
    return f"gs://{bucket}/airflow-scratch/{run_id}/{filename}.json"


def write_scratch_json(data: Any, bucket: str, run_id: str, filename: str) -> str:
    """
    Write data as JSON to GCS scratch location.
    
    Args:
        data: Data to serialize as JSON (must be JSON-serializable)
        bucket: GCS bucket name (without gs:// prefix)
        run_id: Airflow run_id for uniqueness
        filename: Name of the file (without extension)
        
    Returns:
        Full GCS URI where data was written
        
    Raises:
        ValueError: If data cannot be serialized to JSON
        google.cloud.exceptions.GoogleCloudError: If GCS write fails
    """
    gcs_path = get_scratch_path(bucket, run_id, filename)
    blob_path = f"airflow-scratch/{run_id}/{filename}.json"
    
    try:
        # Serialize to JSON
        json_data = json.dumps(data, indent=2)
        
        # Upload to GCS
        storage_client = storage.Client()
        bucket_obj = storage_client.bucket(bucket)
        blob = bucket_obj.blob(blob_path)
        blob.upload_from_string(json_data, content_type="application/json")
        
        logger.info(f"Wrote scratch data to {gcs_path} ({len(json_data)} bytes)")
        return gcs_path
        
    except (TypeError, ValueError) as e:
        logger.error(f"Failed to serialize data to JSON: {e}")
        raise ValueError(f"Data is not JSON-serializable: {e}") from e
    except Exception as e:
        logger.error(f"Failed to write scratch file to {gcs_path}: {e}")
        raise


def read_scratch_json(gcs_path: str) -> Any:
    """
    Read JSON data from GCS scratch location.
    
    Args:
        gcs_path: Full GCS URI (gs://bucket/path/to/file.json)
        
    Returns:
        Deserialized JSON data (usually a dict or list)
        
    Raises:
        ValueError: If gcs_path is invalid or JSON cannot be parsed
        google.cloud.exceptions.NotFound: If file doesn't exist
        google.cloud.exceptions.GoogleCloudError: If GCS read fails
    """
    if not gcs_path or not gcs_path.startswith("gs://"):
        raise ValueError(f"Invalid GCS path: {gcs_path}")
    
    try:
        # Parse GCS URI
        path_without_prefix = gcs_path.replace("gs://", "")
        bucket_name, blob_path = path_without_prefix.split("/", 1)
        
        # Download from GCS
        storage_client = storage.Client()
        bucket_obj = storage_client.bucket(bucket_name)
        blob = bucket_obj.blob(blob_path)
        
        if not blob.exists():
            raise NotFound(f"Scratch file not found: {gcs_path}")
        
        json_data = blob.download_as_text()
        data = json.loads(json_data)
        
        logger.info(f"Read scratch data from {gcs_path} ({len(json_data)} bytes)")
        return data
        
    except NotFound:
        logger.error(f"Scratch file not found: {gcs_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from {gcs_path}: {e}")
        raise ValueError(f"Invalid JSON in scratch file: {e}") from e
    except Exception as e:
        logger.error(f"Failed to read scratch file from {gcs_path}: {e}")
        raise


def cleanup_old_scratch_files(bucket: str, days_to_keep: int = 7) -> Tuple[int, int]:
    """
    Delete scratch files older than the specified retention period.
    
    Args:
        bucket: GCS bucket name (without gs:// prefix)
        days_to_keep: Number of days to retain scratch files (default: 7)
        
    Returns:
        Tuple of (files_deleted, files_failed) counts
        
    Raises:
        google.cloud.exceptions.GoogleCloudError: If GCS operations fail
    """
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
    files_deleted = 0
    files_failed = 0
    
    logger.info(f"Starting scratch file cleanup in gs://{bucket}/airflow-scratch/")
    logger.info(f"Deleting files older than {cutoff_time.isoformat()} ({days_to_keep} days)")
    
    try:
        storage_client = storage.Client()
        bucket_obj = storage_client.bucket(bucket)
        
        # List all blobs in the scratch prefix
        blobs = bucket_obj.list_blobs(prefix="airflow-scratch/")
        
        for blob in blobs:
            try:
                # Check if file is older than retention period
                if blob.time_created and blob.time_created < cutoff_time:
                    logger.debug(f"Deleting old scratch file: gs://{bucket}/{blob.name}")
                    blob.delete()
                    files_deleted += 1
                    
                    # Log progress every 100 files
                    if files_deleted % 100 == 0:
                        logger.info(f"Deleted {files_deleted} old scratch files...")
                        
            except Exception as e:
                logger.warning(f"Failed to delete gs://{bucket}/{blob.name}: {e}")
                files_failed += 1
                continue
        
        logger.info(
            f"Scratch file cleanup complete: {files_deleted} deleted, {files_failed} failed"
        )
        return (files_deleted, files_failed)
        
    except Exception as e:
        logger.error(f"Error during scratch file cleanup: {e}")
        raise


def list_scratch_files(bucket: str, run_id: str = None) -> List[Dict[str, Any]]:
    """
    List scratch files in the bucket, optionally filtered by run_id.
    
    Useful for debugging and inspecting intermediate data.
    
    Args:
        bucket: GCS bucket name (without gs:// prefix)
        run_id: Optional Airflow run_id to filter by
        
    Returns:
        List of dicts with file metadata: {name, size, created, uri}
        
    Raises:
        google.cloud.exceptions.GoogleCloudError: If GCS operations fail
    """
    prefix = f"airflow-scratch/{run_id}/" if run_id else "airflow-scratch/"
    
    try:
        storage_client = storage.Client()
        bucket_obj = storage_client.bucket(bucket)
        blobs = bucket_obj.list_blobs(prefix=prefix)
        
        files = []
        for blob in blobs:
            files.append({
                "name": blob.name,
                "size": blob.size,
                "created": blob.time_created.isoformat() if blob.time_created else None,
                "uri": f"gs://{bucket}/{blob.name}",
            })
        
        logger.info(f"Found {len(files)} scratch files in gs://{bucket}/{prefix}")
        return files
        
    except Exception as e:
        logger.error(f"Failed to list scratch files in gs://{bucket}/{prefix}: {e}")
        raise

