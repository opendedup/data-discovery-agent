# Secret Manager Configuration
# For storing sensitive configuration like API keys, connection strings, etc.

# Create a secret for sensitive configuration
resource "google_secret_manager_secret" "discovery_config" {
  secret_id = "data-discovery-config"
  project   = var.project_id

  labels = {
    environment = var.environment
    managed_by  = "terraform"
    component   = "data-discovery"
  }

  replication {
    auto {}
  }

  depends_on = [
    google_project_service.required_apis
  ]
}

# Allow discovery service account to access secrets
resource "google_secret_manager_secret_iam_member" "discovery_secret_accessor" {
  secret_id = google_secret_manager_secret.discovery_config.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.discovery_sa.email}"
}

# Note: Secret versions should be created manually or via separate process
# to avoid storing sensitive data in Terraform state

