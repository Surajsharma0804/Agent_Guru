# Monitoring Module Outputs

output "prometheus_endpoint" {
  description = "Prometheus endpoint"
  value       = "http://prometheus-kube-prometheus-prometheus.${var.namespace}.svc.cluster.local:9090"
}

output "grafana_endpoint" {
  description = "Grafana endpoint (external LoadBalancer)"
  value       = "Check kubectl get svc -n ${var.namespace} grafana for external IP"
}

output "jaeger_endpoint" {
  description = "Jaeger query endpoint"
  value       = "http://jaeger-query.${var.namespace}.svc.cluster.local:16686"
}

output "namespace" {
  description = "Monitoring namespace"
  value       = var.namespace
}
