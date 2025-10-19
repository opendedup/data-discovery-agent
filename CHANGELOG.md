# Changelog

## 2025-10-18 - Enhanced JSONL Content and Auto-Indexing

### Summary
Enhanced the BigQuery metadata collection to generate complete, searchable JSONL documents for Vertex AI Search. The JSONL now includes full schema, data quality metrics, column profiles, and data lineage. Additionally, implemented automatic re-indexing after each collection.

### Key Changes

#### 1. Enhanced JSONL Content (`metadata_formatter.py`)

**What Changed:**
- Modified `_build_content_text()` to include **complete metadata** instead of truncated summaries
- Now includes:
  - ✅ **Full schema** (all columns, not limited to 20)
  - ✅ **Data quality metrics** (null statistics for top 10 columns by null %)
  - ✅ **Column profiles**:
    - Numeric: min/max/avg/distinct
    - String: min_length/max_length/distinct
    - Other: distinct/null% (for TIMESTAMP, etc.)
  - ✅ **Complete data lineage** (all upstream/downstream tables)
  - ✅ **Governance metadata** (PII/PHI indicators, labels, tags)

**Why:**
- Previous JSONL was truncated (only 20 columns shown)
- Missing data quality and profiling information
- Not fully searchable for semantic queries

**Example Output:**
```
## Data Quality

### Null Statistics (Top 10 columns by null %)
- **home_team_wins**: 100.0% null
- **attendance**: 100.0% null
...

### Column Profiles

**Numeric Columns:**
- **home_team_id**: min=1610612737, max=1610612766, avg=1610612751.50, distinct=29
...

**String Columns:**
- **game_id**: length=10-10, distinct=6,001
...
```

#### 2. Extended Metadata Collection (`bigquery_collector.py`)

**What Changed:**
- Modified `_collect_table_metadata()` to fetch **extended metadata before formatting JSONL**
- Now fetches during collection (not just for Markdown):
  - Quality stats (`_get_quality_stats()`)
  - Column profiles (`_get_column_profiles()`) with Dataplex or SQL fallback
  - Data lineage (`_get_lineage()`)
- Passes all metadata to `MetadataFormatter.format_bigquery_table()`
- Added `column_count` to table metadata

**Why:**
- Previously, extended metadata was only fetched for Markdown reports
- JSONL content was incomplete and less searchable
- Now metadata is fetched once and used for both JSONL and Markdown

#### 3. Document Upsert for Re-Indexing (`vertex_search_client.py`)

**What Changed:**
- Added `update_document()` method to update existing documents
- Added `upsert_document()` method to create or update (intelligent upsert)
- Modified `create_documents_from_jsonl_file()` to:
  - Use `upsert=True` by default
  - Track "created" and "updated" documents separately
  - Re-index existing documents instead of skipping them

**Why:**
- Previously, documents were skipped if they already existed (409 conflict)
- Re-collection didn't update the search index
- Now every collection automatically updates Vertex AI Search with latest metadata

**Example Output:**
```
✓ Document indexing complete!
  Total:   2
  Created: 0
  Updated: 2  <-- Documents are now updated, not skipped
  Failed:  0
  Skipped: 0
```

#### 4. Auto-Import by Default (`collect-bigquery-metadata.py`)

**What Changed:**
- Changed `--import` flag to be **enabled by default**
- Added `--skip-import` flag to disable auto-import
- Updated script docstring with enhanced features
- Updated progress messages to reflect upsert behavior

**Why:**
- Previously, users had to manually trigger import with `--import` flag
- Easy to forget to re-index after collection
- Now every collection automatically updates Vertex AI Search

**Usage:**
```bash
# Default: collect and auto-import
poetry run python scripts/collect-bigquery-metadata.py

# Skip import (for testing)
poetry run python scripts/collect-bigquery-metadata.py --skip-import
```

#### 5. Bug Fixes

**Fixed:** Format specifier error in `metadata_formatter.py`
- Error: `Invalid format specifier '.2f if isinstance(avg_val, (int, float)) else avg_val'`
- Fix: Moved conditional logic outside f-string format specifier

### Impact

#### Before
- ❌ JSONL truncated (only 20 columns)
- ❌ No data quality metrics in search
- ❌ No column profiles in search
- ❌ Documents skipped if already exist
- ❌ Manual import required

#### After
- ✅ Complete JSONL (all columns)
- ✅ Full data quality metrics searchable
- ✅ Column profiles searchable
- ✅ Documents automatically updated
- ✅ Auto-import after every collection

### Search Improvements

**Example Queries Now Work:**
```bash
# Find tables with null values
poetry run python scripts/test-search.py "null values"

# Find tables with specific columns
poetry run python scripts/test-search.py "attendance"

# Find tables with data quality issues
poetry run python scripts/test-search.py "100% null"

# Find numeric columns with specific ranges
poetry run python scripts/test-search.py "min max avg"
```

### Testing

Tested with:
- ✅ Single table collection with Dataplex profiling
- ✅ Multi-table collection with auto-import
- ✅ Document upsert (update existing documents)
- ✅ Search for data quality metrics
- ✅ Search for specific columns

### Files Modified

1. `src/data_discovery_agent/search/metadata_formatter.py`
   - Enhanced `_build_content_text()` method

2. `src/data_discovery_agent/collectors/bigquery_collector.py`
   - Modified `_collect_table_metadata()` to fetch extended metadata

3. `src/data_discovery_agent/clients/vertex_search_client.py`
   - Added `update_document()` method
   - Added `upsert_document()` method
   - Modified `create_documents_from_jsonl_file()` for upsert support

4. `scripts/collect-bigquery-metadata.py`
   - Changed default behavior to auto-import
   - Added `--skip-import` flag
   - Updated output messages

### Next Steps

1. **Wait 2-10 minutes** after collection for Vertex AI Search to complete indexing
2. **Test search** with various queries to verify enhanced searchability
3. **View Markdown reports** in GCS for detailed human-readable documentation

### Configuration

**Recommended Collection Command:**
```bash
poetry run python scripts/collect-bigquery-metadata.py \
  --use-dataplex \
  --projects proj1 proj2 proj3
```

**For Testing (no import):**
```bash
poetry run python scripts/collect-bigquery-metadata.py \
  --max-tables 10 \
  --skip-import
```

### Notes

- Dataplex profiling provides richer data quality metrics
- SQL-based profiling is used as fallback if Dataplex is not available
- Document upsert ensures latest metadata is always searchable
- JSONL files are stored in GCS for audit and backup

---

## Previous Changes

See git history for previous changes.

