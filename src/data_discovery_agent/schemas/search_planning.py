"""
Pydantic models for the Search and Mapping Plan.

Defines the structured output expected from the Search Planner LLM call,
ensuring type safety and a clear data contract.
"""

from typing import List
from pydantic import BaseModel


class TargetColumn(BaseModel):
    """Represents a single column from the target schema that a search query is intended to find."""
    name: str
    type: str
    description: str


class SearchStep(BaseModel):
    """Defines a single, targeted search operation within the overall discovery plan."""
    conceptual_group: str
    search_query: str
    target_columns_for_validation: List[TargetColumn]


class SearchPlan(BaseModel):
    """Represents the complete search plan with multiple search steps."""
    steps: List[SearchStep]
