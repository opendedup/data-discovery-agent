"""
BigQuery Metadata Collector

Scans BigQuery projects, datasets, and tables to collect comprehensive metadata.
This is the foundation of Phase 2 - populating Vertex AI Search with discoverable assets.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from google.cloud import bigquery
from google.cloud.exceptions import GoogleCloudError

from ..search.metadata_formatter import MetadataFormatter
from ..search.jsonl_schema import BigQueryAssetSchema

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
    ):
        """
        Initialize BigQuery collector.
        
        Args:
            project_id: Project ID where this collector runs (for billing)
            target_projects: List of projects to scan (None = scan current project only)
            exclude_datasets: Dataset patterns to exclude (e.g., ['_', 'temp_'])
        """
        self.project_id = project_id
        self.target_projects = target_projects or [project_id]
        self.exclude_datasets = exclude_datasets or ['_staging', 'temp_', 'tmp_']
        
        # Initialize clients
        self.client = bigquery.Client(project=project_id)
        self.formatter = MetadataFormatter(project_id=project_id)
        
        # Stats tracking
        self.stats = {
            'projects_scanned': 0,
            'datasets_scanned': 0,
            'tables_scanned': 0,
            'tables_formatted': 0,
            'errors': 0,
        }
        
        logger.info(
            f"Initialized BigQueryCollector for project={project_id}, "
            f"targets={target_projects}"
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
                self.stats['projects_scanned'] += 1
                
                # Check limit
                if max_tables and len(all_assets) >= max_tables:
                    logger.info(f"Reached max_tables limit ({max_tables}), stopping")
                    all_assets = all_assets[:max_tables]
                    break
                    
            except GoogleCloudError as e:
                logger.error(f"Error scanning project {project}: {e}")
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
                    self.stats['datasets_scanned'] += 1
                    
                except GoogleCloudError as e:
                    logger.error(f"Error scanning dataset {dataset_id}: {e}")
                    self.stats['errors'] += 1
                    continue
        
        except GoogleCloudError as e:
            logger.error(f"Error listing datasets in {project_id}: {e}")
            self.stats['errors'] += 1
        
        return assets
    
    def _scan_dataset(
        self,
        project_id: str,
        dataset_id: str,
        include_views: bool = True,
    ) -> List[BigQueryAssetSchema]:
        """Scan all tables in a dataset"""
        
        assets = []
        
        try:
            dataset_ref = f"{project_id}.{dataset_id}"
            tables = list(self.client.list_tables(dataset_ref))
            
            logger.info(f"Found {len(tables)} tables in {dataset_ref}")
            
            for table_ref in tables:
                table_id = table_ref.table_id
                
                # Skip views if not included
                if not include_views and table_ref.table_type == "VIEW":
                    continue
                
                try:
                    asset = self._collect_table_metadata(
                        project_id,
                        dataset_id,
                        table_id
                    )
                    
                    if asset:
                        assets.append(asset)
                        self.stats['tables_formatted'] += 1
                    
                    self.stats['tables_scanned'] += 1
                    
                    # Log progress every 10 tables
                    if self.stats['tables_scanned'] % 10 == 0:
                        logger.info(
                            f"Progress: {self.stats['tables_scanned']} tables scanned, "
                            f"{self.stats['tables_formatted']} formatted"
                        )
                
                except Exception as e:
                    logger.error(f"Error collecting {project_id}.{dataset_id}.{table_id}: {e}")
                    self.stats['errors'] += 1
                    continue
        
        except GoogleCloudError as e:
            logger.error(f"Error listing tables in {dataset_ref}: {e}")
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
            
            # Format using our MetadataFormatter
            asset = self.formatter.format_bigquery_table(
                table_metadata=table_metadata,
                schema_info=schema_info,
                lineage_info=None,  # Phase 2.3
                cost_info=cost_info,
                quality_info=None,  # Future enhancement
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

