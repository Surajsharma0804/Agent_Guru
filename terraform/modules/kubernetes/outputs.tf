# Kubernetes Module Outputs

output "cluster_id" {
  description = "Kubernetes cluster ID"
  value       = var.cloud_provider == "aws" ? aws_eks_cluster.main[0].id : null
}

output "cluster_name" {
  description = "Kubernetes cluster name"
  value       = var.cloud_provider == "aws" ? aws_eks_cluster.main[0].name : null
}

output "cluster_endpoint" {
  description = "Kubernetes API endpoint"
  value       = var.cloud_provider == "aws" ? aws_eks_cluster.main[0].endpoint : null
}

output "cluster_ca_certificate" {
  description = "Cluster CA certificate"
  value       = var.cloud_provider == "aws" ? base64decode(aws_eks_cluster.main[0].certificate_authority[0].data) : null
  sensitive   = true
}

output "cluster_security_group_id" {
  description = "Security group ID for the cluster"
  value       = var.cloud_provider == "aws" ? aws_security_group.eks_cluster[0].id : null
}

output "node_role_arn" {
  description = "IAM role ARN for nodes"
  value       = var.cloud_provider == "aws" ? aws_iam_role.eks_node[0].arn : null
}

output "oidc_provider_arn" {
  description = "OIDC provider ARN for IRSA"
  value       = var.cloud_provider == "aws" ? aws_iam_openid_connect_provider.eks[0].arn : null
}

output "kubeconfig" {
  description = "Kubeconfig for cluster access"
  value = var.cloud_provider == "aws" ? {
    apiVersion      = "v1"
    kind            = "Config"
    current-context = aws_eks_cluster.main[0].name
    clusters = [{
      name = aws_eks_cluster.main[0].name
      cluster = {
        certificate-authority-data = aws_eks_cluster.main[0].certificate_authority[0].data
        server                     = aws_eks_cluster.main[0].endpoint
      }
    }]
    contexts = [{
      name = aws_eks_cluster.main[0].name
      context = {
        cluster = aws_eks_cluster.main[0].name
        user    = aws_eks_cluster.main[0].name
      }
    }]
    users = [{
      name = aws_eks_cluster.main[0].name
      user = {
        exec = {
          apiVersion = "client.authentication.k8s.io/v1beta1"
          command    = "aws"
          args = [
            "eks",
            "get-token",
            "--cluster-name",
            aws_eks_cluster.main[0].name
          ]
        }
      }
    }]
  } : null
  sensitive = true
}
