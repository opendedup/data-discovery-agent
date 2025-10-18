variable "project_id" {
  description = "GCP Project ID for GKE cluster and all resources"
  type        = string
  default     = "lennyisagoodboy"
}

variable "region" {
  description = "GCP region for resources"
  type        = string
  default     = "us-central1"
}

variable "cluster_name" {
  description = "Name of the GKE cluster"
  type        = string
  default     = "data-discovery-cluster"
}

variable "network" {
  description = "Self-link or name of the VPC network"
  type        = string
  default     = "projects/hazel-goal-319318/global/networks/ula"
}

variable "subnetwork" {
  description = "Self-link or name of the subnetwork"
  type        = string
  default     = "projects/hazel-goal-319318/regions/us-central1/subnetworks/ula"
}

variable "machine_type" {
  description = "Machine type for GKE nodes"
  type        = string
  default     = "e2-standard-2"
}

variable "initial_node_count" {
  description = "Initial number of nodes in the node pool"
  type        = number
  default     = 2
}

variable "min_node_count" {
  description = "Minimum number of nodes for autoscaling"
  type        = number
  default     = 1
}

variable "max_node_count" {
  description = "Maximum number of nodes for autoscaling"
  type        = number
  default     = 5
}

variable "jsonl_bucket_name" {
  description = "Name of GCS bucket for JSONL files (Vertex AI Search ingestion)"
  type        = string
  default     = "lennyisagoodboy-data-discovery-jsonl"
}

variable "reports_bucket_name" {
  description = "Name of GCS bucket for Markdown reports"
  type        = string
  default     = "lennyisagoodboy-data-discovery-reports"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

