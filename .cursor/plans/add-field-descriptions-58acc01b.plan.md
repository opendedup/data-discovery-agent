<!-- 58acc01b-3b89-4ae3-893a-4fda097c3460 4cf2363f-a480-487f-af16-087afd241ef0 -->
# Add Field Descriptions to Query Output

Enhance the query-generation-agent to generate semantic field descriptions using Gemini Flash based on source table schemas and SQL queries, then update data-graphql-agent to use these descriptions in GraphQL schema generation.

## Changes to Query-Generation-Agent

### 1. Add Field Description Generator to GeminiClient

**File:** `src/query_generation_agent/clients/gemini_client.py`

Add new method to generate field descriptions using gemini-flash-2.0:

```python
async def generate_field_descriptions(
    self,
    sql: str,
    schema: List[Dict[str, str]],
    insight: str,
    source_datasets: List[Dict[str, Any]]
) -> Dict[str, str]:
    """Generate semantic descriptions for query output fields using Gemini Flash.
    
    Uses source table schema descriptions and the SQL query to generate
    clear, concise descriptions for each output field.
    
    Args:
        sql: The SQL query
        schema: Basic field schema (name, type, mode)
        insight: Original user insight/question
        source_datasets: Source datasets with schema descriptions
        
    Returns:
        Dictionary mapping field names to descriptions
    """
```

Implementation details:

- Use `gemini-2.0-flash-latest` model for speed
- Build prompt with: insight, SQL query, source table schemas (with descriptions), output field list
- Request JSON output: `{"field_name": "description", ...}`
- Handle JSON parsing errors gracefully
- Return empty dict on failure (don't block query generation)

### 2. Update BigQueryClient to Support Description Enrichment

**File:** `src/query_generation_agent/clients/bigquery_client.py`

Modify `execute_with_limit` to accept source_tables parameter and return enriched schema:

```python
def execute_with_limit(
    self,
    sql: str,
    limit: int = 10,
    source_tables: Optional[List[str]] = None  # NEW parameter
) -> Tuple[bool, Optional[str], Optional[List[Dict[str, Any]]], Optional[List[Dict[str, str]]]]:
```

Schema will still return basic structure (no changes to format), descriptions will be added later in the pipeline.

### 3. Update DryRunValidator to Pass Source Tables

**File:** `src/query_generation_agent/validation/dryrun_validator.py`

Update `execute_sample` to accept and pass source_tables:

```python
def execute_sample(
    self,
    sql: str,
    source_tables: Optional[List[str]] = None  # NEW parameter
) -> Tuple[bool, Optional[str], Optional[List[Dict[str, Any]]], Optional[List[Dict[str, str]]]]:
    logger.debug(f"Executing sample query (limit {self.max_sample_rows})")
    return self.bigquery_client.execute_with_limit(
        sql, 
        limit=self.max_sample_rows,
        source_tables=source_tables  # Pass through
    )
```

### 4. Update QueryRefiner to Enrich Schema with Descriptions

**File:** `src/query_generation_agent/generation/query_refiner.py`

In `_run_validation_pipeline` method (around line 258):

After getting schema from `execute_sample`, call Gemini to generate descriptions:

```python
# Stage 2: Sample execution
exec_success, exec_error, sample_rows, schema = self.dryrun_validator.execute_sample(sql, source_tables)
validation_details["execution_valid"] = exec_success
validation_details["sample_results"] = sample_rows
validation_details["result_schema"] = schema

if exec_success and schema:
    # Generate field descriptions using Gemini Flash
    try:
        source_datasets_dicts = self._prepare_datasets_for_descriptions(datasets)
        field_descriptions = await self.gemini_client.generate_field_descriptions(
            sql=sql,
            schema=schema,
            insight=insight,
            source_datasets=source_datasets_dicts
        )
        
        # Enrich schema with descriptions
        for field in schema:
            field_name = field.get("name")
            if field_name in field_descriptions:
                field["description"] = field_descriptions[field_name]
        
        validation_details["result_schema"] = schema
    except Exception as e:
        logger.warning(f"Failed to generate field descriptions: {e}")
        # Continue without descriptions
```

Add helper method to extract source table references from SQL:

```python
def _extract_source_tables(self, sql: str, datasets: List[DatasetMetadata]) -> List[str]:
    """Extract fully qualified table names used in SQL."""
    source_tables = []
    for dataset in datasets:
        table_id = dataset.get_full_table_id()
        if table_id in sql:
            source_tables.append(table_id)
    return source_tables
```

Add helper to convert datasets to dicts with schema:

```python
def _prepare_datasets_for_descriptions(self, datasets: List[DatasetMetadata]) -> List[Dict[str, Any]]:
    """Prepare dataset metadata for description generation."""
    return [
        {
            "table_id": ds.get_full_table_id(),
            "description": ds.description,
            "schema": ds.schema  # Contains field descriptions
        }
        for ds in datasets
    ]
```

Pass source_tables to validator:

```python
# Extract source tables from datasets
source_tables = self._extract_source_tables(sql, datasets)
exec_success, exec_error, sample_rows, schema = self.dryrun_validator.execute_sample(sql, source_tables)
```

### 5. Make GeminiClient Methods Async-Compatible

**File:** `src/query_generation_agent/clients/gemini_client.py`

Since we need async call in QueryRefiner, either:

- Make `generate_field_descriptions` sync and call it normally
- Or update QueryRefiner's `_run_validation_pipeline` to be async

Simpler approach: Keep it sync and call directly (no await needed).

## Changes to Data-GraphQL-Agent

### 6. Update SchemaGenerator to Use Field Descriptions

**File:** `src/data_graphql_agent/generation/schema_generator.py`

In `_generate_types_from_schema` method (line 125-164):

Currently generates types from BigQuery schema fields. Update to accept pre-enriched schema with descriptions:

```python
def _generate_types_from_schema(
    self, type_name: str, schema: List[bigquery.SchemaField], 
    field_descriptions: Optional[Dict[str, str]] = None  # NEW parameter
) -> Tuple[List[str], List[Dict[str, any]]]:
```

But since we're now getting schema from JSON (not BigQuery), update the method that calls BigQuery dry run to pass field descriptions from the query metadata.

Actually, better approach: Update `generate_schema_from_queries` to extract descriptions from query metadata:

In line 56-67 where queries are processed:

```python
for query in queries:
    query_name = query["queryName"]
    sql = query["sql"]
    
    # Get schema from BigQuery dry run
    schema = self._get_query_schema(sql)
    
    # Get field descriptions from query validation metadata if available
    field_descriptions = {}
    if "validation_details" in query and query["validation_details"].get("result_schema"):
        for field_info in query["validation_details"]["result_schema"]:
            if "description" in field_info:
                field_descriptions[field_info["name"]] = field_info["description"]
```

Then in `_generate_types_from_schema`, add descriptions to field lines:

```python
for field in schema:
    graphql_type, nested_types = self._field_to_graphql_type(field, type_name)
    types.extend(nested_types)
    
    # Add description if available
    field_desc = field_descriptions.get(field.name) if field_descriptions else None
    if field_desc:
        # Escape for GraphQL
        escaped_desc = field_desc.replace('\\', '\\\\').replace('"', '\\"')
        field_lines.append(f'  """')
        field_lines.append(f'  {escaped_desc}')
        field_lines.append(f'  """')
    
    # Add field to type definition
    field_lines.append(f"  {field.name}: {graphql_type}")
```

### 7. Update QueryInput Model to Include Validation Details

**File:** `src/data_graphql_agent/models/request_models.py`

Add optional validation_details field to QueryInput:

```python
class QueryInput(BaseModel):
    query_name: str = Field(...)
    sql: str = Field(...)
    source_tables: List[str] = Field(...)
    description: Optional[str] = Field(None, ...)
    alignment_score: Optional[float] = Field(None, ...)
    iterations: Optional[int] = Field(None, ...)
    generation_time_ms: Optional[float] = Field(None, ...)
    
    # NEW: Include validation details with schema
    validation_details: Optional[Dict[str, Any]] = Field(
        None,
        description="Validation details including result_schema with field descriptions"
    )
```

Update `generate_schema_from_queries` to pass validation_details through.

## Testing

After implementation, test with the existing backtest_evaluation_view JSON:

1. Run query-generation-agent with test datasets
2. Verify output JSON contains `result_schema` with `description` field
3. Pass JSON to data-graphql-agent
4. Verify generated GraphQL schema has field descriptions
5. Check typeDefs.ts output shows descriptions above fields

## Summary

This implementation:

- Uses Gemini Flash to generate semantic field descriptions based on source schemas and SQL
- Enriches the result_schema in validation_details with descriptions
- Updates data-graphql-agent to read and use these descriptions in GraphQL schema
- Maintains backward compatibility (descriptions are optional)

### To-dos

- [ ] Add generate_field_descriptions method to GeminiClient using gemini-2.0-flash-latest
- [ ] Update BigQueryClient.execute_with_limit to accept source_tables parameter
- [ ] Update DryRunValidator.execute_sample to pass source_tables through
- [ ] Update QueryRefiner to call Gemini for field descriptions and enrich result_schema
- [ ] Add validation_details field to QueryInput model in data-graphql-agent
- [ ] Update SchemaGenerator to extract and use field descriptions from validation_details
- [ ] Test complete flow: query-generation -> data-graphql with field descriptions