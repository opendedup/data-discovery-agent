"""
PRP Requirement Discovery Orchestrator

This module orchestrates the entire strategy-driven discovery workflow, from 
generating a search plan to executing targeted searches and performing context-aware 
validation to find relevant source tables for a given PRP.
"""

import logging
from typing import Any, Dict, List, Optional

from .vertex_search_client import VertexSearchClient
from .search_planner import SearchPlanner
from ..models.search_models import SearchRequest, SortOrder
from .schema_validator import SchemaValidator


class PRPRequirementDiscovery:
    """
    Discovers source tables for PRP data requirements using a multi-step, 
    strategy-driven approach.
    """
    
    def __init__(
        self,
        vertex_client: VertexSearchClient,
        search_planner: SearchPlanner,
        schema_validator: SchemaValidator,
    ):
        """
        Initialize the PRP requirement discovery orchestrator.
        
        Args:
            vertex_client: Vertex AI Search client.
            search_planner: Client for generating the strategic search plan.
            schema_validator: Client for validating schema fitness.
        """
        self.vertex_client = vertex_client
        self.search_planner = search_planner
        self.schema_validator = schema_validator
        self.logger = logging.getLogger(__name__)
    
    async def discover_for_prp(
        self,
        prp_markdown: str,
        target_schema: Dict[str, Any],
        max_results_per_query: int = 5,
        request: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        Orchestrates the discovery of source tables for a PRP.

        This process involves:
        1. Generating a strategic search plan.
        2. Executing each targeted search query in the plan.
        3. Performing context-aware validation on the results of each search.
        4. Aggregating the validated results.

        Args:
            prp_markdown: Full PRP markdown content.
            target_schema: The schema of the final target view.
            max_results_per_query: Max source tables to retrieve for each search query.
            request: Optional FastAPI Request object for cancellation detection.
            
        Returns:
            A list of discovery results, grouped by each step in the search plan.
        """
        self.logger.info("=" * 80)
        self.logger.info("STARTING STRATEGY-DRIVEN SOURCE TABLE DISCOVERY")
        self.logger.info("=" * 80)
        
        # 1. Generate the Search and Mapping Plan
        search_plan = self.search_planner.create_search_plan(prp_markdown, target_schema)
        
        all_discovery_results = []

        # 2. Execute each step in the search plan
        for i, step in enumerate(search_plan.steps, 1):
            # Check if the client is still connected before processing
            if request and await request.is_disconnected():
                self.logger.warning("Client disconnected. Cancelling discovery process.")
                break
            
            self.logger.info("-" * 80)
            self.logger.info(f"Executing Search Step {i}/{len(search_plan.steps)}: {step.conceptual_group}")
            self.logger.info(f"  - Query: \"{step.search_query}\"")
            
            try:
                # Execute semantic search for the current step
                search_request = SearchRequest(
                    query=step.search_query,
                    page_size=max_results_per_query,
                    sort_order=SortOrder.DESC,
                    include_full_content=True,
                )
                search_response = self.vertex_client.search(search_request)
                candidates = search_response.results
                
                self.logger.info(f"  ✓ Found {len(candidates)} candidate table(s)")
                
                # 3. Perform context-aware validation on the candidates
                validated_assets = []
                for j, candidate in enumerate(candidates, 1):
                    full_name = self._get_full_table_name(candidate)
                    self.logger.info(f"  - [{j}/{len(candidates)}] Evaluating: {full_name}")
                    
                    is_valid = self.schema_validator.validate_schema(
                        source_schema=candidate.metadata.schema,
                        target_columns=step.target_columns_for_validation,
                        conceptual_group=step.conceptual_group,
                        source_table_name=full_name,
                    )
                    if is_valid:
                        validated_assets.append(candidate)
                
                self.logger.info(f"  ✓ {len(validated_assets)} table(s) passed schema validation for this step.")

                # 4. Aggregate results for this step
                all_discovery_results.append({
                    "conceptual_group": step.conceptual_group,
                    "search_query": step.search_query,
                    "target_columns": [col.model_dump() for col in step.target_columns_for_validation],
                    "discovered_tables": self._format_as_discovered_assets(validated_assets),
                })

            except Exception as e:
                self.logger.error(f"  ✗ Search failed for step '{step.conceptual_group}': {e}", exc_info=True)
                all_discovery_results.append({
                    "conceptual_group": step.conceptual_group,
                    "search_query": step.search_query,
                    "target_columns": [col.model_dump() for col in step.target_columns_for_validation],
                    "discovered_tables": [],
                    "error": str(e)
                })
        
        self.logger.info("=" * 80)
        self.logger.info("STRATEGY-DRIVEN DISCOVERY COMPLETE")
        self.logger.info("=" * 80)
        
        return all_discovery_results

    def _get_full_table_name(self, result: Any) -> str:
        """Constructs the full BigQuery table name from a search result."""
        if result.metadata:
            return f"{result.metadata.project_id}.{result.metadata.dataset_id}.{result.metadata.table_id}"
        return "UNKNOWN_TABLE"

    def _format_as_discovered_assets(
        self,
        search_results: List[Any]
    ) -> List[Dict[str, Any]]:
        """
        Formats validated search results into the DiscoveredAssetDict structure.
        """
        discovered_assets = []
        for result in search_results:
            metadata = result.metadata
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
                "relevance_score": result.score,
            }
            discovered_assets.append(asset)
        
        return discovered_assets

