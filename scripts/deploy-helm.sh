#!/bin/bash
# Deploy Agent Guru using Helm
# Usage: ./scripts/deploy-helm.sh [environment] [namespace]

set -e

# Configuration
ENVIRONMENT=${1:-"production"}
NAMESPACE=${2:-"agent-guru-${ENVIRONMENT}"}
RELEASE_NAME="agent-guru"
CHART_PATH="./helm/agent-guru"

echo "Deploying Agent Guru to ${ENVIRONMENT} environment..."
echo "  Namespace: ${NAMESPACE}"
echo "  Release: ${RELEASE_NAME}"

# Create namespace if it doesn't exist
kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

# Add labels to namespace
kubectl label namespace "${NAMESPACE}" environment="${ENVIRONMENT}" app=agent-guru --overwrite

# Deploy using Helm
helm upgrade --install "${RELEASE_NAME}" "${CHART_PATH}" \
  --namespace "${NAMESPACE}" \
  --values "${CHART_PATH}/values-${ENVIRONMENT}.yaml" \
  --wait \
  --timeout 10m \
  --atomic \
  --cleanup-on-fail

echo ""
echo "Deployment successful!"
echo ""
echo "Check status:"
echo "  kubectl get pods -n ${NAMESPACE}"
echo "  kubectl get svc -n ${NAMESPACE}"
echo "  kubectl get ingress -n ${NAMESPACE}"
echo ""
echo "View logs:"
echo "  kubectl logs -n ${NAMESPACE} -l app=agent-guru-reasoning --tail=100 -f"
echo ""
echo "Rollback if needed:"
echo "  helm rollback ${RELEASE_NAME} -n ${NAMESPACE}"
