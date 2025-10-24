"""
Tests for the SchemaValidator client.
"""
from unittest.mock import MagicMock, patch
import pytest
from google.generativeai.types import GenerateContentResponse

from data_discovery_agent.clients.schema_validator import SchemaValidator, ValidationResult
from data_discovery_agent.schemas.search_planning import TargetColumn

@pytest.fixture
def mock_validator_response() -> MagicMock:
    """Creates a mock of the Gemini GenerateContentResponse for the validator."""
    mock_response = MagicMock(spec=GenerateContentResponse)
    
    # The expected parsed output
    mock_response.parsed = ValidationResult(
        is_good_fit=True,
        reasoning="This is a good fit because the columns align conceptually."
    )
    mock_response.text = '{"is_good_fit": true, "reasoning": "..."}'
    return mock_response

def test_validator_success(mock_validator_response):
    """
    Tests that the SchemaValidator correctly parses a successful (is_good_fit: true)
    response from the Gemini API.
    """
    with patch('google.generativeai.GenerativeModel.generate_content') as mock_generate_content:
        mock_generate_content.return_value = mock_validator_response
        
        validator = SchemaValidator(gemini_api_key="test_key")
        
        is_valid = validator.validate_schema(
            source_schema=[{"name": "pred_spread", "type": "FLOAT"}],
            target_columns=[TargetColumn(name="predicted_spread", type="float", description="...")],
            conceptual_group="Model Predictions",
            source_table_name="test.predictions"
        )
        
        assert is_valid is True
        mock_generate_content.assert_called_once()
        
        # Verify the prompt contains the contextual information
        call_args, _ = mock_generate_content.call_args
        prompt = call_args[0]
        assert 'CONTEXT: We are searching for data for the conceptual group: "Model Predictions"' in prompt
        assert '"name": "predicted_spread"' in prompt
        assert '"name": "pred_spread"' in prompt

def test_validator_failure_from_llm():
    """
    Tests that the SchemaValidator correctly returns False when the LLM
    indicates the source is not a good fit.
    """
    # Create a mock response for a "false" case
    mock_response_false = MagicMock(spec=GenerateContentResponse)
    mock_response_false.parsed = ValidationResult(is_good_fit=False, reasoning="Poor fit.")
    
    with patch('google.generativeai.GenerativeModel.generate_content') as mock_generate_content:
        mock_generate_content.return_value = mock_response_false
        
        validator = SchemaValidator(gemini_api_key="test_key")
        
        is_valid = validator.validate_schema(
            source_schema=[],
            target_columns=[],
            conceptual_group="Some Group",
            source_table_name="test.table"
        )
        
        assert is_valid is False

def test_validator_api_error():
    """
    Tests that the SchemaValidator returns False if the Gemini API call fails.
    """
    with patch('google.generativeai.GenerativeModel.generate_content') as mock_generate_content:
        mock_generate_content.side_effect = Exception("API failure")
        
        validator = SchemaValidator(gemini_api_key="test_key")
        
        is_valid = validator.validate_schema(
            source_schema=[],
            target_columns=[],
            conceptual_group="Some Group",
            source_table_name="test.table"
        )
        
        assert is_valid is False
