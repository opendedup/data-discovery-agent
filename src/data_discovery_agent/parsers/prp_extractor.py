"""
PRP Extractor

Extracts data requirements from Product Requirement Prompts using Gemini Flash 2.5.
Provides structured extraction of Section 9: Data Requirements with comprehensive logging.
"""

import json
import logging
from typing import Any, Dict, List
import re

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

logger = logging.getLogger(__name__)


class PRPExtractor:
    """
    Extracts data requirements from PRP using Gemini Flash 2.5.
    
    Parses Section 9 to extract target table specifications including
    table names, descriptions, and column schemas.
    """
    
    def __init__(self, gemini_api_key: str):
        """
        Initialize PRP extractor.
        
        Args:
            gemini_api_key: Gemini API key for authentication
        """
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash")
        self.logger = logging.getLogger(__name__)
    
    def extract_section_9(self, prp_markdown: str) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Extract Section 9: Data Requirements from PRP markdown.
        
        Uses Gemini Flash 2.5 to parse markdown and extract structured table
        specifications and data gaps with comprehensive logging.
        
        Args:
            prp_markdown: Full PRP markdown or Section 9 content
            
        Returns:
            A tuple containing:
            - List of table specifications
            - List of data gap definitions
            
        Raises:
            Exception: If extraction fails
        """
        self.logger.info("=" * 80)
        self.logger.info("EXTRACTING PRP SECTION 9 USING GEMINI FLASH 2.5")
        self.logger.info("=" * 80)
        self.logger.debug(f"PRP markdown length: {len(prp_markdown)} characters")
        
        # Build extraction prompt
        prompt = self._build_extraction_prompt(prp_markdown)
        
        try:
            # Call Gemini with JSON mode
            response = self.model.generate_content(
                prompt,
                generation_config=GenerationConfig(
                    temperature=0.1,  # Low temperature for deterministic extraction
                    response_mime_type="application/json"
                )
            )
            
            # Parse JSON response
            result = json.loads(response.text)
            tables = result.get("tables", [])
            
            # Also extract data gaps from the markdown
            data_gaps = self._extract_data_gaps_from_json(prp_markdown)
            
            # Log extraction results
            self._log_extraction_results(tables, data_gaps)
            
            return tables, data_gaps
            
        except json.JSONDecodeError as e:
            self.logger.error("=" * 80)
            self.logger.error("JSON PARSING FAILED")
            self.logger.error("=" * 80)
            self.logger.error(f"Error: {e}")
            self.logger.error(f"Response text: {response.text[:500]}...")
            raise
            
        except Exception as e:
            self.logger.error("=" * 80)
            self.logger.error("EXTRACTION FAILED")
            self.logger.error("=" * 80)
            self.logger.error(f"Error: {e}", exc_info=True)
            raise
    
    def _extract_data_gaps_from_json(self, prp_markdown: str) -> List[Dict[str, Any]]:
        """
        Extracts structured data gaps from a JSON block in the PRP markdown.
        
        Args:
            prp_markdown: The PRP markdown content.
            
        Returns:
            A list of data gap dictionaries, or an empty list if none are found.
        """
        try:
            # Regex to find the json block for data gaps
            match = re.search(r"```json\s*(\{.*?\})\s*```", prp_markdown, re.DOTALL)
            if not match:
                self.logger.info("No structured data gaps found in PRP.")
                return []
            
            gaps_data = json.loads(match.group(1))
            return gaps_data.get("data_gaps", [])
        except json.JSONDecodeError as e:
            self.logger.warning(f"Could not parse data gaps JSON: {e}")
            return []
        except Exception as e:
            self.logger.error(f"An unexpected error occurred while extracting data gaps: {e}")
            return []

    def _build_extraction_prompt(self, prp_markdown: str) -> str:
        """
        Build prompt for Gemini extraction.
        
        Args:
            prp_markdown: PRP markdown content
            
        Returns:
            Formatted prompt string
        """
        return f"""Extract all table specifications from Section 9: Data Requirements in the PRP markdown below.

For each table, extract:
- table_name (without backticks or special characters)
- description (the table's purpose and what it contains)
- columns (array of column specifications)

For each column, extract:
- name (column name without backticks)
- type (data type like STRING, INTEGER, FLOAT, TIMESTAMP, etc.)
- description (what the column represents)

Return ONLY valid JSON in this exact format:
{{
  "tables": [
    {{
      "table_name": "example_table",
      "description": "Description of what this table contains",
      "columns": [
        {{"name": "column1", "type": "STRING", "description": "Description of column1"}},
        {{"name": "column2", "type": "INTEGER", "description": "Description of column2"}}
      ]
    }}
  ]
}}

PRP Markdown:
{prp_markdown}
"""
    
    def _log_extraction_results(
        self, tables: List[Dict[str, Any]], data_gaps: List[Dict[str, Any]]
    ) -> None:
        """
        Log detailed extraction results for tables and data gaps.
        
        Args:
            tables: Extracted table specifications
            data_gaps: Extracted data gap definitions
        """
        self.logger.info(f"✓ Successfully extracted {len(tables)} table(s) and {len(data_gaps)} data gap(s)")
        self.logger.info("-" * 80)
        
        for i, table in enumerate(tables, 1):
            table_name = table.get('table_name', 'UNKNOWN')
            description = table.get('description', '')
            columns = table.get('columns', [])
            
            self.logger.info(f"Table {i}: {table_name}")
            self.logger.info(f"  Description: {description[:100]}{'...' if len(description) > 100 else ''}")
            self.logger.info(f"  Columns: {len(columns)}")
            
            # Log first 5 columns with DEBUG level
            for col in columns[:5]:
                col_name = col.get('name', 'UNKNOWN')
                col_type = col.get('type', 'UNKNOWN')
                col_desc = col.get('description', '')
                self.logger.debug(
                    f"    • {col_name} ({col_type}): "
                    f"{col_desc[:50]}{'...' if len(col_desc) > 50 else ''}"
                )
            
            if len(columns) > 5:
                self.logger.debug(f"    ... and {len(columns) - 5} more column(s)")
            
            self.logger.info("-" * 80)

        if data_gaps:
            self.logger.info("Detected Data Gaps:")
            for gap in data_gaps:
                self.logger.info(f"  - Gap ID: {gap.get('gap_id')}")
                self.logger.info(f"    Target View: {gap.get('target_view')}")
                self.logger.info(f"    Description: {gap.get('description')}")
            self.logger.info("-" * 80)

