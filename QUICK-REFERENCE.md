# Quick Reference Guide

## ✅ What Changed

Your BigQuery metadata collection now:

1. **Generates complete JSONL** with full schema, data quality metrics, column profiles, and lineage
2. **Automatically re-indexes** Vertex AI Search after each collection
3. **Updates existing documents** instead of skipping them

## 🚀 How to Use

### Basic Collection (with auto-import)
```bash
poetry run python scripts/collect-bigquery-metadata.py --use-dataplex
```

This will:
- ✅ Collect metadata from all tables
- ✅ Generate complete JSONL
- ✅ Upload to GCS
- ✅ Generate Markdown reports
- ✅ **Automatically update Vertex AI Search**

### Test with Limited Tables
```bash
poetry run python scripts/collect-bigquery-metadata.py --max-tables 5 --use-dataplex
```

### Skip Auto-Import (for testing)
```bash
poetry run python scripts/collect-bigquery-metadata.py --skip-import
```

### Collect from Specific Projects
```bash
poetry run python scripts/collect-bigquery-metadata.py \
  --projects proj1 proj2 proj3 \
  --use-dataplex
```

## 🔍 Testing Search

### Test Basic Search
```bash
poetry run python scripts/test-search.py "game"
```

### Search for Columns
```bash
poetry run python scripts/test-search.py "attendance"
```

### Search for Data Quality Issues
```bash
poetry run python scripts/test-search.py "null values"
```

### Search for PII Data
```bash
poetry run python scripts/test-search.py "PII"
```

## 📊 What's in the JSONL Now

### Before
```
## Schema
- game_id (STRING, NULLABLE): NBA game ID
- game_date (STRING, NULLABLE): Date the game was played
... and 28 more columns  <-- TRUNCATED!
```

### After
```
## Schema
- game_id (STRING, NULLABLE): NBA game ID
- game_date (STRING, NULLABLE): Date the game was played
- game_status_id (INTEGER, NULLABLE): Game status ID
... ALL 30 columns listed

## Data Quality

### Null Statistics (Top 10 columns by null %)
- **home_team_wins**: 100.0% null
- **attendance**: 100.0% null

### Column Profiles

**Numeric Columns:**
- **home_team_id**: min=1610612737, max=1610612766, avg=1610612751.50, distinct=29

**String Columns:**
- **game_id**: length=10-10, distinct=6,001
```

## 📈 Output Example

```
======================================================================
BigQuery Metadata Collection - Phase 2.1
======================================================================

Project: lennyisagoodboy
Target projects: ['lennyisagoodboy']
Auto-import to Vertex AI Search: enabled  <-- NOW ENABLED BY DEFAULT

Step 1: Collecting BigQuery metadata...
----------------------------------------------------------------------
✓ Collected 2 assets

Step 2: Exporting to JSONL...
----------------------------------------------------------------------
✓ Exported 2 documents to /tmp/bigquery_metadata_20251018_233410.jsonl

Step 3: Uploading JSONL to GCS...
----------------------------------------------------------------------
✓ Uploaded JSONL to gs://lennyisagoodboy-data-discovery-jsonl/...

Step 3.5: Generating Markdown reports...
----------------------------------------------------------------------
✓ Generated 2 Markdown reports

Step 4: Creating documents in Vertex AI Search...
----------------------------------------------------------------------
✓ Document indexing complete!
  Total:   2
  Created: 0
  Updated: 2  <-- DOCUMENTS ARE NOW UPDATED, NOT SKIPPED!
  Failed:  0
  Skipped: 0
```

## ⏱️ Timing

- **Collection:** ~2-5 seconds per table (with Dataplex profiling)
- **JSONL Export:** ~1 second
- **GCS Upload:** ~2-3 seconds
- **Vertex AI Indexing:** 2-10 minutes after upload
- **Markdown Generation:** ~2-3 seconds per table

## 🎯 Key Benefits

1. **Complete Searchability**
   - Search by column names
   - Search by data types
   - Search by descriptions
   - Search by null percentages
   - Search by column statistics

2. **Always Up-to-Date**
   - Every collection updates Vertex AI Search
   - No manual import required
   - Latest metadata always searchable

3. **Rich Metadata**
   - Full schema (all columns)
   - Data quality metrics
   - Column profiles (min/max/avg/distinct)
   - Data lineage
   - PII/PHI indicators

## 🔧 Troubleshooting

### Documents Not Updating?
Wait 2-10 minutes for Vertex AI Search to complete indexing.

### Search Not Finding Results?
```bash
# Check if documents exist
poetry run python scripts/test-search.py "game"
```

### Want to See Raw JSONL?
```bash
cat /tmp/bigquery_metadata_*.jsonl | jq -r '.content.text' | head -100
```

### Disable Dataplex Profiling?
Remove `--use-dataplex` flag to use SQL-based profiling (faster but less detailed).

## 📚 Additional Resources

- **Changelog:** See `CHANGELOG.md` for detailed changes
- **README:** See `README.md` for full documentation
- **Dataplex Scheduling:** See `terraform/dataplex-profiling/SCHEDULING.md`

## 🎉 Summary

Your data discovery system is now:
- ✅ Generating complete, searchable metadata
- ✅ Automatically re-indexing after every collection
- ✅ Updating documents instead of skipping them
- ✅ Ready for production use!

