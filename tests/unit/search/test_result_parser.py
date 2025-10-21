"""Unit tests for SearchResultParser."""

from __future__ import annotations

import pytest

from data_discovery_agent.search.result_parser import (
    SearchResult,
    SearchResponse,
    SearchResultParser,
)


@pytest.mark.unit
@pytest.mark.formatters
class TestSearchResultParser:
    """Tests for SearchResultParser class."""

    def test_init(self) -> None:
        """Test parser initialization."""
        parser = SearchResultParser(project_id="test-project")

        assert parser is not None
        assert parser.project_id == "test-project"

    def test_parse_single_result(self) -> None:
        """Test parsing a single search result."""
        parser = SearchResultParser(project_id="test-project")

        raw_result = {
            "id": "test-project.test_dataset.test_table",
            "document": {
                "structData": {
                    "project_id": "test-project",
                    "dataset_id": "test_dataset",
                    "table_id": "test_table",
                    "asset_type": "TABLE",
                    "description": "Test table",
                    "indexed_at": "2024-01-01T00:00:00Z",
                },
                "derivedStructData": {"snippets": [{"snippet": "test snippet"}]},
            },
        }

        result = parser._parse_single_result(raw_result, "test query")

        assert result is not None
        assert isinstance(result, SearchResult)
        assert result.table_id == "test_table"

    def test_parse_multiple_results(self) -> None:
        """Test parsing multiple search results."""
        parser = SearchResultParser(project_id="test-project")

        raw_results = [
            {
                "id": f"test-project.test_dataset.table{i}",
                "document": {
                    "structData": {
                        "project_id": "test-project",
                        "dataset_id": "test_dataset",
                        "table_id": f"table{i}",
                        "asset_type": "TABLE",
                        "description": f"Test table {i}",
                        "indexed_at": "2024-01-01T00:00:00Z",
                    },
                    "derivedStructData": {"snippets": [{"snippet": "test snippet"}]},
                },
            }
            for i in range(5)
        ]

        results = [parser._parse_single_result(r, "test query") for r in raw_results]

        assert len(results) == 5
        assert all(isinstance(r, SearchResult) for r in results)

    def test_extract_table_metadata(self) -> None:
        """Test extraction of table metadata."""
        parser = SearchResultParser(project_id="test-project")

        raw_result = {
            "id": "test-project.test_dataset.test_table",
            "document": {
                "structData": {
                    "project_id": "test-project",
                    "dataset_id": "test_dataset",
                    "table_id": "test_table",
                    "asset_type": "TABLE",
                    "description": "Test table",
                    "row_count": 1000,
                    "size_bytes": 50000,
                    "indexed_at": "2024-01-01T00:00:00Z",
                },
                "derivedStructData": {"snippets": [{"snippet": "test snippet"}]},
            },
        }

        result = parser._parse_single_result(raw_result, "test query")

        assert result.project_id == "test-project"
        assert result.dataset_id == "test_dataset"
        assert result.table_id == "test_table"
        assert "test snippet" in result.content_snippet

    def test_pagination_info(self) -> None:
        """Test extraction of pagination information."""
        parser = SearchResultParser(project_id="test-project")

        raw_response = {
            "results": [
                {
                    "id": "test-project.test_dataset.test_table",
                    "document": {
                        "structData": {
                            "project_id": "test-project",
                            "dataset_id": "test_dataset",
                            "table_id": "test_table",
                            "asset_type": "TABLE",
                            "indexed_at": "2024-01-01T00:00:00Z",
                        },
                        "derivedStructData": {"snippets": [{"snippet": "test snippet"}]},
                    },
                }
            ],
            "totalSize": 100,
            "nextPageToken": "token123",
        }

        response = parser.parse_response(raw_response, query="test query")

        assert isinstance(response, SearchResponse)
        assert response.total_count == 100
        assert response.next_page_token == "token123"

    def test_handles_missing_fields(self) -> None:
        """Test handling of missing optional fields."""
        parser = SearchResultParser(project_id="test-project")

        raw_result = {
            "id": "test-project.test_dataset.test_table",
            "document": {
                "structData": {
                    "project_id": "test-project",
                    "dataset_id": "test_dataset",
                    "table_id": "test_table",
                    "asset_type": "TABLE",
                    "indexed_at": "2024-01-01T00:00:00Z",
                    # Missing description and other optional fields
                },
                "derivedStructData": {"snippets": [{"snippet": "test snippet"}]},
            },
        }

        result = parser._parse_single_result(raw_result, "test query")

        assert result is not None
        # Should handle missing fields gracefully
        assert result.row_count is None

    def test_parse_empty_results(self) -> None:
        """Test parsing empty results."""
        parser = SearchResultParser(project_id="test-project")

        raw_response = {
            "results": [],
            "totalSize": 0,
        }

        response = parser.parse_response(raw_response, query="test query")

        assert response.results == []
        assert response.total_count == 0

    def test_extract_report_link(self) -> None:
        """Test extraction of report link if available."""
        parser = SearchResultParser(
            project_id="test-project", reports_bucket="test-bucket"
        )

        raw_result = {
            "id": "test-project.test_dataset.test_table",
            "document": {
                "structData": {
                    "project_id": "test-project",
                    "dataset_id": "test_dataset",
                    "table_id": "test_table",
                    "asset_type": "TABLE",
                    "indexed_at": "2024-01-01T00:00:00Z",
                },
                "derivedStructData": {"snippets": [{"snippet": "test snippet"}]},
            },
        }

        result = parser._parse_single_result(raw_result, "test query")

        assert result is not None
        assert result.report_link == "gs://test-bucket/test_dataset/test_table.md"

    def test_search_response_summary(self) -> None:
        """Test search response summary generation."""
        parser = SearchResultParser(project_id="test-project")

        raw_response = {
            "results": [
                {
                    "id": f"test-project.test_dataset.table{i}",
                    "document": {
                        "structData": {
                            "project_id": "test-project",
                            "dataset_id": "test_dataset",
                            "table_id": f"table{i}",
                            "asset_type": "TABLE",
                            "indexed_at": "2024-01-01T00:00:00Z",
                        },
                        "derivedStructData": {"snippets": [{"snippet": "test snippet"}]},
                    },
                }
                for i in range(3)
            ],
            "totalSize": 10,
        }

        response = parser.parse_response(raw_response, query="test query")
        summary = response.get_summary()

        assert "10" in summary
        # Should include result counts

    def test_handles_malformed_results(self) -> None:
        """Test handling of malformed results."""
        parser = SearchResultParser(project_id="test-project")

        raw_result = {
            "id": "malformed",
            # Missing document structure
        }

        # Should handle gracefully by returning result with defaults
        result = parser._parse_single_result(raw_result, "test query")
        assert result is not None
        assert result.title == "unknown"  # Default when no dataset/table found
        assert result.content_snippet == "No content available"  # Default snippet

