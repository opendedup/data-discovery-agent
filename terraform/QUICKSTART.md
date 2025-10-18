# Phase 0 Infrastructure - Quick Start Guide

## 🚀 One-Command Deploy

```bash
./scripts/setup-infrastructure.sh
```

This script will:
1. ✓ Check prerequisites (gcloud, terraform, kubectl)
2. ✓ Create terraform.tfvars
3. ✓ Initialize Terraform
4. ✓ Plan and apply infrastructure
5. ✓ Configure kubectl
6. ✓ Set up Workload Identity

**Estimated time**: 10-15 minutes

---

## 📋 Prerequisites

| Tool | Required Version | Install Command |
|------|-----------------|----------------|
| `terraform` | >= 1.5.0 | [Install Guide](https://developer.hashicorp.com/terraform/downloads) |
| `gcloud` | Latest | [Install Guide](https://cloud.google.com/sdk/docs/install) |
| `kubectl` | Latest | `gcloud components install kubectl` |

### Authentication

```bash
# Login to GCP
gcloud auth login

# Set project
gcloud config set project lennyisagoodboy

# Configure application default credentials
gcloud auth application-default login
```

---

## 🏗️ What Gets Created

### GKE Cluster
- **Name**: `data-discovery-cluster`
- **Region**: `us-central1` (3 zones)
- **Mode**: Standard (not Autopilot)
- **Nodes**: 2x `e2-standard-2` (2 vCPU, 8 GB RAM each)
- **Scaling**: 1-5 nodes (autoscaling enabled)
- **Network**: Private cluster (no external IPs)
- **Cost**: ~$123/month

### GCS Buckets
- **JSONL**: `lennyisagoodboy-data-discovery-jsonl` (for Vertex AI Search)
- **Reports**: `lennyisagoodboy-data-discovery-reports` (for human docs)
- **Location**: Regional (`us-central1`)
- **Cost**: ~$5-20/month (depends on data volume)

### Service Accounts
1. **discovery-agent**: Read-only data discovery (BigQuery, Data Catalog, Logging)
2. **metadata-writer**: Write to Data Catalog only (SR-2A compliant)
3. **gke-service**: GKE node operations

---

## 🔧 Manual Deployment Steps

If you prefer step-by-step control:

### 1. Create Configuration

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit if needed (defaults are pre-configured)
```

### 2. Initialize Terraform

```bash
terraform init
```

### 3. Review Plan

```bash
terraform plan
```

### 4. Deploy

```bash
terraform apply
```

Type `yes` when prompted. Wait ~10 minutes for cluster creation.

### 5. Configure kubectl

```bash
gcloud container clusters get-credentials data-discovery-cluster \
  --region us-central1 \
  --project lennyisagoodboy
```

### 6. Set up Workload Identity

```bash
# Create namespace
kubectl create namespace data-discovery

# Create K8s service accounts
kubectl create serviceaccount discovery-agent -n data-discovery
kubectl create serviceaccount metadata-writer -n data-discovery

# Annotate with GCP service accounts
kubectl annotate serviceaccount discovery-agent -n data-discovery \
  iam.gke.io/gcp-service-account=data-discovery-agent@lennyisagoodboy.iam.gserviceaccount.com

kubectl annotate serviceaccount metadata-writer -n data-discovery \
  iam.gke.io/gcp-service-account=data-discovery-metadata@lennyisagoodboy.iam.gserviceaccount.com
```

---

## ✅ Validate Deployment

```bash
./scripts/validate-setup.sh
```

This checks:
- ✓ GKE cluster is running
- ✓ Workload Identity is configured
- ✓ GCS buckets exist
- ✓ Service accounts have correct IAM roles
- ✓ Kubernetes resources are created
- ✓ Required APIs are enabled

---

## 🔍 Verify Resources

### Check Cluster

```bash
kubectl get nodes
kubectl get namespaces
kubectl get serviceaccounts -n data-discovery
```

### Check Buckets

```bash
gsutil ls -L gs://lennyisagoodboy-data-discovery-jsonl
gsutil ls -L gs://lennyisagoodboy-data-discovery-reports
```

### Check Service Accounts

```bash
gcloud iam service-accounts list --project=lennyisagoodboy
```

### Test Workload Identity

```bash
kubectl run -it --rm --restart=Never test-pod \
  --serviceaccount=discovery-agent \
  --namespace=data-discovery \
  --image=google/cloud-sdk:slim \
  -- gcloud auth list
```

Expected output: `data-discovery-agent@lennyisagoodboy.iam.gserviceaccount.com`

---

## 📊 View Terraform Outputs

```bash
cd terraform
terraform output
```

Key outputs:
- `cluster_endpoint`: GKE API server endpoint
- `jsonl_bucket_name`: Bucket for Vertex AI Search
- `reports_bucket_name`: Bucket for reports
- `discovery_service_account_email`: Discovery SA email
- `kubectl_connection_command`: Command to connect kubectl

---

## 🛠️ Troubleshooting

### "API not enabled" errors

Wait 2-3 minutes after first apply, then retry:

```bash
terraform apply
```

APIs take time to propagate after enablement.

### "Network not found"

Verify network paths in `terraform.tfvars`:
- Network: `projects/hazel-goal-319318/global/networks/ula`
- Subnet: `projects/hazel-goal-319318/regions/us-central1/subnetworks/ula`

### Workload Identity not working

1. Check annotations:
```bash
kubectl get sa discovery-agent -n data-discovery -o yaml
```

2. Verify IAM binding:
```bash
gcloud iam service-accounts get-iam-policy \
  data-discovery-agent@lennyisagoodboy.iam.gserviceaccount.com
```

Should show `roles/iam.workloadIdentityUser` for K8s SA.

### Can't connect to cluster

```bash
# Re-authenticate
gcloud auth login
gcloud auth application-default login

# Reconnect to cluster
gcloud container clusters get-credentials data-discovery-cluster \
  --region us-central1 \
  --project lennyisagoodboy
```

---

## 🔄 Update Infrastructure

To modify resources:

1. Edit `terraform.tfvars`
2. Run `terraform plan` to review changes
3. Run `terraform apply` to apply

Example: Scale node pool

```bash
# Edit terraform.tfvars
max_node_count = 10

# Apply changes
terraform plan
terraform apply
```

---

## 🗑️ Destroy Infrastructure

**⚠️ WARNING**: This deletes everything!

```bash
./scripts/teardown.sh
```

Or manually:

```bash
cd terraform
terraform destroy
```

You'll need to type the project ID and "destroy" to confirm.

---

## 📖 Next Steps

After Phase 0 is complete:

1. **Phase 0.2**: Deploy GenAI Toolbox (coming next)
2. **Phase 1**: Set up Vertex AI Search data store
3. **Phase 2**: Build and deploy discovery agents
4. **Phase 3**: Implement Smart Query Router

See [README.md](README.md) for full documentation.

---

## 💰 Cost Breakdown

| Resource | Monthly Cost (USD) |
|----------|-------------------|
| GKE Management Fee | $73 |
| 2x e2-standard-2 nodes | $50 |
| GCS Storage (JSONL) | $5-10 |
| GCS Storage (Reports) | $5-10 |
| **Total** | **~$130-150** |

> Costs are for `us-central1` region, dev environment, light usage

To reduce costs:
- Scale down nodes: `min_node_count = 0, max_node_count = 2`
- Use preemptible nodes (not included in this config)
- Delete unused resources with `terraform destroy`

---

## 🔐 Security Notes

- **Private Cluster**: Nodes have no external IPs
- **Workload Identity**: Secure GCP API access without keys
- **Least Privilege**: Service accounts have minimal required permissions
- **Read-Only**: Discovery SA cannot modify source data (SR-2A compliant)
- **Audit Logs**: All operations are logged

---

## 📞 Support

- **Terraform Issues**: Check `terraform/README.md`
- **GCP Issues**: Run `./scripts/validate-setup.sh` for diagnostics
- **Architecture**: See `docs/ARCHITECTURE.md`
- **Full Plan**: See `.cursor/plans/bigquery-discovery-system-217d0748.plan.md`

