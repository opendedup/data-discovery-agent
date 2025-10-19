# Dataplex Scan Scheduling Guide

Configure scans to run automatically on a schedule that aligns with your metadata collection workflow.

## Default Schedule

By default, scans are configured to run:
- **Immediately** when first created (via `run_scans_on_create = true`)
- **Daily at 10 PM** (`0 22 * * *`) - 2 hours before midnight metadata collection

## Customizing the Schedule

### Common Schedules

Edit `terraform.tfvars` to set your preferred schedule:

```hcl
# Run 4 hours before midnight metadata collection
scan_schedule_cron = "0 20 * * *"  # 8 PM daily

# Run 6 hours before midnight
scan_schedule_cron = "0 18 * * *"  # 6 PM daily

# Run twice daily (morning and evening)
scan_schedule_cron = "0 6,18 * * *"  # 6 AM and 6 PM

# Run every 6 hours
scan_schedule_cron = "0 */6 * * *"

# Run weekly on Sunday at 10 PM
scan_schedule_cron = "0 22 * * 0"

# Run on weekdays at 8 PM
scan_schedule_cron = "0 20 * * 1-5"
```

### Cron Format Reference

```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6) (Sunday to Saturday)
│ │ │ │ │
│ │ │ │ │
* * * * *
```

**Examples:**
- `0 22 * * *` - Every day at 10 PM
- `30 18 * * 1-5` - Weekdays at 6:30 PM
- `0 */4 * * *` - Every 4 hours
- `0 6 * * 0` - Sundays at 6 AM

### Align with Metadata Collection

If your metadata collection runs at a specific time, schedule scans to complete before it:

**Example: Metadata collection runs at midnight**

```hcl
# Run scans at 10 PM (2 hours before)
scan_schedule_cron = "0 22 * * *"
```

**Example: Metadata collection runs at 6 AM**

```hcl
# Run scans at 4 AM (2 hours before)
scan_schedule_cron = "0 4 * * *"
```

**Example: Metadata collection runs hourly**

```hcl
# Run scans 15 minutes before each hour
scan_schedule_cron = "45 * * * *"
```

## Immediate Execution

### Terraform

Control whether scans run immediately after creation:

```hcl
# Run scans immediately (default)
run_scans_on_create = true

# Only schedule, don't run immediately
run_scans_on_create = false
```

### Python Script

```bash
# Run immediately after creation (default)
poetry run python scripts/create-dataplex-scans-bulk.py \
  --project lennyisagoodboy

# Create but don't run immediately
poetry run python scripts/create-dataplex-scans-bulk.py \
  --project lennyisagoodboy \
  --no-run-immediately

# Custom schedule with immediate run
poetry run python scripts/create-dataplex-scans-bulk.py \
  --project lennyisagoodboy \
  --schedule-cron "0 20 * * *"  # 8 PM daily
```

## Complete Workflow Example

### Scenario: Daily Data Pipeline

Your workflow:
1. **6 PM**: Data loads complete
2. **8 PM**: Dataplex scans run (profile fresh data)
3. **10 PM**: Scans complete (2 hour window)
4. **11 PM**: Metadata collector runs (uses Dataplex results)
5. **Midnight**: Vertex AI Search updated

**Configuration:**

```hcl
# terraform.tfvars
project_id = "lennyisagoodboy"
location = "us-central1"

# Schedule scans for 8 PM (after data loads)
scan_schedule_cron = "0 20 * * *"

# Run immediately on creation
run_scans_on_create = true
```

**Metadata collection cron:**
```bash
# Run at 11 PM
0 23 * * * cd /path/to/project && poetry run python scripts/collect-bigquery-metadata.py --use-dataplex
```

## Monitoring Scan Schedules

Check when scans are scheduled to run:

```bash
gcloud dataplex datascans list \
  --project=lennyisagoodboy \
  --location=us-central1 \
  --format="table(name,executionSpec.trigger.schedule.cron)"
```

View recent scan jobs:

```bash
gcloud dataplex datascans jobs list \
  --datascan=profile-lfndata-post_game_summaries \
  --project=lennyisagoodboy \
  --location=us-central1 \
  --limit=10
```

## Cost Optimization

For large datasets, balance freshness vs. cost:

### Daily Large Tables
```hcl
# Run daily at 2 AM, sample 10%
scan_schedule_cron = "0 2 * * *"
bulk_scan_sampling_percent = 10.0
```

### Weekly Full Scan
```hcl
# Run weekly Sunday at midnight, full scan
scan_schedule_cron = "0 0 * * 0"
bulk_scan_sampling_percent = 100.0
```

### Hourly Small Tables
```hcl
# Run every hour for critical small tables
scan_schedule_cron = "0 * * * *"
```

## Troubleshooting

### Scans not running on schedule

Check the schedule is valid:
```bash
# Describe the scan
gcloud dataplex datascans describe profile-lfndata-post_game_summaries \
  --project=lennyisagoodboy \
  --location=us-central1
```

### Manual trigger for testing

```bash
gcloud dataplex datascans run profile-lfndata-post_game_summaries \
  --project=lennyisagoodboy \
  --location=us-central1
```

### Update schedule for existing scan

Use Terraform to update:
```hcl
# Update terraform.tfvars
scan_schedule_cron = "0 18 * * *"  # Change to 6 PM
```

Then apply:
```bash
terraform apply
```

