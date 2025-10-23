#!/usr/bin/env python3
"""
BigQuery Metadata Collection Script

Scans BigQuery projects/datasets/tables and exports complete metadata to JSONL 
for Vertex AI Search. Automatically re-indexes the data after each collection.

The JSONL now includes:
- Full schema (all columns, including nested fields)
- Data quality metrics (null statistics)
- Column profiles (min/max/avg/distinct for numeric and string columns)
- Data lineage (upstream and downstream dependencies)
- Governance metadata (labels, tags, PII/PHI indicators)

Usage:
    poetry run python scripts/collect-bigquery-metadata.py [options]
    
Examples:
    # Collect from current project and auto-import to Vertex AI Search (default)
    poetry run python scripts/collect-bigquery-metadata.py
    
    # Collect with Dataplex profiling (richer data)
    poetry run python scripts/collect-bigquery-metadata.py --use-dataplex
    
    # Collect from specific projects
    poetry run python scripts/collect-bigquery-metadata.py --projects proj1 proj2
    
    # Test with limited tables
    poetry run python scripts/collect-bigquery-metadata.py --max-tables 10
    
    # Skip automatic import (for testing)
    poetry run python scripts/collect-bigquery-metadata.py --skip-import
"""

import argparse
import logging
import sys
import os
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_discovery_agent.collectors import BigQueryCollector
from data_discovery_agent.search import MetadataFormatter, MarkdownFormatter
from data_discovery_agent.clients import VertexSearchClient
from data_discovery_agent.writers.bigquery_writer import BigQueryWriter


def setup_logging(verbose: bool = False):
    """Configure logging"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def generate_single_markdown_report(
    asset,
    args,
    collector,
    markdown_formatter,
    logger,
):
    """Generate a single Markdown report for a table (for parallel execution)"""
    try:
        # Extract struct data
        struct_dict = asset.struct_data.model_dump() if hasattr(asset.struct_data, 'model_dump') else asset.struct_data.dict()
        
        # Build extended metadata by re-collecting the table metadata with schema
        dataset_id = struct_dict.get('dataset_id')
        table_id = struct_dict.get('table_id')
        project_id = struct_dict.get('project_id', args.project)
        
        # Get the full table schema from BigQuery
        from google.cloud import bigquery as bq
        bq_client = bq.Client(project=project_id)
        table_ref = f"{project_id}.{dataset_id}.{table_id}"
        
        try:
            table = bq_client.get_table(table_ref)
            
            # Build schema dict for extended_metadata with nested fields
            def format_field(field, prefix=""):
                """Recursively format a field including nested fields"""
                field_name = f"{prefix}{field.name}" if prefix else field.name
                field_dict = {
                    "name": field_name,
                    "type": field.field_type,
                    "mode": field.mode,
                    "description": field.description or "",
                }
                
                fields = [field_dict]
                
                # If this is a RECORD with nested fields, add them too
                if field.field_type in ('RECORD', 'STRUCT') and field.fields:
                    for nested_field in field.fields:
                        # Recursively format nested fields
                        nested_fields = format_field(nested_field, f"{field_name}.")
                        fields.extend(nested_fields)
                
                return fields
            
            schema_fields = []
            for field in table.schema:
                schema_fields.extend(format_field(field))
            
            # Get data quality stats
            quality_stats = collector._get_quality_stats(project_id, dataset_id, table_id, table.schema)
            
            # Get column profiling
            column_profiles = collector._get_column_profiles(project_id, dataset_id, table_id, table.schema)
            
            # Get sample values - use Dataplex if available (same logic as JSONL)
            sample_values = {}
            if collector.dataplex_profiler:
                sample_values = collector.dataplex_profiler.get_sample_values_from_profile(
                    dataset_id, table_id
                )
                if sample_values:
                    logger.info(f"Using Dataplex sample values for Markdown: {table_id} ({len(sample_values)} columns)")
            
            # Fall back to SQL-based sampling if no Dataplex samples
            if not sample_values and table.schema:
                logger.info(f"Fetching sample values via SQL for Markdown: {table_id}")
                sample_values = collector._get_sample_values(project_id, dataset_id, table_id, table.schema)
            
            # Get data lineage
            lineage = collector._get_lineage(project_id, dataset_id, table_id)
            
            # Generate analytical insights with Gemini (for Markdown)
            insights = None
            if collector.gemini_describer:
                try:
                    logger.info(f"Generating insights for Markdown: {table_id}")
                    insights = collector.gemini_describer.generate_table_insights(
                        table_name=table_ref,
                        description=table.description or "",
                        schema=schema_fields,
                        sample_values=sample_values,
                        column_profiles=column_profiles,
                        row_count=table.num_rows,
                        num_insights=5,
                    )
                    if insights:
                        logger.info(f"✓ Generated {len(insights)} insights for Markdown: {table_id}")
                except Exception as e:
                    logger.error(f"Error generating insights for Markdown {table_id}: {e}")
            
            # Merge sample values and insights into quality_stats
            if not quality_stats:
                quality_stats = {}
            
            if sample_values:
                quality_stats["sample_values"] = sample_values
            
            if insights:
                quality_stats["insights"] = insights
            
            extended_metadata = {
                "schema": {"fields": schema_fields},
                "description": table.description or "",
                "quality_stats": quality_stats,
                "column_profiles": column_profiles,
                "lineage": lineage if lineage else None,
            }
        except Exception as e:
            logger.warning(f"Could not fetch extended metadata for {table_ref}: {e}")
            extended_metadata = {}
        
        # Generate Markdown report with extended metadata
        report = markdown_formatter.generate_table_report(asset, extended_metadata=extended_metadata)
        
        # Export to GCS if not skipping
        if not args.skip_gcs:
            gcs_path = f"{dataset_id}/{table_id}.md"
            
            markdown_formatter.export_to_gcs(
                markdown=report,
                gcs_bucket=args.reports_bucket,
                gcs_path=gcs_path,
            )
        
        return {"success": True, "table_id": table_id}
        
    except Exception as e:
        logger.error(f"Failed to generate Markdown for {asset.id}: {e}")
        return {"success": False, "table_id": asset.id, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="Collect BigQuery metadata for Vertex AI Search",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Collection options
    parser.add_argument(
        '--project',
        default=os.getenv('GCP_PROJECT_ID', os.getenv('PROJECT_ID', '')),
        help='GCP project ID (default: from GCP_PROJECT_ID or PROJECT_ID env var)'
    )
    parser.add_argument(
        '--projects',
        nargs='+',
        help='Target projects to scan (default: current project only)'
    )
    parser.add_argument(
        '--max-tables',
        type=int,
        help='Maximum number of tables to collect (for testing)'
    )
    parser.add_argument(
        '--exclude-datasets',
        nargs='+',
        default=['_staging', 'temp_', 'tmp_'],
        help='Dataset patterns to exclude'
    )
    parser.add_argument(
        '--skip-views',
        action='store_true',
        help='Skip views, collect tables only'
    )
    parser.add_argument(
        '--use-dataplex',
        action='store_true',
        help='Use Dataplex Data Profile Scan for richer profiling (instead of SQL-based)'
    )
    parser.add_argument(
        '--dataplex-location',
        default='us-central1',
        help='Dataplex location for profile scans (default: us-central1)'
    )
    parser.add_argument(
        '--use-gemini',
        action='store_true',
        default=True,
        help='Use Gemini 2.5 Flash to generate descriptions for tables without them (default: enabled)'
    )
    parser.add_argument(
        '--skip-gemini',
        action='store_true',
        help='Skip Gemini description generation'
    )
    parser.add_argument(
        '--gemini-api-key',
        help='Gemini API key (or use GEMINI_API_KEY env var)'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=os.cpu_count(),
        help=f'Number of concurrent threads for data collection (default: {os.cpu_count()} CPU cores)'
    )
    
    # Export options
    parser.add_argument(
        '--output',
        type=Path,
        help='Local output path for JSONL (default: /tmp/bigquery_metadata_TIMESTAMP.jsonl)'
    )
    parser.add_argument(
        '--gcs-bucket',
        default=os.getenv('GCS_JSONL_BUCKET', f"{os.getenv('GCP_PROJECT_ID', os.getenv('PROJECT_ID', ''))}-data-discovery-jsonl"),
        help='GCS bucket for JSONL export (default: ${PROJECT_ID}-data-discovery-jsonl)'
    )
    parser.add_argument(
        '--reports-bucket',
        default=os.getenv('GCS_REPORTS_BUCKET', f"{os.getenv('GCP_PROJECT_ID', os.getenv('PROJECT_ID', ''))}-data-discovery-reports"),
        help='GCS bucket for Markdown reports (default: ${PROJECT_ID}-data-discovery-reports)'
    )
    parser.add_argument(
        '--skip-gcs',
        action='store_true',
        help='Skip GCS upload, save locally only'
    )
    parser.add_argument(
        '--skip-markdown',
        action='store_true',
        help='Skip Markdown report generation'
    )
    
    # Import options
    parser.add_argument(
        '--import',
        dest='trigger_import',
        action='store_true',
        default=True,
        help='Trigger Vertex AI Search import after export (default: enabled)'
    )
    parser.add_argument(
        '--skip-import',
        action='store_true',
        help='Skip Vertex AI Search import (documents won\'t be searchable until imported)'
    )
    parser.add_argument(
        '--datastore',
        default='data-discovery-metadata',
        help='Vertex AI Search data store ID'
    )
    
    # Other options
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    
    # BigQuery Export options
    parser.add_argument(
        '--export-to-bigquery',
        action='store_true',
        help='Export metadata to a BigQuery table'
    )
    parser.add_argument(
        '--bq-dataset',
        default='data_discovery',
        help='BigQuery dataset for metadata export'
    )
    parser.add_argument(
        '--bq-table',
        default='discovered_assets',
        help='BigQuery table for metadata export'
    )
    
    args = parser.parse_args()
    
    # Handle skip-import flag
    if args.skip_import:
        args.trigger_import = False
    
    # Handle skip-gemini flag
    if args.skip_gemini:
        args.use_gemini = False
    
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    print("=" * 70)
    print("BigQuery Metadata Collection - Phase 2.1")
    print("=" * 70)
    print()
    print(f"Project: {args.project}")
    print(f"Target projects: {args.projects or [args.project]}")
    print(f"Exclude datasets: {args.exclude_datasets}")
    print(f"Max tables: {args.max_tables or 'unlimited'}")
    print(f"Include views: {not args.skip_views}")
    print(f"Dataplex profiling: {'enabled' if args.use_dataplex else 'disabled (SQL fallback)'}")
    if args.use_dataplex:
        print(f"Dataplex location: {args.dataplex_location}")
    print(f"Gemini descriptions: {'enabled' if args.use_gemini else 'disabled'}")
    print(f"Concurrent workers: {args.workers}")
    print(f"Auto-import to Vertex AI Search: {'enabled' if args.trigger_import else 'disabled'}")
    print()
    
    try:
        # Step 1: Collect metadata
        print("Step 1: Collecting BigQuery metadata...")
        print("-" * 70)
        
        collector = BigQueryCollector(
            project_id=args.project,
            target_projects=args.projects,
            exclude_datasets=args.exclude_datasets,
            use_dataplex_profiling=args.use_dataplex,
            dataplex_location=args.dataplex_location,
            use_gemini_descriptions=args.use_gemini,
            gemini_api_key=args.gemini_api_key,
            max_workers=args.workers,
        )
        
        assets = collector.collect_all(
            max_tables=args.max_tables,
            include_views=not args.skip_views,
        )
        
        if not assets:
            print("\n⚠️  No tables found or collected")
            return 1
        
        print(f"\n✓ Collected {len(assets)} assets")
        
        # Step 2: Export to JSONL
        print("\nStep 2: Exporting to JSONL...")
        print("-" * 70)
        
        formatter = MetadataFormatter(project_id=args.project)
        
        # Determine output path
        if args.output:
            output_path = args.output
        else:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            output_path = Path(f"/tmp/bigquery_metadata_{timestamp}.jsonl")
        
        # Export locally
        count = formatter.export_to_jsonl(assets, output_path)
        print(f"✓ Exported {count} documents to {output_path}")
        print(f"  File size: {output_path.stat().st_size:,} bytes")
        
        # Step 3: Upload JSONL to GCS
        if not args.skip_gcs:
            print("\nStep 3: Uploading JSONL to GCS...")
            print("-" * 70)
            
            try:
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                gcs_uri = formatter.export_batch_to_gcs(
                    documents=assets,
                    gcs_bucket=args.gcs_bucket,
                    batch_id=timestamp,
                )
                print(f"✓ Uploaded JSONL to {gcs_uri}")
            except Exception as e:
                print(f"⚠️  JSONL GCS upload failed: {e}")
                print("   You can manually upload the local file later")
                gcs_uri = None
        else:
            print("\nStep 3: Skipped JSONL GCS upload (--skip-gcs)")
            gcs_uri = None
        
        # Step 3.5: Generate and upload Markdown reports
        if not args.skip_markdown:
            print("\nStep 3.5: Generating Markdown reports...")
            print("-" * 70)
            
            markdown_formatter = MarkdownFormatter(project_id=args.project)
            markdown_count = 0
            
            print(f"  Generating reports with {args.workers} workers...")
            
            # Process Markdown reports in parallel using ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                # Submit all tasks
                future_to_asset = {
                    executor.submit(
                        generate_single_markdown_report,
                        asset,
                        args,
                        collector,
                        markdown_formatter,
                        logger,
                    ): asset
                    for asset in assets
                }
                
                # Collect results as they complete
                for future in as_completed(future_to_asset):
                    asset = future_to_asset[future]
                    try:
                        result = future.result()
                        if result["success"]:
                            markdown_count += 1
                            
                            # Progress update
                            if markdown_count % 10 == 0:
                                print(f"  Generated {markdown_count}/{len(assets)} reports...")
                    except Exception as e:
                        logger.error(f"Failed to generate Markdown for {asset.id}: {e}")
                        continue
            
            print(f"✓ Generated {markdown_count} Markdown reports")
            if not args.skip_gcs:
                print(f"  Uploaded to gs://{args.reports_bucket}/")
        else:
            print("\nStep 3.5: Skipped Markdown generation (--skip-markdown)")
        
        # Step 4: Create documents via API (JSONL not supported in GCS import)
        if args.trigger_import:
            print("\nStep 4: Importing documents into Vertex AI Search...")
            print("-" * 70)
            
            try:
                client = VertexSearchClient(
                    project_id=args.project,
                    location="global",
                    datastore_id=args.datastore,
                )
                
                if args.export_to_bigquery:
                    # New: Import from BigQuery table
                    print(f"Importing from BigQuery table: {args.project}.{args.bq_dataset}.{args.bq_table}")
                    operation_name = client.import_documents_from_bigquery(
                        dataset_id=args.bq_dataset,
                        table_id=args.bq_table,
                        reconciliation_mode="FULL",
                    )
                    print(f"✓ Import started. Operation: {operation_name}")
                    print("  Check the status in the Google Cloud Console.")
                
                else:
                    # Legacy: Import from JSONL file
                    print(f"Importing from local JSONL file: {output_path}")
                    print("Note: Using Document Service API (GCS import doesn't support JSONL)")
                    stats = client.create_documents_from_jsonl_file(
                        jsonl_path=str(output_path),
                        batch_size=10,
                    )
                    
                    print(f"✓ Document indexing complete!")
                    print(f"  Total:   {stats['total']}")
                    print(f"  Created: {stats['created']}")
                    print(f"  Updated: {stats.get('updated', 0)}")
                    print(f"  Failed:  {stats['failed']}")
                    print(f"  Skipped: {stats['skipped']}")
                
                print(f"\n  Check data store in Cloud Console:")
                print(f"  https://console.cloud.google.com/gen-app-builder/engines?project={args.project}")
                
            except Exception as e:
                print(f"⚠️  Document import failed: {e}")
                logger.exception("Document import error")
        
        else:
            print("\nStep 4: Skipped document import (--skip-import flag)")
        
        # Summary
        print("\n" + "=" * 70)
        print("Collection Complete!")
        print("=" * 70)
        
        stats = collector.get_stats()
        print(f"\nStatistics:")
        print(f"  Projects scanned:         {stats['projects_scanned']}")
        print(f"  Datasets scanned:         {stats['datasets_scanned']}")
        print(f"  Tables scanned:           {stats['tables_scanned']}")
        print(f"  Assets exported:          {len(assets)}")
        if stats.get('descriptions_generated', 0) > 0:
            print(f"  Descriptions generated:   {stats['descriptions_generated']}")
        print(f"  Errors:                   {stats['errors']}")
        
        print(f"\nOutput:")
        print(f"  Local JSONL:      {output_path}")
        if gcs_uri:
            print(f"  GCS JSONL:        {gcs_uri}")
        if not args.skip_markdown and not args.skip_gcs:
            print(f"  Markdown reports: gs://{args.reports_bucket}/")
        
        # Step 5: Export to BigQuery
        if args.export_to_bigquery:
            print("\nStep 5: Exporting to BigQuery...")
            print("-" * 70)
            try:
                bq_writer = BigQueryWriter(
                    project_id=args.project,
                    dataset_id=args.bq_dataset,
                    table_id=args.bq_table
                )
                
                # Convert assets to dicts for BQ writer
                asset_dicts = [asset.model_dump() for asset in assets]
                
                bq_writer.write_to_bigquery(assets=asset_dicts)
                print(f"✓ Exported {len(assets)} assets to BigQuery table: {args.project}.{bq_writer.dataset_id}.{bq_writer.table_id}")
            except Exception as e:
                print(f"⚠️  BigQuery export failed: {e}")
                logger.exception("BigQuery export error")

        print("\nNext steps:")
        if args.trigger_import:
            print("1. Wait 2-10 minutes for indexing to complete in Vertex AI Search")
            print("2. Test search: poetry run python scripts/test-search.py 'your query'")
            print("3. View Markdown reports in GCS Console or locally")
        else:
            print("1. Trigger Vertex AI Search import (run without --skip-import)")
            print("2. Wait 2-10 minutes for indexing to complete")
            print("3. Test search: poetry run python scripts/test-search.py 'your query'")
            print("4. View Markdown reports in GCS Console or locally")
        print()
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        return 130
    
    except Exception as e:
        logger.exception("Collection failed")
        print(f"\n✗ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

