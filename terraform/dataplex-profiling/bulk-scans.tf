#
# Bulk Dataplex Data Profile Scans using Data Sources
#
# Dynamically discovers all tables in specified datasets and creates scans.
# This is an alternative to the Python script approach.
#

variable "bulk_scan_enabled" {
  description = "Enable bulk scanning of all tables in datasets"
  type        = bool
  default     = false
}

variable "bulk_scan_datasets" {
  description = "List of datasets to bulk scan"
  type = list(object({
    project_id = string
    dataset_id = string
  }))
  default = []
}

variable "bulk_scan_sampling_percent" {
  description = "Sampling percentage for bulk scans"
  type        = number
  default     = 100.0
}

# Data source to list all tables in specified datasets
data "google_bigquery_tables" "bulk_tables" {
  for_each = var.bulk_scan_enabled ? { for ds in var.bulk_scan_datasets : "${ds.project_id}.${ds.dataset_id}" => ds } : {}
  
  project    = each.value.project_id
  dataset_id = each.value.dataset_id
}

# Create scans for all discovered tables
resource "google_dataplex_datascan" "bulk_profile" {
  for_each = var.bulk_scan_enabled ? {
    for combo in flatten([
      for ds_key, tables in data.google_bigquery_tables.bulk_tables : [
        for table in tables.tables : {
          key        = "${tables.dataset_id}.${table.table_id}"
          project_id = tables.project
          dataset_id = tables.dataset_id
          table_id   = table.table_id
        }
      ]
    ]) : combo.key => combo
  } : {}
  
  project  = each.value.project_id
  location = var.location
  
  data_scan_id = "profile-${each.value.dataset_id}-${each.value.table_id}"
  
  display_name = "Profile: ${each.value.dataset_id}.${each.value.table_id}"
  description  = "Bulk automated data profile scan"
  
  labels = {
    managed_by = "terraform"
    purpose    = "data-discovery"
    dataset    = each.value.dataset_id
    bulk_scan  = "true"
  }
  
  data {
    resource = "//bigquery.googleapis.com/projects/${each.value.project_id}/datasets/${each.value.dataset_id}/tables/${each.value.table_id}"
  }
  
  data_profile_spec {
    sampling_percent = var.bulk_scan_sampling_percent
  }
  
  execution_spec {
    trigger {
      schedule {
        cron = var.scan_schedule_cron
      }
    }
  }
  
  depends_on = [google_project_service.dataplex_api]
}

# Trigger bulk scans immediately after creation (if enabled)
resource "null_resource" "trigger_bulk_scan" {
  for_each = var.run_scans_on_create && var.bulk_scan_enabled ? google_dataplex_datascan.bulk_profile : {}
  
  provisioner "local-exec" {
    command = <<-EOT
      gcloud dataplex datascans run ${each.value.data_scan_id} \
        --project=${var.project_id} \
        --location=${var.location} \
        --async \
        || echo "Warning: Failed to trigger scan ${each.value.data_scan_id}"
    EOT
  }
  
  depends_on = [google_dataplex_datascan.bulk_profile]
}

# Output bulk scan information
output "bulk_scan_count" {
  description = "Number of bulk scans created"
  value       = var.bulk_scan_enabled ? length(google_dataplex_datascan.bulk_profile) : 0
}

output "bulk_scan_ids" {
  description = "IDs of bulk scans created"
  value = var.bulk_scan_enabled ? [
    for scan in google_dataplex_datascan.bulk_profile : scan.data_scan_id
  ] : []
}

