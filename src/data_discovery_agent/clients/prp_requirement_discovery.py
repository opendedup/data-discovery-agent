"""
PRP Requirement Discovery

Discovers source tables for PRP Section 9 data requirements using semantic search.
"""

import logging
from typing import Any, Dict, List, Optional

from .vertex_search_client import VertexSearchClient
from ..parsers.prp_extractor import PRPExtractor
from ..schemas.asset_schema import DiscoveredAssetDict
from ..models.search_models import SearchRequest, SortOrder
from .schema_validator import SchemaValidator
from ..mcp.tools import REQUEST_USER_CONFIRMATION_TOOL

logger = logging.getLogger(__name__)


class UserConfirmationNeeded(Exception):
    """Custom exception to signal that user confirmation is required."""
    def __init__(self, gap_details: Dict[str, Any], candidate_tables: List[str]):
        self.gap_details = gap_details
        self.candidate_tables = candidate_tables
        super().__init__("User confirmation is needed to resolve a data gap.")


class PRPRequirementDiscovery:
    """
    Discovers source tables for PRP data requirements.
    
    Combines Gemini extraction with Vertex AI semantic search to find
    relevant source tables for each target table specification.
    """
    
    def __init__(
        self,
        vertex_client: VertexSearchClient,
        prp_extractor: PRPExtractor,
        schema_validator: SchemaValidator,
    ):
        """
        Initialize PRP requirement discovery.
        
        Args:
            vertex_client: Vertex AI Search client
            prp_extractor: PRP extractor for Section 9 parsing
            schema_validator: Client for validating schema fitness
        """
        self.vertex_client = vertex_client
        self.prp_extractor = prp_extractor
        self.schema_validator = schema_validator
        self.logger = logging.getLogger(__name__)
    
    async def discover_for_prp(
        self,
        prp_markdown: str,
        max_results_per_table: int = 5,
        resolved_gaps: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Discover source tables for each PRP requirement.
        
        Args:
            prp_markdown: Full PRP markdown or Section 9 content
            max_results_per_table: Maximum source tables to return per target
            resolved_gaps: Optional dict of user-confirmed gap resolutions
                Format: {"gap_id": {"resolved": True, "selected_table": "table_id", ...}}
            
        Returns:
            List of discovery results, one per target table:
            [
                {
                    "target_table_name": str,
                    "target_description": str,
                    "target_columns": List[Dict],
                    "discovered_tables": List[DiscoveredAssetDict],
                    "search_query": str
                }
            ]
        """
        self.logger.info("=" * 80)
        self.logger.info("DISCOVERING SOURCE TABLES FOR PRP REQUIREMENTS")
        self.logger.info("=" * 80)
        
        # Extract target tables and data gaps using the updated extractor
        target_tables, data_gaps = self.prp_extractor.extract_section_9(prp_markdown)
        
        # Create a map of data gaps by target view for easy lookup
        gaps_by_target = {gap['target_view']: gap for gap in data_gaps}
        
        self.logger.info(f"Discovering source tables for {len(target_tables)} target(s)")
        self.logger.info("=" * 80)
        
        discovery_results = []
        for i, target in enumerate(target_tables, 1):
            target_name = target.get('table_name', 'UNKNOWN')
            self.logger.info(f"[{i}/{len(target_tables)}] Searching for: {target_name}")
            
            # Check if there's a data gap for this target
            relevant_gap = gaps_by_target.get(target_name)
            if relevant_gap:
                self.logger.info(f"  - Detected data gap: {relevant_gap.get('description')}")

            # Build search query from target specification
            search_query = self._build_search_query(target)
            self.logger.debug(f"  Search query: {search_query}")
            
            # Execute semantic search
            try:
                search_request = SearchRequest(
                    query=search_query,
                    page_size=max_results_per_table,
                    sort_order=SortOrder.DESC,
                    include_full_content=True,
                )
                
                search_response = self.vertex_client.search(search_request)
                results = search_response.results
                
                self.logger.info(f"  ✓ Found {len(results)} candidate table(s)")
                
                # Validate and filter results
                validated_results = []
                for i, result in enumerate(results, 1):
                    # Extract table information for logging
                    table_id = result.metadata.table_id if result.metadata else "UNKNOWN"
                    full_name = f"{result.metadata.project_id}.{result.metadata.dataset_id}.{table_id}" if result.metadata else "UNKNOWN"
                    
                    self.logger.info(f"  [{i}/{len(results)}] Evaluating: {full_name}")
                    
                    is_valid = self.schema_validator.validate_schema(
                        source_schema=result.metadata.schema,
                        target_view=target,
                        data_gap=relevant_gap,
                        source_table_name=full_name,
                    )
                    if is_valid:
                        validated_results.append(result)
                
                self.logger.info(f"  ✓ {len(validated_results)} table(s) passed schema validation")
                
                # Log top 3 results
                for j, result in enumerate(validated_results[:3], 1):
                    table_id = result.metadata.table_id if result.metadata else "UNKNOWN"
                    score = result.score if hasattr(result, 'score') else 0.0
                    self.logger.debug(
                        f"    {j}. {table_id} "
                        f"(score: {score:.2f})"
                    )
                
                # Format as DiscoveredAssetDict for query generation
                discovered_assets = self._format_as_discovered_assets(validated_results)
                
                # If a gap exists and we still have no validated tables, ask the user
                if relevant_gap and not validated_results:
                    self.logger.warning(f"  ! No validated tables found for gap: {relevant_gap['gap_id']}")
                    
                    candidate_ids = [r.metadata.table_id for r in results] # Use pre-validation results as candidates
                    
                    # Signal that we need user confirmation
                    raise UserConfirmationNeeded(
                        gap_details=relevant_gap,
                        candidate_tables=candidate_ids
                    )

                discovery_results.append({
                    "target_table_name": target_name,
                    "target_description": target.get('description', ''),
                    "target_columns": target.get('columns', []),
                    "discovered_tables": discovered_assets,
                    "search_query": search_query
                })
                
            except Exception as e:
                self.logger.error(f"  ✗ Search failed for {target_name}: {e}")
                # Add empty result for this target
                discovery_results.append({
                    "target_table_name": target_name,
                    "target_description": target.get('description', ''),
                    "target_columns": target.get('columns', []),
                    "discovered_tables": [],
                    "search_query": search_query,
                    "error": str(e)
                })
            
            self.logger.info("-" * 80)
        
        self.logger.info("=" * 80)
        self.logger.info("DISCOVERY COMPLETE")
        self.logger.info("=" * 80)
        
        return discovery_results
    
    def _build_search_query(self, target: Dict[str, Any]) -> str:
        """
        Build semantic search query from target table specification.
        
        Combines description and column names for rich semantic matching.
        
        Args:
            target: Target table specification
            
        Returns:
            Search query string
        """
        description = target.get('description', '')
        columns = target.get('columns', [])
        
        # Extract column names
        column_names = [col.get('name', '') for col in columns if col.get('name')]
        
        # Combine description with key column names (first 10 for brevity)
        query_parts = [description]
        if column_names:
            query_parts.append(" ".join(column_names[:10]))
        
        search_query = " ".join(query_parts).strip()
        
        # Limit query length (Vertex AI Search has limits)
        if len(search_query) > 500:
            search_query = search_query[:500]
        
        return search_query
    
    def _format_as_discovered_assets(
        self,
        search_results: List[Any]
    ) -> List[Dict[str, Any]]:
        """
        Format search results as DiscoveredAssetDict for query generation.
        
        Args:
            search_results: Raw search results from Vertex AI Search
            
        Returns:
            List of asset dictionaries in BigQuery writer format
        """
        discovered_assets = []
        
        for result in search_results:
            # Convert SearchResultItem to dict format expected by query-generation-agent
            # Access attributes from result.metadata (AssetMetadata)
            metadata = result.metadata if hasattr(result, 'metadata') else None
            
            if not metadata:
                continue
            
            asset = {
                "table_id": metadata.table_id or "",
                "project_id": metadata.project_id or "",
                "dataset_id": metadata.dataset_id or "",
                "asset_type": metadata.asset_type or "TABLE",
                "description": metadata.description or "",
                "schema": metadata.schema if hasattr(metadata, 'schema') else [],
                "row_count": metadata.row_count,
                "column_count": metadata.column_count,
                "size_bytes": metadata.size_bytes,
                "has_pii": metadata.has_pii,
                "has_phi": metadata.has_phi,
                "relevance_score": result.score if hasattr(result, 'score') else 0.0,
            }
            
            discovered_assets.append(asset)
        
        return discovered_assets

