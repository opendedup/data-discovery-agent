"""
Tests for the PRPRequirementDiscovery orchestrator client.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock

# Fixtures for PRP and target schema
from .test_search_planner import sample_prp, sample_target_schema

from data_discovery_agent.clients.prp_requirement_discovery import PRPRequirementDiscovery
from data_discovery_agent.schemas.search_planning import SearchPlan, SearchStep, TargetColumn

@pytest.fixture
def mock_search_plan() -> SearchPlan:
    """Provides a sample mock SearchPlan object."""
    return [
        SearchStep(
            conceptual_group="Model Predictions",
            search_query="Query for predictions",
            target_columns_for_validation=[TargetColumn(name="predicted_spread", type="float", description="...")]
        ),
        SearchStep(
            conceptual_group="Actual Game Results",
            search_query="Query for game results",
            target_columns_for_validation=[TargetColumn(name="actual_spread", type="float", description="...")]
        )
    ]

@pytest.fixture
def mock_clients(mock_search_plan: SearchPlan) -> dict:
    """Provides mock versions of the clients used by the orchestrator."""
    mock_search_planner = MagicMock()
    mock_search_planner.create_search_plan.return_value = mock_search_plan
    
    # Mock Vertex Search Client to return some dummy candidates
    mock_vertex_client = MagicMock()
    mock_search_response = MagicMock()
    # Simulate two candidate results for each search call
    mock_candidate = MagicMock()
    mock_candidate.metadata.project_id = "proj"
    mock_candidate.metadata.dataset_id = "dset"
    mock_candidate.metadata.table_id = "table1"
    mock_candidate.metadata.schema = [{"name": "col1"}]
    mock_candidate.score = 0.9
    mock_search_response.results = [mock_candidate, mock_candidate]
    mock_vertex_client.search = MagicMock(return_value=mock_search_response)
    
    # Mock Schema Validator. Let's say the first candidate is valid, the second is not.
    mock_schema_validator = MagicMock()
    mock_schema_validator.validate_schema.side_effect = [True, False, True, False] # For two search steps
    
    return {
        "search_planner": mock_search_planner,
        "vertex_client": mock_vertex_client,
        "schema_validator": mock_schema_validator
    }

@pytest.mark.asyncio
async def test_orchestrator_workflow(sample_prp, sample_target_schema, mock_clients):
    """
    Tests the full orchestration workflow of PRPRequirementDiscovery.
    """
    # Initialize the orchestrator with mocked clients
    orchestrator = PRPRequirementDiscovery(
        vertex_client=mock_clients["vertex_client"],
        search_planner=mock_clients["search_planner"],
        schema_validator=mock_clients["schema_validator"]
    )
    
    # Run the discovery process
    results = await orchestrator.discover_for_prp(
        prp_markdown=sample_prp,
        target_schema=sample_target_schema,
        max_results_per_query=5
    )
    
    # 1. Verify that the search planner was called correctly
    mock_clients["search_planner"].create_search_plan.assert_called_once_with(
        sample_prp, sample_target_schema
    )
    
    # 2. Verify that the vertex client (search) was called for each step in the plan
    assert mock_clients["vertex_client"].search.call_count == 2
    
    # 3. Verify that the schema validator was called for each candidate (2 candidates * 2 steps)
    assert mock_clients["schema_validator"].validate_schema.call_count == 4
    
    # 4. Check the final aggregated results
    assert len(results) == 2 # One result object per search step
    
    # Check the first result group
    result_step1 = results[0]
    assert result_step1["conceptual_group"] == "Model Predictions"
    assert len(result_step1["discovered_tables"]) == 1 # Only one was validated as True
    assert result_step1["discovered_tables"][0]["table_id"] == "table1"

    # Check the second result group
    result_step2 = results[1]
    assert result_step2["conceptual_group"] == "Actual Game Results"
    assert len(result_step2["discovered_tables"]) == 1 # Only one was validated as True

