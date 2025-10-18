# data-discovery-agent

An ADK agent that profiles data in a dataset and dynamically creates context for the data.

## Setup

1. **Install Poetry** (if not already installed):
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. **Install dependencies**:
   ```bash
   poetry install
   ```

3. **Set up your environment**:
   - Create a `.env` file in the project root
   - Add your Google API key:
     ```
     GOOGLE_API_KEY=your_api_key_here
     ```
   - Get your API key from: https://aistudio.google.com/apikey

## Usage

Run the example:
```bash
poetry run python example_usage.py
```

Or use the ADK CLI to interact with your agent:
```bash
poetry run adk chat data_discovery_agent.agents.data_profiler
```

## Project Structure

```
data-discovery-agent/
├── src/
│   └── data_discovery_agent/
│       ├── __init__.py
│       └── agents/
│           ├── __init__.py
│           └── data_profiler/
│               ├── __init__.py
│               └── agent.py          # Main agent definition (root_agent)
├── example_usage.py                  # Example usage script
├── pyproject.toml                    # Poetry configuration
└── README.md                         # This file
```

## Adding More Agents

To add a new agent:

1. Create a new directory under `src/data_discovery_agent/agents/`
2. Add `__init__.py` with: `from . import agent`
3. Add `agent.py` with your agent definition: `root_agent = Agent(...)`

## Development

Run tests:
```bash
poetry run pytest
```

Format code:
```bash
poetry run black .
```

Lint code:
```bash
poetry run ruff check .
```
