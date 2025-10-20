# Artifact Registry Setup

This document describes the Artifact Registry setup for the Data Discovery MCP service.

## Overview

The Terraform configuration automatically creates an Artifact Registry repository for storing Docker images of the MCP service.

## What's Created

### Repository

- **Location**: Configurable (default: `us-central1`)
- **Repository ID**: Configurable (default: `data-discovery`)
- **Format**: Docker
- **Full Path**: `{location}-docker.pkg.dev/{project-id}/data-discovery`

### Cleanup Policies

The repository includes automatic cleanup policies:

1. **Delete Untagged Images**: Removes untagged images older than 30 days (configurable)
2. **Keep Recent Versions**: Retains the 10 most recent versions (configurable)

### IAM Permissions

The following service accounts are automatically granted access:

- **GKE Service Account**: `artifactregistry.reader` (pull images)
- **Composer Service Account**: `artifactregistry.reader` (pull images)
- **Discovery Service Account**: `artifactregistry.writer` (push images)

## Configuration Variables

Add these to your `terraform.tfvars`:

```hcl
# Artifact Registry Configuration
artifact_registry_location       = "us-central1"
artifact_registry_repository_id  = "data-discovery"
artifact_registry_retention_days = 30  # Days to keep untagged images
artifact_registry_keep_count     = 10  # Number of recent versions to keep
```

## Deployment

### 1. Apply Terraform Configuration

```bash
cd terraform/
terraform init
terraform plan
terraform apply
```

### 2. Get Artifact Registry URL

After applying, Terraform will output the repository URL:

```bash
terraform output artifact_registry_url
```

Example output:
```
us-central1-docker.pkg.dev/your-project-id/data-discovery
```

## Pushing Images

### Option 1: Using the Helper Script (Recommended)

```bash
# Push with version tag
./scripts/push-to-artifact-registry.sh v1.0.0

# Push as latest
./scripts/push-to-artifact-registry.sh latest

# Or just run (defaults to latest)
./scripts/push-to-artifact-registry.sh
```

The script automatically:
1. Configures Docker authentication
2. Builds the image
3. Tags it appropriately
4. Pushes to Artifact Registry

### Option 2: Manual Commands

```bash
# 1. Configure Docker authentication
gcloud auth configure-docker us-central1-docker.pkg.dev

# 2. Build image
docker build -t data-discovery-mcp:latest .

# 3. Tag for Artifact Registry
docker tag data-discovery-mcp:latest \
  us-central1-docker.pkg.dev/your-project-id/data-discovery/mcp:latest

# 4. Push to Artifact Registry
docker push us-central1-docker.pkg.dev/your-project-id/data-discovery/mcp:latest
```

### Option 3: Use Terraform Output

```bash
# Get the exact push command from Terraform
terraform output docker_push_command_example

# Copy and run the output
```

## Pulling Images

### From GKE (Automatic)

GKE nodes can automatically pull images if the GKE service account has the `artifactregistry.reader` role (automatically configured by Terraform).

No additional configuration needed in your Kubernetes manifests:

```yaml
spec:
  containers:
  - name: mcp
    image: us-central1-docker.pkg.dev/your-project-id/data-discovery/mcp:latest
```

### From Local Machine

```bash
# Configure authentication
gcloud auth configure-docker us-central1-docker.pkg.dev

# Pull image
docker pull us-central1-docker.pkg.dev/your-project-id/data-discovery/mcp:latest
```

### From Cloud Build

Cloud Build can automatically access Artifact Registry in the same project. No additional configuration needed.

### From Other GCP Projects

Grant the service account from the other project the `artifactregistry.reader` role:

```bash
gcloud artifacts repositories add-iam-policy-binding data-discovery \
  --location=us-central1 \
  --member="serviceAccount:external-sa@other-project.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.reader"
```

## Versioning Strategy

### Recommended Tagging Convention

```bash
# Production releases
us-central1-docker.pkg.dev/project/data-discovery/mcp:v1.0.0
us-central1-docker.pkg.dev/project/data-discovery/mcp:v1.0.1

# Environment tags
us-central1-docker.pkg.dev/project/data-discovery/mcp:prod
us-central1-docker.pkg.dev/project/data-discovery/mcp:staging
us-central1-docker.pkg.dev/project/data-discovery/mcp:dev

# Git commit SHA (for CI/CD)
us-central1-docker.pkg.dev/project/data-discovery/mcp:sha-abc1234

# Latest (always points to most recent)
us-central1-docker.pkg.dev/project/data-discovery/mcp:latest
```

### CI/CD Integration

Example GitHub Actions workflow:

```yaml
- name: Build and Push to Artifact Registry
  run: |
    gcloud auth configure-docker us-central1-docker.pkg.dev
    
    docker build -t data-discovery-mcp:${{ github.sha }} .
    
    docker tag data-discovery-mcp:${{ github.sha }} \
      us-central1-docker.pkg.dev/${{ secrets.GCP_PROJECT_ID }}/data-discovery/mcp:${{ github.sha }}
    
    docker tag data-discovery-mcp:${{ github.sha }} \
      us-central1-docker.pkg.dev/${{ secrets.GCP_PROJECT_ID }}/data-discovery/mcp:latest
    
    docker push us-central1-docker.pkg.dev/${{ secrets.GCP_PROJECT_ID }}/data-discovery/mcp:${{ github.sha }}
    docker push us-central1-docker.pkg.dev/${{ secrets.GCP_PROJECT_ID }}/data-discovery/mcp:latest
```

## Managing Images

### List Images

```bash
gcloud artifacts docker images list \
  us-central1-docker.pkg.dev/your-project-id/data-discovery
```

### List Tags for an Image

```bash
gcloud artifacts docker tags list \
  us-central1-docker.pkg.dev/your-project-id/data-discovery/mcp
```

### Delete an Image

```bash
gcloud artifacts docker images delete \
  us-central1-docker.pkg.dev/your-project-id/data-discovery/mcp:v1.0.0 \
  --delete-tags
```

### View Repository Details

```bash
gcloud artifacts repositories describe data-discovery \
  --location=us-central1
```

## Cleanup Policies

### View Current Policies

```bash
gcloud artifacts repositories describe data-discovery \
  --location=us-central1 \
  --format="yaml(cleanupPolicies)"
```

### Modify Retention Period

Update `artifact_registry_retention_days` in `terraform.tfvars` and reapply:

```hcl
artifact_registry_retention_days = 60  # Keep untagged images for 60 days
```

```bash
terraform apply
```

## Cost Optimization

### Storage Costs

Artifact Registry charges for:
- Storage ($0.10/GB/month)
- Network egress (varies by region)

### Tips to Reduce Costs

1. **Enable cleanup policies** (already configured)
2. **Use specific tags** instead of pushing every commit as `:latest`
3. **Delete old images** that are no longer needed
4. **Use regional locations** close to your compute resources

### Estimate Costs

```bash
# Get total storage used
gcloud artifacts repositories list \
  --location=us-central1 \
  --format="table(name,sizeBytes)"
```

## Troubleshooting

### Authentication Issues

```bash
# Reconfigure Docker auth
gcloud auth configure-docker us-central1-docker.pkg.dev

# Or use application default credentials
gcloud auth application-default login
```

### Permission Denied

Ensure your account or service account has the required roles:

```bash
# Grant yourself artifact registry admin
gcloud projects add-iam-policy-binding your-project-id \
  --member="user:your-email@example.com" \
  --role="roles/artifactregistry.admin"
```

### Cannot Pull from GKE

Verify the GKE service account has reader access:

```bash
gcloud artifacts repositories get-iam-policy data-discovery \
  --location=us-central1
```

### Repository Not Found

Ensure the repository was created by Terraform:

```bash
# List repositories
gcloud artifacts repositories list --location=us-central1

# If missing, apply Terraform
cd terraform/
terraform apply
```

## Terraform Outputs

After applying Terraform, you can view useful outputs:

```bash
# Repository URL
terraform output artifact_registry_url

# Example push command
terraform output docker_push_command_example

# Repository name
terraform output artifact_registry_repository

# Location
terraform output artifact_registry_location
```

## Integration with Kubernetes

Update your Kubernetes deployment to use the Artifact Registry image:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: data-discovery-mcp
spec:
  replicas: 2
  selector:
    matchLabels:
      app: data-discovery-mcp
  template:
    metadata:
      labels:
        app: data-discovery-mcp
    spec:
      serviceAccountName: data-discovery-mcp  # Must have workload identity configured
      containers:
      - name: mcp
        image: us-central1-docker.pkg.dev/your-project-id/data-discovery/mcp:latest
        imagePullPolicy: Always  # Or IfNotPresent for production
        ports:
        - containerPort: 8080
        env:
        - name: GCP_PROJECT_ID
          value: "your-project-id"
        # ... other env vars
```

## Security Best Practices

1. **Use specific version tags** in production (not `:latest`)
2. **Scan images for vulnerabilities** using Artifact Analysis
3. **Enable Binary Authorization** for deployment policies
4. **Use minimal IAM permissions** (reader for pull, writer for push)
5. **Implement image signing** for critical deployments
6. **Monitor access logs** for unusual activity

## Next Steps

1. **Apply Terraform** to create the repository
2. **Push your first image** using the helper script
3. **Update Kubernetes manifests** to use Artifact Registry
4. **Set up CI/CD** to automatically push images
5. **Configure image scanning** for security

## Additional Resources

- [Artifact Registry Documentation](https://cloud.google.com/artifact-registry/docs)
- [Docker Authentication](https://cloud.google.com/artifact-registry/docs/docker/authentication)
- [Cleanup Policies](https://cloud.google.com/artifact-registry/docs/repositories/cleanup-policy)
- [GKE with Artifact Registry](https://cloud.google.com/kubernetes-engine/docs/how-to/using-artifact-registry)

