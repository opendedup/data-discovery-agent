# Kubernetes provider configuration for GenAI Toolbox deployment

terraform {
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
  }
}

# Kubernetes provider will be configured by the parent module
# using the GKE cluster credentials

