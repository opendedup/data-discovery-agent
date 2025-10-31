"""
Search Result Parser for Vertex AI Search

Parses and enriches search results from Vertex AI Search.
Formats results for presentation to users with proper citations and context.
"""

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SearchResult(BaseModel):
    """Single search result with metadata and content"""
    
    # Identity
    id: str = Field(..., description="Unique document ID")
    title: str = Field(..., description="Display title")
    
    # Match info
    score: float = Field(..., description="Relevance score")
    matched_query: str = Field(..., description="Query that matched")
    
    # Structured data (for filtering and display)
    project_id: str
    dataset_id: Optional[str] = None
    table_id: Optional[str] = None
    asset_type: str
    
    # Key attributes
    has_pii: bool = False
    has_phi: bool = False
    row_count: Optional[int] = None
    size_bytes: Optional[int] = None
    monthly_cost_usd: Optional[float] = None
    
    # Content snippet
    content_snippet: str = Field(..., description="Relevant content excerpt")
    
    # Full content (optional)
    full_content: Optional[str] = None
    
    # Metadata
    indexed_at: str
    last_modified: Optional[str] = None
    
    # Links
    console_link: Optional[str] = None
    report_link: Optional[str] = None


class SearchResponse(BaseModel):
    """Complete search response with results and metadata"""
    
    # Query info
    query: str = Field(..., description="Original query")
    filter: Optional[str] = Field(None, description="Applied filter")
    
    # Results
    results: List[SearchResult] = Field(default_factory=list)
    total_count: int = Field(0, description="Total matching documents")
    
    # Facets (for aggregations)
    facets: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    
    # Performance
    query_time_ms: float = Field(..., description="Query execution time")
    
    # Pagination
    page_size: int
    next_page_token: Optional[str] = None
    
    # Suggestions
    suggested_queries: List[str] = Field(default_factory=list)
    
    def get_summary(self) -> str:
        """Get human-readable summary of results"""
        
        if not self.results:
            return f"No results found for '{self.query}'"
        
        summary = f"Found {self.total_count} result(s) for '{self.query}'"
        
        if self.filter:
            summary += f" (filtered by: {self.filter})"
        
        summary += f" in {self.query_time_ms:.0f}ms"
        
        return summary


class SearchResultParser:
    """
    Parses Vertex AI Search API responses into structured SearchResponse objects.
    
    Handles:
    - Extracting structured data from document fields
    - Generating content snippets
    - Creating console links
    - Computing relevance scores
    """
    
    def __init__(self, project_id: str, reports_bucket: Optional[str] = None):
        self.project_id = project_id
        self.reports_bucket = reports_bucket
    
    def parse_response(
        self,
        api_response: Dict[str, Any],
        query: str,
        filter_expr: Optional[str] = None,
    ) -> SearchResponse:
        """
        Parse Vertex AI Search API response.
        
        Args:
            api_response: Raw API response from Vertex AI Search
            query: Original query string
            filter_expr: Filter expression used
        
        Returns:
            Parsed SearchResponse
        """
        
        # Extract results
        raw_results = api_response.get("results", [])
        parsed_results = [
            self._parse_single_result(r, query)
            for r in raw_results
        ]
        
        # Extract total count
        total_count = api_response.get("totalSize", len(parsed_results))
        
        # Extract facets (if any)
        facets = self._parse_facets(api_response.get("facets", []))
        
        # Extract query time
        # Note: Vertex AI Search doesn't return query time, estimate from client
        query_time_ms = api_response.get("queryTime", 0) * 1000
        
        # Extract pagination
        next_page_token = api_response.get("nextPageToken")
        
        # Generate suggested queries
        suggested_queries = self._generate_suggestions(
            query, parsed_results, api_response
        )
        
        return SearchResponse(
            query=query,
            filter=filter_expr,
            results=parsed_results,
            total_count=total_count,
            facets=facets,
            query_time_ms=query_time_ms,
            page_size=len(parsed_results),
            next_page_token=next_page_token,
            suggested_queries=suggested_queries,
        )
    
    def _parse_single_result(
        self, raw_result: Dict[str, Any], query: str
    ) -> SearchResult:
        """Parse a single search result from API response"""
        
        # Extract document
        document = raw_result.get("document", {})
        doc_id = document.get("id", "unknown")
        
        # Extract structured data
        struct_data = document.get("structData", {})
        
        # Extract content
        content = document.get("derivedStructData", {}).get("snippets", [])
        content_snippet = self._extract_snippet(content, document.get("content", {}))
        
        # Extract full content if available
        full_content = None
        if content_obj := document.get("content"):
            full_content = content_obj.get("text")
        
        # Build title
        project = struct_data.get("project_id", self.project_id)
        dataset = struct_data.get("dataset_id", "")
        table = struct_data.get("table_id", "")
        title = f"{project}.{dataset}.{table}" if project and dataset and table else doc_id
        
        # Extract score
        # Note: Vertex AI Search may not return explicit scores
        score = raw_result.get("relevanceScore", 1.0)
        
        # Build console link
        console_link = self._build_console_link(
            struct_data.get("project_id", self.project_id),
            dataset,
            table,
            struct_data.get("asset_type", "TABLE"),
        )
        
        # Build report link
        report_link = None
        if self.reports_bucket and dataset and table:
            report_link = f"gs://{self.reports_bucket}/{dataset}/{table}.md"
        
        return SearchResult(
            id=doc_id,
            title=title,
            score=score,
            matched_query=query,
            project_id=struct_data.get("project_id", self.project_id),
            dataset_id=dataset,
            table_id=table,
            asset_type=struct_data.get("asset_type", "TABLE"),
            has_pii=struct_data.get("has_pii", False),
            has_phi=struct_data.get("has_phi", False),
            row_count=struct_data.get("row_count"),
            size_bytes=struct_data.get("size_bytes"),
            monthly_cost_usd=struct_data.get("monthly_cost_usd"),
            content_snippet=content_snippet,
            full_content=full_content,
            indexed_at=struct_data.get("indexed_at", ""),
            last_modified=struct_data.get("last_modified_timestamp"),
            console_link=console_link,
            report_link=report_link,
        )
    
    def _extract_snippet(
        self, snippets: List[Dict[str, Any]], content: Dict[str, Any]
    ) -> str:
        """Extract content snippet from search result"""
        
        if snippets:
            # Use first snippet
            snippet_text = snippets[0].get("snippet", "")
            if snippet_text:
                return snippet_text
        
        # Fallback: extract from full content
        if content_text := content.get("text"):
            # Take first 200 characters
            return content_text[:200] + "..." if len(content_text) > 200 else content_text
        
        return "No content available"
    
    def _build_console_link(
        self, project_id: str, dataset_id: str, table_id: str, asset_type: str
    ) -> Optional[str]:
        """Build BigQuery Console link"""
        
        if not all([project_id, dataset_id, table_id]):
            return None
        
        if asset_type in ["TABLE", "VIEW", "MATERIALIZED_VIEW"]:
            return (
                f"https://console.cloud.google.com/bigquery?"
                f"project={project_id}&"
                f"ws=!1m5!1m4!4m3!1s{project_id}!2s{dataset_id}!3s{table_id}"
            )
        
        return None
    
    def _parse_facets(self, raw_facets: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Parse facet results from aggregation queries"""
        
        facets = {}
        
        for facet in raw_facets:
            facet_key = facet.get("key", "unknown")
            values = []
            
            for value in facet.get("values", []):
                values.append({
                    "value": value.get("value"),
                    "count": value.get("count", 0),
                })
            
            facets[facet_key] = values
        
        return facets
    
    def _generate_suggestions(
        self,
        query: str,
        results: List[SearchResult],
        api_response: Dict[str, Any],
    ) -> List[str]:
        """Generate suggested queries based on results"""
        
        suggestions = []
        
        # If no results, suggest broader query
        if not results:
            suggestions.append(query.replace(" AND ", " "))
            suggestions.append(query.replace("=", "contains"))
        
        # If many results, suggest refinements
        elif len(results) > 50:
            # Suggest filtering by environment
            suggestions.append(f"{query} environment:prod")
            
            # Suggest filtering by PII
            suggestions.append(f"{query} has_pii:true")
            
            # Suggest filtering by recent
            suggestions.append(f"{query} last_modified > 2024-01-01")
        
        # Suggest related queries based on facets
        if api_response.get("facets"):
            for facet in api_response["facets"]:
                facet_key = facet.get("key")
                top_value = facet.get("values", [{}])[0].get("value")
                if facet_key and top_value:
                    suggestions.append(f"{query} {facet_key}:{top_value}")
        
        return suggestions[:3]  # Limit to 3 suggestions
    
    def format_results_for_display(
        self, response: SearchResponse, format_type: str = "text"
    ) -> str:
        """
        Format search results for display.
        
        Args:
            response: SearchResponse object
            format_type: Output format ("text", "markdown", "json")
        
        Returns:
            Formatted string
        """
        
        if format_type == "json":
            return response.model_dump_json(indent=2)
        
        elif format_type == "markdown":
            return self._format_markdown(response)
        
        else:  # text
            return self._format_text(response)
    
    def _format_text(self, response: SearchResponse) -> str:
        """Format as plain text"""
        
        lines = []
        lines.append(response.get_summary())
        lines.append("")
        
        for i, result in enumerate(response.results, 1):
            lines.append(f"{i}. {result.title}")
            
            # Metadata line
            meta = []
            if result.asset_type:
                meta.append(result.asset_type)
            if result.has_pii:
                meta.append("PII")
            if result.row_count:
                meta.append(f"{result.row_count:,} rows")
            if result.monthly_cost_usd:
                meta.append(f"${result.monthly_cost_usd:.2f}/mo")
            
            if meta:
                lines.append(f"   {' | '.join(meta)}")
            
            # Snippet
            lines.append(f"   {result.content_snippet[:150]}...")
            
            # Link
            if result.console_link:
                lines.append(f"   Link: {result.console_link}")
            
            lines.append("")
        
        # Suggestions
        if response.suggested_queries:
            lines.append("Suggested queries:")
            for suggestion in response.suggested_queries:
                lines.append(f"  - {suggestion}")
        
        return "\n".join(lines)
    
    def _format_markdown(self, response: SearchResponse) -> str:
        """Format as Markdown"""
        
        lines = []
        lines.append(f"# Search Results: {response.query}")
        lines.append("")
        lines.append(response.get_summary())
        lines.append("")
        
        for i, result in enumerate(response.results, 1):
            lines.append(f"## {i}. {result.title}")
            lines.append("")
            
            # Metadata table
            lines.append("| Attribute | Value |")
            lines.append("|-----------|-------|")
            lines.append(f"| Type | {result.asset_type} |")
            if result.row_count:
                lines.append(f"| Rows | {result.row_count:,} |")
            if result.size_bytes:
                size_gb = result.size_bytes / (1024**3)
                lines.append(f"| Size | {size_gb:.2f} GB |")
            if result.monthly_cost_usd:
                lines.append(f"| Cost | ${result.monthly_cost_usd:.2f}/month |")
            if result.has_pii:
                lines.append("| Classification | PII |")
            lines.append("")
            
            # Snippet
            lines.append("### Description")
            lines.append("")
            lines.append(result.content_snippet)
            lines.append("")
            
            # Links
            if result.console_link:
                lines.append(f"[View in BigQuery Console]({result.console_link})")
            if result.report_link:
                lines.append(f" | [Full Report]({result.report_link})")
            lines.append("")
            lines.append("---")
            lines.append("")
        
        # Suggestions
        if response.suggested_queries:
            lines.append("## 💡 Suggested Queries")
            lines.append("")
            for suggestion in response.suggested_queries:
                lines.append(f"- `{suggestion}`")
        
        return "\n".join(lines)

