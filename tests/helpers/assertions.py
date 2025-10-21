"""Custom assertion helpers for test validation."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from data_discovery_agent.search.jsonl_schema import BigQueryAssetSchema


def assert_valid_table_description(
    description: Optional[str], min_length: int = 10
) -> None:
    """
    Assert that a table description is valid and meaningful.
    
    Args:
        description: Table description to validate
        min_length: Minimum length for description
        
    Raises:
        AssertionError: If description is invalid
    """
    assert description is not None, "Table description cannot be None"
    assert description.strip(), "Table description cannot be empty"
    assert (
        len(description.strip()) >= min_length
    ), f"Table description too short (min {min_length} chars): {description}"


def assert_valid_column_description(
    description: Optional[str], column_name: str, min_length: int = 5
) -> None:
    """
    Assert that a column description is valid.
    
    Args:
        description: Column description to validate
        column_name: Name of the column
        min_length: Minimum length for description
        
    Raises:
        AssertionError: If description is invalid
    """
    assert (
        description is not None
    ), f"Column '{column_name}' description cannot be None"
    assert description.strip(), f"Column '{column_name}' description cannot be empty"
    assert len(description.strip()) >= min_length, (
        f"Column '{column_name}' description too short "
        f"(min {min_length} chars): {description}"
    )


def assert_valid_bigquery_asset(
    asset: BigQueryAssetSchema, table_type: str = "TABLE"
) -> None:
    """
    Assert that a BigQueryAssetSchema is valid and complete.
    
    Args:
        asset: BigQueryAssetSchema to validate
        table_type: Expected table type (TABLE or VIEW)
        
    Raises:
        AssertionError: If asset is invalid
    """
    # Validate ID
    assert asset.id, "Asset ID cannot be empty"
    assert "." in asset.id, "Asset ID must be in format project.dataset.table"

    # Validate content (ContentData is a Pydantic model, not a dict)
    assert asset.content, "Asset content cannot be None"
    assert asset.content.mime_type, "Content mime_type is required"
    assert asset.content.text, "Content text is required"

    # Validate structData (StructData is a Pydantic model, not a dict)
    assert asset.struct_data, "Asset struct_data cannot be None"
    struct_data = asset.struct_data

    # Required fields
    assert struct_data.project_id, "project_id is required"
    assert struct_data.dataset_id, "dataset_id is required"
    assert struct_data.table_id, "table_id is required"
    
    # Check table_type if specified
    if table_type:
        actual_type = struct_data.table_type if hasattr(struct_data, 'table_type') else struct_data.asset_type
        # Handle enum or string
        actual_type_str = actual_type if isinstance(actual_type, str) else str(actual_type)
        assert actual_type_str == table_type, f"Expected {table_type}, got {actual_type_str}"

    # Description validation
    description = getattr(struct_data, "description", None)
    assert_valid_table_description(description)

    # Statistics validation
    row_count = getattr(struct_data, "row_count", None)
    size_bytes = getattr(struct_data, "size_bytes", None)
    
    if table_type == "TABLE":
        assert row_count is not None, "row_count required for TABLE"
        assert size_bytes is not None, "size_bytes required for TABLE"
        assert row_count >= 0, "row_count must be non-negative"
        assert size_bytes >= 0, "size_bytes must be non-negative"
    elif table_type == "VIEW":
        # Views may have 0 or null for row_count and size_bytes
        if row_count is not None:
            assert row_count >= 0, "row_count must be non-negative"
        if size_bytes is not None:
            assert size_bytes >= 0, "size_bytes must be non-negative"

    # Timestamp validation
    created_time = getattr(struct_data, "created_timestamp", None) or getattr(struct_data, "created_time", None)
    modified_time = getattr(struct_data, "last_modified_timestamp", None) or getattr(struct_data, "modified_time", None)
    assert created_time, "created_time or created_timestamp is required"
    assert modified_time, "modified_time or last_modified_timestamp is required"

    # Schema validation
    schema_info = getattr(struct_data, "schema_info", None)
    if schema_info:
        # schema_info is a dict, so use dict access instead of getattr
        schema = schema_info.get("fields", []) if isinstance(schema_info, dict) else getattr(schema_info, "fields", [])
        assert schema, "Schema fields cannot be empty"
        for field in schema:
            # Fields are also dicts
            if isinstance(field, dict):
                field_name = field.get("name")
                field_type = field.get("type")
                field_desc = field.get("description")
            else:
                field_name = getattr(field, "name", None)
                field_type = getattr(field, "type", None)
                field_desc = getattr(field, "description", None)
            assert field_name, "column name is required"
            assert field_type, "column type is required"
            assert_valid_column_description(field_desc, field_name or "unknown")


def assert_valid_markdown(markdown: str, table_id: str) -> None:
    """
    Assert that markdown content is valid and well-formed.
    
    Args:
        markdown: Markdown content to validate
        table_id: Expected table ID in markdown
        
    Raises:
        AssertionError: If markdown is invalid
    """
    assert markdown, "Markdown content cannot be empty"

    # Check for main sections
    assert "# " in markdown, "Markdown must have H1 header"
    assert "## Overview" in markdown, "Markdown must have Overview section"
    assert "## Schema" in markdown, "Markdown must have Schema section"
    assert "## Statistics" in markdown, "Markdown must have Statistics section"

    # Check for table in markdown
    assert table_id in markdown, f"Table ID '{table_id}' must be in markdown"

    # Check for table syntax (schema table)
    assert "|" in markdown, "Markdown must contain table syntax"
    assert "Column Name" in markdown or "column_name" in markdown.lower(), (
        "Schema section must have column names"
    )

    # Check for no broken links
    broken_link_pattern = r'\[.*?\]\(\s*\)'
    broken_links = re.findall(broken_link_pattern, markdown)
    assert not broken_links, f"Markdown contains broken links: {broken_links}"


def assert_valid_lineage_event(
    event: Dict[str, Any],
    expected_source: Optional[str] = None,
    expected_target: Optional[str] = None,
) -> None:
    """
    Assert that a lineage event is valid and complete.
    
    Args:
        event: Lineage event dictionary
        expected_source: Expected source FQN
        expected_target: Expected target FQN
        
    Raises:
        AssertionError: If lineage event is invalid
    """
    assert event, "Lineage event cannot be None"
    assert "name" in event or "links" in event, "Event must have name or links"

    if "links" in event:
        links = event["links"]
        assert links, "Lineage event must have at least one link"

        for link in links:
            assert "source" in link, "Link must have source"
            assert "target" in link, "Link must have target"

            source = link["source"]
            target = link["target"]

            assert source.get(
                "fully_qualified_name"
            ), "Source must have fully_qualified_name"
            assert target.get(
                "fully_qualified_name"
            ), "Target must have fully_qualified_name"

            source_fqn = source["fully_qualified_name"]
            target_fqn = target["fully_qualified_name"]

            # Validate FQN format
            assert (
                ":" in source_fqn or "://" in source_fqn
            ), f"Invalid source FQN format: {source_fqn}"
            assert (
                ":" in target_fqn or "://" in target_fqn
            ), f"Invalid target FQN format: {target_fqn}"

            # Check expected values if provided
            if expected_source:
                assert (
                    source_fqn == expected_source
                ), f"Expected source {expected_source}, got {source_fqn}"
            if expected_target:
                assert (
                    target_fqn == expected_target
                ), f"Expected target {expected_target}, got {target_fqn}"


def assert_valid_schema_field(
    field: Dict[str, Any], required_description: bool = True
) -> None:
    """
    Assert that a schema field is valid.
    
    Args:
        field: Schema field dictionary
        required_description: Whether description is required
        
    Raises:
        AssertionError: If schema field is invalid
    """
    assert "column_name" in field or "name" in field, "Field must have name"
    assert "column_type" in field or "type" in field, "Field must have type"

    if required_description:
        description = field.get("column_description") or field.get("description")
        assert_valid_column_description(
            description, field.get("column_name") or field.get("name")
        )


def assert_statistics_valid(
    stats: Dict[str, Any], table_type: str = "TABLE"
) -> None:
    """
    Assert that table statistics are valid.
    
    Args:
        stats: Statistics dictionary
        table_type: Table type (TABLE or VIEW)
        
    Raises:
        AssertionError: If statistics are invalid
    """
    if table_type == "TABLE":
        assert "row_count" in stats, "TABLE must have row_count"
        assert "size_bytes" in stats, "TABLE must have size_bytes"
        assert stats["row_count"] >= 0, "row_count must be non-negative"
        assert stats["size_bytes"] > 0, "TABLE size_bytes must be > 0"
    elif table_type == "VIEW":
        # Views may have 0 or null values
        if "row_count" in stats and stats["row_count"] is not None:
            assert stats["row_count"] >= 0, "row_count must be non-negative"
        if "size_bytes" in stats and stats["size_bytes"] is not None:
            assert stats["size_bytes"] >= 0, "size_bytes must be non-negative"

    assert "created_time" in stats or "created" in stats, "Must have creation time"
    assert "modified_time" in stats or "modified" in stats, "Must have modified time"

