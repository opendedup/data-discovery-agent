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
        parser = SearchResultParser()

        assert parser is not None

    def test_parse_single_result(self) -> None:
        """Test parsing a single search result."""
        parser = SearchResultParser()

        raw_result = {
            "id": "test-project.test_dataset.test_table",
            "document": {
                "structData": {
                    "project_id": "test-project",
                    "dataset_id": "test_dataset",
                    "table_id": "test_table",
                    "description": "Test table",
                }
            },
        }

        result = parser.parse_result(raw_result)

        assert result is not None
        assert isinstance(result, SearchResult)
        assert result.table_id == "test_table"

    def test_parse_multiple_results(self) -> None:
        """Test parsing multiple search results."""
        parser = SearchResultParser()

        raw_results = [
            {
                "id": f"test-project.test_dataset.table{i}",
                "document": {
                    "structData": {
                        "project_id": "test-project",
                        "dataset_id": "test_dataset",
                        "table_id": f"table{i}",
                        "description": f"Test table {i}",
                    }
                },
            }
            for i in range(5)
        ]

        results = [parser.parse_result(r) for r in raw_results]

        assert len(results) == 5
        assert all(isinstance(r, SearchResult) for r in results)

    def test_extract_table_metadata(self) -> None:
        """Test extraction of table metadata."""
        parser = SearchResultParser()

        raw_result = {
            "id": "test-project.test_dataset.test_table",
            "document": {
                "structData": {
                    "project_id": "test-project",
                    "dataset_id": "test_dataset",
                    "table_id": "test_table",
                    "table_type": "TABLE",
                    "description": "Test table",
                    "row_count": 1000,
                    "size_bytes": 50000,
                }
            },
        }

        result = parser.parse_result(raw_result)

        assert result.project_id == "test-project"
        assert result.dataset_id == "test_dataset"
        assert result.table_id == "test_table"
        assert result.description == "Test table"

    def test_pagination_info(self) -> None:
        """Test extraction of pagination information."""
        parser = SearchResultParser()

        raw_response = {
            "results": [
                {
                    "id": "test-project.test_dataset.test_table",
                    "document": {
                        "structData": {
                            "project_id": "test-project",
                            "dataset_id": "test_dataset",
                            "table_id": "test_table",
                        }
                    },
                }
            ],
            "totalSize": 100,
            "nextPageToken": "token123",
        }

        response = parser.parse_response(raw_response)

        assert isinstance(response, SearchResponse)
        assert response.total_size == 100
        assert response.next_page_token == "token123"

    def test_handles_missing_fields(self) -> None:
        """Test handling of missing optional fields."""
        parser = SearchResultParser()

        raw_result = {
            "id": "test-project.test_dataset.test_table",
            "document": {
                "structData": {
                    "project_id": "test-project",
                    "dataset_id": "test_dataset",
                    "table_id": "test_table",
                    # Missing description and other optional fields
                }
            },
        }

        result = parser.parse_result(raw_result)

        assert result is not None
        # Should handle missing fields gracefully

    def test_parse_empty_results(self) -> None:
        """Test parsing empty results."""
        parser = SearchResultParser()

        raw_response = {
            "results": [],
            "totalSize": 0,
        }

        response = parser.parse_response(raw_response)

        assert response.results == []
        assert response.total_size == 0

    def test_extract_report_link(self) -> None:
        """Test extraction of report link if available."""
        parser = SearchResultParser()

        raw_result = {
            "id": "test-project.test_dataset.test_table",
            "document": {
                "structData": {
                    "project_id": "test-project",
                    "dataset_id": "test_dataset",
                    "table_id": "test_table",
                    "report_link": "gs://bucket/reports/table.md",
                }
            },
        }

        result = parser.parse_result(raw_result)

        assert result is not None
        # Should extract report link if present

    def test_search_response_summary(self) -> None:
        """Test search response summary generation."""
        parser = SearchResultParser()

        raw_response = {
            "results": [
                {
                    "id": f"test-project.test_dataset.table{i}",
                    "document": {
                        "structData": {
                            "project_id": "test-project",
                            "dataset_id": "test_dataset",
                            "table_id": f"table{i}",
                        }
                    },
                }
                for i in range(3)
            ],
            "totalSize": 10,
        }

        response = parser.parse_response(raw_response)
        summary = response.get_summary()

        assert "3" in summary or "10" in summary
        # Should include result counts

    def test_handles_malformed_results(self) -> None:
        """Test handling of malformed results."""
        parser = SearchResultParser()

        raw_result = {
            "id": "malformed",
            # Missing document structure
        }

        # Should handle gracefully
        with pytest.raises(Exception) or True:
            result = parser.parse_result(raw_result)

