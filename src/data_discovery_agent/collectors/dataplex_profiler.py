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
from google.cloud.dataplex_v1.types import DataScan, DataProfileResult, GetDataScanRequest
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
        
        formatted = {
            "row_count": result.row_count,
            "columns": {}
        }
        
        # Add scanned data info if available
        if result.scanned_data and hasattr(result.scanned_data, 'data_size_bytes'):
            formatted["scanned_data"] = {
                "bytes": result.scanned_data.data_size_bytes
            }
        
        # Extract column-level profiles
        if result.profile and result.profile.fields:
            for field in result.profile.fields:
                col_name = field.name
                profile_info = field.profile
                
                if not profile_info:
                    continue
                
                col_data = {
                    "null_ratio": profile_info.null_ratio if hasattr(profile_info, 'null_ratio') else 0.0,
                    "distinct_ratio": profile_info.distinct_ratio if hasattr(profile_info, 'distinct_ratio') else 0.0,
                    "distinct_count": int(result.row_count * profile_info.distinct_ratio) if hasattr(profile_info, 'distinct_ratio') else 0,
                }
                
                # Integer/Numeric stats
                if profile_info.integer_profile:
                    int_profile = profile_info.integer_profile
                    col_data["type"] = "numeric"
                    col_data.update({
                        "avg": int_profile.average,  # Use "avg" for consistency with markdown formatter
                        "mean": int_profile.average,  # Also keep "mean" for compatibility
                        "min": int_profile.min_,
                        "max": int_profile.max_,
                        "stddev": int_profile.standard_deviation,
                        "median": int_profile.quartiles[1] if int_profile.quartiles and len(int_profile.quartiles) > 1 else None,
                        "quartiles": list(int_profile.quartiles) if int_profile.quartiles else [],
                    })
                elif profile_info.double_profile:
                    dbl_profile = profile_info.double_profile
                    col_data["type"] = "numeric"
                    col_data.update({
                        "avg": dbl_profile.average,  # Use "avg" for consistency with markdown formatter
                        "mean": dbl_profile.average,  # Also keep "mean" for compatibility
                        "min": dbl_profile.min_,
                        "max": dbl_profile.max_,
                        "stddev": dbl_profile.standard_deviation,
                        "median": dbl_profile.quartiles[1] if dbl_profile.quartiles and len(dbl_profile.quartiles) > 1 else None,
                        "quartiles": list(dbl_profile.quartiles) if dbl_profile.quartiles else [],
                    })
                
                # String stats
                if profile_info.string_profile:
                    str_profile = profile_info.string_profile
                    col_data["type"] = "string"
                    col_data.update({
                        "min_length": str_profile.min_length,
                        "max_length": str_profile.max_length,
                        "avg_length": str_profile.average_length if hasattr(str_profile, 'average_length') else None,
                    })
                
                # Other types (timestamp, etc.) - still add to profiles for distinct count info
                if not profile_info.integer_profile and not profile_info.double_profile and not profile_info.string_profile:
                    col_data["type"] = "other"
                
                # Top N values (most common values)
                if profile_info.top_n_values:
                    col_data["top_values"] = [
                        {"value": str(v.value), "count": v.count}
                        for v in profile_info.top_n_values[:10]  # Limit to top 10
                    ]
                    
                    # Extract sample values (just the values, not counts) for easy display
                    col_data["sample_values"] = [
                        str(v.value) for v in profile_info.top_n_values[:3]  # Top 3 for samples
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

