from typing import Any, Dict, List, Optional
import logging
import re
import time
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
import json
from pydantic import BaseModel

from ..schemas.search_planning import TargetColumn

logger = logging.getLogger(__name__)


class ValidationResult(BaseModel):
    """Data model for the structured output of the schema validation LLM call."""
    is_good_fit: bool
    reasoning: str


class SchemaValidator:
    """
    Validates if a source table's schema can fulfill a specific, targeted data requirement.
    """

    def __init__(
        self, 
        gemini_api_key: str,
        max_retries: int = 5,
        initial_retry_delay: float = 1.0,
    ):
        """
        Initialize the schema validator.
        
        Args:
            gemini_api_key: Gemini API key for authentication.
            max_retries: Maximum number of retry attempts for rate limit errors (default: 5).
            initial_retry_delay: Initial delay in seconds for exponential backoff (default: 1.0).
        """
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel("gemini-flash-latest")
        self.logger = logging.getLogger(__name__)
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay

    def _call_with_retry(self, prompt: str, context: str) -> Optional[Any]:
        """
        Call Gemini API with retry logic for rate limit errors.
        
        Args:
            prompt: The prompt to send to Gemini.
            context: Context string for logging (e.g., table name).
            
        Returns:
            API response or None if all retries fail.
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                response = self.model.generate_content(
                    prompt,
                    generation_config=GenerationConfig(
                        temperature=0.0,
                        response_mime_type="application/json",
                    ),
                )
                
                # Log the response for debugging
                self.logger.debug("=" * 80)
                self.logger.debug(f"LLM RESPONSE ({context}):")
                self.logger.debug("-" * 80)
                self.logger.debug(response.text)
                self.logger.debug("=" * 80)
                
                return response
                
            except Exception as e:
                last_exception = e
                error_str = str(e)
                
                # Check if this is a rate limit error (429)
                is_rate_limit = "429" in error_str or "quota" in error_str.lower()
                
                if not is_rate_limit:
                    # Not a rate limit error, don't retry
                    self.logger.error(f"Non-retryable error for {context}: {e}")
                    return None
                
                if attempt >= self.max_retries:
                    # Max retries reached
                    self.logger.error(f"Max retries ({self.max_retries}) reached for {context}: {e}")
                    return None
                
                # Calculate delay with exponential backoff
                delay = self.initial_retry_delay * (2 ** attempt)
                
                # Try to parse suggested retry delay from error message
                # Error format: "Please retry in 52.191488352s"
                retry_match = re.search(r'retry in ([\d.]+)(ms|s)', error_str)
                if retry_match:
                    suggested_delay = float(retry_match.group(1))
                    unit = retry_match.group(2)
                    if unit == 'ms':
                        suggested_delay /= 1000  # Convert to seconds
                    
                    # Use the suggested delay if it's reasonable, otherwise use exponential backoff
                    if 0.1 <= suggested_delay <= 60:
                        delay = suggested_delay
                        self.logger.info(f"Using API suggested retry delay: {delay:.2f}s")
                
                self.logger.warning(
                    f"Rate limit hit for {context} (attempt {attempt + 1}/{self.max_retries + 1}). "
                    f"Retrying in {delay:.2f}s..."
                )
                time.sleep(delay)
        
        # Should not reach here, but just in case
        if last_exception:
            self.logger.error(f"Failed after all retries for {context}: {last_exception}")
        return None

    def validate_schema(
        self,
        source_schema: List[Dict[str, Any]],
        target_columns: List[TargetColumn],
        conceptual_group: str,
        source_table_name: str = "UNKNOWN"
    ) -> bool:
        """
        Validate a source schema against a targeted list of columns using an LLM.
        
        Args:
            source_schema: The schema of the source table.
            target_columns: The specific subset of columns this source is expected to provide.
            conceptual_group: The high-level description of the data being sought.
            source_table_name: The name of the source table being validated.
            
        Returns:
            True if the schema is a good fit, False otherwise.
        """
        prompt = self._build_validation_prompt(
            source_schema, target_columns, conceptual_group
        )
        
        logger.debug("=" * 80)
        logger.debug(f"LLM CONTEXT - SCHEMA VALIDATION ({source_table_name} for {conceptual_group}):")
        logger.debug("-" * 80)
        logger.debug(prompt)
        logger.debug("=" * 80)
        
        try:
            # Validate schema with retry logic
            response = self._call_with_retry(
                prompt, 
                f"schema validation - {source_table_name}"
            )

            if not response:
                self.logger.error(f"    ✗ Schema validation failed for {source_table_name}: No response after retries")
                return False

            # Parse the JSON response manually and validate with Pydantic
            response_text = response.text
            response_data = json.loads(response_text)
            result = ValidationResult(**response_data)

            # Log detailed validation results
            if result.is_good_fit:
                self.logger.info(f"    ✓ Good Fit: {source_table_name}")
                self.logger.info(f"      Reasoning: {result.reasoning}")
            else:
                self.logger.info(f"    ✗ Poor Fit: {source_table_name}")
                self.logger.info(f"      Reasoning: {result.reasoning}")
            
            return result.is_good_fit
            
        except Exception as e:
            self.logger.error(f"    ✗ Schema validation failed for {source_table_name}: {e}")
            if 'response' in locals() and response and hasattr(response, 'text'):
                self.logger.error(f"LLM Response Text: {response.text}")
            return False

    def _build_validation_prompt(
        self,
        source_schema: List[Dict[str, Any]],
        target_columns: List[TargetColumn],
        conceptual_group: str,
    ) -> str:
        """
        Build the prompt for the LLM-based schema validation.
        """
        target_columns_str = json.dumps(
            [col.model_dump() for col in target_columns], indent=2
        )
        source_schema_str = json.dumps(source_schema, indent=2)

        return f"""
        Analyze if the source table schema is a USEFUL CANDIDATE for a specific data requirement.

        CONTEXT: We are searching for data for the conceptual group: "{conceptual_group}".

        REQUIRED COLUMNS FOR THIS GROUP:
        We need to find a source that can provide the following columns:
        {target_columns_str}

        CANDIDATE SOURCE TABLE SCHEMA:
        Below is the schema of a candidate source table we have found.
        {source_schema_str}

        TASK:
        Based on the `CANDIDATE SOURCE TABLE SCHEMA`, determine if it is a "good fit" to provide the data for the `REQUIRED COLUMNS FOR THIS GROUP`.

        IMPORTANT:
        - A "good fit" means the source table contains a high degree of conceptual overlap with the required columns. Column names do not need to match exactly.
        - It is acceptable and expected that the source table will NOT contain columns from other conceptual groups. Focus only on its ability to fulfill THIS specific requirement.

        Respond with ONLY a JSON object in this format:
        {{
          "is_good_fit": boolean,
          "reasoning": "Explain why this is a good or poor candidate for providing the specified required columns. Be specific about column overlap or conceptual mismatches."
        }}
        """
