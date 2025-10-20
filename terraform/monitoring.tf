# Cloud Monitoring Configuration
# Basic monitoring setup for the data discovery system

# Log sink for audit logs (optional - can be used for lineage and security tracking)
resource "google_logging_project_sink" "discovery_audit_sink" {
  name        = "data-discovery-audit-logs"
  destination = "storage.googleapis.com/${google_storage_bucket.reports_bucket.name}"

  # Filter for relevant audit logs
  filter = <<-EOT
    protoPayload.serviceName="bigquery.googleapis.com"
    OR protoPayload.serviceName="datacatalog.googleapis.com"
    OR protoPayload.serviceName="storage.googleapis.com"
  EOT

  unique_writer_identity = true

  depends_on = [
    google_storage_bucket.reports_bucket
  ]
}

# Grant the log sink permission to write to the bucket
resource "google_storage_bucket_iam_member" "audit_log_writer" {
  bucket = google_storage_bucket.reports_bucket.name
  role   = "roles/storage.objectCreator"
  member = google_logging_project_sink.discovery_audit_sink.writer_identity
}

# Notification channel for alerts (email - customize as needed)
resource "google_monitoring_notification_channel" "email" {
  display_name = "Data Discovery Email Alerts"
  type         = "email"

  labels = {
    email_address = "alerts@example.com" # Change this!
  }

  enabled = false # Set to true and configure email when ready
}

# Alert policy for GKE cluster health
# Commented out temporarily - GKE metrics take 10-30 minutes to become available after cluster creation
# Uncomment and run `terraform apply` after the cluster has been running for a while
/*
resource "google_monitoring_alert_policy" "gke_node_health" {
  display_name = "Data Discovery - GKE Node Health"
  combiner     = "OR"
  
  conditions {
    display_name = "Node Not Ready"
    
    condition_threshold {
      filter          = "resource.type = \"k8s_node\" AND resource.labels.cluster_name = \"${var.cluster_name}\" AND metric.type = \"kubernetes.io/node/ready\""
      duration        = "300s"
      comparison      = "COMPARISON_LT"
      threshold_value = 1
      
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  # Uncomment when notification channel is configured
  # notification_channels = [google_monitoring_notification_channel.email.name]

  alert_strategy {
    auto_close = "1800s"
  }

  enabled = false  # Enable when ready

  depends_on = [
    google_container_cluster.data_discovery
  ]
}
*/

# Alert policy for bucket storage usage
resource "google_monitoring_alert_policy" "bucket_size" {
  display_name = "Data Discovery - Bucket Size Alert"
  combiner     = "OR"

  conditions {
    display_name = "Large Bucket Size"

    condition_threshold {
      filter          = "resource.type = \"gcs_bucket\" AND (resource.labels.bucket_name = \"${var.jsonl_bucket_name}\" OR resource.labels.bucket_name = \"${var.reports_bucket_name}\") AND metric.type = \"storage.googleapis.com/storage/total_bytes\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 100000000000 # 100 GB

      aggregations {
        alignment_period   = "3600s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  # Uncomment when notification channel is configured
  # notification_channels = [google_monitoring_notification_channel.email.name]

  enabled = false # Enable when ready

  depends_on = [
    google_storage_bucket.jsonl_bucket,
    google_storage_bucket.reports_bucket
  ]
}

