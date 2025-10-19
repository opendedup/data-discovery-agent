# GCS Buckets for Data Discovery System
# - JSONL bucket: For Vertex AI Search ingestion
# - Reports bucket: For human-readable Markdown reports

# Bucket for JSONL files (Vertex AI Search ingestion)
resource "google_storage_bucket" "jsonl_bucket" {
  name     = var.jsonl_bucket_name
  location = var.region
  project  = var.project_id

  # Regional bucket for better performance and lower cost
  storage_class = "REGIONAL"

  # Uniform bucket-level access (recommended)
  uniform_bucket_level_access = true

  # Versioning for data safety
  versioning {
    enabled = true
  }

  # Lifecycle rules to manage storage costs
  lifecycle_rule {
    condition {
      age = 90  # Delete files older than 90 days
    }
    action {
      type = "Delete"
    }
  }

  lifecycle_rule {
    condition {
      age = 30  # Move to Nearline after 30 days
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  # Labels
  labels = {
    environment = var.environment
    managed_by  = "terraform"
    component   = "data-discovery"
    purpose     = "vertex-ai-search-ingestion"
  }

  # Prevent accidental deletion in production
  force_destroy = var.environment != "prod"

  depends_on = [
    google_project_service.required_apis
  ]
}

# Bucket for Markdown reports
resource "google_storage_bucket" "reports_bucket" {
  name     = var.reports_bucket_name
  location = var.region
  project  = var.project_id

  # Regional bucket
  storage_class = "REGIONAL"

  # Uniform bucket-level access
  uniform_bucket_level_access = true

  # Versioning
  versioning {
    enabled = true
  }

  # Lifecycle rules
  lifecycle_rule {
    condition {
      age = 180  # Keep reports for 6 months
    }
    action {
      type = "Delete"
    }
  }

  lifecycle_rule {
    condition {
      age = 60  # Move to Nearline after 60 days
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  # Labels
  labels = {
    environment = var.environment
    managed_by  = "terraform"
    component   = "data-discovery"
    purpose     = "human-readable-reports"
  }

  # Prevent accidental deletion in production
  force_destroy = var.environment != "prod"

  depends_on = [
    google_project_service.required_apis
  ]
}

# IAM bindings for buckets

# Allow discovery service account to write to JSONL bucket
resource "google_storage_bucket_iam_member" "jsonl_bucket_writer" {
  bucket = google_storage_bucket.jsonl_bucket.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.discovery_sa.email}"
}

# Allow Vertex AI Search to read from JSONL bucket (for ingestion)
# Note: This will be configured when the Vertex AI Search data store is created
# For now, we'll grant the project's default Vertex AI service account access
resource "google_storage_bucket_iam_member" "jsonl_bucket_vertex_reader" {
  bucket = google_storage_bucket.jsonl_bucket.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-aiplatform.iam.gserviceaccount.com"
}

# Allow discovery service account to write to reports bucket
resource "google_storage_bucket_iam_member" "reports_bucket_writer" {
  bucket = google_storage_bucket.reports_bucket.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.discovery_sa.email}"
}

# Allow broader read access to reports bucket (for stakeholders)
resource "google_storage_bucket_iam_member" "reports_bucket_readers" {
  bucket = google_storage_bucket.reports_bucket.name
  role   = "roles/storage.objectViewer"
  member = "projectViewer:${var.project_id}"
}

# Composer service account access to buckets
resource "google_storage_bucket_iam_member" "jsonl_bucket_composer" {
  bucket = google_storage_bucket.jsonl_bucket.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.composer_sa.email}"
}

resource "google_storage_bucket_iam_member" "reports_bucket_composer" {
  bucket = google_storage_bucket.reports_bucket.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.composer_sa.email}"
}

# Data source for project information
data "google_project" "project" {
  project_id = var.project_id
}

