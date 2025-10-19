#
# Dataplex Data Profile Scans
#
# Creates data profile scans for BigQuery tables to enable rich metadata collection.
# Reference: https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/dataplex_datascan
#

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "location" {
  description = "Dataplex location for data scans"
  type        = string
  default     = "us-central1"
}

variable "tables_to_profile" {
  description = "List of tables to create profile scans for"
  type = list(object({
    dataset_id = string
    table_id   = string
  }))
  default = []
}

variable "scan_schedule_cron" {
  description = "Cron schedule for profile scans (e.g., '0 22 * * *' for 10 PM daily)"
  type        = string
  default     = "0 22 * * *"  # 10 PM daily (2 hours before midnight metadata collection)
}

variable "run_scans_on_create" {
  description = "Trigger scans immediately after creation"
  type        = bool
  default     = true
}

# Enable Dataplex API
resource "google_project_service" "dataplex_api" {
  project = var.project_id
  service = "dataplex.googleapis.com"
  
  disable_on_destroy = false
}

# Create a data profile scan for each table
resource "google_dataplex_datascan" "table_profile" {
  for_each = { for table in var.tables_to_profile : "${table.dataset_id}.${table.table_id}" => table }
  
  project  = var.project_id
  location = var.location
  
  # Scan ID (must be unique within project/location)
  data_scan_id = "profile-${each.value.dataset_id}-${each.value.table_id}"
  
  display_name = "Profile: ${each.value.dataset_id}.${each.value.table_id}"
  description  = "Automated data profile scan for ${each.value.dataset_id}.${each.value.table_id}"
  
  # Labels for organization
  labels = {
    managed_by = "terraform"
    purpose    = "data-discovery"
    dataset    = each.value.dataset_id
  }
  
  # Target BigQuery table
  data {
    resource = "//bigquery.googleapis.com/projects/${var.project_id}/datasets/${each.value.dataset_id}/tables/${each.value.table_id}"
  }
  
  # Data profile specification
  data_profile_spec {
    # Sample 100% of the data for complete profiling
    sampling_percent = 100.0
    
    # Optional: Add row filter to exclude certain rows
    # row_filter = "column_name IS NOT NULL"
  }
  
  # Execution schedule
  execution_spec {
    trigger {
      schedule {
        cron = var.scan_schedule_cron
      }
    }
  }
  
  depends_on = [google_project_service.dataplex_api]
}

# Trigger scans immediately after creation (if enabled)
resource "null_resource" "trigger_scan" {
  for_each = var.run_scans_on_create ? google_dataplex_datascan.table_profile : {}
  
  provisioner "local-exec" {
    command = <<-EOT
      gcloud dataplex datascans run ${each.value.data_scan_id} \
        --project=${var.project_id} \
        --location=${var.location} \
        --async \
        || echo "Warning: Failed to trigger scan ${each.value.data_scan_id}"
    EOT
  }
  
  depends_on = [google_dataplex_datascan.table_profile]
}

# Output scan information
output "profile_scan_ids" {
  description = "Created data profile scan IDs"
  value = {
    for k, scan in google_dataplex_datascan.table_profile : k => scan.name
  }
}

output "profile_scan_names" {
  description = "Full resource names of profile scans"
  value = [
    for scan in google_dataplex_datascan.table_profile : scan.name
  ]
}

