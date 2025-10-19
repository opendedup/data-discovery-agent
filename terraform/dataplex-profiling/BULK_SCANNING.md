# Bulk Dataplex Data Profile Scanning

Automatically discover and create scans for all tables in your BigQuery projects.

## Two Approaches

### 🐍 Approach 1: Python Script (Recommended)

**Pros:**
- More flexible filtering (exclude patterns, table types, etc.)
- Better error handling and logging
- Can process multiple projects easily
- Preview mode with `--dry-run`
- Handles existing scans gracefully

**Usage:**

```bash
# Preview what would be created
poetry run python scripts/create-dataplex-scans-bulk.py \
  --project lennyisagoodboy \
  --dry-run

# Create scans for all tables in current project
poetry run python scripts/create-dataplex-scans-bulk.py \
  --project lennyisagoodboy

# Create scans for multiple projects
poetry run python scripts/create-dataplex-scans-bulk.py \
  --project lennyisagoodboy \
  --projects lennyisagoodboy other-project-id

# Exclude certain datasets
poetry run python scripts/create-dataplex-scans-bulk.py \
  --project lennyisagoodboy \
  --exclude-datasets _staging temp_ tmp_ test_

# Use lower sampling for large tables (faster, cheaper)
poetry run python scripts/create-dataplex-scans-bulk.py \
  --project lennyisagoodboy \
  --sampling-percent 10.0

# Test with limited tables
poetry run python scripts/create-dataplex-scans-bulk.py \
  --project lennyisagoodboy \
  --max-tables 5 \
  --dry-run
```

---

### 🏗️ Approach 2: Terraform (Declarative)

**Pros:**
- Declarative infrastructure as code
- Automatic state management
- Easy to destroy all scans with `terraform destroy`

**Cons:**
- Less flexible filtering
- Must specify datasets explicitly
- Terraform plan can be slow with many tables

**Usage:**

1. Edit `terraform.tfvars`:

```hcl
# Enable bulk scanning
bulk_scan_enabled = true

# Specify datasets to scan
bulk_scan_datasets = [
  {
    project_id = "lennyisagoodboy"
    dataset_id = "lfndata"
  },
  {
    project_id = "lennyisagoodboy"
    dataset_id = "abndata"
  },
]

# Optional: reduce sampling for large datasets
bulk_scan_sampling_percent = 100.0
```

2. Apply Terraform:

```bash
cd terraform/dataplex-profiling
terraform plan
terraform apply
```

3. View created scans:

```bash
terraform output bulk_scan_count
terraform output bulk_scan_ids
```

---

## Running the Scans

### Option 1: Automatic (Scheduled)

All scans are configured to run daily at 2 AM UTC automatically.

### Option 2: Manual (On-Demand)

Run all scans at once:

```bash
# Get list of scan IDs
SCANS=$(gcloud dataplex datascans list \
  --project=lennyisagoodboy \
  --location=us-central1 \
  --filter="labels.purpose=data-discovery" \
  --format="value(name)")

# Run each scan
for SCAN in $SCANS; do
  echo "Running: $SCAN"
  gcloud dataplex datascans run $SCAN
done
```

Or run specific scans:

```bash
gcloud dataplex datascans run profile-lfndata-post_game_summaries \
  --project=lennyisagoodboy \
  --location=us-central1
```

---

## Monitoring Scan Progress

Check status of all scans:

```bash
gcloud dataplex datascans list \
  --project=lennyisagoodboy \
  --location=us-central1 \
  --filter="labels.purpose=data-discovery"
```

Check jobs for a specific scan:

```bash
gcloud dataplex datascans jobs list \
  --datascan=profile-lfndata-post_game_summaries \
  --project=lennyisagoodboy \
  --location=us-central1 \
  --limit=5
```

---

## Cost Optimization

For large datasets (>1TB), consider:

### 1. Use Sampling

```bash
# Python script
poetry run python scripts/create-dataplex-scans-bulk.py \
  --project lennyisagoodboy \
  --sampling-percent 10.0  # Profile 10% of data

# Terraform
bulk_scan_sampling_percent = 10.0
```

### 2. Selective Scanning

Only scan tables that matter:

```bash
# Exclude test/staging datasets
poetry run python scripts/create-dataplex-scans-bulk.py \
  --project lennyisagoodboy \
  --exclude-datasets _staging temp_ tmp_ test_ dev_ sandbox_
```

### 3. Less Frequent Scanning

Edit `dataplex-scans.tf` to reduce frequency:

```hcl
execution_spec {
  trigger {
    schedule {
      cron = "0 2 * * 0"  # Weekly (Sunday at 2 AM) instead of daily
    }
  }
}
```

---

## Integration with Metadata Collector

Once scans are complete and have results, use them in the collector:

```bash
poetry run python scripts/collect-bigquery-metadata.py \
  --use-dataplex \
  --dataplex-location us-central1
```

The collector will:
1. Check for Dataplex profile results for each table
2. Use them if available (richer profiling + PII detection)
3. Fall back to SQL queries if not available

---

## Cleanup

### Python Script Scans

Delete all scans created by the script:

```bash
SCANS=$(gcloud dataplex datascans list \
  --project=lennyisagoodboy \
  --location=us-central1 \
  --filter="labels.purpose=data-discovery" \
  --format="value(name)")

for SCAN in $SCANS; do
  echo "Deleting: $SCAN"
  gcloud dataplex datascans delete $SCAN --quiet
done
```

### Terraform Scans

```bash
cd terraform/dataplex-profiling
terraform destroy
```

---

## Recommended Workflow

1. **Start small** - Test with one dataset first:
   ```bash
   poetry run python scripts/create-dataplex-scans-bulk.py \
     --project lennyisagoodboy \
     --max-tables 5 \
     --dry-run
   ```

2. **Run and verify** - Create scans for one dataset:
   ```bash
   poetry run python scripts/create-dataplex-scans-bulk.py \
     --project lennyisagoodboy \
     --max-tables 5
   ```

3. **Monitor** - Wait for scans to complete and check results

4. **Scale up** - Once verified, run for all tables:
   ```bash
   poetry run python scripts/create-dataplex-scans-bulk.py \
     --project lennyisagoodboy
   ```

5. **Integrate** - Use in metadata collector:
   ```bash
   poetry run python scripts/collect-bigquery-metadata.py \
     --use-dataplex
   ```

