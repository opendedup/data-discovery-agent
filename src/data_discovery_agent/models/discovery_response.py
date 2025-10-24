"""
Discovery Response Models
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AssetInfo(BaseModel):
    """Basic information about a data asset"""
    
    # Identity
    project_id: str
    dataset_id: str
    table_id: str
    full_path: str
    asset_type: str
    
    # Basic stats
    row_count: Optional[int] = None
    size_bytes: Optional[int] = None
    created: Optional[str] = None  # Renamed from created_at for consistency
    last_modified: Optional[str] = None
    
    # Classification
    has_pii: bool = False
    has_phi: bool = False
    
    # Cost
    monthly_cost_usd: Optional[float] = None
    
    # Owner
    owner_email: Optional[str] = None


class ColumnInfo(BaseModel):
    """Information about a table column"""
    
    name: str
    type: str
    mode: str = "NULLABLE"
    description: Optional[str] = None
    
    # Statistics (if profiled)
    null_count: Optional[int] = None
    null_percentage: Optional[float] = None
    distinct_count: Optional[int] = None
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    avg_value: Optional[float] = None
    
    # PII detection
    contains_pii: bool = False
    pii_type: Optional[str] = None


class InspectResponse(BaseModel):
    """Response for deep inspection"""
    
    # Basic info
    asset: AssetInfo
    
    # Schema
    table_schema: Optional[List[ColumnInfo]] = None
    
    # Sample data
    sample_rows: Optional[List[Dict[str, Any]]] = None
    
    # Statistics
    statistics: Optional[Dict[str, Any]] = None
    
    # Lineage
    upstream_tables: Optional[List[str]] = None
    downstream_tables: Optional[List[str]] = None
    
    # Access history
    recent_queries: Optional[List[Dict[str, Any]]] = None
    active_users: Optional[List[str]] = None
    
    # Cost breakdown
    cost_breakdown: Optional[Dict[str, float]] = None
    
    # DLP findings
    dlp_findings: Optional[List[Dict[str, Any]]] = None


class LineageNode(BaseModel):
    """Single node in lineage graph"""
    
    id: str
    label: str
    asset_type: str
    project_id: str
    dataset_id: str
    table_id: str


class LineageEdge(BaseModel):
    """Edge in lineage graph"""
    
    source: str
    target: str
    edge_type: str = "data_flow"  # data_flow, reference, etc.


class LineageResponse(BaseModel):
    """Response for lineage query"""
    
    # Target asset
    root_asset: AssetInfo
    
    # Graph structure
    nodes: List[LineageNode]
    edges: List[LineageEdge]
    
    # Statistics
    total_upstream: int
    total_downstream: int
    max_depth_reached: int


class ColumnProfile(BaseModel):
    """Detailed profile for a single column"""
    
    column_name: str
    data_type: str
    
    # Completeness
    total_rows: int
    null_count: int
    null_percentage: float
    
    # Cardinality
    distinct_count: int
    distinct_percentage: float
    
    # Distribution (for numeric)
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    mean: Optional[float] = None
    median: Optional[float] = None
    std_dev: Optional[float] = None
    
    # Top values (for all types)
    top_values: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="[{value, count, percentage}]"
    )
    
    # Patterns (for strings)
    common_patterns: Optional[List[str]] = None
    
    # Quality issues
    quality_issues: List[str] = Field(default_factory=list)


class ProfileResponse(BaseModel):
    """Response for data profiling"""
    
    # Target
    asset: AssetInfo
    
    # Column profiles
    column_profiles: List[ColumnProfile]
    
    # Overall statistics
    total_rows: int
    total_columns: int
    overall_completeness: float
    
    # Quality summary
    quality_score: float = Field(..., description="Overall quality score 0-1")
    quality_issues: List[str] = Field(default_factory=list)


class DiscoveryResponse(BaseModel):
    """
    Universal discovery response.
    
    Wraps all response types with metadata.
    """
    
    # Query info
    query_type: str
    query: str
    
    # Timing
    execution_time_ms: float
    from_cache: bool = False
    
    # Response data (one of these will be populated)
    search_results: Optional[Any] = None
    inspect_result: Optional[InspectResponse] = None
    lineage_result: Optional[LineageResponse] = None
    profile_result: Optional[ProfileResponse] = None
    aggregation_results: Optional[Any] = None
    
    # Metadata
    total_results: int = 0
    results_truncated: bool = False
    
    # Suggestions
    suggestions: List[str] = Field(default_factory=list)
    
    # Errors/warnings
    warnings: List[str] = Field(default_factory=list)
    
    def get_summary(self) -> str:
        """Get human-readable summary"""
        summary = f"Query: {self.query}\n"
        summary += f"Type: {self.query_type}\n"
        summary += f"Execution time: {self.execution_time_ms:.0f}ms\n"
        
        if self.from_cache:
            summary += "Source: Cache\n"
        else:
            summary += "Source: Live query\n"
        
        summary += f"Results: {self.total_results}\n"
        
        return summary

