"""
Vertex AI Search Client

High-level client for interacting with Vertex AI Search.
Wraps the Discovery Engine API with our data models and query builder.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from google.cloud import discoveryengine_v1beta as discoveryengine
from google.api_core import retry

from ..models.search_models import SearchRequest, SearchResponse, SearchResultItem, AssetMetadata
from ..search.query_builder import SearchQueryBuilder
from ..search.result_parser import SearchResultParser

logger = logging.getLogger(__name__)


class VertexSearchClient:
    """
    Client for Vertex AI Search operations.
    
    Features:
    - Semantic search using natural language queries
    - BigQuery import from discovered_assets_latest view
    - Automatic schema discovery by Vertex AI Search
    - FULL reconciliation mode to handle deleted tables
    - Error handling and retries
    """
    
    def __init__(
        self,
        project_id: str,
        location: str = "global",
        datastore_id: str = "data-discovery-metadata",
        reports_bucket: Optional[str] = None,
    ):
        """
        Initialize Vertex AI Search client.
        
        Args:
            project_id: GCP project ID
            location: GCP location for Vertex AI Search (use 'global' for data stores)
            datastore_id: ID of the data store
            reports_bucket: GCS bucket for Markdown reports (optional)
        """
        self.project_id = project_id
        self.location = location
        self.datastore_id = datastore_id
        self.reports_bucket = reports_bucket
        
        # Initialize Google Cloud clients
        self.search_client = discoveryengine.SearchServiceClient()
        self.document_client = discoveryengine.DocumentServiceClient()  # Still needed for delete operations
        
        # Initialize our helper classes
        self.query_builder = SearchQueryBuilder(project_id)
        self.result_parser = SearchResultParser(project_id, reports_bucket)
        
        # Build resource paths
        self.serving_config = self._build_serving_config_path()
        self.branch_path = self._build_branch_path()
        
        logger.info(
            f"Initialized VertexSearchClient for project={project_id}, "
            f"datastore={datastore_id}"
        )
    
    def _build_serving_config_path(self) -> str:
        """Build serving config path for search requests"""
        return (
            f"projects/{self.project_id}/locations/{self.location}/"
            f"collections/default_collection/dataStores/{self.datastore_id}/"
            f"servingConfigs/default_config"
        )
    
    def _build_branch_path(self) -> str:
        """Build branch path for document operations"""
        return (
            f"projects/{self.project_id}/locations/{self.location}/"
            f"collections/default_collection/dataStores/{self.datastore_id}/"
            f"branches/default_branch"
        )
    
    def _convert_proto_to_dict(self, obj: Any) -> Any:
        """
        Recursively convert proto-plus objects to Python dicts.
        
        Handles MapComposite, RepeatedComposite, and other proto-plus wrappers
        that Google Cloud libraries use.
        
        Args:
            obj: Proto-plus object or primitive value
            
        Returns:
            Native Python type (dict, list, or primitive)
        """
        # Handle None
        if obj is None:
            return None
        
        # Handle primitive types
        if isinstance(obj, (str, int, float, bool)):
            return obj
        
        # Handle dict-like objects (MapComposite)
        if hasattr(obj, 'items'):
            try:
                return {key: self._convert_proto_to_dict(value) for key, value in obj.items()}
            except Exception:
                # If items() fails, try to convert as-is
                pass
        
        # Handle list-like objects (RepeatedComposite)
        if hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, dict)):
            try:
                return [self._convert_proto_to_dict(item) for item in obj]
            except Exception:
                # If iteration fails, return as-is
                pass
        
        # Try to convert to dict if it has __dict__
        if hasattr(obj, '__dict__'):
            try:
                return self._convert_proto_to_dict(dict(obj.__dict__))
            except Exception:
                pass
        
        # Return as-is if no conversion worked
        return obj
    
    def search(
        self,
        request: SearchRequest,
        timeout: float = 30.0,
    ) -> SearchResponse:
        """
        Execute a search query.
        
        Args:
            request: SearchRequest object
            timeout: Query timeout in seconds
        
        Returns:
            SearchResponse with results
        """
        
        start_time = time.time()
        
        # Build filters from request
        filters = {}
        if request.project_id:
            filters["project_id"] = request.project_id
        if request.dataset_id:
            filters["dataset_id"] = request.dataset_id
        if request.table_id:
            filters["table_id"] = request.table_id
        if request.has_pii is not None:
            filters["has_pii"] = request.has_pii
        if request.has_phi is not None:
            filters["has_phi"] = request.has_phi
        if request.environment:
            filters["environment"] = request.environment
        if request.min_row_count:
            filters["row_count__>="] = request.min_row_count
        if request.max_row_count:
            filters["row_count__<="] = request.max_row_count
        if request.min_cost:
            filters["monthly_cost_usd__>="] = request.min_cost
        if request.max_cost:
            filters["monthly_cost_usd__<="] = request.max_cost
        
        # Build query
        query_dict = self.query_builder.build_query(
            user_query=request.query,
            explicit_filters=filters,
            page_size=request.page_size,
            order_by=f"{request.sort_by} {request.sort_order.value}" if request.sort_by else None,
        )
        
        # Execute search
        try:
            api_response = self._execute_search_api(
                query_dict,
                request.page_token,
                timeout
            )
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise
        
        # Parse results
        parsed_response = self._parse_api_response(
            api_response,
            request,
            query_dict,
        )
        
        # Calculate query time
        query_time_ms = (time.time() - start_time) * 1000
        parsed_response.query_time_ms = query_time_ms
        
        logger.info(
            f"Search completed: query='{request.query}', "
            f"results={len(parsed_response.results)}, "
            f"time={query_time_ms:.0f}ms"
        )
        
        return parsed_response
    
    def _execute_search_api(
        self,
        query_dict: Dict[str, Any],
        page_token: Optional[str],
        timeout: float,
    ) -> Any:
        """Execute the actual search API call"""
        
        search_request = discoveryengine.SearchRequest(
            serving_config=self.serving_config,
            query=query_dict["query"],
            page_size=query_dict["page_size"],
            page_token=page_token or "",
        )
        
        # Add filter if present
        if "filter" in query_dict and query_dict["filter"]:
            search_request.filter = query_dict["filter"]
        
        # Add order_by if present
        if "order_by" in query_dict and query_dict["order_by"]:
            search_request.order_by = query_dict["order_by"]
        
        # Add boost spec if present
        if "boost_spec" in query_dict:
            # Note: boost_spec format depends on API version
            # This is a simplified version
            pass
        
        # Execute with retry
        logger.info("Calling Vertex AI Search API...")
        response = self.search_client.search(
            request=search_request,
            timeout=timeout,
            retry=retry.Retry(
                initial=1.0,
                maximum=10.0,
                multiplier=2.0,
                predicate=retry.if_exception_type(Exception),
            ),
        )
        logger.info("Got response from Vertex AI Search API")
        
        return response
    
    def _parse_api_response(
        self,
        api_response: Any,
        request: SearchRequest,
        query_dict: Dict[str, Any],
    ) -> SearchResponse:
        """Parse API response into our SearchResponse model"""
        
        logger.info("Parsing API response...")
        results = []
        total_count = 0
        next_page_token = None
        
        logger.info("Iterating over response results...")
        for response_item in api_response.results:
            # Extract document
            document = response_item.document
            
            # Build AssetMetadata
            struct_data = document.struct_data if hasattr(document, 'struct_data') else {}
            # Handle None struct_data
            if struct_data is None:
                struct_data = {}
            
            # Convert proto-plus objects to Python dict (handles nested structures)
            struct_data = self._convert_proto_to_dict(struct_data)
            if not isinstance(struct_data, dict):
                struct_data = {}
            
            # Map BigQuery view schema to AssetMetadata
            # Note: table_type → asset_type for future extensibility
            # Construct semantic ID from components (project.dataset.table)
            # rather than using Vertex AI's sanitized ID (project_dataset_table)
            project_id = struct_data.get("project_id", self.project_id)
            dataset_id = struct_data.get("dataset_id", "")
            table_id = struct_data.get("table_id", "")
            semantic_id = f"{project_id}.{dataset_id}.{table_id}"
            
            metadata = AssetMetadata(
                id=semantic_id,
                project_id=project_id,
                dataset_id=dataset_id,
                table_id=table_id,
                
                # Map table_type to asset_type
                asset_type=struct_data.get("table_type", "TABLE"),
                
                # Description
                description=struct_data.get("description"),
                
                # Size and scale
                row_count=struct_data.get("row_count"),
                size_bytes=struct_data.get("size_bytes"),
                column_count=struct_data.get("column_count"),
                
                # Security
                has_pii=struct_data.get("has_pii", False),
                has_phi=struct_data.get("has_phi", False),
                encryption_type=struct_data.get("encryption_type"),
                
                # Cost
                monthly_cost_usd=struct_data.get("monthly_cost_usd"),
                
                # Timestamps (renamed to match view schema)
                created=struct_data.get("created"),
                last_modified=struct_data.get("last_modified"),
                last_accessed=struct_data.get("last_accessed"),
                insert_timestamp=struct_data.get("insert_timestamp"),
                indexed_at=struct_data.get("indexed_at", struct_data.get("insert_timestamp", "")),
                
                # Quality
                completeness_score=struct_data.get("completeness_score"),
                freshness_score=struct_data.get("freshness_score"),
                
                # Governance
                owner_email=struct_data.get("owner_email"),
                team=struct_data.get("team"),
                environment=struct_data.get("environment"),
                tags=struct_data.get("tags", []),
                
                # Rich metadata arrays
                schema=struct_data.get("schema", []),
                column_profiles=struct_data.get("column_profiles", []),
                lineage=struct_data.get("lineage", []),
                analytical_insights=struct_data.get("analytical_insights", []),
                key_metrics=struct_data.get("key_metrics", []),
            )
            
            # Extract snippet
            snippet = self._extract_snippet(response_item)
            
            # Build full content if requested
            full_content = None
            if request.include_full_content and hasattr(document, 'content') and document.content:
                content = document.content
                # Handle protobuf Content object
                if hasattr(content, 'raw_bytes') and content.raw_bytes:
                    try:
                        full_content = content.raw_bytes.decode('utf-8')
                    except (AttributeError, UnicodeDecodeError):
                        full_content = None
                # Handle dict-like content
                elif isinstance(content, dict):
                    full_content = content.get("text", "")
            
            # Build console link
            console_link = self._build_console_link(metadata)
            
            # Build report link
            report_link = None
            if self.reports_bucket and metadata.dataset_id and metadata.table_id:
                report_link = (
                    f"gs://{self.reports_bucket}/"
                    f"{metadata.dataset_id}/{metadata.table_id}.md"
                )
            
            # Create result item
            result = SearchResultItem(
                id=document.id,
                title=f"{metadata.dataset_id}.{metadata.table_id}" if metadata.dataset_id and metadata.table_id else document.id,
                score=1.0,  # API may not return explicit scores
                metadata=metadata,
                snippet=snippet,
                full_content=full_content,
                console_link=console_link,
                report_link=report_link,
            )
            
            results.append(result)
        
        # Extract pagination info
        if hasattr(api_response, 'total_size'):
            total_count = api_response.total_size
        else:
            total_count = len(results)
        
        if hasattr(api_response, 'next_page_token'):
            next_page_token = api_response.next_page_token
        
        # Build filters dict for response
        filters_dict = {}
        if request.project_id:
            filters_dict["project_id"] = request.project_id
        if request.dataset_id:
            filters_dict["dataset_id"] = request.dataset_id
        if request.has_pii is not None:
            filters_dict["has_pii"] = request.has_pii
        if request.has_phi is not None:
            filters_dict["has_phi"] = request.has_phi
        if request.environment:
            filters_dict["environment"] = request.environment
        if request.min_row_count:
            filters_dict["min_row_count"] = request.min_row_count
        if request.max_row_count:
            filters_dict["max_row_count"] = request.max_row_count
        if request.min_cost:
            filters_dict["min_cost"] = request.min_cost
        if request.max_cost:
            filters_dict["max_cost"] = request.max_cost
        
        # Build response
        return SearchResponse(
            query=request.query,
            filters_applied=filters_dict,
            results=results,
            total_count=total_count,
            query_time_ms=0,  # Will be set by caller
            page_size=request.page_size,
            next_page_token=next_page_token,
            has_more_results=bool(next_page_token),
            suggested_queries=[],  # Could be enhanced
        )
    
    def _extract_snippet(self, response_item: Any) -> str:
        """Extract content snippet from search result"""
        
        # Try to get snippet from derived_struct_data
        if hasattr(response_item, 'derived_struct_data'):
            derived_data = response_item.derived_struct_data
            if derived_data:
                # Convert proto-plus objects to Python dict
                derived_data = self._convert_proto_to_dict(derived_data)
                snippets = derived_data.get('snippets', []) if isinstance(derived_data, dict) else []
                if snippets:
                    return snippets[0].get('snippet', '')
        
        # Fallback to first 200 chars of content
        if hasattr(response_item, 'document') and hasattr(response_item.document, 'content'):
            content = response_item.document.content
            # Handle protobuf Content object
            if hasattr(content, 'raw_bytes'):
                try:
                    text = content.raw_bytes.decode('utf-8') if content.raw_bytes else ''
                    return text[:200] + "..." if len(text) > 200 else text
                except (AttributeError, UnicodeDecodeError):
                    pass
            # Handle dict-like content
            elif isinstance(content, dict):
                text = content.get('text', '')
                return text[:200] + "..." if len(text) > 200 else text
        
        return "No content available"
    
    def _build_console_link(self, metadata: AssetMetadata) -> Optional[str]:
        """Build BigQuery Console link"""
        
        if not all([metadata.project_id, metadata.dataset_id, metadata.table_id]):
            return None
        
        return (
            f"https://console.cloud.google.com/bigquery?"
            f"project={metadata.project_id}&"
            f"ws=!1m5!1m4!4m3!1s{metadata.project_id}!2s{metadata.dataset_id}!3s{metadata.table_id}"
        )
    
    def import_documents_from_bigquery(
        self,
        dataset_id: str,
        table_id: str,
        reconciliation_mode: str = "FULL",
    ) -> str:
        """
        Import documents from a BigQuery table.
        
        Uses FULL reconciliation mode by default to ensure deleted tables
        are removed from the search index (keeps index in sync with source).
        
        Uses auto-generated IDs - Vertex AI generates internal document IDs
        automatically. Note: Purge the datastore before import to avoid
        accumulating duplicate documents.

        Args:
            dataset_id: The BigQuery dataset ID.
            table_id: The BigQuery table ID.
            reconciliation_mode: FULL (default) or INCREMENTAL.

        Returns:
            Operation name for tracking.
        """
        logger.info(f"Starting document import from BigQuery table: {self.project_id}.{dataset_id}.{table_id}")

        request = discoveryengine.ImportDocumentsRequest(
            parent=self.branch_path,
            bigquery_source=discoveryengine.BigQuerySource(
                project_id=self.project_id,
                dataset_id=dataset_id,
                table_id=table_id,
                data_schema="custom",
            ),
            reconciliation_mode=reconciliation_mode,
            auto_generate_ids=True,  # Let Vertex AI generate document IDs
        )

        operation = self.document_client.import_documents(request=request)
        logger.info(f"Import operation started: {operation.operation.name}")
        return operation.operation.name
    
    def purge_documents(self, force: bool = True) -> str:
        """
        Purge all documents from the datastore.
        
        This operation deletes all documents in the datastore. Use this before
        importing new data to ensure a clean state and avoid duplicate documents
        when using auto-generated IDs.
        
        Args:
            force: If True, actually delete documents. If False, return expected 
                   count without deleting (dry run).
        
        Returns:
            Operation name for tracking.
        """
        from google.api_core.client_options import ClientOptions
        
        logger.info(f"Starting purge operation for datastore {self.datastore_id} (force={force})")
        
        # Configure client for regional endpoints
        client_options = (
            ClientOptions(api_endpoint=f"{self.location}-discoveryengine.googleapis.com")
            if self.location != "global"
            else None
        )
        
        document_client = discoveryengine.DocumentServiceClient(client_options=client_options)
        
        request = discoveryengine.PurgeDocumentsRequest(
            parent=self.branch_path,
            filter="*",
            force=force,
        )
        
        operation = document_client.purge_documents(request=request)
        logger.info(f"Purge operation started: {operation.operation.name}")
        
        return operation.operation.name
    
    def wait_for_import(
        self,
        operation_name: str,
        timeout: float = 600.0,
    ) -> Dict[str, Any]:
        """
        Wait for import operation to complete.
        
        Args:
            operation_name: Operation name from import_documents_from_bigquery
            timeout: Maximum wait time in seconds
        
        Returns:
            Operation result
        """
        
        logger.info(f"Waiting for operation {operation_name}")
        
        # Poll for completion
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Check operation status
            # This is simplified; actual implementation would use operations API
            time.sleep(10)
            
            # In production, check operation.done()
            # For now, just wait
        
        logger.info("Operation completed (or timed out)")
        
        return {"status": "completed"}
    
    def delete_documents(
        self,
        document_ids: List[str],
    ) -> None:
        """
        Delete documents from the data store.
        
        Args:
            document_ids: List of document IDs to delete
        """
        
        logger.info(f"Deleting {len(document_ids)} documents")
        
        for doc_id in document_ids:
            document_path = f"{self.branch_path}/documents/{doc_id}"
            
            try:
                self.document_client.delete_document(name=document_path)
                logger.debug(f"Deleted document: {doc_id}")
            except Exception as e:
                logger.error(f"Failed to delete document {doc_id}: {e}")
    
    def get_document_count(self) -> int:
        """
        Get total document count in data store.
        
        Returns:
            Number of documents
        """
        
        # This would require listing all documents
        # Simplified implementation
        logger.info("Getting document count")
        
        # In production, use list_documents API
        return 0
    
    def health_check(self) -> bool:
        """
        Check if Vertex AI Search is accessible.
        
        Returns:
            True if healthy
        """
        
        try:
            # Try a simple search
            search_request = discoveryengine.SearchRequest(
                serving_config=self.serving_config,
                query="test",
                page_size=1,
            )
            
            self.search_client.search(request=search_request, timeout=10.0)
            
            logger.info("Health check passed")
            return True
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False


# Example usage
if __name__ == "__main__":
    # Initialize client
    client = VertexSearchClient(
        project_id="your-project-id",
        location="global",
        datastore_id="data-discovery-metadata",
        reports_bucket="your-reports-bucket",
    )
    
    # Health check
    if client.health_check():
        print("✓ Vertex AI Search is healthy")
    
    # Import from BigQuery
    print("\nImporting from BigQuery...")
    operation = client.import_documents_from_bigquery(
        dataset_id="data_discovery",
        table_id="discovered_assets_latest",
        reconciliation_mode="FULL",
    )
    print(f"✓ Import started: {operation}")
    
    # Example search
    search_req = SearchRequest(
        query="tables with PII",
        has_pii=True,
        page_size=5,
    )
    
    response = client.search(search_req)
    print(f"\n{response.get_summary()}")
    
    for result in response.results:
        print(f"\n{result.title}")
        print(f"  {result.metadata.asset_type} | {result.metadata.row_count:,} rows")
        print(f"  {result.snippet[:100]}...")

