"""
MCP Service Configuration

Configuration management for the MCP service using environment variables.
"""

import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()


class MCPConfig(BaseModel):
    """
    Configuration for MCP service.
    
    All configuration loaded from environment variables.
    Follows security best practices - no hardcoded credentials.
    """
    
    # GCP Configuration
    project_id: str = Field(
        default_factory=lambda: os.getenv("GCP_PROJECT_ID", ""),
        description="Google Cloud Project ID"
    )
    
    # Vertex AI Search Configuration
    vertex_location: str = Field(
        default_factory=lambda: os.getenv("VERTEX_LOCATION", "global"),
        description="Vertex AI Search location (typically 'global')"
    )
    
    vertex_datastore_id: str = Field(
        default_factory=lambda: os.getenv("VERTEX_DATASTORE_ID", "data-discovery-metadata"),
        description="Vertex AI Search datastore ID"
    )
    
    # GCS Configuration
    reports_bucket: str = Field(
        default_factory=lambda: os.getenv("GCS_REPORTS_BUCKET", ""),
        description="GCS bucket containing Markdown reports"
    )
    
    # MCP Service Configuration
    mcp_server_name: str = Field(
        default_factory=lambda: os.getenv("MCP_SERVER_NAME", "data-discovery-agent"),
        description="MCP server name"
    )
    
    mcp_server_version: str = Field(
        default_factory=lambda: os.getenv("MCP_SERVER_VERSION", "1.0.0"),
        description="MCP server version"
    )
    
    mcp_port: int = Field(
        default_factory=lambda: int(os.getenv("MCP_PORT", "8080")),
        description="Port for MCP HTTP service"
    )
    
    mcp_transport: str = Field(
        default_factory=lambda: os.getenv("MCP_TRANSPORT", "stdio"),
        description="MCP transport mode: 'stdio' for local/subprocess or 'http' for network/container"
    )
    
    mcp_host: str = Field(
        default_factory=lambda: os.getenv("MCP_HOST", "0.0.0.0"),
        description="Host address for HTTP server (use 0.0.0.0 in containers)"
    )
    
    # Query Configuration
    default_page_size: int = Field(
        default_factory=lambda: int(os.getenv("MCP_DEFAULT_PAGE_SIZE", "10")),
        description="Default number of results per page"
    )
    
    max_page_size: int = Field(
        default_factory=lambda: int(os.getenv("MCP_MAX_PAGE_SIZE", "50")),
        description="Maximum number of results per page"
    )
    
    query_timeout: float = Field(
        default_factory=lambda: float(os.getenv("MCP_QUERY_TIMEOUT", "30.0")),
        description="Query timeout in seconds"
    )
    
    # Feature Flags
    include_full_markdown: bool = Field(
        default_factory=lambda: os.getenv("MCP_INCLUDE_FULL_MARKDOWN", "true").lower() == "true",
        description="Whether to include full markdown content in responses"
    )
    
    enable_console_links: bool = Field(
        default_factory=lambda: os.getenv("MCP_ENABLE_CONSOLE_LINKS", "true").lower() == "true",
        description="Whether to include BigQuery console links"
    )
    
    # Logging Configuration
    log_level: str = Field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"),
        description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )
    
    # Gemini Configuration for PRP Discovery
    gemini_api_key: str = Field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", ""),
        description="Gemini API key for PRP analysis and dataset evaluation"
    )
    
    prp_max_queries: int = Field(
        default_factory=lambda: int(os.getenv("PRP_MAX_QUERIES", "10")),
        description="Maximum number of search queries to generate from PRP"
    )
    
    prp_min_relevance_score: float = Field(
        default_factory=lambda: float(os.getenv("PRP_MIN_RELEVANCE_SCORE", "60.0")),
        description="Minimum relevance score for dataset inclusion (0-100)"
    )
    
    # Discovery Configuration
    discovery_region: str = Field(
        default_factory=lambda: os.getenv("GCP_DISCOVERY_REGION", ""),
        description="Region filter for BigQuery dataset discovery (empty = all regions)"
    )
    
    def validate_required_fields(self) -> None:
        """
        Validate that required configuration fields are set.
        
        Raises:
            ValueError: If required fields are missing
        """
        required_fields = {
            "project_id": self.project_id,
            "reports_bucket": self.reports_bucket,
        }
        
        missing = [field for field, value in required_fields.items() if not value]
        
        if missing:
            raise ValueError(
                f"Required configuration missing: {', '.join(missing)}. "
                f"Please set the following environment variables: "
                f"{', '.join(f'{field.upper()}' for field in missing)}"
            )
    
    class Config:
        """Pydantic config."""
        
        arbitrary_types_allowed = True


def load_config() -> MCPConfig:
    """
    Load and validate MCP configuration from environment.
    
    Returns:
        MCPConfig instance
        
    Raises:
        ValueError: If required configuration is missing
    """
    config = MCPConfig()
    config.validate_required_fields()
    return config

