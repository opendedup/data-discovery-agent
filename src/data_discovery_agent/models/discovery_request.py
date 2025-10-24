"""
Discovery Request Models
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict


class QueryType(str, Enum):
    """Type of discovery query"""
    
    # Metadata queries (cached)
    SEARCH = "search"  # Natural language search
    FILTER = "filter"  # Structured filtering
    AGGREGATE = "aggregate"  # Statistics and aggregations
    
    # Live queries (real-time)
    INSPECT = "inspect"  # Deep inspection of single asset
    LINEAGE = "lineage"  # Dependency graph
    PROFILE = "profile"  # Data profiling
    QUERY_ANALYSIS = "query_analysis"  # Query performance analysis
    COST_ANALYSIS = "cost_analysis"  # Cost breakdown
    
    # Hybrid queries
    RECOMMENDATIONS = "recommendations"  # ML-powered recommendations
    SIMILARITY = "similarity"  # Find similar assets


class DiscoveryRequest(BaseModel):
    """
    Universal discovery request model.
    
    Supports both cached (Vertex AI Search) and live (Agent) queries.
    """
    
    # Core request
    query_type: QueryType = Field(..., description="Type of query")
    query: str = Field(..., description="Natural language query")
    
    # Target scope
    project_id: Optional[str] = Field(None, description="Target project")
    dataset_id: Optional[str] = Field(None, description="Target dataset")
    table_id: Optional[str] = Field(None, description="Target table")
    
    # Filtering (for cached queries)
    filters: Dict[str, Any] = Field(default_factory=dict, description="Structured filters")
    
    # Options
    max_results: int = Field(10, description="Maximum results to return", ge=1, le=100)
    include_details: bool = Field(True, description="Include detailed metadata")
    force_live: bool = Field(False, description="Force live query (bypass cache)")
    
    # Context (for LLM-powered queries)
    conversation_context: Optional[List[Dict[str, str]]] = Field(
        None,
        description="Previous conversation for context"
    )
    
    # User identity (for audit trail)
    user_email: Optional[str] = Field(None, description="User making request")
    
    model_config = ConfigDict(
        json_schema_extra = {
            "example": {
                "query_type": "search",
                "query": "Find PII tables in finance dataset",
                "project_id": "my-project",
                "filters": {"has_pii": True, "dataset_id": "finance"},
                "max_results": 20
            }
        }
    )


class InspectRequest(BaseModel):
    """Request for deep inspection of a single asset"""
    
    # Target
    project_id: str
    dataset_id: str
    table_id: str
    
    # What to inspect
    include_schema: bool = True
    include_sample_data: bool = False
    include_statistics: bool = True
    include_lineage: bool = True
    include_access_history: bool = False
    include_cost_breakdown: bool = True
    include_dlp_scan: bool = False  # Expensive operation
    
    # Options
    sample_size: int = Field(100, description="Number of sample rows", ge=1, le=1000)


class LineageRequest(BaseModel):
    """Request for lineage information"""
    
    # Target
    project_id: str
    dataset_id: str
    table_id: str
    
    # Lineage options
    direction: str = Field("both", description="upstream, downstream, or both")
    max_depth: int = Field(3, description="Maximum depth to traverse", ge=1, le=10)
    include_views: bool = True
    include_scripts: bool = True
    
    # Output format
    format: str = Field("graph", description="graph or list")


class ProfileRequest(BaseModel):
    """Request for data profiling"""
    
    # Target
    project_id: str
    dataset_id: str
    table_id: str
    
    # Profiling options
    profile_all_columns: bool = False
    target_columns: Optional[List[str]] = Field(None, description="Specific columns to profile")
    
    # Analysis types
    include_nulls: bool = True
    include_cardinality: bool = True
    include_distribution: bool = True
    include_patterns: bool = False  # Regex patterns for strings
    
    # Sampling
    use_sampling: bool = True
    sample_percent: float = Field(10.0, description="Percentage to sample", ge=0.1, le=100)

