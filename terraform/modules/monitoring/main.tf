# Monitoring Module
# Deploys Prometheus, Grafana, and Jaeger for observability

terraform {
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11"
    }
  }
}

# Create monitoring namespace
resource "kubernetes_namespace" "monitoring" {
  metadata {
    name = var.namespace

    labels = {
      name = var.namespace
    }
  }
}

# Prometheus using Helm
resource "helm_release" "prometheus" {
  name       = "prometheus"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  namespace  = kubernetes_namespace.monitoring.metadata[0].name
  version    = "54.0.0"

  values = [
    yamlencode({
      prometheus = {
        prometheusSpec = {
          retention          = "${var.prometheus_retention_days}d"
          storageSpec = {
            volumeClaimTemplate = {
              spec = {
                accessModes = ["ReadWriteOnce"]
                resources = {
                  requests = {
                    storage = var.prometheus_storage_size
                  }
                }
              }
            }
          }
          resources = {
            requests = {
              cpu    = "500m"
              memory = "2Gi"
            }
            limits = {
              cpu    = "2000m"
              memory = "4Gi"
            }
          }
        }
      }
      grafana = {
        enabled = false  # We'll deploy Grafana separately
      }
      alertmanager = {
        enabled = var.enable_alertmanager
        alertmanagerSpec = {
          storage = {
            volumeClaimTemplate = {
              spec = {
                accessModes = ["ReadWriteOnce"]
                resources = {
                  requests = {
                    storage = "10Gi"
                  }
                }
              }
            }
          }
        }
      }
    })
  ]

  depends_on = [kubernetes_namespace.monitoring]
}

# Grafana using Helm
resource "helm_release" "grafana" {
  name       = "grafana"
  repository = "https://grafana.github.io/helm-charts"
  chart      = "grafana"
  namespace  = kubernetes_namespace.monitoring.metadata[0].name
  version    = "7.0.0"

  values = [
    yamlencode({
      adminPassword = var.grafana_admin_password
      persistence = {
        enabled = true
        size    = "10Gi"
      }
      datasources = {
        "datasources.yaml" = {
          apiVersion = 1
          datasources = [
            {
              name      = "Prometheus"
              type      = "prometheus"
              url       = "http://prometheus-kube-prometheus-prometheus:9090"
              access    = "proxy"
              isDefault = true
            },
            {
              name   = "Jaeger"
              type   = "jaeger"
              url    = "http://jaeger-query:16686"
              access = "proxy"
            }
          ]
        }
      }
      dashboardProviders = {
        "dashboardproviders.yaml" = {
          apiVersion = 1
          providers = [
            {
              name            = "default"
              orgId           = 1
              folder          = ""
              type            = "file"
              disableDeletion = false
              editable        = true
              options = {
                path = "/var/lib/grafana/dashboards/default"
              }
            }
          ]
        }
      }
      dashboards = {
        default = {
          kubernetes-cluster = {
            gnetId    = 7249
            revision  = 1
            datasource = "Prometheus"
          }
          kubernetes-pods = {
            gnetId    = 6417
            revision  = 1
            datasource = "Prometheus"
          }
        }
      }
      service = {
        type = "LoadBalancer"
      }
      resources = {
        requests = {
          cpu    = "250m"
          memory = "512Mi"
        }
        limits = {
          cpu    = "500m"
          memory = "1Gi"
        }
      }
    })
  ]

  depends_on = [kubernetes_namespace.monitoring, helm_release.prometheus]
}

# Jaeger using Helm
resource "helm_release" "jaeger" {
  name       = "jaeger"
  repository = "https://jaegertracing.github.io/helm-charts"
  chart      = "jaeger"
  namespace  = kubernetes_namespace.monitoring.metadata[0].name
  version    = "0.71.0"

  values = [
    yamlencode({
      provisionDataStore = {
        cassandra = false
      }
      allInOne = {
        enabled = true
        resources = {
          requests = {
            cpu    = "250m"
            memory = "512Mi"
          }
          limits = {
            cpu    = "1000m"
            memory = "2Gi"
          }
        }
      }
      storage = {
        type = "memory"
      }
      agent = {
        enabled = false
      }
      collector = {
        enabled = false
      }
      query = {
        enabled = false
      }
    })
  ]

  depends_on = [kubernetes_namespace.monitoring]
}

# ServiceMonitor for Agent Guru application
resource "kubernetes_manifest" "agent_guru_servicemonitor" {
  manifest = {
    apiVersion = "monitoring.coreos.com/v1"
    kind       = "ServiceMonitor"
    metadata = {
      name      = "agent-guru-reasoning-engine"
      namespace = kubernetes_namespace.monitoring.metadata[0].name
      labels = {
        app = "agent-guru"
      }
    }
    spec = {
      selector = {
        matchLabels = {
          app = "agent-guru-reasoning-engine"
        }
      }
      endpoints = [
        {
          port     = "metrics"
          interval = "30s"
          path     = "/metrics"
        }
      ]
    }
  }

  depends_on = [helm_release.prometheus]
}

# AlertManager configuration
resource "kubernetes_config_map" "alertmanager_config" {
  count = var.enable_alertmanager ? 1 : 0

  metadata {
    name      = "alertmanager-config"
    namespace = kubernetes_namespace.monitoring.metadata[0].name
  }

  data = {
    "alertmanager.yml" = yamlencode({
      global = {
        resolve_timeout = "5m"
      }
      route = {
        group_by        = ["alertname", "cluster", "service"]
        group_wait      = "10s"
        group_interval  = "10s"
        repeat_interval = "12h"
        receiver        = "default"
        routes = [
          {
            match = {
              alertname = "Watchdog"
            }
            receiver = "null"
          }
        ]
      }
      receivers = [
        {
          name = "default"
          webhook_configs = var.alert_webhook_url != "" ? [
            {
              url = var.alert_webhook_url
            }
          ] : []
        },
        {
          name = "null"
        }
      ]
    })
  }

  depends_on = [kubernetes_namespace.monitoring]
}
