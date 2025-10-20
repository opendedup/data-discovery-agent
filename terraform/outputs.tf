output "cluster_name" {
  description = "Name of the GKE cluster"
  value       = var.enable_gke ? google_container_cluster.data_discovery[0].name : null
}

output "cluster_endpoint" {
  description = "Endpoint for GKE cluster"
  value       = var.enable_gke ? google_container_cluster.data_discovery[0].endpoint : null
  sensitive   = true
}

output "cluster_ca_certificate" {
  description = "CA certificate for GKE cluster"
  value       = var.enable_gke ? google_container_cluster.data_discovery[0].master_auth[0].cluster_ca_certificate : null
  sensitive   = true
}

output "cluster_location" {
  description = "Location of the GKE cluster"
  value       = var.enable_gke ? google_container_cluster.data_discovery[0].location : null
}

output "jsonl_bucket_name" {
  description = "Name of the JSONL GCS bucket"
  value       = google_storage_bucket.jsonl_bucket.name
}

output "reports_bucket_name" {
  description = "Name of the reports GCS bucket"
  value       = google_storage_bucket.reports_bucket.name
}

output "discovery_service_account_email" {
  description = "Email of the discovery service account"
  value       = google_service_account.discovery_sa.email
}

output "metadata_write_service_account_email" {
  description = "Email of the metadata write service account"
  value       = google_service_account.metadata_write_sa.email
}

output "gke_service_account_email" {
  description = "Email of the GKE service account"
  value       = var.enable_gke ? google_service_account.gke_sa[0].email : null
}

output "kubectl_connection_command" {
  description = "Command to configure kubectl"
  value       = var.enable_gke ? "gcloud container clusters get-credentials ${google_container_cluster.data_discovery[0].name} --region ${var.region} --project ${var.project_id}" : "GKE is disabled"
}

# Artifact Registry Outputs
output "artifact_registry_repository" {
  description = "Full name of the Artifact Registry repository"
  value       = google_artifact_registry_repository.mcp_images.name
}

output "artifact_registry_location" {
  description = "Location of the Artifact Registry repository"
  value       = google_artifact_registry_repository.mcp_images.location
}

output "artifact_registry_url" {
  description = "URL for pushing/pulling images to/from Artifact Registry"
  value       = "${google_artifact_registry_repository.mcp_images.location}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.mcp_images.repository_id}"
}

output "docker_push_command_example" {
  description = "Example command to push Docker image to Artifact Registry"
  value       = "docker tag data-discovery-mcp:latest ${google_artifact_registry_repository.mcp_images.location}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.mcp_images.repository_id}/mcp:latest && docker push ${google_artifact_registry_repository.mcp_images.location}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.mcp_images.repository_id}/mcp:latest"
}

