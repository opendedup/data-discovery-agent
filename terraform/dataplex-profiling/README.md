# Dataplex Data Profile Scans

This directory contains Terraform configuration to create and manage Dataplex Data Profile Scans for BigQuery tables.

## Overview

Dataplex Data Profile Scans provide comprehensive table and column profiling including:
- Column-level statistics (min, max, mean, median, stddev, quartiles)
- Data quality metrics (null ratios, distinct counts)
- String profiling (min/max/avg length)
- Top N values per column
- Built-in PII detection

Reference: https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/dataplex_datascan

## Setup

1. **Copy the example variables:**
   ```bash
   cd terraform/dataplex-profiling
   cp terraform.tfvars.example terraform.tfvars
   ```

2. **Edit terraform.tfvars:**
   ```hcl
   project_id = "lennyisagoodboy"
   location   = "us-central1"
   
   tables_to_profile = [
     {
       dataset_id = "lfndata"
       table_id   = "post_game_summaries"
     },
   ]
   ```

3. **Initialize Terraform:**
   ```bash
   terraform init
   ```

4. **Review the plan:**
   ```bash
   terraform plan
   ```

5. **Apply the configuration:**
   ```bash
   terraform apply
   ```

## Running Scans

### Option 1: Automatic (Scheduled)

Scans are configured to run daily at 2 AM UTC automatically.

### Option 2: On-Demand (Manual)

Run a scan immediately using gcloud:

```bash
# Get the scan name from terraform output
terraform output profile_scan_names

# Run a specific scan
gcloud dataplex datascans run \
  projects/YOUR_PROJECT/locations/us-central1/dataScans/profile-lfndata-post_game_summaries
```

### Option 3: On-Demand (Python API)

Use the DataplexProfiler helper:

```python
from data_discovery_agent.collectors.dataplex_profiler import DataplexProfiler

profiler = DataplexProfiler(project_id="lennyisagoodboy", location="us-central1")

# Run a scan
scan_name = "projects/lennyisagoodboy/locations/us-central1/dataScans/profile-lfndata-post_game_summaries"
job_name = profiler.run_profile_scan(scan_name)
print(f"Started scan: {job_name}")
```

## Retrieving Scan Results

Once a scan has run successfully, retrieve the results:

```python
from data_discovery_agent.collectors.dataplex_profiler import DataplexProfiler

profiler = DataplexProfiler(project_id="lennyisagoodboy", location="us-central1")

# Get profile results
profile = profiler.get_profile_scan_for_table(
    dataset_id="lfndata",
    table_id="post_game_summaries"
)

if profile:
    print(f"Row count: {profile['row_count']}")
    print(f"Columns profiled: {len(profile['columns'])}")
    
    for col_name, stats in profile['columns'].items():
        print(f"  {col_name}: null_ratio={stats['null_ratio']:.2%}")
```

## Integration with Collector

To use Dataplex profiling in the metadata collector:

```bash
poetry run python scripts/collect-bigquery-metadata.py \
  --use-dataplex \
  --dataplex-location us-central1
```

The collector will:
1. Check for existing Dataplex profile scan results
2. Use them if available (richer profiling)
3. Fall back to SQL-based profiling if not available

## Cost Considerations

Dataplex Data Profile Scans pricing:
- **Data scanned**: ~$0.04 per GB scanned
- **Storage**: Minimal (only metadata stored)
- **Scheduled runs**: Consider sampling_percent < 100 for large tables

To reduce costs:
- Use `sampling_percent = 10.0` for large tables (samples 10% of rows)
- Add `row_filter` to exclude certain data
- Reduce scan frequency in `execution_spec.trigger.schedule`

## Cleanup

To remove all profile scans:

```bash
terraform destroy
```

## Troubleshooting

### "API not enabled" error

Enable the Dataplex API:
```bash
gcloud services enable dataplex.googleapis.com --project=YOUR_PROJECT
```

### "Permission denied" error

Ensure your service account has these IAM roles:
- `roles/dataplex.admin` or `roles/dataplex.dataScanEditor`
- `roles/bigquery.dataViewer` (to read BigQuery tables)

### Scan failed

Check scan job status:
```bash
gcloud dataplex datascans jobs list \
  --project=YOUR_PROJECT \
  --location=us-central1 \
  --datascan=profile-DATASET-TABLE
```

View job details:
```bash
gcloud dataplex datascans jobs describe JOB_ID \
  --project=YOUR_PROJECT \
  --location=us-central1 \
  --datascan=profile-DATASET-TABLE
```

