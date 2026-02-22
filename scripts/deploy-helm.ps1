# Deploy Agent Guru using Helm
# Usage: .\scripts\deploy-helm.ps1 [-Environment "production"] [-Namespace "agent-guru-production"]

param(
    [string]$Environment = "production",
    [string]$Namespace = "agent-guru-$Environment"
)

$ErrorActionPreference = "Stop"

$ReleaseName = "agent-guru"
$ChartPath = ".\helm\agent-guru"

Write-Host "Deploying Agent Guru to $Environment environment..." -ForegroundColor Green
Write-Host "  Namespace: $Namespace"
Write-Host "  Release: $ReleaseName"

# Create namespace if it doesn't exist
kubectl create namespace "$Namespace" --dry-run=client -o yaml | kubectl apply -f -

# Add labels to namespace
kubectl label namespace "$Namespace" environment="$Environment" app=agent-guru --overwrite

# Deploy using Helm
helm upgrade --install "$ReleaseName" "$ChartPath" `
  --namespace "$Namespace" `
  --values "$ChartPath\values-$Environment.yaml" `
  --wait `
  --timeout 10m `
  --atomic `
  --cleanup-on-fail

if ($LASTEXITCODE -ne 0) {
    Write-Error "Deployment failed!"
    exit 1
}

Write-Host "`nDeployment successful!" -ForegroundColor Green
Write-Host "`nCheck status:"
Write-Host "  kubectl get pods -n $Namespace"
Write-Host "  kubectl get svc -n $Namespace"
Write-Host "  kubectl get ingress -n $Namespace"
Write-Host "`nView logs:"
Write-Host "  kubectl logs -n $Namespace -l app=agent-guru-reasoning --tail=100 -f"
Write-Host "`nRollback if needed:"
Write-Host "  helm rollback $ReleaseName -n $Namespace"
