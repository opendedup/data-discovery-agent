output "cluster_name" {
  description = "Name of the GKE cluster"
  value       = google_container_cluster.data_discovery.name
}

output "cluster_endpoint" {
  description = "Endpoint for GKE cluster"
  value       = google_container_cluster.data_discovery.endpoint
  sensitive   = true
}

output "cluster_ca_certificate" {
  description = "CA certificate for GKE cluster"
  value       = google_container_cluster.data_discovery.master_auth[0].cluster_ca_certificate
  sensitive   = true
}

output "cluster_location" {
  description = "Location of the GKE cluster"
  value       = google_container_cluster.data_discovery.location
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
  value       = google_service_account.gke_sa.email
}

output "kubectl_connection_command" {
  description = "Command to configure kubectl"
  value       = "gcloud container clusters get-credentials ${google_container_cluster.data_discovery.name} --region ${var.region} --project ${var.project_id}"
}

