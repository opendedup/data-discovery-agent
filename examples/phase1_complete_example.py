"""
Phase 1 Complete Example

This script demonstrates the complete Phase 1 workflow:
1. Format BigQuery metadata to JSONL
2. Export to GCS for Vertex AI Search ingestion
3. Search metadata using Vertex AI Search
4. Generate Markdown reports

Requirements:
- Vertex AI Search data store created
- GCS buckets created
- Proper IAM permissions
- Environment variables set (see .env.example)

Set the following environment variables:
- GCP_PROJECT_ID: Your GCP project ID
- GCS_JSONL_BUCKET: Your JSONL bucket name
- GCS_REPORTS_BUCKET: Your reports bucket name
- VERTEX_DATASTORE_ID: Your Vertex AI Search datastore ID (default: data-discovery-metadata)
- VERTEX_LOCATION: Vertex AI Search location (default: global)
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_discovery_agent.search import (
    MetadataFormatter,
    MarkdownFormatter,
    BigQueryAssetSchema,
)
from data_discovery_agent.clients import VertexSearchClient
from data_discovery_agent.models import SearchRequest

# Get configuration from environment variables
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "YOUR_PROJECT_ID")
JSONL_BUCKET = os.getenv("GCS_JSONL_BUCKET", f"{PROJECT_ID}-data-discovery-jsonl")
REPORTS_BUCKET = os.getenv("GCS_REPORTS_BUCKET", f"{PROJECT_ID}-data-discovery-reports")
DATASTORE_ID = os.getenv("VERTEX_DATASTORE_ID", "data-discovery-metadata")
LOCATION = os.getenv("VERTEX_LOCATION", "global")


def example_1_format_metadata():
    """Example 1: Format BigQuery table metadata to JSONL"""
    
    print("=" * 60)
    print("Example 1: Format Metadata to JSONL")
    print("=" * 60)
    
    formatter = MetadataFormatter(project_id=PROJECT_ID)
    
    # Simulate metadata from BigQuery discovery agent
    table_metadata = {
        "project_id": PROJECT_ID,
        "dataset_id": "finance",
        "table_id": "transactions",
        "table_type": "TABLE",
        "num_rows": 5000000,
        "num_bytes": 2500000000,
        "created_time": "2023-01-15T10:00:00Z",
        "modified_time": "2024-01-15T14:30:00Z",
        "description": "Central transactions table containing all customer purchase records",
    }
    
    schema_info = {
        "fields": [
            {"name": "transaction_id", "type": "STRING", "description": "Unique ID"},
            {"name": "customer_id", "type": "STRING", "description": "Customer reference"},
            {"name": "customer_email", "type": "STRING", "description": "Customer email [PII]"},
            {"name": "amount", "type": "NUMERIC", "description": "Amount in USD"},
            {"name": "transaction_date", "type": "DATE", "description": "Date of transaction"},
        ]
    }
    
    lineage_info = {
        "upstream_tables": ["stripe_raw.payments"],
        "downstream_tables": ["finance.revenue_summary", "analytics.customer_ltv"],
    }
    
    cost_info = {
        "storage_cost_usd": 50.0,
        "query_cost_usd": 75.50,
        "total_monthly_cost_usd": 125.50,
    }
    
    security_info = {
        "has_pii": True,
        "has_phi": False,
    }
    
    governance_info = {
        "owner_email": "finance-team@company.com",
        "team": "finance",
        "environment": "prod",
        "tags": ["pii", "financial", "transactions"],
    }
    
    # Format to BigQueryAssetSchema
    asset = formatter.format_bigquery_table(
        table_metadata=table_metadata,
        schema_info=schema_info,
        lineage_info=lineage_info,
        cost_info=cost_info,
        quality_info=None,
        security_info=security_info,
        governance_info=governance_info,
    )
    
    print(f"\nFormatted asset: {asset.id}")
    print(f"Has PII: {asset.struct_data.has_pii}")
    print(f"Row count: {asset.struct_data.row_count:,}")
    print(f"Monthly cost: ${asset.struct_data.monthly_cost_usd:.2f}")
    print(f"Volatility: {asset.struct_data.volatility}")
    print(f"Cache TTL: {asset.struct_data.cache_ttl}")
    
    # Export to local JSONL file
    output_path = Path("/tmp/bigquery_metadata_example.jsonl")
    formatter.export_to_jsonl([asset], output_path)
    
    print(f"\n✓ Exported to: {output_path}")
    print(f"  File size: {output_path.stat().st_size} bytes")
    
    return asset


def example_2_generate_markdown_report(asset: BigQueryAssetSchema):
    """Example 2: Generate Markdown report from asset"""
    
    print("\n" + "=" * 60)
    print("Example 2: Generate Markdown Report")
    print("=" * 60)
    
    formatter = MarkdownFormatter(project_id=PROJECT_ID)
    
    # Extended metadata for report
    extended_metadata = {
        "schema": {
            "fields": [
                {"name": "transaction_id", "type": "STRING", "mode": "REQUIRED", "description": "Unique ID"},
                {"name": "customer_id", "type": "STRING", "mode": "REQUIRED", "description": "Customer reference"},
                {"name": "customer_email", "type": "STRING", "mode": "NULLABLE", "description": "Customer email [PII]"},
                {"name": "amount", "type": "NUMERIC", "mode": "REQUIRED", "description": "Amount in USD"},
                {"name": "transaction_date", "type": "DATE", "mode": "REQUIRED", "description": "Date of transaction"},
            ]
        },
        "lineage": {
            "upstream_tables": ["stripe_raw.payments"],
            "downstream_tables": ["finance.revenue_summary", "analytics.customer_ltv"],
        },
        "usage": {
            "query_count_30d": 1250,
            "active_users_30d": 15,
            "avg_query_time_seconds": 2.3,
        }
    }
    
    # Generate report
    report = formatter.generate_table_report(
        asset=asset,
        extended_metadata=extended_metadata,
    )
    
    # Save to file
    output_path = Path("/tmp/transactions_report.md")
    formatter.export_to_file(report, output_path)
    
    print(f"\n✓ Generated report: {output_path}")
    print(f"  Length: {len(report)} characters")
    print("\nReport preview:")
    print("-" * 60)
    print(report[:500] + "...")
    
    return report


def example_3_search_metadata():
    """Example 3: Search metadata using Vertex AI Search"""
    
    print("\n" + "=" * 60)
    print("Example 3: Search Metadata")
    print("=" * 60)
    
    # Initialize client
    client = VertexSearchClient(
        project_id=PROJECT_ID,
        location=LOCATION,  # Data stores are global resources
        datastore_id=DATASTORE_ID,
        reports_bucket=REPORTS_BUCKET,
    )
    
    # Health check
    print("\nPerforming health check...")
    if client.health_check():
        print("✓ Vertex AI Search is healthy")
    else:
        print("✗ Vertex AI Search health check failed")
        return
    
    # Example searches
    test_queries = [
        SearchRequest(
            query="tables with PII data",
            has_pii=True,
            page_size=5,
        ),
        SearchRequest(
            query="expensive tables",
            min_cost=100.0,
            sort_by="monthly_cost_usd",
            sort_order="desc",
            page_size=5,
        ),
        SearchRequest(
            query="finance dataset tables",
            dataset_id="finance",
            page_size=5,
        ),
    ]
    
    for i, request in enumerate(test_queries, 1):
        print(f"\n--- Query {i}: {request.query} ---")
        
        try:
            response = client.search(request)
            
            print(f"Results: {len(response.results)} (total: {response.total_count})")
            print(f"Query time: {response.query_time_ms:.0f}ms")
            
            for j, result in enumerate(response.results[:3], 1):
                print(f"\n  {j}. {result.title}")
                print(f"     Type: {result.metadata.asset_type}")
                if result.metadata.row_count:
                    print(f"     Rows: {result.metadata.row_count:,}")
                if result.metadata.monthly_cost_usd:
                    print(f"     Cost: ${result.metadata.monthly_cost_usd:.2f}/month")
                print(f"     Snippet: {result.snippet[:80]}...")
                
        except Exception as e:
            print(f"  Error: {e}")


def example_4_export_to_gcs():
    """Example 4: Export data to GCS for ingestion"""
    
    print("\n" + "=" * 60)
    print("Example 4: Export to GCS")
    print("=" * 60)
    
    formatter = MetadataFormatter(project_id=PROJECT_ID)
    
    # Create sample assets
    assets = []
    
    for i in range(5):
        table_metadata = {
            "project_id": PROJECT_ID,
            "dataset_id": "example_dataset",
            "table_id": f"table_{i}",
            "table_type": "TABLE",
            "num_rows": 1000000 * (i + 1),
            "num_bytes": 500000000 * (i + 1),
        }
        
        asset = formatter.format_bigquery_table(
            table_metadata=table_metadata,
            cost_info={"monthly_cost_usd": 50.0 * (i + 1)},
        )
        
        assets.append(asset)
    
    print(f"\nCreated {len(assets)} sample assets")
    
    # Export to GCS (commented out to avoid actual GCS calls)
    # Uncomment when ready to actually export
    
    # batch_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    # gcs_uri = formatter.export_batch_to_gcs(
    #     documents=assets,
    #     gcs_bucket=JSONL_BUCKET,
    #     batch_id=batch_id,
    # )
    # print(f"\n✓ Exported to: {gcs_uri}")
    
    print("\n⚠ GCS export is commented out (set up GCS first)")
    print("  To actually export, uncomment the export_batch_to_gcs call")


def main():
    """Run all examples"""
    
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "Phase 1 - Complete Example" + " " * 22 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    try:
        # Example 1: Format metadata
        asset = example_1_format_metadata()
        
        # Example 2: Generate Markdown report
        report = example_2_generate_markdown_report(asset)
        
        # Example 3: Search metadata (requires Vertex AI Search to be set up)
        try:
            example_3_search_metadata()
        except Exception as e:
            print(f"\n⚠ Search example skipped: {e}")
            print("  Make sure Vertex AI Search is set up and data is ingested")
        
        # Example 4: Export to GCS (commented out by default)
        example_4_export_to_gcs()
        
        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Set up Vertex AI Search: ./scripts/setup-vertex-search.sh")
        print("2. Ingest data: gcloud alpha discovery-engine data-stores import documents ...")
        print("3. Run this script again to test search")
        print()
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

