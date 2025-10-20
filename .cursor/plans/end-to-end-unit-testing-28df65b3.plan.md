<!-- 28df65b3-5675-4596-80bd-05ac946264db 87f8c865-7cc5-4c2d-a37f-e65ca1ab7a47 -->
# End-to-End Unit Testing Plan

## Test Strategy

This plan implements comprehensive testing with:

- **Unit tests** for core business logic (mocked GCP dependencies where appropriate)
- **Integration tests** for DAG execution using real GCP environment from `.env`
- **Validation tests** for data quality across BigQuery, GCS, and Vertex AI Search

## Phase 1: Test Infrastructure Setup

### 1.1 Update Dependencies

- Add testing dependencies to `pyproject.toml`:
  - `pytest-asyncio` (async test support)
  - `pytest-mock` (mocking utilities)
  - `pytest-cov` (coverage reporting)
  - `freezegun` (time mocking)
  - `responses` (HTTP mocking)

### 1.2 Create Test Configuration

- Create `pytest.ini` with:
  - Test discovery patterns
  - Asyncio mode configuration
  - Coverage settings
  - Markers for unit vs integration tests

- Create `tests/conftest.py` with shared fixtures:
  - `mock_env` - Mock environment variables
  - `gcp_config` - Load real GCP config from `.env`
  - `mock_bigquery_client` - Mocked BigQuery client
  - `mock_storage_client` - Mocked GCS client
  - `mock_vertex_client` - Mocked Vertex AI client
  - `sample_table_metadata` - Test data fixtures

### 1.3 Create Test Helpers

- Create `tests/helpers/`:
  - `mock_gcp.py` - GCP service mocking utilities (ONLY for unit tests, not integration tests)
  - `fixtures.py` - Sample metadata, schemas, responses (shared by both unit and integration tests)
  - `assertions.py` - Custom assertions for metadata validation (shared by both test types)

**Note**: `mock_gcp.py` is used exclusively for unit tests to simulate GCP API responses without making real API calls. Integration tests will use the live GCP environment from `.env` with no mocking.

## Phase 2: Core Business Logic Tests

### 2.1 Collectors Tests (`tests/unit/collectors/`)

**`test_bigquery_collector.py`**

- Test initialization with various configurations
- Test `collect_all()` method:
  - Mock BigQuery API responses
  - Verify dataset/table discovery
  - Test exclusion patterns
  - Test threading behavior (max_workers)
  - Verify BigQueryAssetSchema output structure
- Test error handling (API failures, timeouts)
- Test progress tracking

**`test_dataplex_profiler.py`**

- Test profile scan retrieval
- Test parsing of profile results
- Test column statistics extraction
- Test PII/PHI detection handling
- Test NotFound error handling

**`test_gemini_describer.py`**

- Test description generation with mocked Gemini API
- Test retry logic for rate limits
- Test fallback when API key missing
- Test prompt construction
- Test response parsing and sanitization

### 2.2 Formatters Tests (`tests/unit/search/`)

**`test_metadata_formatter.py`**

- Test `format_bigquery_table()`:
  - Verify content text generation
  - Test struct data population
  - Verify searchable fields
  - Test ID generation
- Test handling of missing/optional fields
- Test nested schema formatting

**`test_markdown_formatter.py`**

- Test markdown report generation:
  - Verify header structure
  - Test table overview section
  - Test schema table formatting
  - Test security/governance sections
  - Test statistics formatting
- Verify markdown syntax validity
- Test GCS path generation

**`test_jsonl_schema.py`**

- Test Pydantic model validation
- Test enum values
- Test field constraints
- Test model serialization/deserialization

**`test_query_builder.py`**

- Test query parsing and filter extraction
- Test semantic query building
- Test filter expression construction
- Test boost spec generation
- Test edge cases (empty query, special chars)

**`test_result_parser.py`**

- Test search result parsing
- Test pagination handling
- Test field extraction
- Test error response handling

### 2.3 Writers Tests (`tests/unit/writers/`)

**`test_bigquery_writer.py`**

- Test schema creation
- Test table creation (if not exists)
- Test data insertion with mocked BigQuery:
  - Verify run_timestamp addition
  - Test batch insertion
  - Test schema validation
- Test lineage recording:
  - Mock lineage API calls
  - Verify process/run/event creation
  - Test error handling
- Test dataset/table existence checks

### 2.4 Utils Tests (`tests/unit/utils/`)

**`test_lineage.py`**

- Test `record_lineage()` function
- Test `format_bigquery_fqn()` 
- Test process creation
- Test run creation (COMPLETED/FAILED states)
- Test lineage event creation
- Test FQN formatting for various sources
- Test error handling

## Phase 3: MCP Service Tests

### 3.1 MCP Core Tests (`tests/unit/mcp/`)

**`test_config.py`**

- Test `load_config()` from environment
- Test configuration validation
- Test default values
- Test missing required fields

**`test_tools.py`**

- Test `get_available_tools()` returns correct tools
- Test `validate_query_params()` validation logic
- Test `format_tool_response()` formatting
- Test `format_error_response()` error formatting

**`test_handlers.py`**

- Test `MCPHandlers` initialization
- Test `handle_query_data_assets()`:
  - Mock Vertex AI Search responses
  - Verify request formatting
  - Test pagination
  - Test filter application
- Test `handle_get_asset_details()`:
  - Mock GCS markdown retrieval
  - Test error handling for missing reports
- Test `handle_list_datasets()`:
  - Test dataset listing logic
  - Test filtering and sorting

**`test_server.py`**

- Test `create_mcp_server()` initialization
- Test tool registration
- Test handler routing
- Test error handling in handlers

**`test_http_server.py`**

- Test FastAPI app creation
- Test `/mcp/tools` endpoint
- Test `/mcp/call-tool` endpoint
- Test health check endpoint
- Test error responses

## Phase 4: Orchestration Tests

### 4.1 Task Tests (`tests/unit/orchestration/`)

**`test_tasks.py`**

- Test `collect_metadata_task()`:
  - Mock BigQueryCollector
  - Verify XCom push of assets
  - Test configuration loading from env
  - Test error handling

- Test `export_to_bigquery_task()`:
  - Mock BigQueryWriter
  - Verify XCom pull of assets
  - Test run_timestamp generation
  - Test lineage recording

- Test `export_markdown_reports_task()`:
  - Mock GCS uploads
  - Verify markdown generation
  - Test path structure
  - Test error handling

- Test `import_to_vertex_ai_task()`:
  - Mock Vertex AI import API
  - Verify BigQuery source configuration
  - Test import job monitoring

## Phase 5: Integration Tests (Real GCP)

### 5.1 End-to-End DAG Tests (`tests/integration/`)

**`test_dag_execution.py`**

- Load configuration from `.env`
- Execute full DAG workflow:

  1. Run `collect_metadata_task()`
  2. Run `export_to_bigquery_task()`
  3. Run `export_markdown_reports_task()`
  4. Run `import_to_vertex_ai_task()`

### 5.2 BigQuery Output Validation (`tests/integration/test_bigquery_validation.py`)

Query the real BigQuery export table and validate:

- **Row completeness**:
  - All expected tables present
  - run_timestamp populated
  - No null required fields

- **Schema validation**:
  - column_name, column_type populated
  - column_description present
  - Policy tags recorded if applicable

- **Description quality**:
  - table_description is non-empty and meaningful
  - column_description present for all columns
  - Minimum description length checks

- **Statistics validation**:
  - For tables: row_count >= 0, size_bytes > 0
  - For views: row_count and size_bytes may be 0 or null (acceptable)
  - last_modified_time present for all asset types
  - Distinguish between table_type (TABLE vs VIEW) in validation logic

- **Lineage presence**:
  - Query Data Catalog Lineage API
  - Verify process exists for DAG
  - Verify runs recorded
  - Verify events link sources to BigQuery table

### 5.3 GCS Markdown Validation (`tests/integration/test_markdown_validation.py`)

Retrieve and validate markdown reports from GCS:

- **File existence**:
  - Reports exist for all collected tables
  - Correct path structure: `{run_timestamp}/{project}/{dataset}/{table}.md`

- **Markdown syntax validation**:
  - Parse with markdown parser
  - Verify header structure (H1, H2, H3)
  - Verify table syntax
  - No broken markdown

- **Content completeness**:
  - Table overview section present
  - Schema table with all columns
  - Column descriptions present
  - Statistics section
  - Security/governance section if applicable

- **Data accuracy**:
  - Cross-reference with BigQuery export
  - Verify row counts match
  - Verify schema matches
  - Verify timestamps match

### 5.4 Vertex AI Search Validation (`tests/integration/test_vertex_validation.py`)

Query Vertex AI Search datastore and validate:

- **Import success**:
  - Verify import job completed
  - Check document count matches expected

- **Search functionality**:
  - Test semantic search queries
  - Verify results contain expected tables
  - Test filter queries (project, dataset)
  - Verify ranking/relevance

- **Document structure**:
  - Retrieve sample documents
  - Verify required fields present
  - Verify content text populated
  - Verify struct data fields

- **Data freshness**:
  - Verify timestamps in results
  - Check most recent run_timestamp

### 5.5 Lineage Validation (`tests/integration/test_lineage_validation.py`)

Query Data Catalog Lineage API and validate:

- **Process existence**:
  - Verify process for DAG exists
  - Check process attributes

- **Run records**:
  - Verify runs for recent executions
  - Check run states (COMPLETED)
  - Verify start/end times

- **Lineage events**:
  - Query incoming lineage (discovered tables → metadata table)
  - Verify source FQNs formatted correctly
  - Verify target FQN is metadata table
  - Check event timestamps

- **Multi-hop lineage**:
  - Verify GCS → BigQuery lineage
  - Verify BigQuery → Vertex AI lineage (if applicable)

## Phase 6: Test Execution & Reporting

### 6.1 Test Organization

```
tests/
├── __init__.py
├── conftest.py
├── helpers/
│   ├── __init__.py
│   ├── mock_gcp.py
│   ├── fixtures.py
│   └── assertions.py
├── unit/
│   ├── __init__.py
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── test_bigquery_collector.py
│   │   ├── test_dataplex_profiler.py
│   │   └── test_gemini_describer.py
│   ├── search/
│   │   ├── __init__.py
│   │   ├── test_metadata_formatter.py
│   │   ├── test_markdown_formatter.py
│   │   ├── test_jsonl_schema.py
│   │   ├── test_query_builder.py
│   │   └── test_result_parser.py
│   ├── writers/
│   │   ├── __init__.py
│   │   └── test_bigquery_writer.py
│   ├── mcp/
│   │   ├── __init__.py
│   │   ├── test_config.py
│   │   ├── test_tools.py
│   │   ├── test_handlers.py
│   │   ├── test_server.py
│   │   └── test_http_server.py
│   ├── orchestration/
│   │   ├── __init__.py
│   │   └── test_tasks.py
│   └── utils/
│       ├── __init__.py
│       └── test_lineage.py
└── integration/
    ├── __init__.py
    ├── test_dag_execution.py
    ├── test_bigquery_validation.py
    ├── test_markdown_validation.py
    ├── test_vertex_validation.py
    └── test_lineage_validation.py
```

### 6.2 Running Tests

**Unit tests only** (fast, mocked):

```bash
pytest tests/unit/ -v
```

**Integration tests** (slower, uses real GCP):

```bash
pytest tests/integration/ -v --slow
```

**All tests with coverage**:

```bash
pytest tests/ -v --cov=src/data_discovery_agent --cov-report=html
```

**Specific test markers**:

```bash
pytest -m "not slow"  # Skip integration tests
pytest -m "integration"  # Only integration tests
```

## Key Files to Create/Modify

1. `pyproject.toml` - Add test dependencies
2. `pytest.ini` - Pytest configuration
3. `tests/conftest.py` - Shared fixtures
4. `tests/helpers/` - Test utilities (3 files)
5. `tests/unit/` - Unit tests (20+ test files)
6. `tests/integration/` - Integration tests (5 test files)

## Success Criteria

- ✅ All unit tests pass with >80% code coverage
- ✅ Integration tests validate all three output systems
- ✅ Lineage records verified for all operations
- ✅ Schema and descriptions validated for completeness
- ✅ Markdown syntax validated
- ✅ Vertex AI Search queries return expected results
- ✅ Tests run in CI/CD pipeline

### To-dos

- [ ] Set up test infrastructure: dependencies, pytest.ini, conftest.py, and test helpers
- [ ] Create unit tests for collectors (BigQueryCollector, DataplexProfiler, GeminiDescriber)
- [ ] Create unit tests for formatters and search components (MetadataFormatter, MarkdownFormatter, QueryBuilder, ResultParser)
- [ ] Create unit tests for BigQueryWriter with lineage tracking
- [ ] Create unit tests for MCP service (config, tools, handlers, server)
- [ ] Create unit tests for orchestration tasks
- [ ] Create integration test for full DAG execution
- [ ] Create BigQuery output validation tests (schema, descriptions, completeness)
- [ ] Create GCS markdown validation tests (syntax, content, accuracy)
- [ ] Create Vertex AI Search validation tests (import, search, documents)
- [ ] Create lineage validation tests (process, runs, events, multi-hop)