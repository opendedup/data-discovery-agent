"""Tests for the data profiler agent."""

import pytest
from data_discovery_agent.agents.data_profiler.agent import root_agent


def test_agent_exists():
    """Test that the root agent is properly defined."""
    assert root_agent is not None
    assert root_agent.name == "data_profiler"


def test_agent_has_description():
    """Test that the agent has a description."""
    assert root_agent.description is not None
    assert len(root_agent.description) > 0


def test_agent_has_instruction():
    """Test that the agent has instructions."""
    assert root_agent.instruction is not None
    assert len(root_agent.instruction) > 0


def test_agent_model():
    """Test that the agent has a model configured."""
    assert root_agent.model is not None

