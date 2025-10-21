<!-- d912badd-6bf5-4994-b409-af15620ad08b 0fd6d940-7767-4a01-94fb-8379219fe481 -->
# Create Data Discovery Infrastructure GCP Project

## Overview

Create a new standalone Terraform infrastructure repository at `/home/user/git/data-discovery-infrastructure-gcp` that deploys comprehensive GCP resources for data discovery systems, including GKE, Cloud Composer, GCS buckets, service accounts, Dataplex profiling, and Vertex AI Search.

## Structure

```
data-discovery-infrastructure-gcp/
├── LICENSE (Apache 2.0)
├── README.md
├── QUICKSTART.md
├── .gitignore
├── main.tf
├── variables.tf
├── outputs.tf
├── versions.tf
├── service-accounts.tf
├── storage.tf
├── composer.tf
├── monitoring.tf
├── secrets.tf
├── artifact-registry.tf
├── ARTIFACT_REGISTRY.md
├── terraform.tfvars.example
├── dataplex-profiling/
│   ├── README.md
│   ├── dataplex-scans.tf
│   ├── bulk-scans.tf
│   └── terraform.tfvars.example
└── vertex-ai-search/
    ├── README.md
    └── vertex-search.tf
```

## Changes from Source

### Sanitize All Hardcoded Values

**In `variables.tf`:**

- Remove default value for `project_id` (was "lennyisagoodboy")
- Remove default values for `network` (was "projects/hazel-goal-319318/...")
- Remove default values for `subnetwork` (was "projects/hazel-goal-319318/...")
- Update bucket name defaults to use placeholder pattern: `"<your-project-id>-data-discovery-jsonl"`
- Keep generic defaults for: region, machine_type, node counts, environment

**In all `.tf` files:**

- No hardcoded project IDs or network paths
- All sensitive values must come from variables

**In all example files:**

- Replace specific values with placeholders:
  - `project_id = "YOUR_PROJECT_ID"`
  - `network = "projects/YOUR_PROJECT_ID/global/networks/YOUR_NETWORK"`
  - `subnetwork = "projects/YOUR_PROJECT_ID/regions/YOUR_REGION/subnetworks/YOUR_SUBNET"`

### Update Documentation

**README.md:**

- Remove references to specific projects ("lennyisagoodboy", "hazel-goal-319318")
- Update prerequisites section for public use
- Add GitHub repository information
- Include Apache 2.0 license notice
- Add badges: ![Terraform](https://img.shields.io/badge/terraform-%235835CC.svg?style=flat&logo=terraform&logoColor=white) ![GCP](https://img.shields.io/badge/Google_Cloud-%234285F4.svg?style=flat&logo=google-cloud&logoColor=white) ![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)
- Emphasize that this is a generic, reusable infrastructure template
- Add "Getting Started" section with prerequisites
- Add "Contributing" section for public repository

**QUICKSTART.md:**

- Update all commands to use `YOUR_PROJECT_ID` or `${PROJECT_ID}`
- Remove references to specific networks
- Simplify for first-time users

**ARTIFACT_REGISTRY.md:**

- Keep as-is but sanitize examples

**Subdirectory READMEs:**

- Update all examples to use placeholders
- Remove hardcoded project references

### Add New Files

**LICENSE:**

```
Apache License 2.0
Copyright 2025
Full Apache 2.0 license text
```

**GitHub Configuration:**

Add repository topics/tags:

- terraform
- gcp
- google-cloud
- infrastructure-as-code
- bigquery
- data-discovery
- gke
- cloud-composer
- vertex-ai
- apache-2

**.gitignore:**

- Copy existing gitignore (already good)
- Add any additional patterns if needed

## Implementation Steps

1. **Create project directory structure** at `/home/user/git/data-discovery-infrastructure-gcp/`

2. **Copy and sanitize main Terraform files:**

   - `main.tf` - review for hardcoded values
   - `variables.tf` - remove all hardcoded defaults per security policy
   - `outputs.tf` - copy as-is
   - `versions.tf` - copy as-is
   - `service-accounts.tf` - copy as-is
   - `storage.tf` - copy as-is
   - `composer.tf` - copy as-is
   - `monitoring.tf` - copy as-is
   - `secrets.tf` - copy as-is
   - `artifact-registry.tf` - copy as-is

3. **Copy and sanitize example files:**

   - Create `terraform.tfvars.example` with placeholder values

4. **Copy and update documentation:**

   - `README.md` - comprehensive update for public repo
   - `QUICKSTART.md` - update with placeholders
   - `ARTIFACT_REGISTRY.md` - sanitize examples

5. **Copy subdirectories:**

   - `dataplex-profiling/` - all files, sanitize examples
   - `vertex-ai-search/` - all files, sanitize examples

6. **Create new files:**

   - `LICENSE` - Apache 2.0 full text
   - `.gitignore` - copy and enhance if needed

7. **Final verification:**

   - Grep for any remaining hardcoded values
   - Verify all sensitive values use variables
   - Test that terraform.tfvars.example is comprehensive

## Key Files to Sanitize

### variables.tf Changes

```hcl
# BEFORE
variable "project_id" {
  default = "lennyisagoodboy"
}

# AFTER
variable "project_id" {
  description = "GCP Project ID for all resources"
  type        = string
  # No default - must be provided
}
```

### terraform.tfvars.example Structure

```hcl
# GCP Project Configuration
project_id = "YOUR_PROJECT_ID"
region     = "us-central1"

# Network Configuration
network    = "projects/YOUR_PROJECT_ID/global/networks/default"
subnetwork = "projects/YOUR_PROJECT_ID/regions/us-central1/subnetworks/default"

# Or use default VPC:
# network    = "default"
# subnetwork = "default"

# ... rest of configuration with sensible examples
```

## Validation Checklist

- [ ] No hardcoded project IDs in any .tf files
- [ ] No hardcoded network paths in any .tf files
- [ ] No hardcoded bucket names (except using variable patterns)
- [ ] All .tfvars.example files use placeholders
- [ ] README.md references generic project setup
- [ ] QUICKSTART.md uses ${PROJECT_ID} or YOUR_PROJECT_ID
- [ ] LICENSE file exists with Apache 2.0
- [ ] .gitignore prevents credential leaks
- [ ] All subdirectories included
- [ ] Documentation is clear for first-time users

## Post-Creation Tasks

After creating the repository structure:

1. Initialize git repository
2. Add all files
3. Create initial commit
4. Ready for GitHub publication with tags

### To-dos

- [ ] Create project directory structure at /home/user/git/data-discovery-infrastructure-gcp/
- [ ] Copy and sanitize main Terraform files (main.tf, variables.tf, outputs.tf, versions.tf, service-accounts.tf, storage.tf, composer.tf, monitoring.tf, secrets.tf, artifact-registry.tf)
- [ ] Create comprehensive terraform.tfvars.example with placeholder values
- [ ] Copy and sanitize dataplex-profiling/ and vertex-ai-search/ subdirectories
- [ ] Create LICENSE file with Apache 2.0 full text
- [ ] Copy .gitignore and ensure credential protection
- [ ] Create comprehensive README.md for public repository with badges, getting started, and contribution guidelines
- [ ] Update QUICKSTART.md with sanitized commands using placeholders
- [ ] Copy and sanitize ARTIFACT_REGISTRY.md and subdirectory READMEs
- [ ] Search all files for hardcoded project IDs, network paths, and sensitive values