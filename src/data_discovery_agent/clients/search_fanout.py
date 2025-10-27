"""
Search Fan-out Generator

Generates related search queries to expand search scope when initial queries
return no results.
"""

import json
import logging
import re
import time
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


class SearchFanoutGenerator:
    """Generates related search queries to expand search scope."""
    
    def __init__(
        self, 
        gemini_client: Any,
        max_retries: int = 5,
        initial_retry_delay: float = 1.0,
    ):
        """
        Initialize the fan-out generator.
        
        Args:
            gemini_client: GeminiClient instance for generating related queries.
            max_retries: Maximum number of retry attempts for rate limit errors (default: 5).
            initial_retry_delay: Initial delay in seconds for exponential backoff (default: 1.0).
        """
        self.gemini_client = gemini_client
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay

    def _call_with_retry(self, prompt: str, context: str) -> Optional[Any]:
        """
        Call Gemini API with retry logic for rate limit errors.
        
        Args:
            prompt: The prompt to send to Gemini.
            context: Context string for logging (e.g., original query).
            
        Returns:
            API response or None if all retries fail.
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # Import here to avoid circular dependency
                import google.generativeai as genai
                
                # Generate related queries using Gemini
                response = self.gemini_client.model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.7,  # Some creativity for diverse queries
                    ),
                    safety_settings=self.gemini_client.safety_settings,
                )
                
                # Log the response for debugging
                logger.debug("=" * 80)
                logger.debug(f"LLM RESPONSE ({context}):")
                logger.debug("-" * 80)
                logger.debug(response.text)
                logger.debug("=" * 80)
                
                return response
                
            except Exception as e:
                last_exception = e
                error_str = str(e)
                
                # Check if this is a rate limit error (429)
                is_rate_limit = "429" in error_str or "quota" in error_str.lower()
                
                if not is_rate_limit:
                    # Not a rate limit error, don't retry
                    logger.error(f"Non-retryable error for {context}: {e}")
                    return None
                
                if attempt >= self.max_retries:
                    # Max retries reached
                    logger.error(f"Max retries ({self.max_retries}) reached for {context}: {e}")
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
                        logger.info(f"Using API suggested retry delay: {delay:.2f}s")
                
                logger.warning(
                    f"Rate limit hit for {context} (attempt {attempt + 1}/{self.max_retries + 1}). "
                    f"Retrying in {delay:.2f}s..."
                )
                time.sleep(delay)
        
        # Should not reach here, but just in case
        if last_exception:
            logger.error(f"Failed after all retries for {context}: {last_exception}")
        return None
    
    def generate_related_queries(self, original_query: str, num_queries: int = 4) -> List[str]:
        """
        Generate related search queries based on different interpretations.
        
        Args:
            original_query: The user's original intent
            num_queries: Number of related queries to generate
            
        Returns:
            List of related search query strings
        """
        # Use Gemini to generate semantically related queries
        prompt = f"""Given this user query: "{original_query}"

Generate {num_queries} related search queries that interpret this question from different angles or related topics.

Examples:
- Original: "should I trade for aaron rodgers"
  Related: ["quarterback performance metrics", "fantasy football player analysis", "NFL player statistics", "trade value analysis"]

- Original: "customer churn prediction"
  Related: ["customer retention data", "subscription cancellation patterns", "user engagement metrics", "customer lifetime value"]

- Original: "trending products"
  Related: ["product sales data", "inventory movement", "customer purchase patterns", "seasonal trends"]

Generate ONLY the queries as a JSON array, nothing else. No markdown, no explanation:"""
        
        logger.debug("=" * 80)
        logger.debug(f"LLM CONTEXT - SEARCH FANOUT GENERATION ({original_query}):")
        logger.debug("-" * 80)
        logger.debug(prompt)
        logger.debug("=" * 80)
        
        try:
            # Generate related queries with retry logic
            response = self._call_with_retry(
                prompt,
                f"search fanout - {original_query}"
            )
            
            if not response:
                logger.error(f"Failed to generate related queries for: {original_query}")
                return []
            
            # Extract text and parse JSON
            response_text = response.text.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1]) if len(lines) > 2 else response_text
            
            # Parse JSON
            related_queries = json.loads(response_text)
            
            if not isinstance(related_queries, list):
                logger.warning(f"Expected list of queries, got {type(related_queries)}")
                return []
            
            # Validate and clean
            valid_queries = [
                str(q).strip() 
                for q in related_queries 
                if q and isinstance(q, str) and len(str(q).strip()) > 0
            ]
            
            logger.info(f"Generated {len(valid_queries)} related queries for: {original_query}")
            logger.debug(f"Related queries: {valid_queries}")
            
            return valid_queries[:num_queries]
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Gemini response: {e}")
            if 'response_text' in locals():
                logger.debug(f"Response text: {response_text}")
            return []
        except Exception as e:
            logger.error(f"Failed to generate related queries: {e}", exc_info=True)
            return []

