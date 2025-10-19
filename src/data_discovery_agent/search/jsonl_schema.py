"""
JSONL Schema Definitions for Vertex AI Search

Defines the structure of documents indexed in Vertex AI Search.
Separates filterable structured data from semantically searchable content.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


class DataSource(str, Enum):
    """Supported data sources"""
    BIGQUERY = "bigquery"
    GCS = "gcs"
    CLOUD_SQL = "cloudsql"
    DATAPLEX = "dataplex"


class AssetType(str, Enum):
    """Types of assets"""
    TABLE = "TABLE"
    VIEW = "VIEW"
    MATERIALIZED_VIEW = "MATERIALIZED_VIEW"
    DATASET = "DATASET"
    BUCKET = "BUCKET"
    FOLDER = "FOLDER"


class Volatility(str, Enum):
    """Data volatility classification"""
    LOW = "low"        # Changes rarely (metadata, schemas)
    MEDIUM = "medium"  # Changes occasionally (row counts, sizes)
    HIGH = "high"      # Changes frequently (permissions, active jobs)


class StructData(BaseModel):
    """
    Filterable structured fields for Vertex AI Search.
    
    These fields support exact matching and filtering:
    - filter='project_id="my-project"'
    - filter='has_pii=true AND row_count > 1000000'
    """
    
    # Identity
    project_id: str = Field(..., description="GCP project ID")
    dataset_id: Optional[str] = Field(None, description="Dataset ID (for BigQuery)")
    table_id: Optional[str] = Field(None, description="Table/asset ID")
    
    # Classification
    data_source: DataSource = Field(..., description="Source system")
    asset_type: AssetType = Field(..., description="Type of asset")
    
    # Security & Compliance
    has_pii: bool = Field(False, description="Contains PII data")
    has_phi: bool = Field(False, description="Contains PHI data")
    encryption_type: Optional[str] = Field(None, description="Encryption type")
    
    # Size & Scale
    row_count: Optional[int] = Field(None, description="Number of rows")
    size_bytes: Optional[int] = Field(None, description="Size in bytes")
    column_count: Optional[int] = Field(None, description="Number of columns")
    
    # Timestamps (ISO 8601 format for filtering)
    created_timestamp: Optional[str] = Field(None, description="Creation timestamp")
    last_modified_timestamp: Optional[str] = Field(None, description="Last modification")
    last_accessed_timestamp: Optional[str] = Field(None, description="Last access")
    indexed_at: str = Field(..., description="When this was indexed")
    
    # Cost
    monthly_cost_usd: Optional[float] = Field(None, description="Estimated monthly cost")
    storage_cost_usd: Optional[float] = Field(None, description="Storage cost")
    query_cost_usd: Optional[float] = Field(None, description="Query cost")
    
    # Governance
    owner_email: Optional[str] = Field(None, description="Owner email")
    team: Optional[str] = Field(None, description="Owning team")
    environment: Optional[str] = Field(None, description="Environment (dev/staging/prod)")
    
    # Cache metadata
    cache_ttl: str = Field("24h", description="Cache TTL (e.g., '24h', '1w')")
    volatility: Volatility = Field(Volatility.LOW, description="Data volatility")
    
    # Quality metrics
    completeness_score: Optional[float] = Field(None, description="Data completeness 0-1")
    freshness_score: Optional[float] = Field(None, description="Data freshness 0-1")
    
    # Tags (for filtering)
    tags: list[str] = Field(default_factory=list, description="Asset tags")
    
    # Detailed metadata for rich reporting (not for filtering)
    schema_info: Optional[Dict[str, Any]] = Field(None, description="Detailed schema information")
    quality_stats: Optional[Dict[str, Any]] = Field(None, description="Data quality statistics")
    column_profiles: Optional[Dict[str, Any]] = Field(None, description="Column-level data profiles")
    lineage: Optional[Dict[str, Any]] = Field(None, description="Data lineage information")
    
    @field_validator('indexed_at', 'created_timestamp', 'last_modified_timestamp', 'last_accessed_timestamp')
    @classmethod
    def validate_iso8601(cls, v: Optional[str]) -> Optional[str]:
        """Validate ISO 8601 timestamp format"""
        if v is None:
            return v
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except ValueError:
            raise ValueError(f"Invalid ISO 8601 timestamp: {v}")
    
    class Config:
        use_enum_values = True


class ContentData(BaseModel):
    """
    Semantically searchable content for Vertex AI Search.
    
    This is the rich text description that supports natural language queries.
    Should include all relevant context for semantic understanding.
    """
    
    mime_type: str = Field("text/plain", description="Content MIME type")
    text: str = Field(..., description="Rich searchable text content")
    
    @field_validator('text')
    @classmethod
    def validate_text_length(cls, v: str) -> str:
        """Ensure text is not empty and not too long"""
        if not v or len(v.strip()) == 0:
            raise ValueError("Content text cannot be empty")
        if len(v) > 100000:  # 100KB limit
            raise ValueError("Content text exceeds 100KB limit")
        return v


class BigQueryAssetSchema(BaseModel):
    """
    Complete schema for a BigQuery asset in Vertex AI Search.
    
    This represents a single document that will be indexed.
    """
    
    # Unique identifier (must be unique across all documents)
    id: str = Field(..., description="Unique document ID (e.g., project.dataset.table)")
    
    # Structured filterable data
    struct_data: StructData = Field(..., alias="structData")
    
    # Semantically searchable content
    content: ContentData = Field(...)
    
    class Config:
        populate_by_name = True  # Allow both struct_data and structData


class JSONLDocument(BaseModel):
    """
    JSONL document format for Vertex AI Search ingestion.
    
    This is the exact format expected by Vertex AI Search import API.
    Each line in the JSONL file should be one instance of this model.
    """
    
    id: str
    structData: Dict[str, Any]
    content: Dict[str, str]
    
    @classmethod
    def from_bigquery_asset(cls, asset: BigQueryAssetSchema) -> "JSONLDocument":
        """Convert BigQueryAssetSchema to JSONL format"""
        return cls(
            id=asset.id,
            structData=asset.struct_data.model_dump(by_alias=True, exclude_none=True),
            content=asset.content.model_dump()
        )
    
    def to_jsonl_line(self) -> str:
        """Convert to a single JSONL line (no newline at end)"""
        import json
        return json.dumps(self.model_dump(), ensure_ascii=False)


# Example usage and template
EXAMPLE_BIGQUERY_TABLE = BigQueryAssetSchema(
    id="my-project.finance.transactions",
    structData=StructData(
        project_id="my-project",
        dataset_id="finance",
        table_id="transactions",
        data_source=DataSource.BIGQUERY,
        asset_type=AssetType.TABLE,
        has_pii=True,
        row_count=5000000,
        size_bytes=2500000000,
        column_count=25,
        created_timestamp="2023-01-15T10:00:00Z",
        last_modified_timestamp="2024-01-15T14:30:00Z",
        indexed_at=datetime.utcnow().isoformat() + "Z",
        monthly_cost_usd=125.50,
        owner_email="finance-team@company.com",
        team="finance",
        environment="prod",
        volatility=Volatility.LOW,
        tags=["pii", "financial", "transactions"]
    ),
    content=ContentData(
        text="""
        # transactions Table
        
        **Dataset**: finance
        **Owner**: finance-team@company.com
        **Environment**: Production
        
        ## Description
        Central transactions table containing all customer purchase records.
        Updated nightly via ETL pipeline. Contains PII (customer_email, phone).
        
        ## Schema
        - transaction_id (STRING): Unique transaction identifier
        - customer_id (STRING): Customer reference
        - customer_email (STRING): Customer email [PII]
        - amount (NUMERIC): Transaction amount in USD
        - transaction_date (DATE): Date of transaction
        - product_id (STRING): Product reference
        - status (STRING): Transaction status (completed, pending, cancelled)
        
        ## Usage
        Primary table for financial reporting and customer analytics.
        Used by: revenue_dashboard, customer_lifetime_value, churn_analysis
        
        ## Lineage
        Source: Stripe API -> Cloud Function -> BigQuery
        Downstream: revenue_summary (view), monthly_revenue (materialized view)
        
        ## Governance
        - PII classification: Yes (customer_email, phone)
        - Retention: 7 years (regulatory requirement)
        - Access: Finance team, Data analysts (read-only)
        
        ## Cost
        - Monthly storage cost: $50
        - Monthly query cost: $75.50
        - Total: $125.50/month
        
        ## Quality Metrics
        - Completeness: 99.8%
        - Freshness: Daily updates
        - Last quality check: 2024-01-15
        """
    )
)

