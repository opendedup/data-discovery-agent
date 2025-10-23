"""
Unit tests for PRPDiscoveryClient
"""

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from typing import TYPE_CHECKING

from src.data_discovery_agent.clients.prp_client import PRPDiscoveryClient
from src.data_discovery_agent.schemas.asset_schema import DiscoveredAssetDict

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture


@pytest.fixture
def mock_vertex_client(mocker: "MockerFixture") -> Mock:
    """Create a mock Vertex Search client."""
    mock_client = mocker.Mock()
    return mock_client


@pytest.fixture
def mock_gemini_describer(mocker: "MockerFixture") -> Mock:
    """Create a mock Gemini describer."""
    mock_describer = mocker.Mock()
    mock_describer.is_enabled = True
    return mock_describer


@pytest.fixture
def prp_client(
    mock_vertex_client: Mock,
    mocker: "MockerFixture"
) -> PRPDiscoveryClient:
    """Create PRPDiscoveryClient with mocked dependencies."""
    with patch(
        "src.data_discovery_agent.clients.prp_client.GeminiDescriber"
    ) as mock_gemini_class:
        mock_gemini_instance = mocker.Mock()
        mock_gemini_instance.is_enabled = True
        mock_gemini_class.return_value = mock_gemini_instance
        
        client = PRPDiscoveryClient(
            vertex_client=mock_vertex_client,
            gemini_api_key="test-key",
            max_queries=5,
            min_relevance_score=60.0,
        )
        
        # Replace the gemini instance with our mock
        client.gemini = mock_gemini_instance
        
        return client


@pytest.fixture
def sample_prp_text() -> str:
    """Sample PRP text for testing."""
    return """
# Data Product Requirement Prompt

## 1. Product Type
Decision Framework

## 2. Business Objective
To support player acquisition decisions by providing comprehensive historical performance comparison.

## 4. Key Metrics
- **Historical Performance Averages:** Mean, median, standard deviation of fantasy points per game
- **Performance Consistency:** Percentage of games above/below performance tiers
- **Performance Trends:** Rolling average of fantasy points over N games

## 5. Dimensions & Breakdowns
- **Player:** The primary entity for comparison
- **Time:** Season, Week, Rolling N-game periods
- **Opponent Quality:** Top-10, Mid-Tier, Bottom-10 based on defensive rankings

## 9. Data Requirements
Based on available data:
1. Historical player game-by-game statistics in the Lfndata domain
2. Historical game schedules in the Abndata domain
3. Team defensive rankings
"""


@pytest.mark.asyncio
async def test_discover_datasets_for_prp_success(
    prp_client: PRPDiscoveryClient,
    sample_prp_text: str,
    mocker: "MockerFixture"
) -> None:
    """Test successful dataset discovery from PRP."""
    # Mock query generation
    mock_queries = [
        "fantasy points player statistics",
        "game schedules opponent",
        "defensive rankings team"
    ]
    mock_refinements = []
    mocker.patch.object(
        prp_client,
        "_generate_queries_from_prp",
        return_value=(mock_queries, mock_refinements)
    )
    
    # Mock candidate search - return 3+ to avoid triggering fan-out
    mock_candidates = {
        "proj.dataset.table1": {
            "table_id": "table1",
            "project_id": "proj",
            "dataset_id": "dataset",
            "description": "Player statistics",
            "relevance_score": 85.0,
        },
        "proj.dataset.table2": {
            "table_id": "table2",
            "project_id": "proj",
            "dataset_id": "dataset",
            "description": "Game schedules",
            "relevance_score": 80.0,
        },
        "proj.dataset.table3": {
            "table_id": "table3",
            "project_id": "proj",
            "dataset_id": "dataset",
            "description": "Defensive rankings",
            "relevance_score": 75.0,
        },
    }
    from src.data_discovery_agent.clients.prp_client import QueryExecution
    mock_query_executions = [
        QueryExecution(
            query=mock_queries[0],
            results_count=10,
            execution_time_ms=150.0,
            top_tables=["proj.dataset.table1", "proj.dataset.table2", "proj.dataset.table3"],
            status="success"
        )
    ]
    mocker.patch.object(
        prp_client,
        "_search_for_candidates",
        return_value=(mock_candidates, mock_query_executions)
    )
    
    # Mock relevance scoring
    scored_datasets = [
        {**mock_candidates["proj.dataset.table1"], "relevance_score": 85.0},
        {**mock_candidates["proj.dataset.table2"], "relevance_score": 80.0},
        {**mock_candidates["proj.dataset.table3"], "relevance_score": 75.0},
    ]
    mocker.patch.object(
        prp_client,
        "_score_dataset_relevance",
        return_value=scored_datasets
    )
    
    # Execute discovery
    result = await prp_client.discover_datasets_for_prp(
        prp_text=sample_prp_text,
        max_results=10
    )
    
    # Assertions
    assert result["total_count"] == 3
    assert len(result["datasets"]) == 3
    assert result["datasets"][0]["relevance_score"] == 85.0
    
    # Check metadata
    assert "discovery_metadata" in result
    metadata = result["discovery_metadata"]
    assert "queries_executed" in metadata
    assert "refinements_made" in metadata
    assert "summary" in metadata
    assert len(metadata["queries_executed"]) == 1
    assert metadata["summary"]["total_queries_generated"] == 1


@pytest.mark.asyncio
async def test_discover_datasets_no_candidates(
    prp_client: PRPDiscoveryClient,
    sample_prp_text: str,
    mocker: "MockerFixture"
) -> None:
    """Test discovery when no candidates are found."""
    # Mock query generation
    mocker.patch.object(
        prp_client,
        "_generate_queries_from_prp",
        return_value=(["test query"], [])
    )
    
    # Mock empty search results
    from src.data_discovery_agent.clients.prp_client import QueryExecution
    mocker.patch.object(
        prp_client,
        "_search_for_candidates",
        return_value=({}, [QueryExecution(
            query="test query",
            results_count=0,
            execution_time_ms=100.0,
            top_tables=[],
            status="no_results"
        )])
    )
    
    result = await prp_client.discover_datasets_for_prp(
        prp_text=sample_prp_text,
        max_results=10
    )
    
    assert result["total_count"] == 0
    assert len(result["datasets"]) == 0
    assert "discovery_metadata" in result


@pytest.mark.asyncio
async def test_discover_datasets_filters_low_scores(
    prp_client: PRPDiscoveryClient,
    sample_prp_text: str,
    mocker: "MockerFixture"
) -> None:
    """Test that datasets below minimum score are filtered out."""
    # Mock query generation
    mocker.patch.object(
        prp_client,
        "_generate_queries_from_prp",
        return_value=(["test query"], [])
    )
    
    # Mock candidates
    mock_candidates = {
        "proj.dataset.high_score": {"table_id": "high_score"},
        "proj.dataset.low_score": {"table_id": "low_score"},
    }
    from src.data_discovery_agent.clients.prp_client import QueryExecution
    mocker.patch.object(
        prp_client,
        "_search_for_candidates",
        return_value=(mock_candidates, [QueryExecution(
            query="test query",
            results_count=2,
            execution_time_ms=200.0,
            top_tables=["proj.dataset.high_score", "proj.dataset.low_score"],
            status="success"
        )])
    )
    
    # Mock scoring with one high and one low score
    scored_datasets = [
        {**mock_candidates["proj.dataset.high_score"], "relevance_score": 75.0},
        {**mock_candidates["proj.dataset.low_score"], "relevance_score": 45.0},
    ]
    mocker.patch.object(
        prp_client,
        "_score_dataset_relevance",
        return_value=scored_datasets
    )
    
    result = await prp_client.discover_datasets_for_prp(
        prp_text=sample_prp_text,
        max_results=10
    )
    
    # Only high-scoring dataset should be returned (min_relevance_score=60.0)
    assert result["total_count"] == 1
    assert result["datasets"][0]["table_id"] == "high_score"
    assert "discovery_metadata" in result


def test_parse_queries_from_response(prp_client: PRPDiscoveryClient) -> None:
    """Test parsing queries from Gemini response."""
    response_text = """
1. fantasy points player statistics
2. game schedules opponent rankings
3. team defensive statistics
4. historical player performance data
"""
    
    queries = prp_client._parse_queries_from_response(response_text)
    
    assert len(queries) == 4
    assert "fantasy points player statistics" in queries
    assert "game schedules opponent rankings" in queries


def test_parse_queries_with_markdown(prp_client: PRPDiscoveryClient) -> None:
    """Test parsing queries with markdown formatting."""
    response_text = """
1. **fantasy points** player statistics
2. *game schedules* opponent rankings
3. "team defensive statistics"
"""
    
    queries = prp_client._parse_queries_from_response(response_text)
    
    assert len(queries) == 3
    assert "fantasy points player statistics" in queries
    assert "game schedules opponent rankings" in queries
    assert "team defensive statistics" in queries


def test_extract_keywords_from_prp(
    prp_client: PRPDiscoveryClient,
    sample_prp_text: str
) -> None:
    """Test keyword extraction fallback when Gemini is unavailable."""
    queries = prp_client._extract_keywords_from_prp(sample_prp_text)
    
    # Should extract some queries from the PRP
    assert len(queries) > 0
    # Should contain keywords from the PRP sections
    assert any(
        any(keyword in q.lower() for keyword in ["performance", "player", "lfndata", "abndata"]) 
        for q in queries
    )


def test_parse_score_from_response(prp_client: PRPDiscoveryClient) -> None:
    """Test parsing relevance score from Gemini response."""
    response_text = """85
This dataset contains all required metrics and dimensions."""
    
    score = prp_client._parse_score_from_response(response_text)
    
    assert score == 85.0


def test_parse_score_from_response_with_text(
    prp_client: PRPDiscoveryClient
) -> None:
    """Test parsing score when mixed with other text."""
    response_text = """The relevance score is 72.5 out of 100.
This dataset is a good match."""
    
    score = prp_client._parse_score_from_response(response_text)
    
    assert score == 72.5


def test_parse_score_fallback(prp_client: PRPDiscoveryClient) -> None:
    """Test score parsing fallback to neutral score."""
    response_text = "No numeric score found in this text."
    
    score = prp_client._parse_score_from_response(response_text)
    
    assert score == 50.0


def test_parse_score_clamps_to_range(prp_client: PRPDiscoveryClient) -> None:
    """Test that scores outside 0-100 are handled correctly."""
    # Test within range
    assert prp_client._parse_score_from_response("85") == 85.0
    
    # Test that scores outside 0-100 range fall back to neutral score
    # The _parse_score_from_response method only accepts scores 0-100, 
    # anything else returns the fallback
    assert prp_client._parse_score_from_response("150") == 50.0  # Fallback to neutral score


@pytest.mark.asyncio
async def test_generate_queries_gemini_failure_uses_fallback(
    prp_client: PRPDiscoveryClient,
    sample_prp_text: str,
    mocker: "MockerFixture"
) -> None:
    """Test that query generation falls back to keywords on Gemini failure."""
    # Mock Gemini to raise an exception
    prp_client.gemini._call_with_retry = Mock(side_effect=Exception("API error"))
    
    # Mock keyword extraction
    mock_keywords = ["player stats", "game data"]
    mocker.patch.object(
        prp_client,
        "_extract_keywords_from_prp",
        return_value=mock_keywords
    )
    
    queries, refinements = await prp_client._generate_queries_from_prp(sample_prp_text)
    
    assert queries == mock_keywords
    assert len(refinements) > 0
    assert refinements[0].reason.startswith("Gemini API error")


def test_convert_result_to_asset_dict(prp_client: PRPDiscoveryClient) -> None:
    """Test conversion of search result to DiscoveredAssetDict."""
    # Create mock search result
    mock_result = Mock()
    mock_result.metadata = Mock(
        table_id="test_table",
        project_id="test_project",
        dataset_id="test_dataset",
        asset_type="TABLE",
        created_at="2024-01-01T00:00:00Z",
        last_modified="2024-01-02T00:00:00Z",
        last_accessed=None,
        row_count=1000,
        column_count=10,
        size_bytes=5000000,
        has_pii=False,
        has_phi=False,
        environment="PROD",
        owner_email="test@example.com",
        tags=["analytics", "core"],
    )
    mock_result.snippet = "Test table description"
    mock_result.full_content = "# Test Table\n\nFull documentation here."
    
    asset_dict = prp_client._convert_result_to_asset_dict(mock_result)
    
    assert asset_dict["table_id"] == "test_table"
    assert asset_dict["project_id"] == "test_project"
    assert asset_dict["dataset_id"] == "test_dataset"
    assert asset_dict["description"] == "Test table description"
    assert asset_dict["row_count"] == 1000
    assert asset_dict["column_count"] == 10
    assert asset_dict["has_pii"] is False
    assert asset_dict["environment"] == "PROD"
    assert "analytics" in asset_dict["tags"]


@pytest.mark.asyncio
async def test_score_dataset_relevance_without_gemini(
    mocker: "MockerFixture",
    mock_vertex_client: Mock
) -> None:
    """Test that scoring falls back to neutral scores when Gemini unavailable."""
    # Create client with disabled Gemini
    with patch(
        "src.data_discovery_agent.clients.prp_client.GeminiDescriber"
    ) as mock_gemini_class:
        mock_gemini_instance = mocker.Mock()
        mock_gemini_instance.is_enabled = False
        mock_gemini_class.return_value = mock_gemini_instance
        
        client = PRPDiscoveryClient(
            vertex_client=mock_vertex_client,
            gemini_api_key=None,
        )
    
    mock_candidates = {
        "proj.dataset.table1": {
            "table_id": "table1",
            "project_id": "proj",
            "dataset_id": "dataset",
        }
    }
    
    scored = await client._score_dataset_relevance(
        prp_text="test prp",
        candidates=mock_candidates
    )
    
    assert len(scored) == 1
    assert scored[0]["relevance_score"] == 70.0  # Neutral fallback score


@pytest.mark.asyncio
async def test_discover_datasets_fanout_with_one_result(
    prp_client: PRPDiscoveryClient,
    sample_prp_text: str,
    mocker: "MockerFixture"
) -> None:
    """Test that fan-out is triggered when only 1 result is found."""
    # Mock primary query generation
    primary_queries = ["specific query"]
    mocker.patch.object(
        prp_client,
        "_generate_queries_from_prp",
        return_value=(primary_queries, [])
    )
    
    # Mock primary search returning 1 result
    mock_primary_candidates = {
        "proj.dataset.table1": {
            "table_id": "table1",
            "project_id": "proj",
            "dataset_id": "dataset",
            "description": "Primary result",
        }
    }
    from src.data_discovery_agent.clients.prp_client import QueryExecution
    
    # Mock fan-out query generation
    fanout_queries = ["broader query 1", "broader query 2"]
    mocker.patch.object(
        prp_client,
        "_generate_fanout_queries",
        return_value=fanout_queries
    )
    
    # Mock fan-out search returning additional results
    mock_fanout_candidates = {
        "proj.dataset.table2": {
            "table_id": "table2",
            "project_id": "proj",
            "dataset_id": "dataset",
            "description": "Fan-out result",
        }
    }
    
    # _search_for_candidates will be called twice: primary and fan-out
    search_calls = [
        (mock_primary_candidates, [QueryExecution(
            query="specific query",
            results_count=1,
            execution_time_ms=100.0,
            top_tables=["proj.dataset.table1"],
            status="success"
        )]),
        (mock_fanout_candidates, [QueryExecution(
            query="broader query 1",
            results_count=1,
            execution_time_ms=120.0,
            top_tables=["proj.dataset.table2"],
            status="success"
        )])
    ]
    mocker.patch.object(
        prp_client,
        "_search_for_candidates",
        side_effect=search_calls
    )
    
    # Mock scoring
    mocker.patch.object(
        prp_client,
        "_score_dataset_relevance",
        return_value=[
            {**mock_primary_candidates["proj.dataset.table1"], "relevance_score": 80.0},
            {**mock_fanout_candidates["proj.dataset.table2"], "relevance_score": 75.0},
        ]
    )
    
    result = await prp_client.discover_datasets_for_prp(
        prp_text=sample_prp_text,
        max_results=10
    )
    
    # Assertions
    assert result["total_count"] == 2
    assert len(result["datasets"]) == 2
    
    # Verify fan-out was triggered
    metadata = result["discovery_metadata"]
    assert metadata["summary"]["fanout_triggered"] is True
    assert metadata["summary"]["fanout_queries_count"] == 2
    
    # Verify _generate_fanout_queries was called
    prp_client._generate_fanout_queries.assert_called_once()


@pytest.mark.asyncio
async def test_discover_datasets_fanout_with_two_results(
    prp_client: PRPDiscoveryClient,
    sample_prp_text: str,
    mocker: "MockerFixture"
) -> None:
    """Test that fan-out is triggered when 2 results are found."""
    # Mock primary query generation
    mocker.patch.object(
        prp_client,
        "_generate_queries_from_prp",
        return_value=(["query1"], [])
    )
    
    # Mock primary search returning 2 results
    mock_primary_candidates = {
        "proj.dataset.table1": {"table_id": "table1", "project_id": "proj", "dataset_id": "dataset"},
        "proj.dataset.table2": {"table_id": "table2", "project_id": "proj", "dataset_id": "dataset"},
    }
    from src.data_discovery_agent.clients.prp_client import QueryExecution
    
    # Mock fan-out
    mocker.patch.object(
        prp_client,
        "_generate_fanout_queries",
        return_value=["broader query"]
    )
    
    # Search calls: primary (2 results) + fan-out (1 more result)
    search_calls = [
        (mock_primary_candidates, [QueryExecution(
            query="query1", results_count=2, execution_time_ms=100.0,
            top_tables=["proj.dataset.table1", "proj.dataset.table2"], status="success"
        )]),
        ({"proj.dataset.table3": {"table_id": "table3", "project_id": "proj", "dataset_id": "dataset"}},
         [QueryExecution(query="broader query", results_count=1, execution_time_ms=110.0,
                        top_tables=["proj.dataset.table3"], status="success")])
    ]
    mocker.patch.object(prp_client, "_search_for_candidates", side_effect=search_calls)
    
    # Mock scoring
    mocker.patch.object(
        prp_client,
        "_score_dataset_relevance",
        return_value=[
            {"table_id": "table1", "relevance_score": 80.0},
            {"table_id": "table2", "relevance_score": 75.0},
            {"table_id": "table3", "relevance_score": 70.0},
        ]
    )
    
    result = await prp_client.discover_datasets_for_prp(
        prp_text=sample_prp_text,
        max_results=10
    )
    
    # Fan-out should have been triggered
    assert result["total_count"] == 3
    assert result["discovery_metadata"]["summary"]["fanout_triggered"] is True


@pytest.mark.asyncio
async def test_discover_datasets_no_fanout_with_three_results(
    prp_client: PRPDiscoveryClient,
    sample_prp_text: str,
    mocker: "MockerFixture"
) -> None:
    """Test that fan-out is NOT triggered when 3 or more results are found."""
    # Mock primary query generation
    mocker.patch.object(
        prp_client,
        "_generate_queries_from_prp",
        return_value=(["query1"], [])
    )
    
    # Mock primary search returning 3 results
    mock_primary_candidates = {
        "proj.dataset.table1": {"table_id": "table1", "project_id": "proj", "dataset_id": "dataset"},
        "proj.dataset.table2": {"table_id": "table2", "project_id": "proj", "dataset_id": "dataset"},
        "proj.dataset.table3": {"table_id": "table3", "project_id": "proj", "dataset_id": "dataset"},
    }
    from src.data_discovery_agent.clients.prp_client import QueryExecution
    
    mocker.patch.object(
        prp_client,
        "_search_for_candidates",
        return_value=(mock_primary_candidates, [QueryExecution(
            query="query1", results_count=3, execution_time_ms=100.0,
            top_tables=list(mock_primary_candidates.keys()), status="success"
        )])
    )
    
    # Mock fan-out generation (should NOT be called)
    mock_fanout = mocker.patch.object(
        prp_client,
        "_generate_fanout_queries",
        return_value=[]
    )
    
    # Mock scoring
    mocker.patch.object(
        prp_client,
        "_score_dataset_relevance",
        return_value=[
            {"table_id": "table1", "relevance_score": 80.0},
            {"table_id": "table2", "relevance_score": 75.0},
            {"table_id": "table3", "relevance_score": 70.0},
        ]
    )
    
    result = await prp_client.discover_datasets_for_prp(
        prp_text=sample_prp_text,
        max_results=10
    )
    
    # Assertions
    assert result["total_count"] == 3
    
    # Fan-out should NOT have been triggered
    assert result["discovery_metadata"]["summary"]["fanout_triggered"] is False
    assert result["discovery_metadata"]["summary"]["fanout_queries_count"] == 0
    
    # Verify _generate_fanout_queries was NOT called
    mock_fanout.assert_not_called()


@pytest.mark.asyncio
async def test_generate_fanout_queries_with_gemini(
    prp_client: PRPDiscoveryClient,
    sample_prp_text: str,
    mocker: "MockerFixture"
) -> None:
    """Test fan-out query generation with Gemini enabled."""
    # Mock SearchFanoutGenerator
    mock_fanout_gen = mocker.Mock()
    mock_fanout_gen.generate_related_queries.return_value = [
        "player statistics",
        "game data analytics",
        "team performance metrics"
    ]
    
    # Patch SearchFanoutGenerator in the search_fanout module
    with patch(
        "src.data_discovery_agent.clients.search_fanout.SearchFanoutGenerator",
        return_value=mock_fanout_gen
    ):
        # Mock PRP summary extraction
        mocker.patch.object(
            prp_client,
            "_extract_prp_summary",
            return_value="Player performance comparison analysis"
        )
        
        fanout_queries = await prp_client._generate_fanout_queries(
            prp_text=sample_prp_text,
            primary_queries=["specific narrow query"]
        )
        
        # Assertions
        assert len(fanout_queries) == 3
        assert "player statistics" in fanout_queries
        assert "game data analytics" in fanout_queries
        
        # Verify SearchFanoutGenerator was called correctly
        mock_fanout_gen.generate_related_queries.assert_called_once_with(
            original_query="Player performance comparison analysis",
            num_queries=prp_client.max_queries
        )


@pytest.mark.asyncio
async def test_generate_fanout_queries_fallback(
    mocker: "MockerFixture",
    mock_vertex_client: Mock,
    sample_prp_text: str
) -> None:
    """Test fan-out query generation fallback when Gemini unavailable."""
    # Create client with disabled Gemini
    with patch(
        "src.data_discovery_agent.clients.prp_client.GeminiDescriber"
    ) as mock_gemini_class:
        mock_gemini_instance = mocker.Mock()
        mock_gemini_instance.is_enabled = False
        mock_gemini_class.return_value = mock_gemini_instance
        
        client = PRPDiscoveryClient(
            vertex_client=mock_vertex_client,
            gemini_api_key=None,
        )
        
        # Mock fallback method
        mock_fallback_queries = ["player data", "game data", "lfndata"]
        mocker.patch.object(
            client,
            "_generate_fallback_fanout_queries",
            return_value=mock_fallback_queries
        )
        
        fanout_queries = await client._generate_fanout_queries(
            prp_text=sample_prp_text,
            primary_queries=["specific query"]
        )
        
        # Should use fallback
        assert fanout_queries == mock_fallback_queries
        client._generate_fallback_fanout_queries.assert_called_once()


def test_extract_prp_summary(
    prp_client: PRPDiscoveryClient,
    sample_prp_text: str
) -> None:
    """Test extraction of PRP summary for fan-out queries."""
    summary = prp_client._extract_prp_summary(sample_prp_text)
    
    # Should contain objective and metrics
    assert len(summary) > 0
    assert "player acquisition" in summary.lower() or "performance comparison" in summary.lower()
    assert "Metrics:" in summary or "Historical Performance" in summary


def test_generate_fallback_fanout_queries(
    prp_client: PRPDiscoveryClient,
    sample_prp_text: str
) -> None:
    """Test fallback fan-out query generation."""
    queries = prp_client._generate_fallback_fanout_queries(
        prp_text=sample_prp_text,
        primary_queries=["narrow specific query"]
    )
    
    # Should generate some queries
    assert len(queries) > 0
    
    # Should extract entities or domains from PRP
    query_text = " ".join(queries).lower()
    # Should find at least one domain or entity
    assert any(
        term in query_text 
        for term in ["player", "game", "lfndata", "abndata", "data", "statistics"]
    )

