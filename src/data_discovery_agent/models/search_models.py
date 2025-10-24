"""
Data Models for Search Requests and Responses
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SortOrder(str, Enum):
    """Sort order for results"""
    ASC = "asc"
    DESC = "desc"


class SearchRequest(BaseModel):
    """
    Search request model for Vertex AI Search queries.
    
    This is the high-level interface for searching metadata.
    """
    
    # Core query
    query: str = Field(..., description="Natural language search query")
    
    # Filtering
    project_id: Optional[str] = Field(None, description="Filter by project")
    dataset_id: Optional[str] = Field(None, description="Filter by dataset")
    has_pii: Optional[bool] = Field(None, description="Filter by PII presence")
    has_phi: Optional[bool] = Field(None, description="Filter by PHI presence")
    environment: Optional[str] = Field(None, description="Filter by environment (prod/staging/dev)")
    min_row_count: Optional[int] = Field(None, description="Minimum row count")
    max_row_count: Optional[int] = Field(None, description="Maximum row count")
    min_cost: Optional[float] = Field(None, description="Minimum monthly cost")
    max_cost: Optional[float] = Field(None, description="Maximum cost")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    
    # Sorting
    sort_by: Optional[str] = Field(None, description="Field to sort by")
    sort_order: SortOrder = Field(SortOrder.DESC, description="Sort order")
    
    # Pagination
    page_size: int = Field(10, description="Number of results per page", ge=1, le=100)
    page_token: Optional[str] = Field(None, description="Token for next page")
    
    # Advanced options
    include_full_content: bool = Field(False, description="Include full content in results")
    enable_suggestions: bool = Field(True, description="Generate query suggestions")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "customer tables with PII",
                "project_id": "my-project",
                "has_pii": True,
                "page_size": 20,
                "sort_by": "monthly_cost_usd",
                "sort_order": "desc"
            }
        }


class AssetMetadata(BaseModel):
    """
    Metadata for a discovered asset.
    
    BREAKING CHANGES in v2.0:
    - Renamed: created_at → created
    - Renamed: last_modified remains but was last_modified_timestamp
    - Renamed: last_accessed remains but was last_accessed_timestamp
    - Added: description, schema, column_profiles, lineage, analytical_insights, key_metrics
    - Added: insert_timestamp
    """
    
    model_config = ConfigDict(protected_namespaces=())
    
    # Identity
    id: str
    project_id: str
    dataset_id: Optional[str] = None
    table_id: Optional[str] = None
    asset_type: str  # "TABLE" or "VIEW" (mapped from table_type)
    
    # Description
    description: Optional[str] = Field(None, description="Table/view description")
    
    # Size and scale
    row_count: Optional[int] = None
    size_bytes: Optional[int] = None
    column_count: Optional[int] = None
    
    # Security
    has_pii: bool = False
    has_phi: bool = False
    encryption_type: Optional[str] = None
    
    # Cost
    monthly_cost_usd: Optional[float] = None
    
    # Timestamps (renamed to match BigQuery view schema)
    created: Optional[str] = Field(None, description="Creation timestamp")
    last_modified: Optional[str] = Field(None, description="Last modification timestamp")
    last_accessed: Optional[str] = Field(None, description="Last access timestamp")
    insert_timestamp: Optional[str] = Field(None, description="When record was inserted into discovery system")
    indexed_at: str = Field("", description="When indexed in Vertex AI Search")
    
    # Quality
    completeness_score: Optional[float] = None
    freshness_score: Optional[float] = None
    
    # Governance
    owner_email: Optional[str] = None
    team: Optional[str] = None
    environment: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    
    # Rich metadata from discovered_assets_latest view
    schema: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Column definitions with name, type, description, sample_values"
    )
    column_profiles: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Column statistics: distinct_count, null_percentage, min/max, avg"
    )
    lineage: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Data lineage with source and target relationships"
    )
    analytical_insights: List[str] = Field(
        default_factory=list,
        description="AI-generated analytical questions about the data"
    )
    key_metrics: List[Any] = Field(
        default_factory=list,
        description="Important business metrics"
    )


class SearchResultItem(BaseModel):
    """Single search result item"""
    
    # Identity
    id: str
    title: str
    
    # Match info
    score: float = Field(..., description="Relevance score 0-1")
    
    # Metadata
    metadata: AssetMetadata
    
    # Content
    snippet: str = Field(..., description="Relevant content excerpt")
    full_content: Optional[str] = Field(None, description="Full searchable content")
    
    # Links
    console_link: Optional[str] = Field(None, description="Link to GCP console")
    report_link: Optional[str] = Field(None, description="Link to full report")
    
    # Highlighting (which parts matched the query)
    highlighted_fields: List[str] = Field(default_factory=list, description="Fields that matched query")


class SearchResponse(BaseModel):
    """
    Search response model.
    
    Contains results, metadata, and suggestions.
    """
    
    # Query info
    query: str
    filters_applied: Dict[str, Any] = Field(default_factory=dict)
    
    # Results
    results: List[SearchResultItem] = Field(default_factory=list)
    total_count: int = Field(0, description="Total matching documents")
    
    # Performance
    query_time_ms: float
    
    # Pagination
    page_size: int
    next_page_token: Optional[str] = None
    has_more_results: bool = False
    
    # Aggregations (facets)
    facets: Dict[str, List[Dict[str, Any]]] = Field(
        default_factory=dict,
        description="Aggregated counts by field"
    )
    
    # Suggestions
    suggested_queries: List[str] = Field(default_factory=list)
    did_you_mean: Optional[str] = Field(None, description="Query correction suggestion")
    
    # Cache info
    from_cache: bool = Field(False, description="Whether results came from cache")
    cache_age_seconds: Optional[int] = Field(None, description="Age of cached results")
    
    def get_summary(self) -> str:
        """Get human-readable summary"""
        if not self.results:
            return f"No results found for '{self.query}'"
        
        summary = f"Found {self.total_count} result(s) in {self.query_time_ms:.0f}ms"
        
        if self.from_cache:
            summary += f" (cached {self.cache_age_seconds}s ago)"
        
        return summary


class AggregationRequest(BaseModel):
    """
    Request for aggregated statistics.
    
    Example: "Show me top datasets by table count"
    """
    
    query: str = Field(..., description="Base query for filtering")
    group_by: str = Field(..., description="Field to group by (e.g., dataset_id, team)")
    aggregate_function: str = Field("count", description="Aggregation function (count, sum, avg)")
    aggregate_field: Optional[str] = Field(None, description="Field to aggregate (for sum/avg)")
    top_k: int = Field(10, description="Number of top results", ge=1, le=100)
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "PII tables",
                "group_by": "dataset_id",
                "aggregate_function": "count",
                "top_k": 10
            }
        }


class AggregationResponse(BaseModel):
    """Response for aggregation queries"""
    
    query: str
    group_by: str
    results: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Aggregation results [{value, count/sum/avg}]"
    )
    total_groups: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "PII tables",
                "group_by": "dataset_id",
                "results": [
                    {"value": "finance", "count": 25},
                    {"value": "marketing", "count": 12},
                ],
                "total_groups": 5
            }
        }

