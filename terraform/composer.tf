# ------------------------------------------------------------------------------
# Cloud Composer for Airflow Orchestration
# ------------------------------------------------------------------------------

resource "google_composer_environment" "data_discovery_agent" {
  name   = var.composer_env_name
  region = var.composer_region

  labels = {
    environment = var.environment
    team        = "data-discovery"
    managed_by  = "terraform"
  }

  config {
    software_config {
      image_version = var.composer_image_version
      
      # Environment variables for DAGs to access configuration
      env_variables = {
        GCP_PROJECT_ID      = var.project_id
        GCS_JSONL_BUCKET    = var.jsonl_bucket_name
        GCS_REPORTS_BUCKET  = var.reports_bucket_name
        VERTEX_DATASTORE_ID = var.vertex_datastore_id
        VERTEX_LOCATION     = var.vertex_location
        BQ_DATASET          = var.bq_dataset
        BQ_TABLE            = var.bq_table
        BQ_LOCATION         = var.bq_location
        ENVIRONMENT         = var.environment
      }
      
      # Install PyPI packages required by the discovery agent.
      # This list should be kept in sync with pyproject.toml
      pypi_packages = {
        "google-cloud-aiplatform"   = ""
        "google-cloud-bigquery"     = ""
        "google-cloud-storage"      = ""
        "google-generativeai"       = ""
        "python-dotenv"             = ""
        "pydantic"                  = ""
        "google-cloud-datacatalog"  = ""
        "google-cloud-dlp"          = ""
        "google-cloud-logging"      = ""
        "google-cloud-monitoring"   = ""
      }
    }

    # Use a small environment for cost-effectiveness. Composer 3 uses a different sizing model.
    environment_size = "ENVIRONMENT_SIZE_SMALL"

    node_config {
      network         = var.network
      subnetwork      = var.subnetwork
      service_account = google_service_account.composer_sa.email
    }

    workloads_config {
      worker {
        min_count  = 1
        max_count  = 3
        cpu        = 8
        memory_gb  = 16
        storage_gb = 10
      }
    }
  }

  project = var.project_id

  depends_on = [
    google_service_account.composer_sa,
    google_project_iam_member.composer_worker,
    google_project_iam_member.composer_sa_log_writer,
    google_project_iam_member.composer_sa_metric_writer,
    google_project_iam_member.composer_bq_metadata_viewer,
    google_project_iam_member.composer_bq_data_viewer,
    google_project_iam_member.composer_bq_data_editor,
    google_project_iam_member.composer_bq_job_user,
    google_project_iam_member.composer_datacatalog_viewer,
    google_project_iam_member.composer_aiplatform_user,
    google_project_iam_member.composer_dlp_reader,
    google_project_iam_member.composer_dataplex_viewer,
    google_project_iam_member.composer_dataplex_dataScanAdmin,
    google_storage_bucket_iam_member.jsonl_bucket_composer,
    google_storage_bucket_iam_member.reports_bucket_composer
  ]
}
