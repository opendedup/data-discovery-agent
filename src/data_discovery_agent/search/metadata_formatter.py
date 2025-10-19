"""
Metadata Formatter - CRITICAL COMPONENT

Transforms raw discovery agent outputs into optimized JSONL for Vertex AI Search.
This is the bridge between discovery agents and the search index.

Key responsibilities:
1. Aggregate metadata from multiple discovery agents
2. Generate rich, searchable content text
3. Create structured filterable fields
4. Handle incremental updates
5. Manage cache TTLs based on volatility
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from .jsonl_schema import (
    AssetType,
    BigQueryAssetSchema,
    ContentData,
    DataSource,
    JSONLDocument,
    StructData,
    Volatility,
)

logger = logging.getLogger(__name__)


class MetadataFormatter:
    """
    Formats discovery metadata into Vertex AI Search JSONL documents.
    
    Designed to be extensible for multiple data sources (BigQuery, GCS, etc.)
    """
    
    def __init__(self, project_id: str):
        self.project_id = project_id
    
    def format_bigquery_table(
        self,
        table_metadata: Dict[str, Any],
        schema_info: Optional[Dict[str, Any]] = None,
        lineage_info: Optional[Dict[str, Any]] = None,
        cost_info: Optional[Dict[str, Any]] = None,
        quality_info: Optional[Dict[str, Any]] = None,
        security_info: Optional[Dict[str, Any]] = None,
        governance_info: Optional[Dict[str, Any]] = None,
    ) -> BigQueryAssetSchema:
        """
        Format BigQuery table metadata into a searchable document.
        
        Args:
            table_metadata: Core table info (required)
            schema_info: Column schemas (optional)
            lineage_info: Upstream/downstream dependencies (optional)
            cost_info: Cost analysis (optional)
            quality_info: Data quality metrics (optional)
            security_info: IAM, RLS, CLS policies (optional)
            governance_info: Labels, tags, DLP findings (optional)
        
        Returns:
            BigQueryAssetSchema ready for JSONL export
        """
        
        # Extract core identifiers
        project_id = table_metadata.get("project_id", self.project_id)
        dataset_id = table_metadata["dataset_id"]
        table_id = table_metadata["table_id"]
        document_id = f"{project_id}.{dataset_id}.{table_id}"
        
        # Determine asset type
        table_type = table_metadata.get("table_type", "TABLE")
        asset_type = self._map_table_type(table_type)
        
        # Build structured data
        struct_data = self._build_struct_data(
            project_id=project_id,
            dataset_id=dataset_id,
            table_id=table_id,
            asset_type=asset_type,
            table_metadata=table_metadata,
            cost_info=cost_info,
            quality_info=quality_info,
            security_info=security_info,
            governance_info=governance_info,
        )
        
        # Build searchable content
        content_text = self._build_content_text(
            table_metadata=table_metadata,
            schema_info=schema_info,
            lineage_info=lineage_info,
            cost_info=cost_info,
            quality_info=quality_info,
            security_info=security_info,
            governance_info=governance_info,
        )
        
        content = ContentData(text=content_text)
        
        return BigQueryAssetSchema(
            id=document_id,
            structData=struct_data,
            content=content,
        )
    
    def _map_table_type(self, table_type: str) -> AssetType:
        """Map BigQuery table type to AssetType enum"""
        mapping = {
            "TABLE": AssetType.TABLE,
            "VIEW": AssetType.VIEW,
            "MATERIALIZED_VIEW": AssetType.MATERIALIZED_VIEW,
            "EXTERNAL": AssetType.TABLE,
        }
        return mapping.get(table_type, AssetType.TABLE)
    
    def _build_struct_data(
        self,
        project_id: str,
        dataset_id: str,
        table_id: str,
        asset_type: AssetType,
        table_metadata: Dict[str, Any],
        cost_info: Optional[Dict[str, Any]],
        quality_info: Optional[Dict[str, Any]],
        security_info: Optional[Dict[str, Any]],
        governance_info: Optional[Dict[str, Any]],
    ) -> StructData:
        """Build filterable structured data"""
        
        # Determine volatility based on asset type and metadata
        volatility = self._determine_volatility(table_metadata, asset_type)
        
        # Calculate cache TTL based on volatility
        cache_ttl = self._calculate_cache_ttl(volatility)
        
        # Extract security flags
        has_pii = False
        has_phi = False
        if security_info:
            has_pii = security_info.get("has_pii", False)
            has_phi = security_info.get("has_phi", False)
        if governance_info and governance_info.get("dlp_findings"):
            has_pii = has_pii or any(
                "PII" in finding for finding in governance_info["dlp_findings"]
            )
        
        # Extract cost data
        monthly_cost = None
        if cost_info:
            storage_cost = cost_info.get("storage_cost_usd", 0)
            query_cost = cost_info.get("query_cost_usd", 0)
            monthly_cost = storage_cost + query_cost
        
        # Extract quality scores
        completeness_score = None
        freshness_score = None
        if quality_info:
            completeness_score = quality_info.get("completeness_score")
            freshness_score = quality_info.get("freshness_score")
        
        # Extract governance info
        owner_email = governance_info.get("owner_email") if governance_info else None
        team = governance_info.get("team") if governance_info else None
        environment = governance_info.get("environment", "unknown") if governance_info else "unknown"
        tags = governance_info.get("tags", []) if governance_info else []
        
        # Build timestamps
        now = datetime.utcnow().isoformat() + "Z"
        created = self._format_timestamp(table_metadata.get("created_time"))
        modified = self._format_timestamp(table_metadata.get("modified_time"))
        accessed = self._format_timestamp(table_metadata.get("last_accessed_time"))
        
        return StructData(
            project_id=project_id,
            dataset_id=dataset_id,
            table_id=table_id,
            data_source=DataSource.BIGQUERY,
            asset_type=asset_type,
            has_pii=has_pii,
            has_phi=has_phi,
            encryption_type=table_metadata.get("encryption_type"),
            row_count=table_metadata.get("num_rows"),
            size_bytes=table_metadata.get("num_bytes"),
            column_count=len(table_metadata.get("schema", {}).get("fields", [])),
            created_timestamp=created,
            last_modified_timestamp=modified,
            last_accessed_timestamp=accessed,
            indexed_at=now,
            monthly_cost_usd=monthly_cost,
            owner_email=owner_email,
            team=team,
            environment=environment,
            cache_ttl=cache_ttl,
            volatility=volatility,
            completeness_score=completeness_score,
            freshness_score=freshness_score,
            tags=tags,
        )
    
    def _build_content_text(
        self,
        table_metadata: Dict[str, Any],
        schema_info: Optional[Dict[str, Any]],
        lineage_info: Optional[Dict[str, Any]],
        cost_info: Optional[Dict[str, Any]],
        quality_info: Optional[Dict[str, Any]],
        security_info: Optional[Dict[str, Any]],
        governance_info: Optional[Dict[str, Any]],
    ) -> str:
        """
        Build rich, searchable content text.
        
        This is the key to good semantic search results.
        Include all context that would help answer natural language queries.
        
        Enhanced to include:
        - Full schema (all columns, not truncated)
        - Data quality metrics (null statistics)
        - Column profiles (min/max/avg/distinct)
        - Complete lineage information
        """
        
        sections = []
        
        # Title and basic info
        table_name = f"{table_metadata['dataset_id']}.{table_metadata['table_id']}"
        sections.append(f"# {table_name}")
        sections.append("")
        sections.append(f"**Type**: {table_metadata.get('table_type', 'TABLE')}")
        sections.append(f"**Dataset**: {table_metadata['dataset_id']}")
        sections.append(f"**Project**: {table_metadata.get('project_id', self.project_id)}")
        
        # Statistics (moved up for better search context)
        sections.append("")
        sections.append("## Statistics")
        if num_rows := table_metadata.get("num_rows"):
            sections.append(f"- **Rows**: {num_rows:,}")
        if num_bytes := table_metadata.get("num_bytes"):
            size_gb = num_bytes / (1024**3)
            sections.append(f"- **Size**: {size_gb:.2f} GB")
        if table_metadata.get("column_count"):
            sections.append(f"- **Columns**: {table_metadata['column_count']}")
        if modified := table_metadata.get("modified_time"):
            sections.append(f"- **Last Modified**: {modified}")
        
        # Description
        if description := table_metadata.get("description"):
            sections.append("")
            sections.append("## Description")
            sections.append(description)
        
        # Schema - INCLUDE ALL COLUMNS (not truncated) with sample values
        if schema_info or table_metadata.get("schema"):
            sections.append("")
            sections.append("## Schema")
            schema = schema_info or table_metadata.get("schema", {})
            fields = schema.get("fields", [])
            
            # Get sample values if available
            sample_values = quality_info.get("sample_values", {}) if quality_info else {}
            
            # Include ALL fields for complete searchability
            for field in fields:
                field_name = field.get("name", "unknown")
                field_type = field.get("type", "unknown")
                field_desc = field.get("description", "")
                mode = field.get("mode", "NULLABLE")
                
                line = f"- **{field_name}** ({field_type}, {mode})"
                if field_desc:
                    line += f": {field_desc}"
                
                # Add sample values if available
                if field_name in sample_values and sample_values[field_name]:
                    samples = sample_values[field_name]
                    samples_str = ", ".join([f"'{s}'" for s in samples])
                    line += f" — Examples: {samples_str}"
                
                sections.append(line)
        
        # Data Quality - Enhanced with null statistics and column profiles
        if quality_info:
            sections.append("")
            sections.append("## Data Quality")
            
            # Null statistics
            if columns_stats := quality_info.get("columns"):
                sections.append("")
                sections.append("### Null Statistics (Top 10 columns by null %)")
                # Sort by null percentage, show top 10
                sorted_cols = sorted(
                    columns_stats.items(),
                    key=lambda x: x[1].get("null_percentage", 0),
                    reverse=True
                )[:10]
                
                for col_name, stats in sorted_cols:
                    null_pct = stats.get("null_percentage", 0)
                    if null_pct > 0:  # Only show columns with nulls
                        sections.append(f"- **{col_name}**: {null_pct:.1f}% null")
            
            # Column profiles
            if column_profiles := quality_info.get("column_profiles"):
                sections.append("")
                sections.append("### Column Profiles")
                
                # Numeric columns
                numeric_cols = {k: v for k, v in column_profiles.items() if v.get("type") == "numeric"}
                if numeric_cols:
                    sections.append("")
                    sections.append("**Numeric Columns:**")
                    for col_name, profile in list(numeric_cols.items())[:10]:  # Top 10
                        min_val = profile.get("min")
                        max_val = profile.get("max")
                        avg_val = profile.get("avg")
                        distinct = profile.get("distinct_count", 0)
                        
                        # Format avg value properly
                        if isinstance(avg_val, (int, float)):
                            avg_str = f"{avg_val:.2f}"
                        else:
                            avg_str = str(avg_val) if avg_val is not None else "N/A"
                        
                        sections.append(
                            f"- **{col_name}**: min={min_val}, max={max_val}, "
                            f"avg={avg_str}, distinct={distinct:,}"
                        )
                
                # String columns
                string_cols = {k: v for k, v in column_profiles.items() if v.get("type") == "string"}
                if string_cols:
                    sections.append("")
                    sections.append("**String Columns:**")
                    for col_name, profile in list(string_cols.items())[:10]:  # Top 10
                        min_len = profile.get("min_length")
                        max_len = profile.get("max_length")
                        distinct = profile.get("distinct_count", 0)
                        sections.append(
                            f"- **{col_name}**: length={min_len}-{max_len}, distinct={distinct:,}"
                        )
            
            # Legacy quality info
            if freshness := quality_info.get("freshness"):
                sections.append(f"- **Freshness**: {freshness}")
            
            if completeness := quality_info.get("completeness_score"):
                sections.append(f"- **Completeness**: {completeness*100:.1f}%")
            
            if issues := quality_info.get("quality_issues"):
                sections.append(f"- **Issues**: {len(issues)} quality issues found")
        
        # Usage and lineage - Enhanced to show all dependencies
        if lineage_info:
            sections.append("")
            sections.append("## Lineage")
            
            if upstream := lineage_info.get("upstream_tables"):
                sections.append("")
                sections.append("**Upstream Sources:**")
                for table in upstream:  # Show all, not truncated
                    sections.append(f"- {table}")
            
            if downstream := lineage_info.get("downstream_tables"):
                sections.append("")
                sections.append("**Downstream Consumers:**")
                for table in downstream:  # Show all, not truncated
                    sections.append(f"- {table}")
        
        # Security and governance
        if security_info or governance_info:
            sections.append("")
            sections.append("## Governance")
            
            if security_info:
                if security_info.get("has_pii"):
                    sections.append("- **Classification**: Contains PII data")
                if security_info.get("has_phi"):
                    sections.append("- **Classification**: Contains PHI data")
                if iam := security_info.get("iam_summary"):
                    sections.append(f"- **Access**: {iam}")
            
            if governance_info:
                if owner := governance_info.get("owner_email"):
                    sections.append(f"- **Owner**: {owner}")
                if team := governance_info.get("team"):
                    sections.append(f"- **Team**: {team}")
                if labels := governance_info.get("labels"):
                    label_str = ", ".join(f"{k}={v}" for k, v in labels.items())
                    sections.append(f"- **Labels**: {label_str}")
        
        # Cost information
        if cost_info:
            sections.append("")
            sections.append("## Cost")
            
            if storage_cost := cost_info.get("storage_cost_usd"):
                sections.append(f"- **Storage**: ${storage_cost:.2f}/month")
            
            if query_cost := cost_info.get("query_cost_usd"):
                sections.append(f"- **Queries**: ${query_cost:.2f}/month")
            
            if total_cost := cost_info.get("total_monthly_cost_usd"):
                sections.append(f"- **Total**: ${total_cost:.2f}/month")
        
        # Analytical Insights
        if quality_info and quality_info.get("insights"):
            sections.append("")
            sections.append("## Analytical Insights")
            sections.append("")
            sections.append("Questions that could be answered using this table:")
            for i, insight in enumerate(quality_info["insights"], 1):
                sections.append(f"{i}. {insight}")
        
        return "\n".join(sections)
    
    def _determine_volatility(
        self, table_metadata: Dict[str, Any], asset_type: AssetType
    ) -> Volatility:
        """Determine data volatility for cache TTL calculation"""
        
        # Views are generally low volatility (definition doesn't change often)
        if asset_type in [AssetType.VIEW, AssetType.MATERIALIZED_VIEW]:
            return Volatility.LOW
        
        # Check if table is partitioned (often indicates high-volume data)
        if table_metadata.get("time_partitioning"):
            return Volatility.MEDIUM
        
        # Check modification frequency (if available)
        # This would come from historical analysis
        if update_freq := table_metadata.get("update_frequency_hours"):
            if update_freq < 1:
                return Volatility.HIGH
            elif update_freq < 24:
                return Volatility.MEDIUM
        
        # Default to low volatility (metadata changes rarely)
        return Volatility.LOW
    
    def _calculate_cache_ttl(self, volatility: Volatility) -> str:
        """Calculate cache TTL based on volatility"""
        ttl_map = {
            Volatility.LOW: "7d",      # 7 days
            Volatility.MEDIUM: "24h",  # 1 day
            Volatility.HIGH: "1h",     # 1 hour
        }
        return ttl_map[volatility]
    
    def _format_timestamp(self, ts: Any) -> Optional[str]:
        """Format timestamp to ISO 8601"""
        if ts is None:
            return None
        
        if isinstance(ts, datetime):
            # Use Z suffix for UTC times
            if ts.tzinfo is None:
                return ts.isoformat() + "Z"
            return ts.isoformat()
        
        if isinstance(ts, (int, float)):
            # Assume Unix timestamp
            return datetime.utcfromtimestamp(ts).isoformat() + "Z"
        
        if isinstance(ts, str):
            # If already ends with Z, return as is
            if ts.endswith('Z'):
                return ts
            # Try to parse and reformat
            try:
                dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                # Return with appropriate suffix
                if dt.tzinfo is None:
                    return dt.isoformat() + "Z"
                return dt.isoformat()
            except ValueError:
                return ts
        
        return None
    
    def export_to_jsonl(
        self,
        documents: List[BigQueryAssetSchema],
        output_path: Path,
    ) -> int:
        """
        Export documents to JSONL file for Vertex AI Search ingestion.
        
        Args:
            documents: List of BigQueryAssetSchema documents
            output_path: Path to output JSONL file
        
        Returns:
            Number of documents exported
        """
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for doc in documents:
                jsonl_doc = JSONLDocument.from_bigquery_asset(doc)
                f.write(jsonl_doc.to_jsonl_line() + "\n")
        
        logger.info(f"Exported {len(documents)} documents to {output_path}")
        return len(documents)
    
    def export_batch_to_gcs(
        self,
        documents: List[BigQueryAssetSchema],
        gcs_bucket: str,
        gcs_path: str = "metadata",
        batch_id: Optional[str] = None,
    ) -> str:
        """
        Export documents directly to GCS for Vertex AI Search ingestion.
        
        Args:
            documents: List of documents
            gcs_bucket: GCS bucket name
            gcs_path: Path within bucket
            batch_id: Optional batch identifier
        
        Returns:
            GCS URI of exported file
        """
        from google.cloud import storage
        
        if batch_id is None:
            batch_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        filename = f"{gcs_path}/bigquery_metadata_{batch_id}.jsonl"
        
        # Create JSONL content
        lines = []
        for doc in documents:
            jsonl_doc = JSONLDocument.from_bigquery_asset(doc)
            lines.append(jsonl_doc.to_jsonl_line())
        
        content = "\n".join(lines)
        
        # Upload to GCS
        storage_client = storage.Client()
        bucket = storage_client.bucket(gcs_bucket)
        blob = bucket.blob(filename)
        blob.upload_from_string(content, content_type="application/jsonl")
        
        gcs_uri = f"gs://{gcs_bucket}/{filename}"
        logger.info(f"Exported {len(documents)} documents to {gcs_uri}")
        
        return gcs_uri

