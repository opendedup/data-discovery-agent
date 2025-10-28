"""
Backfill dataset_region for existing discovered_assets records.

This script updates all records with NULL dataset_region to 'us-central1',
which is the region where all existing discovered data resides.
"""
from google.cloud import bigquery
import os
from dotenv import load_dotenv

load_dotenv()

project_id = os.getenv("GCP_PROJECT_ID")
dataset_id = os.getenv("BQ_DATASET", "data_discovery")
table_id = os.getenv("BQ_TABLE", "discovered_assets")
backfill_region = "us-central1"  # All existing data is in us-central1

client = bigquery.Client(project=project_id)

query = f"""
UPDATE `{project_id}.{dataset_id}.{table_id}`
SET dataset_region = '{backfill_region}'
WHERE dataset_region IS NULL
"""

print(f"Backfilling dataset_region='{backfill_region}' for {project_id}.{dataset_id}.{table_id}")
print("This will update all records with NULL dataset_region")
confirm = input("Continue? (yes/no): ")

if confirm.lower() == 'yes':
    job = client.query(query)
    result = job.result()
    print(f"✓ Updated {job.num_dml_affected_rows} rows")
else:
    print("Cancelled")

