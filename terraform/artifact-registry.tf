# Artifact Registry for Data Discovery MCP Container Images

# Artifact Registry repository for Docker images
resource "google_artifact_registry_repository" "mcp_images" {
  location      = var.artifact_registry_location
  repository_id = var.artifact_registry_repository_id
  description   = "Docker images for Data Discovery MCP service"
  format        = "DOCKER"

  # Cleanup policies for old images
  cleanup_policy_dry_run = false

  cleanup_policies {
    id     = "delete-untagged"
    action = "DELETE"

    condition {
      tag_state = "UNTAGGED"
      older_than = format("%ds", var.artifact_registry_retention_days * 24 * 3600)
    }
  }

  cleanup_policies {
    id     = "keep-recent-versions"
    action = "KEEP"

    most_recent_versions {
      keep_count = var.artifact_registry_keep_count
    }
  }

  labels = {
    environment = var.environment
    managed_by  = "terraform"
    component   = "data-discovery-mcp"
  }

  depends_on = [
    google_project_service.required_apis
  ]
}

# IAM: Grant GKE service account permission to pull images
resource "google_artifact_registry_repository_iam_member" "gke_reader" {
  count = var.enable_gke ? 1 : 0

  project    = var.project_id
  location   = google_artifact_registry_repository.mcp_images.location
  repository = google_artifact_registry_repository.mcp_images.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.gke_sa[0].email}"

  depends_on = [
    google_artifact_registry_repository.mcp_images
  ]
}

# IAM: Grant Composer service account permission to pull images
resource "google_artifact_registry_repository_iam_member" "composer_reader" {
  project    = var.project_id
  location   = google_artifact_registry_repository.mcp_images.location
  repository = google_artifact_registry_repository.mcp_images.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.composer_sa.email}"

  depends_on = [
    google_artifact_registry_repository.mcp_images
  ]
}

# IAM: Grant discovery service account permission to push images (for CI/CD)
resource "google_artifact_registry_repository_iam_member" "discovery_writer" {
  project    = var.project_id
  location   = google_artifact_registry_repository.mcp_images.location
  repository = google_artifact_registry_repository.mcp_images.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.discovery_sa.email}"

  depends_on = [
    google_artifact_registry_repository.mcp_images
  ]
}

