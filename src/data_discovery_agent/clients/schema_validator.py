from typing import Any, Dict, List
import logging
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
import json

logger = logging.getLogger(__name__)

class SchemaValidator:
    """
    Validates if a source table's schema can fulfill the requirements of a target view.
    """

    def __init__(self, gemini_api_key: str):
        """
        Initialize the schema validator.
        
        Args:
            gemini_api_key: Gemini API key for authentication.
        """
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash")
        self.logger = logging.getLogger(__name__)

    def validate_schema(
        self,
        source_schema: List[Dict[str, Any]],
        target_view: Dict[str, Any],
        data_gap: Dict[str, Any] = None,
        source_table_name: str = "UNKNOWN"
    ) -> bool:
        """
        Validate a source schema against a target view's requirements using an LLM.
        
        Args:
            source_schema: The schema of the source table.
            target_view: The specification of the target view.
            data_gap: The data gap information, if any.
            source_table_name: The name of the source table being validated.
            
        Returns:
            True if the schema is a good fit, False otherwise.
        """
        prompt = self._build_validation_prompt(source_schema, target_view, data_gap)
        
        logger.debug("=" * 80)
        logger.debug(f"LLM CONTEXT - SCHEMA VALIDATION ({source_table_name}):")
        logger.debug("-" * 80)
        logger.debug(prompt)
        logger.debug("=" * 80)
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=GenerationConfig(
                    temperature=0.0,
                    response_mime_type="application/json"
                )
            )
            
            logger.debug("=" * 80)
            logger.debug(f"LLM RESPONSE - SCHEMA VALIDATION ({source_table_name}):")
            logger.debug("-" * 80)
            logger.debug(response.text)
            logger.debug("=" * 80)
            
            result = json.loads(response.text)
            is_good_fit = result.get("is_good_fit", False)
            reasoning = result.get('reasoning', 'N/A')
            
            # Log detailed validation results
            if is_good_fit:
                self.logger.info(f"    ✓ Good Fit: {source_table_name}")
                self.logger.info(f"      Reasoning: {reasoning}")
            else:
                self.logger.info(f"    ✗ Poor Fit: {source_table_name}")
                self.logger.info(f"      Reasoning: {reasoning}")
            
            return is_good_fit
            
        except Exception as e:
            self.logger.error(f"    ✗ Schema validation failed for {source_table_name}: {e}")
            return False

    def _build_validation_prompt(
        self,
        source_schema: List[Dict[str, Any]],
        target_view: Dict[str, Any],
        data_gap: Dict[str, Any] = None
    ) -> str:
        """
        Build the prompt for the LLM-based schema validation.
        """
        target_schema_str = json.dumps(target_view.get("columns", []), indent=2)
        source_schema_str = json.dumps(source_schema, indent=2)
        
        gap_info = ""
        if data_gap:
            gap_info = f"""
CRITICAL DATA GAP:
A known data gap for this view is: "{data_gap.get('description')}"
The required information to fill this gap is: "{data_gap.get('required_information')}"
Does the source table help resolve this specific gap?
"""

        return f"""
Analyze if the source table schema is a USEFUL CANDIDATE for creating the target view.

TARGET VIEW:
Name: {target_view.get('table_name')}
Purpose: {target_view.get('description')}
Schema:
{target_schema_str}

SOURCE TABLE SCHEMA:
{source_schema_str}

{gap_info}

Is this source table a USEFUL CANDIDATE for building the target view?

IMPORTANT: We are looking for CANDIDATE tables with significant overlap, not perfect matches.

Mark as "is_good_fit: true" if:
- The source table contains MANY of the key columns (>50% overlap with target)
- The source has core identifier columns (e.g., IDs, dates, keys needed for joins)
- Missing some derived or calculated columns is ACCEPTABLE
- Column names do not need to match exactly, but the concepts should be present
- Focus on whether this table provides valuable SOURCE DATA, even if transformations are needed

Mark as "is_good_fit: false" ONLY if:
- The table has minimal column overlap (<30%)
- It's clearly for a different domain/purpose  
- It lacks the fundamental identifier columns needed for joins

Respond with ONLY a JSON object in this format:
{{
  "is_good_fit": boolean,
  "reasoning": "Explain the approximate column overlap and which key columns are present or missing. Be specific about what makes this a good or poor candidate."
}}
"""
