# Artifact Registry Setup Summary

## ✅ Terraform Configuration Added

I've added Artifact Registry to your GCP infrastructure with complete Terraform configuration!

### What Was Created

#### 1. Terraform Resources (`terraform/artifact-registry.tf`)
- **Artifact Registry Repository** for Docker images
- **IAM Permissions** for GKE, Composer, and Discovery service accounts
- **Cleanup Policies** for automatic image management

#### 2. Variables (`terraform/variables.tf`)
- `artifact_registry_location` - Location for the repository (default: us-central1)
- `artifact_registry_repository_id` - Repository name (default: data-discovery)
- `artifact_registry_retention_days` - Days to keep untagged images (default: 30)
- `artifact_registry_keep_count` - Number of versions to keep (default: 10)

#### 3. Outputs (`terraform/outputs.tf`)
- `artifact_registry_repository` - Full repository name
- `artifact_registry_location` - Repository location
- `artifact_registry_url` - Full URL for pushing/pulling
- `docker_push_command_example` - Ready-to-run push command

#### 4. Helper Script (`scripts/push-to-artifact-registry.sh`)
Automated script that:
- Configures Docker authentication
- Builds your MCP image
- Tags it for Artifact Registry
- Pushes to the repository

#### 5. Documentation
- `terraform/ARTIFACT_REGISTRY.md` - Complete setup and usage guide
- `terraform/terraform.tfvars.example` - Updated with AR variables

## 🚀 How to Deploy

### Step 1: Update Your terraform.tfvars

Add these variables (or keep the defaults):

\`\`\`hcl
# Artifact Registry Configuration
artifact_registry_location       = "us-central1"
artifact_registry_repository_id  = "data-discovery"
artifact_registry_retention_days = 30
artifact_registry_keep_count     = 10
\`\`\`

### Step 2: Apply Terraform

\`\`\`bash
cd terraform/

# Initialize (if needed)
terraform init

# Review changes
terraform plan

# Apply configuration
terraform apply
\`\`\`

This will create:
- Artifact Registry repository
- IAM bindings for service accounts
- Cleanup policies

### Step 3: Get Repository URL

\`\`\`bash
terraform output artifact_registry_url
\`\`\`

Example output:
\`\`\`
us-central1-docker.pkg.dev/lennyisagoodboy/data-discovery
\`\`\`

## 📦 Pushing Your First Image

### Option 1: Using the Helper Script (Easiest)

\`\`\`bash
# Push with latest tag
./scripts/push-to-artifact-registry.sh

# Or push with version
./scripts/push-to-artifact-registry.sh v1.0.0
\`\`\`

### Option 2: Manual Steps

\`\`\`bash
# 1. Configure Docker auth
gcloud auth configure-docker us-central1-docker.pkg.dev

# 2. Build image (already done!)
# docker build -t data-discovery-mcp:latest .

# 3. Tag for Artifact Registry
docker tag data-discovery-mcp:latest \
  us-central1-docker.pkg.dev/lennyisagoodboy/data-discovery/mcp:latest

# 4. Push
docker push us-central1-docker.pkg.dev/lennyisagoodboy/data-discovery/mcp:latest
\`\`\`

### Option 3: Get Command from Terraform

\`\`\`bash
terraform output docker_push_command_example
\`\`\`

Copy and run the output!

## 🔐 IAM Permissions (Auto-Configured)

The Terraform automatically configures these permissions:

| Service Account | Role | Purpose |
|----------------|------|---------|
| GKE SA | `artifactregistry.reader` | Pull images to GKE nodes |
| Composer SA | `artifactregistry.reader` | Pull images for Composer |
| Discovery SA | `artifactregistry.writer` | Push images from CI/CD |

## 📋 Cleanup Policies (Auto-Configured)

1. **Delete Untagged Images**: After 30 days (configurable)
2. **Keep Recent Versions**: Keep 10 most recent (configurable)

These help control costs and keep your repository clean.

## 🎯 Next Steps

### 1. Apply Terraform (Now!)

\`\`\`bash
cd terraform/
terraform apply
\`\`\`

### 2. Push Your Image

\`\`\`bash
./scripts/push-to-artifact-registry.sh
\`\`\`

### 3. Update Kubernetes Manifests

Update `k8s/deployment.yaml` to use Artifact Registry:

\`\`\`yaml
spec:
  containers:
  - name: mcp
    image: us-central1-docker.pkg.dev/lennyisagoodboy/data-discovery/mcp:latest
    imagePullPolicy: Always
\`\`\`

### 4. Deploy to GKE

\`\`\`bash
kubectl apply -f k8s/
\`\`\`

## 💰 Cost Estimates

**Artifact Registry Pricing:**
- Storage: $0.10/GB/month
- Network egress: Varies by region

**Typical costs for this project:**
- ~500MB image × 10 versions = 5GB
- **~$0.50/month** for storage
- Minimal egress within same region

## 📊 Verification

After applying, verify everything:

\`\`\`bash
# List repositories
gcloud artifacts repositories list --location=us-central1

# View repository details
gcloud artifacts repositories describe data-discovery --location=us-central1

# Check IAM permissions
gcloud artifacts repositories get-iam-policy data-discovery --location=us-central1

# View Terraform outputs
terraform output
\`\`\`

## 🛠️ Management Commands

\`\`\`bash
# List all images
gcloud artifacts docker images list \
  us-central1-docker.pkg.dev/lennyisagoodboy/data-discovery

# List tags for mcp image
gcloud artifacts docker tags list \
  us-central1-docker.pkg.dev/lennyisagoodboy/data-discovery/mcp

# Delete an old version
gcloud artifacts docker images delete \
  us-central1-docker.pkg.dev/lennyisagoodboy/data-discovery/mcp:old-tag
\`\`\`

## 📚 Documentation

- **Full Setup Guide**: `terraform/ARTIFACT_REGISTRY.md`
- **Docker Deployment**: `docs/DOCKER_DEPLOYMENT.md`
- **Terraform Config**: `terraform/artifact-registry.tf`
- **Variables**: `terraform/variables.tf`

## ✨ Features

✅ **Automatic IAM Configuration** - Service accounts get correct permissions
✅ **Cleanup Policies** - Auto-delete old/untagged images
✅ **Helper Scripts** - One command to build and push
✅ **Terraform Outputs** - Get URLs and commands easily
✅ **Multi-Environment Support** - Tag images by environment
✅ **Cost Optimization** - Retention policies control costs
✅ **Security** - Minimal required permissions only

## 🎉 Ready!

Your Artifact Registry is fully configured and ready to use!

\`\`\`bash
# Deploy it now:
cd terraform && terraform apply

# Then push your image:
cd .. && ./scripts/push-to-artifact-registry.sh
\`\`\`

---

**Created**: $(date)
**Status**: ✅ Ready to Deploy
**Action Required**: Run \`terraform apply\`
