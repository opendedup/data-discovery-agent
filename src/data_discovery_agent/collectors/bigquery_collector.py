"""
BigQuery Metadata Collector

Scans BigQuery projects, datasets, and tables to collect comprehensive metadata.
This is the foundation of Phase 2 - populating Vertex AI Search with discoverable assets.
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from google.cloud import bigquery
from google.cloud.exceptions import GoogleCloudError
from google.cloud.datacatalog_lineage_v1 import LineageClient
from google.cloud.datacatalog_lineage_v1.types import (
    SearchLinksRequest,
    EntityReference,
)

from ..search.metadata_formatter import MetadataFormatter
from ..search.jsonl_schema import BigQueryAssetSchema
from .dataplex_profiler import DataplexProfiler
from .gemini_describer import GeminiDescriber

logger = logging.getLogger(__name__)


class BigQueryCollector:
    """
    Collects metadata from BigQuery for discovery and indexing.
    
    Features:
    - Scans projects, datasets, and tables
    - Extracts comprehensive metadata (schema, stats, timestamps)
    - Basic cost estimation
    - Progress tracking
    - Error handling and retry logic
    """
    
    def __init__(
        self,
        project_id: str,
        target_projects: Optional[List[str]] = None,
        exclude_datasets: Optional[List[str]] = None,
        use_dataplex_profiling: bool = False,
        dataplex_location: str = "us-central1",
        use_gemini_descriptions: bool = True,
        gemini_api_key: Optional[str] = None,
        max_workers: int = 5,
    ):
        """
        Initialize BigQuery collector.
        
        Args:
            project_id: Project ID where this collector runs (for billing)
            target_projects: List of projects to scan (None = scan current project only)
            exclude_datasets: Dataset patterns to exclude (e.g., ['_', 'temp_'])
            use_dataplex_profiling: Use Dataplex Data Profile Scan instead of SQL-based profiling
            dataplex_location: Dataplex location for profile scans (default: us-central1)
            use_gemini_descriptions: Use Gemini to generate descriptions for tables without them
            gemini_api_key: Gemini API key (or uses GEMINI_API_KEY env var)
            max_workers: Maximum number of concurrent threads for collection (default: 5)
        """
        self.project_id = project_id
        self.target_projects = target_projects or [project_id]
        
        # Build exclusion list - always exclude the metadata dataset to avoid circular indexing
        default_excludes = ['_staging', 'temp_', 'tmp_']
        
        # Get the metadata dataset from env and add to exclusions
        metadata_dataset = os.getenv("BQ_DATASET", "data_discovery")
        if metadata_dataset not in default_excludes:
            default_excludes.append(metadata_dataset)
        
        self.exclude_datasets = exclude_datasets or default_excludes
        
        # Ensure metadata dataset is in exclusions even if user provided custom list
        if metadata_dataset not in self.exclude_datasets:
            self.exclude_datasets.append(metadata_dataset)
        
        self.use_dataplex_profiling = use_dataplex_profiling
        self.max_workers = max_workers
        self.stats_lock = Lock()  # Thread-safe stats updates
        
        # Initialize clients
        self.client = bigquery.Client(project=project_id)
        self.formatter = MetadataFormatter(project_id=project_id)
        
        # Initialize Lineage client for data lineage
        try:
            self.lineage_client = LineageClient()
            logger.info("Data Lineage API enabled")
        except Exception as e:
            logger.warning(f"Could not initialize Lineage client: {e}")
            self.lineage_client = None
        
        # Initialize Dataplex profiler if enabled
        if use_dataplex_profiling:
            try:
                self.dataplex_profiler = DataplexProfiler(
                    project_id=project_id,
                    location=dataplex_location
                )
                logger.info(f"Dataplex Data Profile Scan enabled (location: {dataplex_location})")
            except Exception as e:
                logger.warning(f"Could not initialize Dataplex profiler: {e}")
                logger.warning("Falling back to SQL-based profiling")
                self.dataplex_profiler = None
                self.use_dataplex_profiling = False
        else:
            self.dataplex_profiler = None
        
        # Initialize Gemini describer for auto-generating descriptions
        if use_gemini_descriptions:
            try:
                self.gemini_describer = GeminiDescriber(api_key=gemini_api_key)
                if self.gemini_describer.enabled:
                    logger.info("Gemini description generation enabled")
                else:
                    logger.warning("Gemini API key not found - description generation disabled")
                    self.gemini_describer = None
            except Exception as e:
                logger.warning(f"Could not initialize Gemini describer: {e}")
                self.gemini_describer = None
        else:
            self.gemini_describer = None
        
        # Stats tracking
        self.stats = {
            'projects_scanned': 0,
            'datasets_scanned': 0,
            'tables_scanned': 0,
            'tables_formatted': 0,
            'errors': 0,
            'descriptions_generated': 0,
        }
        
        logger.info(
            f"Initialized BigQueryCollector for project={project_id}, "
            f"targets={target_projects}, "
            f"excluding datasets: {self.exclude_datasets}"
        )
    
    def collect_all(
        self,
        max_tables: Optional[int] = None,
        include_views: bool = True,
    ) -> List[BigQueryAssetSchema]:
        """
        Collect metadata from all accessible BigQuery tables.
        
        Args:
            max_tables: Maximum number of tables to collect (for testing)
            include_views: Whether to include views
        
        Returns:
            List of formatted BigQuery assets
        """
        
        logger.info(f"Starting BigQuery metadata collection")
        logger.info(f"Target projects: {self.target_projects}")
        
        all_assets = []
        
        for project in self.target_projects:
            try:
                logger.info(f"Scanning project: {project}")
                assets = self._scan_project(project, include_views=include_views)
                all_assets.extend(assets)
                with self.stats_lock:
                    self.stats['projects_scanned'] += 1
                
                # Check limit
                if max_tables and len(all_assets) >= max_tables:
                    logger.info(f"Reached max_tables limit ({max_tables}), stopping")
                    all_assets = all_assets[:max_tables]
                    break
                    
            except GoogleCloudError as e:
                logger.error(f"Error scanning project {project}: {e}")
                with self.stats_lock:
                    self.stats['errors'] += 1
                continue
        
        logger.info(f"Collection complete: {len(all_assets)} assets collected")
        self._print_stats()
        
        return all_assets
    
    def _scan_project(
        self,
        project_id: str,
        include_views: bool = True,
    ) -> List[BigQueryAssetSchema]:
        """Scan all datasets in a project"""
        
        assets = []
        
        try:
            # List datasets
            datasets = list(self.client.list_datasets(project=project_id))
            logger.info(f"Found {len(datasets)} datasets in {project_id}")
            
            for dataset_ref in datasets:
                dataset_id = dataset_ref.dataset_id
                
                # Skip excluded datasets
                if self._should_exclude_dataset(dataset_id):
                    logger.debug(f"Skipping excluded dataset: {dataset_id}")
                    continue
                
                try:
                    dataset_assets = self._scan_dataset(
                        project_id,
                        dataset_id,
                        include_views=include_views
                    )
                    assets.extend(dataset_assets)
                    with self.stats_lock:
                        self.stats['datasets_scanned'] += 1
                    
                except GoogleCloudError as e:
                    logger.error(f"Error scanning dataset {dataset_id}: {e}")
                    with self.stats_lock:
                        self.stats['errors'] += 1
                    continue
        
        except GoogleCloudError as e:
            logger.error(f"Error listing datasets in {project_id}: {e}")
            with self.stats_lock:
                self.stats['errors'] += 1
        
        return assets
    
    def _scan_dataset(
        self,
        project_id: str,
        dataset_id: str,
        include_views: bool = True,
    ) -> List[BigQueryAssetSchema]:
        """Scan all tables in a dataset using multi-threading"""
        
        assets = []
        
        try:
            dataset_ref = f"{project_id}.{dataset_id}"
            tables = list(self.client.list_tables(dataset_ref))
            
            logger.info(f"Found {len(tables)} tables in {dataset_ref}")
            
            # Filter tables
            tables_to_process = []
            for table_ref in tables:
                # Skip views if not included
                if not include_views and table_ref.table_type == "VIEW":
                    continue
                tables_to_process.append(table_ref)
            
            logger.info(f"Processing {len(tables_to_process)} tables with {self.max_workers} workers")
            
            # Process tables in parallel using ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all tasks
                future_to_table = {
                    executor.submit(
                        self._collect_table_metadata,
                        project_id,
                        dataset_id,
                        table_ref.table_id
                    ): table_ref.table_id
                    for table_ref in tables_to_process
                }
                
                # Collect results as they complete
                for future in as_completed(future_to_table):
                    table_id = future_to_table[future]
                    try:
                        asset = future.result()
                        
                        if asset:
                            assets.append(asset)
                            with self.stats_lock:
                                self.stats['tables_formatted'] += 1
                        
                        with self.stats_lock:
                            self.stats['tables_scanned'] += 1
                            
                            # Log progress every 10 tables
                            if self.stats['tables_scanned'] % 10 == 0:
                                logger.info(
                                    f"Progress: {self.stats['tables_scanned']} tables scanned, "
                                    f"{self.stats['tables_formatted']} formatted"
                                )
                    
                    except Exception as e:
                        logger.error(f"Error collecting {project_id}.{dataset_id}.{table_id}: {e}")
                        with self.stats_lock:
                            self.stats['errors'] += 1
                        continue
        
        except GoogleCloudError as e:
            logger.error(f"Error listing tables in {dataset_ref}: {e}")
            with self.stats_lock:
                self.stats['errors'] += 1
        
        return assets
    
    def _collect_table_metadata(
        self,
        project_id: str,
        dataset_id: str,
        table_id: str,
    ) -> Optional[BigQueryAssetSchema]:
        """Collect comprehensive metadata for a single table"""
        
        try:
            # Get table reference
            table_ref = f"{project_id}.{dataset_id}.{table_id}"
            table = self.client.get_table(table_ref)
            
            # Build core metadata
            table_metadata = {
                "project_id": project_id,
                "dataset_id": dataset_id,
                "table_id": table_id,
                "table_type": table.table_type,
                "description": table.description or "",
                "num_rows": table.num_rows,
                "num_bytes": table.num_bytes,
                "column_count": len(table.schema) if table.schema else 0,
                "created_time": table.created.isoformat() if table.created else None,
                "modified_time": table.modified.isoformat() if table.modified else None,
                "schema": self._format_schema(table.schema) if table.schema else None,
            }
            
            # Extract schema info
            schema_info = None
            if table.schema:
                schema_info = {"fields": self._format_schema(table.schema).get("fields", [])}
            
            # Basic cost estimation
            cost_info = self._estimate_cost(table)
            
            # Check for common PII indicators in schema
            security_info = self._detect_pii_indicators(table.schema) if table.schema else {}
            
            # Governance info from labels
            governance_info = {
                "labels": dict(table.labels) if table.labels else {},
                "tags": list(table.labels.keys()) if table.labels else [],
            }
            
            # Fetch extended metadata for complete JSONL
            # Get quality stats (null counts, percentages)
            quality_stats = self._get_quality_stats(
                project_id, dataset_id, table_id, table.schema
            ) if table.schema else {}
            
            # Get column profiles (min/max/avg/distinct)
            column_profiles = self._get_column_profiles(
                project_id, dataset_id, table_id, table.schema
            ) if table.schema else {}
            
            # Get lineage information
            lineage = self._get_lineage(project_id, dataset_id, table_id)
            
            # Get sample values for columns
            # Use Dataplex samples if available (more efficient than SQL queries)
            sample_values = {}
            if self.dataplex_profiler:
                sample_values = self.dataplex_profiler.get_sample_values_from_profile(
                    dataset_id, table_id
                )
                if sample_values:
                    logger.info(f"Using Dataplex sample values for {table_id} ({len(sample_values)} columns)")
            
            # Fall back to SQL-based sampling if no Dataplex samples
            if not sample_values and table.schema:
                logger.info(f"Fetching sample values via SQL for {table_id}")
                sample_values = self._get_sample_values(
                    project_id, dataset_id, table_id, table.schema
                )
            
            # Build comprehensive quality_info
            quality_info = {}
            if quality_stats or column_profiles or sample_values:
                quality_info = {
                    "columns": quality_stats.get("columns", {}),
                    "column_profiles": column_profiles,
                    "sample_values": sample_values,
                    "total_rows": quality_stats.get("total_rows", table.num_rows),
                }
            
            # Generate description with Gemini if missing
            if not table.description and self.gemini_describer:
                try:
                    logger.info(f"Generating description for {table_id} using Gemini...")
                    generated_desc = self.gemini_describer.generate_table_description(
                        table_name=table_ref,
                        schema=schema_info.get("fields", []) if schema_info else [],
                        sample_values=sample_values,
                        column_profiles=column_profiles,
                        row_count=table.num_rows,
                        size_bytes=table.num_bytes,
                    )
                    
                    if generated_desc:
                        table_metadata["description"] = generated_desc
                        with self.stats_lock:
                            self.stats['descriptions_generated'] += 1
                        logger.info(f"✓ Generated description for {table_id}")
                    else:
                        logger.warning(f"Failed to generate description for {table_id}")
                except Exception as e:
                    logger.error(f"Error generating description for {table_id}: {e}")
            
            # Generate analytical insights with Gemini
            insights = None
            if self.gemini_describer:
                try:
                    logger.info(f"Generating insights for {table_id} using Gemini...")
                    insights = self.gemini_describer.generate_table_insights(
                        table_name=table_ref,
                        description=table_metadata.get("description", ""),
                        schema=schema_info.get("fields", []) if schema_info else [],
                        sample_values=sample_values,
                        column_profiles=column_profiles,
                        row_count=table.num_rows,
                        num_insights=5,
                    )
                    
                    if insights:
                        logger.info(f"✓ Generated {len(insights)} insights for {table_id}")
                        # Add insights to quality_info for inclusion in JSONL/Markdown
                        if not quality_info:
                            quality_info = {}
                        quality_info["insights"] = insights
                    else:
                        logger.warning(f"Failed to generate insights for {table_id}")
                except Exception as e:
                    logger.error(f"Error generating insights for {table_id}: {e}")
            
            # Build lineage_info
            lineage_info = None
            if lineage:
                lineage_info = {
                    "upstream_tables": lineage.get("upstream", []),
                    "downstream_tables": lineage.get("downstream", []),
                }
            
            # Format using our MetadataFormatter with complete data
            asset = self.formatter.format_bigquery_table(
                table_metadata=table_metadata,
                schema_info=schema_info,
                lineage_info=lineage_info,
                cost_info=cost_info,
                quality_info=quality_info,
                security_info=security_info,
                governance_info=governance_info,
            )
            
            logger.debug(f"Collected metadata for {table_ref}")
            return asset
            
        except GoogleCloudError as e:
            logger.error(f"Error getting table {project_id}.{dataset_id}.{table_id}: {e}")
            return None
    
    def _format_schema(self, schema: List[bigquery.SchemaField]) -> Dict[str, Any]:
        """Format BigQuery schema to our format"""
        
        fields = []
        for field in schema:
            field_dict = {
                "name": field.name,
                "type": field.field_type,
                "mode": field.mode,
                "description": field.description or "",
            }
            
            # Handle nested fields
            if field.fields:
                field_dict["fields"] = [
                    {
                        "name": f.name,
                        "type": f.field_type,
                        "mode": f.mode,
                        "description": f.description or "",
                    }
                    for f in field.fields
                ]
            
            fields.append(field_dict)
        
        return {"fields": fields}
    
    def _estimate_cost(self, table: bigquery.Table) -> Dict[str, float]:
        """
        Basic cost estimation.
        
        BigQuery pricing (us-central1):
        - Storage: $0.020 per GB/month (active), $0.010 per GB/month (long-term)
        - Query: $6.25 per TB processed
        
        This is a rough estimate. Phase 2.2 will add precise billing data.
        """
        
        if not table.num_bytes:
            return {}
        
        size_gb = table.num_bytes / (1024 ** 3)
        
        # Assume active storage for now
        storage_cost_monthly = size_gb * 0.020
        
        # Very rough query cost estimate (assume scanned once per week)
        size_tb = size_gb / 1024
        query_cost_monthly = size_tb * 6.25 * 4  # ~4 times per month
        
        return {
            "storage_cost_usd": round(storage_cost_monthly, 2),
            "query_cost_usd": round(query_cost_monthly, 2),
            "total_monthly_cost_usd": round(storage_cost_monthly + query_cost_monthly, 2),
        }
    
    def _detect_pii_indicators(self, schema: List[bigquery.SchemaField]) -> Dict[str, bool]:
        """
        Detect potential PII based on column names.
        
        This is a basic heuristic. Phase 2.X will add DLP API integration.
        """
        
        pii_keywords = [
            'email', 'phone', 'ssn', 'social_security',
            'credit_card', 'card_number', 'cvv',
            'address', 'street', 'zip', 'postal',
            'name', 'firstname', 'lastname', 'full_name',
            'dob', 'date_of_birth', 'birth_date',
            'ip_address', 'ipaddress',
            'passport', 'license', 'drivers_license',
        ]
        
        phi_keywords = [
            'diagnosis', 'medical', 'health', 'patient',
            'prescription', 'treatment', 'condition',
            'mrn', 'medical_record',
        ]
        
        has_pii = False
        has_phi = False
        
        for field in schema:
            field_name_lower = field.name.lower()
            
            if any(keyword in field_name_lower for keyword in pii_keywords):
                has_pii = True
            
            if any(keyword in field_name_lower for keyword in phi_keywords):
                has_phi = True
        
        return {
            "has_pii": has_pii,
            "has_phi": has_phi,
        }
    
    def _should_exclude_dataset(self, dataset_id: str) -> bool:
        """Check if dataset should be excluded"""
        
        for pattern in self.exclude_datasets:
            if pattern in dataset_id:
                return True
        
        return False
    
    def _print_stats(self):
        """Print collection statistics"""
        
        logger.info("=" * 60)
        logger.info("BigQuery Metadata Collection Statistics")
        logger.info("=" * 60)
        logger.info(f"Projects scanned:    {self.stats['projects_scanned']}")
        logger.info(f"Datasets scanned:    {self.stats['datasets_scanned']}")
        logger.info(f"Tables scanned:      {self.stats['tables_scanned']}")
        logger.info(f"Tables formatted:    {self.stats['tables_formatted']}")
        logger.info(f"Errors encountered:  {self.stats['errors']}")
        logger.info("=" * 60)
    
    def get_stats(self) -> Dict[str, int]:
        """Get collection statistics"""
        return self.stats.copy()
    
    def _get_quality_stats(
        self, 
        project_id: str, 
        dataset_id: str, 
        table_id: str,
        schema: List[bigquery.SchemaField]
    ) -> Dict[str, Any]:
        """
        Get data quality statistics including null counts and percentages.
        
        Uses Dataplex Data Profile Scan if enabled, otherwise falls back to SQL-based profiling.
        
        Returns:
            Dictionary with quality stats per column
        """
        # Try Dataplex profiling first if enabled
        if self.use_dataplex_profiling and self.dataplex_profiler:
            try:
                profile = self.dataplex_profiler.get_profile_scan_for_table(
                    dataset_id=dataset_id,
                    table_id=table_id,
                )
                
                if profile and profile.get('columns'):
                    # Convert Dataplex profile to our format
                    columns = {}
                    for col_name, col_data in profile['columns'].items():
                        null_ratio = col_data.get('null_ratio', 0.0)
                        columns[col_name] = {
                            'null_count': int(profile['row_count'] * null_ratio),
                            'null_percentage': null_ratio * 100.0,
                        }
                    
                    logger.info(f"Using Dataplex profile for {table_id}")
                    return {
                        'total_rows': profile['row_count'],
                        'columns': columns,
                    }
                else:
                    logger.debug(f"No Dataplex profile found for {table_id}, using SQL fallback")
                    
            except Exception as e:
                logger.debug(f"Dataplex profiling failed for {table_id}: {e}, using SQL fallback")
        
        # Fallback to SQL-based profiling
        try:
            # Build dynamic query for null stats
            null_checks = []
            for field in schema:
                if field.field_type not in ['RECORD', 'STRUCT']:  # Skip complex types
                    null_checks.append(
                        f"COUNTIF(`{field.name}` IS NULL) AS `{field.name}_nulls`, "
                        f"ROUND(100.0 * COUNTIF(`{field.name}` IS NULL) / COUNT(*), 2) AS `{field.name}_null_pct`"
                    )
            
            if not null_checks:
                return {}
            
            query = f"""
                SELECT
                    COUNT(*) AS total_rows,
                    {', '.join(null_checks)}
                FROM `{project_id}.{dataset_id}.{table_id}`
            """
            
            # Execute query
            query_job = self.client.query(query)
            result = list(query_job.result())
            
            if not result:
                return {}
            
            row = result[0]
            stats = {
                "total_rows": row.get("total_rows", 0),
                "columns": {}
            }
            
            # Extract per-column stats
            for field in schema:
                if field.field_type not in ['RECORD', 'STRUCT']:
                    stats["columns"][field.name] = {
                        "null_count": row.get(f"{field.name}_nulls", 0),
                        "null_percentage": row.get(f"{field.name}_null_pct", 0.0),
                    }
            
            return stats
            
        except Exception as e:
            logger.warning(f"Could not fetch quality stats for {project_id}.{dataset_id}.{table_id}: {e}")
            return {}
    
    def _get_column_profiles(
        self,
        project_id: str,
        dataset_id: str,
        table_id: str,
        schema: List[bigquery.SchemaField],
        sample_limit: int = 10000
    ) -> Dict[str, Any]:
        """
        Get column profiling including min/max/distinct values.
        
        Uses Dataplex Data Profile Scan if enabled, otherwise falls back to SQL-based profiling.
        
        Args:
            sample_limit: Limit sampling to this many rows for performance
            
        Returns:
            Dictionary with column profiles
        """
        # Try Dataplex profiling first if enabled
        if self.use_dataplex_profiling and self.dataplex_profiler:
            try:
                profile = self.dataplex_profiler.get_profile_scan_for_table(
                    dataset_id=dataset_id,
                    table_id=table_id,
                )
                
                if profile and profile.get('columns'):
                    # Use Dataplex profiles directly - they already have the correct format
                    profiles = profile['columns']
                    
                    if profiles:
                        logger.info(f"Using Dataplex column profiles for {table_id}")
                        return profiles
                    else:
                        logger.debug(f"No Dataplex column profiles found for {table_id}, using SQL fallback")
                    
            except Exception as e:
                logger.debug(f"Dataplex column profiling failed for {table_id}: {e}, using SQL fallback")
        
        # Fallback to SQL-based profiling
        try:
            profiles = {}
            
            # Build profile queries for numeric and string columns
            profile_checks = []
            numeric_types = ['INTEGER', 'INT64', 'FLOAT', 'FLOAT64', 'NUMERIC', 'BIGNUMERIC']
            string_types = ['STRING', 'BYTES']
            
            for field in schema:
                if field.field_type in numeric_types:
                    profile_checks.append(
                        f"MIN(`{field.name}`) AS `{field.name}_min`, "
                        f"MAX(`{field.name}`) AS `{field.name}_max`, "
                        f"AVG(`{field.name}`) AS `{field.name}_avg`, "
                        f"APPROX_COUNT_DISTINCT(`{field.name}`) AS `{field.name}_distinct`"
                    )
                elif field.field_type in string_types:
                    profile_checks.append(
                        f"MIN(LENGTH(`{field.name}`)) AS `{field.name}_min_length`, "
                        f"MAX(LENGTH(`{field.name}`)) AS `{field.name}_max_length`, "
                        f"APPROX_COUNT_DISTINCT(`{field.name}`) AS `{field.name}_distinct`"
                    )
            
            if not profile_checks:
                return {}
            
            # Sample table for performance
            query = f"""
                SELECT
                    {', '.join(profile_checks)}
                FROM `{project_id}.{dataset_id}.{table_id}`
                LIMIT {sample_limit}
            """
            
            # Execute query
            query_job = self.client.query(query)
            result = list(query_job.result())
            
            if not result:
                return {}
            
            row = result[0]
            
            # Extract per-column profiles
            for field in schema:
                if field.field_type in numeric_types:
                    profiles[field.name] = {
                        "type": "numeric",
                        "min": row.get(f"{field.name}_min"),
                        "max": row.get(f"{field.name}_max"),
                        "avg": row.get(f"{field.name}_avg"),
                        "distinct_count": row.get(f"{field.name}_distinct", 0),
                    }
                elif field.field_type in string_types:
                    profiles[field.name] = {
                        "type": "string",
                        "min_length": row.get(f"{field.name}_min_length"),
                        "max_length": row.get(f"{field.name}_max_length"),
                        "distinct_count": row.get(f"{field.name}_distinct", 0),
                    }
            
            return profiles
            
        except Exception as e:
            logger.warning(f"Could not fetch column profiles for {project_id}.{dataset_id}.{table_id}: {e}")
            return {}
    
    def _get_lineage(
        self,
        project_id: str,
        dataset_id: str,
        table_id: str,
    ) -> Dict[str, Any]:
        """
        Get data lineage information for a table.
        
        Returns upstream sources and downstream dependencies.
        Uses INFORMATION_SCHEMA to find views/tables that reference this table.
        
        Args:
            project_id: GCP project ID
            dataset_id: BigQuery dataset ID
            table_id: BigQuery table ID
            
        Returns:
            Dictionary with upstream_tables and downstream_tables lists
        """
        lineage_info = {
            "upstream_tables": [],
            "downstream_tables": [],
        }
        
        try:
            # Find downstream dependencies by searching view definitions
            # that reference this table
            table_ref = f"`{project_id}.{dataset_id}.{table_id}`"
            
            # Query to find views that reference this table
            query = f"""
                SELECT 
                    table_catalog as project_id,
                    table_schema as dataset_id,
                    table_name as table_id,
                    table_type
                FROM `{project_id}.{dataset_id}.INFORMATION_SCHEMA.TABLES`
                WHERE table_type IN ('VIEW', 'MATERIALIZED_VIEW')
                AND table_schema = '{dataset_id}'
            """
            
            result = self.client.query(query).result()
            
            for row in result:
                # Get the view definition to check if it references our table
                view_project = row['project_id']
                view_dataset = row['dataset_id']
                view_table = row['table_id']
                
                try:
                    view_ref = f"{view_project}.{view_dataset}.{view_table}"
                    view_obj = self.client.get_table(view_ref)
                    
                    # Check if view definition references our table
                    if hasattr(view_obj, 'view_query') and view_obj.view_query:
                        if table_id in view_obj.view_query or f"{dataset_id}.{table_id}" in view_obj.view_query:
                            lineage_info["downstream_tables"].append(view_ref)
                except Exception as e:
                    logger.debug(f"Could not check view {view_ref}: {e}")
            
            # Try to find upstream sources from table DDL (for tables created with SELECT)
            try:
                table = self.client.get_table(f"{project_id}.{dataset_id}.{table_id}")
                
                # For views, parse the view_query
                if hasattr(table, 'view_query') and table.view_query:
                    # Extract table references from query (basic parsing)
                    import re
                    # Match patterns like: `project.dataset.table` or dataset.table
                    patterns = [
                        r'`([^`]+)\.([^`]+)\.([^`]+)`',  # `project.dataset.table`
                        r'FROM\s+([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)',  # FROM dataset.table
                        r'JOIN\s+([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)',  # JOIN dataset.table
                    ]
                    
                    for pattern in patterns:
                        matches = re.findall(pattern, table.view_query, re.IGNORECASE)
                        for match in matches:
                            if len(match) == 3:  # project.dataset.table
                                source_ref = f"{match[0]}.{match[1]}.{match[2]}"
                            elif len(match) == 2:  # dataset.table
                                source_ref = f"{project_id}.{match[0]}.{match[1]}"
                            
                            # Don't add the table itself
                            if source_ref != f"{project_id}.{dataset_id}.{table_id}":
                                if source_ref not in lineage_info["upstream_tables"]:
                                    lineage_info["upstream_tables"].append(source_ref)
            except Exception as e:
                logger.debug(f"Could not parse upstream sources: {e}")
            
            return lineage_info
            
        except Exception as e:
            logger.warning(f"Could not fetch lineage for {project_id}.{dataset_id}.{table_id}: {e}")
            return {}
    
    def _get_sample_values(
        self,
        project_id: str,
        dataset_id: str,
        table_id: str,
        schema: List[bigquery.SchemaField],
        limit: int = 3,
    ) -> Dict[str, List[Any]]:
        """
        Get top N sample values for each column via SQL queries.
        
        This is a FALLBACK method - Dataplex sample values are preferred.
        Only used when Dataplex profiling is not available.
        
        This helps users understand what kind of data is in each column.
        
        Args:
            project_id: GCP project ID
            dataset_id: BigQuery dataset ID
            table_id: BigQuery table ID
            schema: Table schema
            limit: Number of sample values to fetch per column (default: 3)
            
        Returns:
            Dictionary mapping column names to lists of sample values
        """
        
        samples = {}
        
        try:
            # Build column list (exclude RECORD/STRUCT types for simplicity)
            columns = []
            for field in schema:
                if field.field_type not in ('RECORD', 'STRUCT'):
                    columns.append(field.name)
            
            if not columns:
                return samples
            
            # Fetch distinct sample values for each column
            # We'll query each column separately to avoid complexity
            table_ref = f"`{project_id}.{dataset_id}.{table_id}`"
            
            for col in columns[:30]:  # Limit to first 30 columns to avoid excessive queries
                try:
                    # Get top N distinct non-null values
                    query = f"""
                        SELECT DISTINCT `{col}` as value
                        FROM {table_ref}
                        WHERE `{col}` IS NOT NULL
                        LIMIT {limit}
                    """
                    
                    result = self.client.query(query).result()
                    values = []
                    
                    for row in result:
                        val = row['value']
                        # Convert to string representation
                        if val is not None:
                            # Handle different types
                            if isinstance(val, (bytes, bytearray)):
                                values.append(f"<bytes: {len(val)} bytes>")
                            elif isinstance(val, (list, dict)):
                                values.append(str(val)[:100])  # Truncate complex types
                            else:
                                values.append(str(val))
                    
                    if values:
                        samples[col] = values
                
                except Exception as e:
                    logger.debug(f"Could not fetch samples for column {col}: {e}")
                    continue
            
            return samples
            
        except Exception as e:
            logger.warning(f"Could not fetch sample values for {project_id}.{dataset_id}.{table_id}: {e}")
            return {}

