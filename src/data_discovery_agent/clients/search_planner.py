"""
Search Planner Client

This module defines the SearchPlanner class, which is responsible for analyzing a 
Product Requirement Prompt (PRP) and generating a strategic, multi-step search plan 
for discovering the required data sources.
"""

import json
import logging
from typing import Any, Dict

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from ..schemas.search_planning import SearchPlan

logger = logging.getLogger(__name__)


class SearchPlanner:
    """
    Generates a structured search plan from a PRP using a Gemini model.
    
    This class leverages the full context of a PRP to create a series of targeted 
    search queries, each mapped to a specific subset of the required data, 
    guaranteeing a structured JSON output for programmatic execution.
    """

    def __init__(self, gemini_api_key: str):
        """
        Initialize the Search Planner.
        
        Args:
            gemini_api_key: Gemini API key for authentication.
        """
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel("gemini-flash-latest")
        self.logger = logging.getLogger(__name__)

    def create_search_plan(self, prp_markdown: str, target_schema: Dict[str, Any]) -> SearchPlan:
        """
        Analyzes a PRP and target schema to create a multi-step search plan.

        Args:
            prp_markdown: The full content of the Product Requirement Prompt.
            target_schema: The schema of the final target view to be created.

        Returns:
            A SearchPlan object containing a list of targeted search steps.
            
        Raises:
            Exception: If the LLM call fails or returns an invalid structure.
        """
        self.logger.info("=" * 80)
        self.logger.info("GENERATING SEARCH AND MAPPING PLAN FROM PRP")
        self.logger.info("=" * 80)
        
        prompt = self._build_planning_prompt(prp_markdown, target_schema)
        
        self.logger.debug("=" * 80)
        self.logger.debug("LLM CONTEXT - SEARCH PLAN GENERATION:")
        self.logger.debug("-" * 80)
        self.logger.debug(prompt)
        self.logger.debug("=" * 80)
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=GenerationConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                )
            )
            
            self.logger.debug("=" * 80)
            self.logger.debug("LLM RESPONSE - SEARCH PLAN GENERATION:")
            self.logger.debug("-" * 80)
            self.logger.debug(response.text) # Log the raw JSON string
            self.logger.debug("=" * 80)
            
            # Parse the JSON response and validate with Pydantic
            response_json = json.loads(response.text)
            search_plan: SearchPlan = SearchPlan.model_validate(response_json)
            
            self.logger.info(f"✓ Successfully generated a search plan with {len(search_plan.steps)} steps.")
            for i, step in enumerate(search_plan.steps, 1):
                self.logger.info(f"  Step {i} ({step.conceptual_group}): \"{step.search_query}\"")
                self.logger.debug(f"    - Target columns: {[col.name for col in step.target_columns_for_validation]}")
            
            return search_plan

        except Exception as e:
            self.logger.error("=" * 80)
            self.logger.error("SEARCH PLAN GENERATION FAILED")
            self.logger.error("=" * 80)
            self.logger.error(f"Error: {e}", exc_info=True)
            # Log the response text if available for debugging
            if 'response' in locals() and hasattr(response, 'text'):
                self.logger.error(f"LLM Response Text: {response.text}")
            raise

    def _build_planning_prompt(self, prp_markdown: str, target_schema: Dict[str, Any]) -> str:
        """
        Builds the detailed prompt for the Gemini model to generate the search plan.

        Args:
            prp_markdown: The full PRP content.
            target_schema: The final target schema.

        Returns:
            The formatted prompt string.
        """
        return f"""
        Analyze this entire PRP and the final target schema. Identify the distinct 
        conceptual groups of data required to build the final view. 

        For each group, generate a targeted, one-sentence semantic search query. 
        Crucially, for each query, also extract the specific subset of columns from the 
        final target schema that this query is meant to discover.

        Return your response as JSON with this structure:
        {{
            "steps": [
                {{
                    "conceptual_group": "brief name for this data group",
                    "search_query": "semantic search query",
                    "target_columns_for_validation": [
                        {{"name": "column_name", "type": "column_type", "description": "column_description"}}
                    ]
                }}
            ]
        }}

        PRP:
        ---
        {prp_markdown}
        ---

        FINAL TARGET SCHEMA:
        ---
        {target_schema}
        ---
        """
