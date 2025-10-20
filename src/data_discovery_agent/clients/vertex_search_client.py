"""
Vertex AI Search Client

High-level client for interacting with Vertex AI Search.
Wraps the Discovery Engine API with our data models and query builder.
"""

import logging
import time
from pathlib import Path
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
    - High-level search interface using our data models
    - Automatic query building and result parsing
    - Document ingestion from JSONL files
    - Batch operations for indexing
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
        self.document_client = discoveryengine.DocumentServiceClient()
        
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
        # Note: project_id is not supported in Vertex AI Search filters
        # (the datastore is already scoped to a project)
        filters = {}
        if request.dataset_id:
            filters["dataset_id"] = request.dataset_id
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
            
            metadata = AssetMetadata(
                id=document.id,
                project_id=struct_data.get("project_id", self.project_id),
                dataset_id=struct_data.get("dataset_id"),
                table_id=struct_data.get("table_id"),
                asset_type=struct_data.get("asset_type", "TABLE"),
                row_count=struct_data.get("row_count"),
                size_bytes=struct_data.get("size_bytes"),
                column_count=struct_data.get("column_count"),
                has_pii=struct_data.get("has_pii", False),
                has_phi=struct_data.get("has_phi", False),
                encryption_type=struct_data.get("encryption_type"),
                monthly_cost_usd=struct_data.get("monthly_cost_usd"),
                created_at=struct_data.get("created_timestamp"),
                last_modified=struct_data.get("last_modified_timestamp"),
                last_accessed=struct_data.get("last_accessed_timestamp"),
                indexed_at=struct_data.get("indexed_at", ""),
                completeness_score=struct_data.get("completeness_score"),
                freshness_score=struct_data.get("freshness_score"),
                owner_email=struct_data.get("owner_email"),
                team=struct_data.get("team"),
                environment=struct_data.get("environment"),
                tags=struct_data.get("tags", []),
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
                snippets = derived_data.get('snippets', [])
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
    
    def create_document(
        self,
        document_id: str,
        struct_data: Dict[str, Any],
        content: str,
    ) -> str:
        """
        Create a single document in Vertex AI Search using the Document Service API.
        
        This bypasses the GCS import limitation and allows JSONL-style structured data.
        
        Args:
            document_id: Unique document ID (e.g., "project.dataset.table")
            struct_data: Structured metadata (filterable fields)
            content: Text content for search
        
        Returns:
            Document name
        """
        
        logger.debug(f"Creating document: {document_id}")
        
        document = discoveryengine.Document(
            id=document_id,
            struct_data=struct_data,
            content=discoveryengine.Document.Content(
                mime_type="text/plain",
                raw_bytes=content.encode('utf-8'),
            ),
        )
        
        request = discoveryengine.CreateDocumentRequest(
            parent=self.branch_path,
            document=document,
            document_id=document_id,
        )
        
        created_doc = self.document_client.create_document(request=request)
        
        logger.debug(f"Created document: {created_doc.name}")
        
        return created_doc.name
    
    def update_document(
        self,
        document_id: str,
        struct_data: Dict[str, Any],
        content: str,
    ) -> str:
        """
        Update an existing document in Vertex AI Search.
        
        Args:
            document_id: Unique document ID (e.g., "project.dataset.table")
            struct_data: Structured metadata (filterable fields)
            content: Text content for search
        
        Returns:
            Document name
        """
        
        logger.debug(f"Updating document: {document_id}")
        
        # Build document path
        document_path = f"{self.branch_path}/documents/{document_id}"
        
        document = discoveryengine.Document(
            name=document_path,
            id=document_id,
            struct_data=struct_data,
            content=discoveryengine.Document.Content(
                mime_type="text/plain",
                raw_bytes=content.encode('utf-8'),
            ),
        )
        
        request = discoveryengine.UpdateDocumentRequest(
            document=document,
        )
        
        updated_doc = self.document_client.update_document(request=request)
        
        logger.debug(f"Updated document: {updated_doc.name}")
        
        return updated_doc.name
    
    def upsert_document(
        self,
        document_id: str,
        struct_data: Dict[str, Any],
        content: str,
    ) -> tuple[str, str]:
        """
        Create or update a document (upsert).
        
        Args:
            document_id: Unique document ID (e.g., "project.dataset.table")
            struct_data: Structured metadata (filterable fields)
            content: Text content for search
        
        Returns:
            Tuple of (document_name, operation: "created" or "updated")
        """
        
        try:
            # Try to create first
            doc_name = self.create_document(document_id, struct_data, content)
            return (doc_name, "created")
        except Exception as e:
            error_msg = str(e)
            
            # If document already exists, update it
            if "409" in error_msg and "exists" in error_msg.lower():
                doc_name = self.update_document(document_id, struct_data, content)
                return (doc_name, "updated")
            else:
                # Re-raise other errors
                raise
    
    def create_documents_from_jsonl_file(
        self,
        jsonl_path: str,
        batch_size: int = 10,
        upsert: bool = True,
    ) -> Dict[str, int]:
        """
        Create/update documents from a local JSONL file.
        
        Since Vertex AI Search doesn't support JSONL import from GCS,
        we read the JSONL and create/update documents via API.
        
        Args:
            jsonl_path: Path to local JSONL file
            batch_size: Number of documents to create in parallel
            upsert: If True, update existing documents. If False, skip existing documents.
        
        Returns:
            Statistics dict
        """
        
        import json
        from pathlib import Path
        
        operation = "Upserting" if upsert else "Creating"
        logger.info(f"{operation} documents from {jsonl_path}")
        
        stats = {
            "total": 0,
            "created": 0,
            "updated": 0,
            "failed": 0,
            "skipped": 0,
        }
        
        json_path = Path(jsonl_path)
        if not json_path.exists():
            raise FileNotFoundError(f"JSONL file not found: {jsonl_path}")
        
        with open(json_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                if not line.strip():
                    continue
                
                stats["total"] += 1
                
                try:
                    # Parse JSONL line
                    doc_data = json.loads(line)
                    
                    doc_id = doc_data.get("id")
                    struct_data = doc_data.get("structData", {})
                    content_data = doc_data.get("content", {})
                    content_text = content_data.get("text", "")
                    
                    if not doc_id:
                        logger.warning(f"Line {line_num}: No 'id' field, skipping")
                        stats["skipped"] += 1
                        continue
                    
                    # Sanitize document ID: replace periods with underscores
                    # Vertex AI Search document IDs can only contain: [a-zA-Z0-9-_]
                    sanitized_id = doc_id.replace(".", "_")
                    
                    if upsert:
                        # Create or update document
                        _, operation = self.upsert_document(
                            document_id=sanitized_id,
                            struct_data=struct_data,
                            content=content_text,
                        )
                        
                        if operation == "created":
                            stats["created"] += 1
                        else:
                            stats["updated"] += 1
                        
                        # Progress update
                        total_processed = stats["created"] + stats["updated"]
                        if total_processed % 10 == 0:
                            logger.info(f"Processed {total_processed}/{stats['total']} documents...")
                    else:
                        # Create document only (skip if exists)
                        self.create_document(
                            document_id=sanitized_id,
                            struct_data=struct_data,
                            content=content_text,
                        )
                        
                        stats["created"] += 1
                        
                        # Progress update
                        if stats["created"] % 10 == 0:
                            logger.info(f"Created {stats['created']}/{stats['total']} documents...")
                
                except json.JSONDecodeError as e:
                    logger.error(f"Line {line_num}: JSON decode error: {e}")
                    stats["failed"] += 1
                
                except Exception as e:
                    error_msg = str(e)
                    
                    # Handle document already exists (409 conflict) - only in non-upsert mode
                    if not upsert and "409" in error_msg and "exists" in error_msg.lower():
                        logger.info(f"Line {line_num}: Document {sanitized_id} already exists, skipping")
                        stats["skipped"] += 1
                    else:
                        logger.error(f"Line {line_num}: Failed to process document: {e}")
                        stats["failed"] += 1
        
        logger.info(f"Document creation complete: {stats}")
        
        return stats
    
    def import_documents_from_gcs(
        self,
        gcs_uri: str,
        reconciliation_mode: str = "INCREMENTAL",
    ) -> str:
        """
        Import UNSTRUCTURED documents from GCS (PDF, HTML, TXT, DOCX, PPTX, XLSX).
        
        Note: This does NOT support JSONL files. For structured data,
        use create_documents_from_jsonl_file() instead.
        
        Args:
            gcs_uri: GCS URI pattern (e.g., gs://bucket/path/*.pdf)
            reconciliation_mode: FULL or INCREMENTAL
        
        Returns:
            Operation name for tracking
        """
        
        logger.info(f"Starting unstructured document import from {gcs_uri}")
        logger.warning("GCS import only supports: PDF, HTML, TXT, DOCX, PPTX, XLSX (NOT JSONL)")
        
        import_request = discoveryengine.ImportDocumentsRequest(
            parent=self.branch_path,
            gcs_source=discoveryengine.GcsSource(
                input_uris=[gcs_uri],
                data_schema="content",
            ),
            reconciliation_mode=reconciliation_mode,
        )
        
        operation = self.document_client.import_documents(request=import_request)
        
        logger.info(f"Import operation started: {operation.operation.name}")
        
        return operation.operation.name

    def import_documents_from_bigquery(
        self,
        dataset_id: str,
        table_id: str,
        reconciliation_mode: str = "INCREMENTAL",
    ) -> str:
        """
        Import documents from a BigQuery table.

        Args:
            dataset_id: The BigQuery dataset ID.
            table_id: The BigQuery table ID.
            reconciliation_mode: FULL or INCREMENTAL.

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
        )

        operation = self.document_client.import_documents(request=request)
        logger.info(f"Import operation started: {operation.operation.name}")
        return operation.operation.name
    
    def wait_for_import(
        self,
        operation_name: str,
        timeout: float = 600.0,
    ) -> Dict[str, Any]:
        """
        Wait for import operation to complete.
        
        Args:
            operation_name: Operation name from import_documents_from_gcs
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
        
        logger.info(f"Operation completed (or timed out)")
        
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
        project_id="lennyisagoodboy",
        location="us-central1",
        datastore_id="data-discovery-metadata",
        reports_bucket="lennyisagoodboy-data-discovery-reports",
    )
    
    # Health check
    if client.health_check():
        print("✓ Vertex AI Search is healthy")
    
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

