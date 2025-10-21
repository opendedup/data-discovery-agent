"""
Dataplex Data Profiling Integration

Integrates with Dataplex Universal Catalog data profiling to get:
- Comprehensive column statistics
- Data quality metrics
- PII/PHI detection
- Profile scan results

References:
- https://cloud.google.com/bigquery/docs/data-profile-scan
- https://cloud.google.com/dataplex/docs/reference/rest/v1/projects.locations.dataScans
"""

import logging
from typing import Any, Dict, Optional, List
from google.cloud import dataplex_v1
from google.cloud.dataplex_v1.types import DataProfileResult
from google.api_core.exceptions import NotFound

logger = logging.getLogger(__name__)


class DataplexProfiler:
    """
    Client for Dataplex Data Profiling API.
    
    Provides access to data profile scan results including:
    - Column-level statistics
    - Data quality metrics
    - PII detection results
    - Null ratios, distinct counts, etc.
    """
    
    def __init__(self, project_id: str, location: str = "us-central1"):
        """
        Initialize Dataplex Profiler client.
        
        Args:
            project_id: GCP project ID
            location: Dataplex location (default: us-central1)
        """
        self.project_id = project_id
        self.location = location
        self.client = dataplex_v1.DataScanServiceClient()
    
    def get_profile_scan_for_table(
        self,
        dataset_id: str,
        table_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get data profile scan results for a BigQuery table.
        
        Args:
            dataset_id: BigQuery dataset ID
            table_id: BigQuery table ID
            
        Returns:
            Profile scan results or None if not found
        """
        scan_id = f"profile-{dataset_id}-{table_id}".replace("_", "-").lower()
        scan_name = f"projects/{self.project_id}/locations/{self.location}/dataScans/{scan_id}"
        
        try:
            # Get the data scan with FULL view to include profile results
            request = dataplex_v1.GetDataScanRequest(
                name=scan_name,
                view=dataplex_v1.GetDataScanRequest.DataScanView.FULL
            )
            data_scan = self.client.get_data_scan(request=request)
            
            if data_scan.state != dataplex_v1.State.ACTIVE:
                logger.debug(f"Data scan {scan_id} is not ACTIVE. Current state: {data_scan.state.name}")
                return None
            
            # Check if profile result is available
            if data_scan.data_profile_result:
                logger.info(f"Using Dataplex profile for {dataset_id}.{table_id}")
                return self._format_profile_result(data_scan.data_profile_result)
            else:
                logger.debug(f"No profile result available yet for {scan_id}")
                return None
                
        except NotFound:
            logger.debug(f"Data scan {scan_id} not found")
            return None
        except Exception as e:
            logger.warning(f"Error getting profile scan for {dataset_id}.{table_id}: {e}")
            return None
    
    def _format_profile_result(self, result: DataProfileResult) -> Dict[str, Any]:
        """Format Dataplex profile result into a dictionary compatible with our metadata format"""
        
        # This function is complex due to the nested protobuf structure.
        # It's designed to be robust to missing fields.
        
        def get_attr(obj, attr, default=None):
            """Safely get attribute from a protobuf object or a dict."""
            if isinstance(obj, dict):
                return obj.get(attr, default)
            return getattr(obj, attr, default)

        formatted = {
            "row_count": get_attr(result, 'row_count'),
            "columns": {}
        }
        
        # Add scanned data info if available
        scanned_data = get_attr(result, 'scanned_data')
        if scanned_data and get_attr(scanned_data, 'data_size_bytes') is not None:
            formatted["scanned_data"] = {
                "bytes": get_attr(scanned_data, 'data_size_bytes')
            }
        
        # Extract column-level profiles
        profile = get_attr(result, 'profile')
        if profile and get_attr(profile, 'fields'):
            for field in get_attr(profile, 'fields', []):
                col_name = get_attr(field, 'name')
                profile_info = get_attr(field, 'profile')
                
                if not col_name or not profile_info:
                    continue
                
                null_ratio = get_attr(profile_info, 'null_ratio', 0.0)
                distinct_ratio = get_attr(profile_info, 'distinct_ratio', 0.0)
                
                col_data = {
                    "null_ratio": null_ratio,
                    "distinct_ratio": distinct_ratio,
                    "distinct_count": int(formatted["row_count"] * distinct_ratio) if formatted["row_count"] else 0,
                }
                
                # Integer/Numeric stats
                int_profile = get_attr(profile_info, 'integer_profile')
                dbl_profile = get_attr(profile_info, 'double_profile')
                
                if int_profile:
                    col_data["type"] = "numeric"
                    col_data.update({
                        "avg": get_attr(int_profile, 'average'),
                        "mean": get_attr(int_profile, 'average'),
                        "min": get_attr(int_profile, 'min_'),
                        "max": get_attr(int_profile, 'max_'),
                        "stddev": get_attr(int_profile, 'standard_deviation'),
                        "median": get_attr(int_profile, 'quartiles', [])[1] if len(get_attr(int_profile, 'quartiles', [])) > 1 else None,
                        "quartiles": list(get_attr(int_profile, 'quartiles', [])),
                    })
                elif dbl_profile:
                    col_data["type"] = "numeric"
                    col_data.update({
                        "avg": get_attr(dbl_profile, 'average'),
                        "mean": get_attr(dbl_profile, 'average'),
                        "min": get_attr(dbl_profile, 'min_'),
                        "max": get_attr(dbl_profile, 'max_'),
                        "stddev": get_attr(dbl_profile, 'standard_deviation'),
                        "median": get_attr(dbl_profile, 'quartiles', [])[1] if len(get_attr(dbl_profile, 'quartiles', [])) > 1 else None,
                        "quartiles": list(get_attr(dbl_profile, 'quartiles', [])),
                    })
                
                # String stats
                str_profile = get_attr(profile_info, 'string_profile')
                if str_profile:
                    col_data["type"] = "string"
                    col_data.update({
                        "min_length": get_attr(str_profile, 'min_length'),
                        "max_length": get_attr(str_profile, 'max_length'),
                        "avg_length": get_attr(str_profile, 'average_length'),
                    })
                
                # Other types
                if not int_profile and not dbl_profile and not str_profile:
                    col_data["type"] = "other"
                
                # Top N values
                top_n_values = get_attr(profile_info, 'top_n_values', [])
                if top_n_values:
                    col_data["top_values"] = [
                        {"value": str(get_attr(v, 'value')), "count": get_attr(v, 'count')}
                        for v in top_n_values[:10]
                    ]
                    col_data["sample_values"] = [
                        str(get_attr(v, 'value')) for v in top_n_values[:3]
                    ]
                
                # InfoTypes (PII)
                info_types = get_attr(field, 'info_types', [])
                if info_types:
                    col_data["info_types"] = [
                        {"name": get_attr(it, 'name'), "count": get_attr(it, 'count')}
                        for it in info_types
                    ]
                
                formatted["columns"][col_name] = col_data
        
        return formatted
    
    def get_sample_values_from_profile(
        self,
        dataset_id: str,
        table_id: str,
    ) -> Dict[str, List[str]]:
        """
        Get sample values from a Dataplex profile scan (top N most common values).
        
        This is more efficient than running separate SQL queries for each column.
        
        Args:
            dataset_id: BigQuery dataset ID
            table_id: BigQuery table ID
            
        Returns:
            Dictionary mapping column names to lists of sample values
        """
        
        try:
            # Get the profile result
            profile = self.get_profile_scan_for_table(dataset_id, table_id)
            
            if not profile or "columns" not in profile:
                return {}
            
            # Extract sample values from each column
            samples = {}
            for col_name, col_data in profile["columns"].items():
                if "sample_values" in col_data and col_data["sample_values"]:
                    samples[col_name] = col_data["sample_values"]
            
            return samples
            
        except Exception as e:
            logger.debug(f"Could not get sample values from Dataplex for {dataset_id}.{table_id}: {e}")
            return {}
    
    def create_profile_scan(
        self,
        dataset_id: str,
        table_id: str,
        scan_id: Optional[str] = None,
        sampling_percent: float = 100.0,
        row_filter: Optional[str] = None,
    ) -> str:
        """
        Create a new data profile scan for a BigQuery table.
        
        Args:
            dataset_id: BigQuery dataset ID
            table_id: BigQuery table ID
            scan_id: Optional scan ID (auto-generated if not provided)
            sampling_percent: Percentage of data to sample (default: 100%)
            row_filter: Optional SQL WHERE clause to filter rows
            
        Returns:
            Data scan name
        """
        try:
            parent = f"projects/{self.project_id}/locations/{self.location}"
            
            if not scan_id:
                # Replace underscores with hyphens for Dataplex compatibility
                scan_id = f"profile-{dataset_id}-{table_id}".replace("_", "-").lower()
            
            # Build data scan configuration
            data_scan = dataplex_v1.DataScan()
            data_scan.data.resource = f"//bigquery.googleapis.com/projects/{self.project_id}/datasets/{dataset_id}/tables/{table_id}"
            
            # Configure data profile spec
            data_scan.data_profile_spec.sampling_percent = sampling_percent
            if row_filter:
                data_scan.data_profile_spec.row_filter = row_filter
            
            # Create the scan
            request = dataplex_v1.CreateDataScanRequest(
                parent=parent,
                data_scan=data_scan,
                data_scan_id=scan_id,
            )
            
            operation = self.client.create_data_scan(request=request)
            result = operation.result(timeout=300)  # 5 minute timeout
            
            logger.info(f"Created data profile scan: {result.name}")
            return result.name
            
        except Exception as e:
            logger.error(f"Error creating profile scan: {e}")
            raise
    
    def run_profile_scan(self, scan_name: str) -> str:
        """
        Run a data profile scan.
        
        Args:
            scan_name: Full scan name (projects/.../locations/.../dataScans/...)
            
        Returns:
            Job name
        """
        try:
            request = dataplex_v1.RunDataScanRequest(name=scan_name)
            response = self.client.run_data_scan(request=request)
            
            logger.info(f"Started profile scan job: {response.job.name}")
            return response.job.name
            
        except Exception as e:
            logger.error(f"Error running profile scan: {e}")
            raise

