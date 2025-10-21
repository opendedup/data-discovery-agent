"""Test data fixtures and factory functions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import Mock

from google.cloud import bigquery

# Removed deprecated imports - using plain dicts now


def create_mock_dataset(
    project_id: str = "test-project",
    dataset_id: str = "test_dataset",
    location: str = "US",
    description: str = "Test dataset",
) -> Mock:
    """
    Create a mock BigQuery dataset.
    
    Args:
        project_id: Project ID
        dataset_id: Dataset ID
        location: Dataset location
        description: Dataset description
        
    Returns:
        Mock BigQuery dataset
    """
    mock_dataset = Mock(spec=bigquery.Dataset)
    mock_dataset.project = project_id
    mock_dataset.dataset_id = dataset_id
    mock_dataset.location = location
    mock_dataset.description = description
    mock_dataset.created = datetime(2024, 1, 1, tzinfo=timezone.utc)
    mock_dataset.modified = datetime.now(timezone.utc)
    return mock_dataset


def create_mock_bigquery_table(
    project_id: str = "test-project",
    dataset_id: str = "test_dataset",
    table_id: str = "test_table",
    table_type: str = "TABLE",
    description: str = "Test table for unit testing",
    num_rows: int = 1000,
    num_bytes: int = 50000,
    schema: Optional[List[Dict[str, str]]] = None,
) -> Mock:
    """
    Create a mock BigQuery table with schema.
    
    Args:
        project_id: Project ID
        dataset_id: Dataset ID
        table_id: Table ID
        table_type: Table type (TABLE or VIEW)
        description: Table description
        num_rows: Number of rows
        num_bytes: Size in bytes
        schema: List of schema field dictionaries
        
    Returns:
        Mock BigQuery table
    """
    mock_table = Mock(spec=bigquery.Table)
    mock_table.project = project_id
    mock_table.dataset_id = dataset_id
    mock_table.table_id = table_id
    mock_table.table_type = table_type
    mock_table.description = description
    mock_table.num_rows = num_rows
    mock_table.num_bytes = num_bytes
    mock_table.created = datetime(2024, 1, 1, tzinfo=timezone.utc)
    mock_table.modified = datetime.now(timezone.utc)

    # Create schema
    if schema is None:
        schema = [
            {
                "name": "id",
                "type": "STRING",
                "mode": "REQUIRED",
                "description": "Unique identifier",
            },
            {
                "name": "name",
                "type": "STRING",
                "mode": "NULLABLE",
                "description": "Name field",
            },
            {
                "name": "created_at",
                "type": "TIMESTAMP",
                "mode": "NULLABLE",
                "description": "Creation timestamp",
            },
        ]

    mock_schema = []
    for field in schema:
        mock_field = Mock(spec=bigquery.SchemaField)
        mock_field.name = field["name"]
        mock_field.field_type = field["type"]
        mock_field.mode = field.get("mode", "NULLABLE")
        mock_field.description = field.get("description", "")
        mock_schema.append(mock_field)

    mock_table.schema = mock_schema
    return mock_table


def create_sample_asset_schema(
    project_id: str = "test-project",
    dataset_id: str = "test_dataset",
    table_id: str = "test_table",
    description: str = "Sample test table for unit testing purposes",
) -> Dict[str, Any]:
    """
    Create a sample asset dict for testing.
    
    Args:
        project_id: Project ID
        dataset_id: Dataset ID
        table_id: Table ID
        description: Table description
        
    Returns:
        Dict representing a BigQuery asset
    """
    schema_fields = [
        {
            "name": "id",
            "type": "STRING",
            "mode": "REQUIRED",
            "description": "Unique identifier for the record",
        },
        {
            "name": "name",
            "type": "STRING",
            "mode": "NULLABLE",
            "description": "Name of the entity",
        },
        {
            "name": "created_at",
            "type": "TIMESTAMP",
            "mode": "NULLABLE",
            "description": "Timestamp when the record was created",
        },
    ]

    return {
        "project_id": project_id,
        "dataset_id": dataset_id,
        "table_id": table_id,
        "description": description,
        "table_type": "TABLE",
        "created": "2024-01-01T00:00:00Z",
        "last_modified": "2024-10-20T00:00:00Z",
        "last_accessed": None,
        "row_count": 1000,
        "column_count": 3,
        "size_bytes": 50000,
        "has_pii": False,
        "has_phi": False,
        "environment": "test",
        "labels": [],
        "schema": schema_fields,
        "analytical_insights": [],
        "lineage": [],
        "column_profiles": [],
        "key_metrics": [],
        "_extended": {
            "schema_info": {"fields": schema_fields},
            "lineage_info": {"upstream_tables": [], "downstream_tables": []},
            "cost_info": {},
            "quality_info": {},
            "security_info": {"has_pii": False, "has_phi": False},
            "governance_info": {"labels": {}, "tags": [], "environment": "test"},
        }
    }


def create_sample_profile_result() -> Dict[str, Any]:
    """
    Create a sample Dataplex profile result.
    
    Returns:
        Dictionary representing a profile result
    """
    return {
        "row_count": 1000,
        "profile": {
            "fields": [
                {
                    "name": "id",
                    "type": "STRING",
                    "mode": "REQUIRED",
                    "profile": {
                        "null_ratio": 0.0,
                        "distinct_ratio": 1.0,
                        "string_profile": {
                            "min_length": 10,
                            "max_length": 36,
                            "average_length": 32.5,
                        },
                    },
                },
                {
                    "name": "name",
                    "type": "STRING",
                    "mode": "NULLABLE",
                    "profile": {
                        "null_ratio": 0.05,
                        "distinct_ratio": 0.95,
                        "string_profile": {
                            "min_length": 1,
                            "max_length": 100,
                            "average_length": 25.3,
                        },
                    },
                },
                {
                    "name": "email",
                    "type": "STRING",
                    "mode": "NULLABLE",
                    "profile": {
                        "null_ratio": 0.02,
                        "distinct_ratio": 0.98,
                        "string_profile": {
                            "min_length": 5,
                            "max_length": 100,
                            "average_length": 28.7,
                        },
                    },
                    "info_types": [
                        {
                            "name": "EMAIL_ADDRESS",
                            "count": 980,
                        }
                    ],
                },
            ],
        },
    }


def create_sample_markdown_report(
    project_id: str = "test-project",
    dataset_id: str = "test_dataset",
    table_id: str = "test_table",
) -> str:
    """
    Create a sample markdown report.
    
    Args:
        project_id: Project ID
        dataset_id: Dataset ID
        table_id: Table ID
        
    Returns:
        Markdown string
    """
    return f"""# {table_id}

## Overview

**Project**: `{project_id}`  
**Dataset**: `{dataset_id}`  
**Table**: `{table_id}`  
**Type**: TABLE  
**Description**: Sample test table for unit testing purposes

## Schema

| Column Name | Type | Mode | Description |
|------------|------|------|-------------|
| id | STRING | REQUIRED | Unique identifier for the record |
| name | STRING | NULLABLE | Name of the entity |
| created_at | TIMESTAMP | NULLABLE | Timestamp when the record was created |

## Statistics

- **Row Count**: 1,000
- **Size**: 48.8 KB
- **Created**: 2024-01-01
- **Last Modified**: 2024-10-20

## Data Quality

No data quality issues detected.
"""


def create_sample_lineage_event(
    source_fqn: str = "bigquery:test-project.source_dataset.source_table",
    target_fqn: str = "bigquery:test-project.target_dataset.target_table",
) -> Dict[str, Any]:
    """
    Create a sample lineage event.
    
    Args:
        source_fqn: Source fully qualified name
        target_fqn: Target fully qualified name
        
    Returns:
        Dictionary representing a lineage event
    """
    return {
        "name": "projects/test-project/locations/us-central1/processes/test-dag/runs/test-run/lineageEvents/test-event",
        "links": [
            {
                "source": {"fully_qualified_name": source_fqn},
                "target": {"fully_qualified_name": target_fqn},
            }
        ],
        "start_time": "2024-10-20T10:00:00Z",
        "end_time": "2024-10-20T10:05:00Z",
    }

