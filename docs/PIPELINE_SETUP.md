# Pipeline Setup Guide

Complete instructions for setting up the Data Discovery Agent infrastructure and deploying the pipeline code.

> **Note**: This guide covers a **simple Cloud Composer-based deployment**. GKE is **optional** and not required for basic pipeline operation. All data discovery workflows run in the managed Cloud Composer environment.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Step 1: Initial Setup](#step-1-initial-setup)
- [Step 2: Configure Environment Variables](#step-2-configure-environment-variables)
- [Step 3: Deploy Infrastructure with Terraform](#step-3-deploy-infrastructure-with-terraform)
- [Step 4: Create Vertex AI Search Datastore](#step-4-create-vertex-ai-search-datastore)
- [Step 5: Deploy Pipeline Code](#step-5-deploy-pipeline-code)
- [Step 6: Verify Deployment](#step-6-verify-deployment)
- [Step 7: Run the Pipeline](#step-7-run-the-pipeline)
- [Troubleshooting](#troubleshooting)
- [Updating the Pipeline](#updating-the-pipeline)

---

## Architecture: GKE vs Composer-Only

### Simple Setup (Recommended)

**Use Composer-only deployment** (`enable_gke = false`):
- ✅ All workflows run on managed Cloud Composer/Airflow
- ✅ No Kubernetes management required
- ✅ Lower cost (~$305-430/month)
- ✅ Simpler operations and maintenance
- ✅ Adequate for most data discovery use cases

### When to Enable GKE

**Enable GKE** (`enable_gke = true`) only if you need:
- Custom containerized workloads outside Airflow
- Microservices architecture
- Real-time API endpoints for data discovery
- Custom ML inference services
- Advanced Kubernetes features (service mesh, operators, etc.)

**For this guide, we recommend starting with `enable_gke = false`.**

---

## Prerequisites

### Required Tools

Install the following tools before starting:

1. **Google Cloud SDK (gcloud)** - Required
   ```bash
   # Install gcloud CLI
   curl https://sdk.cloud.google.com | bash
   exec -l $SHELL
   gcloud init
   ```

2. **Terraform** (v1.0+) - Required
   ```bash
   # Download and install Terraform
   wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
   unzip terraform_1.6.0_linux_amd64.zip
   sudo mv terraform /usr/local/bin/
   terraform --version
   ```

3. **Python** (3.11+) - Optional (only for local development)
   ```bash
   python3 --version
   ```

4. **uv** (Python package manager) - Optional (only for local development)
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

5. **kubectl** - Optional (only if `enable_gke = true`)
   ```bash
   # Only install if you plan to enable GKE
   gcloud components install kubectl
   ```

**Note**: For a simple Composer-only deployment, you only need gcloud and Terraform.

### GCP Project Setup

1. **Create or select a GCP project**
   ```bash
   gcloud projects create YOUR-PROJECT-ID
   # OR select existing project
   gcloud config set project YOUR-PROJECT-ID
   ```

2. **Enable billing** for the project via the [GCP Console](https://console.cloud.google.com/billing)

3. **Set up authentication**
   ```bash
   gcloud auth login
   gcloud auth application-default login
   ```

4. **Required IAM Roles** (for the user running Terraform)
   - `roles/owner` OR
   - `roles/editor` + `roles/iam.securityAdmin` + `roles/serviceusage.serviceUsageAdmin`

---

## Step 1: Initial Setup

### 1.1 Clone the Repository

```bash
git clone <repository-url>
cd data-discovery-agent
```

### 1.2 Set Your GCP Project

```bash
export PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID
```

### 1.3 Verify Project Access

```bash
gcloud projects describe $PROJECT_ID
```

---

## Step 2: Configure Environment Variables

### 2.1 Copy Environment Template

```bash
cp .env.example .env
```

### 2.2 Edit `.env` File

Open `.env` and set all required values:

```bash
# GCP Configuration
GCP_PROJECT_ID=your-project-id
GCP_REGION=us-central1

# BigQuery Configuration
BQ_DATASET_NAME=data_discovery
BQ_TABLE_NAME=discovered_assets
BQ_LOCATION=US

# Vertex AI Search Configuration
VERTEX_DATASTORE_ID=data-discovery-metadata
VERTEX_LOCATION=global

# GCS Buckets (will be created by Terraform with project prefix)
JSONL_BUCKET_NAME=your-project-id-data-discovery-jsonl
REPORTS_BUCKET_NAME=your-project-id-data-discovery-reports

# Lineage Configuration
LINEAGE_ENABLED=true
LINEAGE_LOCATION=us-central1

# Monitoring
LOG_LEVEL=INFO
```

### 2.3 Create Terraform Variables File

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:

```hcl
project_id = "your-project-id"
region     = "us-central1"

# GKE Configuration (OPTIONAL - set to false for simple setup)
# For a basic pipeline, you do NOT need GKE - everything runs on Cloud Composer
enable_gke = false  # Set to true only if you need custom containerized workloads

# If enable_gke = true, configure these:
cluster_name       = "data-discovery-cluster"
machine_type       = "e2-standard-2"
initial_node_count = 2
min_node_count     = 1
max_node_count     = 5

# Vertex AI Search
vertex_datastore_id = "data-discovery-metadata"
vertex_location     = "global"

# BigQuery
bq_dataset  = "data_discovery"
bq_table    = "discovered_assets"
bq_location = "US"

# Lineage
lineage_enabled  = true
lineage_location = "us-central1"

# Storage Configuration
jsonl_bucket_name   = "your-project-id-data-discovery-jsonl"
reports_bucket_name = "your-project-id-data-discovery-reports"

# Environment
environment = "dev"
```

**Important**: For a simple pipeline setup, set `enable_gke = false`. The entire data discovery pipeline runs on Cloud Composer (managed Airflow) without needing GKE.

---

## Step 3: Deploy Infrastructure with Terraform

### 3.1 Initialize Terraform

```bash
cd terraform
terraform init
```

Expected output: "Terraform has been successfully initialized!"

### 3.2 Review the Plan

```bash
terraform plan -out=tfplan
```

Review the resources that will be created:
- Service Accounts (3-4, depending on GKE setting)
- GCS Buckets (2)
- BigQuery Dataset and Table (via Composer)
- Cloud Composer Environment
- GKE Cluster (only if `enable_gke = true`)
- IAM Bindings (~25)
- Monitoring and Logging

**Note**: If `enable_gke = false`, no GKE resources will be created.

### 3.3 Apply the Infrastructure

```bash
terraform apply tfplan
```

**⏱️ Expected Duration**: 
- With GKE disabled (`enable_gke = false`): 20-25 minutes
- With GKE enabled (`enable_gke = true`): 25-35 minutes

Cloud Composer takes the longest to provision (15-20 minutes).

**Note**: If you get an error about API enablement, wait 1-2 minutes and retry. Some APIs need time to propagate.

### 3.4 Save Terraform Outputs

```bash
terraform output > ../terraform-outputs.txt
```

**GKE Note**: If you set `enable_gke = false`, GKE-related outputs will show `null` or "GKE is disabled". This is expected and normal.

---

## Step 4: Create Vertex AI Search Datastore

### 4.1 Navigate to Vertex AI Search

1. Go to [Vertex AI Search Console](https://console.cloud.google.com/gen-app-builder/engines)
2. Click **"Create App"**

### 4.2 Configure the Datastore

| Setting | Value |
|---------|-------|
| **App Type** | Search |
| **Content Type** | Structured data |
| **Data Store Name** | `data-discovery-metadata` |
| **Industry** | Generic |
| **Location** | Global |

### 4.3 Create Data Store Schema

Set up the schema for discovered assets:

```json
{
  "project_id": "string",
  "dataset_id": "string",
  "table_id": "string",
  "table_type": "string",
  "row_count": "number",
  "size_bytes": "number",
  "created_time": "timestamp",
  "modified_time": "timestamp",
  "description": "string",
  "labels": "string",
  "has_pii": "boolean",
  "environment": "string",
  "full_table_id": "string"
}
```

### 4.4 Note the Data Store ID

Copy the Data Store ID from the console (should match `data-discovery-metadata`).

---

## Step 5: Deploy Pipeline Code

### 5.1 Get Composer Bucket Name

```bash
cd ..  # Back to project root
export COMPOSER_BUCKET=$(gcloud composer environments describe data-discovery-agent-composer \
  --location us-central1 \
  --format="value(config.dagGcsPrefix)")

echo "Composer bucket: $COMPOSER_BUCKET"
# Should output: gs://us-central1-data-discovery--XXXXXXXX-bucket/dags
```

### 5.2 Upload DAG File

```bash
gsutil cp dags/metadata_collection_dag.py $COMPOSER_BUCKET/
```

### 5.3 Upload Source Code

```bash
gsutil -m cp -r src/data_discovery_agent $COMPOSER_BUCKET/src/
```

### 5.4 Upload .airflowignore

```bash
gsutil cp .airflowignore $COMPOSER_BUCKET/
```

### 5.5 Wait for Composer to Pick Up Changes

```bash
echo "Waiting for Airflow to scan DAGs (30 seconds)..."
sleep 30
```

---

## Step 6: Verify Deployment

### 6.1 Check Composer Environment Status

```bash
gcloud composer environments describe data-discovery-agent-composer \
  --location us-central1 \
  --format="value(state)"
```

Expected: `RUNNING`

### 6.2 List DAGs

```bash
gcloud composer environments run data-discovery-agent-composer \
  --location us-central1 \
  dags list
```

You should see: `bigquery_metadata_collection`

### 6.3 Check for Import Errors

```bash
gcloud composer environments run data-discovery-agent-composer \
  --location us-central1 \
  dags list-import-errors
```

Expected: `No data found` (no errors)

### 6.4 Verify Service Accounts

```bash
# Check Composer service account (always created)
gcloud iam service-accounts describe data-discovery-composer@${PROJECT_ID}.iam.gserviceaccount.com

# Check Discovery service account (always created)
gcloud iam service-accounts describe data-discovery-agent@${PROJECT_ID}.iam.gserviceaccount.com

# Check GKE service account (only if enable_gke = true)
# gcloud iam service-accounts describe data-discovery-gke@${PROJECT_ID}.iam.gserviceaccount.com
```

### 6.5 Verify BigQuery Dataset

```bash
bq ls
bq show data_discovery
bq show data_discovery.discovered_assets
```

### 6.6 Verify GCS Buckets

```bash
gsutil ls -L gs://${PROJECT_ID}-data-discovery-jsonl
gsutil ls -L gs://${PROJECT_ID}-data-discovery-reports
```

---

## Step 7: Run the Pipeline

### 7.1 Manual Trigger (First Run)

```bash
gcloud composer environments run data-discovery-agent-composer \
  --location us-central1 \
  dags trigger -- bigquery_metadata_collection
```

### 7.2 Monitor DAG Execution

**Option 1: Via Airflow Web UI**
```bash
# Get the Airflow web UI URL
gcloud composer environments describe data-discovery-agent-composer \
  --location us-central1 \
  --format="value(config.airflowUri)"
```

Open the URL in your browser and navigate to the DAG view.

**Option 2: Via Command Line**
```bash
# Check DAG runs
gcloud composer environments run data-discovery-agent-composer \
  --location us-central1 \
  dags list-jobs -- -d bigquery_metadata_collection
```

### 7.3 Check Logs (Real-time)

```bash
gcloud logging read \
  'resource.type="cloud_composer_environment" 
   AND resource.labels.environment_name="data-discovery-agent-composer"' \
  --limit 50 \
  --format=json \
  --freshness=10m
```

### 7.4 Verify Pipeline Output

**Check BigQuery Records**
```bash
bq query --use_legacy_sql=false \
  'SELECT COUNT(*) as total_records, 
          MAX(run_timestamp) as latest_run 
   FROM `'${PROJECT_ID}'.data_discovery.discovered_assets`'
```

**Check GCS Reports**
```bash
gsutil ls gs://${PROJECT_ID}-data-discovery-reports/reports/
```

**Check Vertex AI Search Imports**
```bash
# View the datastore in console
open "https://console.cloud.google.com/gen-app-builder/engines?project=${PROJECT_ID}"
```

### 7.5 Verify Lineage Tracking

```bash
# Check lineage logs
gcloud logging read \
  'resource.type="cloud_composer_environment" 
   AND textPayload=~".*lineage.*"' \
  --limit 10 \
  --format="table(timestamp,severity,textPayload)" \
  --freshness=30m
```

Expected logs:
- `Created lineage process: projects/.../processes/...`
- `Created lineage run: projects/.../processes/.../runs/...`
- `Successfully recorded lineage for X/X events`

---

## Troubleshooting

### Common Issues and Solutions

#### 1. **Terraform Apply Fails with API Not Enabled**

**Error**: `Error 403: ... API has not been used in project`

**Solution**:
```bash
# Enable all required APIs
gcloud services enable \
  bigquery.googleapis.com \
  composer.googleapis.com \
  container.googleapis.com \
  storage.googleapis.com \
  datacatalog.googleapis.com \
  aiplatform.googleapis.com \
  dlp.googleapis.com \
  dataplex.googleapis.com \
  discoveryengine.googleapis.com \
  datalineage.googleapis.com

# Wait 2 minutes for propagation, then retry
sleep 120
terraform apply tfplan
```

#### 2. **Composer Environment Stuck in CREATING**

**Issue**: Environment takes > 30 minutes to create

**Solution**:
```bash
# Check environment state
gcloud composer environments describe data-discovery-agent-composer \
  --location us-central1 \
  --format="value(state)"

# Check for errors
gcloud composer environments describe data-discovery-agent-composer \
  --location us-central1 \
  --format="value(config.softwareConfig.airflowConfigOverrides)"
```

If stuck for > 45 minutes:
1. Check GCP Console for detailed error messages
2. Verify quota limits (Composer, GKE nodes)
3. Try destroying and recreating: `terraform destroy` then `terraform apply`

#### 3. **DAG Import Errors: ModuleNotFoundError**

**Error**: `No module named 'data_discovery_agent'`

**Solution**:
```bash
# Verify .airflowignore is uploaded
gsutil cat $COMPOSER_BUCKET/.airflowignore

# Re-upload source code
gsutil -m cp -r src/data_discovery_agent $COMPOSER_BUCKET/src/

# Re-upload DAG
gsutil cp dags/metadata_collection_dag.py $COMPOSER_BUCKET/

# Wait for Airflow to re-scan
sleep 30
```

#### 4. **Permission Denied Errors in DAG Execution**

**Error**: `403 Permission 'X.Y.Z' denied`

**Solution**:
```bash
# Re-apply IAM permissions
cd terraform
terraform apply -target=google_project_iam_member.composer_*

# Or re-apply all infrastructure
terraform apply
```

Check [ACLS.md](./ACLS.md) for detailed permission requirements.

#### 5. **Vertex AI Search Import Fails**

**Error**: `403 Permission 'discoveryengine.documents.import' denied`

**Solution**:
```bash
# Verify Discovery Engine role
gcloud projects get-iam-policy ${PROJECT_ID} \
  --flatten="bindings[].members" \
  --filter="bindings.members:data-discovery-composer@"

# If missing, re-apply Terraform
cd terraform
terraform apply -target=google_project_iam_member.composer_discoveryengine_editor
```

#### 6. **Lineage Tracking Not Working**

**Issue**: No lineage logs in Cloud Logging

**Solution**:
```bash
# 1. Verify lineage is enabled
grep LINEAGE .env

# 2. Verify Data Lineage API is enabled
gcloud services list --enabled | grep datalineage

# 3. Enable if needed
gcloud services enable datalineage.googleapis.com

# 4. Verify IAM permission
gcloud projects get-iam-policy ${PROJECT_ID} \
  --flatten="bindings[].members" \
  --filter="bindings.members:data-discovery-composer@" \
  --filter="bindings.role:roles/datalineage.admin"

# 5. Re-deploy pipeline code
gsutil -m cp -r src/data_discovery_agent $COMPOSER_BUCKET/src/
```

#### 7. **Composer Package Installation Fails**

**Error**: `ERROR: ResolutionImpossible` or `dependency conflict`

**Solution**:
```bash
# Check composer.tf for conflicting packages
cat terraform/composer.tf | grep pypi_packages -A 20

# Common conflicts:
# - google-adk requires sqlalchemy>=2.0
# - airflow 2.10.5 requires sqlalchemy<2.0
# Solution: Remove google-adk if not needed

# Apply updated Composer config
cd terraform
terraform apply -target=google_composer_environment.data_discovery_agent
```

#### 8. **BigQuery Table Not Found**

**Error**: `404 Not found: Table project:dataset.table`

**Solution**:
```bash
# Check if dataset exists
bq ls

# Create dataset manually if missing
bq mk --dataset \
  --location=US \
  --description="Data Discovery Metadata Storage" \
  ${PROJECT_ID}:data_discovery

# Re-run Terraform to create table
cd terraform
terraform apply -target=google_bigquery_table.discovered_assets
```

---

## Updating the Pipeline

### Updating DAG Code

```bash
# 1. Make changes to dags/metadata_collection_dag.py

# 2. Upload updated DAG
gsutil cp dags/metadata_collection_dag.py $COMPOSER_BUCKET/

# 3. Wait for Airflow to reload (automatic, ~30 seconds)
```

### Updating Source Code

```bash
# 1. Make changes to src/data_discovery_agent/

# 2. Upload updated code
gsutil -m cp -r src/data_discovery_agent $COMPOSER_BUCKET/src/

# 3. Verify upload
gsutil ls -r $COMPOSER_BUCKET/src/data_discovery_agent/

# 4. Clear any cached modules (if needed)
gcloud composer environments run data-discovery-agent-composer \
  --location us-central1 \
  tasks clear -- bigquery_metadata_collection --state '*'
```

### Updating Infrastructure

```bash
cd terraform

# 1. Make changes to .tf files

# 2. Review changes
terraform plan

# 3. Apply changes
terraform apply

# Note: Composer environment updates may take 10-20 minutes
```

### Updating Python Dependencies

```bash
# 1. Edit terraform/composer.tf - update pypi_packages

# 2. Apply changes
cd terraform
terraform apply -target=google_composer_environment.data_discovery_agent

# 3. Wait for Composer to rebuild environment (15-30 minutes)
gcloud composer environments describe data-discovery-agent-composer \
  --location us-central1 \
  --format="value(state)"
```

### Rolling Back Changes

```bash
# Option 1: Revert code changes
git revert HEAD
gsutil cp dags/metadata_collection_dag.py $COMPOSER_BUCKET/
gsutil -m cp -r src/data_discovery_agent $COMPOSER_BUCKET/src/

# Option 2: Restore from previous version in GCS
gsutil ls -a $COMPOSER_BUCKET/metadata_collection_dag.py
gsutil cp gs://...#<generation> $COMPOSER_BUCKET/metadata_collection_dag.py
```

---

## Scheduling and Automation

### Set Up Automatic DAG Schedule

The DAG is configured with a default schedule in `metadata_collection_dag.py`:

```python
schedule_interval='@daily',  # Run daily at midnight UTC
```

To customize:

1. Edit `dags/metadata_collection_dag.py`
2. Update `schedule_interval` to your preferred cron expression:
   - `'@hourly'` - Every hour
   - `'@daily'` - Daily at midnight
   - `'0 */6 * * *'` - Every 6 hours
   - `'0 2 * * *'` - Daily at 2 AM
   - `None` - Manual trigger only

3. Upload updated DAG:
   ```bash
   gsutil cp dags/metadata_collection_dag.py $COMPOSER_BUCKET/
   ```

### Enable/Disable DAG

```bash
# Pause DAG (stops scheduled runs)
gcloud composer environments run data-discovery-agent-composer \
  --location us-central1 \
  dags pause -- bigquery_metadata_collection

# Unpause DAG
gcloud composer environments run data-discovery-agent-composer \
  --location us-central1 \
  dags unpause -- bigquery_metadata_collection
```

---

## Monitoring and Alerting

### View DAG Metrics

Access Airflow metrics:
```bash
# Get Airflow Web UI URL
gcloud composer environments describe data-discovery-agent-composer \
  --location us-central1 \
  --format="value(config.airflowUri)"
```

Navigate to: **Browse → DAG Runs** or **Browse → Task Instances**

### Check Cloud Monitoring

1. Go to [Cloud Monitoring Console](https://console.cloud.google.com/monitoring)
2. Navigate to **Dashboards → Cloud Composer**
3. Select your environment: `data-discovery-agent-composer`

Key metrics to monitor:
- DAG run duration
- Task success rate
- Worker CPU/Memory usage
- Database connections

### Set Up Custom Alerts

Already configured via Terraform:
- GCS bucket size alerts
- Email notifications to `alert_email` in terraform.tfvars

To add custom alerts, edit `terraform/monitoring.tf`.

### View Lineage in Data Catalog

1. Go to [Data Catalog Console](https://console.cloud.google.com/datacatalog)
2. Search for your BigQuery table: `discovered_assets`
3. Click **Lineage** tab to visualize data flow

---

## Performance Tuning

### Scale Composer Environment

In `terraform.tfvars`:
```hcl
composer_environment_size = "ENVIRONMENT_SIZE_MEDIUM"  # or LARGE
```

Apply changes:
```bash
cd terraform
terraform apply
```

---

## Security Best Practices

1. **Never commit `.env` or `terraform.tfvars`** to version control
2. **Rotate service account keys** quarterly
3. **Review IAM permissions** regularly (see [ACLS.md](./ACLS.md))
4. **Enable VPC Service Controls** for production (see [Terraform VPC docs](https://cloud.google.com/vpc-service-controls))
5. **Use Secret Manager** for sensitive values (already configured in Terraform)
6. **Enable audit logging** (already enabled via `terraform/logging.tf`)

---

## Cost Optimization

### Estimated Monthly Costs

| Service | Configuration | Estimated Cost | Required |
|---------|--------------|----------------|----------|
| Cloud Composer | Small environment | $300-400/month | Yes |
| GCS Storage | ~10GB reports | $0.20/month | Yes |
| BigQuery Storage | ~1GB metadata | $0.02/month | Yes |
| BigQuery Queries | ~1000 queries/day | $5-10/month | Yes |
| Vertex AI Search | 100K searches/month | $50-100/month | Optional |
| **GKE Cluster** | 2 nodes (e2-standard-2) | **$123/month** | **No (Optional)** |

**Recommendation**: Start with `enable_gke = false` for a simpler, more cost-effective deployment.

### Cost Reduction Tips

1. **Disable GKE** (saves ~$123/month):
   ```hcl
   # In terraform.tfvars
   enable_gke = false
   ```
   All workflows run on Cloud Composer without needing GKE.

2. **Use Composer Autopilot** (currently in preview):
   ```hcl
   # In terraform/composer.tf (when available)
   composer_environment_size = "AUTOPILOT"
   ```

3. **Reduce Composer environment size** if workload is light:
   ```hcl
   composer_environment_size = "ENVIRONMENT_SIZE_SMALL"
   ```

4. **Set GCS lifecycle policies** for old reports:
   ```bash
   # Delete reports older than 90 days
   gsutil lifecycle set lifecycle-config.json gs://${PROJECT_ID}-data-discovery-reports
   ```

5. **Pause Composer when not needed**:
   ```bash
   # Stop scheduled runs
   gcloud composer environments run data-discovery-agent-composer \
     --location us-central1 \
     dags pause -- bigquery_metadata_collection
   ```

6. **Use committed use discounts** for Composer (and GKE if enabled)

---

## Next Steps

After successful deployment:

1. ✅ **Review the architecture**: See [ARCHITECTURE.md](./ARCHITECTURE.md)
2. ✅ **Understand the permissions**: See [ACLS.md](./ACLS.md)
3. ✅ **Set up the MCP service**: Follow Phase 4 in the project plan
4. ✅ **Build a local CLI**: For testing indexer jobs independently
5. ✅ **Add custom metadata enrichment**: Extend collectors for your specific needs
6. ✅ **Integrate with BI tools**: Query Vertex AI Search from Looker, Tableau, etc.

---

## Support and Resources

### Documentation

- [Architecture Overview](./ARCHITECTURE.md)
- [Access Control Lists](./ACLS.md)
- [Lineage Tracking Rule](./.cursor/rules/bigquery-lineage-tracking.mdc)
- [Project Plan](../.cursor/plans/bigquery-discovery-mcp-beb6d83e.plan.md)

### Google Cloud Documentation

- [Cloud Composer](https://cloud.google.com/composer/docs)
- [Vertex AI Search](https://cloud.google.com/generative-ai-app-builder/docs)
- [Data Catalog Lineage](https://cloud.google.com/data-catalog/docs/how-to/lineage)
- [Terraform GCP Provider](https://registry.terraform.io/providers/hashicorp/google/latest/docs)

### Troubleshooting Commands

```bash
# Quick health check
./scripts/health-check.sh  # (create this for convenience)

# Or manually:
echo "=== Composer Status ==="
gcloud composer environments describe data-discovery-agent-composer --location us-central1 --format="value(state)"

echo "=== DAG Status ==="
gcloud composer environments run data-discovery-agent-composer --location us-central1 dags list

echo "=== Recent Logs ==="
gcloud logging read 'resource.type="cloud_composer_environment"' --limit 10

echo "=== BigQuery Data ==="
bq query --use_legacy_sql=false 'SELECT COUNT(*) FROM `'${PROJECT_ID}'.data_discovery.discovered_assets`'
```

---

**Last Updated**: October 20, 2025  
**Maintained By**: Sam Silverberg  
**Estimated Setup Time**: 
- Simple setup (Composer-only, `enable_gke = false`): 1-1.5 hours
- Full setup (with GKE, `enable_gke = true`): 1.5-2 hours

**Recommendation**: Start with the simple Composer-only deployment for easier operations and lower costs.

For issues or questions, refer to the troubleshooting section or review the Cloud Logging for detailed error messages.

