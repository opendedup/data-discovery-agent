"""
Gemini Description Generator

Uses Gemini 2.5 Flash to automatically generate table descriptions
when they're missing from BigQuery metadata.

Environment Variables:
    GEMINI_API_KEY: API key for Google Gemini API (loaded from .env file)
                    Get your key from: https://aistudio.google.com/app/apikey

Example .env file:
    GEMINI_API_KEY=your-api-key-here
"""

import logging
from typing import Dict, Any, Optional, List
import google.generativeai as genai
import os
import time
import re

logger = logging.getLogger(__name__)


class GeminiDescriber:
    """
    Generates table descriptions using Gemini 2.5 Flash.
    
    Analyzes table schema, sample values, column profiles, and other metadata
    to create meaningful, context-aware descriptions.
    """
    
    def __init__(
        self, 
        api_key: Optional[str] = None, 
        model_name: str = "gemini-flash-latest",
        max_retries: int = 5,
        initial_retry_delay: float = 1.0,
    ):
        """
        Initialize the Gemini describer.
        
        Args:
            api_key: Gemini API key (or uses GEMINI_API_KEY env var from .env file)
            model_name: Gemini model to use (default: gemini-flash-latest)
            max_retries: Maximum number of retry attempts for rate limit errors (default: 5)
            initial_retry_delay: Initial delay in seconds for exponential backoff (default: 1.0)
            
        Note:
            Ensure .env file is loaded (via load_dotenv()) before initializing this class
            if you want to use GEMINI_API_KEY from .env file.
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay
        
        if not self.api_key:
            logger.warning("No Gemini API key provided. Description generation will be disabled.")
            self.enabled = False
            return
        
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
            self.enabled = True
            logger.info(f"Initialized Gemini describer with model: {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            self.enabled = False
        print(f"GeminiDescriber initialized with enabled={self.enabled}")

    @property
    def is_enabled(self) -> bool:
        """Check if the Gemini client is enabled."""
        return self.enabled

    def _call_with_retry(self, prompt: str, context: str) -> Optional[Any]:
        """
        Call Gemini API with retry logic for rate limit errors.
        
        Args:
            prompt: The prompt to send to Gemini
            context: Context string for logging (e.g., table name)
            
        Returns:
            API response or None if all retries fail
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                response = self.model.generate_content(prompt)
                
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
                # Error format: "Please retry in 611.469707ms"
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
    
    def generate_table_description(
        self,
        table_name: str,
        schema: List[Dict[str, Any]],
        sample_values: Optional[Dict[str, List[str]]] = None,
        column_profiles: Optional[Dict[str, Dict[str, Any]]] = None,
        row_count: Optional[int] = None,
        size_bytes: Optional[int] = None,
    ) -> Optional[str]:
        """
        Generate a description for a BigQuery table using Gemini.
        
        Args:
            table_name: Full table name (project.dataset.table)
            schema: List of field definitions with name, type, mode, description
            sample_values: Sample values for each column
            column_profiles: Statistical profiles for columns
            row_count: Number of rows in the table
            size_bytes: Size of the table in bytes
            
        Returns:
            Generated description or None if generation fails
        """
        
        if not self.enabled:
            return None
        
        try:
            # Build a rich context for Gemini
            prompt = self._build_prompt(
                table_name=table_name,
                schema=schema,
                sample_values=sample_values,
                column_profiles=column_profiles,
                row_count=row_count,
                size_bytes=size_bytes,
            )
            
            logger.debug("=" * 80)
            logger.debug(f"LLM CONTEXT - TABLE DESCRIPTION GENERATION ({table_name}):")
            logger.debug("-" * 80)
            logger.debug(prompt)
            logger.debug("=" * 80)
            
            # Generate description with retry logic
            response = self._call_with_retry(prompt, table_name)
            
            if response and response.text:
                description = response.text.strip()
                logger.info(f"Generated description for {table_name}: {len(description)} chars")
                return description
            else:
                logger.warning(f"Empty response from Gemini for {table_name}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to generate description for {table_name}: {e}")
            return None
    
    def _build_prompt(
        self,
        table_name: str,
        schema: List[Dict[str, Any]],
        sample_values: Optional[Dict[str, List[str]]],
        column_profiles: Optional[Dict[str, Dict[str, Any]]],
        row_count: Optional[int],
        size_bytes: Optional[int],
    ) -> str:
        """Build a comprehensive prompt for Gemini"""
        
        parts = []
        
        # Header
        parts.append("Analyze the following BigQuery table and generate a concise, informative description.")
        parts.append(f"\n**Table Name:** {table_name}\n")
        
        # Statistics
        if row_count or size_bytes:
            parts.append("**Table Statistics:**")
            if row_count:
                parts.append(f"- Rows: {row_count:,}")
            if size_bytes:
                size_gb = size_bytes / (1024**3)
                parts.append(f"- Size: {size_gb:.2f} GB")
            parts.append("")
        
        # Schema with sample values
        parts.append("**Schema:**")
        for field in schema[:30]:  # Limit to first 30 columns
            field_name = field.get("name", "")
            field_type = field.get("type", "")
            field_mode = field.get("mode", "NULLABLE")
            field_desc = field.get("description", "")
            
            line = f"- **{field_name}** ({field_type}, {field_mode})"
            
            # Add existing description if available
            if field_desc:
                line += f": {field_desc}"
            
            # Add sample values
            if sample_values and field_name in sample_values:
                samples = sample_values[field_name]
                if samples:
                    samples_str = ", ".join([f"'{s}'" for s in samples[:3]])
                    line += f" [Examples: {samples_str}]"
            
            parts.append(line)
        
        if len(schema) > 30:
            parts.append(f"... and {len(schema) - 30} more columns")
        
        parts.append("")
        
        # Column profiles summary
        if column_profiles:
            parts.append("**Data Characteristics:**")
            
            # Count column types
            numeric_cols = [k for k, v in column_profiles.items() if v.get("type") == "numeric"]
            string_cols = [k for k, v in column_profiles.items() if v.get("type") == "string"]
            other_cols = [k for k, v in column_profiles.items() if v.get("type") == "other"]
            
            if numeric_cols:
                parts.append(f"- {len(numeric_cols)} numeric columns")
            if string_cols:
                parts.append(f"- {len(string_cols)} string columns")
            if other_cols:
                parts.append(f"- {len(other_cols)} other columns (timestamp, etc.)")
            
            parts.append("")
        
        # Instructions
        parts.append("**Instructions:**")
        parts.append("Generate a 2-3 sentence description that:")
        parts.append("1. Explains what data this table contains")
        parts.append("2. Identifies the business domain or use case")
        parts.append("3. Highlights key columns or relationships if apparent")
        parts.append("4. Uses professional, technical language appropriate for data documentation")
        parts.append("")
        parts.append("Do NOT:")
        parts.append("- Start with 'This table...' or 'The table...'")
        parts.append("- Include column counts or technical statistics")
        parts.append("- Use placeholder text or generic descriptions")
        parts.append("")
        parts.append("**Generated Description:**")
        
        return "\n".join(parts)
    
    def generate_table_insights(
        self,
        table_name: str,
        description: str,
        schema: List[Dict[str, Any]],
        sample_values: Optional[Dict[str, List[str]]] = None,
        column_profiles: Optional[Dict[str, Dict[str, Any]]] = None,
        row_count: Optional[int] = None,
        num_insights: int = 5,
    ) -> Optional[List[str]]:
        """
        Generate analytical insights/questions that could be answered using this table.
        
        Args:
            table_name: Full table name (project.dataset.table)
            description: Table description (ideally generated or existing)
            schema: List of field definitions
            sample_values: Sample values for each column
            column_profiles: Statistical profiles for columns
            row_count: Number of rows in the table
            num_insights: Number of insights to generate (default: 5)
            
        Returns:
            List of insight questions or None if generation fails
        """
        
        if not self.enabled:
            return None
        
        try:
            # Build a rich context for generating insights
            prompt = self._build_insights_prompt(
                table_name=table_name,
                description=description,
                schema=schema,
                sample_values=sample_values,
                column_profiles=column_profiles,
                row_count=row_count,
                num_insights=num_insights,
            )
            
            logger.debug("=" * 80)
            logger.debug(f"LLM CONTEXT - TABLE INSIGHTS GENERATION ({table_name}):")
            logger.debug("-" * 80)
            logger.debug(prompt)
            logger.debug("=" * 80)
            
            # Generate insights with retry logic
            response = self._call_with_retry(prompt, f"{table_name} (insights)")
            
            if response and response.text:
                # Parse the response into a list of insights
                insights_text = response.text.strip()
                
                # Split by numbered lines (1., 2., etc.)
                insights = []
                
                # Pattern to match numbered lines: "1. Question text"
                # Allow for optional markdown formatting
                numbered_pattern = r'^(\d+)\.\s*(.+?)$'
                
                for line in insights_text.split('\n'):
                    # Skip empty lines
                    if not line.strip():
                        continue
                    
                    # Skip lines that are clearly sub-bullets or formatting
                    # (lines starting with spaces, dashes, asterisks, or indentation)
                    if line.startswith(('  ', '   ', '\t', '- ', '* ', '  -', '  *')):
                        continue
                    
                    # Skip lines that are headers or intro text
                    stripped = line.strip()
                    if stripped.startswith(('**', '###', 'Here are', 'Analytical Questions', 'Questions:')):
                        continue
                    
                    # Try to match numbered pattern
                    match = re.match(numbered_pattern, stripped)
                    if match:
                        question_text = match.group(2).strip()
                        
                        # Clean up the question text
                        # Remove markdown bold formatting
                        question_text = re.sub(r'\*\*(.+?)\*\*', r'\1', question_text)
                        
                        # Skip if this looks like an intro line
                        if any(skip_word in question_text.lower() for skip_word in [
                            'here are', 'following are', 'questions:', 'insights:',
                            'analytical questions', 'actionable questions'
                        ]):
                            continue
                        
                        # Only include if it's a reasonable length (between 10 and 500 chars)
                        if 10 <= len(question_text) <= 500:
                            insights.append(question_text)
                
                if insights:
                    logger.info(f"Generated {len(insights)} insights for {table_name}")
                    return insights[:num_insights]  # Ensure we don't exceed requested number
                else:
                    logger.warning(f"Could not parse insights from Gemini response for {table_name}")
                    return None
            else:
                logger.warning(f"Empty insights response from Gemini for {table_name}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to generate insights for {table_name}: {e}")
            return None
    
    def _build_insights_prompt(
        self,
        table_name: str,
        description: str,
        schema: List[Dict[str, Any]],
        sample_values: Optional[Dict[str, List[str]]],
        column_profiles: Optional[Dict[str, Dict[str, Any]]],
        row_count: Optional[int],
        num_insights: int,
    ) -> str:
        """Build a comprehensive prompt for generating insights"""
        
        parts = []
        
        # Header
        parts.append("You are a data analyst. Analyze the following table and generate specific, actionable analytical questions that could be answered using this data.")
        parts.append(f"\n**Table Name:** {table_name}\n")
        
        # Description
        if description:
            parts.append(f"**Description:** {description}\n")
        
        # Statistics
        if row_count:
            parts.append(f"**Rows:** {row_count:,}\n")
        
        # Schema with sample values
        parts.append("**Schema:**")
        for field in schema[:30]:  # Limit to first 30 columns
            field_name = field.get("name", "")
            field_type = field.get("type", "")
            field_desc = field.get("description", "")
            
            line = f"- **{field_name}** ({field_type})"
            
            if field_desc:
                line += f": {field_desc}"
            
            # Add sample values
            if sample_values and field_name in sample_values:
                samples = sample_values[field_name]
                if samples:
                    samples_str = ", ".join([f"'{s}'" for s in samples[:3]])
                    line += f" [Examples: {samples_str}]"
            
            parts.append(line)
        
        if len(schema) > 30:
            parts.append(f"... and {len(schema) - 30} more columns")
        
        parts.append("")
        
        # Column types summary
        if column_profiles:
            numeric_cols = [k for k, v in column_profiles.items() if v.get("type") == "numeric"]
            string_cols = [k for k, v in column_profiles.items() if v.get("type") == "string"]
            
            if numeric_cols:
                parts.append(f"**Key Numeric Columns:** {', '.join(numeric_cols[:10])}")
            if string_cols:
                parts.append(f"**Key Categorical Columns:** {', '.join(string_cols[:10])}")
            parts.append("")
        
        # Instructions
        parts.append(f"**Generate {num_insights} analytical questions/insights:**")
        parts.append("")
        parts.append("IMPORTANT FORMAT RULES:")
        parts.append(f"- Generate EXACTLY {num_insights} questions as a simple numbered list")
        parts.append("- Each question should be ONE concise sentence on a SINGLE line")
        parts.append("- DO NOT add sub-bullets, explanations, or additional formatting")
        parts.append("- DO NOT include introductory text or headers")
        parts.append("- Just list the questions directly")
        parts.append("")
        parts.append("Each question should:")
        parts.append("- Be specific and actionable")
        parts.append("- Reference specific columns from the schema")
        parts.append("- Suggest a meaningful analysis (trends, correlations, comparisons, aggregations)")
        parts.append("- Be answerable using SQL queries on this table")
        parts.append("")
        parts.append("GOOD examples:")
        parts.append("1. What is the trend of penalties and penalty yards over the weeks of the season for each team?")
        parts.append("2. What is the average number of turnovers for home vs away teams grouped by prior losses?")
        parts.append("3. Which teams have the highest average score differential?")
        parts.append("4. What percentage of drives resulted in a touchdown in each quarter?")
        parts.append("")
        parts.append("BAD examples (too detailed or with sub-bullets):")
        parts.append("1. **Question:** What is the correlation...")
        parts.append("   - **Columns:** x, y, z")
        parts.append("   - **Analysis:** Calculate...")
        parts.append("")
        parts.append(f"Now generate EXACTLY {num_insights} simple, concise questions as a numbered list:")
        
        return "\n".join(parts)

