#!/bin/bash
# Data Discovery Agent - Infrastructure Teardown Script
# WARNING: This will destroy all infrastructure created in Phase 0

set -e
set -u

# Colors
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TERRAFORM_DIR="$PROJECT_ROOT/terraform"
PROJECT_ID="${PROJECT_ID:-lennyisagoodboy}"

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

display_warning() {
    echo ""
    echo "=========================================="
    echo "            ⚠️  WARNING  ⚠️               "
    echo "=========================================="
    echo ""
    echo "This script will DESTROY the following:"
    echo ""
    echo "  • GKE cluster and all workloads"
    echo "  • GCS buckets (and all data)"
    echo "  • Service accounts"
    echo "  • IAM bindings"
    echo "  • Monitoring resources"
    echo "  • All deployed infrastructure"
    echo ""
    echo "Project: $PROJECT_ID"
    echo ""
    echo "This action CANNOT be undone!"
    echo ""
    echo "=========================================="
    echo ""
}

confirm_destruction() {
    log_warning "Type the project ID to confirm destruction: $PROJECT_ID"
    read -p "> " confirm_project
    
    if [ "$confirm_project" != "$PROJECT_ID" ]; then
        log_error "Project ID mismatch. Aborting."
        exit 1
    fi
    
    log_warning "Are you ABSOLUTELY SURE? Type 'destroy' to proceed:"
    read -p "> " confirm_destroy
    
    if [ "$confirm_destroy" != "destroy" ]; then
        log_error "Confirmation failed. Aborting."
        exit 1
    fi
}

backup_tfstate() {
    echo "Creating backup of Terraform state..."
    
    cd "$TERRAFORM_DIR"
    
    if [ -f "terraform.tfstate" ]; then
        local backup_file="terraform.tfstate.backup.$(date +%Y%m%d_%H%M%S)"
        cp terraform.tfstate "$backup_file"
        echo "State backed up to: $backup_file"
    fi
}

destroy_infrastructure() {
    echo ""
    echo "Destroying infrastructure..."
    echo ""
    
    cd "$TERRAFORM_DIR"
    
    # Run terraform destroy
    if terraform destroy -auto-approve; then
        echo ""
        echo "=========================================="
        echo "   Infrastructure successfully destroyed  "
        echo "=========================================="
        echo ""
        return 0
    else
        log_error "Terraform destroy encountered errors"
        echo ""
        echo "Some resources may not have been deleted."
        echo "Check GCP Console and Terraform state."
        return 1
    fi
}

cleanup_local_state() {
    echo ""
    echo "Cleaning up local Terraform state..."
    
    cd "$TERRAFORM_DIR"
    
    read -p "Remove local Terraform state files? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf .terraform
        rm -f tfplan
        echo "Local state cleaned"
    fi
}

main() {
    display_warning
    confirm_destruction
    backup_tfstate
    
    if destroy_infrastructure; then
        cleanup_local_state
        
        echo ""
        echo "All infrastructure has been destroyed."
        echo ""
        echo "Note: Some resources may take time to fully delete:"
        echo "  • GCS buckets (if not empty)"
        echo "  • Service accounts (IAM propagation delay)"
        echo "  • VPC resources (if dependencies exist)"
        echo ""
    else
        echo ""
        echo "Teardown completed with errors."
        echo "Manual cleanup may be required."
        echo ""
        exit 1
    fi
}

main "$@"

