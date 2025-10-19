"""
BigQuery Data Insights Integration

Integrates with BigQuery's Gemini-powered Data Insights to get:
- Natural language questions about the data
- SQL queries that answer those questions
- Auto-generated table and column descriptions

References:
- https://cloud.google.com/bigquery/docs/data-insights
- https://cloud.google.com/dataplex/docs/reference/rest/v1/projects.locations.entryGroups.entries
"""

import logging
from typing import Any, Dict, Optional, List
from google.cloud import datacatalog_v1
from google.cloud.datacatalog_v1.types import Entry, Tag

logger = logging.getLogger(__name__)


class GeminiInsightsClient:
    """
    Client for BigQuery Data Insights (Gemini-powered).
    
    Note: BigQuery Data Insights are primarily accessed through the BigQuery UI.
    The insights themselves (natural language questions and SQL queries) are stored
    in Dataplex Universal Catalog as tags.
    
    This client retrieves:
    - Generated insights from Dataplex
    - Auto-generated descriptions
    - Insight questions and queries
    """
    
    def __init__(self, project_id: str, location: str = "us"):
        """
        Initialize Gemini Insights client.
        
        Args:
            project_id: GCP project ID
            location: Data Catalog location (default: us)
        """
        self.project_id = project_id
        self.location = location
        self.catalog_client = datacatalog_v1.DataCatalogClient()
    
    def get_insights_for_table(
        self,
        dataset_id: str,
        table_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get Gemini-generated insights for a BigQuery table.
        
        Note: Insights must be generated in BigQuery UI first via
        the "Generate insights" button in the Insights tab.
        
        Args:
            dataset_id: BigQuery dataset ID
            table_id: BigQuery table ID
            
        Returns:
            Insights data or None if not available
        """
        try:
            # Lookup the Data Catalog entry for this BigQuery table
            linked_resource = (
                f"//bigquery.googleapis.com/projects/{self.project_id}"
                f"/datasets/{dataset_id}/tables/{table_id}"
            )
            
            request = datacatalog_v1.LookupEntryRequest(
                linked_resource=linked_resource
            )
            
            entry = self.catalog_client.lookup_entry(request=request)
            
            # List tags associated with this entry
            # Insights are stored as tags with specific templates
            tags_request = datacatalog_v1.ListTagsRequest(
                parent=entry.name
            )
            
            tags = self.catalog_client.list_tags(request=tags_request)
            
            insights = {
                "questions": [],
                "generated_description": None,
                "generated_column_descriptions": {},
            }
            
            for tag in tags:
                # Look for insight-related tags
                # The exact tag template depends on how BigQuery stores insights
                # This is a placeholder for when the API becomes more accessible
                if "insight" in tag.template.lower():
                    insights["questions"].append(self._parse_insight_tag(tag))
            
            if insights["questions"] or insights["generated_description"]:
                return insights
            
            logger.info(f"No Gemini insights found for {dataset_id}.{table_id}")
            logger.info("Note: Insights must be generated in BigQuery UI first")
            return None
            
        except Exception as e:
            logger.debug(f"Could not get Gemini insights for {dataset_id}.{table_id}: {e}")
            return None
    
    def _parse_insight_tag(self, tag: Tag) -> Dict[str, Any]:
        """Parse an insight tag into a structured format"""
        
        insight = {
            "question": None,
            "sql": None,
            "category": None,
        }
        
        for field_name, field_value in tag.fields.items():
            if "question" in field_name.lower():
                insight["question"] = field_value.string_value
            elif "sql" in field_name.lower() or "query" in field_name.lower():
                insight["sql"] = field_value.string_value
            elif "category" in field_name.lower():
                insight["category"] = field_value.string_value
        
        return insight
    
    def get_table_description(
        self,
        dataset_id: str,
        table_id: str,
    ) -> Optional[str]:
        """
        Get Gemini-generated table description.
        
        Args:
            dataset_id: BigQuery dataset ID
            table_id: BigQuery table ID
            
        Returns:
            Generated description or None
        """
        insights = self.get_insights_for_table(dataset_id, table_id)
        return insights.get("generated_description") if insights else None


# Note: BigQuery Data Insights API is primarily UI-based as of October 2024
# The programmatic API for retrieving insights is limited
# This module provides a placeholder for future API enhancements
# 
# Current workflow:
# 1. Use Dataplex Data Profile Scan for detailed statistics
# 2. Generate insights manually in BigQuery UI
# 3. Access insights through BigQuery UI or Dataplex catalog
#
# For now, we'll focus on Dataplex Data Profile Scan integration
# which provides rich metadata that can be included in reports

