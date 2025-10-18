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
        if asset.content.text:
            sections.append("## 📝 Description")
            sections.append("")
            # Extract description from content text
            description = self._extract_description_from_content(asset.content.text)
            sections.append(description)
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
        if asset.struct_data.completeness_score or asset.struct_data.freshness_score:
            sections.append(self._generate_quality_section(asset))
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
        
        # Asset type badge
        type_emoji = {
            AssetType.TABLE: "📊",
            AssetType.VIEW: "👁️",
            AssetType.MATERIALIZED_VIEW: "💎",
        }
        emoji = type_emoji.get(asset.struct_data.asset_type, "📊")
        badges.append(f"{emoji} {asset.struct_data.asset_type}")
        
        # Security badges
        if asset.struct_data.has_pii:
            badges.append("🔒 PII")
        if asset.struct_data.has_phi:
            badges.append("🏥 PHI")
        
        # Environment badge
        env_emoji = {
            "prod": "🔴",
            "staging": "🟡",
            "dev": "🟢",
        }
        env = asset.struct_data.environment or "unknown"
        emoji = env_emoji.get(env.lower(), "⚪")
        badges.append(f"{emoji} {env.upper()}")
        
        badge_line = " | ".join(badges)
        
        return f"# {table_name}\n\n{badge_line}"
    
    def _generate_summary(self, asset: BigQueryAssetSchema) -> str:
        """Generate executive summary"""
        
        lines = []
        lines.append("## 📊 Executive Summary")
        lines.append("")
        
        # Quick facts
        facts = []
        
        if asset.struct_data.row_count:
            facts.append(f"**{asset.struct_data.row_count:,}** rows")
        
        if asset.struct_data.size_bytes:
            size_gb = asset.struct_data.size_bytes / (1024**3)
            facts.append(f"**{size_gb:.2f} GB**")
        
        if asset.struct_data.column_count:
            facts.append(f"**{asset.struct_data.column_count}** columns")
        
        if asset.struct_data.monthly_cost_usd:
            facts.append(f"**${asset.struct_data.monthly_cost_usd:.2f}/month**")
        
        if facts:
            lines.append(" • ".join(facts))
            lines.append("")
        
        # Key attributes
        attributes = []
        
        if asset.struct_data.owner_email:
            attributes.append(f"👤 **Owner**: {asset.struct_data.owner_email}")
        
        if asset.struct_data.team:
            attributes.append(f"👥 **Team**: {asset.struct_data.team}")
        
        if asset.struct_data.last_modified_timestamp:
            attributes.append(f"🕒 **Last Modified**: {self._format_date(asset.struct_data.last_modified_timestamp)}")
        
        if attributes:
            lines.extend(attributes)
        
        return "\n".join(lines)
    
    def _generate_metrics_table(self, asset: BigQueryAssetSchema) -> str:
        """Generate key metrics table"""
        
        lines = []
        lines.append("## 📈 Key Metrics")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        
        metrics = []
        
        if asset.struct_data.row_count is not None:
            metrics.append(("Row Count", f"{asset.struct_data.row_count:,}"))
        
        if asset.struct_data.size_bytes is not None:
            size_gb = asset.struct_data.size_bytes / (1024**3)
            metrics.append(("Size", f"{size_gb:.2f} GB"))
        
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
        """Generate schema section"""
        
        lines = []
        lines.append("## 📋 Schema")
        lines.append("")
        
        # Extract schema from extended metadata if available
        schema = None
        if extended_metadata and "schema" in extended_metadata:
            schema = extended_metadata["schema"]
        
        if schema and "fields" in schema:
            lines.append("| Column | Type | Mode | Description |")
            lines.append("|--------|------|------|-------------|")
            
            for field in schema["fields"]:
                name = field.get("name", "")
                type_ = field.get("type", "")
                mode = field.get("mode", "NULLABLE")
                description = field.get("description", "")
                
                # Add PII indicator if field looks sensitive
                if self._is_sensitive_field(name):
                    name = f"{name} 🔒"
                
                lines.append(f"| {name} | {type_} | {mode} | {description} |")
        else:
            lines.append(f"*Schema contains {asset.struct_data.column_count or 'unknown'} columns*")
            lines.append("")
            lines.append("Run full discovery to see detailed schema information.")
        
        return "\n".join(lines)
    
    def _generate_governance_section(self, asset: BigQueryAssetSchema) -> str:
        """Generate security and governance section"""
        
        lines = []
        lines.append("## 🔐 Security & Governance")
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
        lines.append("## 💰 Cost Analysis")
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
    
    def _generate_quality_section(self, asset: BigQueryAssetSchema) -> str:
        """Generate data quality section"""
        
        lines = []
        lines.append("## ✅ Data Quality")
        lines.append("")
        
        metrics = []
        
        if asset.struct_data.completeness_score is not None:
            score = asset.struct_data.completeness_score * 100
            emoji = "🟢" if score >= 95 else "🟡" if score >= 80 else "🔴"
            metrics.append(f"{emoji} **Completeness**: {score:.1f}%")
        
        if asset.struct_data.freshness_score is not None:
            score = asset.struct_data.freshness_score * 100
            emoji = "🟢" if score >= 95 else "🟡" if score >= 80 else "🔴"
            metrics.append(f"{emoji} **Freshness**: {score:.1f}%")
        
        if metrics:
            lines.extend(metrics)
        else:
            lines.append("*No quality metrics available*")
        
        return "\n".join(lines)
    
    def _generate_lineage_section(self, lineage: Dict[str, Any]) -> str:
        """Generate lineage section"""
        
        lines = []
        lines.append("## 🔗 Data Lineage")
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
        lines.append("## 📊 Usage Patterns")
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
        lines.append("💡 *This report is generated from cached metadata. For real-time information, query the live system.*")
        
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
    
    def _is_sensitive_field(self, field_name: str) -> bool:
        """Check if field name suggests sensitive data"""
        sensitive_keywords = [
            "email", "phone", "ssn", "credit_card", "password",
            "address", "name", "dob", "birth", "salary", "account"
        ]
        field_lower = field_name.lower()
        return any(keyword in field_lower for keyword in sensitive_keywords)
    
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
        blob.upload_from_string(markdown, content_type="text/markdown")
        
        gcs_uri = f"gs://{gcs_bucket}/{gcs_path}"
        logger.info(f"Exported report to {gcs_uri}")
        
        return gcs_uri

