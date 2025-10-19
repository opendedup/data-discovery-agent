# Gemini-Generated Table Descriptions

## Overview

The BigQuery metadata collector now uses **Gemini 2.5 Flash** to automatically generate descriptions for tables that don't have one. This ensures all tables in your discovery system have meaningful, context-aware descriptions.

## How It Works

1. **Detection**: When collecting metadata, the system checks if a table has a description
2. **Context Building**: If missing, it gathers rich context:
   - Full schema with column names, types, and descriptions
   - Sample values (top 3 most common per column from Dataplex)
   - Column profiles (min/max/avg for numeric, length for strings)
   - Table statistics (row count, size)
3. **Generation**: Sends context to Gemini 2.5 Flash with specific instructions
4. **Integration**: Generated description is added to the table metadata

## Setup

### 1. Get Gemini API Key

Get your API key from [Google AI Studio](https://aistudio.google.com/app/apikey)

### 2. Set Environment Variable

```bash
export GEMINI_API_KEY="your-api-key-here"
```

Or add to `.bashrc`:
```bash
echo 'export GEMINI_API_KEY="your-api-key-here"' >> ~/.bashrc
source ~/.bashrc
```

### 3. Run Collection

```bash
# With Gemini enabled (default)
poetry run python scripts/collect-bigquery-metadata.py --use-dataplex

# Skip Gemini if not needed
poetry run python scripts/collect-bigquery-metadata.py --skip-gemini

# Provide API key directly
poetry run python scripts/collect-bigquery-metadata.py --gemini-api-key "your-key"
```

## Example Output

### Input Context to Gemini

```
**Table Name:** lennyisagoodboy.abndata.game_info

**Table Statistics:**
- Rows: 7,237
- Size: 0.00 GB

**Schema:**
- **game_id** (STRING, NULLABLE): NBA game ID [Examples: '0022400531', '0022400530', '0022400529']
- **game_date** (STRING, NULLABLE): Date the game was played [Examples: '2024-04-14T00:00:00', ...]
- **season** (STRING, NULLABLE): NBA season [Examples: '2023', '2024', '2022']
- **home_team_id** (INTEGER, NULLABLE): NBA home team ID [Examples: '1610612749', ...]
... and 25 more columns

**Data Characteristics:**
- 7 numeric columns
- 20 string columns
- 3 other columns (timestamp, etc.)
```

### Generated Description

```
Contains NBA game information including scheduled and completed games with details about 
participating teams, game status, venue, attendance, broadcasters, and series statistics. 
Tracks head-to-head matchups across regular season and playoffs with historical context 
from previous games between teams.
```

## Features

### Context-Aware Generation

Gemini analyzes:
- ✅ **Column names and types**: Understands data structure
- ✅ **Sample values**: Sees actual data patterns
- ✅ **Column descriptions**: Leverages existing documentation
- ✅ **Statistical profiles**: Understands data distribution
- ✅ **Table size**: Considers scale and importance

### Quality Instructions

The prompt instructs Gemini to:
- ✅ Explain what data the table contains
- ✅ Identify the business domain or use case
- ✅ Highlight key columns or relationships
- ✅ Use professional, technical language
- ❌ Avoid starting with "This table..." or "The table..."
- ❌ Don't include column counts or technical statistics
- ❌ No placeholder text or generic descriptions

### Model Configuration

- **Model**: `gemini-2.0-flash-exp` (Gemini 2.5 Flash)
- **Speed**: Fast (~1-2 seconds per table)
- **Cost**: Very low ($0.00015 per 1000 tokens)
- **Quality**: High-quality, context-aware descriptions

## Usage Examples

### Basic Collection with Gemini

```bash
poetry run python scripts/collect-bigquery-metadata.py \
  --use-dataplex \
  --projects my-project
```

### Generate Descriptions for Specific Dataset

```bash
poetry run python scripts/collect-bigquery-metadata.py \
  --use-dataplex \
  --projects my-project \
  --max-tables 10
```

### Disable Gemini (Keep Existing Behavior)

```bash
poetry run python scripts/collect-bigquery-metadata.py \
  --use-dataplex \
  --skip-gemini
```

## Output

### Collection Stats

```
Statistics:
  Projects scanned:         1
  Datasets scanned:         2
  Tables scanned:           34
  Assets exported:          34
  Descriptions generated:   12  ← NEW!
  Errors:                   0
```

### Log Output

```
INFO - Generating description for game_info using Gemini...
INFO - ✓ Generated description for game_info
INFO - Generating description for player_stats using Gemini...
INFO - ✓ Generated description for player_stats
```

## Benefits

### 1. Complete Documentation

- **Before**: Many tables have no description
- **After**: All tables have meaningful descriptions

### 2. Better Discoverability

- **Search**: Descriptions are indexed in Vertex AI Search
- **Understanding**: Users can quickly understand table purpose
- **Context**: AI-generated descriptions based on actual data

### 3. Cost-Effective

- **Model**: Gemini 2.5 Flash is extremely cost-effective
- **Speed**: Generates descriptions in 1-2 seconds
- **Quality**: High-quality, professional descriptions

### 4. Automatic

- **No manual work**: Descriptions generated during collection
- **Consistent**: All tables get the same quality of documentation
- **Scalable**: Works for hundreds or thousands of tables

## Configuration

### Environment Variables

```bash
# Required for Gemini
export GEMINI_API_KEY="your-api-key-here"

# Optional: Custom model
export GEMINI_MODEL="gemini-2.0-flash-exp"
```

### Command Line Options

```bash
--use-gemini          # Enable Gemini (default: true)
--skip-gemini         # Disable Gemini
--gemini-api-key KEY  # Provide API key directly
```

## Integration with Existing Features

Gemini description generation works seamlessly with:

- ✅ **Dataplex profiling**: Uses sample values from Dataplex
- ✅ **SQL fallback**: Uses SQL samples if Dataplex not available
- ✅ **Vertex AI Search**: Descriptions are indexed for search
- ✅ **Markdown reports**: Descriptions appear in reports
- ✅ **JSONL export**: Descriptions included in JSONL

## Error Handling

### Missing API Key

```
WARNING - Gemini API key not found - description generation disabled
```

**Solution**: Set `GEMINI_API_KEY` environment variable

### API Errors

```
ERROR - Error generating description for table_name: API rate limit exceeded
```

**Solution**: Wait a moment or disable Gemini with `--skip-gemini`

### Generation Failures

```
WARNING - Failed to generate description for table_name
```

**Solution**: Table proceeds without description (no data loss)

## Cost Estimation

### Gemini 2.5 Flash Pricing

- **Input**: $0.15 per 1M tokens
- **Output**: $0.60 per 1M tokens

### Example Cost

For a table with:
- 30 columns
- Sample values for each
- Column descriptions

**Input tokens**: ~1,000 tokens  
**Output tokens**: ~100 tokens  
**Cost per table**: ~$0.0002 (less than a cent!)

**100 tables**: ~$0.02  
**1,000 tables**: ~$0.20

## Best Practices

### 1. Use with Dataplex

```bash
poetry run python scripts/collect-bigquery-metadata.py \
  --use-dataplex \
  --use-gemini
```

Dataplex provides richer context (sample values, profiles) for better descriptions.

### 2. Set API Key in Environment

```bash
export GEMINI_API_KEY="your-key"
```

More secure than passing via command line.

### 3. Review Generated Descriptions

Generated descriptions are high-quality but may benefit from manual review for critical tables.

### 4. Re-run Collection

Re-running collection won't regenerate descriptions for tables that already have them. Only new tables or tables without descriptions will be processed.

## Troubleshooting

### No Descriptions Generated

**Check:**
1. Is `GEMINI_API_KEY` set?
2. Are tables already have descriptions?
3. Check logs for errors

### Poor Quality Descriptions

**Try:**
1. Use `--use-dataplex` for better context
2. Add column descriptions in BigQuery
3. Contact support if consistent issues

### API Rate Limits

**Solution:**
- Reduce batch size with `--max-tables`
- Add delays between tables (future enhancement)
- Use multiple API keys (future enhancement)

## Future Enhancements

Planned improvements:
- [ ] Batch processing for faster generation
- [ ] Caching to avoid regenerating descriptions
- [ ] Custom prompts per dataset or domain
- [ ] Quality scoring and review workflow
- [ ] Support for other models (Claude, GPT-4, etc.)

## Conclusion

Gemini-generated descriptions ensure every table in your data discovery system has meaningful documentation, improving discoverability and understanding with minimal cost and effort.

---

For more information, see:
- [Gemini API Documentation](https://ai.google.dev/docs)
- [BigQuery Metadata Collection](./README.md)
- [Dataplex Profiling](./terraform/dataplex-profiling/SCHEDULING.md)

