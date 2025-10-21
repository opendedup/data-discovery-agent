"""
Shared Asset Schema Definitions

Defines the canonical schema for discovered assets used across
the data discovery system (BigQuery writer, MCP tools, etc.).
"""

from typing import TypedDict, List, Optional, Any
from datetime import datetime


class LabelDict(TypedDict):
    """Key-value label pair."""
    key: str
    value: str


class SchemaFieldDict(TypedDict):
    """Schema field definition."""
    name: str
    type: str
    mode: Optional[str]
    description: Optional[str]
    sample_values: Optional[List[str]]


class LineageDict(TypedDict):
    """Lineage relationship."""
    source: str
    target: str


class ColumnProfileDict(TypedDict):
    """Column profile statistics."""
    column_name: str
    profile_type: Optional[str]
    min_value: Optional[str]
    max_value: Optional[str]
    avg_value: Optional[str]
    distinct_count: Optional[int]
    null_percentage: Optional[float]


class KeyMetricDict(TypedDict):
    """Key metric for an asset."""
    metric_name: str
    metric_value: str


class DiscoveredAssetDict(TypedDict, total=False):
    """
    Complete discovered asset schema.
    
    This matches the BigQuery writer schema and is the canonical format
    for asset metadata across the data discovery system.
    """
    # Core identifiers
    table_id: str
    project_id: str
    dataset_id: str
    
    # Metadata
    description: Optional[str]
    table_type: str  # TABLE, VIEW, MATERIALIZED_VIEW, etc.
    asset_type: Optional[str]  # Alias for table_type (for backwards compatibility)
    
    # Timestamps
    created: Optional[str]  # ISO format timestamp
    last_modified: Optional[str]
    last_accessed: Optional[str]
    
    # Statistics
    row_count: Optional[int]
    column_count: Optional[int]
    size_bytes: Optional[int]
    
    # Security & Governance
    has_pii: bool
    has_phi: bool
    environment: Optional[str]  # PROD, DEV, STAGING, etc.
    
    # Labels and tags
    labels: List[LabelDict]
    
    # Schema
    schema: List[SchemaFieldDict]
    
    # AI-generated insights
    analytical_insights: List[str]
    
    # Lineage
    lineage: List[LineageDict]
    
    # Profiling
    column_profiles: List[ColumnProfileDict]
    
    # Metrics
    key_metrics: List[KeyMetricDict]
    
    # Run metadata
    run_timestamp: str  # ISO format timestamp
    insert_timestamp: str  # ISO format timestamp or "AUTO"
    
    # Additional fields for MCP tools
    full_markdown: Optional[str]  # Complete markdown documentation
    owner_email: Optional[str]  # Asset owner
    tags: Optional[List[str]]  # Additional tags


def create_asset_dict(
    table_id: str,
    project_id: str,
    dataset_id: str,
    table_type: str = "TABLE",
    description: str = None,
    created: datetime = None,
    last_modified: datetime = None,
    last_accessed: datetime = None,
    row_count: int = None,
    column_count: int = None,
    size_bytes: int = None,
    has_pii: bool = False,
    has_phi: bool = False,
    environment: str = None,
    labels: List[LabelDict] = None,
    schema: List[SchemaFieldDict] = None,
    analytical_insights: List[str] = None,
    lineage: List[LineageDict] = None,
    column_profiles: List[ColumnProfileDict] = None,
    key_metrics: List[KeyMetricDict] = None,
    run_timestamp: datetime = None,
    full_markdown: str = None,
    owner_email: str = None,
    tags: List[str] = None,
) -> DiscoveredAssetDict:
    """
    Create a discovered asset dictionary with proper defaults.
    
    Args:
        table_id: Table identifier
        project_id: GCP project ID
        dataset_id: BigQuery dataset ID
        table_type: Type of table (TABLE, VIEW, etc.)
        description: Table description
        created: Creation timestamp
        last_modified: Last modified timestamp
        last_accessed: Last accessed timestamp
        row_count: Number of rows
        column_count: Number of columns
        size_bytes: Size in bytes
        has_pii: Contains PII data
        has_phi: Contains PHI data
        environment: Environment (PROD, DEV, etc.)
        labels: Key-value labels
        schema: Schema fields
        analytical_insights: AI-generated insights
        lineage: Lineage relationships
        column_profiles: Column statistics
        key_metrics: Key metrics
        run_timestamp: Run timestamp
        full_markdown: Complete markdown documentation
        owner_email: Asset owner email
        tags: Additional tags
        
    Returns:
        DiscoveredAssetDict with all fields
    """
    from datetime import timezone
    
    now = datetime.now(timezone.utc)
    run_ts = run_timestamp or now
    
    return DiscoveredAssetDict(
        table_id=table_id,
        project_id=project_id,
        dataset_id=dataset_id,
        table_type=table_type,
        asset_type=table_type,  # Same as table_type for backwards compatibility
        description=description,
        created=created.isoformat() if created else None,
        last_modified=last_modified.isoformat() if last_modified else None,
        last_accessed=last_accessed.isoformat() if last_accessed else None,
        row_count=row_count,
        column_count=column_count,
        size_bytes=size_bytes,
        has_pii=has_pii,
        has_phi=has_phi,
        environment=environment,
        labels=labels or [],
        schema=schema or [],
        analytical_insights=analytical_insights or [],
        lineage=lineage or [],
        column_profiles=column_profiles or [],
        key_metrics=key_metrics or [],
        run_timestamp=run_ts.isoformat(),
        insert_timestamp="AUTO",
        full_markdown=full_markdown,
        owner_email=owner_email,
        tags=tags or [],
    )

