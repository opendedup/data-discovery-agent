# Vertex AI Search Data Store Configuration
# Phase 1: Core search infrastructure for cached discovery

# Variables
variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region for Vertex AI Search (use 'global' for data stores)"
  type        = string
  default     = "global"
}

variable "datastore_id" {
  description = "ID for the Vertex AI Search data store"
  type        = string
  default     = "data-discovery-metadata"
}

variable "jsonl_bucket_name" {
  description = "GCS bucket containing JSONL files for ingestion"
  type        = string
}

# Data source for GCS bucket
data "google_storage_bucket" "jsonl_bucket" {
  name = var.jsonl_bucket_name
}

# Vertex AI Search Data Store
# Note: As of 2024, Vertex AI Search may need to be created via gcloud or console
# This is a placeholder for when Terraform provider fully supports it

# For now, create via Python script: scripts/create-datastore.py
# Or via gcloud command:
# gcloud alpha discovery-engine data-stores create ${var.datastore_id} \
#   --project=${var.project_id} \
#   --location=global \
#   --collection=default_collection \
#   --industry-vertical=GENERIC \
#   --content-config=CONTENT_REQUIRED \
#   --solution-type=SOLUTION_TYPE_SEARCH

# Service account for Vertex AI Search
resource "google_service_account" "vertex_search_sa" {
  account_id   = "vertex-search-ingestion"
  display_name = "Vertex AI Search Ingestion Service Account"
  description  = "Service account for Vertex AI Search to ingest data from GCS"
  project      = var.project_id
}

# Grant Vertex AI Search SA access to read JSONL bucket
resource "google_storage_bucket_iam_member" "vertex_search_bucket_reader" {
  bucket = data.google_storage_bucket.jsonl_bucket.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.vertex_search_sa.email}"
}

# Grant discovery SA permission to use Vertex AI Search
resource "google_project_iam_member" "discovery_vertex_search_user" {
  project = var.project_id
  role    = "roles/discoveryengine.viewer"
  member  = "serviceAccount:data-discovery-agent@${var.project_id}.iam.gserviceaccount.com"
}

resource "google_project_iam_member" "discovery_vertex_search_editor" {
  project = var.project_id
  role    = "roles/discoveryengine.editor"
  member  = "serviceAccount:data-discovery-agent@${var.project_id}.iam.gserviceaccount.com"
}

# Enable Discovery Engine API (Vertex AI Search)
resource "google_project_service" "discovery_engine" {
  project = var.project_id
  service = "discoveryengine.googleapis.com"
  
  disable_on_destroy = false
}

# Outputs
output "vertex_search_sa_email" {
  description = "Email of Vertex AI Search service account"
  value       = google_service_account.vertex_search_sa.email
}

output "datastore_id" {
  description = "ID of the Vertex AI Search data store"
  value       = var.datastore_id
}

output "datastore_location" {
  description = "Location of the Vertex AI Search data store"
  value       = var.region
}

output "setup_commands" {
  description = "Commands to complete Vertex AI Search setup"
  value       = <<-EOT
  
  To create the Vertex AI Search data store, run:
  
  gcloud alpha discovery-engine data-stores create ${var.datastore_id} \\
    --project=${var.project_id} \\
    --location=${var.region} \\
    --collection=default_collection \\
    --industry-vertical=GENERIC \\
    --content-config=CONTENT_REQUIRED \\
    --solution-type=SOLUTION_TYPE_SEARCH
  
  To import data from GCS:
  
  gcloud alpha discovery-engine data-stores import documents \\
    --project=${var.project_id} \\
    --location=${var.region} \\
    --data-store=${var.datastore_id} \\
    --gcs-uri=gs://${var.jsonl_bucket_name}/*.jsonl
  
  EOT
}

