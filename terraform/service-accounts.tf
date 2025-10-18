# Service Accounts with Least-Privilege IAM Roles
# Following SR-2 security requirements

# Service Account for GKE nodes
resource "google_service_account" "gke_sa" {
  account_id   = "data-discovery-gke"
  display_name = "Data Discovery GKE Service Account"
  description  = "Service account for GKE cluster nodes"
  project      = var.project_id
}

# Minimal permissions for GKE nodes
resource "google_project_iam_member" "gke_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.gke_sa.email}"
}

resource "google_project_iam_member" "gke_metric_writer" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.gke_sa.email}"
}

resource "google_project_iam_member" "gke_monitoring_viewer" {
  project = var.project_id
  role    = "roles/monitoring.viewer"
  member  = "serviceAccount:${google_service_account.gke_sa.email}"
}

# Service Account for Discovery Operations (Read-Only)
resource "google_service_account" "discovery_sa" {
  account_id   = "data-discovery-agent"
  display_name = "Data Discovery Agent Service Account"
  description  = "Read-only service account for data discovery operations (SR-2A compliant)"
  project      = var.project_id
}

# BigQuery read-only permissions
resource "google_project_iam_member" "discovery_bq_metadata_viewer" {
  project = var.project_id
  role    = "roles/bigquery.metadataViewer"
  member  = "serviceAccount:${google_service_account.discovery_sa.email}"
}

resource "google_project_iam_member" "discovery_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.discovery_sa.email}"
}

# Data Catalog read permissions
resource "google_project_iam_member" "discovery_datacatalog_viewer" {
  project = var.project_id
  role    = "roles/datacatalog.viewer"
  member  = "serviceAccount:${google_service_account.discovery_sa.email}"
}

# Cloud Logging read permissions (for audit log analysis)
resource "google_project_iam_member" "discovery_logging_viewer" {
  project = var.project_id
  role    = "roles/logging.viewer"
  member  = "serviceAccount:${google_service_account.discovery_sa.email}"
}

resource "google_project_iam_member" "discovery_logging_private_viewer" {
  project = var.project_id
  role    = "roles/logging.privateLogViewer"
  member  = "serviceAccount:${google_service_account.discovery_sa.email}"
}

# DLP read permissions (for PII detection)
resource "google_project_iam_member" "discovery_dlp_reader" {
  project = var.project_id
  role    = "roles/dlp.reader"
  member  = "serviceAccount:${google_service_account.discovery_sa.email}"
}

# Vertex AI Search permissions (for querying)
resource "google_project_iam_member" "discovery_aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.discovery_sa.email}"
}

# Dataplex permissions (for GenAI Toolbox - lineage and data quality)
resource "google_project_iam_member" "discovery_dataplex_viewer" {
  project = var.project_id
  role    = "roles/dataplex.viewer"
  member  = "serviceAccount:${google_service_account.discovery_sa.email}"
}

resource "google_project_iam_member" "discovery_dataplex_metadataReader" {
  project = var.project_id
  role    = "roles/dataplex.metadataReader"
  member  = "serviceAccount:${google_service_account.discovery_sa.email}"
}

# Looker permissions - DISABLED (not needed for initial setup)
# Uncomment below if Looker integration is needed in the future:
# resource "google_project_iam_member" "discovery_looker_viewer" {
#   project = var.project_id
#   role    = "roles/looker.viewer"
#   member  = "serviceAccount:${google_service_account.discovery_sa.email}"
# }

# Storage write permissions (for JSONL and reports)
# Note: Granular bucket-level permissions are set in storage.tf

# Service Account for Metadata Writes (Data Catalog Only)
resource "google_service_account" "metadata_write_sa" {
  account_id   = "data-discovery-metadata"
  display_name = "Data Discovery Metadata Write Service Account"
  description  = "Service account for writing metadata to Data Catalog only (SR-2A compliant)"
  project      = var.project_id
}

# Data Catalog write permissions (limited scope)
resource "google_project_iam_member" "metadata_datacatalog_entrygroup_owner" {
  project = var.project_id
  role    = "roles/datacatalog.entryGroupOwner"
  member  = "serviceAccount:${google_service_account.metadata_write_sa.email}"
}

# Allow metadata SA to also read (for verification)
resource "google_project_iam_member" "metadata_datacatalog_viewer" {
  project = var.project_id
  role    = "roles/datacatalog.viewer"
  member  = "serviceAccount:${google_service_account.metadata_write_sa.email}"
}

# Logging for audit trail
resource "google_project_iam_member" "metadata_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.metadata_write_sa.email}"
}

# Workload Identity bindings (GKE pods → GCP service accounts)
# These allow Kubernetes service accounts to impersonate GCP service accounts

# Workload Identity for discovery service account
resource "google_service_account_iam_member" "discovery_workload_identity" {
  service_account_id = google_service_account.discovery_sa.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[data-discovery/discovery-agent]"
  
  depends_on = [
    google_container_cluster.data_discovery
  ]
}

# Workload Identity for metadata write service account
resource "google_service_account_iam_member" "metadata_workload_identity" {
  service_account_id = google_service_account.metadata_write_sa.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[data-discovery/metadata-writer]"
  
  depends_on = [
    google_container_cluster.data_discovery
  ]
}

# Output service account emails for reference
output "service_account_setup_notes" {
  value = <<-EOT
  
  Service Accounts Created:
  
  1. Discovery Service Account (Read-Only):
     Email: ${google_service_account.discovery_sa.email}
     Purpose: All data discovery and indexing operations
     Permissions: BigQuery metadata viewer, Data Catalog viewer, Logging viewer, DLP reader
     K8s Namespace: data-discovery
     K8s Service Account: discovery-agent
  
  2. Metadata Write Service Account:
     Email: ${google_service_account.metadata_write_sa.email}
     Purpose: Writing enriched metadata to Data Catalog only
     Permissions: Data Catalog entry group owner
     K8s Namespace: data-discovery
     K8s Service Account: metadata-writer
  
  3. GKE Service Account:
     Email: ${google_service_account.gke_sa.email}
     Purpose: GKE node operations
     Permissions: Logging and monitoring
  
  Workload Identity Setup:
  - Create K8s namespace: kubectl create namespace data-discovery
  - Create K8s service accounts: discovery-agent and metadata-writer
  - Annotate them with the GCP service account emails (see deployment scripts)
  EOT
}

