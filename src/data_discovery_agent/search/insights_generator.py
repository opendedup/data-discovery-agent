"""
Insights Generator

Analyzes table metadata and generates actionable insights and recommendations.
Inspired by BigQuery ML's contribution analysis insights.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class InsightsGenerator:
    """
    Generates automated insights from table metadata.
    
    Provides actionable recommendations based on:
    - Data quality issues
    - Schema anomalies
    - Usage patterns
    - Cost optimization opportunities
    - Lineage gaps
    """
    
    def __init__(self):
        pass
    
    def generate_insights(
        self,
        metadata: Dict[str, Any],
        quality_stats: Optional[Dict[str, Any]] = None,
        column_profiles: Optional[Dict[str, Any]] = None,
        lineage: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, str]]:
        """
        Generate insights from table metadata.
        
        Args:
            metadata: Table metadata (size, row count, timestamps, etc.)
            quality_stats: Data quality statistics
            column_profiles: Column profiling data
            lineage: Lineage information
            
        Returns:
            List of insights with severity, category, and message
        """
        insights = []
        
        # Data quality insights
        if quality_stats:
            insights.extend(self._analyze_data_quality(metadata, quality_stats))
        
        # Schema insights
        if column_profiles:
            insights.extend(self._analyze_schema(metadata, column_profiles))
        
        # Usage insights
        insights.extend(self._analyze_usage(metadata))
        
        # Cost insights
        insights.extend(self._analyze_cost(metadata))
        
        # Lineage insights
        if lineage:
            insights.extend(self._analyze_lineage(metadata, lineage))
        
        # Size/growth insights
        insights.extend(self._analyze_size(metadata))
        
        return insights
    
    def _analyze_data_quality(
        self,
        metadata: Dict[str, Any],
        quality_stats: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Analyze data quality and identify issues"""
        insights = []
        
        if not quality_stats or 'columns' not in quality_stats:
            return insights
        
        columns = quality_stats.get('columns', {})
        
        # Find columns with high null percentage
        high_null_cols = []
        moderate_null_cols = []
        
        for col_name, stats in columns.items():
            null_pct = stats.get('null_percentage', 0)
            
            if null_pct >= 95:
                high_null_cols.append((col_name, null_pct))
            elif null_pct >= 50:
                moderate_null_cols.append((col_name, null_pct))
        
        if high_null_cols:
            col_names = ', '.join([f"`{col}`" for col, _ in high_null_cols[:3]])
            if len(high_null_cols) > 3:
                col_names += f" and {len(high_null_cols) - 3} more"
            
            insights.append({
                'severity': 'warning',
                'category': 'Data Quality',
                'message': f"High null percentage detected: {col_names} have ≥95% nulls. Consider dropping these columns or investigating data pipeline issues."
            })
        
        if moderate_null_cols:
            insights.append({
                'severity': 'info',
                'category': 'Data Quality',
                'message': f"{len(moderate_null_cols)} column(s) have 50-95% nulls. Review if these are expected sparse columns or data quality issues."
            })
        
        # Check for complete columns (0% nulls)
        complete_cols = sum(1 for stats in columns.values() if stats.get('null_percentage', 100) == 0)
        total_cols = len(columns)
        
        if complete_cols == total_cols:
            insights.append({
                'severity': 'info',
                'category': 'Data Quality',
                'message': f"Excellent data quality: All {total_cols} columns are 100% populated with no nulls."
            })
        
        return insights
    
    def _analyze_schema(
        self,
        metadata: Dict[str, Any],
        column_profiles: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Analyze schema for anomalies and recommendations"""
        insights = []
        
        # Check for columns with low cardinality (potential for partitioning/clustering)
        low_cardinality_cols = []
        
        for col_name, profile in column_profiles.items():
            distinct_count = profile.get('distinct_count', 0)
            
            # If distinct count is very low relative to row count, flag it
            row_count = metadata.get('row_count', 1)
            if distinct_count > 0 and row_count > 0:
                cardinality_ratio = distinct_count / row_count
                
                if cardinality_ratio < 0.01 and distinct_count < 1000:  # <1% unique and <1000 values
                    low_cardinality_cols.append((col_name, distinct_count))
        
        if low_cardinality_cols:
            col_names = ', '.join([f"`{col}` ({count} values)" for col, count in low_cardinality_cols[:3]])
            insights.append({
                'severity': 'info',
                'category': 'Schema Optimization',
                'message': f"Low cardinality columns detected: {col_names}. Consider using these for table clustering or partitioning to improve query performance."
            })
        
        # Check for string columns with consistent length (potential for optimization)
        fixed_length_strings = []
        
        for col_name, profile in column_profiles.items():
            if profile.get('type') == 'string':
                min_len = profile.get('min_length')
                max_len = profile.get('max_length')
                
                if min_len == max_len and min_len is not None and min_len > 0:
                    fixed_length_strings.append((col_name, min_len))
        
        if fixed_length_strings:
            col_names = ', '.join([f"`{col}` ({length} chars)" for col, length in fixed_length_strings[:3]])
            insights.append({
                'severity': 'info',
                'category': 'Schema Optimization',
                'message': f"Fixed-length string columns: {col_names}. These appear to be codes/IDs with consistent formatting."
            })
        
        return insights
    
    def _analyze_usage(
        self,
        metadata: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Analyze usage patterns"""
        insights = []
        
        # Check last modified time
        last_modified = metadata.get('last_modified_timestamp')
        if last_modified:
            try:
                last_mod_date = datetime.fromisoformat(last_modified.replace('Z', '+00:00'))
                days_since_modified = (datetime.now(last_mod_date.tzinfo) - last_mod_date).days
                
                if days_since_modified > 90:
                    insights.append({
                        'severity': 'info',
                        'category': 'Usage',
                        'message': f"Table hasn't been modified in {days_since_modified} days. Consider archiving if no longer actively used."
                    })
                elif days_since_modified < 1:
                    insights.append({
                        'severity': 'info',
                        'category': 'Usage',
                        'message': f"Table was recently modified (within 24 hours). Active table with frequent updates."
                    })
            except:
                pass
        
        return insights
    
    def _analyze_cost(
        self,
        metadata: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Analyze cost and provide optimization recommendations"""
        insights = []
        
        monthly_cost = metadata.get('monthly_cost_usd', 0)
        size_bytes = metadata.get('size_bytes', 0)
        row_count = metadata.get('row_count', 0)
        
        # High cost tables
        if monthly_cost > 100:
            insights.append({
                'severity': 'warning',
                'category': 'Cost Optimization',
                'message': f"High monthly cost (${monthly_cost:.2f}). Consider partitioning, clustering, or archiving older data to reduce costs."
            })
        
        # Large tables with potential for compression
        if size_bytes > 100 * 1024**3:  # >100GB
            size_gb = size_bytes / (1024**3)
            insights.append({
                'severity': 'info',
                'category': 'Cost Optimization',
                'message': f"Large table ({size_gb:.1f} GB). Consider enabling column-level compression or moving to long-term storage if infrequently accessed."
            })
        
        # Small tables taking up negligible space
        if size_bytes < 1024**2 and row_count < 1000:  # <1MB and <1000 rows
            insights.append({
                'severity': 'info',
                'category': 'Cost Optimization',
                'message': f"Small table ({row_count:,} rows, {size_bytes:,} bytes). Negligible storage cost - no optimization needed."
            })
        
        return insights
    
    def _analyze_lineage(
        self,
        metadata: Dict[str, Any],
        lineage: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Analyze lineage and identify gaps"""
        insights = []
        
        upstream = lineage.get('upstream_tables', [])
        downstream = lineage.get('downstream_tables', [])
        
        # Tables with no downstream consumers (potential for cleanup)
        if not downstream and metadata.get('row_count', 0) > 0:
            insights.append({
                'severity': 'warning',
                'category': 'Lineage',
                'message': f"No downstream consumers detected. This table may be unused and could be a candidate for archival or removal."
            })
        
        # Tables with many downstream consumers (critical table)
        if len(downstream) >= 5:
            insights.append({
                'severity': 'critical',
                'category': 'Lineage',
                'message': f"Critical table: {len(downstream)} downstream dependencies. Changes to this table will impact multiple views/tables. Test thoroughly before modifications."
            })
        
        # Tables with upstream sources from GCS (data ingestion)
        gcs_sources = [u for u in upstream if u.startswith('gs://')]
        if gcs_sources:
            insights.append({
                'severity': 'info',
                'category': 'Lineage',
                'message': f"Data ingestion table: Loaded from {len(gcs_sources)} GCS source(s). Monitor source data quality and ingestion pipeline health."
            })
        
        # Source tables (no upstream)
        if not upstream:
            insights.append({
                'severity': 'info',
                'category': 'Lineage',
                'message': f"Source table: No upstream dependencies. This is a root table in your data pipeline."
            })
        
        return insights
    
    def _analyze_size(
        self,
        metadata: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Analyze table size and growth"""
        insights = []
        
        row_count = metadata.get('row_count', 0)
        size_bytes = metadata.get('size_bytes', 0)
        column_count = metadata.get('column_count', 0)
        
        # Check average row size
        if row_count > 0 and size_bytes > 0:
            avg_row_size = size_bytes / row_count
            
            if avg_row_size > 10 * 1024:  # >10KB per row
                insights.append({
                    'severity': 'warning',
                    'category': 'Schema Design',
                    'message': f"Large average row size ({avg_row_size/1024:.1f} KB/row). Consider normalizing nested RECORD fields or moving large columns to separate tables."
                })
        
        # Many columns
        if column_count > 100:
            insights.append({
                'severity': 'info',
                'category': 'Schema Design',
                'message': f"Wide table with {column_count} columns. Consider if all columns are necessary or if some can be moved to separate tables for better query performance."
            })
        
        return insights
    
    def format_insights_markdown(self, insights: List[Dict[str, str]]) -> str:
        """Format insights as Markdown"""
        if not insights:
            return "*No automated insights generated. Table appears healthy.*"
        
        # Group by severity
        critical = [i for i in insights if i['severity'] == 'critical']
        warnings = [i for i in insights if i['severity'] == 'warning']
        info = [i for i in insights if i['severity'] == 'info']
        
        lines = []
        
        if critical:
            lines.append("### [CRITICAL] Action Required")
            lines.append("")
            for insight in critical:
                lines.append(f"- **{insight['category']}**: {insight['message']}")
            lines.append("")
        
        if warnings:
            lines.append("### [WARNING] Recommendations")
            lines.append("")
            for insight in warnings:
                lines.append(f"- **{insight['category']}**: {insight['message']}")
            lines.append("")
        
        if info:
            lines.append("### [INFO] Observations")
            lines.append("")
            for insight in info:
                lines.append(f"- **{insight['category']}**: {insight['message']}")
            lines.append("")
        
        return "\n".join(lines).strip()

