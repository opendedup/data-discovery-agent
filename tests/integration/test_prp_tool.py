"""
Integration tests for PRP Discovery Tool

Tests the end-to-end workflow of the discover_datasets_for_prp tool.
"""

import pytest
import json
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

from src.data_discovery_agent.mcp.handlers import MCPHandlers
from src.data_discovery_agent.mcp.config import MCPConfig
from src.data_discovery_agent.clients.vertex_search_client import VertexSearchClient
from google.cloud import storage

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture


@pytest.fixture
def sample_prp() -> str:
    """Sample PRP from the provided example."""
    return """
# Data Product Requirement Prompt

## 1. Product Type
Decision Framework. This is a reusable tool designed to provide a structured, data-driven comparison of players to support trade decisions.

## 2. Business Objective
To support player acquisition decisions by providing a comprehensive historical performance comparison between a target player and one or more other players. The ultimate goal is to enable users to make trades that maximize their team's scoring potential.

## 3. Product Functionality
This data product will accept a target player and a set of comparison players (e.g., players on the current roster or players being offered in a trade) as inputs. It will then generate a comparative historical analysis summarizing each player's past performance, performance trends, and situational statistics to reveal their relative value, consistency, and risk profiles.

## 4. Key Metrics
- **Historical Performance Averages:** Mean, median, and standard deviation of fantasy points per game (overall, by season).
- **Performance Consistency:** Percentage of games above/below defined performance tiers (e.g., "Boom" weeks > X points, "Bust" weeks < Y points).
- **Performance Trends:** Rolling average of fantasy points over N games to identify recent performance trajectories (e.g., improving, declining, stable).
- **Situational Performance:** Average fantasy points broken down by situational factors (e.g., vs. top/bottom-tier opponents, home vs. away games).
- **Opportunity/Usage Metrics:** Key volume statistics relevant to the player's position (e.g., pass attempts, targets, carries per game).

## 5. Dimensions & Breakdowns
- **Player:** The primary entity for comparison (Target Player, Roster Player, Trade-away Player).
- **Time:** Season, Week, Rolling N-game periods.
- **Opponent Quality:** A categorical breakdown of opponent strength (e.g., Top-10, Mid-Tier, Bottom-10) based on defensive rankings.
- **Game Context:** Home vs. Away.

## 6. Success Criteria
The product is successful if it provides a clear, multi-faceted comparison that helps a user confidently assess whether a potential trade is likely to increase their team's overall scoring output. A "good" output is one that highlights non-obvious performance patterns, trends, and situational strengths/weaknesses that are not visible from simple season-total statistics.

## 7. Usage Pattern
- **Frequency**: On-demand.
- **Audience**: Team Manager / Analyst.
- **Triggers**: Evaluating a received trade offer, considering proposing a new trade, or assessing a potential free-agent acquisition.

## 8. Example Usage Scenario
- **What inputs they provide**:
    - Target Player: "Sam Darnold"
    - Comparison Players: ["Player to Trade Away", "Current Roster Player"]
- **What outputs they get**:
    - A side-by-side report comparing the historical data for the specified players. The report includes:
        - A summary table with average points per game and consistency scores.
        - A trend chart showing their rolling 4-game performance average over the last two seasons.
        - A breakdown table showing their average points in specific situations (e.g., vs. Top-10 defenses, in away games).
- **How they make decisions with it**:
    - The user observes that while Sam Darnold has a similar season average to the "Player to Trade Away," his performance drops significantly against top-tier opponents. Given their team's difficult upcoming schedule, the user concludes the trade would likely decrease their team's total projected points and decides to decline the offer.

## 9. Data Requirements
Based on available data:
Based on the data catalog, we have:
1. data in the Lfndata domain (168.0 records) with 20.0 fields
2. data in the Abndata domain (1,104.0 records) with 68.0 fields
3. data in the Lfndata domain (2,688.0 records) with 13.0 fields

- **What data sources are needed?**
    - Historical player game-by-game statistics (e.g., passing yards, touchdowns, receptions) are required to calculate fantasy points. This data is expected to be in the `Lfndata` domain.
    - Historical game schedules, including opponent and location (home/away) for each game. This is also likely in the `Lfndata` domain.
    - Historical team defensive rankings or statistics to create the "Opponent Quality" dimension. This may need to be sourced or derived.
- **What gaps exist (if any)?**
    - A standardized fantasy scoring formula must be defined and applied.
    - A clear data source for historical weekly opponent strength/rankings may be missing and might need to be integrated.
- **What assumptions are made?**
    - We assume the `Lfndata` domain contains granular, player-level statistics for each game played.
    - We assume that historical performance and trends are meaningful indicators for evaluating future potential.
    - We assume that the available data is sufficient to construct all required metrics and dimensions.
"""


@pytest.fixture
def mock_config(mocker: "MockerFixture") -> MCPConfig:
    """Create mock MCP configuration."""
    config = mocker.Mock(spec=MCPConfig)
    config.project_id = "test-project"
    config.reports_bucket = "test-bucket"
    config.gemini_api_key = "test-gemini-key"
    config.prp_max_queries = 10
    config.prp_min_relevance_score = 60.0
    config.default_page_size = 10
    config.max_page_size = 50
    config.query_timeout = 30.0
    return config


@pytest.fixture
def mock_vertex_client(mocker: "MockerFixture") -> Mock:
    """Create mock Vertex Search client."""
    return mocker.Mock(spec=VertexSearchClient)


@pytest.fixture
def mock_storage_client(mocker: "MockerFixture") -> Mock:
    """Create mock GCS storage client."""
    return mocker.Mock(spec=storage.Client)


@pytest.fixture
def mcp_handlers(
    mock_config: MCPConfig,
    mock_vertex_client: Mock,
    mock_storage_client: Mock
) -> MCPHandlers:
    """Create MCPHandlers instance with mocked dependencies."""
    return MCPHandlers(
        config=mock_config,
        vertex_client=mock_vertex_client,
        storage_client=mock_storage_client,
    )


@pytest.mark.asyncio
async def test_handle_discover_datasets_for_prp_success(
    mcp_handlers: MCPHandlers,
    sample_prp: str,
    mocker: "MockerFixture"
) -> None:
    """Test successful PRP discovery through handler."""
    # Mock the PRP client's discover method
    mock_discovery_result = {
        "total_count": 2,
        "datasets": [
            {
                "table_id": "player_stats",
                "project_id": "test-project",
                "dataset_id": "lfndata",
                "description": "Player game statistics",
                "relevance_score": 85.0,
                "schema": [],
                "labels": [],
                "analytical_insights": [],
                "lineage": [],
                "column_profiles": [],
                "key_metrics": [],
                "run_timestamp": "2024-01-01T00:00:00Z",
                "insert_timestamp": "AUTO",
                "tags": [],
            },
            {
                "table_id": "game_schedules",
                "project_id": "test-project",
                "dataset_id": "lfndata",
                "description": "Game schedule and opponent data",
                "relevance_score": 75.0,
                "schema": [],
                "labels": [],
                "analytical_insights": [],
                "lineage": [],
                "column_profiles": [],
                "key_metrics": [],
                "run_timestamp": "2024-01-01T00:00:00Z",
                "insert_timestamp": "AUTO",
                "tags": [],
            },
        ],
        "discovery_metadata": {
            "queries_executed": [
                {
                    "query": "fantasy points player statistics",
                    "results_count": 15,
                    "execution_time_ms": 234.5,
                    "top_tables": ["test-project.lfndata.player_stats"],
                    "status": "success",
                    "error_message": None
                }
            ],
            "refinements_made": [],
            "summary": {
                "total_queries_generated": 3,
                "successful_queries": 3,
                "failed_queries": 0,
                "total_candidates_found": 45,
                "candidates_after_deduplication": 23,
                "candidates_after_scoring": 2,
                "total_execution_time_ms": 3456.78
            }
        }
    }
    
    with patch(
        "src.data_discovery_agent.clients.prp_client.PRPDiscoveryClient.discover_datasets_for_prp"
    ) as mock_discover:
        mock_discover.return_value = mock_discovery_result
        
        # Call the handler
        result = await mcp_handlers.handle_discover_datasets_for_prp({
            "prp_text": sample_prp,
            "max_results": 10
        })
    
    # Verify response format
    assert len(result) == 1
    assert result[0].type == "text"
    
    # Parse JSON response
    response_data = json.loads(result[0].text)
    
    # Assertions
    assert response_data["total_count"] == 2
    assert len(response_data["datasets"]) == 2
    assert response_data["datasets"][0]["table_id"] == "player_stats"
    assert response_data["datasets"][0]["relevance_score"] == 85.0
    assert response_data["datasets"][1]["table_id"] == "game_schedules"
    
    # Check metadata
    assert "discovery_metadata" in response_data
    metadata = response_data["discovery_metadata"]
    assert "queries_executed" in metadata
    assert "refinements_made" in metadata
    assert "summary" in metadata
    assert len(metadata["queries_executed"]) == 1
    assert metadata["summary"]["total_queries_generated"] == 3


@pytest.mark.asyncio
async def test_handle_discover_datasets_for_prp_no_results(
    mcp_handlers: MCPHandlers,
    sample_prp: str,
    mocker: "MockerFixture"
) -> None:
    """Test PRP discovery when no datasets are found."""
    mock_discovery_result = {
        "total_count": 0,
        "datasets": [],
        "discovery_metadata": {
            "queries_executed": [
                {
                    "query": "test query",
                    "results_count": 0,
                    "execution_time_ms": 100.0,
                    "top_tables": [],
                    "status": "no_results",
                    "error_message": None
                }
            ],
            "refinements_made": [],
            "summary": {
                "total_queries_generated": 1,
                "successful_queries": 0,
                "failed_queries": 0,
                "total_candidates_found": 0,
                "candidates_after_deduplication": 0,
                "candidates_after_scoring": 0,
                "total_execution_time_ms": 150.0
            }
        }
    }
    
    with patch(
        "src.data_discovery_agent.clients.prp_client.PRPDiscoveryClient.discover_datasets_for_prp"
    ) as mock_discover:
        mock_discover.return_value = mock_discovery_result
        
        result = await mcp_handlers.handle_discover_datasets_for_prp({
            "prp_text": sample_prp,
            "max_results": 10
        })
    
    response_data = json.loads(result[0].text)
    
    assert response_data["total_count"] == 0
    assert len(response_data["datasets"]) == 0
    assert "discovery_metadata" in response_data


@pytest.mark.asyncio
async def test_handle_discover_datasets_for_prp_error_handling(
    mcp_handlers: MCPHandlers,
    sample_prp: str,
    mocker: "MockerFixture"
) -> None:
    """Test error handling in PRP discovery."""
    with patch(
        "src.data_discovery_agent.clients.prp_client.PRPDiscoveryClient.discover_datasets_for_prp"
    ) as mock_discover:
        mock_discover.side_effect = Exception("API error")
        
        result = await mcp_handlers.handle_discover_datasets_for_prp({
            "prp_text": sample_prp,
            "max_results": 10
        })
    
    # Should return error response
    assert len(result) == 1
    assert "Error" in result[0].text
    assert "API error" in result[0].text


@pytest.mark.asyncio
async def test_handle_discover_datasets_respects_max_results(
    mcp_handlers: MCPHandlers,
    sample_prp: str,
    mocker: "MockerFixture"
) -> None:
    """Test that max_results parameter is respected."""
    max_results_value = 5
    
    with patch(
        "src.data_discovery_agent.clients.prp_client.PRPDiscoveryClient.discover_datasets_for_prp"
    ) as mock_discover:
        mock_discover.return_value = {
            "total_count": 0,
            "datasets": [],
            "queries_generated": []
        }
        
        await mcp_handlers.handle_discover_datasets_for_prp({
            "prp_text": sample_prp,
            "max_results": max_results_value
        })
        
        # Verify max_results was passed to discovery client
        mock_discover.assert_called_once()
        call_kwargs = mock_discover.call_args[1]
        assert call_kwargs["max_results"] == max_results_value


@pytest.mark.asyncio
async def test_handle_discover_datasets_validates_prp_text(
    mcp_handlers: MCPHandlers,
    mocker: "MockerFixture"
) -> None:
    """Test that handler validates prp_text parameter."""
    # Test with missing prp_text - should return error response
    result = await mcp_handlers.handle_discover_datasets_for_prp({
        "max_results": 10
    })
    
    # Should return an error response
    assert len(result) == 1
    assert "Error" in result[0].text
    assert "prp_text" in result[0].text

