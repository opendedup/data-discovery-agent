# Sample Values from Dataplex - Performance Improvement

## Summary

Updated the BigQuery metadata collection to retrieve **sample values directly from Dataplex Data Profile Scan results** instead of running separate SQL queries for each column.

## What Changed

### 1. Dataplex Profiler Enhancement (`dataplex_profiler.py`)

**Added:**
- Extracts `sample_values` from Dataplex `top_n_values` (most common values)
- New method: `get_sample_values_from_profile()` to retrieve sample values efficiently

**Code:**
```python
# Extract sample values (just the values, not counts) for easy display
col_data["sample_values"] = [
    str(v.value) for v in profile_info.top_n_values[:3]  # Top 3 for samples
]
```

### 2. BigQuery Collector Update (`bigquery_collector.py`)

**Changed:**
- `_get_sample_values()` is now a **FALLBACK method**
- Tries Dataplex sample values first (when `--use-dataplex` is enabled)
- Only runs SQL queries if Dataplex is not available

**Logic:**
```python
# Get sample values for columns
# Use Dataplex samples if available (more efficient than SQL queries)
sample_values = {}
if self.dataplex_profiler:
    sample_values = self.dataplex_profiler.get_sample_values_from_profile(
        dataset_id, table_id
    )
    if sample_values:
        logger.info(f"Using Dataplex sample values for {table_id}")

# Fall back to SQL-based sampling if no Dataplex samples
if not sample_values and table.schema:
    logger.info(f"Fetching sample values via SQL for {table_id}")
    sample_values = self._get_sample_values(...)
```

## Performance Impact

### Before (SQL-based)
- **30+ SQL queries per table** (one per column)
- Each query: `SELECT DISTINCT column LIMIT 3`
- Slow for large tables
- Higher BigQuery costs

### After (Dataplex-based)
- **0 additional queries** (uses existing Dataplex profile)
- Sample values already collected during profiling
- Much faster collection
- No additional BigQuery costs

### Example Log Output

**With Dataplex (NEW):**
```
Using Dataplex sample values for game_info (10 columns)
Using Dataplex sample values for game_line_scores (4 columns)
Using Dataplex sample values for game_stats (67 columns)
```

**Without Dataplex (FALLBACK):**
```
Fetching sample values via SQL for table_name
```

## Sample Values in Output

### JSONL (for Vertex AI Search)
```
## Schema
- **game_id** (STRING, NULLABLE): NBA game ID — Examples: '0022400531', '0022400530', '0022400529'
- **game_date** (STRING, NULLABLE): Date the game was played — Examples: '2024-04-14T00:00:00', '2024-04-12T00:00:00'
- **season** (STRING, NULLABLE): NBA season — Examples: '2023', '2024', '2022'
```

### Markdown Reports
```
| Column | Type | Mode | Description | Sample Values |
|--------|------|------|-------------|---------------|
| game_id | STRING | NULLABLE | NBA game ID | 0022400531, 0022400530, 0022400529 |
| game_date | STRING | NULLABLE | Date the game was played | 2024-04-14T00:00:00, 2024-04-12T00:00:00 |
| season | STRING | NULLABLE | NBA season | 2023, 2024, 2022 |
```

## Dataplex Top N Values

Dataplex provides the **most common values** in each column, which are perfect for understanding data distribution:

- **Numeric columns:** Most frequent values (e.g., common IDs, status codes)
- **String columns:** Most frequent values (e.g., common categories, states)
- **Timestamp columns:** Most common timestamps
- **Empty for NULL columns:** Columns with 100% null show no samples

## Files Modified

1. **`src/data_discovery_agent/collectors/dataplex_profiler.py`**
   - Added `sample_values` extraction from `top_n_values`
   - Added `get_sample_values_from_profile()` method

2. **`src/data_discovery_agent/collectors/bigquery_collector.py`**
   - Updated `_collect_table_metadata()` to use Dataplex samples first
   - Updated `_get_sample_values()` docstring to clarify it's a fallback

## Usage

### With Dataplex (Recommended - Fast)
```bash
poetry run python scripts/collect-bigquery-metadata.py --use-dataplex
```

### Without Dataplex (Slower - SQL fallback)
```bash
poetry run python scripts/collect-bigquery-metadata.py
```

## Benefits

1. **Performance:** No additional SQL queries when using Dataplex
2. **Cost:** Reduced BigQuery query costs
3. **Quality:** Sample values are the most common values (better representation)
4. **Consistency:** All metadata from single Dataplex scan
5. **Searchability:** Sample values are indexed in Vertex AI Search

## Example: Search for Specific Values

With sample values indexed, you can now search for:
- **"game_id 0022400531"** - finds tables with that specific value
- **"season 2024"** - finds tables with 2024 season data
- **"Final status"** - finds tables with "Final" status values

## Next Steps

1. Run collection with `--use-dataplex` to get sample values from Dataplex
2. Sample values will appear in both JSONL and Markdown reports
3. Search functionality will include sample values for better discoverability

---

## Technical Details

### Dataplex `top_n_values` Structure

```python
# From Dataplex profile result
profile_info.top_n_values = [
    TopNValue(value="2024", count=1500),
    TopNValue(value="2023", count=1200),
    TopNValue(value="2022", count=800),
    ...
]

# Extracted as sample_values
sample_values = ["2024", "2023", "2022"]  # Top 3
```

### Benefits of Top N Values

- **Representative:** Shows most common data patterns
- **Efficient:** Already collected during profiling
- **Accurate:** Based on actual data distribution
- **Contextual:** Helps understand data without querying

## Testing

Verified:
- ✅ Dataplex sample values extracted correctly
- ✅ Sample values appear in JSONL content
- ✅ Sample values appear in Markdown reports
- ✅ SQL fallback works when Dataplex is not available
- ✅ Logs show "Using Dataplex sample values" for all tables

## Comparison

| Aspect | SQL-based Sampling | Dataplex-based Sampling |
|--------|-------------------|------------------------|
| **Speed** | Slow (30+ queries) | Fast (0 queries) |
| **Cost** | High (per-column queries) | Free (included in profile) |
| **Values** | Random distinct values | Most common values |
| **Accuracy** | Sample of 3 | Top 3 by frequency |
| **Availability** | Always | Requires Dataplex scan |

## Conclusion

By using Dataplex sample values instead of SQL queries, we've significantly improved performance and reduced costs while providing more meaningful sample data (most common values vs. random values).

