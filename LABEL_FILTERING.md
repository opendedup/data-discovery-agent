# Label-Based Discovery Filtering

This document describes the label-based filtering feature that allows you to control which BigQuery datasets and tables are included in the data discovery scan.

## Overview

The data discovery agent now supports filtering datasets and tables based on BigQuery labels. This allows you to explicitly exclude or include resources during the discovery process using a hierarchical filtering approach.

## How It Works

### Filtering Logic

The filtering uses a **configurable label key** (default: `ignore-gmcp-discovery-scan`) with hierarchical logic where table-level labels override dataset-level labels:

1. **Dataset with label = `true`**: Skip all tables in that dataset UNLESS a table has the label set to `false`
2. **Dataset with label = `false` or missing**: Include tables (unless a specific table has label = `true`)
3. **Table with label = `true`**: Skip that table (even if dataset allows it)
4. **Table with label = `false`**: Include that table (even if dataset blocks it)

### Label Behavior

- **Label Key**: Case-sensitive (default: `ignore-gmcp-discovery-scan`)
- **Label Value**: Case-insensitive (`true`, `True`, `TRUE` all work the same)
- **Default Behavior**: Resources without the label are included by default

## Configuration

### Environment Variable

Set the `DISCOVERY_FILTER_LABEL_KEY` environment variable to customize the label key:

```bash
# Default value (no need to set if using default)
export DISCOVERY_FILTER_LABEL_KEY=ignore-gmcp-discovery-scan

# Custom label key
export DISCOVERY_FILTER_LABEL_KEY=my-custom-filter-label
```

### BigQueryCollector

When using the `BigQueryCollector` directly in Python:

```python
from data_discovery_agent.collectors import BigQueryCollector

# Using default label key
collector = BigQueryCollector(
    project_id="my-project",
    filter_label_key="ignore-gmcp-discovery-scan"  # This is the default
)

# Using custom label key
collector = BigQueryCollector(
    project_id="my-project",
    filter_label_key="my-custom-filter"
)

assets = collector.collect_all()
```

### Bulk Dataplex Script

When using the bulk Dataplex scan creation script:

```bash
# Using default label key
poetry run python scripts/create-dataplex-scans-bulk.py \
  --project my-project

# Using custom label key
poetry run python scripts/create-dataplex-scans-bulk.py \
  --project my-project \
  --filter-label-key my-custom-filter
```

### Airflow/Composer

The Airflow tasks automatically read from the `DISCOVERY_FILTER_LABEL_KEY` environment variable. Set this in your Composer environment variables or Secret Manager.

You can also override it via `dag_run.conf` for manual runs:

```python
{
  "collector_args": {
    "filter_label_key": "my-custom-filter"
  }
}
```

## Usage Examples

### Example 1: Exclude an Entire Dataset

To exclude all tables in a dataset from discovery:

```bash
# Set label on dataset
bq update --set_label ignore-gmcp-discovery-scan:true \
  my-project:my_dataset
```

Result: All tables in `my_dataset` will be skipped during discovery.

### Example 2: Exclude Dataset But Include Specific Table

To exclude a dataset but include one specific table:

```bash
# Set label on dataset (exclude all)
bq update --set_label ignore-gmcp-discovery-scan:true \
  my-project:sensitive_dataset

# Set label on specific table (include this one)
bq update --set_label ignore-gmcp-discovery-scan:false \
  my-project:sensitive_dataset.public_summary_table
```

Result:
- `sensitive_dataset` is marked for exclusion
- All tables in `sensitive_dataset` are skipped EXCEPT `public_summary_table`
- `public_summary_table` explicitly overrides the dataset-level setting

### Example 3: Include Dataset But Exclude Specific Tables

To include a dataset but exclude specific sensitive tables:

```bash
# Dataset has no label (included by default)

# Set label on specific tables to exclude them
bq update --set_label ignore-gmcp-discovery-scan:true \
  my-project:analytics.pii_data

bq update --set_label ignore-gmcp-discovery-scan:true \
  my-project:analytics.internal_metrics
```

Result:
- `analytics` dataset is scanned
- Most tables in `analytics` are included
- `pii_data` and `internal_metrics` are explicitly excluded

### Example 4: Remove Filter Label

To remove the filtering label and restore default behavior:

```bash
# Remove label from dataset
bq update --remove_label ignore-gmcp-discovery-scan \
  my-project:my_dataset

# Remove label from table
bq update --remove_label ignore-gmcp-discovery-scan \
  my-project:my_dataset.my_table
```

## Monitoring and Statistics

The collector tracks filtering statistics:

```python
collector = BigQueryCollector(project_id="my-project")
assets = collector.collect_all()

stats = collector.get_stats()
print(f"Tables filtered by label: {stats['tables_filtered_by_label']}")
```

The statistics will show:
- `tables_filtered_by_label`: Number of tables skipped due to label filtering
- `tables_scanned`: Number of tables successfully scanned
- `datasets_scanned`: Number of datasets scanned

## Best Practices

1. **Use at Dataset Level for Broad Exclusions**: If you want to exclude many tables, apply the label at the dataset level rather than individual tables.

2. **Use at Table Level for Specific Exceptions**: Use table-level labels to create exceptions to dataset-level rules.

3. **Document Your Filtering Strategy**: Keep track of which datasets and tables have filtering labels and why.

4. **Test Before Production**: Use the `--dry-run` flag with the bulk script to preview which tables will be discovered:
   ```bash
   poetry run python scripts/create-dataplex-scans-bulk.py \
     --project my-project \
     --dry-run
   ```

5. **Regular Audits**: Periodically review your filtering labels to ensure they still reflect your current requirements.

## Troubleshooting

### Tables Not Being Discovered

If tables are unexpectedly missing from discovery:

1. Check if the dataset has a filtering label:
   ```bash
   bq show --format=prettyjson my-project:my_dataset | grep -A 2 labels
   ```

2. Check if the specific table has a filtering label:
   ```bash
   bq show --format=prettyjson my-project:my_dataset.my_table | grep -A 2 labels
   ```

3. Check the filtering statistics in the collector output to see how many tables were filtered.

### Case Sensitivity Issues

Remember:
- **Label key is case-sensitive**: `ignore-gmcp-discovery-scan` ≠ `IGNORE-GMCP-DISCOVERY-SCAN`
- **Label value is case-insensitive**: `true` = `True` = `TRUE` = `tRuE`

## Implementation Details

### Files Modified

- `src/data_discovery_agent/collectors/bigquery_collector.py`: Core filtering logic
- `scripts/create-dataplex-scans-bulk.py`: Bulk scan script with filtering
- `src/data_discovery_agent/orchestration/tasks.py`: Airflow task configuration
- `tests/unit/collectors/test_label_filtering.py`: Comprehensive test coverage

### Methods Added

- `BigQueryCollector._should_filter_by_label()`: Check if resource should be filtered
- `BigQueryCollector._get_dataset_labels()`: Retrieve labels from a dataset
- Modified `BigQueryCollector._scan_dataset()`: Apply hierarchical filtering logic

## Future Enhancements

Potential future improvements to this feature:

- Support for pattern matching in label values (e.g., `env:prod*` matches `env:prod-us`, `env:prod-eu`)
- Support for multiple label keys (AND/OR logic)
- UI integration for managing filter labels
- Reporting/dashboard for filtered resources

