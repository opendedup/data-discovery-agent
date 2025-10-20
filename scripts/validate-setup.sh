#!/bin/bash
# Data Discovery Agent - Infrastructure Validation Script
# Validates that Phase 0 infrastructure is properly deployed

set -e
set -u

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-us-central1}"
CLUSTER_NAME="${CLUSTER_NAME:-data-discovery-cluster}"
JSONL_BUCKET="${PROJECT_ID}-data-discovery-jsonl"
REPORTS_BUCKET="${PROJECT_ID}-data-discovery-reports"

# Counters
PASSED=0
FAILED=0

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}[✓ PASS]${NC} $1"
    ((PASSED++))
}

log_fail() {
    echo -e "${RED}[✗ FAIL]${NC} $1"
    ((FAILED++))
}

check_gke_cluster() {
    log_info "Checking GKE cluster..."
    
    if gcloud container clusters describe "$CLUSTER_NAME" \
        --region "$REGION" \
        --project "$PROJECT_ID" &> /dev/null; then
        log_pass "GKE cluster exists: $CLUSTER_NAME"
        
        # Check cluster details
        local status=$(gcloud container clusters describe "$CLUSTER_NAME" \
            --region "$REGION" \
            --project "$PROJECT_ID" \
            --format="value(status)")
        
        if [ "$status" = "RUNNING" ]; then
            log_pass "GKE cluster is running"
        else
            log_fail "GKE cluster status: $status (expected RUNNING)"
        fi
        
        # Check Workload Identity
        local wi_pool=$(gcloud container clusters describe "$CLUSTER_NAME" \
            --region "$REGION" \
            --project "$PROJECT_ID" \
            --format="value(workloadIdentityConfig.workloadPool)")
        
        if [ -n "$wi_pool" ]; then
            log_pass "Workload Identity enabled: $wi_pool"
        else
            log_fail "Workload Identity not enabled"
        fi
        
        # Check node pool
        local node_count=$(kubectl get nodes --no-headers 2>/dev/null | wc -l)
        if [ "$node_count" -ge 1 ]; then
            log_pass "Nodes available: $node_count"
        else
            log_fail "No nodes found"
        fi
        
    else
        log_fail "GKE cluster not found: $CLUSTER_NAME"
    fi
}

check_gcs_buckets() {
    log_info "Checking GCS buckets..."
    
    # Check JSONL bucket
    if gsutil ls -b "gs://$JSONL_BUCKET" &> /dev/null; then
        log_pass "JSONL bucket exists: $JSONL_BUCKET"
        
        local location=$(gsutil ls -L -b "gs://$JSONL_BUCKET" | grep "Location constraint:" | awk '{print $3}')
        if [ "$location" = "$REGION" ]; then
            log_pass "JSONL bucket location: $location"
        else
            log_fail "JSONL bucket location: $location (expected $REGION)"
        fi
    else
        log_fail "JSONL bucket not found: $JSONL_BUCKET"
    fi
    
    # Check reports bucket
    if gsutil ls -b "gs://$REPORTS_BUCKET" &> /dev/null; then
        log_pass "Reports bucket exists: $REPORTS_BUCKET"
        
        local location=$(gsutil ls -L -b "gs://$REPORTS_BUCKET" | grep "Location constraint:" | awk '{print $3}')
        if [ "$location" = "$REGION" ]; then
            log_pass "Reports bucket location: $location"
        else
            log_fail "Reports bucket location: $location (expected $REGION)"
        fi
    else
        log_fail "Reports bucket not found: $REPORTS_BUCKET"
    fi
}

check_service_accounts() {
    log_info "Checking service accounts..."
    
    local discovery_sa="data-discovery-agent@${PROJECT_ID}.iam.gserviceaccount.com"
    local metadata_sa="data-discovery-metadata@${PROJECT_ID}.iam.gserviceaccount.com"
    local gke_sa="data-discovery-gke@${PROJECT_ID}.iam.gserviceaccount.com"
    
    # Check discovery SA
    if gcloud iam service-accounts describe "$discovery_sa" \
        --project "$PROJECT_ID" &> /dev/null; then
        log_pass "Discovery service account exists"
        
        # Check key IAM roles
        local roles=$(gcloud projects get-iam-policy "$PROJECT_ID" \
            --flatten="bindings[].members" \
            --filter="bindings.members:serviceAccount:$discovery_sa" \
            --format="value(bindings.role)")
        
        if echo "$roles" | grep -q "bigquery.metadataViewer"; then
            log_pass "Discovery SA has BigQuery metadataViewer role"
        else
            log_fail "Discovery SA missing BigQuery metadataViewer role"
        fi
    else
        log_fail "Discovery service account not found"
    fi
    
    # Check metadata SA
    if gcloud iam service-accounts describe "$metadata_sa" \
        --project "$PROJECT_ID" &> /dev/null; then
        log_pass "Metadata write service account exists"
    else
        log_fail "Metadata write service account not found"
    fi
    
    # Check GKE SA
    if gcloud iam service-accounts describe "$gke_sa" \
        --project "$PROJECT_ID" &> /dev/null; then
        log_pass "GKE service account exists"
    else
        log_fail "GKE service account not found"
    fi
}

check_kubernetes_setup() {
    log_info "Checking Kubernetes configuration..."
    
    # Check namespace
    if kubectl get namespace data-discovery &> /dev/null; then
        log_pass "Namespace exists: data-discovery"
    else
        log_fail "Namespace not found: data-discovery"
    fi
    
    # Check service accounts
    if kubectl get serviceaccount discovery-agent -n data-discovery &> /dev/null; then
        log_pass "K8s service account exists: discovery-agent"
        
        # Check annotation
        local annotation=$(kubectl get serviceaccount discovery-agent -n data-discovery \
            -o jsonpath='{.metadata.annotations.iam\.gke\.io/gcp-service-account}')
        
        if [ -n "$annotation" ]; then
            log_pass "Workload Identity annotation present: $annotation"
        else
            log_fail "Workload Identity annotation missing"
        fi
    else
        log_fail "K8s service account not found: discovery-agent"
    fi
    
    if kubectl get serviceaccount metadata-writer -n data-discovery &> /dev/null; then
        log_pass "K8s service account exists: metadata-writer"
    else
        log_fail "K8s service account not found: metadata-writer"
    fi
}

check_apis() {
    log_info "Checking enabled APIs..."
    
    local required_apis=(
        "container.googleapis.com"
        "storage.googleapis.com"
        "bigquery.googleapis.com"
        "datacatalog.googleapis.com"
        "aiplatform.googleapis.com"
    )
    
    for api in "${required_apis[@]}"; do
        if gcloud services list --enabled --project "$PROJECT_ID" \
            --filter="name:$api" --format="value(name)" | grep -q "$api"; then
            log_pass "API enabled: $api"
        else
            log_fail "API not enabled: $api"
        fi
    done
}

test_workload_identity() {
    log_info "Testing Workload Identity (optional test pod)..."
    
    # Create a test pod to verify Workload Identity
    cat <<EOF | kubectl apply -f - &> /dev/null
apiVersion: v1
kind: Pod
metadata:
  name: workload-identity-test
  namespace: data-discovery
spec:
  serviceAccountName: discovery-agent
  containers:
  - name: test
    image: google/cloud-sdk:slim
    command: ["sleep", "60"]
EOF
    
    sleep 5
    
    # Check if pod can authenticate
    if kubectl exec -n data-discovery workload-identity-test -- gcloud auth list &> /dev/null; then
        local auth_account=$(kubectl exec -n data-discovery workload-identity-test -- \
            gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null)
        
        if [ -n "$auth_account" ]; then
            log_pass "Workload Identity working: $auth_account"
        else
            log_fail "Workload Identity authentication failed"
        fi
    else
        log_fail "Cannot test Workload Identity (pod may not be ready)"
    fi
    
    # Cleanup test pod
    kubectl delete pod workload-identity-test -n data-discovery &> /dev/null || true
}

display_summary() {
    echo ""
    echo "=========================================="
    echo "         VALIDATION SUMMARY              "
    echo "=========================================="
    echo ""
    echo -e "Tests Passed: ${GREEN}$PASSED${NC}"
    echo -e "Tests Failed: ${RED}$FAILED${NC}"
    echo ""
    
    if [ "$FAILED" -eq 0 ]; then
        echo -e "${GREEN}✓ All validation checks passed!${NC}"
        echo ""
        echo "Infrastructure is ready for Phase 0.2 (GenAI Toolbox deployment)"
        return 0
    else
        echo -e "${RED}✗ Some validation checks failed${NC}"
        echo ""
        echo "Please review the failed checks and fix any issues before proceeding."
        return 1
    fi
}

main() {
    echo ""
    echo "=========================================="
    echo "   Infrastructure Validation - Phase 0   "
    echo "=========================================="
    echo ""
    echo "Project: $PROJECT_ID"
    echo "Region: $REGION"
    echo "Cluster: $CLUSTER_NAME"
    echo ""
    
    check_apis
    check_gke_cluster
    check_gcs_buckets
    check_service_accounts
    check_kubernetes_setup
    test_workload_identity
    
    echo ""
    display_summary
}

main "$@"

