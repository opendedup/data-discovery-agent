# GenAI Toolbox Deployment on GKE
# Phase 0.2: Deploy GenAI Toolbox with BigQuery and Dataplex tools

# Variables for GenAI Toolbox deployment
variable "genai_toolbox_image" {
  description = "GenAI Toolbox container image"
  type        = string
  default     = "gcr.io/google.com/genai-toolbox:latest"  # Update with actual image when available
}

variable "genai_toolbox_replicas" {
  description = "Number of GenAI Toolbox replicas"
  type        = number
  default     = 2
}

variable "genai_toolbox_port" {
  description = "GenAI Toolbox MCP protocol port"
  type        = number
  default     = 8080
}

# Kubernetes namespace (assuming it's created in main terraform)
data "kubernetes_namespace" "data_discovery" {
  metadata {
    name = "data-discovery"
  }
  
  depends_on = [var.cluster_name]
}

# ConfigMap for GenAI Toolbox configuration
resource "kubernetes_config_map" "genai_toolbox_config" {
  metadata {
    name      = "genai-toolbox-config"
    namespace = data.kubernetes_namespace.data_discovery.metadata[0].name
    
    labels = {
      app       = "genai-toolbox"
      component = "data-discovery"
    }
  }

  data = {
    "toolbox-config.yaml" = file("${path.module}/../../config/genai-toolbox/toolbox-config.yaml")
  }
}

# Deployment for GenAI Toolbox
resource "kubernetes_deployment" "genai_toolbox" {
  metadata {
    name      = "genai-toolbox"
    namespace = data.kubernetes_namespace.data_discovery.metadata[0].name
    
    labels = {
      app       = "genai-toolbox"
      component = "data-discovery"
      version   = "1.0.0"
    }
  }

  spec {
    replicas = var.genai_toolbox_replicas

    selector {
      match_labels = {
        app = "genai-toolbox"
      }
    }

    template {
      metadata {
        labels = {
          app       = "genai-toolbox"
          component = "data-discovery"
          version   = "1.0.0"
        }
        
        annotations = {
          # Prometheus scraping annotations
          "prometheus.io/scrape" = "true"
          "prometheus.io/port"   = "8080"
          "prometheus.io/path"   = "/metrics"
        }
      }

      spec {
        # Use Workload Identity
        service_account_name = "discovery-agent"
        
        # Security context
        security_context {
          run_as_non_root = true
          run_as_user     = 1000
          fs_group        = 1000
        }

        container {
          name  = "genai-toolbox"
          image = var.genai_toolbox_image
          
          # Image pull policy
          image_pull_policy = "IfNotPresent"

          # Container ports
          port {
            name           = "mcp"
            container_port = var.genai_toolbox_port
            protocol       = "TCP"
          }

          port {
            name           = "health"
            container_port = 8081
            protocol       = "TCP"
          }

          # Environment variables
          env {
            name  = "GOOGLE_CLOUD_PROJECT"
            value = var.project_id
          }

          env {
            name  = "GOOGLE_APPLICATION_CREDENTIALS"
            value = "/var/secrets/google/key.json"  # Workload Identity doesn't need this, but keeping for compatibility
          }

          env {
            name  = "CONFIG_PATH"
            value = "/config/toolbox-config.yaml"
          }

          env {
            name  = "READ_ONLY_MODE"
            value = "true"
          }

          env {
            name  = "LOG_LEVEL"
            value = "INFO"
          }

          # Resource requests and limits
          resources {
            requests = {
              cpu    = "250m"
              memory = "512Mi"
            }
            limits = {
              cpu    = "1000m"
              memory = "2Gi"
            }
          }

          # Volume mounts
          volume_mount {
            name       = "config"
            mount_path = "/config"
            read_only  = true
          }

          # Liveness probe
          liveness_probe {
            http_get {
              path = "/health"
              port = 8081
            }
            initial_delay_seconds = 30
            period_seconds        = 10
            timeout_seconds       = 5
            failure_threshold     = 3
          }

          # Readiness probe
          readiness_probe {
            http_get {
              path = "/health"
              port = 8081
            }
            initial_delay_seconds = 10
            period_seconds        = 5
            timeout_seconds       = 3
            failure_threshold     = 3
          }

          # Security context
          security_context {
            allow_privilege_escalation = false
            read_only_root_filesystem  = true
            run_as_non_root           = true
            run_as_user               = 1000
            
            capabilities {
              drop = ["ALL"]
            }
          }
        }

        # Volumes
        volume {
          name = "config"
          config_map {
            name = kubernetes_config_map.genai_toolbox_config.metadata[0].name
          }
        }

        # Pod anti-affinity for high availability
        affinity {
          pod_anti_affinity {
            preferred_during_scheduling_ignored_during_execution {
              weight = 100
              pod_affinity_term {
                label_selector {
                  match_expressions {
                    key      = "app"
                    operator = "In"
                    values   = ["genai-toolbox"]
                  }
                }
                topology_key = "kubernetes.io/hostname"
              }
            }
          }
        }
      }
    }

    strategy {
      type = "RollingUpdate"
      rolling_update {
        max_surge       = "1"
        max_unavailable = "0"
      }
    }
  }
}

# Service for GenAI Toolbox (Internal LoadBalancer)
# Note: Uses Internal LB for VPC-only access. Change to ClusterIP for cluster-only access.
resource "kubernetes_service" "genai_toolbox" {
  metadata {
    name      = "genai-toolbox"
    namespace = data.kubernetes_namespace.data_discovery.metadata[0].name
    
    labels = {
      app       = "genai-toolbox"
      component = "data-discovery"
    }
    
    annotations = {
      "cloud.google.com/load-balancer-type" = "Internal"
    }
  }

  spec {
    type = "LoadBalancer"  # Change to "ClusterIP" for cluster-only access
    
    selector = {
      app = "genai-toolbox"
    }

    port {
      name        = "mcp"
      port        = var.genai_toolbox_port
      target_port = var.genai_toolbox_port
      protocol    = "TCP"
    }

    port {
      name        = "health"
      port        = 8081
      target_port = 8081
      protocol    = "TCP"
    }

    session_affinity = "ClientIP"
  }
}

# Horizontal Pod Autoscaler
resource "kubernetes_horizontal_pod_autoscaler_v2" "genai_toolbox" {
  metadata {
    name      = "genai-toolbox"
    namespace = data.kubernetes_namespace.data_discovery.metadata[0].name
  }

  spec {
    scale_target_ref {
      api_version = "apps/v1"
      kind        = "Deployment"
      name        = kubernetes_deployment.genai_toolbox.metadata[0].name
    }

    min_replicas = 2
    max_replicas = 10

    metric {
      type = "Resource"
      resource {
        name = "cpu"
        target {
          type                = "Utilization"
          average_utilization = 70
        }
      }
    }

    metric {
      type = "Resource"
      resource {
        name = "memory"
        target {
          type                = "Utilization"
          average_utilization = 80
        }
      }
    }

    behavior {
      scale_down {
        stabilization_window_seconds = 300
        policy {
          type           = "Percent"
          value          = 50
          period_seconds = 60
        }
      }
      scale_up {
        stabilization_window_seconds = 60
        policy {
          type           = "Percent"
          value          = 100
          period_seconds = 60
        }
      }
    }
  }
}

# Network Policy for GenAI Toolbox
resource "kubernetes_network_policy" "genai_toolbox" {
  metadata {
    name      = "genai-toolbox"
    namespace = data.kubernetes_namespace.data_discovery.metadata[0].name
  }

  spec {
    pod_selector {
      match_labels = {
        app = "genai-toolbox"
      }
    }

    policy_types = ["Ingress", "Egress"]

    # Ingress rules
    ingress {
      from {
        # Allow from same namespace
        namespace_selector {
          match_labels = {
            name = "data-discovery"
          }
        }
      }

      ports {
        protocol = "TCP"
        port     = var.genai_toolbox_port
      }

      ports {
        protocol = "TCP"
        port     = 8081
      }
    }

    # Egress rules
    egress {
      # Allow to GCP APIs
      to {
        ip_block {
          cidr = "0.0.0.0/0"
        }
      }

      ports {
        protocol = "TCP"
        port     = 443
      }
    }

    egress {
      # Allow DNS
      ports {
        protocol = "UDP"
        port     = 53
      }
    }
  }
}

# Outputs
output "genai_toolbox_service_name" {
  description = "Name of the GenAI Toolbox service"
  value       = kubernetes_service.genai_toolbox.metadata[0].name
}

output "genai_toolbox_endpoint" {
  description = "Internal endpoint for GenAI Toolbox MCP protocol"
  value       = "http://${kubernetes_service.genai_toolbox.metadata[0].name}.${data.kubernetes_namespace.data_discovery.metadata[0].name}.svc.cluster.local:${var.genai_toolbox_port}"
}

output "genai_toolbox_health_endpoint" {
  description = "Health check endpoint"
  value       = "http://${kubernetes_service.genai_toolbox.metadata[0].name}.${data.kubernetes_namespace.data_discovery.metadata[0].name}.svc.cluster.local:8081/health"
}

