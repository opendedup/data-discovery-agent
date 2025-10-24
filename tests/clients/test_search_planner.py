"""
Tests for the SearchPlanner client.
"""
from unittest.mock import MagicMock, patch
import pytest
from google.generativeai.types import GenerateContentResponse

from data_discovery_agent.clients.search_planner import SearchPlanner
from data_discovery_agent.schemas.search_planning import SearchPlan, SearchStep, TargetColumn

# A fixture to load the sample PRP markdown content
@pytest.fixture
def sample_prp() -> str:
    """Returns the content of the sample PRP file."""
    with open("tests/fixtures/sample_prp.md", "r") as f:
        return f.read()

# A fixture for a sample target schema
@pytest.fixture
def sample_target_schema() -> dict:
    """Returns a sample target schema dictionary."""
    return {
        "table_name": "backtest_evaluation_view",
        "description": "A view for analyzing model backtest performance.",
        "columns": [
            {"name": "run_id", "type": "string", "description": "Identifier for a backtest run."},
            {"name": "game_id", "type": "string", "description": "Identifier for a game."},
            {"name": "predicted_spread", "type": "float", "description": "The model's predicted spread."},
            {"name": "actual_spread", "type": "float", "description": "The actual game spread."},
        ]
    }

# A fixture for a mocked Gemini API response
@pytest.fixture
def mock_gemini_response() -> MagicMock:
    """Creates a mock of the Gemini GenerateContentResponse."""
    mock_response = MagicMock(spec=GenerateContentResponse)
    
    # Create the Pydantic model structure that we expect to be parsed
    expected_plan = [
        SearchStep(
            conceptual_group="Model Predictions",
            search_query="Find tables with model prediction data including predicted_spread.",
            target_columns_for_validation=[
                TargetColumn(name="run_id", type="string", description="Identifier for a backtest run."),
                TargetColumn(name="predicted_spread", type="float", description="The model's predicted spread.")
            ]
        ),
        SearchStep(
            conceptual_group="Actual Game Results",
            search_query="Find tables with actual game results to calculate actual_spread.",
            target_columns_for_validation=[
                TargetColumn(name="game_id", type="string", description="Identifier for a game."),
                TargetColumn(name="actual_spread", type="float", description="The actual game spread.")
            ]
        )
    ]
    
    # The .parsed attribute is what the app uses, so we mock that
    mock_response.parsed = expected_plan
    
    # Also mock .text for logging/debugging purposes
    mock_response.text = '[{"conceptual_group": "Model Predictions", ...}]'
    
    return mock_response

def test_create_search_plan_success(sample_prp, sample_target_schema, mock_gemini_response):
    """
    Tests that the SearchPlanner successfully creates a search plan by calling the 
    Gemini API and parsing its structured output.
    """
    with patch('google.generativeai.GenerativeModel.generate_content') as mock_generate_content:
        # Configure the mock to return our desired response
        mock_generate_content.return_value = mock_gemini_response
        
        # Initialize the planner
        planner = SearchPlanner(gemini_api_key="test_key")
        
        # Run the method to be tested
        search_plan = planner.create_search_plan(sample_prp, sample_target_schema)
        
        # Assertions
        assert isinstance(search_plan, list)
        assert len(search_plan) == 2
        
        # Check the first step of the plan
        step1 = search_plan[0]
        assert isinstance(step1, SearchStep)
        assert step1.conceptual_group == "Model Predictions"
        assert "predicted_spread" in step1.search_query
        assert len(step1.target_columns_for_validation) == 2
        assert step1.target_columns_for_validation[0].name == "run_id"
        
        # Check that the API was called once
        mock_generate_content.assert_called_once()
        
        # Check that the prompt contains key elements
        call_args, call_kwargs = mock_generate_content.call_args
        prompt = call_args[0]
        assert "Analyze this entire PRP" in prompt
        assert "backtest_evaluation_view" in prompt # From target schema
        assert "Business Objective" in prompt # From PRP content

def test_create_search_plan_api_error(sample_prp, sample_target_schema):
    """
    Tests that the SearchPlanner raises an exception if the Gemini API call fails.
    """
    with patch('google.generativeai.GenerativeModel.generate_content') as mock_generate_content:
        # Configure the mock to raise an exception
        mock_generate_content.side_effect = Exception("API communication error")
        
        planner = SearchPlanner(gemini_api_key="test_key")
        
        # Expect an exception to be raised
        with pytest.raises(Exception, match="API communication error"):
            planner.create_search_plan(sample_prp, sample_target_schema)
