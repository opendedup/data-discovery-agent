#!/usr/bin/env python3
"""
Bulk Dataplex Data Profile Scan Creator

Automatically discovers all BigQuery tables in specified projects and creates
Dataplex Data Profile Scans for them.

Usage:
    poetry run python scripts/create-dataplex-scans-bulk.py --project PROJECT_ID
    
Examples:
    # Create scans for all tables in current project
    poetry run python scripts/create-dataplex-scans-bulk.py --project lennyisagoodboy
    
    # Create scans for multiple projects
    poetry run python scripts/create-dataplex-scans-bulk.py --projects proj1 proj2
    
    # Exclude certain datasets
    poetry run python scripts/create-dataplex-scans-bulk.py \
      --project lennyisagoodboy \
      --exclude-datasets _staging temp_ tmp_
    
    # Preview without creating
    poetry run python scripts/create-dataplex-scans-bulk.py --project lennyisagoodboy --dry-run
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Set

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from google.cloud import bigquery
from data_discovery_agent.collectors.dataplex_profiler import DataplexProfiler

logger = logging.getLogger(__name__)


def discover_tables(
    project_id: str,
    target_projects: List[str],
    exclude_datasets: List[str],
    max_tables: int = None,
    filter_label_key: str = "ignore-gmcp-discovery-scan",
) -> List[tuple]:
    """
    Discover all BigQuery tables in specified projects.
    
    Applies hierarchical label-based filtering:
    - Dataset with filter_label_key=true: Skip all tables unless table has filter_label_key=false
    - Table with filter_label_key=true: Skip table (even if dataset allows)
    - Table with filter_label_key=false: Include table (even if dataset blocks)
    
    Args:
        project_id: Project ID for BigQuery client
        target_projects: List of projects to scan
        exclude_datasets: Dataset patterns to exclude
        max_tables: Maximum number of tables to discover
        filter_label_key: Label key to check for filtering (case-sensitive)
    
    Returns:
        List of (project_id, dataset_id, table_id) tuples
    """
    client = bigquery.Client(project=project_id)
    tables = []
    tables_filtered = 0
    
    for target_project in target_projects:
        logger.info(f"Scanning project: {target_project}")
        
        try:
            # List all datasets in the project
            datasets = list(client.list_datasets(project=target_project))
            
            for dataset in datasets:
                dataset_id = dataset.dataset_id
                
                # Check if dataset should be excluded
                if any(pattern in dataset_id for pattern in exclude_datasets):
                    logger.debug(f"  Skipping dataset (excluded): {dataset_id}")
                    continue
                
                # Get dataset labels
                try:
                    dataset_ref_full = f"{target_project}.{dataset_id}"
                    dataset_obj = client.get_dataset(dataset_ref_full)
                    dataset_labels = dict(dataset_obj.labels) if dataset_obj.labels else {}
                except Exception as e:
                    logger.debug(f"  Could not get labels for dataset {dataset_id}: {e}")
                    dataset_labels = {}
                
                # Check if dataset should be filtered
                dataset_filtered = (
                    filter_label_key in dataset_labels and 
                    str(dataset_labels[filter_label_key]).lower() == "true"
                )
                
                if dataset_filtered:
                    logger.debug(
                        f"  Dataset {dataset_id} has {filter_label_key}=true, "
                        f"will skip tables unless they have {filter_label_key}=false"
                    )
                
                logger.info(f"  Scanning dataset: {dataset_id}")
                
                # List all tables in the dataset
                dataset_ref = f"{target_project}.{dataset_id}"
                try:
                    tables_in_dataset = list(client.list_tables(dataset_ref))
                    
                    for table_ref in tables_in_dataset:
                        # Get table labels
                        try:
                            table_full_ref = f"{target_project}.{dataset_id}.{table_ref.table_id}"
                            table_obj = client.get_table(table_full_ref)
                            table_labels = dict(table_obj.labels) if table_obj.labels else {}
                        except Exception as e:
                            logger.debug(f"    Could not get labels for table {table_ref.table_id}: {e}")
                            table_labels = {}
                        
                        # Check if table should be filtered
                        table_filtered = (
                            filter_label_key in table_labels and 
                            str(table_labels[filter_label_key]).lower() == "true"
                        )
                        
                        # Apply hierarchical logic
                        should_skip = False
                        if filter_label_key in table_labels:
                            # Table has explicit label - use it (overrides dataset)
                            if table_filtered:
                                logger.debug(f"    Skipping table {table_ref.table_id}: {filter_label_key}=true")
                                should_skip = True
                            else:
                                logger.debug(
                                    f"    Including table {table_ref.table_id}: "
                                    f"{filter_label_key}=false (overrides dataset)"
                                )
                        elif dataset_filtered:
                            # No table label, but dataset is filtered
                            logger.debug(
                                f"    Skipping table {table_ref.table_id}: "
                                f"inherited from dataset {filter_label_key}=true"
                            )
                            should_skip = True
                        
                        if should_skip:
                            tables_filtered += 1
                            continue
                        
                        tables.append((target_project, dataset_id, table_ref.table_id))
                        logger.debug(f"    Found table: {table_ref.table_id}")
                        
                        if max_tables and len(tables) >= max_tables:
                            logger.info(f"Reached max_tables limit: {max_tables}")
                            logger.info(f"Tables filtered by label: {tables_filtered}")
                            return tables
                    
                except Exception as e:
                    logger.warning(f"Error listing tables in {dataset_ref}: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error scanning project {target_project}: {e}")
            continue
    
    logger.info(f"Tables filtered by label: {tables_filtered}")
    return tables


def create_scans(
    profiler: DataplexProfiler,
    tables: List[tuple],
    sampling_percent: float,
    schedule_cron: str,
    run_immediately: bool,
    dry_run: bool,
) -> dict:
    """
    Create Dataplex scans for discovered tables.
    
    Returns:
        Dictionary with statistics
    """
    stats = {
        'total_tables': len(tables),
        'scans_created': 0,
        'scans_existing': 0,
        'scans_failed': 0,
        'scans_triggered': 0,
        'scans_trigger_failed': 0,
    }
    
    for project_id, dataset_id, table_id in tables:
        # Replace underscores with hyphens for Dataplex compatibility
        scan_id = f"profile-{dataset_id}-{table_id}".replace("_", "-").lower()
        
        logger.info(f"Processing: {dataset_id}.{table_id}")
        
        if dry_run:
            logger.info(f"  [DRY RUN] Would create scan: {scan_id}")
            if run_immediately:
                logger.info(f"  [DRY RUN] Would trigger scan immediately")
            stats['scans_created'] += 1
            continue
        
        try:
            # Check if scan already exists
            scan_name = f"projects/{project_id}/locations/{profiler.location}/dataScans/{scan_id}"
            
            # Try to create the scan
            created_scan_name = profiler.create_profile_scan(
                dataset_id=dataset_id,
                table_id=table_id,
                scan_id=scan_id,
                sampling_percent=sampling_percent,
            )
            
            logger.info(f"  ✓ Created scan: {scan_id}")
            stats['scans_created'] += 1
            
            # Trigger scan immediately if requested
            if run_immediately:
                try:
                    job_name = profiler.run_profile_scan(created_scan_name)
                    logger.info(f"  ▶ Triggered scan immediately: {job_name}")
                    stats['scans_triggered'] += 1
                except Exception as trigger_error:
                    logger.warning(f"  ⚠ Failed to trigger scan: {trigger_error}")
                    stats['scans_trigger_failed'] += 1
            
        except Exception as e:
            error_msg = str(e)
            
            if "already exists" in error_msg or "ALREADY_EXISTS" in error_msg:
                logger.info(f"  ○ Scan already exists: {scan_id}")
                stats['scans_existing'] += 1
            else:
                logger.error(f"  ✗ Failed to create scan: {e}")
                stats['scans_failed'] += 1
    
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Bulk create Dataplex Data Profile Scans",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--project',
        required=True,
        help='GCP project ID (where scans will be created)'
    )
    parser.add_argument(
        '--projects',
        nargs='+',
        help='Target projects to scan (default: same as --project)'
    )
    parser.add_argument(
        '--location',
        default='us-central1',
        help='Dataplex location for scans (default: us-central1)'
    )
    parser.add_argument(
        '--exclude-datasets',
        nargs='+',
        default=['_staging', 'temp_', 'tmp_'],
        help='Dataset patterns to exclude'
    )
    parser.add_argument(
        '--filter-label-key',
        default='ignore-gmcp-discovery-scan',
        help='BigQuery label key to use for filtering (default: ignore-gmcp-discovery-scan). '
             'Tables/datasets with this label set to "true" are skipped. '
             'Table labels override dataset labels.'
    )
    parser.add_argument(
        '--max-tables',
        type=int,
        help='Maximum number of tables to process (for testing)'
    )
    parser.add_argument(
        '--sampling-percent',
        type=float,
        default=100.0,
        help='Sampling percentage for profiling (default: 100)'
    )
    parser.add_argument(
        '--schedule-cron',
        default='0 22 * * *',
        help='Cron schedule for scans (default: "0 22 * * *" = 10 PM daily)'
    )
    parser.add_argument(
        '--run-immediately',
        action='store_true',
        default=True,
        help='Trigger scans immediately after creation (default: True)'
    )
    parser.add_argument(
        '--no-run-immediately',
        dest='run_immediately',
        action='store_false',
        help='Do not trigger scans immediately'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview without creating scans'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    target_projects = args.projects or [args.project]
    
    print("=" * 70)
    print("Bulk Dataplex Data Profile Scan Creator")
    print("=" * 70)
    print()
    print(f"Project (scan location):  {args.project}")
    print(f"Target projects:          {', '.join(target_projects)}")
    print(f"Dataplex location:        {args.location}")
    print(f"Exclude datasets:         {', '.join(args.exclude_datasets)}")
    print(f"Filter label key:         {args.filter_label_key}")
    print(f"Sampling percent:         {args.sampling_percent}%")
    print(f"Scan schedule:            {args.schedule_cron}")
    print(f"Run immediately:          {'Yes' if args.run_immediately else 'No'}")
    print(f"Max tables:               {args.max_tables or 'unlimited'}")
    print(f"Mode:                     {'DRY RUN' if args.dry_run else 'CREATE'}")
    print()
    
    try:
        # Step 1: Discover tables
        print("Step 1: Discovering BigQuery tables...")
        print("-" * 70)
        
        tables = discover_tables(
            project_id=args.project,
            target_projects=target_projects,
            exclude_datasets=args.exclude_datasets,
            max_tables=args.max_tables,
            filter_label_key=args.filter_label_key,
        )
        
        print(f"✓ Discovered {len(tables)} tables")
        print()
        
        if len(tables) == 0:
            print("No tables found. Exiting.")
            return 0
        
        # Step 2: Create scans
        print("Step 2: Creating Dataplex Data Profile Scans...")
        print("-" * 70)
        
        profiler = DataplexProfiler(
            project_id=args.project,
            location=args.location
        )
        
        stats = create_scans(
            profiler=profiler,
            tables=tables,
            sampling_percent=args.sampling_percent,
            schedule_cron=args.schedule_cron,
            run_immediately=args.run_immediately,
            dry_run=args.dry_run,
        )
        
        print()
        print("=" * 70)
        print("Complete!")
        print("=" * 70)
        print()
        print(f"Total tables:       {stats['total_tables']}")
        print(f"Scans created:      {stats['scans_created']}")
        print(f"Scans triggered:    {stats['scans_triggered']}")
        print(f"Already existing:   {stats['scans_existing']}")
        print(f"Failed:             {stats['scans_failed']}")
        if stats['scans_trigger_failed'] > 0:
            print(f"Trigger failed:     {stats['scans_trigger_failed']}")
        print()
        
        if args.dry_run:
            print("This was a DRY RUN. Run without --dry-run to create scans.")
        else:
            print("Next steps:")
            if args.run_immediately:
                print(f"1. Scans are running! Monitor progress:")
                print(f"   gcloud dataplex datascans list --project={args.project} --location={args.location}")
                print()
                print(f"2. Wait for scans to complete (2-10 minutes per table)")
                print()
                print(f"3. Use Dataplex profiling in metadata collector:")
            else:
                print("1. Run the scans (they're scheduled, or run manually):")
                print(f"   gcloud dataplex datascans run SCAN_ID --project={args.project} --location={args.location}")
                print()
                print("2. Use Dataplex profiling in metadata collector:")
            print(f"   poetry run python scripts/collect-bigquery-metadata.py --use-dataplex --dataplex-location {args.location}")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())

