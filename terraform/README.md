# Data Discovery Agent - Terraform Infrastructure

This directory contains Terraform configuration for deploying the Data Discovery Agent infrastructure on Google Cloud Platform (GCP).

## Architecture Overview

The infrastructure includes:
- **GKE Cluster**: Standard mode cluster with Workload Identity, private nodes (no external IPs)
- **GCS Buckets**: Regional buckets for JSONL files (Vertex AI Search) and Markdown reports
- **Service Accounts**: Least-privilege accounts for discovery (read-only) and metadata writes
- **Monitoring**: Cloud Monitoring dashboards and alerts
- **Secrets**: Secret Manager for sensitive configuration

## Prerequisites

1. **GCP Project**: Active GCP project (`lennyisagoodboy`)
2. **Terraform**: Version >= 1.5.0
3. **gcloud CLI**: Authenticated and configured
4. **Permissions**: Owner or Editor role on the project (for initial setup)
5. **Existing Network**: VPC and subnet already configured
   - Network: `projects/hazel-goal-319318/global/networks/ula`
   - Subnet: `projects/hazel-goal-319318/regions/us-central1/subnetworks/ula`

## Quick Start

### 1. Configure Variables

Copy the example variables file and customize:

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars if you need to change any defaults
```

### 2. Initialize Terraform

```bash
terraform init
```

### 3. Review the Plan

```bash
terraform plan
```

This will show you all resources that will be created.

### 4. Apply Configuration

```bash
terraform apply
```

Review the changes and type `yes` to proceed. This will:
- Enable required GCP APIs
- Create the GKE cluster with 2 nodes (can scale to 5)
- Create GCS buckets for JSONL and reports
- Create service accounts with appropriate IAM roles
- Configure Workload Identity bindings
- Set up monitoring and logging

### 5. Connect to the Cluster

After Terraform completes, connect to your GKE cluster:

```bash
gcloud container clusters get-credentials data-discovery-cluster \
  --region us-central1 \
  --project lennyisagoodboy
```

Verify the connection:

```bash
kubectl get nodes
```

## Infrastructure Components

### GKE Cluster

- **Name**: `data-discovery-cluster`
- **Location**: Regional (`us-central1`)
- **Mode**: Standard (not Autopilot)
- **Machine Type**: `e2-standard-2` (2 vCPU, 8 GB RAM)
- **Nodes**: 2 initial, autoscaling 1-5
- **Network**: Private cluster (no external IPs on nodes)
- **Workload Identity**: Enabled for secure GCP API access
- **Features**: Shielded nodes, auto-repair, auto-upgrade

### GCS Buckets

#### JSONL Bucket
- **Name**: `lennyisagoodboy-data-discovery-jsonl`
- **Purpose**: Store JSONL files for Vertex AI Search ingestion
- **Location**: Regional (`us-central1`)
- **Lifecycle**: Nearline after 30 days, delete after 90 days
- **Access**: Discovery SA (write), Vertex AI SA (read)

#### Reports Bucket
- **Name**: `lennyisagoodboy-data-discovery-reports`
- **Purpose**: Store Markdown reports for human consumption
- **Location**: Regional (`us-central1`)
- **Lifecycle**: Nearline after 60 days, delete after 180 days
- **Access**: Discovery SA (write), project viewers (read)

### Service Accounts

#### 1. Discovery Service Account (Read-Only)
- **Email**: `data-discovery-agent@lennyisagoodboy.iam.gserviceaccount.com`
- **Purpose**: All data discovery and indexing operations
- **Permissions**:
  - `roles/bigquery.metadataViewer` - Read BigQuery metadata
  - `roles/bigquery.jobUser` - Run queries (read-only)
  - `roles/datacatalog.viewer` - Read Data Catalog
  - `roles/logging.viewer` - Read audit logs
  - `roles/logging.privateLogViewer` - Read private logs
  - `roles/dlp.reader` - Read DLP findings
  - `roles/aiplatform.user` - Query Vertex AI Search
  - `roles/dataplex.viewer` - **GenAI Toolbox**: Read Dataplex resources
  - `roles/dataplex.metadataReader` - **GenAI Toolbox**: Read lineage and data quality
- **Workload Identity**: Bound to K8s SA `discovery-agent` in namespace `data-discovery`

> **Note**: Looker permissions are disabled by default. Uncomment in `service-accounts.tf` if needed.

#### 2. Metadata Write Service Account
- **Email**: `data-discovery-metadata@lennyisagoodboy.iam.gserviceaccount.com`
- **Purpose**: Write enriched metadata to Data Catalog only (SR-2A compliant)
- **Permissions**:
  - `roles/datacatalog.entryGroupOwner` - Write to Data Catalog
  - `roles/datacatalog.viewer` - Read for verification
  - `roles/logging.logWriter` - Audit trail
- **Workload Identity**: Bound to K8s SA `metadata-writer` in namespace `data-discovery`

#### 3. GKE Service Account
- **Email**: `data-discovery-gke@lennyisagoodboy.iam.gserviceaccount.com`
- **Purpose**: GKE node operations
- **Permissions**: Logging and monitoring only

## Workload Identity Setup

After creating the cluster, you need to set up Kubernetes service accounts:

```bash
# Create namespace
kubectl create namespace data-discovery

# Create Kubernetes service accounts
kubectl create serviceaccount discovery-agent -n data-discovery
kubectl create serviceaccount metadata-writer -n data-discovery

# Annotate with GCP service account emails
kubectl annotate serviceaccount discovery-agent -n data-discovery \
  iam.gke.io/gcp-service-account=data-discovery-agent@lennyisagoodboy.iam.gserviceaccount.com

kubectl annotate serviceaccount metadata-writer -n data-discovery \
  iam.gke.io/gcp-service-account=data-discovery-metadata@lennyisagoodboy.iam.gserviceaccount.com
```

## Security Notes

### SR-2A Compliance: Read-Only by Design

This infrastructure enforces **read-only operations** on data sources:

✅ **Allowed**:
- Reading BigQuery metadata (schemas, tables, views)
- Running read-only queries (SELECT only)
- Reading Data Catalog entries
- Analyzing audit logs
- Writing to Data Catalog (metadata only)
- Writing to GCS buckets (JSONL, reports)

❌ **Prohibited**:
- Creating/modifying/deleting BigQuery tables
- Running DDL/DML operations
- Modifying IAM policies automatically
- Any source data modifications

### Private Cluster

The GKE cluster uses private nodes (no external IPs) for enhanced security:
- Nodes communicate with GCP APIs via Private Google Access
- Master endpoint is still accessible (set `enable_private_endpoint = true` for full private)
- Adjust `master_authorized_networks_config` in `main.tf` to restrict master access

### Least Privilege

Each service account has minimal permissions required for its function. No service account has owner or editor roles.

## Monitoring and Logging

### Logs

View logs in Cloud Console:
- **GKE logs**: Navigation > Kubernetes Engine > Workloads
- **Audit logs**: Navigation > Logging > Logs Explorer
- **Bucket logs**: Stored in reports bucket via log sink

### Alerts

Configure alerts by:
1. Update email in `monitoring.tf` (search for `alerts@example.com`)
2. Set `enabled = true` in notification channel and alert policies
3. Run `terraform apply`

## Cost Estimation

Estimated monthly costs (us-central1):

- **GKE Cluster**:
  - Management fee: $73/month
  - 2x e2-standard-2 nodes: ~$50/month
  - **Total GKE**: ~$123/month

- **GCS Buckets**:
  - Storage: $0.02/GB/month (regional)
  - Operations: Minimal for periodic writes
  - **Estimated**: ~$5-20/month (depends on data volume)

- **Vertex AI Search**: Not included (deployed separately)

**Total Estimated Cost**: ~$130-150/month for dev environment

> Scale up/down by adjusting `max_node_count` in `variables.tf`

## Terraform Commands

```bash
# Initialize
terraform init

# Format code
terraform fmt

# Validate configuration
terraform validate

# Plan changes
terraform plan

# Apply changes
terraform apply

# Show current state
terraform show

# List resources
terraform state list

# Destroy infrastructure (careful!)
terraform destroy
```

## Outputs

After applying, Terraform provides useful outputs:

```bash
# View all outputs
terraform output

# Get kubectl connection command
terraform output kubectl_connection_command

# Get service account emails
terraform output discovery_service_account_email
terraform output metadata_write_service_account_email
```

## Troubleshooting

### API Not Enabled

If you see errors about APIs not being enabled, wait a few minutes after the first apply and try again. API enablement can take time to propagate.

### Network Not Found

Ensure the network and subnet paths are correct:
- Network: `projects/hazel-goal-319318/global/networks/ula`
- Subnet: `projects/hazel-goal-319318/regions/us-central1/subnetworks/ula`

### Workload Identity Issues

If pods can't access GCP APIs:
1. Verify K8s service accounts are created and annotated
2. Check IAM bindings: `gcloud iam service-accounts get-iam-policy <sa-email>`
3. Ensure pod spec uses correct K8s service account

### Bucket Name Conflicts

If bucket names are taken, change them in `terraform.tfvars`.

## Next Steps

After infrastructure is deployed:

1. **Deploy GenAI Toolbox** (Phase 0.2): Follow `../scripts/deploy-genai-toolbox.sh`
2. **Configure Vertex AI Search** (Phase 1): Create data store manually or via SDK
3. **Deploy Discovery Agents** (Phase 2): Build Docker images and deploy to GKE
4. **Set up Cloud Scheduler** (Phase 2): Schedule background indexing jobs

## Cleanup

To destroy all infrastructure:

```bash
terraform destroy
```

⚠️ **Warning**: This will delete:
- GKE cluster and all workloads
- GCS buckets (if `force_destroy = true`)
- Service accounts
- All data in buckets

Backup any important data first!

## Support

For issues or questions:
1. Check Terraform logs: `terraform apply -debug`
2. Check GCP Console for resource status
3. Review [ARCHITECTURE.md](../docs/ARCHITECTURE.md) for system design
4. Review [bigquery-discovery-system.plan.md](.cursor/plans/bigquery-discovery-system-217d0748.plan.md) for implementation details

