"""
PRP Discovery Client

Analyzes Product Requirement Prompts (PRPs) and discovers relevant datasets
using AI-powered query generation and relevance scoring.
"""

import json
import logging
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

from ..collectors.gemini_describer import GeminiDescriber
from ..clients.vertex_search_client import VertexSearchClient
from ..models.search_models import SearchRequest, SearchResponse, SortOrder
from ..schemas.asset_schema import DiscoveredAssetDict

logger = logging.getLogger(__name__)


@dataclass
class QueryExecution:
    """Record of a single query execution."""
    
    query: str
    results_count: int
    execution_time_ms: float
    top_tables: List[str]
    status: str
    error_message: Optional[str] = None


@dataclass
class QueryRefinement:
    """Record of a query refinement."""
    
    original_query: str
    refined_query: str
    reason: str


@dataclass
class DiscoveryMetadata:
    """Metadata about the discovery process."""
    
    queries_executed: List[Dict[str, Any]]
    refinements_made: List[Dict[str, Any]]
    summary: Dict[str, Any]


class PRPDiscoveryClient:
    """
    Client for discovering datasets based on Product Requirement Prompts.
    
    Uses Gemini to intelligently parse PRPs, generate targeted search queries,
    and score dataset relevance to requirements.
    """
    
    def __init__(
        self,
        vertex_client: VertexSearchClient,
        gemini_api_key: Optional[str] = None,
        max_queries: int = 10,
        min_relevance_score: float = 60.0,
    ):
        """
        Initialize PRP discovery client.
        
        Args:
            vertex_client: Vertex AI Search client for dataset discovery
            gemini_api_key: Gemini API key for LLM operations
            max_queries: Maximum number of search queries to generate
            min_relevance_score: Minimum relevance score for dataset inclusion (0-100)
        """
        self.vertex_client = vertex_client
        self.max_queries = max_queries
        self.min_relevance_score = min_relevance_score
        
        # Initialize Gemini client
        self.gemini = GeminiDescriber(
            api_key=gemini_api_key,
            model_name="gemini-2.5-pro",
        )
        
        if not self.gemini.is_enabled:
            logger.warning(
                "Gemini is not enabled. PRP discovery will be limited to keyword-based search."
            )
        
        logger.info(
            f"Initialized PRPDiscoveryClient (max_queries={max_queries}, "
            f"min_score={min_relevance_score}, gemini_enabled={self.gemini.is_enabled})"
        )
    
    async def discover_datasets_for_prp(
        self,
        prp_text: str,
        max_results: int = 10,
    ) -> Dict[str, Any]:
        """
        Discover datasets relevant to a Product Requirement Prompt.
        
        Workflow:
        1. Parse PRP and generate targeted search queries using Gemini
        2. Execute searches against Vertex AI Search
        3. Collect and deduplicate candidate datasets
        4. Score each dataset's relevance to PRP using Gemini
        5. Rank and return top N datasets
        
        Args:
            prp_text: Product Requirement Prompt as markdown text
            max_results: Maximum number of datasets to return
            
        Returns:
            Dictionary with:
                - total_count: Number of datasets found
                - datasets: List of DiscoveredAssetDict objects with relevance scores
                - discovery_metadata: Detailed metadata about the discovery process
        """
        start_time = time.time()
        logger.info(f"Starting PRP discovery (prp_length={len(prp_text)} chars)")
        
        # Initialize metadata tracking
        queries_executed: List[QueryExecution] = []
        refinements_made: List[QueryRefinement] = []
        
        # Step 1: Generate search queries from PRP
        queries, query_refinements = await self._generate_queries_from_prp(prp_text)
        refinements_made.extend(query_refinements)
        logger.info(f"Generated {len(queries)} search queries")
        
        # Step 2: Execute searches and collect candidates
        candidates, query_executions = await self._search_for_candidates(queries)
        queries_executed.extend(query_executions)
        logger.info(f"Found {len(candidates)} unique candidate datasets")
        
        # Step 2.5: Check if we need fan-out (< 3 results)
        if len(candidates) < 3:
            logger.info(f"Only {len(candidates)} datasets found, executing fan-out strategy")
            fanout_queries = await self._generate_fanout_queries(prp_text, queries)
            
            # Track fan-out as refinements
            for fq in fanout_queries:
                refinements_made.append(QueryRefinement(
                    original_query=f"Primary queries ({len(queries)} total)",
                    refined_query=fq,
                    reason=f"Fan-out query: initial results < 3 (found {len(candidates)})"
                ))
            
            # Execute fan-out searches (reuse existing _search_for_candidates)
            fanout_candidates, fanout_executions = await self._search_for_candidates(fanout_queries)
            queries_executed.extend(fanout_executions)
            
            # Merge fan-out candidates with existing (avoiding duplicates)
            new_candidates = 0
            for fqn, dataset in fanout_candidates.items():
                if fqn not in candidates:
                    candidates[fqn] = dataset
                    new_candidates += 1
            
            logger.info(
                f"Fan-out complete: added {new_candidates} new datasets (total: {len(candidates)})"
            )
        
        if not candidates:
            total_time_ms = (time.time() - start_time) * 1000
            metadata = self._build_metadata(
                queries_executed=queries_executed,
                refinements_made=refinements_made,
                total_candidates=0,
                deduped_candidates=0,
                scored_candidates=0,
                total_time_ms=total_time_ms,
            )
            return {
                "total_count": 0,
                "datasets": [],
                "discovery_metadata": metadata,
            }
        
        # Step 3: Score relevance of each candidate
        scored_datasets = await self._score_dataset_relevance(
            prp_text=prp_text,
            candidates=candidates,
        )
        logger.info(f"Scored {len(scored_datasets)} datasets")
        
        # Step 4: Filter by minimum score and sort by relevance
        filtered_datasets = [
            ds for ds in scored_datasets 
            if ds.get("relevance_score", 0) >= self.min_relevance_score
        ]
        
        sorted_datasets = sorted(
            filtered_datasets,
            key=lambda x: x.get("relevance_score", 0),
            reverse=True,
        )[:max_results]
        
        total_time_ms = (time.time() - start_time) * 1000
        
        # Build metadata
        metadata = self._build_metadata(
            queries_executed=queries_executed,
            refinements_made=refinements_made,
            total_candidates=sum(qe.results_count for qe in queries_executed),
            deduped_candidates=len(candidates),
            scored_candidates=len(sorted_datasets),
            total_time_ms=total_time_ms,
        )
        
        logger.info(
            f"Returning {len(sorted_datasets)} datasets "
            f"(filtered from {len(scored_datasets)} with score >= {self.min_relevance_score})"
        )
        
        return {
            "total_count": len(sorted_datasets),
            "datasets": sorted_datasets,
            "discovery_metadata": metadata,
        }
    
    async def _generate_queries_from_prp(
        self,
        prp_text: str
    ) -> Tuple[List[str], List[QueryRefinement]]:
        """
        Generate targeted search queries from PRP using Gemini.
        
        Args:
            prp_text: PRP markdown text
            
        Returns:
            Tuple of (queries, refinements)
        """
        refinements: List[QueryRefinement] = []
        
        if not self.gemini.is_enabled:
            # Fallback: Extract keywords from PRP
            logger.warning("Gemini not available, using keyword extraction fallback")
            queries = self._extract_keywords_from_prp(prp_text)
            refinements.append(QueryRefinement(
                original_query="N/A",
                refined_query="keyword_extraction_fallback",
                reason="Gemini unavailable, used keyword extraction"
            ))
            return queries, refinements
        
        prompt = self._build_query_generation_prompt(prp_text)
        
        try:
            response = self.gemini._call_with_retry(prompt, "PRP query generation")
            
            if not response or not response.text:
                logger.warning("Empty response from Gemini for query generation")
                queries = self._extract_keywords_from_prp(prp_text)
                refinements.append(QueryRefinement(
                    original_query="gemini_empty_response",
                    refined_query="keyword_extraction_fallback",
                    reason="Empty response from Gemini API"
                ))
                return queries, refinements
            
            # Parse queries from response
            queries = self._parse_queries_from_response(response.text)
            
            if not queries:
                logger.warning("No queries parsed from Gemini response, using fallback")
                queries = self._extract_keywords_from_prp(prp_text)
                refinements.append(QueryRefinement(
                    original_query="gemini_parse_failed",
                    refined_query="keyword_extraction_fallback",
                    reason="Failed to parse queries from Gemini response"
                ))
                return queries, refinements
            
            return queries[:self.max_queries], refinements
            
        except Exception as e:
            logger.error(f"Error generating queries with Gemini: {e}")
            queries = self._extract_keywords_from_prp(prp_text)
            refinements.append(QueryRefinement(
                original_query="gemini_exception",
                refined_query="keyword_extraction_fallback",
                reason=f"Gemini API error: {str(e)}"
            ))
            return queries, refinements
    
    def _build_query_generation_prompt(self, prp_text: str) -> str:
        """Build prompt for Gemini to generate search queries from PRP."""
        return f"""You are a data discovery expert. Analyze the following Product Requirement Prompt (PRP) and generate specific, targeted search queries to find relevant datasets in a data catalog.

**Product Requirement Prompt:**
{prp_text}

**Instructions:**
1. Carefully read the PRP, paying special attention to:
   - Key Metrics (section 4): What data points are needed?
   - Dimensions & Breakdowns (section 5): How is data organized?
   - Data Requirements (section 9): What data sources/domains are mentioned?
   - Business Objective (section 2): What problem is being solved?

2. Generate {self.max_queries} specific search queries that would find datasets containing the required data.

3. Each query should be:
   - Specific and targeted (not generic)
   - Focused on finding actual data tables/datasets
   - Include domain terms, metrics, or entity names mentioned in the PRP
   - Between 3-8 words

4. Format your response as a simple numbered list with NO additional text:
1. query one here
2. query two here
3. query three here
...

Do NOT include explanations, headers, or any text other than the numbered queries.

Generate the search queries now:"""
    
    def _parse_queries_from_response(self, response_text: str) -> List[str]:
        """
        Parse search queries from Gemini response.
        
        Args:
            response_text: Raw response from Gemini
            
        Returns:
            List of query strings
        """
        queries = []
        
        # Pattern to match numbered lines: "1. Query text"
        numbered_pattern = r'^\d+\.\s*(.+?)$'
        
        for line in response_text.split('\n'):
            line = line.strip()
            
            if not line:
                continue
            
            # Try to match numbered pattern
            match = re.match(numbered_pattern, line)
            if match:
                query_text = match.group(1).strip()
                
                # Clean up markdown formatting
                query_text = re.sub(r'\*\*(.+?)\*\*', r'\1', query_text)
                query_text = re.sub(r'\*(.+?)\*', r'\1', query_text)
                query_text = query_text.strip('"\'')
                
                # Skip if too short or looks like header
                if len(query_text) < 5 or any(
                    skip in query_text.lower() 
                    for skip in ['search queries', 'query:', 'queries:']
                ):
                    continue
                
                queries.append(query_text)
        
        return queries
    
    def _extract_keywords_from_prp(self, prp_text: str) -> List[str]:
        """
        Fallback keyword extraction when Gemini is unavailable.
        
        Extracts domain names, metrics, and key terms from PRP sections.
        
        Args:
            prp_text: PRP markdown text
            
        Returns:
            List of keyword-based queries
        """
        queries = []
        
        # Extract from "Key Metrics" section
        metrics_match = re.search(
            r'##\s*4\.\s*Key Metrics(.*?)(?=##|\Z)',
            prp_text,
            re.DOTALL | re.IGNORECASE
        )
        if metrics_match:
            metrics_text = metrics_match.group(1)
            # Extract bullet points
            metric_items = re.findall(r'-\s*\*\*(.+?)\*\*', metrics_text)
            queries.extend([m.lower() for m in metric_items[:3]])
        
        # Extract from "Dimensions & Breakdowns" section
        dimensions_match = re.search(
            r'##\s*5\.\s*Dimensions.*?Breakdowns(.*?)(?=##|\Z)',
            prp_text,
            re.DOTALL | re.IGNORECASE
        )
        if dimensions_match:
            dimensions_text = dimensions_match.group(1)
            dimension_items = re.findall(r'-\s*\*\*(.+?)\*\*', dimensions_text)
            queries.extend([d.lower() for d in dimension_items[:3]])
        
        # Extract domain names from "Data Requirements" section
        data_req_match = re.search(
            r'##\s*9\.\s*Data Requirements(.*?)(?=##|\Z)',
            prp_text,
            re.DOTALL | re.IGNORECASE
        )
        if data_req_match:
            data_req_text = data_req_match.group(1)
            # Look for domain mentions like "Lfndata domain", "Abndata domain"
            domains = re.findall(r'([A-Z][a-z]+data)\s+domain', data_req_text)
            queries.extend([d.lower() for d in domains])
        
        # If still no queries, extract some keywords
        if not queries:
            # Extract capitalized terms (likely important entities)
            keywords = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', prp_text)
            queries = list(set(keywords[:5]))
        
        return queries[:self.max_queries] if queries else ["player statistics game data"]
    
    async def _generate_fanout_queries(
        self,
        prp_text: str,
        primary_queries: List[str],
    ) -> List[str]:
        """
        Generate broader/related queries for fan-out when primary queries return < 3 results.
        
        Reuses SearchFanoutGenerator from data-planning-agent pattern.
        
        Args:
            prp_text: Original PRP text
            primary_queries: The primary queries that were already executed
            
        Returns:
            List of broader fanout query strings
        """
        if not self.gemini.is_enabled:
            logger.warning("Gemini not available, using keyword fallback for fan-out")
            return self._generate_fallback_fanout_queries(prp_text, primary_queries)
        
        # Import SearchFanoutGenerator (reused from data-planning-agent)
        from .search_fanout import SearchFanoutGenerator
        
        # Create a summary of what we're looking for (from PRP)
        prp_summary = self._extract_prp_summary(prp_text)
        
        # Use SearchFanoutGenerator with PRP context
        fanout_gen = SearchFanoutGenerator(self.gemini)
        
        # Generate related queries based on PRP summary
        fanout_queries = fanout_gen.generate_related_queries(
            original_query=prp_summary,
            num_queries=self.max_queries
        )
        
        logger.info(f"Generated {len(fanout_queries)} fan-out queries")
        return fanout_queries
    
    def _extract_prp_summary(self, prp_text: str) -> str:
        """
        Extract a concise summary from PRP for fan-out query generation.
        
        Takes key sections from PRP and creates a natural language summary.
        
        Args:
            prp_text: Full PRP markdown text
            
        Returns:
            Concise summary suitable for query generation
        """
        summary_parts = []
        
        # Extract objective (section 2)
        obj_match = re.search(
            r'##\s*2\.\s*Business Objective(.*?)(?=##|\Z)',
            prp_text,
            re.DOTALL | re.IGNORECASE
        )
        if obj_match:
            objective = obj_match.group(1).strip()[:200]
            summary_parts.append(objective)
        
        # Extract key metrics (section 4, first 3)
        metrics_match = re.search(
            r'##\s*4\.\s*Key Metrics(.*?)(?=##|\Z)',
            prp_text,
            re.DOTALL | re.IGNORECASE
        )
        if metrics_match:
            metric_items = re.findall(r'-\s*\*\*(.+?)\*\*', metrics_match.group(1))[:3]
            if metric_items:
                summary_parts.append("Metrics: " + ", ".join(metric_items))
        
        summary = ". ".join(summary_parts) if summary_parts else prp_text[:300]
        return summary
    
    def _generate_fallback_fanout_queries(
        self,
        prp_text: str,
        primary_queries: List[str],
    ) -> List[str]:
        """
        Fallback method to generate broader queries when Gemini unavailable.
        
        Uses simple keyword extraction with broader, less specific terms.
        
        Args:
            prp_text: Original PRP text
            primary_queries: Primary queries already tried
            
        Returns:
            List of broader query strings
        """
        fanout_queries = []
        
        # Extract domain names (Lfndata, Abndata, etc.)
        domains = re.findall(r'([A-Z][a-z]+data)\s+domain', prp_text, re.IGNORECASE)
        fanout_queries.extend([d.lower() for d in set(domains)])
        
        # Extract entity types (player, game, team, etc.)
        entities = re.findall(
            r'\b(player|game|team|customer|user|product|order)\w*\b',
            prp_text,
            re.IGNORECASE
        )
        fanout_queries.extend([e.lower() + " data" for e in list(set(entities))[:2]])
        
        # Add generic broader terms based on PRP content
        if "statistic" in prp_text.lower() or "metric" in prp_text.lower():
            fanout_queries.append("statistics")
        if "analytics" in prp_text.lower():
            fanout_queries.append("analytics data")
        
        return list(set(fanout_queries))[:self.max_queries]
    
    async def _search_for_candidates(
        self,
        queries: List[str],
    ) -> Tuple[Dict[str, DiscoveredAssetDict], List[QueryExecution]]:
        """
        Execute searches and collect unique candidate datasets.
        
        Args:
            queries: List of search query strings
            
        Returns:
            Tuple of (candidates dict, query execution records)
        """
        candidates: Dict[str, DiscoveredAssetDict] = {}
        query_executions: List[QueryExecution] = []
        
        import asyncio
        loop = asyncio.get_running_loop()
        
        for query in queries:
            query_start_time = time.time()
            try:
                # Build search request
                search_request = SearchRequest(
                    query=query,
                    page_size=10,  # Get top 10 per query
                    sort_order=SortOrder.DESC,
                    include_full_content=True,
                )
                
                # Execute search in thread pool
                search_response: SearchResponse = await loop.run_in_executor(
                    None,
                    lambda: self.vertex_client.search(search_request),
                )
                
                execution_time_ms = (time.time() - query_start_time) * 1000
                
                # Collect top tables from results
                top_tables = []
                for result in search_response.results[:5]:  # Top 5
                    table_fqn = f"{result.metadata.project_id}.{result.metadata.dataset_id}.{result.metadata.table_id}"
                    top_tables.append(table_fqn)
                    
                    # Skip if already collected
                    if table_fqn in candidates:
                        continue
                    
                    # Convert to DiscoveredAssetDict
                    asset_dict = self._convert_result_to_asset_dict(result)
                    candidates[table_fqn] = asset_dict
                
                # Record successful execution
                query_executions.append(QueryExecution(
                    query=query,
                    results_count=len(search_response.results),
                    execution_time_ms=execution_time_ms,
                    top_tables=top_tables,
                    status="success" if search_response.results else "no_results",
                    error_message=None
                ))
                
                logger.debug(f"Query '{query}' returned {len(search_response.results)} results in {execution_time_ms:.0f}ms")
                
            except Exception as e:
                execution_time_ms = (time.time() - query_start_time) * 1000
                error_msg = str(e)
                logger.warning(f"Error executing search for query '{query}': {error_msg}")
                
                # Record failed execution
                query_executions.append(QueryExecution(
                    query=query,
                    results_count=0,
                    execution_time_ms=execution_time_ms,
                    top_tables=[],
                    status="failed",
                    error_message=error_msg
                ))
        
        return candidates, query_executions
    
    def _convert_result_to_asset_dict(self, result: Any) -> DiscoveredAssetDict:
        """
        Convert search result to DiscoveredAssetDict format.
        
        Args:
            result: SearchResultItem from Vertex Search
            
        Returns:
            DiscoveredAssetDict
        """
        from datetime import datetime, timezone
        
        metadata = result.metadata
        
        # Build basic asset dictionary
        asset: DiscoveredAssetDict = {
            "table_id": metadata.table_id or "",
            "project_id": metadata.project_id or "",
            "dataset_id": metadata.dataset_id or "",
            "description": result.snippet or "",
            "table_type": metadata.asset_type or "TABLE",
            "asset_type": metadata.asset_type or "TABLE",
            "created": metadata.created_at if metadata.created_at else None,
            "last_modified": metadata.last_modified if metadata.last_modified else None,
            "last_accessed": metadata.last_accessed if metadata.last_accessed else None,
            "row_count": metadata.row_count,
            "column_count": metadata.column_count,
            "size_bytes": metadata.size_bytes,
            "has_pii": metadata.has_pii or False,
            "has_phi": metadata.has_phi or False,
            "environment": metadata.environment,
            "labels": [],
            "schema": [],
            "analytical_insights": [],
            "lineage": [],
            "column_profiles": [],
            "key_metrics": [],
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "insert_timestamp": "AUTO",
            "full_markdown": result.full_content or "",
            "owner_email": metadata.owner_email,
            "tags": metadata.tags if metadata.tags else [],
        }
        
        return asset
    
    async def _score_dataset_relevance(
        self,
        prp_text: str,
        candidates: Dict[str, DiscoveredAssetDict],
    ) -> List[DiscoveredAssetDict]:
        """
        Score each candidate dataset's relevance to PRP using Gemini.
        
        Args:
            prp_text: Original PRP text
            candidates: Dictionary of candidate datasets
            
        Returns:
            List of datasets with relevance_score added
        """
        if not self.gemini.is_enabled:
            # Fallback: Return all candidates with neutral score
            logger.warning("Gemini not available, assigning neutral scores")
            return [
                {**dataset, "relevance_score": 70.0}
                for dataset in candidates.values()
            ]
        
        scored_datasets = []
        
        for table_fqn, dataset in candidates.items():
            try:
                score = await self._score_single_dataset(prp_text, dataset)
                dataset_with_score = {**dataset, "relevance_score": score}
                scored_datasets.append(dataset_with_score)
                
                logger.debug(f"Scored {table_fqn}: {score}")
                
            except Exception as e:
                logger.warning(f"Error scoring dataset {table_fqn}: {e}")
                # Assign neutral score on error
                dataset_with_score = {**dataset, "relevance_score": 50.0}
                scored_datasets.append(dataset_with_score)
        
        return scored_datasets
    
    async def _score_single_dataset(
        self,
        prp_text: str,
        dataset: DiscoveredAssetDict,
    ) -> float:
        """
        Score a single dataset's relevance to PRP using Gemini.
        
        Args:
            prp_text: Original PRP text
            dataset: Dataset to score
            
        Returns:
            Relevance score (0-100)
        """
        prompt = self._build_scoring_prompt(prp_text, dataset)
        
        try:
            response = self.gemini._call_with_retry(
                prompt,
                f"scoring {dataset['table_id']}"
            )
            
            if not response or not response.text:
                return 50.0  # Neutral score
            
            # Parse score from response
            score = self._parse_score_from_response(response.text)
            return max(0.0, min(100.0, score))  # Clamp to 0-100
            
        except Exception as e:
            logger.warning(f"Error scoring dataset: {e}")
            return 50.0
    
    def _build_scoring_prompt(
        self,
        prp_text: str,
        dataset: DiscoveredAssetDict,
    ) -> str:
        """Build prompt for Gemini to score dataset relevance."""
        
        # Truncate PRP if too long (keep key sections)
        prp_summary = prp_text[:2000] + "..." if len(prp_text) > 2000 else prp_text
        
        # Build dataset summary
        dataset_summary = f"""
**Dataset**: {dataset['project_id']}.{dataset['dataset_id']}.{dataset['table_id']}

**Description**: {dataset.get('description', 'No description')}

**Statistics**:
- Rows: {dataset.get('row_count', 'Unknown')}
- Columns: {dataset.get('column_count', 'Unknown')}
- Type: {dataset.get('table_type', 'TABLE')}

**Full Documentation**:
{dataset.get('full_markdown', 'No documentation available')[:1000]}
"""
        
        return f"""You are a data analyst evaluating whether a dataset can fulfill the requirements of a data product.

**Product Requirement Prompt (PRP):**
{prp_summary}

**Dataset to Evaluate:**
{dataset_summary}

**Your Task:**
Score this dataset's relevance to the PRP requirements on a scale of 0-100, where:
- 0-20: Completely irrelevant
- 21-40: Somewhat related but missing key requirements
- 41-60: Moderately relevant, has some required data
- 61-80: Highly relevant, meets most requirements
- 81-100: Excellent match, fulfills all or nearly all requirements

Consider:
1. Does the dataset contain the key metrics mentioned in the PRP?
2. Does it have the dimensions/breakdowns needed?
3. Does the data domain match what's described in the PRP?
4. Does the granularity match (e.g., game-level, player-level)?

**Response Format:**
Provide ONLY a number between 0 and 100 as the first line, followed by a brief justification.

Example:
85
This dataset contains player-level game statistics with all required metrics (points, yards, touchdowns) and dimensions (season, week, opponent).

Your score:"""
    
    def _parse_score_from_response(self, response_text: str) -> float:
        """
        Parse relevance score from Gemini response.
        
        Args:
            response_text: Raw response text
            
        Returns:
            Parsed score (0-100), defaults to 50 if parsing fails
        """
        # Look for a number on the first line or anywhere in text
        lines = response_text.strip().split('\n')
        
        for line in lines[:3]:  # Check first 3 lines
            # Try to find a number
            numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', line)
            if numbers:
                try:
                    score = float(numbers[0])
                    if 0 <= score <= 100:
                        return score
                except ValueError:
                    continue
        
        # Fallback: return neutral score
        logger.warning(f"Could not parse score from response: {response_text[:100]}")
        return 50.0
    
    def _build_metadata(
        self,
        queries_executed: List[QueryExecution],
        refinements_made: List[QueryRefinement],
        total_candidates: int,
        deduped_candidates: int,
        scored_candidates: int,
        total_time_ms: float,
    ) -> Dict[str, Any]:
        """
        Build discovery metadata summary.
        
        Args:
            queries_executed: List of query execution records
            refinements_made: List of query refinement records
            total_candidates: Total candidates found across all queries
            deduped_candidates: Candidates after deduplication
            scored_candidates: Candidates after scoring/filtering
            total_time_ms: Total execution time in milliseconds
            
        Returns:
            Dictionary with complete metadata
        """
        # Count successful vs failed queries
        successful_queries = sum(
            1 for qe in queries_executed 
            if qe.status == "success"
        )
        failed_queries = sum(
            1 for qe in queries_executed 
            if qe.status == "failed"
        )
        
        return {
            "queries_executed": [asdict(qe) for qe in queries_executed],
            "refinements_made": [asdict(ref) for ref in refinements_made],
            "summary": {
                "total_queries_generated": len(queries_executed),
                "successful_queries": successful_queries,
                "failed_queries": failed_queries,
                "total_candidates_found": total_candidates,
                "candidates_after_deduplication": deduped_candidates,
                "candidates_after_scoring": scored_candidates,
                "total_execution_time_ms": round(total_time_ms, 2),
                # Fan-out tracking
                "fanout_triggered": any(
                    r.reason and "fan-out" in r.reason.lower()
                    for r in refinements_made
                ) if refinements_made else False,
                "fanout_queries_count": sum(
                    1 for r in refinements_made
                    if r.reason and "fan-out" in r.reason.lower()
                ) if refinements_made else 0,
            }
        }

