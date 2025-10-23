<!-- 6b9f587d-ce45-44bf-a3db-09a47c2a1ad4 3fd903f9-7196-48d5-a603-6eab0a8bca93 -->
# Planning Agent Implementation

## Overview

Create the Planning Agent as a full MCP server with stdio/HTTP transport that guides users through conversational refinement to generate structured Data Product Requirement Prompts (Data PRPs).

## Architecture

Following the patterns from `data-discovery-agent` and `query-generation-agent`:

- **MCP Server**: Full implementation with stdio (primary) and HTTP (secondary) transports
- **Conversational Engine**: Uses Gemini 2.5 Pro for intelligent requirement gathering
- **Session Management**: Track conversation state across multiple turns
- **Output Handling**: Support both GCS (`gs://`) and local file paths (`file://` or regular paths)
- **CLI Tool**: Interactive command-line interface for testing

## Project Structure

```
/home/user/git/data-planning-agent/
├── src/
│   └── data_planning_agent/
│       ├── __init__.py
│       ├── mcp/
│       │   ├── __init__.py
│       │   ├── server.py          # Stdio MCP server
│       │   ├── http_server.py     # HTTP MCP server
│       │   ├── config.py          # Pydantic configuration
│       │   ├── handlers.py        # MCP tool handlers
│       │   └── tools.py           # MCP tool definitions
│       ├── clients/
│       │   ├── __init__.py
│       │   ├── gemini_client.py   # Gemini API client
│       │   └── storage_client.py  # GCS/local file writer
│       ├── core/
│       │   ├── __init__.py
│       │   ├── conversation.py    # Conversation state management
│       │   ├── refiner.py         # Requirement refinement logic
│       │   └── prp_generator.py   # Data PRP markdown generation
│       ├── models/
│       │   ├── __init__.py
│       │   ├── session.py         # Session data models
│       │   └── prp_schema.py      # Data PRP schema
│       └── cli/
│           ├── __init__.py
│           └── interactive.py     # Interactive CLI tool
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── mcp/
│   │   │   ├── __init__.py
│   │   │   ├── test_server.py
│   │   │   ├── test_http_server.py
│   │   │   ├── test_handlers.py
│   │   │   └── test_tools.py
│   │   ├── clients/
│   │   │   ├── __init__.py
│   │   │   ├── test_gemini_client.py
│   │   │   └── test_storage_client.py
│   │   └── core/
│   │       ├── __init__.py
│   │       ├── test_conversation.py
│   │       ├── test_refiner.py
│   │       └── test_prp_generator.py
│   └── integration/
│       ├── __init__.py
│       └── test_end_to_end.py
├── .env.example
├── .gitignore
├── LICENSE
├── pyproject.toml
└── README.md
```

## Implementation Details

### 1. Configuration (`src/data_planning_agent/mcp/config.py`)

Pydantic-based config loading from environment variables:

- `GEMINI_API_KEY`: API key for Gemini
- `GEMINI_MODEL`: Model name (default: `gemini-2.5-pro`)
- `OUTPUT_DIR`: Default output directory (supports `gs://` and local paths)
- `MCP_TRANSPORT`: Transport mode (`stdio` or `http`)
- `MCP_HOST`, `MCP_PORT`: HTTP server settings
- `LOG_LEVEL`: Logging level

### 2. MCP Tools (`src/data_planning_agent/mcp/tools.py`)

Three MCP tools:

**`start_planning_session`**

- Input: `initial_intent` (string) - The high-level business intent
- Output: Session ID and first clarifying questions
- Creates new conversation session

**`continue_conversation`**

- Input: `session_id` (string), `user_response` (string)
- Output: Next questions or indication that requirements are complete
- Advances conversation with AI-driven follow-up questions

**`generate_data_prp`**

- Input: `session_id` (string), `output_path` (optional string)
- Output: Generated Data PRP markdown and file location
- Synthesizes conversation into structured Data PRP markdown

### 3. Gemini Client (`src/data_planning_agent/clients/gemini_client.py`)

Wrapper around `google-generativeai` SDK:

- Generate clarifying questions based on conversation history
- Determine when requirements are sufficiently detailed
- Generate structured Data PRP from gathered information
- Handle retries and error cases

### 4. Conversation Manager (`src/data_planning_agent/core/conversation.py`)

Session state management:

- Track conversation history (user inputs + AI responses)
- Store extracted requirements
- Determine conversation completeness
- Support session persistence (in-memory for MVP)

### 5. PRP Generator (`src/data_planning_agent/core/prp_generator.py`)

Generate structured markdown following exact PRD format:

```markdown
# Data Product Requirement Prompt

## 1. Executive Summary
- Objective: [one-sentence summary]
- Target Audience: [stakeholders]
- Key Question: [primary question]

## 2. Business Context
[detailed paragraph]

## 3. Data Requirements

### 3.1. Key Metrics
[list of metrics]

### 3.2. Dimensions & Breakdowns
[segmentation requirements]

### 3.3. Filters
[conditions and constraints]

## 4. Success Criteria
- Primary Metric: [main success indicator]
- Timeline: [delivery expectations]
```

### 6. Storage Client (`src/data_planning_agent/clients/storage_client.py`)

Handle output to different destinations:

- GCS paths: `gs://bucket-name/path/to/file.md`
- Local file paths: `file:///absolute/path/file.md` or `/path/to/file.md`
- Auto-detect path type and route to appropriate writer
- Create directories as needed for local paths

### 7. Interactive CLI (`src/data_planning_agent/cli/interactive.py`)

Command-line interface for testing:

```bash
poetry run planning-agent interactive
```

Features:

- Welcome message and instructions
- Prompt user for initial business intent
- Display AI questions in formatted output (using `rich`)
- Collect user responses
- Show conversation progress
- Generate and display final Data PRP
- Save to specified output path

### 8. MCP Servers

**Stdio Server** (`src/data_planning_agent/mcp/server.py`):

- Default transport for Cursor integration
- Uses `mcp.server.stdio` for subprocess communication
- Entry point: `poetry run python -m data_planning_agent.mcp`

**HTTP Server** (`src/data_planning_agent/mcp/http_server.py`):

- FastAPI-based HTTP server
- Endpoints: `/health`, `/`, `/mcp/tools`, `/mcp/call-tool`
- JSON-RPC 2.0 protocol for MCP clients
- SSE support for notifications

### 9. Testing

**Unit Tests**:

- Mock Gemini API responses
- Test conversation state transitions
- Validate PRP generation output format
- Test GCS/local file writing

**Integration Tests**:

- End-to-end conversation flow
- Output to both GCS and local paths
- MCP tool invocation via stdio and HTTP

## Dependencies (pyproject.toml)

Core:

- `python = ">=3.10,<3.13"`
- `google-generativeai = "^0.8.0"` - Gemini API
- `google-cloud-storage = "^2.10.0"` - GCS support
- `mcp = "^1.0.0"` - MCP SDK
- `fastapi = "^0.115.0"` - HTTP server
- `uvicorn = "^0.32.0"` - ASGI server
- `pydantic = "^2.0.0"` - Configuration
- `python-dotenv = "^1.0.0"` - Environment variables
- `rich = "^13.0.0"` - Terminal formatting

Dev:

- `pytest = "^7.4.2"`
- `pytest-asyncio = "^0.21.2"`
- `pytest-mock = "^3.11.0"`
- `pytest-cov = "^4.1.0"`
- `black = "^23.0.0"`
- `ruff = "^0.1.0"`

## Environment Variables (.env.example)

```bash
# Gemini Configuration
GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_MODEL=gemini-2.5-pro

# Output Configuration
OUTPUT_DIR=./output
# Or use GCS: OUTPUT_DIR=gs://your-bucket/planning-sessions

# MCP Configuration
MCP_TRANSPORT=stdio
MCP_SERVER_NAME=data-planning-agent
MCP_SERVER_VERSION=1.0.0
MCP_HOST=0.0.0.0
MCP_PORT=8080

# Logging
LOG_LEVEL=INFO
```

## Key Files

### README.md

- Project overview and features
- Installation instructions (`poetry install`)
- Configuration setup (`.env` file)
- Usage examples (CLI and MCP)
- Cursor integration guide
- Example conversation flow

### LICENSE

- Apache 2.0 License (full text)

### .gitignore

- Python-specific ignores
- `.env` (but not `.env.example`)
- Virtual environments
- `__pycache__`, `.pytest_cache`
- IDE files

## Cursor Integration

Users can add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "data-planning-agent": {
      "command": "poetry",
      "args": ["run", "python", "-m", "data_planning_agent.mcp"],
      "cwd": "/home/user/git/data-planning-agent",
      "env": {
        "GEMINI_API_KEY": "your-key-here",
        "MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```

## Conversation Logic

The agent will ask questions in these categories:

1. **Objective**: Business goal and decision-making purpose
2. **Audience**: End-users and stakeholders
3. **Key Metrics**: Specific measurements needed
4. **Dimensions**: Data segmentation and grouping
5. **Filters**: Conditions and constraints
6. **Comparisons**: Time-based or category-based comparisons
7. **Timeline**: Delivery and update frequency expectations

The Gemini client uses prompts that guide the model to:

- Ask up to 4 focused questions at a time (maximize efficiency)
- Bias towards multiple choice questions when possible (easier for users to respond)
- Use open-ended questions only when specific details are needed
- Avoid asking questions already answered
- Recognize when enough detail has been gathered
- Generate complete, well-structured Data PRPs

**Example Question Format**:

```
Based on your intent, I have a few questions:

1. What is the primary audience for this analysis?
   a) Executives (high-level summary)
   b) Regional managers (summary + detail)
   c) Data analysts (detailed data)
   d) Other (please specify)

2. What key metrics define "trending" for your use case?
   a) Unit sales volume
   b) Revenue growth
   c) Profit margin
   d) Multiple metrics (please specify)

3. What time frame should we analyze?
   a) Last 4 weeks
   b) Last 8 weeks
   c) Last quarter
   d) Custom period (please specify)

4. Do you need comparisons to previous periods?
   a) Yes, week-over-week
   b) Yes, year-over-year
   c) Yes, both
   d) No comparisons needed
```

### To-dos

- [ ] Add CONTEXT_DIR field to PlanningAgentConfig
- [ ] Create context_loader.py with directory reading and concatenation logic
- [ ] Add context parameter to GeminiClient and modify all prompt-building methods
- [ ] Load context in stdio server initialization and pass to Gemini client
- [ ] Load context in HTTP server lifespan and pass to Gemini client
- [ ] Load context in InteractiveCLI and pass to Gemini client
- [ ] Write unit tests for context loading functionality
- [ ] Update conftest.py fixtures to include context parameter
- [ ] Write integration tests verifying context influences agent behavior
- [ ] Create context.example/ directory with sample context files
- [ ] Update README.md and .env.example with context loading documentation