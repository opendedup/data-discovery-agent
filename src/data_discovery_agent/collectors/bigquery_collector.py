"""
BigQuery Metadata Collector

Scans BigQuery projects, datasets, and tables to collect comprehensive metadata.
This is the foundation of Phase 2 - populating Vertex AI Search with discoverable assets.
"""

import logging
import os
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from google.cloud import bigquery
from google.cloud.exceptions import GoogleCloudError, NotFound
from google.cloud.datacatalog_lineage_v1 import LineageClient

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
    - Label-based filtering (hierarchical: table labels override dataset labels)
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
        max_workers: int = 2,
        filter_label_key: str = "ignore-gmcp-discovery-scan",
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
            max_workers: Maximum number of concurrent threads for collection (default: 2)
            filter_label_key: BigQuery label key to use for filtering (default: ignore-gmcp-discovery-scan)
                             Tables/datasets with this label set to 'true' are skipped.
                             Table labels override dataset labels.
        """
        self.project_id = project_id
        self.target_projects = target_projects or [project_id]
        self.location = os.getenv("BQ_LOCATION", "US")  # BigQuery location for regional INFORMATION_SCHEMA queries
        
        # Build exclusion list - always exclude the metadata dataset to avoid circular indexing
        default_excludes = ['_staging', 'temp_', 'tmp_']
        
        # Get the metadata dataset from env and add to exclusions
        metadata_dataset = os.getenv("BQ_DATASET", "data_discovery")
        if metadata_dataset not in default_excludes:
            default_excludes.append(metadata_dataset)
        
        self.exclude_datasets = exclude_datasets or default_excludes
        self.metadata_dataset = os.getenv("BQ_DATASET", "data_discovery")
        self.metadata_table = os.getenv("BQ_TABLE", "discovered_assets")

        # Ensure metadata dataset is in exclusions even if user provided custom list
        if self.metadata_dataset not in self.exclude_datasets:
            self.exclude_datasets.append(self.metadata_dataset)
        
        self.use_dataplex_profiling = use_dataplex_profiling
        self.max_workers = max_workers
        self.filter_label_key = filter_label_key
        self.stats_lock = Lock()  # Thread-safe stats updates
        
        # Initialize clients
        self.client = bigquery.Client(project=project_id)
        
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
                    logger.warning("Gemini description generation disabled")
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
            'datasets_filtered_by_label': 0,
            'tables_filtered_by_label': 0,
        }
        
        logger.info(
            f"Initialized BigQueryCollector for project={project_id}, "
            f"targets={target_projects}, "
            f"excluding datasets: {self.exclude_datasets}, "
            f"filter_label_key={filter_label_key}"
        )
    
    def collect_all(
        self,
        max_tables: Optional[int] = None,
        include_views: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Collect metadata from all accessible BigQuery tables.
        
        Args:
            max_tables: Maximum number of tables to collect (for testing)
            include_views: Whether to include views
        
        Returns:
            List of BigQuery asset metadata as dictionaries
        """
        
        logger.info("Starting BigQuery metadata collection")
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
    ) -> List[Dict[str, Any]]:
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
                
                # Get dataset labels for filtering
                dataset_labels = self._get_dataset_labels(project_id, dataset_id)
                
                # Check if dataset should be filtered by label
                dataset_filtered = self._should_filter_by_label(dataset_labels)
                if dataset_filtered:
                    logger.debug(
                        f"Dataset {dataset_id} has {self.filter_label_key}=true, "
                        f"will skip tables unless they have {self.filter_label_key}=false"
                    )
                
                try:
                    dataset_assets = self._scan_dataset(
                        project_id,
                        dataset_id,
                        include_views=include_views,
                        dataset_labels=dataset_labels
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
        dataset_labels: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Scan all tables in a dataset using multi-threading.
        
        Args:
            project_id: GCP project ID
            dataset_id: BigQuery dataset ID
            include_views: Whether to include views
            dataset_labels: Labels from the dataset (for hierarchical filtering)
        
        Returns:
            List of BigQuery asset metadata as dictionaries
        """
        
        assets = []
        dataset_labels = dataset_labels or {}
        dataset_filtered = self._should_filter_by_label(dataset_labels)
        
        try:
            dataset_ref = f"{project_id}.{dataset_id}"
            tables = list(self.client.list_tables(dataset_ref))
            
            logger.info(f"Found {len(tables)} tables in {dataset_ref}")
            
            # Filter tables by type and labels
            tables_to_process = []
            for table_ref in tables:
                # Skip views if not included
                if not include_views and table_ref.table_type == "VIEW":
                    continue
                
                # Apply hierarchical label filtering
                # Get table to check its labels
                try:
                    table = self.client.get_table(f"{project_id}.{dataset_id}.{table_ref.table_id}")
                    table_labels = dict(table.labels) if table.labels else {}
                    
                    # Check if table should be filtered
                    table_filtered = self._should_filter_by_label(table_labels)
                    
                    # Hierarchical logic:
                    # 1. If table has explicit label, use that (overrides dataset)
                    # 2. Otherwise, use dataset-level setting
                    if self.filter_label_key in table_labels:
                        # Table has explicit label - use it
                        if table_filtered:
                            logger.debug(
                                f"Skipping table {table_ref.table_id}: "
                                f"{self.filter_label_key}=true"
                            )
                            with self.stats_lock:
                                self.stats['tables_filtered_by_label'] += 1
                            continue
                        else:
                            logger.debug(
                                f"Including table {table_ref.table_id}: "
                                f"{self.filter_label_key}=false (overrides dataset)"
                            )
                    elif dataset_filtered:
                        # No table label, but dataset is filtered
                        logger.debug(
                            f"Skipping table {table_ref.table_id}: "
                            f"inherited from dataset {self.filter_label_key}=true"
                        )
                        with self.stats_lock:
                            self.stats['tables_filtered_by_label'] += 1
                        continue
                    
                except Exception as e:
                    logger.warning(f"Could not check labels for {table_ref.table_id}: {e}")
                    # If we can't get labels, apply dataset-level filter
                    if dataset_filtered:
                        logger.debug(f"Skipping table {table_ref.table_id}: dataset filtered and labels unavailable")
                        with self.stats_lock:
                            self.stats['tables_filtered_by_label'] += 1
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
    ) -> Optional[Dict[str, Any]]:
        """Collect comprehensive metadata for a single table"""
        
        try:
            # Get table reference
            table_ref = f"{project_id}.{dataset_id}.{table_id}"
            table = self.client.get_table(table_ref)
            
            # Get existing description from metadata table
            existing_table_description = self._get_existing_metadata(project_id, dataset_id, table_id)
            
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
                "schema": self._format_schema(table.schema, existing_table_description.get("column_descriptions")) if table.schema else {},
            }
            
            # Extract schema info
            schema_info = None
            if table.schema:
                schema_info = {"fields": self._format_schema(table.schema, existing_table_description.get("column_descriptions")).get("fields", [])}
            
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
            
            # Merge sample values into schema fields
            if sample_values and table_metadata.get("schema", {}).get("fields"):
                for field in table_metadata["schema"]["fields"]:
                    field_name = field["name"]
                    if field_name in sample_values:
                        field["sample_values"] = sample_values[field_name]
                        logger.debug(f"Added {len(sample_values[field_name])} sample values to field {field_name}")
            
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
            if not table.description:
                if existing_table_description:
                    table_metadata["description"] = existing_table_description["description"]
                    logger.info(f"Using existing description for {table_id} from metadata table.")
                elif self.gemini_describer:
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
                            logger.warning(f"Failed to generate description for {table_id}, using fallback")
                            # Provide a fallback description if Gemini fails
                            table_metadata["description"] = self._generate_fallback_description(
                                table_ref, table.table_type, table.num_rows, len(table.schema) if table.schema else 0
                            )
                    except Exception as e:
                        logger.error(f"Error generating description for {table_id}: {e}, using fallback")
                        # Provide a fallback description on exception
                        table_metadata["description"] = self._generate_fallback_description(
                            table_ref, table.table_type, table.num_rows, len(table.schema) if table.schema else 0
                        )
            
            # If still no description (e.g. Gemini disabled), provide fallback
            if not table_metadata["description"]:
                table_metadata["description"] = self._generate_fallback_description(
                    table_ref, table.table_type, table.num_rows, len(table.schema) if table.schema else 0
                )
            
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
            
            # Build lineage_info - ALWAYS populate, even if empty, to indicate lineage was checked
            # Note: _get_lineage() returns dict with keys "upstream_tables" and "downstream_tables"
            if lineage:
                lineage_info = {
                    "upstream_tables": lineage.get("upstream_tables", []),
                    "downstream_tables": lineage.get("downstream_tables", []),
                }
            else:
                # No lineage found - set empty arrays to explicitly indicate it was checked
                lineage_info = {
                    "upstream_tables": [],
                    "downstream_tables": [],
                }
            
            # Build comprehensive asset dictionary
            asset = {
                # Core metadata
                "project_id": project_id,
                "dataset_id": dataset_id,
                "table_id": table_id,
                "description": table_metadata.get("description", ""),
                "table_type": table_metadata.get("table_type", "TABLE"),
                "created": table_metadata.get("created_time"),
                "last_modified": table_metadata.get("modified_time"),
                "last_accessed": None,  # Not available in basic metadata
                "row_count": table_metadata.get("num_rows"),
                "column_count": table_metadata.get("column_count", 0),
                "size_bytes": table_metadata.get("num_bytes"),
                
                # Security and governance
                "has_pii": security_info.get("has_pii", False) if security_info else False,
                "has_phi": security_info.get("has_phi", False) if security_info else False,
                "environment": governance_info.get("environment", "unknown") if governance_info else "unknown",
                
                # Labels (convert to list of dicts for BigQuery schema)
                "labels": [
                    {"key": k, "value": v}
                    for k, v in governance_info.get("labels", {}).items()
                ] if governance_info else [],
                
                # Schema (already formatted)
                "schema": table_metadata.get("schema", {}).get("fields", []),
                
                # Analytical insights
                "analytical_insights": quality_info.get("insights", []) if quality_info else [],
                
                # Lineage (convert to list of dicts for BigQuery schema)
                "lineage": self._format_lineage_for_bigquery(lineage_info) if lineage_info else [],
                
                # Column profiles (convert to list of dicts for BigQuery schema)
                "column_profiles": self._format_column_profiles_for_bigquery(
                    quality_info.get("column_profiles", {}) if quality_info else {}
                ),
                
                # Key metrics (convert to list of dicts for BigQuery schema)
                "key_metrics": self._format_key_metrics_for_bigquery(
                    quality_info, cost_info, table_metadata
                ),
                
                # Extended metadata for markdown generation (not stored in BQ)
                "_extended": {
                    "schema_info": table_metadata.get("schema"),
                    "lineage_info": lineage_info,
                    "cost_info": cost_info,
                    "quality_info": quality_info,
                    "security_info": security_info,
                    "governance_info": governance_info,
                }
            }
            
            logger.debug(f"Collected metadata for {table_ref}")
            return asset
            
        except GoogleCloudError as e:
            logger.error(f"Error getting table {project_id}.{dataset_id}.{table_id}: {e}")
            return None
    
    def _get_existing_metadata(self, project_id: str, dataset_id: str, table_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the most recent existing metadata for a table from the discovery table.
        
        Args:
            project_id: The project ID of the table to look up.
            dataset_id: The dataset ID of the table to look up.
            table_id: The table ID of the table to look up.
            
        Returns:
            A dictionary with 'description' and 'column_descriptions' if found, otherwise None.
        """
        metadata_table_ref = f"{self.project_id}.{self.metadata_dataset}.{self.metadata_table}"
        
        query = f"""
            SELECT description, schema
            FROM `{metadata_table_ref}`
            WHERE project_id = @project_id
              AND dataset_id = @dataset_id
              AND table_id = @table_id
            ORDER BY insert_timestamp DESC
            LIMIT 1
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("project_id", "STRING", project_id),
                bigquery.ScalarQueryParameter("dataset_id", "STRING", dataset_id),
                bigquery.ScalarQueryParameter("table_id", "STRING", table_id),
            ]
        )
        
        try:
            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job.result())
            
            if not results:
                return None
                
            row = results[0]
            
            column_descriptions = {}
            if row.schema:
                
                def extract_descriptions(fields, parent_name=""):
                    for field in fields:
                        field_name = f"{parent_name}{field.get('name')}"
                        if field.get('description'):
                            column_descriptions[field_name] = field['description']
                        if "fields" in field and field["fields"]:
                             extract_descriptions(field["fields"], parent_name=f"{field_name}.")
                
                extract_descriptions(row.schema)

            return {
                "description": row.description,
                "column_descriptions": column_descriptions,
            }
                
        except NotFound:
            logger.debug(f"Metadata table {metadata_table_ref} not found. Cannot get existing descriptions.")
            return None
        except Exception as e:
            logger.warning(f"Could not query existing metadata for {project_id}.{dataset_id}.{table_id}: {e}")
            return None

    def _format_schema(self, schema: List[bigquery.SchemaField], existing_column_descriptions: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Format BigQuery schema to our format"""
        
        existing_column_descriptions = existing_column_descriptions or {}
        fields = []
        for field in schema:
            # Generate fallback description if missing
            description = field.description
            if not description:
                description = existing_column_descriptions.get(field.name)
            
            if not description:
                description = self._generate_field_fallback_description(field.name, field.field_type, field.mode)
            
            field_dict = {
                "name": field.name,
                "type": field.field_type,
                "mode": field.mode,
                "description": description,
            }
            
            # Handle nested fields
            if field.fields:
                field_dict["fields"] = [
                    {
                        "name": f.name,
                        "type": f.field_type,
                        "mode": f.mode,
                        "description": f.description or existing_column_descriptions.get(f"{field.name}.{f.name}") or self._generate_field_fallback_description(f.name, f.field_type, f.mode),
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
    
    def _generate_fallback_description(
        self, 
        table_ref: str, 
        table_type: str, 
        row_count: Optional[int], 
        column_count: int
    ) -> str:
        """
        Generate a basic fallback description when no description exists and Gemini fails.
        
        Args:
            table_ref: Full table reference (project.dataset.table)
            table_type: Type of the table (TABLE, VIEW, etc.)
            row_count: Number of rows in the table
            column_count: Number of columns in the table
            
        Returns:
            A basic description string
        """
        parts = table_ref.split('.')
        table_id = parts[-1] if parts else "unknown"
        
        # Format table type for display
        type_display = table_type.lower() if table_type else "table"
        
        # Build description
        desc_parts = [f"BigQuery {type_display} '{table_id}'"]
        
        if column_count > 0:
            desc_parts.append(f"with {column_count} column{'s' if column_count != 1 else ''}")
        
        if row_count is not None and row_count >= 0:
            desc_parts.append(f"containing {row_count:,} row{'s' if row_count != 1 else ''}")
        
        description = " ".join(desc_parts) + "."
        
        return description
    
    def _generate_field_fallback_description(
        self,
        field_name: str,
        field_type: str,
        field_mode: str
    ) -> str:
        """
        Generate a basic fallback description for a field without a description.
        
        Args:
            field_name: Name of the field
            field_type: Data type of the field
            field_mode: Mode of the field (NULLABLE, REQUIRED, REPEATED)
            
        Returns:
            A basic description string
        """
        # Make field name more readable
        readable_name = field_name.replace('_', ' ').title()
        
        # Build description based on field type
        type_lower = field_type.lower()
        mode_lower = field_mode.lower() if field_mode else "nullable"
        
        # Create a basic description
        if mode_lower == "repeated":
            description = f"{readable_name} - Array of {type_lower} values"
        elif mode_lower == "required":
            description = f"{readable_name} - Required {type_lower} field"
        else:
            description = f"{readable_name} - {type_lower.capitalize()} field"
        
        return description
    
    def _should_exclude_dataset(self, dataset_id: str) -> bool:
        """Check if dataset should be excluded by pattern matching"""
        
        for pattern in self.exclude_datasets:
            if pattern in dataset_id:
                return True
        
        return False
    
    def _get_dataset_labels(self, project_id: str, dataset_id: str) -> Dict[str, str]:
        """
        Get labels for a dataset.
        
        Args:
            project_id: GCP project ID
            dataset_id: BigQuery dataset ID
            
        Returns:
            Dictionary of labels (empty if dataset not found or has no labels)
        """
        try:
            dataset_ref = f"{project_id}.{dataset_id}"
            dataset = self.client.get_dataset(dataset_ref)
            return dict(dataset.labels) if dataset.labels else {}
        except Exception as e:
            logger.debug(f"Could not get labels for dataset {dataset_id}: {e}")
            return {}
    
    def _should_filter_by_label(self, labels: Dict[str, str]) -> bool:
        """
        Check if a resource should be filtered based on labels.
        
        Args:
            labels: Dictionary of BigQuery labels
            
        Returns:
            True if the resource should be filtered (skipped), False otherwise
        """
        if not labels or self.filter_label_key not in labels:
            return False
        
        label_value = labels.get(self.filter_label_key, "")
        # Case-insensitive comparison for the value
        return str(label_value).lower() == "true"
    
    def _format_lineage_for_bigquery(self, lineage_info: Dict[str, Any]) -> List[Dict[str, str]]:
        """Format lineage info for BigQuery schema (list of source/target dicts)"""
        
        lineage_records = []
        
        # Add upstream sources
        for source in lineage_info.get("upstream_tables", []):
            lineage_records.append({
                "source": source,
                "target": ""  # Empty target means this table is the target
            })
        
        # Add downstream targets
        for target in lineage_info.get("downstream_tables", []):
            lineage_records.append({
                "source": "",  # Empty source means this table is the source
                "target": target
            })
        
        return lineage_records
    
    def _format_column_profiles_for_bigquery(self, column_profiles: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Format column profiles for BigQuery schema"""
        
        profiles_list = []
        
        for col_name, profile in column_profiles.items():
            profile_type = profile.get("type", "other")
            
            profile_dict = {
                "column_name": col_name,
                "profile_type": profile_type,
                "min_value": str(profile.get("min")) if profile.get("min") is not None else None,
                "max_value": str(profile.get("max")) if profile.get("max") is not None else None,
                "avg_value": str(profile.get("avg")) if profile.get("avg") is not None else None,
                "distinct_count": profile.get("distinct_count"),
                "null_percentage": profile.get("null_ratio", 0.0) * 100.0 if "null_ratio" in profile else None,
            }
            
            # Handle string-specific fields
            if "min_length" in profile:
                profile_dict["min_value"] = str(profile["min_length"])
            if "max_length" in profile:
                profile_dict["max_value"] = str(profile["max_length"])
            
            profiles_list.append(profile_dict)
        
        return profiles_list
    
    def _format_key_metrics_for_bigquery(
        self,
        quality_info: Optional[Dict[str, Any]],
        cost_info: Optional[Dict[str, Any]],
        table_metadata: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Format key metrics for BigQuery schema"""
        
        metrics = []
        
        # Add cost metrics
        if cost_info:
            if "storage_cost_usd" in cost_info:
                metrics.append({
                    "metric_name": "storage_cost_monthly_usd",
                    "metric_value": str(cost_info["storage_cost_usd"])
                })
            if "query_cost_usd" in cost_info:
                metrics.append({
                    "metric_name": "query_cost_monthly_usd",
                    "metric_value": str(cost_info["query_cost_usd"])
                })
            if "total_monthly_cost_usd" in cost_info:
                metrics.append({
                    "metric_name": "total_monthly_cost_usd",
                    "metric_value": str(cost_info["total_monthly_cost_usd"])
                })
        
        # Add quality metrics
        if quality_info:
            if "completeness_score" in quality_info:
                metrics.append({
                    "metric_name": "completeness_score",
                    "metric_value": str(quality_info["completeness_score"])
                })
            if "freshness_score" in quality_info:
                metrics.append({
                    "metric_name": "freshness_score",
                    "metric_value": str(quality_info["freshness_score"])
                })
        
        # Add table size metric
        if table_metadata.get("num_bytes"):
            size_gb = table_metadata["num_bytes"] / (1024 ** 3)
            metrics.append({
                "metric_name": "size_gb",
                "metric_value": f"{size_gb:.2f}"
            })
        
        return metrics
    
    def _print_stats(self):
        """Print collection statistics"""
        
        logger.info("=" * 60)
        logger.info("BigQuery Metadata Collection Statistics")
        logger.info("=" * 60)
        logger.info(f"Projects scanned:              {self.stats['projects_scanned']}")
        logger.info(f"Datasets scanned:              {self.stats['datasets_scanned']}")
        logger.info(f"Tables scanned:                {self.stats['tables_scanned']}")
        logger.info(f"Tables formatted:              {self.stats['tables_formatted']}")
        logger.info(f"Tables filtered by label:      {self.stats['tables_filtered_by_label']}")
        logger.info(f"Errors encountered:            {self.stats['errors']}")
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
        Uses both INFORMATION_SCHEMA and Data Catalog Lineage API.
        
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
        
        # First, try to get lineage from Data Catalog Lineage API
        try:
            from google.cloud import datacatalog_lineage_v1
            
            target_fqn = f"bigquery:{project_id}.{dataset_id}.{table_id}"
            lineage_client = datacatalog_lineage_v1.LineageClient()
            lineage_location = os.getenv("LINEAGE_LOCATION", self.location)
            
            # Search for upstream sources (where this table is the target)
            try:
                request = datacatalog_lineage_v1.SearchLinksRequest(
                    parent=f"projects/{project_id}/locations/{lineage_location}",
                    target=datacatalog_lineage_v1.EntityReference(
                        fully_qualified_name=target_fqn
                    )
                )
                
                for link in lineage_client.search_links(request=request):
                    source_fqn = link.source.fully_qualified_name
                    # Don't add self-references
                    if source_fqn != target_fqn and source_fqn not in lineage_info["upstream_tables"]:
                        lineage_info["upstream_tables"].append(source_fqn)
                        logger.debug(f"Found upstream source from Lineage API: {source_fqn}")
            except Exception as e:
                logger.warning(f"Could not search upstream links in Lineage API: {e}")
            
            # Search for downstream targets (where this table is the source)
            try:
                request = datacatalog_lineage_v1.SearchLinksRequest(
                    parent=f"projects/{project_id}/locations/{lineage_location}",
                    source=datacatalog_lineage_v1.EntityReference(
                        fully_qualified_name=target_fqn
                    )
                )
                
                for link in lineage_client.search_links(request=request):
                    target_fqn_link = link.target.fully_qualified_name
                    # Don't add self-references or our own reports
                    if (target_fqn_link != target_fqn 
                        and not target_fqn_link.startswith("gs://") 
                        and not target_fqn_link.endswith(".md")):
                        # Normalize BigQuery FQN (remove bigquery: prefix for consistency)
                        normalized_fqn = target_fqn_link.replace("bigquery:", "")
                        if normalized_fqn not in lineage_info["downstream_tables"]:
                            lineage_info["downstream_tables"].append(normalized_fqn)
                            logger.debug(f"Found downstream target from Lineage API: {normalized_fqn}")
            except Exception as e:
                logger.warning(f"Could not search downstream links in Lineage API: {e}")
                
        except ImportError:
            logger.warning("datacatalog_lineage_v1 not available, skipping Lineage API search")
        except Exception as e:
            logger.warning(f"Could not query Data Catalog Lineage API: {e}")
        
        # Log what we found from Lineage API
        if lineage_info["upstream_tables"]:
            logger.info(f"Found {len(lineage_info['upstream_tables'])} upstream sources from Lineage API for {table_id}")
        if lineage_info["downstream_tables"]:
            logger.info(f"Found {len(lineage_info['downstream_tables'])} downstream targets from Lineage API for {table_id}")
        
        # Then supplement with INFORMATION_SCHEMA discovery
        try:
            # Find downstream dependencies by searching view definitions
            # that reference this table across ALL datasets in the project
            table_ref = f"`{project_id}.{dataset_id}.{table_id}`"
            
            # Search pattern variations for the table reference
            search_patterns = [
                f"{project_id}.{dataset_id}.{table_id}",  # Full reference
                f"{dataset_id}.{table_id}",  # Dataset.table
                f"`{project_id}.{dataset_id}.{table_id}`",  # Backtick wrapped
            ]
            
            # Query ALL views in the project (not just same dataset)
            query = f"""
                SELECT 
                    table_catalog as project_id,
                    table_schema as dataset_id,
                    table_name as table_id
                FROM `{project_id}.region-{self.location.lower()}`.INFORMATION_SCHEMA.VIEWS
                WHERE table_catalog = '{project_id}'
            """
            
            try:
                result = self.client.query(query).result()
                
                for row in result:
                    # Get the view definition to check if it references our table
                    view_project = row['project_id']
                    view_dataset = row['dataset_id']
                    view_table = row['table_id']
                    
                    # Skip if view is in excluded dataset
                    if view_dataset in self.exclude_datasets:
                        continue
                    
                    try:
                        view_ref = f"{view_project}.{view_dataset}.{view_table}"
                        view_obj = self.client.get_table(view_ref)
                        
                        # Check if view definition references our table
                        if hasattr(view_obj, 'view_query') and view_obj.view_query:
                            view_query_lower = view_obj.view_query.lower()
                            
                            # Check all search patterns
                            for pattern in search_patterns:
                                if pattern.lower() in view_query_lower:
                                    if view_ref not in lineage_info["downstream_tables"]:
                                        lineage_info["downstream_tables"].append(view_ref)
                                        logger.debug(f"Found downstream dependency: {view_ref} references {table_ref}")
                                    break
                    except Exception as e:
                        logger.debug(f"Could not check view {view_ref}: {e}")
                        
            except Exception as query_error:
                # Fall back to per-dataset search if regional INFORMATION_SCHEMA fails
                logger.warning(f"Regional INFORMATION_SCHEMA query failed (likely permissions), falling back to dataset-scoped search: {query_error}")
                
                # Get list of all datasets in the project
                try:
                    datasets = list(self.client.list_datasets(project=project_id))
                    logger.info(f"Scanning {len(datasets)} datasets for downstream views...")
                    
                    for dataset_ref in datasets:
                        dataset_name = dataset_ref.dataset_id
                        
                        # Skip excluded datasets
                        if dataset_name in self.exclude_datasets:
                            continue
                        
                        try:
                            fallback_query = f"""
                                SELECT 
                                    table_catalog as project_id,
                                    table_schema as dataset_id,
                                    table_name as table_id,
                                    table_type
                                FROM `{project_id}.{dataset_name}.INFORMATION_SCHEMA.TABLES`
                                WHERE table_type IN ('VIEW', 'MATERIALIZED_VIEW')
                            """
                            
                            result = self.client.query(fallback_query).result()
                            
                            for row in result:
                                view_project = row['project_id']
                                view_dataset = row['dataset_id']
                                view_table = row['table_id']
                                
                                try:
                                    view_ref = f"{view_project}.{view_dataset}.{view_table}"
                                    view_obj = self.client.get_table(view_ref)
                                    
                                    if hasattr(view_obj, 'view_query') and view_obj.view_query:
                                        view_query_lower = view_obj.view_query.lower()
                                        for pattern in search_patterns:
                                            if pattern.lower() in view_query_lower:
                                                if view_ref not in lineage_info["downstream_tables"]:
                                                    lineage_info["downstream_tables"].append(view_ref)
                                                    logger.debug(f"Found downstream dependency: {view_ref}")
                                                break
                                except Exception as e:
                                    logger.debug(f"Could not check view {view_ref}: {e}")
                        except Exception as dataset_error:
                            logger.debug(f"Could not query dataset {dataset_name}: {dataset_error}")
                            continue
                except Exception as list_error:
                    logger.warning(f"Could not list datasets, falling back to single dataset search: {list_error}")
                    
                    # Last resort: just check the same dataset as the table
                    fallback_query = f"""
                        SELECT 
                            table_catalog as project_id,
                            table_schema as dataset_id,
                            table_name as table_id,
                            table_type
                        FROM `{project_id}.{dataset_id}.INFORMATION_SCHEMA.TABLES`
                        WHERE table_type IN ('VIEW', 'MATERIALIZED_VIEW')
                    """
                    
                    result = self.client.query(fallback_query).result()
                    
                    for row in result:
                        view_project = row['project_id']
                        view_dataset = row['dataset_id']
                        view_table = row['table_id']
                        
                        try:
                            view_ref = f"{view_project}.{view_dataset}.{view_table}"
                            view_obj = self.client.get_table(view_ref)
                            
                            if hasattr(view_obj, 'view_query') and view_obj.view_query:
                                view_query_lower = view_obj.view_query.lower()
                                for pattern in search_patterns:
                                    if pattern.lower() in view_query_lower:
                                        if view_ref not in lineage_info["downstream_tables"]:
                                            lineage_info["downstream_tables"].append(view_ref)
                                        break
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

