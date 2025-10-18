#!/bin/bash
# Data Discovery Agent - Infrastructure Setup Script
# Phase 0: Deploy GKE cluster, GCS buckets, and service accounts

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TERRAFORM_DIR="$PROJECT_ROOT/terraform"
PROJECT_ID="${PROJECT_ID:-lennyisagoodboy}"
REGION="${REGION:-us-central1}"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check for required tools
    local missing_tools=()
    
    for tool in gcloud terraform kubectl; do
        if ! command -v "$tool" &> /dev/null; then
            missing_tools+=("$tool")
        fi
    done
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        log_info "Install missing tools and try again"
        exit 1
    fi
    
    # Check Terraform version
    local tf_version=$(terraform version -json | grep -o '"terraform_version":"[^"]*"' | cut -d'"' -f4)
    log_info "Terraform version: $tf_version"
    
    # Check gcloud authentication
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
        log_error "Not authenticated with gcloud. Run: gcloud auth login"
        exit 1
    fi
    
    local active_account=$(gcloud auth list --filter=status:ACTIVE --format="value(account)")
    log_success "Authenticated as: $active_account"
    
    # Check project access
    if ! gcloud projects describe "$PROJECT_ID" &> /dev/null; then
        log_error "Cannot access project: $PROJECT_ID"
        log_info "Check project ID and permissions"
        exit 1
    fi
    
    log_success "Project accessible: $PROJECT_ID"
}

create_tfvars() {
    log_info "Creating terraform.tfvars..."
    
    cd "$TERRAFORM_DIR"
    
    if [ -f "terraform.tfvars" ]; then
        log_warning "terraform.tfvars already exists"
        read -p "Overwrite? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Using existing terraform.tfvars"
            return
        fi
    fi
    
    cp terraform.tfvars.example terraform.tfvars
    log_success "Created terraform.tfvars from example"
    log_info "Review and customize terraform.tfvars if needed"
}

terraform_init() {
    log_info "Initializing Terraform..."
    
    cd "$TERRAFORM_DIR"
    
    if terraform init; then
        log_success "Terraform initialized"
    else
        log_error "Terraform init failed"
        exit 1
    fi
}

terraform_plan() {
    log_info "Planning infrastructure changes..."
    
    cd "$TERRAFORM_DIR"
    
    if terraform plan -out=tfplan; then
        log_success "Terraform plan created"
        log_info "Plan saved to: $TERRAFORM_DIR/tfplan"
    else
        log_error "Terraform plan failed"
        exit 1
    fi
}

terraform_apply() {
    log_info "Applying infrastructure changes..."
    log_warning "This will create real GCP resources and incur costs"
    
    read -p "Continue with apply? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Aborted by user"
        exit 0
    fi
    
    cd "$TERRAFORM_DIR"
    
    if terraform apply tfplan; then
        log_success "Infrastructure deployed successfully!"
    else
        log_error "Terraform apply failed"
        exit 1
    fi
}

show_outputs() {
    log_info "Retrieving Terraform outputs..."
    
    cd "$TERRAFORM_DIR"
    
    echo ""
    echo "=========================================="
    echo "         INFRASTRUCTURE OUTPUTS          "
    echo "=========================================="
    echo ""
    
    terraform output
    
    echo ""
    echo "=========================================="
    echo ""
}

setup_kubectl() {
    log_info "Configuring kubectl access to GKE cluster..."
    
    cd "$TERRAFORM_DIR"
    
    local cluster_name=$(terraform output -raw cluster_name 2>/dev/null || echo "data-discovery-cluster")
    
    if gcloud container clusters get-credentials "$cluster_name" \
        --region "$REGION" \
        --project "$PROJECT_ID"; then
        log_success "kubectl configured for cluster: $cluster_name"
    else
        log_error "Failed to configure kubectl"
        exit 1
    fi
    
    # Verify connection
    if kubectl get nodes &> /dev/null; then
        log_success "Successfully connected to cluster"
        echo ""
        kubectl get nodes
    else
        log_error "Cannot connect to cluster"
        exit 1
    fi
}

setup_workload_identity() {
    log_info "Setting up Workload Identity..."
    
    cd "$TERRAFORM_DIR"
    
    # Get service account emails from Terraform
    local discovery_sa=$(terraform output -raw discovery_service_account_email 2>/dev/null)
    local metadata_sa=$(terraform output -raw metadata_write_service_account_email 2>/dev/null)
    
    # Create namespace
    log_info "Creating Kubernetes namespace: data-discovery"
    kubectl create namespace data-discovery --dry-run=client -o yaml | kubectl apply -f -
    
    # Create Kubernetes service accounts
    log_info "Creating Kubernetes service accounts..."
    
    kubectl create serviceaccount discovery-agent -n data-discovery --dry-run=client -o yaml | kubectl apply -f -
    kubectl create serviceaccount metadata-writer -n data-discovery --dry-run=client -o yaml | kubectl apply -f -
    
    # Annotate with GCP service account emails
    log_info "Annotating service accounts with Workload Identity bindings..."
    
    kubectl annotate serviceaccount discovery-agent -n data-discovery \
        iam.gke.io/gcp-service-account="$discovery_sa" --overwrite
    
    kubectl annotate serviceaccount metadata-writer -n data-discovery \
        iam.gke.io/gcp-service-account="$metadata_sa" --overwrite
    
    log_success "Workload Identity configured"
    
    echo ""
    echo "Kubernetes Service Accounts:"
    kubectl get serviceaccounts -n data-discovery
}

display_next_steps() {
    echo ""
    echo "=========================================="
    echo "           SETUP COMPLETE! ✓             "
    echo "=========================================="
    echo ""
    echo "Next Steps:"
    echo ""
    echo "1. Verify cluster status:"
    echo "   kubectl get nodes"
    echo "   kubectl get namespaces"
    echo ""
    echo "2. Check GCS buckets:"
    echo "   gsutil ls -L gs://lennyisagoodboy-data-discovery-jsonl"
    echo "   gsutil ls -L gs://lennyisagoodboy-data-discovery-reports"
    echo ""
    echo "3. Verify service accounts:"
    echo "   gcloud iam service-accounts list --project=$PROJECT_ID"
    echo ""
    echo "4. Deploy GenAI Toolbox (Phase 0.2):"
    echo "   ./scripts/deploy-genai-toolbox.sh"
    echo ""
    echo "5. Configure Vertex AI Search data store (manually or via SDK)"
    echo ""
    echo "6. Build and deploy discovery agents (Phase 2)"
    echo ""
    echo "=========================================="
    echo ""
}

# Main execution
main() {
    echo ""
    echo "=========================================="
    echo "  Data Discovery Agent - Phase 0 Setup  "
    echo "=========================================="
    echo ""
    echo "Project ID: $PROJECT_ID"
    echo "Region: $REGION"
    echo ""
    
    check_prerequisites
    create_tfvars
    terraform_init
    terraform_plan
    terraform_apply
    show_outputs
    setup_kubectl
    setup_workload_identity
    display_next_steps
}

# Run main function
main "$@"

