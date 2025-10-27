"""
Search Planner Client

This module defines the SearchPlanner class, which is responsible for analyzing a 
Product Requirement Prompt (PRP) and generating a strategic, multi-step search plan 
for discovering the required data sources.
"""

import json
import logging
import re
import time
from typing import Any, Dict, Optional

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

    def __init__(
        self, 
        gemini_api_key: str,
        max_retries: int = 5,
        initial_retry_delay: float = 1.0,
    ):
        """
        Initialize the Search Planner.
        
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
            context: Context string for logging (e.g., "search plan generation").
            
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
                    )
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
            # Generate search plan with retry logic
            response = self._call_with_retry(prompt, "search plan generation")
            
            if not response:
                raise Exception("Failed to generate search plan after retries")
            
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
            if 'response' in locals() and response and hasattr(response, 'text'):
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
        You are an expert data discovery strategist. Your task is to analyze a Product 
        Requirement Prompt (PRP) and a final target schema to create a robust, multi-step 
        search plan. The goal is to find all the necessary source data to build the final view.

        **CRITICAL CONSIDERATIONS:**
        1.  **Derived Columns:** Some columns in the final schema may not exist directly 
            in any source table. They might need to be **calculated or derived** from 
            other fields. For example, a `profit` column might be calculated from 
            `revenue` and `costs` columns. When you identify a potentially derived column, 
            your search query should look for its constituent parts.
        2.  **Composite Join Keys:** Join keys might not exist in all tables as a single column. 
            It may be necessary to **construct a join key** by merging multiple columns 
            together (e.g., creating a unique `order_item_id` by combining `order_id` and `product_id`). 
            Your search should identify tables containing these constituent parts if a direct 
            join key is not available.
        3.  **Joining Tables:** The required data is likely spread across multiple tables. 
            Your search queries should aim to find tables that can be joined using either 
            direct or composite keys.

        **TASK:**
        Analyze the entire PRP and the final target schema below. Identify the distinct 
        conceptual groups of data required. For each group:
        1.  Generate a targeted, one-sentence semantic search query. This query should 
            be smart enough to look for either the direct column, the primitive fields 
            needed to calculate it, or the fields needed to construct a join key.
        2.  Extract the specific subset of columns from the final target schema that this 
            query is responsible for discovering or enabling.

        **EXAMPLE OF DERIVED COLUMN LOGIC:**
        If the target schema requires a `profit` column, instead of searching for "profit", a 
        good search query would be: "Find financial data with revenue and cost figures to 
        calculate profit."
        
        **EXAMPLE OF COMPOSITE KEY LOGIC:**
        If you need to join tables on `order_item_id` but a table lacks it, a good search query
        would be: "Find order and product identifiers that can be combined to create a unique
        ID for each item in an order."

        Return your response as JSON with this exact structure:
        {{
            "steps": [
                {{
                    "conceptual_group": "A brief, descriptive name for this data group",
                    "search_query": "A semantic search query for the source data, considering derived columns and composite keys.",
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
