# Analytical Insights Generation

## Overview

The system now automatically generates **4-5 analytical insights/questions** for each table using **Gemini 2.5 Flash**. These insights help users understand what analytical questions can be answered using the data.

## Example Insights

For a table like `nfl_post_game_info`, the system generates questions such as:

1. Analyze the trend of penalties and penalty yards over the weeks of the season for each team, to identify potential discipline issues
2. Calculate the average number of turnovers for home and away teams based on the number of home team losses prior to the game
3. Calculate the covariance between the home team's rushing yards and the away team's passing yards
4. Find the home teams with the highest average difference between their score and the away team's score
5. Determine the percentage of drives that resulted in a touchdown for each quarter

## How It Works

### 1. Context Gathering

Gemini analyzes:
- ✅ **Table name** and **description**
- ✅ **Full schema** with column names, types, and descriptions
- ✅ **Sample values** (top 3 most common per column)
- ✅ **Column profiles** (min/max/avg for numeric, lengths for strings)
- ✅ **Table statistics** (row count, data types)

### 2. Insight Generation

Gemini is prompted to generate:
- **Specific, actionable questions** that reference actual columns
- **Meaningful analyses** (trends, correlations, comparisons, aggregations)
- **SQL-answerable queries** using the table data
- **Business-valuable insights** that provide real analytical value

### 3. Integration

Insights appear in:
- ✅ **JSONL files** (indexed in Vertex AI Search)
- ✅ **Markdown reports** (human-readable documentation)

## Output Locations

### JSONL (Vertex AI Search)

```
## Analytical Insights

Questions that could be answered using this table:
1. Analyze the trend of penalties and penalty yards over the weeks...
2. Calculate the average number of turnovers for home and away teams...
3. Calculate the covariance between the home team's rushing yards...
4. Find the home teams with the highest average difference...
5. Determine the percentage of drives that resulted in a touchdown...
```

### Markdown Reports

```markdown
## Analytical Insights

This table can be used to answer questions such as:

1. Analyze the trend of penalties and penalty yards over the weeks...
2. Calculate the average number of turnovers for home and away teams...
3. Calculate the covariance between the home team's rushing yards...
4. Find the home teams with the highest average difference...
5. Determine the percentage of drives that resulted in a touchdown...
```

## Prompt Design

The prompt instructs Gemini to:

### DO:
- ✅ Be specific and actionable
- ✅ Reference specific columns from the schema
- ✅ Suggest meaningful analysis types (trends, correlations, comparisons)
- ✅ Make queries answerable using SQL on this table
- ✅ Provide business value or interesting insights

### DON'T:
- ❌ Generate generic questions
- ❌ Reference non-existent columns
- ❌ Suggest analyses requiring external data
- ❌ Use vague or unclear language

## Example Prompt Context

```
You are a data analyst. Analyze the following table and generate specific, 
actionable analytical questions that could be answered using this data.

**Table Name:** lennyisagoodboy.nfldata.post_game_stats

**Description:** Contains NFL post-game statistics including team performance 
metrics, scores, penalties, turnovers, and drive outcomes across regular season 
and playoff games.

**Rows:** 5,234

**Schema:**
- **game_id** (STRING): NFL game identifier [Examples: 'NFL_2023_W01_001', ...]
- **week** (INTEGER): Week of the season [Examples: '1', '2', '3']
- **home_team** (STRING): Home team name [Examples: 'Patriots', 'Cowboys', ...]
- **away_team** (STRING): Away team name [Examples: 'Bills', 'Giants', ...]
- **home_score** (INTEGER): Home team final score [Examples: '27', '24', '31']
- **away_score** (INTEGER): Away team final score [Examples: '20', '17', '28']
- **penalties_home** (INTEGER): Number of penalties for home team [Examples: '5', '7', '3']
- **penalty_yards_home** (INTEGER): Penalty yards for home team [Examples: '45', '60', '25']
- **turnovers_home** (INTEGER): Number of turnovers for home team [Examples: '1', '2', '0']
- **rushing_yards_home** (INTEGER): Rushing yards for home team [Examples: '120', '95', '150']
- **passing_yards_away** (INTEGER): Passing yards for away team [Examples: '280', '310', '245']
... and 25 more columns

**Key Numeric Columns:** home_score, away_score, penalties_home, turnovers_home, rushing_yards_home
**Key Categorical Columns:** game_id, home_team, away_team, quarter

**Generate 5 analytical questions/insights:**
```

## Configuration

### Enable/Disable

Insights generation is **enabled by default** when Gemini is enabled:

```bash
# With insights (default)
poetry run python scripts/collect-bigquery-metadata.py --use-dataplex

# Without Gemini/insights
poetry run python scripts/collect-bigquery-metadata.py --skip-gemini
```

### Number of Insights

Default: 5 insights per table

Can be modified in the code:
```python
insights = self.gemini_describer.generate_table_insights(
    ...,
    num_insights=5,  # Change this value
)
```

## Benefits

### 1. Improved Discoverability

- Users can quickly understand **what questions the data can answer**
- Insights are **indexed in Vertex AI Search** for easy finding
- Helps users decide if a table is relevant to their analysis

### 2. Analytical Guidance

- Provides **specific, actionable examples** of analyses
- References **actual columns** from the schema
- Suggests **meaningful analytical approaches**

### 3. Documentation Value

- Acts as **living documentation** for data analysts
- Shows **practical use cases** for each table
- Demonstrates **analytical possibilities**

### 4. Search Enhancement

- Insights are **fully searchable** in Vertex AI Search
- Users can search by **analytical approach** (e.g., "correlation", "trend")
- Makes tables discoverable by **use case** not just name

## Cost

**Very low:**
- ~1,000 tokens per table (similar to descriptions)
- ~$0.0002 per table
- 100 tables ≈ $0.02
- 1,000 tables ≈ $0.20

**Total cost with descriptions + insights:**
- ~$0.0004 per table (both combined)
- 100 tables ≈ $0.04
- 1,000 tables ≈ $0.40

## Examples by Domain

### NBA Game Data

```
1. Analyze the correlation between home team attendance and final score differential
2. Calculate the average number of overtime games per team across all seasons
3. Identify teams with the highest variance in scoring across home vs away games
4. Determine the impact of back-to-back games on team performance and turnovers
5. Find the relationship between early season records and playoff appearances
```

### Financial Transactions

```
1. Analyze the distribution of transaction amounts by merchant category and time of day
2. Calculate the percentage of declined transactions by card type and issuer
3. Identify patterns in fraudulent transactions based on transaction velocity and location
4. Determine the average time between transactions for high-value customers
5. Find correlations between transaction amounts and customer demographic segments
```

### E-commerce Orders

```
1. Analyze the trend of cart abandonment rates across different product categories
2. Calculate the average order value by customer acquisition channel and device type
3. Identify the impact of shipping cost on conversion rates for different price ranges
4. Determine the percentage of orders with returns by product category and season
5. Find the correlation between customer reviews and repeat purchase rates
```

## Logging

```
INFO - Generating insights for game_info using Gemini...
INFO - ✓ Generated 5 insights for game_info
INFO - Generating insights for Markdown: game_info
INFO - ✓ Generated 5 insights for Markdown: game_info
```

## Integration Points

### 1. JSONL Generation (bigquery_collector.py)

```python
# Generate analytical insights with Gemini
insights = None
if self.gemini_describer:
    insights = self.gemini_describer.generate_table_insights(
        table_name=table_ref,
        description=table_metadata.get("description", ""),
        schema=schema_info.get("fields", []),
        sample_values=sample_values,
        column_profiles=column_profiles,
        row_count=table.num_rows,
        num_insights=5,
    )
    
    if insights:
        quality_info["insights"] = insights
```

### 2. Markdown Generation (collect-bigquery-metadata.py)

```python
# Generate analytical insights with Gemini (for Markdown)
insights = collector.gemini_describer.generate_table_insights(
    table_name=table_ref,
    description=table.description or "",
    schema=schema_fields,
    sample_values=sample_values,
    column_profiles=column_profiles,
    row_count=table.num_rows,
    num_insights=5,
)

if insights:
    quality_stats["insights"] = insights
```

### 3. JSONL Formatter (metadata_formatter.py)

```python
# Analytical Insights
if quality_info and quality_info.get("insights"):
    sections.append("## Analytical Insights")
    sections.append("Questions that could be answered using this table:")
    for i, insight in enumerate(quality_info["insights"], 1):
        sections.append(f"{i}. {insight}")
```

### 4. Markdown Formatter (markdown_formatter.py)

```python
# Analytical Insights
if extended_metadata and extended_metadata.get("quality_stats"):
    if extended_metadata["quality_stats"].get("insights"):
        sections.append(self._generate_insights_section(
            extended_metadata["quality_stats"]["insights"]
        ))
```

## Error Handling

### No Gemini API Key

```
WARNING - Gemini API key not found - description generation disabled
```

**Result**: No insights generated, collection continues

### Generation Failure

```
ERROR - Failed to generate insights for table_name: API error
```

**Result**: Table processed without insights, no data loss

### Parsing Issues

```
WARNING - Could not parse insights from Gemini response for table_name
```

**Result**: Insights skipped, other metadata collected normally

## Future Enhancements

Planned improvements:
- [ ] Cache insights to avoid regeneration
- [ ] Custom prompt templates per domain
- [ ] User feedback on insight quality
- [ ] Suggested SQL queries for each insight
- [ ] Insight difficulty ratings (beginner/intermediate/advanced)
- [ ] Link insights to example queries or notebooks

## Conclusion

Analytical insights make your data discovery system more valuable by:
- **Guiding users** on how to analyze the data
- **Demonstrating value** of each table
- **Improving searchability** by use case
- **Documenting possibilities** for data analysts

All at a minimal cost and fully automated!

---

For more information, see:
- [Gemini Descriptions](./GEMINI-DESCRIPTIONS.md)
- [Sample Values](./SAMPLE-VALUES-UPDATE.md)
- [BigQuery Collection](./README.md)

