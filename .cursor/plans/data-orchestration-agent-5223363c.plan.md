<!-- 5223363c-9216-4afd-a971-a29ae679b400 d469f370-dca8-418d-a135-64ecd700c0b7 -->
# Create Data Orchestration Agent with Google ADK

## Overview

Build a root agent at `/home/user/git/data-orchestration-agent` using Google's Agent Development Kit (ADK) that orchestrates all four data agents through three distinct modes: Ask Mode, Planning Mode, and Action Mode. The agent will use InMemorySessionService for session/state management and integrate with existing MCP services over HTTP.

## Architecture

The root agent will:

- Use Google ADK framework with InMemorySessionService for sessions, state, and memory
- Expose an HTTP interface (ADK web transport) on a configurable port
- Connect to existing MCP agents via HTTP:
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - data-discovery-agent: http://localhost:8080
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - query-generation-agent: http://localhost:8081
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - data-planning-agent: http://localhost:8082
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - data-graphql-agent: http://localhost:8083
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - apollo-mcp: http://localhost:8084
- Implement three operational modes with mode-specific tools
- Support stateful multi-step workflows with user confirmations

## Implementation Plan

### 1. Project Setup and Structure

**Create project directory:**

```
/home/user/git/data-orchestration-agent/
├── pyproject.toml              # Poetry dependencies
├── .env.example                # Environment variable template
├── .gitignore                  # Git ignore patterns
├── README.md                   # Project documentation
├── src/
│   └── data_orchestration_agent/
│       ├── __init__.py
│       ├── main.py            # ADK agent entry point
│       ├── config.py          # Configuration management
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── root_agent.py  # Main orchestration agent
│       │   └── modes.py       # Mode detection logic
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── ask_mode_tools.py      # Ask mode tools
│       │   ├── planning_mode_tools.py  # Planning mode tools
│       │   └── action_mode_tools.py    # Action mode tools
│       ├── clients/
│       │   ├── __init__.py
│       │   ├── discovery_client.py    # Data discovery HTTP client
│       │   ├── query_gen_client.py    # Query generation HTTP client
│       │   ├── planning_client.py     # Planning agent HTTP client
│       │   ├── graphql_client.py      # GraphQL agent HTTP client
│       │   └── apollo_mcp_client.py   # Apollo MCP HTTP client
│       └── utils/
│           ├── __init__.py
│           └── session_helpers.py     # Session state utilities
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── unit/
    │   ├── test_tools.py
    │   └── test_clients.py
    └── integration/
        └── test_workflows.py
```

**Key dependencies in `pyproject.toml`:**

- `google-adk` - Agent Development Kit framework
- `httpx` - Async HTTP client for MCP services
- `pydantic` - Data validation and settings
- `python-dotenv` - Environment management

### 2. Configuration Management

**File: `src/data_orchestration_agent/config.py`**

Create a configuration class using Pydantic that loads from environment variables:

- Service URLs (data-discovery, query-gen, planning, graphql, apollo-mcp)
- ADK agent configuration (model, port, host)
- Session timeout settings
- Mode-specific settings

Use `load_dotenv()` and `os.getenv()` pattern following workspace rules. Create `.env.example` with placeholders.

### 3. HTTP Clients for MCP Services

**Files in `src/data_orchestration_agent/clients/`**

Create typed HTTP client wrappers for each MCP service:

**`discovery_client.py`**: Wraps data-discovery-agent endpoints

- `query_data_assets(query, filters)` → calls `/mcp/call-tool` with `query_data_assets` tool
- `get_asset_details(project_id, dataset_id, table_id)` → calls `get_asset_details` tool
- `discover_from_prp(prp_markdown, target_schema)` → calls `discover_from_prp` tool

**`query_gen_client.py`**: Wraps query-generation-agent endpoints

- `generate_queries(insight, datasets, max_queries, max_iterations)` → calls `generate_queries` tool
- Handle both sync and async responses, poll task status if needed

**`planning_client.py`**: Wraps data-planning-agent endpoints

- `start_planning_session(initial_intent)` → calls `start_planning_session` tool
- `continue_conversation(session_id, user_response)` → calls `continue_conversation` tool
- `generate_data_prp(session_id)` → calls `generate_data_prp` tool

**`graphql_client.py`**: Wraps data-graphql-agent endpoints

- `generate_graphql_api(queries, project_name, validation_level)` → calls `generate_graphql_api` tool

**`apollo_mcp_client.py`**: Wraps Apollo MCP server

- `list_tools()` → get available GraphQL operations as tools
- `call_tool(name, arguments)` → execute GraphQL queries

Each client should:

- Use `httpx.AsyncClient` for async HTTP requests
- Handle errors with proper exception types
- Include timeout configuration from config
- Log requests/responses for debugging
- Return typed responses (Pydantic models or dicts)

### 4. ADK Agent Tools by Mode

**File: `src/data_orchestration_agent/tools/ask_mode_tools.py`**

Implement ADK function tools for Ask Mode:

```python
@function_tool
async def search_datasets(query: str, context: ToolContext) -> str:
    """Search for BigQuery datasets using natural language query."""
    # Call discovery_client.query_data_assets()
    # Return markdown-formatted results
```



```python
@function_tool
async def get_dataset_details(table_id: str, context: ToolContext) -> str:
    """Get detailed metadata for a specific BigQuery table."""
    # Parse table_id (project.dataset.table)
    # Call discovery_client.get_asset_details()
```



```python
@function_tool
async def query_graphql_data(operation_name: str, variables: dict, context: ToolContext) -> str:
    """Execute GraphQL query via Apollo MCP server."""
    # Call apollo_mcp_client.call_tool()
    # Return formatted results
```



```python
@function_tool
async def list_graphql_operations(context: ToolContext) -> str:
    """List available GraphQL operations from Apollo MCP."""
    # Call apollo_mcp_client.list_tools()
```

**File: `src/data_orchestration_agent/tools/planning_mode_tools.py`**

Implement ADK function tools for Planning Mode:

```python
@function_tool
async def start_planning(initial_intent: str, context: ToolContext) -> str:
    """Start a planning session to gather requirements for a data product."""
    # Call planning_client.start_planning_session()
    # Store session_id in session.state using context.session.state
    # Return questions to user
```



```python
@function_tool
async def answer_planning_questions(user_response: str, context: ToolContext) -> str:
    """Continue planning conversation with user responses."""
    # Retrieve session_id from context.session.state
    # Call planning_client.continue_conversation()
    # Update state with is_complete status
    # Return next questions or completion message
```



```python
@function_tool
async def generate_prp(context: ToolContext) -> str:
    """Generate the final Data Product Requirement Prompt (PRP)."""
    # Retrieve session_id from context.session.state
    # Call planning_client.generate_data_prp()
    # Store PRP text in session.state["prp_text"]
    # Return success message with PRP summary
```

**File: `src/data_orchestration_agent/tools/action_mode_tools.py`**

Implement ADK function tools for Action Mode:

```python
@function_tool
async def discover_sources_from_prp(context: ToolContext) -> str:
    """Discover source tables from PRP Section 9 requirements."""
    # Retrieve prp_text from context.session.state
    # Extract target schemas from PRP (similar to integrated_workflow_example.py)
    # Call discovery_client.discover_from_prp()
    # Store discovered_datasets in session.state
    # Return summary with user confirmation prompt
```



```python
@function_tool
async def generate_queries_from_discovery(approve_discovery: bool, context: ToolContext) -> str:
    """Generate SQL queries from discovered datasets (after user confirmation)."""
    # Check approve_discovery flag
    # Retrieve discovered_datasets from context.session.state
    # For each target table, call query_gen_client.generate_queries()
    # Store query_results in session.state
    # Return summary with user confirmation prompt
```



```python
@function_tool
async def create_graphql_api(approve_queries: bool, project_name: str, context: ToolContext) -> str:
    """Generate GraphQL API from validated queries (after user confirmation)."""
    # Check approve_queries flag
    # Retrieve query_results from context.session.state
    # Call graphql_client.generate_graphql_api()
    # Store graphql_output_path in session.state
    # Return success message with file paths
```



```python
@function_tool
async def iterate_on_step(step_name: str, modifications: str, context: ToolContext) -> str:
    """Allow user to request modifications to a previous step."""
    # step_name: "discovery", "queries", or "graphql"
    # modifications: user's requested changes
    # Re-execute the appropriate step with modifications
    # Update session.state accordingly
```

### 5. Mode Detection Logic

**File: `src/data_orchestration_agent/agents/modes.py`**

Create an enum and detection logic:

```python
from enum import Enum

class AgentMode(Enum):
    ASK = "ask"
    PLANNING = "planning"
    ACTION = "action"

def detect_mode(user_message: str, session_state: dict) -> AgentMode:
    """Detect which mode the user wants based on message and state."""
    # Check session state for active planning session or PRP
    # Use keyword detection or LLM-based classification
    # Return appropriate mode
```

### 6. Root Agent Implementation

**File: `src/data_orchestration_agent/agents/root_agent.py`**

Create the main ADK agent:

```python
from google.adk.agents import LLMAgent
from google.adk.sessions import InMemorySessionService, InMemoryMemoryService
from ..tools.ask_mode_tools import search_datasets, get_dataset_details, query_graphql_data, list_graphql_operations
from ..tools.planning_mode_tools import start_planning, answer_planning_questions, generate_prp
from ..tools.action_mode_tools import discover_sources_from_prp, generate_queries_from_discovery, create_graphql_api, iterate_on_step

def create_orchestration_agent(config):
    """Create the root orchestration agent."""
    
    # Initialize services
    session_service = InMemorySessionService()
    memory_service = InMemoryMemoryService()
    
    # Define agent instruction
    instruction = """
    You are a Data Orchestration Agent that helps users with data discovery, planning, and execution.
    
    You have three operational modes:
    
    1. ASK MODE: Help users explore available datasets and GraphQL data
       - Use search_datasets to find BigQuery tables
       - Use get_dataset_details for detailed table information
       - Use list_graphql_operations and query_graphql_data for GraphQL queries
    
    2. PLANNING MODE: Guide users through creating Data Product Requirement Prompts (PRPs)
       - Use start_planning to begin a planning session
       - Use answer_planning_questions to continue the conversation
       - Use generate_prp to create the final PRP document
    
    3. ACTION MODE: Execute PRPs to build data products
       - Use discover_sources_from_prp to find source tables
       - Use generate_queries_from_discovery to create SQL queries
       - Use create_graphql_api to generate the GraphQL API
       - After each step, ask for user confirmation before proceeding
       - Use iterate_on_step if the user wants modifications
    
    Always ask the user which mode they want to use if it's unclear.
    Track workflow state in the session to provide continuity across turns.
    """
    
    # Create agent
    agent = LLMAgent(
        name="data-orchestration-agent",
        model=config.model_name,  # e.g., "gemini-2.0-flash"
        instruction=instruction,
        description="Root agent for data discovery, planning, and product creation",
        tools=[
            # Ask mode tools
            search_datasets,
            get_dataset_details,
            list_graphql_operations,
            query_graphql_data,
            # Planning mode tools
            start_planning,
            answer_planning_questions,
            generate_prp,
            # Action mode tools
            discover_sources_from_prp,
            generate_queries_from_discovery,
            create_graphql_api,
            iterate_on_step,
        ],
        session_service=session_service,
        memory_service=memory_service,
    )
    
    return agent, session_service
```

### 7. Main Entry Point

**File: `src/data_orchestration_agent/main.py`**

Create the ADK web server entry point:

```python
from google.adk.web import create_app
from .config import load_config
from .agents.root_agent import create_orchestration_agent
from .clients import (
    DiscoveryClient,
    QueryGenClient,
    PlanningClient,
    GraphQLClient,
    ApolloMCPClient,
)

def main():
    """Start the orchestration agent web server."""
    # Load configuration
    config = load_config()
    
    # Initialize HTTP clients
    discovery_client = DiscoveryClient(config.discovery_url)
    query_gen_client = QueryGenClient(config.query_gen_url)
    planning_client = PlanningClient(config.planning_url)
    graphql_client = GraphQLClient(config.graphql_url)
    apollo_mcp_client = ApolloMCPClient(config.apollo_mcp_url)
    
    # Create agent
    agent, session_service = create_orchestration_agent(config)
    
    # Create ADK web app
    app = create_app(
        agent=agent,
        session_service=session_service,
        host=config.host,
        port=config.port,
    )
    
    # Start server
    print(f"Starting Data Orchestration Agent on {config.host}:{config.port}")
    app.run()

if __name__ == "__main__":
    main()
```

### 8. Environment Configuration

**File: `.env.example`**

```bash
# Agent Configuration
AGENT_MODEL=gemini-2.0-flash-001
AGENT_HOST=0.0.0.0
AGENT_PORT=8085

# MCP Service URLs
DISCOVERY_AGENT_URL=http://localhost:8080
QUERY_GEN_AGENT_URL=http://localhost:8081
PLANNING_AGENT_URL=http://localhost:8082
GRAPHQL_AGENT_URL=http://localhost:8083
APOLLO_MCP_URL=http://localhost:8084

# GCP Configuration (for agent model access)
GCP_PROJECT_ID=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# Timeouts and Limits
HTTP_TIMEOUT=300.0
MAX_PLANNING_TURNS=10
MAX_QUERIES_PER_TARGET=3
MAX_QUERY_ITERATIONS=10
```

### 9. Testing Strategy

**Unit Tests:**

- Test each HTTP client with mocked responses
- Test tool functions with mocked clients
- Test mode detection logic
- Test session state management

**Integration Tests:**

- Test full Ask Mode workflow (requires mock MCP services)
- Test full Planning Mode workflow
- Test full Action Mode workflow
- Test mode transitions

### 10. Documentation

**File: `README.md`**

Document:

- Architecture overview with diagram
- Installation and setup instructions
- Running the agent (web interface)
- Mode descriptions with examples
- Environment variables reference
- API endpoints exposed by ADK web server
- Troubleshooting guide

Include example usage for each mode and explain the workflow progression in Action Mode.

## Key Implementation Details

**Session State Schema:**

```python
{
    "current_mode": "ask|planning|action",
    "planning_session_id": "...",  # From planning agent
    "planning_complete": False,
    "prp_text": "...",  # Generated PRP
    "discovered_datasets": [...],  # From discovery
    "query_results": [...],  # From query generation
    "graphql_output_path": "...",  # From GraphQL generation
    "action_step": "discovery|queries|graphql|complete",
    "pending_confirmation": "...",  # Waiting for user approval
}
```

**Error Handling:**

- Wrap all HTTP calls in try-except with proper error messages
- Store error states in session for recovery
- Provide clear guidance to users on how to retry or modify

**User Confirmation Pattern:**

After each Action Mode step:

1. Present results summary to user
2. Ask: "Would you like to proceed, iterate, or cancel?"
3. Based on response, either continue or call `iterate_on_step` tool

## References

- Google ADK Sessions: https://google.github.io/adk-docs/sessions/session/
- Google ADK State Management: https://google.github.io/adk-docs/sessions/state/
- Google ADK Memory: https://google.github.io/adk-docs/sessions/memory/
- Apollo MCP Server: https://www.apollographql.com/docs/apollo-mcp-server
- Integrated Workflow Example: `query-generation-agent/examples/integrated_workflow_example.py`

### To-dos

- [ ] Create project directory structure at /home/user/git/data-orchestration-agent with Poetry configuration
- [ ] Implement configuration management with Pydantic and environment variables
- [ ] Create HTTP client wrappers for all five MCP services (discovery, query-gen, planning, graphql, apollo)
- [ ] Implement ADK function tools for Ask Mode (search datasets, get details, GraphQL queries)
- [ ] Implement ADK function tools for Planning Mode (start session, answer questions, generate PRP)
- [ ] Implement ADK function tools for Action Mode (discover, generate queries, create GraphQL API)
- [ ] Create root ADK agent with InMemorySessionService and all mode tools integrated
- [ ] Implement main entry point with ADK web transport and server configuration
- [ ] Write unit and integration tests for clients, tools, and workflows
- [ ] Create README with architecture, setup instructions, and usage examples for all three modes