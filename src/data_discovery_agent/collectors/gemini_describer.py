"""
Gemini Description Generator

Uses Gemini 2.5 Flash to automatically generate table descriptions
when they're missing from BigQuery metadata.
"""

import logging
from typing import Dict, Any, Optional, List
import google.generativeai as genai
import os

logger = logging.getLogger(__name__)


class GeminiDescriber:
    """
    Generates table descriptions using Gemini 2.5 Flash.
    
    Analyzes table schema, sample values, column profiles, and other metadata
    to create meaningful, context-aware descriptions.
    """
    
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.0-flash-exp"):
        """
        Initialize the Gemini describer.
        
        Args:
            api_key: Gemini API key (or uses GEMINI_API_KEY env var)
            model_name: Gemini model to use (default: gemini-2.0-flash-exp)
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name
        
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
            
            # Generate description
            response = self.model.generate_content(prompt)
            
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
        parts.append(f"Analyze the following BigQuery table and generate a concise, informative description.")
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
            
            # Generate insights
            response = self.model.generate_content(prompt)
            
            if response and response.text:
                # Parse the response into a list of insights
                insights_text = response.text.strip()
                
                # Split by numbered lines (1., 2., etc.) or newlines
                import re
                insights = []
                
                # Try to find numbered items first
                numbered_pattern = r'^\d+\.\s*(.+)$'
                for line in insights_text.split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    
                    match = re.match(numbered_pattern, line)
                    if match:
                        insights.append(match.group(1).strip())
                    elif line and not line.startswith('#') and not line.startswith('**'):
                        # Non-numbered line that's not a header
                        insights.append(line)
                
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
        parts.append("Each question should:")
        parts.append("1. Be specific and actionable")
        parts.append("2. Reference specific columns from the schema")
        parts.append("3. Suggest a meaningful analysis (trends, correlations, comparisons, aggregations)")
        parts.append("4. Be answerable using SQL queries on this table")
        parts.append("5. Provide business value or interesting insights")
        parts.append("")
        parts.append("Examples of good questions:")
        parts.append("- Analyze the trend of penalties and penalty yards over the weeks of the season for each team")
        parts.append("- Calculate the average number of turnovers for home and away teams based on prior losses")
        parts.append("- Find the teams with the highest average score differential")
        parts.append("- Determine the percentage of drives that resulted in a touchdown for each quarter")
        parts.append("")
        parts.append("Format your response as a numbered list (1., 2., 3., etc.)")
        parts.append("")
        parts.append("**Analytical Questions:**")
        
        return "\n".join(parts)

