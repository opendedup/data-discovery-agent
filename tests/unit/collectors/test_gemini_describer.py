"""Unit tests for GeminiDescriber."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest
import os

from data_discovery_agent.collectors.gemini_describer import GeminiDescriber

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture


@pytest.mark.unit
@pytest.mark.collectors
class TestGeminiDescriber:
    """Tests for GeminiDescriber class."""

    def test_init_with_api_key(self, mock_env: dict[str, str]) -> None:
        """Test initialization with API key."""
        describer = GeminiDescriber(api_key="test-api-key")

        assert describer.api_key == "test-api-key"
        assert describer.model_name == "gemini-2.5-flash"
        assert describer.enabled is True

    def test_init_without_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test initialization without API key."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        describer = GeminiDescriber()

        assert describer.api_key is None
        assert describer.enabled is False

    def test_init_with_env_api_key(self, mocker: MockerFixture) -> None:
        """Test initialization with API key from environment variable."""
        mocker.patch.dict(os.environ, {"GEMINI_API_KEY": "env-key"})
        describer = GeminiDescriber()
        assert describer.api_key == "env-key"
        assert describer.is_enabled

    @patch("data_discovery_agent.collectors.gemini_describer.genai")
    def test_generate_description_success(
        self, mock_genai: Mock, mocker: MockerFixture
    ) -> None:
        """Test successful description generation."""
        # Mock Gemini model
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = "This is a test table containing user information."
        mock_genai.GenerativeModel.return_value.generate_content.return_value = (
            mock_response
        )

        describer = GeminiDescriber(api_key="test-key")

        table_metadata = {
            "table_id": "users",
            "schema": [{"name": "id", "type": "STRING"}, {"name": "name", "type": "STRING"}],
        }

        description = describer.generate_table_description(
            table_name=table_metadata["table_id"], schema=table_metadata["schema"]
        )

        assert description is not None
        assert "user" in description.lower()
        mock_genai.GenerativeModel.return_value.generate_content.assert_called_once()
        assert description == "This is a test table containing user information."

    @patch("data_discovery_agent.collectors.gemini_describer.genai")
    def test_generate_description_disabled(
        self, mock_genai: Mock, mocker: MockerFixture
    ) -> None:
        """Test that description generation is skipped if the client is disabled."""
        mocker.patch.dict(os.environ, clear=True)
        mocker.patch(
            "data_discovery_agent.collectors.gemini_describer.os.getenv",
            return_value=None,
        )
        # Initialize without API key to disable the client
        describer = GeminiDescriber(api_key=None)
        assert not describer.is_enabled

        table_metadata = {
            "table_id": "users",
            "schema": [
                {"name": "id", "type": "STRING"},
                {"name": "name", "type": "STRING"},
            ],
        }
        description = describer.generate_table_description(
            table_name=table_metadata["table_id"], schema=[]
        )

        assert description is None
        mock_genai.GenerativeModel.assert_not_called()

    @patch("data_discovery_agent.collectors.gemini_describer.genai")
    @patch("data_discovery_agent.collectors.gemini_describer.time.sleep")
    def test_retry_on_rate_limit(self, mock_sleep: Mock, mock_genai: Mock) -> None:
        """Test retry logic on rate limit errors."""
        mock_model = Mock()
        
        # First call raises rate limit error, second succeeds
        mock_response = Mock()
        mock_response.text = "Generated description"
        mock_model.generate_content.side_effect = [
            Exception("429 Resource Exhausted"),
            mock_response,
        ]
        mock_genai.GenerativeModel.return_value = mock_model

        describer = GeminiDescriber(api_key="test-key", max_retries=2)

        table_metadata = {"table_id": "users"}

        description = describer.generate_table_description(
            table_name=table_metadata["table_id"], schema=[]
        )

        assert description == "Generated description"
        assert mock_model.generate_content.call_count == 2
        mock_sleep.assert_called()

    @patch("data_discovery_agent.collectors.gemini_describer.genai")
    def test_prompt_construction(self, mock_genai: Mock) -> None:
        """Test that prompt is constructed properly."""
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = "Test description"
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        describer = GeminiDescriber(api_key="test-key")

        table_metadata = {
            "table_id": "customer_orders",
            "dataset_id": "sales",
            "schema": [
                {"name": "order_id", "type": "STRING"},
                {"name": "customer_id", "type": "STRING"},
                {"name": "amount", "type": "FLOAT64"},
            ],
        }

        description = describer.generate_table_description(
            table_name=f'{table_metadata.get("dataset_id", "dataset")}.{table_metadata["table_id"]}',
            schema=table_metadata["schema"],
        )

        # Verify prompt includes key information
        call_args = mock_model.generate_content.call_args
        prompt = call_args[0][0]
        assert "customer_orders" in prompt
        assert "order_id" in prompt or "schema" in prompt.lower()

    @patch("data_discovery_agent.collectors.gemini_describer.genai")
    def test_handles_api_errors(self, mock_genai: Mock) -> None:
        """Test handling of API errors."""
        mock_model = Mock()
        mock_model.generate_content.side_effect = Exception("API Error")
        mock_genai.GenerativeModel.return_value = mock_model

        describer = GeminiDescriber(api_key="test-key", max_retries=1)

        table_metadata = {"table_id": "users"}

        # Should handle error gracefully
        description = describer.generate_table_description(
            table_name=table_metadata["table_id"], schema=[]
        )
        
        assert description is None or "error" in description.lower()

    @patch("data_discovery_agent.collectors.gemini_describer.genai")
    def test_response_sanitization(self, mock_genai: Mock) -> None:
        """Test that responses are sanitized properly."""
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = "   Description with extra whitespace   \n\n"
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        describer = GeminiDescriber(api_key="test-key")

        table_metadata = {"table_id": "users"}

        description = describer.generate_table_description(
            table_name=table_metadata["table_id"], schema=[]
        )

        assert description is not None
        assert not description.startswith(" ")
        assert not description.endswith(" ")

    def test_custom_model_name(self) -> None:
        """Test initialization with custom model name."""
        describer = GeminiDescriber(
            api_key="test-key", model_name="gemini-pro"
        )

        assert describer.model_name == "gemini-pro"

