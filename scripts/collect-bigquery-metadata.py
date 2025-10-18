#!/usr/bin/env python3
"""
BigQuery Metadata Collection Script

Scans BigQuery projects/datasets/tables and exports metadata to JSONL for Vertex AI Search.

Usage:
    poetry run python scripts/collect-bigquery-metadata.py [options]
    
Examples:
    # Collect from current project only
    poetry run python scripts/collect-bigquery-metadata.py
    
    # Collect from specific projects
    poetry run python scripts/collect-bigquery-metadata.py --projects proj1 proj2
    
    # Test with limited tables
    poetry run python scripts/collect-bigquery-metadata.py --max-tables 10
    
    # Export and trigger import
    poetry run python scripts/collect-bigquery-metadata.py --import
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_discovery_agent.collectors import BigQueryCollector
from data_discovery_agent.search import MetadataFormatter, MarkdownFormatter
from data_discovery_agent.clients import VertexSearchClient


def setup_logging(verbose: bool = False):
    """Configure logging"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def main():
    parser = argparse.ArgumentParser(
        description="Collect BigQuery metadata for Vertex AI Search",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Collection options
    parser.add_argument(
        '--project',
        default='lennyisagoodboy',
        help='GCP project ID (default: lennyisagoodboy)'
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
    
    # Export options
    parser.add_argument(
        '--output',
        type=Path,
        help='Local output path for JSONL (default: /tmp/bigquery_metadata_TIMESTAMP.jsonl)'
    )
    parser.add_argument(
        '--gcs-bucket',
        default='lennyisagoodboy-data-discovery-jsonl',
        help='GCS bucket for JSONL export'
    )
    parser.add_argument(
        '--reports-bucket',
        default='lennyisagoodboy-data-discovery-reports',
        help='GCS bucket for Markdown reports'
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
        help='Trigger Vertex AI Search import after export'
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
    
    args = parser.parse_args()
    
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
    print()
    
    try:
        # Step 1: Collect metadata
        print("Step 1: Collecting BigQuery metadata...")
        print("-" * 70)
        
        collector = BigQueryCollector(
            project_id=args.project,
            target_projects=args.projects,
            exclude_datasets=args.exclude_datasets,
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
            
            for asset in assets:
                try:
                    # Generate Markdown report
                    report = markdown_formatter.generate_table_report(asset)
                    
                    # Export to GCS if not skipping
                    if not args.skip_gcs:
                        # Convert struct_data to dict to access fields
                        struct_dict = asset.struct_data.model_dump() if hasattr(asset.struct_data, 'model_dump') else asset.struct_data.dict()
                        dataset_id = struct_dict.get('dataset_id', 'unknown')
                        table_id = struct_dict.get('table_id', 'unknown')
                        gcs_path = f"{dataset_id}/{table_id}.md"
                        
                        markdown_formatter.export_to_gcs(
                            markdown=report,
                            gcs_bucket=args.reports_bucket,
                            gcs_path=gcs_path,
                        )
                    
                    markdown_count += 1
                    
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
            print("\nStep 4: Creating documents in Vertex AI Search...")
            print("-" * 70)
            print("Note: Using Document Service API (GCS import doesn't support JSONL)")
            
            try:
                client = VertexSearchClient(
                    project_id=args.project,
                    location="global",
                    datastore_id=args.datastore,
                )
                
                # Create documents from local JSONL file
                stats = client.create_documents_from_jsonl_file(
                    jsonl_path=str(output_path),
                    batch_size=10,
                )
                
                print(f"✓ Document creation complete!")
                print(f"  Total:   {stats['total']}")
                print(f"  Created: {stats['created']}")
                print(f"  Failed:  {stats['failed']}")
                print(f"  Skipped: {stats['skipped']}")
                print(f"\n  Check data store in Cloud Console:")
                print(f"  https://console.cloud.google.com/gen-app-builder/engines?project={args.project}")
                
            except Exception as e:
                print(f"⚠️  Document creation failed: {e}")
                logger.exception("Document creation error")
                print(f"\n   Alternative: Convert JSONL to TXT and use GCS import")
                print(f"   Or create documents manually via API")
        
        elif args.trigger_import:
            print("\nStep 4: Skipped document creation (no --import flag)")
        
        # Summary
        print("\n" + "=" * 70)
        print("Collection Complete!")
        print("=" * 70)
        
        stats = collector.get_stats()
        print(f"\nStatistics:")
        print(f"  Projects scanned:  {stats['projects_scanned']}")
        print(f"  Datasets scanned:  {stats['datasets_scanned']}")
        print(f"  Tables scanned:    {stats['tables_scanned']}")
        print(f"  Assets exported:   {len(assets)}")
        print(f"  Errors:            {stats['errors']}")
        
        print(f"\nOutput:")
        print(f"  Local JSONL:      {output_path}")
        if gcs_uri:
            print(f"  GCS JSONL:        {gcs_uri}")
        if not args.skip_markdown and not args.skip_gcs:
            print(f"  Markdown reports: gs://{args.reports_bucket}/")
        
        print("\nNext steps:")
        if not args.trigger_import:
            print("1. Trigger Vertex AI Search import (run with --import)")
        print("2. Wait 2-10 minutes for indexing to complete")
        print("3. Test search: poetry run python examples/phase1_complete_example.py")
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

