#!/bin/bash
# Deploy GenAI Toolbox to GKE - Phase 0.2
# This script deploys the GenAI Toolbox with BigQuery and Dataplex tools

set -e
set -u

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TERRAFORM_DIR="$PROJECT_ROOT/terraform/genai-toolbox"
PROJECT_ID="${PROJECT_ID:-lennyisagoodboy}"
REGION="${REGION:-us-central1}"
CLUSTER_NAME="${CLUSTER_NAME:-data-discovery-cluster}"
NAMESPACE="data-discovery"

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓ SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[⚠ WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗ ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check for required tools
    for tool in kubectl terraform gcloud; do
        if ! command -v "$tool" &> /dev/null; then
            log_error "Required tool not found: $tool"
            exit 1
        fi
    done
    
    log_success "All required tools are installed"
}

check_cluster() {
    log_info "Checking GKE cluster status..."
    
    # Get cluster status
    local status=$(gcloud container clusters describe "$CLUSTER_NAME" \
        --region "$REGION" \
        --project "$PROJECT_ID" \
        --format="value(status)" 2>/dev/null || echo "NOT_FOUND")
    
    if [ "$status" != "RUNNING" ]; then
        log_error "Cluster is not running. Status: $status"
        log_info "Run Phase 0.1 first: cd $PROJECT_ROOT/terraform && terraform apply"
        exit 1
    fi
    
    log_success "Cluster is running: $CLUSTER_NAME"
}

configure_kubectl() {
    log_info "Configuring kubectl access..."
    
    gcloud container clusters get-credentials "$CLUSTER_NAME" \
        --region "$REGION" \
        --project "$PROJECT_ID" \
        --quiet
    
    if kubectl get nodes &> /dev/null; then
        log_success "kubectl configured successfully"
    else
        log_error "Failed to connect to cluster"
        exit 1
    fi
}

check_namespace() {
    log_info "Checking namespace..."
    
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_warning "Namespace $NAMESPACE not found. Creating..."
        kubectl create namespace "$NAMESPACE"
        log_success "Created namespace: $NAMESPACE"
    else
        log_success "Namespace exists: $NAMESPACE"
    fi
}

check_service_account() {
    log_info "Checking Kubernetes service account..."
    
    if ! kubectl get serviceaccount discovery-agent -n "$NAMESPACE" &> /dev/null; then
        log_warning "Service account discovery-agent not found. Creating..."
        kubectl create serviceaccount discovery-agent -n "$NAMESPACE"
    fi
    
    # Check Workload Identity annotation
    local annotation=$(kubectl get serviceaccount discovery-agent -n "$NAMESPACE" \
        -o jsonpath='{.metadata.annotations.iam\.gke\.io/gcp-service-account}' 2>/dev/null || echo "")
    
    if [ -z "$annotation" ]; then
        log_warning "Workload Identity annotation missing. Adding..."
        kubectl annotate serviceaccount discovery-agent -n "$NAMESPACE" \
            iam.gke.io/gcp-service-account="data-discovery-agent@${PROJECT_ID}.iam.gserviceaccount.com" \
            --overwrite
        log_success "Added Workload Identity annotation"
    else
        log_success "Workload Identity configured: $annotation"
    fi
}

deploy_toolbox() {
    log_info "Deploying GenAI Toolbox..."
    
    cd "$TERRAFORM_DIR"
    
    # Initialize Terraform
    log_info "Initializing Terraform..."
    terraform init
    
    # Plan
    log_info "Planning deployment..."
    terraform plan \
        -var="project_id=$PROJECT_ID" \
        -var="region=$REGION" \
        -var="cluster_name=$CLUSTER_NAME" \
        -out=tfplan
    
    # Apply
    log_info "Applying deployment..."
    terraform apply tfplan
    
    log_success "GenAI Toolbox deployed"
}

wait_for_deployment() {
    log_info "Waiting for GenAI Toolbox to be ready..."
    
    kubectl wait --for=condition=available --timeout=300s \
        deployment/genai-toolbox -n "$NAMESPACE"
    
    log_success "GenAI Toolbox is ready"
}

test_deployment() {
    log_info "Testing GenAI Toolbox deployment..."
    
    # Get pod name
    local pod=$(kubectl get pods -n "$NAMESPACE" -l app=genai-toolbox \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    
    if [ -z "$pod" ]; then
        log_error "No GenAI Toolbox pods found"
        return 1
    fi
    
    log_info "Found pod: $pod"
    
    # Test health endpoint
    log_info "Testing health endpoint..."
    if kubectl exec -n "$NAMESPACE" "$pod" -- wget -q -O- http://localhost:8081/health &> /dev/null; then
        log_success "Health check passed"
    else
        log_warning "Health check failed (may still be starting)"
    fi
}

display_info() {
    echo ""
    echo "=========================================="
    echo "    GenAI Toolbox Deployment Complete    "
    echo "=========================================="
    echo ""
    echo "Service Details:"
    echo "  Namespace: $NAMESPACE"
    echo "  Deployment: genai-toolbox"
    echo "  Replicas: 2 (auto-scaling 2-10)"
    echo ""
    echo "Endpoints:"
    echo "  MCP: http://genai-toolbox.$NAMESPACE.svc.cluster.local:8080/mcp"
    echo "  Health: http://genai-toolbox.$NAMESPACE.svc.cluster.local:8081/health"
    echo "  Metrics: http://genai-toolbox.$NAMESPACE.svc.cluster.local:8080/metrics"
    echo ""
    echo "Tools Available:"
    echo "  ✓ bigquery-get-table-info"
    echo "  ✓ bigquery-execute-sql"
    echo "  ✓ dataplex-get-lineage"
    echo "  ✓ dataplex-get-data-quality"
    echo "  ✓ dataplex-get-data-profile"
    echo ""
    echo "Useful Commands:"
    echo ""
    echo "  # View pods"
    echo "  kubectl get pods -n $NAMESPACE -l app=genai-toolbox"
    echo ""
    echo "  # View logs"
    echo "  kubectl logs -n $NAMESPACE -l app=genai-toolbox --tail=100 -f"
    echo ""
    echo "  # Check health"
    echo "  kubectl run -it --rm debug --image=curlimages/curl --restart=Never -n $NAMESPACE -- \\"
    echo "    curl http://genai-toolbox.$NAMESPACE.svc.cluster.local:8081/health"
    echo ""
    echo "  # View service"
    echo "  kubectl get svc -n $NAMESPACE genai-toolbox"
    echo ""
    echo "Next Steps:"
    echo "  1. Phase 1: Set up Vertex AI Search"
    echo "  2. Phase 2: Create background discovery agents"
    echo "  3. Phase 3: Implement Smart Query Router"
    echo ""
    echo "=========================================="
    echo ""
}

main() {
    echo ""
    echo "=========================================="
    echo "  GenAI Toolbox Deployment - Phase 0.2  "
    echo "=========================================="
    echo ""
    
    check_prerequisites
    check_cluster
    configure_kubectl
    check_namespace
    check_service_account
    deploy_toolbox
    wait_for_deployment
    test_deployment
    display_info
}

main "$@"

