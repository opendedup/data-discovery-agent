# Security Notice

## Sensitive Information

This repository should NOT contain:

- ❌ GCP Project IDs
- ❌ GCP Organization/Folder IDs
- ❌ VPC Network paths or IDs
- ❌ Service Account Keys (.json files)
- ❌ terraform.tfvars files
- ❌ .env files with actual values
- ❌ Deployment summaries with real project data

## Protected by .gitignore

The following sensitive files are automatically excluded:

```
# Terraform state and variables
terraform/*.tfvars
terraform/.terraform/
terraform/*.tfstate*

# Environment variables
.env
.env.local

# Deployment summaries with real data
PHASE*_SUMMARY.md
PHASE*_FINAL_SUMMARY.md

# Service account keys
*.json (except specific config files)
key.json
credentials.json
service-account.json

# Scripts with sensitive data
scripts/create-datastore.py
```

## How to Use This Repository

1. **Copy example files**:
   ```bash
   cp .env.example .env
   cp terraform/terraform.tfvars.example terraform/terraform.tfvars
   ```

2. **Fill in YOUR values** in the copied files (not the .example files!)

3. **Never commit**:
   - `.env` (use `.env.example` instead)
   - `terraform.tfvars` (use `terraform.tfvars.example` instead)
   - Any files with real project IDs or credentials

## Using Environment Variables

All scripts and examples support environment variables:

```bash
# Set your configuration
export GCP_PROJECT_ID=your-project-id
export GCS_JSONL_BUCKET=your-project-id-data-discovery-jsonl
export GCS_REPORTS_BUCKET=your-project-id-data-discovery-reports

# Run scripts
poetry run python scripts/collect-bigquery-metadata.py --import
```

## Terraform Configuration

Update `terraform/terraform.tfvars` (gitignored) with your values:

```hcl
project_id = "your-project-id"
network    = "projects/your-host-project/global/networks/your-network"
subnetwork = "projects/your-host-project/regions/us-central1/subnetworks/your-subnet"
```

## Before Committing

Always check for sensitive data:

```bash
# Check for project IDs
git diff | grep -i "your-actual-project-id"

# Check gitignore is working
git status --ignored

# Verify no sensitive files are staged
git status
```

## If You Accidentally Commit Sensitive Data

1. **Do NOT push** to GitHub
2. Revert the commit:
   ```bash
   git reset --soft HEAD~1
   ```
3. Remove the sensitive file from staging:
   ```bash
   git restore --staged path/to/sensitive/file
   ```
4. Add the file to .gitignore
5. Commit again without the sensitive data

If already pushed, you'll need to:
1. Rotate any exposed credentials immediately
2. Use `git filter-branch` or BFG Repo-Cleaner to remove from history
3. Force push (dangerous - coordinate with team)

## Questions?

If you're unsure whether something is sensitive, **ask before committing**!
