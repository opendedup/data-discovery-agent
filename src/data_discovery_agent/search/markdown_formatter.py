"""
Markdown Formatter for Human-Readable Reports

Generates beautiful, readable discovery reports from metadata.
These reports are stored in GCS and can be viewed directly by users.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .jsonl_schema import AssetType, BigQueryAssetSchema

logger = logging.getLogger(__name__)


class MarkdownFormatter:
    """
    Generates Markdown reports from discovery metadata.
    
    Reports are designed to be:
    - Human-readable and visually appealing
    - Comprehensive with all relevant details
    - Easy to navigate with clear sections
    - Suitable for sharing and documentation
    """
    
    def __init__(self, project_id: str):
        self.project_id = project_id
    
    def generate_table_report(
        self,
        asset: BigQueryAssetSchema,
        extended_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate comprehensive Markdown report for a BigQuery table.
        
        Args:
            asset: BigQueryAssetSchema document
            extended_metadata: Additional metadata not in asset schema
        
        Returns:
            Markdown formatted report
        """
        
        sections = []
        
        # Title and metadata badge
        sections.append(self._generate_header(asset))
        sections.append("")
        
        # Executive summary
        sections.append(self._generate_summary(asset))
        sections.append("")
        
        # Key metrics
        sections.append(self._generate_metrics_table(asset))
        sections.append("")
        
        # Description
        sections.append("## Description")
        sections.append("")
        if extended_metadata and extended_metadata.get("description"):
            sections.append(extended_metadata["description"])
        elif asset.content and asset.content.text:
            # Fallback to extracting from content
            description = self._extract_description_from_content(asset.content.text)
            sections.append(description)
        else:
            sections.append("*No description available for this table.*")
        sections.append("")
        
        # Schema
        sections.append(self._generate_schema_section(asset, extended_metadata))
        sections.append("")
        
        # Security & Governance
        sections.append(self._generate_governance_section(asset))
        sections.append("")
        
        # Cost Analysis
        if asset.struct_data.monthly_cost_usd:
            sections.append(self._generate_cost_section(asset))
            sections.append("")
        
        # Data Quality
        if asset.struct_data.completeness_score or asset.struct_data.freshness_score or (extended_metadata and extended_metadata.get("quality_stats")):
            sections.append(self._generate_quality_section(asset, extended_metadata))
            sections.append("")
        
        # Column Profiling
        if extended_metadata and extended_metadata.get("column_profiles"):
            sections.append(self._generate_column_profiles_section(extended_metadata["column_profiles"]))
            sections.append("")
        
        # Lineage (if available in extended metadata)
        if extended_metadata and "lineage" in extended_metadata:
            sections.append(self._generate_lineage_section(extended_metadata["lineage"]))
            sections.append("")
        
        # Usage patterns (if available)
        if extended_metadata and "usage" in extended_metadata:
            sections.append(self._generate_usage_section(extended_metadata["usage"]))
            sections.append("")
        
        # Footer
        sections.append(self._generate_footer(asset))
        
        return "\n".join(sections)
    
    def _generate_header(self, asset: BigQueryAssetSchema) -> str:
        """Generate report header with title and badges"""
        
        table_name = f"{asset.struct_data.dataset_id}.{asset.struct_data.table_id}"
        
        badges = []
        
        # Asset type badge (ASCII-only)
        badges.append(f"[{asset.struct_data.asset_type.upper()}]")
        
        # Security badges
        if asset.struct_data.has_pii:
            badges.append("[PII]")
        if asset.struct_data.has_phi:
            badges.append("[PHI]")
        
        # Environment badge
        env = asset.struct_data.environment or "unknown"
        badges.append(f"[{env.upper()}]")
        
        badge_line = " | ".join(badges)
        
        return f"# {table_name}\n\n{badge_line}"
    
    def _generate_summary(self, asset: BigQueryAssetSchema) -> str:
        """Generate executive summary"""
        
        lines = []
        lines.append("## Executive Summary")
        lines.append("")
        
        # Quick facts
        facts = []
        
        if asset.struct_data.row_count:
            facts.append(f"**{asset.struct_data.row_count:,}** rows")
        
        if asset.struct_data.size_bytes:
            facts.append(f"**{self._format_size(asset.struct_data.size_bytes)}**")
        
        if asset.struct_data.column_count:
            facts.append(f"**{asset.struct_data.column_count}** columns")
        
        if asset.struct_data.monthly_cost_usd:
            facts.append(f"**${asset.struct_data.monthly_cost_usd:.2f}/month**")
        
        if facts:
            lines.append(" - ".join(facts))
            lines.append("")
        
        # Key attributes
        attributes = []
        
        if asset.struct_data.owner_email:
            attributes.append(f"**Owner**: {asset.struct_data.owner_email}")
        
        if asset.struct_data.team:
            attributes.append(f"**Team**: {asset.struct_data.team}")
        
        if asset.struct_data.last_modified_timestamp:
            attributes.append(f"**Last Modified**: {self._format_date(asset.struct_data.last_modified_timestamp)}")
        
        if attributes:
            lines.extend(attributes)
        
        return "\n".join(lines)
    
    def _generate_metrics_table(self, asset: BigQueryAssetSchema) -> str:
        """Generate key metrics table"""
        
        lines = []
        lines.append("## Key Metrics")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        
        metrics = []
        
        if asset.struct_data.row_count is not None:
            metrics.append(("Row Count", f"{asset.struct_data.row_count:,}"))
        
        if asset.struct_data.size_bytes is not None:
            metrics.append(("Size", self._format_size(asset.struct_data.size_bytes)))
        
        if asset.struct_data.column_count is not None:
            metrics.append(("Columns", str(asset.struct_data.column_count)))
        
        if asset.struct_data.created_timestamp:
            metrics.append(("Created", self._format_date(asset.struct_data.created_timestamp)))
        
        if asset.struct_data.last_modified_timestamp:
            metrics.append(("Last Modified", self._format_date(asset.struct_data.last_modified_timestamp)))
        
        if asset.struct_data.last_accessed_timestamp:
            metrics.append(("Last Accessed", self._format_date(asset.struct_data.last_accessed_timestamp)))
        
        if asset.struct_data.volatility:
            metrics.append(("Volatility", asset.struct_data.volatility.upper()))
        
        if asset.struct_data.cache_ttl:
            metrics.append(("Cache TTL", asset.struct_data.cache_ttl))
        
        for name, value in metrics:
            lines.append(f"| {name} | {value} |")
        
        return "\n".join(lines)
    
    def _generate_schema_section(
        self, asset: BigQueryAssetSchema, extended_metadata: Optional[Dict[str, Any]]
    ) -> str:
        """Generate schema section with sample values"""
        
        lines = []
        lines.append("## Schema")
        lines.append("")
        
        # Extract schema from extended metadata if available
        schema = None
        sample_values = {}
        
        if extended_metadata and "schema" in extended_metadata:
            schema = extended_metadata["schema"]
        
        # Get sample values from extended metadata
        if extended_metadata and "quality_stats" in extended_metadata:
            quality_stats = extended_metadata["quality_stats"]
            if isinstance(quality_stats, dict) and "sample_values" in quality_stats:
                sample_values = quality_stats["sample_values"]
        
        if schema and "fields" in schema:
            lines.append("| Column | Type | Mode | Description | Sample Values |")
            lines.append("|--------|------|------|-------------|---------------|")
            
            for field in schema["fields"]:
                name = field.get("name", "")
                type_ = field.get("type", "")
                mode = field.get("mode", "NULLABLE")
                description = field.get("description", "")
                
                # Get sample values for this column
                samples = sample_values.get(name, [])
                if samples:
                    # Truncate long values and join
                    samples_display = ", ".join([str(s)[:30] for s in samples[:3]])
                    if len(samples_display) > 50:
                        samples_display = samples_display[:50] + "..."
                else:
                    samples_display = ""
                
                # Add PII indicator if field looks sensitive (ASCII-only)
                if self._is_sensitive_field(name):
                    name = f"{name} [SENSITIVE]"
                
                lines.append(f"| {name} | {type_} | {mode} | {description} | {samples_display} |")
        else:
            lines.append(f"*Schema contains {asset.struct_data.column_count or 'unknown'} columns*")
            lines.append("")
            lines.append("Run full discovery to see detailed schema information.")
        
        return "\n".join(lines)
    
    def _generate_governance_section(self, asset: BigQueryAssetSchema) -> str:
        """Generate security and governance section"""
        
        lines = []
        lines.append("## Security & Governance")
        lines.append("")
        
        governance_items = []
        
        # Data classification
        classifications = []
        if asset.struct_data.has_pii:
            classifications.append("**PII** (Personally Identifiable Information)")
        if asset.struct_data.has_phi:
            classifications.append("**PHI** (Protected Health Information)")
        
        if classifications:
            governance_items.append(("Data Classification", ", ".join(classifications)))
        else:
            governance_items.append(("Data Classification", "No sensitive data detected"))
        
        # Encryption
        if asset.struct_data.encryption_type:
            governance_items.append(("Encryption", asset.struct_data.encryption_type))
        
        # Ownership
        if asset.struct_data.owner_email:
            governance_items.append(("Owner", asset.struct_data.owner_email))
        
        if asset.struct_data.team:
            governance_items.append(("Team", asset.struct_data.team))
        
        # Environment
        governance_items.append(("Environment", (asset.struct_data.environment or "unknown").upper()))
        
        # Tags
        if asset.struct_data.tags:
            tags_str = ", ".join(f"`{tag}`" for tag in asset.struct_data.tags)
            governance_items.append(("Tags", tags_str))
        
        # Render as list
        for label, value in governance_items:
            lines.append(f"- **{label}**: {value}")
        
        return "\n".join(lines)
    
    def _generate_cost_section(self, asset: BigQueryAssetSchema) -> str:
        """Generate cost analysis section"""
        
        lines = []
        lines.append("## Cost Analysis")
        lines.append("")
        
        monthly_cost = asset.struct_data.monthly_cost_usd
        storage_cost = asset.struct_data.storage_cost_usd
        query_cost = asset.struct_data.query_cost_usd
        
        lines.append(f"**Total Monthly Cost**: ${monthly_cost:.2f}")
        lines.append("")
        
        if storage_cost or query_cost:
            lines.append("| Component | Cost |")
            lines.append("|-----------|------|")
            
            if storage_cost:
                lines.append(f"| Storage | ${storage_cost:.2f} |")
            if query_cost:
                lines.append(f"| Queries | ${query_cost:.2f} |")
            
            lines.append(f"| **Total** | **${monthly_cost:.2f}** |")
        
        # Cost per GB
        if asset.struct_data.size_bytes and monthly_cost:
            size_gb = asset.struct_data.size_bytes / (1024**3)
            cost_per_gb = monthly_cost / size_gb if size_gb > 0 else 0
            lines.append("")
            lines.append(f"*Cost per GB*: ${cost_per_gb:.2f}")
        
        return "\n".join(lines)
    
    def _generate_quality_section(self, asset: BigQueryAssetSchema, extended_metadata: Optional[Dict[str, Any]] = None) -> str:
        """Generate data quality section"""
        
        lines = []
        lines.append("## Data Quality")
        lines.append("")
        
        metrics = []
        
        if asset.struct_data.completeness_score is not None:
            score = asset.struct_data.completeness_score * 100
            status = "GOOD" if score >= 95 else "FAIR" if score >= 80 else "POOR"
            metrics.append(f"**Completeness**: {score:.1f}% [{status}]")
        
        if asset.struct_data.freshness_score is not None:
            score = asset.struct_data.freshness_score * 100
            status = "GOOD" if score >= 95 else "FAIR" if score >= 80 else "POOR"
            metrics.append(f"**Freshness**: {score:.1f}% [{status}]")
        
        # Add null statistics if available
        if extended_metadata and "quality_stats" in extended_metadata:
            quality_stats = extended_metadata["quality_stats"]
            if quality_stats and "columns" in quality_stats:
                lines.append("### Null Statistics")
                lines.append("")
                lines.append("| Column | Null Count | Null % |")
                lines.append("|--------|------------|--------|")
                
                # Sort by null percentage (highest first)
                sorted_cols = sorted(
                    quality_stats["columns"].items(),
                    key=lambda x: x[1].get("null_percentage", 0),
                    reverse=True
                )
                
                # Show top 20 columns with highest null percentage
                for col_name, stats in sorted_cols[:20]:
                    null_count = stats.get("null_count", 0)
                    null_pct = stats.get("null_percentage", 0.0)
                    lines.append(f"| {col_name} | {null_count:,} | {null_pct:.1f}% |")
                
                if len(sorted_cols) > 20:
                    lines.append(f"| *...and {len(sorted_cols) - 20} more columns* | | |")
                
                lines.append("")
        
        if metrics:
            lines.extend(metrics)
        elif not (extended_metadata and "quality_stats" in extended_metadata):
            lines.append("*No quality metrics available*")
        
        return "\n".join(lines)
    
    def _generate_lineage_section(self, lineage: Dict[str, Any]) -> str:
        """Generate lineage section"""
        
        lines = []
        lines.append("## Data Lineage")
        lines.append("")
        
        upstream = lineage.get("upstream_tables", [])
        downstream = lineage.get("downstream_tables", [])
        
        if upstream:
            lines.append("### Upstream Sources")
            lines.append("")
            for table in upstream[:10]:
                lines.append(f"- `{table}`")
            if len(upstream) > 10:
                lines.append(f"- *... and {len(upstream) - 10} more*")
            lines.append("")
        
        if downstream:
            lines.append("### Downstream Consumers")
            lines.append("")
            for table in downstream[:10]:
                lines.append(f"- `{table}`")
            if len(downstream) > 10:
                lines.append(f"- *... and {len(downstream) - 10} more*")
        
        if not upstream and not downstream:
            lines.append("*No lineage information available*")
        
        return "\n".join(lines)
    
    def _generate_usage_section(self, usage: Dict[str, Any]) -> str:
        """Generate usage patterns section"""
        
        lines = []
        lines.append("## Usage Patterns")
        lines.append("")
        
        query_count = usage.get("query_count_30d")
        if query_count:
            lines.append(f"**Queries (Last 30 days)**: {query_count:,}")
        
        active_users = usage.get("active_users_30d")
        if active_users:
            lines.append(f"**Active Users**: {active_users}")
        
        avg_query_time = usage.get("avg_query_time_seconds")
        if avg_query_time:
            lines.append(f"**Avg Query Time**: {avg_query_time:.2f}s")
        
        return "\n".join(lines)
    
    def _generate_footer(self, asset: BigQueryAssetSchema) -> str:
        """Generate report footer"""
        
        lines = []
        lines.append("---")
        lines.append("")
        lines.append(f"*Report generated at {asset.struct_data.indexed_at}*")
        lines.append("")
        lines.append(f"**Full Path**: `{asset.struct_data.project_id}.{asset.struct_data.dataset_id}.{asset.struct_data.table_id}`")
        lines.append("")
        lines.append("*This report is generated from cached metadata. For real-time information, query the live system.*")
        
        return "\n".join(lines)
    
    def _extract_description_from_content(self, content: str) -> str:
        """Extract description section from content text"""
        
        # Look for description section
        if "## Description" in content:
            parts = content.split("## Description")
            if len(parts) > 1:
                desc_section = parts[1].split("##")[0].strip()
                return desc_section
        
        # Fallback: return first paragraph
        lines = content.split("\n")
        desc_lines = []
        for line in lines:
            if line.startswith("#"):
                continue
            if line.strip():
                desc_lines.append(line)
            if len(desc_lines) > 5:
                break
        
        return "\n".join(desc_lines) if desc_lines else "*No description available*"
    
    def _format_date(self, timestamp: str) -> str:
        """Format ISO timestamp to human-readable date"""
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return dt.strftime("%Y-%m-%d %H:%M UTC")
        except:
            return timestamp
    
    def _format_size(self, size_bytes: int) -> str:
        """Format size in bytes to human-readable format"""
        if size_bytes == 0:
            return "0 B"
        
        # Convert to appropriate unit
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024**2:
            return f"{size_bytes / 1024:.2f} KB"
        elif size_bytes < 1024**3:
            return f"{size_bytes / (1024**2):.2f} MB"
        else:
            return f"{size_bytes / (1024**3):.2f} GB"
    
    def _is_sensitive_field(self, field_name: str) -> bool:
        """Check if field name suggests sensitive data"""
        sensitive_keywords = [
            "email", "phone", "ssn", "credit_card", "password",
            "address", "name", "dob", "birth", "salary", "account"
        ]
        field_lower = field_name.lower()
        return any(keyword in field_lower for keyword in sensitive_keywords)
    
    def _generate_column_profiles_section(self, column_profiles: Dict[str, Any]) -> str:
        """Generate column profiling section"""
        
        lines = []
        lines.append("## Column Profiles")
        lines.append("")
        
        if not column_profiles:
            lines.append("*No column profiles available*")
            return "\n".join(lines)
        
        # Numeric columns
        numeric_cols = {k: v for k, v in column_profiles.items() if v.get("type") == "numeric"}
        if numeric_cols:
            lines.append("### Numeric Columns")
            lines.append("")
            lines.append("| Column | Min | Max | Avg | Distinct |")
            lines.append("|--------|-----|-----|-----|----------|")
            
            for col_name, profile in sorted(numeric_cols.items()):
                min_val = profile.get("min")
                max_val = profile.get("max")
                avg_val = profile.get("avg")
                distinct = profile.get("distinct_count", 0)
                
                # Format values
                min_str = f"{min_val:.2f}" if isinstance(min_val, (int, float)) and min_val is not None else str(min_val)
                max_str = f"{max_val:.2f}" if isinstance(max_val, (int, float)) and max_val is not None else str(max_val)
                avg_str = f"{avg_val:.2f}" if isinstance(avg_val, (int, float)) and avg_val is not None else str(avg_val)
                
                lines.append(f"| {col_name} | {min_str} | {max_str} | {avg_str} | {distinct:,} |")
            
            lines.append("")
        
        # String columns
        string_cols = {k: v for k, v in column_profiles.items() if v.get("type") == "string"}
        if string_cols:
            lines.append("### String Columns")
            lines.append("")
            lines.append("| Column | Min Length | Max Length | Distinct |")
            lines.append("|--------|------------|------------|----------|")
            
            for col_name, profile in sorted(string_cols.items()):
                min_len = profile.get("min_length")
                max_len = profile.get("max_length")
                distinct = profile.get("distinct_count", 0)
                
                lines.append(f"| {col_name} | {min_len} | {max_len} | {distinct:,} |")
            
            lines.append("")
        
        # Other columns (timestamp, etc.)
        other_cols = {k: v for k, v in column_profiles.items() if v.get("type") == "other"}
        if other_cols:
            lines.append("### Other Columns (Timestamp, etc.)")
            lines.append("")
            lines.append("| Column | Distinct | Null % |")
            lines.append("|--------|----------|--------|")
            
            for col_name, profile in sorted(other_cols.items()):
                distinct = profile.get("distinct_count", 0)
                null_ratio = profile.get("null_ratio", 0.0)
                null_pct = null_ratio * 100.0
                
                lines.append(f"| {col_name} | {distinct:,} | {null_pct:.1f}% |")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def export_to_file(self, markdown: str, output_path: Path) -> None:
        """Export Markdown report to file"""
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding='utf-8')
        logger.info(f"Exported report to {output_path}")
    
    def export_to_gcs(
        self,
        markdown: str,
        gcs_bucket: str,
        gcs_path: str,
    ) -> str:
        """
        Export Markdown report to GCS.
        
        Returns:
            GCS URI of exported file
        """
        from google.cloud import storage
        
        storage_client = storage.Client()
        bucket = storage_client.bucket(gcs_bucket)
        blob = bucket.blob(gcs_path)
        
        # Explicitly encode as UTF-8 and set content type
        blob.upload_from_string(
            markdown.encode('utf-8'),
            content_type="text/markdown; charset=utf-8"
        )
        
        gcs_uri = f"gs://{gcs_bucket}/{gcs_path}"
        logger.info(f"Exported report to {gcs_uri}")
        
        return gcs_uri

