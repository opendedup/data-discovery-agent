<!-- 104d97ef-78f6-42db-aa54-46b9f97812b0 c9ae9516-ea21-4920-b142-4156c143569f -->
# Limit BigQuery Data Discovery to Single Region

## Overview

Configure the BigQuery data discovery collector to **only scan datasets** in a specific region (controlled by `GCP_DISCOVERY_REGION` environment variable). The collector will skip datasets that don't match the configured region. Store `dataset_region` in metadata for tracking. No runtime filtering or region parameters needed in MCP tools or search.

## Implementation Steps

### 1. Add dataset_region Field to BigQuery Schema

**File: `data-discovery-agent/src/data_discovery_agent/writers/bigquery_writer.py`**

Add `dataset_region` field after line 44:

```python
bigquery.SchemaField("dataset_region", "STRING", description="The GCP region/location where the dataset resides (e.g., 'US', 'us-central1', 'EU')."),
```

### 2. Add dataset_region to Data Models

**File: `data-discovery-agent/src/data_discovery_agent/schemas/asset_schema.py`**

Add to `DiscoveredAssetDict` after line 60:

```python
dataset_region: Optional[str]  # e.g., "US", "us-central1", "EU"
```

**File: `data-discovery-agent/src/data_discovery_agent/models/search_models.py`**

Add to `AssetMetadata` after line 82:

```python
dataset_region: Optional[str] = Field(None, description="Dataset region/location")
```

### 3. Update BigQuery Collector with Region Filtering

**File: `data-discovery-agent/src/data_discovery_agent/collectors/bigquery_collector.py`**

#### 3a. Add discovery_region to **init** (around line 40)

```python
def __init__(
    self,
    project_id: str,
    # ... existing parameters ...
):
    # ... existing code ...
    self.location = os.getenv("BQ_LOCATION", "US")
    
    # NEW: Region filter for discovery
    self.discovery_region = os.getenv("GCP_DISCOVERY_REGION")
    if self.discovery_region:
        logger.info(f"Discovery limited to region: {self.discovery_region}")
    else:
        logger.info("No region filter - will discover all datasets")
```

#### 3b. Create _get_dataset_metadata method (replace _get_dataset_labels around line 882)

```python
def _get_dataset_metadata(self, project_id: str, dataset_id: str) -> Dict[str, Any]:
    """
    Get metadata for a dataset including labels and location.
    
    Args:
        project_id: GCP project ID
        dataset_id: BigQuery dataset ID
        
    Returns:
        Dictionary with 'labels' and 'location' keys
    """
    try:
        dataset_ref = f"{project_id}.{dataset_id}"
        dataset = self.client.get_dataset(dataset_ref)
        return {
            "labels": dict(dataset.labels) if dataset.labels else {},
            "location": dataset.location
        }
    except Exception as e:
        logger.debug(f"Could not get metadata for dataset {dataset_id}: {e}")
        return {"labels": {}, "location": "UNKNOWN"}
```

#### 3c. Update _scan_project to filter by region (around line 220)

```python
# Get dataset metadata (labels and location)
dataset_metadata = self._get_dataset_metadata(project_id, dataset_id)
dataset_labels = dataset_metadata["labels"]
dataset_location = dataset_metadata["location"]

# NEW: Skip datasets not in discovery region
if self.discovery_region and dataset_location != self.discovery_region:
    logger.info(
        f"Skipping dataset {dataset_id} - location '{dataset_location}' "
        f"does not match discovery region '{self.discovery_region}'"
    )
    continue

# Check if dataset should be filtered by label
dataset_filtered = self._should_filter_by_label(dataset_labels)
# ... rest of existing code ...

# Pass location to _scan_dataset
dataset_assets = self._scan_dataset(
    project_id,
    dataset_id,
    include_views=include_views,
    dataset_labels=dataset_labels,
    dataset_location=dataset_location  # NEW
)
```

#### 3d. Update _scan_dataset signature (line 257)

```python
def _scan_dataset(
    self,
    project_id: str,
    dataset_id: str,
    include_views: bool = True,
    dataset_labels: Optional[Dict[str, str]] = None,
    dataset_location: str = "UNKNOWN",  # NEW
) -> List[Dict[str, Any]]:
```

Update docstring to include dataset_location parameter.

#### 3e. Update _collect_table_metadata signature (line 394)

```python
def _collect_table_metadata(
    self,
    project_id: str,
    dataset_id: str,
    table_id: str,
    dataset_location: str = "UNKNOWN",  # NEW
) -> Optional[Dict[str, Any]]:
```

#### 3f. Pass dataset_location when calling _collect_table_metadata (around line 350)

```python
executor.submit(
    self._collect_table_metadata,
    project_id,
    dataset_id,
    table_ref.table_id,
    dataset_location  # NEW
)
```

#### 3g. Add dataset_region to asset dict (around line 574)

```python
asset = {
    # Core metadata
    "project_id": project_id,
    "dataset_id": dataset_id,
    "table_id": table_id,
    "dataset_region": dataset_location,  # NEW FIELD
    "description": table_metadata.get("description", ""),
    # ... rest of fields
}
```

### 4. Backfill Existing Data

**Create script: `data-discovery-agent/scripts/backfill_dataset_region.py`**

```python
"""
Backfill dataset_region for existing discovered_assets records.
"""
from google.cloud import bigquery
import os
from dotenv import load_dotenv

load_dotenv()

project_id = os.getenv("GCP_PROJECT_ID")
dataset_id = os.getenv("BQ_DATASET", "data_discovery")
table_id = os.getenv("BQ_TABLE", "discovered_assets")
backfill_region = "us-central1"  # All existing data is in us-central1

client = bigquery.Client(project=project_id)

query = f"""
UPDATE `{project_id}.{dataset_id}.{table_id}`
SET dataset_region = '{backfill_region}'
WHERE dataset_region IS NULL
"""

print(f"Backfilling dataset_region='{backfill_region}' for {project_id}.{dataset_id}.{table_id}")
print("This will update all records with NULL dataset_region")
confirm = input("Continue? (yes/no): ")

if confirm.lower() == 'yes':
    job = client.query(query)
    result = job.result()
    print(f"✓ Updated {job.num_dml_affected_rows} rows")
else:
    print("Cancelled")
```

### 5. Update Environment Variable Documentation

**File: `data-discovery-agent/.env.example`**

Add after existing BQ_LOCATION:

```bash
# BigQuery region filter for data discovery
# If set, only datasets in this region will be discovered
# Examples: 'US', 'us-central1', 'EU', 'europe-west1'
# Leave empty to discover all regions
GCP_DISCOVERY_REGION=us-central1
```

## Key Design Points

1. **Collection-time filtering**: Datasets are filtered **during collection** in `_scan_project`, not at query time
2. **No MCP changes needed**: No region parameter in MCP tools or search requests
3. **No Vertex AI Search filtering**: The datastore only contains tables from the configured region
4. **Automatic**: Set `GCP_DISCOVERY_REGION` once, all future collections respect it
5. **Flexible**: Leave `GCP_DISCOVERY_REGION` empty to discover all regions (existing behavior)

## Testing Checklist

1. Set `GCP_DISCOVERY_REGION=us-central1` in `.env`
2. Run data discovery collection
3. Verify only datasets from `us-central1` are discovered (check logs)
4. Verify `dataset_region` field is populated in BigQuery table
5. Test with empty `GCP_DISCOVERY_REGION` - should discover all regions
6. Run backfill script to update existing records

## Files to Modify

1. `data-discovery-agent/src/data_discovery_agent/writers/bigquery_writer.py` - Add dataset_region field
2. `data-discovery-agent/src/data_discovery_agent/schemas/asset_schema.py` - Add to TypedDict
3. `data-discovery-agent/src/data_discovery_agent/models/search_models.py` - Add to AssetMetadata
4. `data-discovery-agent/src/data_discovery_agent/collectors/bigquery_collector.py` - Add region filtering logic
5. `data-discovery-agent/.env.example` - Document GCP_DISCOVERY_REGION
6. `data-discovery-agent/scripts/backfill_dataset_region.py` - Create backfill script (new file)

### To-dos

- [ ] Add dataset_region field to BigQuery writer schema
- [ ] Add dataset_region and region filter to data models (asset_schema.py, search_models.py)
- [ ] Modify BigQuery collector to capture dataset location and add to asset metadata
- [ ] Add region filter support to Vertex AI Search client
- [ ] Add region filter to query builder patterns and filter expression
- [ ] Add region parameter to MCP tool input schemas
- [ ] Add --region flag and pass region to discovery calls in integrated_workflow_example.py
- [ ] Create and run backfill script to set dataset_region='us-central1' for existing records
- [ ] Document BQ_LOCATION in .env.example files
- [ ] Test region filtering end-to-end from discovery to query generation