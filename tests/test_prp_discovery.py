"""
Tests for PRP Discovery

Tests for Gemini-based extraction and discovery of source tables from PRPs.
"""

import os
import pytest

from data_discovery_agent.parsers.prp_extractor import PRPExtractor


@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set"
)
def test_prp_extraction() -> None:
    """Test Gemini extraction on sample PRP."""
    # Read sample PRP
    sample_prp_path = os.path.join(
        os.path.dirname(__file__),
        "fixtures",
        "sample_prp.md"
    )
    
    with open(sample_prp_path, "r") as f:
        prp_markdown = f.read()
    
    # Initialize extractor
    extractor = PRPExtractor(gemini_api_key=os.getenv("GEMINI_API_KEY"))
    
    # Extract Section 9
    tables = extractor.extract_section_9(prp_markdown)
    
    # Verify extraction
    assert len(tables) == 3, f"Expected 3 tables, got {len(tables)}"
    
    # Check first table (ensemble_predictions)
    assert tables[0]["table_name"] == "ensemble_predictions"
    assert "predictions" in tables[0]["description"].lower()
    assert len(tables[0]["columns"]) > 10, "Should have more than 10 columns"
    
    # Verify column structure
    first_column = tables[0]["columns"][0]
    assert "name" in first_column
    assert "type" in first_column
    assert "description" in first_column
    
    # Check second table (game_results)
    assert tables[1]["table_name"] == "game_results"
    assert len(tables[1]["columns"]) == 4
    
    # Check third table (backtest_results)
    assert tables[2]["table_name"] == "backtest_results"
    assert len(tables[2]["columns"]) == 5


def test_prp_extraction_with_minimal_markdown() -> None:
    """Test extraction with minimal valid markdown."""
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")
    
    minimal_prp = """
## 9. Data Requirements
### Table: `test_table`
**Description:** A test table for validation.

**Schema:**
- `id` (STRING): Unique identifier.
- `value` (INTEGER): Some value.
"""
    
    extractor = PRPExtractor(gemini_api_key=os.getenv("GEMINI_API_KEY"))
    tables = extractor.extract_section_9(minimal_prp)
    
    assert len(tables) == 1
    assert tables[0]["table_name"] == "test_table"
    assert len(tables[0]["columns"]) == 2


def test_prp_extraction_empty_markdown() -> None:
    """Test extraction with empty markdown returns empty list."""
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")
    
    extractor = PRPExtractor(gemini_api_key=os.getenv("GEMINI_API_KEY"))
    tables = extractor.extract_section_9("")
    
    # Should return empty list or handle gracefully
    assert isinstance(tables, list)

