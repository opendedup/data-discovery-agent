"""
Search Query Builder for Vertex AI Search

Translates natural language user queries into optimized Vertex AI Search queries.
Handles semantic search, structured filtering, and hybrid queries.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class SearchQueryBuilder:
    """
    Builds optimized queries for Vertex AI Search.
    
    Responsibilities:
    1. Parse natural language queries
    2. Extract structured filters (project, dataset, has_pii, etc.)
    3. Build semantic search queries
    4. Combine semantic + structured for hybrid search
    5. Add boost factors for ranking
    """
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        
        # Filter extraction patterns
        self.filter_patterns = {
            "project": r"(?:project|proj)[\s:=]+['\"]?([a-zA-Z0-9_-]+)['\"]?",
            "dataset": r"(?:dataset|db)[\s:=]+['\"]?([a-zA-Z0-9_-]+)['\"]?",
            "has_pii": r"(?:has )?pii|contains pii|pii data",
            "has_phi": r"(?:has )?phi|contains phi|phi data",
            "environment": r"(?:environment|env)[\s:=]+['\"]?(prod|staging|dev)['\"]?",
            "team": r"(?:team|owner)[\s:=]+['\"]?([a-zA-Z0-9_-]+)['\"]?",
        }
    
    def build_query(
        self,
        user_query: str,
        explicit_filters: Optional[Dict[str, Any]] = None,
        page_size: int = 10,
        order_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build complete Vertex AI Search query from user input.
        
        Args:
            user_query: Natural language query from user
            explicit_filters: Additional filters to apply
            page_size: Number of results to return
            order_by: Field to order results by
        
        Returns:
            Query dictionary for Vertex AI Search API
        """
        
        # Parse query to extract semantic and structured components
        semantic_query, extracted_filters = self._parse_query(user_query)
        
        # Merge explicit filters
        if explicit_filters:
            extracted_filters.update(explicit_filters)
        
        # Build filter expression
        filter_expr = self._build_filter_expression(extracted_filters)
        
        # Build query
        query = {
            "query": semantic_query.strip(),
            "page_size": page_size,
        }
        
        if filter_expr:
            query["filter"] = filter_expr
        
        if order_by:
            query["order_by"] = order_by
        
        # Add boost factors for better ranking
        query["boost_spec"] = self._build_boost_spec(user_query)
        
        logger.info(f"Built query: semantic='{semantic_query}', filter='{filter_expr}'")
        
        return query
    
    def _parse_query(self, user_query: str) -> Tuple[str, Dict[str, Any]]:
        """
        Parse user query into semantic query and structured filters.
        
        Returns:
            (semantic_query, extracted_filters)
        """
        
        extracted_filters = {}
        remaining_query = user_query
        
        # Extract project filter
        if match := re.search(self.filter_patterns["project"], user_query, re.IGNORECASE):
            extracted_filters["project_id"] = match.group(1)
            remaining_query = remaining_query.replace(match.group(0), "")
        
        # Extract dataset filter
        if match := re.search(self.filter_patterns["dataset"], user_query, re.IGNORECASE):
            extracted_filters["dataset_id"] = match.group(1)
            remaining_query = remaining_query.replace(match.group(0), "")
        
        # Extract PII flag
        if re.search(self.filter_patterns["has_pii"], user_query, re.IGNORECASE):
            extracted_filters["has_pii"] = True
            remaining_query = re.sub(
                self.filter_patterns["has_pii"], "", remaining_query, flags=re.IGNORECASE
            )
        
        # Extract PHI flag
        if re.search(self.filter_patterns["has_phi"], user_query, re.IGNORECASE):
            extracted_filters["has_phi"] = True
            remaining_query = re.sub(
                self.filter_patterns["has_phi"], "", remaining_query, flags=re.IGNORECASE
            )
        
        # Extract environment
        if match := re.search(self.filter_patterns["environment"], user_query, re.IGNORECASE):
            extracted_filters["environment"] = match.group(1).lower()
            remaining_query = remaining_query.replace(match.group(0), "")
        
        # Extract team
        if match := re.search(self.filter_patterns["team"], user_query, re.IGNORECASE):
            extracted_filters["team"] = match.group(1)
            remaining_query = remaining_query.replace(match.group(0), "")
        
        # Extract size/cost filters
        remaining_query, size_filter = self._extract_numeric_filter(
            remaining_query, ["size", "bytes", "GB"], "size_bytes"
        )
        if size_filter:
            extracted_filters.update(size_filter)
        
        remaining_query, cost_filter = self._extract_numeric_filter(
            remaining_query, ["cost", "expensive"], "monthly_cost_usd"
        )
        if cost_filter:
            extracted_filters.update(cost_filter)
        
        remaining_query, row_filter = self._extract_numeric_filter(
            remaining_query, ["rows", "records"], "row_count"
        )
        if row_filter:
            extracted_filters.update(row_filter)
        
        # Clean up semantic query
        semantic_query = re.sub(r'\s+', ' ', remaining_query).strip()
        
        return semantic_query, extracted_filters
    
    def _extract_numeric_filter(
        self, query: str, keywords: List[str], field_name: str
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Extract numeric filters like "size > 100GB" or "cost < $50".
        
        Returns:
            (remaining_query, extracted_filter)
        """
        
        for keyword in keywords:
            # Pattern: keyword operator value
            pattern = rf"({keyword})\s*([><]=?|=)\s*(\$)?([0-9.]+)\s*(GB|MB|KB)?"
            
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                operator = match.group(2)
                value_str = match.group(4)
                unit = match.group(5)
                
                # Convert value to appropriate unit
                value = float(value_str)
                
                if unit:
                    unit = unit.upper()
                    if unit == "KB":
                        value *= 1024
                    elif unit == "MB":
                        value *= 1024**2
                    elif unit == "GB":
                        value *= 1024**3
                
                # Build filter
                filter_dict = {f"{field_name}__{operator}": value}
                
                # Remove from query
                remaining_query = query.replace(match.group(0), "")
                
                return remaining_query, filter_dict
        
        return query, None
    
    def _build_filter_expression(self, filters: Dict[str, Any]) -> str:
        """
        Build Vertex AI Search filter expression from extracted filters.
        
        Filter syntax:
        - field="value" for exact match
        - field>value for numeric comparison
        - field=true for boolean
        - AND/OR for combining
        """
        
        filter_parts = []
        
        # String equality filters
        for field in ["project_id", "dataset_id", "table_id", "team", "environment"]:
            if field in filters:
                value = filters[field]
                filter_parts.append(f'{field}="{value}"')
        
        # Boolean filters
        # Vertex AI Search expects: field="true" or field="false" (as strings with quotes)
        for field in ["has_pii", "has_phi"]:
            if field in filters:
                value = "true" if filters[field] else "false"
                filter_parts.append(f'{field}="{value}"')
        
        # Numeric filters with operators
        for key, value in filters.items():
            if "__" in key:
                field, operator = key.rsplit("__", 1)
                
                # Map operator
                op_map = {
                    ">": ">",
                    ">=": ">=",
                    "<": "<",
                    "<=": "<=",
                    "=": "=",
                }
                
                op = op_map.get(operator, "=")
                filter_parts.append(f"{field} {op} {value}")
        
        # Combine with AND
        return " AND ".join(filter_parts) if filter_parts else ""
    
    def _build_boost_spec(self, user_query: str) -> Dict[str, Any]:
        """
        Build boost specification for ranking.
        
        Boosts:
        - Recent tables (last_modified_timestamp)
        - High quality data (completeness_score)
        - Production environment
        - Frequently accessed tables
        """
        
        boosts = []
        
        # Boost recent data
        boosts.append({
            "condition": "last_modified_timestamp >= \"2024-01-01T00:00:00Z\"",
            "boost": 1.5,
        })
        
        # Boost production data
        boosts.append({
            "condition": "environment=\"prod\"",
            "boost": 1.3,
        })
        
        # Boost high quality data
        boosts.append({
            "condition": "completeness_score >= 0.95",
            "boost": 1.2,
        })
        
        # Context-specific boosts
        if "cost" in user_query.lower() or "expensive" in user_query.lower():
            # Boost by cost (descending)
            boosts.append({
                "condition": "monthly_cost_usd > 100",
                "boost": 2.0,
            })
        
        if "large" in user_query.lower() or "big" in user_query.lower():
            # Boost by size
            boosts.append({
                "condition": "row_count > 1000000",
                "boost": 1.5,
            })
        
        return {
            "condition_boost_specs": boosts
        }
    
    def build_aggregation_query(
        self,
        base_query: str,
        aggregation_field: str,
        top_k: int = 10,
    ) -> Dict[str, Any]:
        """
        Build aggregation query for faceted search.
        
        Example: "Show me top datasets by table count"
        
        Args:
            base_query: Base semantic query
            aggregation_field: Field to aggregate on (e.g., "dataset_id")
            top_k: Number of top results
        
        Returns:
            Query with facet specification
        """
        
        semantic_query, filters = self._parse_query(base_query)
        filter_expr = self._build_filter_expression(filters)
        
        query = {
            "query": semantic_query,
            "filter": filter_expr if filter_expr else "",
            "facet_specs": [{
                "facet_key": {
                    "key": aggregation_field,
                },
                "limit": top_k,
                "excluded_filter_keys": [],
            }]
        }
        
        return query
    
    def build_similarity_query(
        self,
        reference_table_id: str,
        similarity_threshold: float = 0.7,
        page_size: int = 10,
    ) -> Dict[str, Any]:
        """
        Build query to find similar tables.
        
        Args:
            reference_table_id: ID of reference table
            similarity_threshold: Minimum similarity score
            page_size: Number of results
        
        Returns:
            Similarity query
        """
        
        # This would use Vertex AI Search's similarity search
        # For now, build a query based on reference table's attributes
        
        query = {
            "query": f"similar to {reference_table_id}",
            "page_size": page_size,
            "similarity_threshold": similarity_threshold,
        }
        
        return query


# Example usage and testing
if __name__ == "__main__":
    import os
    project_id = os.getenv('GCP_PROJECT_ID', os.getenv('PROJECT_ID', 'your-project-id'))
    builder = SearchQueryBuilder(project_id=project_id)
    
    # Test queries
    test_queries = [
        "Find PII tables in finance dataset",
        "Show me expensive tables (cost > $100)",
        "Tables in production with more than 1M rows",
        "dataset:analytics environment:prod",
        "customer tables with PHI",
    ]
    
    for test_query in test_queries:
        print(f"\nQuery: {test_query}")
        result = builder.build_query(test_query)
        print(f"Semantic: {result['query']}")
        print(f"Filter: {result.get('filter', 'None')}")

