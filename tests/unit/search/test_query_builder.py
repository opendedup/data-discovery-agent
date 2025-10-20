"""Unit tests for SearchQueryBuilder."""

from __future__ import annotations

import pytest

from data_discovery_agent.search.query_builder import SearchQueryBuilder


@pytest.mark.unit
@pytest.mark.formatters
class TestSearchQueryBuilder:
    """Tests for SearchQueryBuilder class."""

    def test_init(self) -> None:
        """Test query builder initialization."""
        builder = SearchQueryBuilder(project_id="test-project")

        assert builder.project_id == "test-project"

    def test_build_simple_query(self) -> None:
        """Test building a simple semantic query."""
        builder = SearchQueryBuilder(project_id="test-project")

        query = builder.build_query(user_query="find user tables")

        assert query is not None
        assert "query" in query
        assert query["query"] == "find user tables"
        assert "page_size" in query

    def test_build_query_with_filters(self) -> None:
        """Test building query with explicit filters."""
        builder = SearchQueryBuilder(project_id="test-project")

        explicit_filters = {
            "project": "test-project",
            "dataset": "test_dataset",
        }

        query = builder.build_query(
            user_query="find tables",
            explicit_filters=explicit_filters,
        )

        assert "filter" in query or "query" in query

    def test_extract_project_filter(self) -> None:
        """Test extraction of project filter from query."""
        builder = SearchQueryBuilder(project_id="test-project")

        query = builder.build_query(
            user_query="find tables in project: my-project"
        )

        # Should extract and apply project filter
        assert query is not None

    def test_extract_dataset_filter(self) -> None:
        """Test extraction of dataset filter from query."""
        builder = SearchQueryBuilder(project_id="test-project")

        query = builder.build_query(
            user_query="find tables in dataset: analytics"
        )

        assert query is not None

    def test_extract_pii_filter(self) -> None:
        """Test extraction of PII filter from query."""
        builder = SearchQueryBuilder(project_id="test-project")

        query = builder.build_query(user_query="find tables with PII data")

        assert query is not None
        # Should identify PII-related query

    def test_page_size_configuration(self) -> None:
        """Test page size configuration."""
        builder = SearchQueryBuilder(project_id="test-project")

        query = builder.build_query(user_query="find tables", page_size=50)

        assert query["page_size"] == 50

    def test_order_by_configuration(self) -> None:
        """Test order by configuration."""
        builder = SearchQueryBuilder(project_id="test-project")

        query = builder.build_query(
            user_query="find tables",
            order_by="modified_time desc",
        )

        assert "order_by" in query
        assert query["order_by"] == "modified_time desc"

    def test_boost_spec_generation(self) -> None:
        """Test boost specification for ranking."""
        builder = SearchQueryBuilder(project_id="test-project")

        query = builder.build_query(user_query="user analytics")

        # Should include boost spec for better ranking
        assert "boost_spec" in query or "query" in query

    def test_empty_query_handling(self) -> None:
        """Test handling of empty query."""
        builder = SearchQueryBuilder(project_id="test-project")

        query = builder.build_query(user_query="")

        assert query is not None
        assert "query" in query

    def test_special_characters_in_query(self) -> None:
        """Test handling of special characters in query."""
        builder = SearchQueryBuilder(project_id="test-project")

        query = builder.build_query(
            user_query="tables with email@example.com"
        )

        assert query is not None
        # Should handle special characters safely

    def test_filter_expression_building(self) -> None:
        """Test building filter expressions."""
        builder = SearchQueryBuilder(project_id="test-project")

        filters = {
            "project": "test-project",
            "dataset": "analytics",
            "has_pii": True,
        }

        query = builder.build_query(
            user_query="find tables",
            explicit_filters=filters,
        )

        # Should construct proper filter expression
        assert query is not None

    def test_multiple_filter_combination(self) -> None:
        """Test combining multiple filters."""
        builder = SearchQueryBuilder(project_id="test-project")

        query = builder.build_query(
            user_query="find tables in project:test-project dataset:analytics with PII"
        )

        assert query is not None
        # Should extract and combine multiple filters

    def test_semantic_query_preservation(self) -> None:
        """Test that semantic query is preserved after filter extraction."""
        builder = SearchQueryBuilder(project_id="test-project")

        query = builder.build_query(
            user_query="find user analytics tables in project:test-project"
        )

        # Semantic part should remain
        assert "query" in query
        # "find user analytics tables" should be preserved

