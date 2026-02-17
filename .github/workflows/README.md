# CI/CD Pipeline Documentation

## Overview

This directory contains GitHub Actions workflows for continuous integration and deployment of the Agent Guru Core Reasoning Engine.

## Workflows

### CI Pipeline (`ci.yml`)

Runs on every pull request to `main` or `develop` branches.

**Stages:**

1. **Linting** (runs first, blocks other stages on failure)
   - Black code formatting check
   - Ruff linting
   - mypy type checking with strict mode

2. **Unit Tests** (runs after linting passes)
   - Runs on Python 3.11 and 3.12
   - Requires 80% minimum code coverage
   - Uploads coverage reports to Codecov

3. **Property-Based Tests** (runs after linting passes)
   - Runs Hypothesis property tests
   - Minimum 100 iterations per property
   - Uses deterministic seed in CI for reproducibility

4. **Security Scanning** (runs after linting passes)
   - Bandit security scan for code vulnerabilities
   - Safety check for dependency vulnerabilities
   - Uploads security reports as artifacts

5. **Build Verification** (runs after all tests pass)
   - Builds Python package
   - Verifies package installation

### CD Pipeline (`cd.yml`)

Runs on:
- Push to `main` branch → deploys to staging
- Push of version tags (`v*.*.*`) → deploys to production
- Manual workflow dispatch

**Stages:**

1. **Build Docker Image**
   - Multi-stage build for optimized production image
   - Pushes to GitHub Container Registry (ghcr.io)
   - Generates SBOM (Software Bill of Materials)
   - Tags with version, branch, and SHA

2. **Deploy to Staging** (automatic on main branch)
   - Deploys to Kubernetes staging namespace
   - Runs smoke tests
   - Automatic rollback on failure

3. **Deploy to Production** (on version tags with approval)
   - Requires manual approval via GitHub environment protection
   - Creates deployment backup
   - Deploys to Kubernetes production namespace
   - Runs comprehensive health checks
   - Automatic rollback on failure
   - Creates GitHub release

## Setup Requirements

### Secrets

Configure these secrets in GitHub repository settings:

- `KUBE_CONFIG_STAGING`: Base64-encoded kubeconfig for staging cluster
- `KUBE_CONFIG_PRODUCTION`: Base64-encoded kubeconfig for production cluster
- `GITHUB_TOKEN`: Automatically provided by GitHub Actions

### Kubernetes Secrets

Create these secrets in your Kubernetes clusters:

```bash
# GitHub Container Registry pull secret
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=<github-username> \
  --docker-password=<github-token> \
  -n agent-guru-staging

# Application secrets (production)
kubectl create secret generic agent-guru-secrets \
  --from-literal=sentry-dsn=<sentry-dsn> \
  --from-literal=openai-api-key=<openai-key> \
  --from-literal=anthropic-api-key=<anthropic-key> \
  -n agent-guru-production
```

### GitHub Environments

Configure these environments with protection rules:

1. **staging**
   - URL: https://staging.agent-guru.example.com
   - No approval required

2. **production**
   - URL: https://agent-guru.example.com
   - Require approval from designated reviewers
   - Restrict to version tags only

## Usage

### Running CI

CI runs automatically on pull requests. To run manually:

```bash
gh workflow run ci.yml
```

### Deploying to Staging

Push to main branch:

```bash
git push origin main
```

### Deploying to Production

Create and push a version tag:

```bash
git tag v1.0.0
git push origin v1.0.0
```

### Manual Deployment

Trigger manual deployment via GitHub UI or CLI:

```bash
gh workflow run cd.yml -f environment=staging
gh workflow run cd.yml -f environment=production
```

## Monitoring

### CI Status

Check CI status on pull requests or via:

```bash
gh run list --workflow=ci.yml
```

### Deployment Status

Check deployment status:

```bash
gh run list --workflow=cd.yml
```

### Kubernetes Status

Check deployment status in Kubernetes:

```bash
# Staging
kubectl get pods -n agent-guru-staging
kubectl rollout status deployment/agent-guru-reasoning -n agent-guru-staging

# Production
kubectl get pods -n agent-guru-production
kubectl rollout status deployment/agent-guru-reasoning -n agent-guru-production
```

## Rollback

### Automatic Rollback

Both staging and production deployments automatically rollback on failure.

### Manual Rollback

If needed, manually rollback:

```bash
# Staging
kubectl rollout undo deployment/agent-guru-reasoning -n agent-guru-staging

# Production
kubectl rollout undo deployment/agent-guru-reasoning -n agent-guru-production
```

## Troubleshooting

### CI Failures

1. **Linting failures**: Run locally before pushing
   ```bash
   black Agent_Guru/
   ruff check Agent_Guru/
   mypy Agent_Guru/reasoning --strict
   ```

2. **Test failures**: Run tests locally
   ```bash
   pytest Agent_Guru/reasoning/tests -v
   ```

3. **Coverage failures**: Check coverage report
   ```bash
   pytest --cov=Agent_Guru/reasoning --cov-report=html
   open htmlcov/index.html
   ```

### Deployment Failures

1. Check workflow logs in GitHub Actions
2. Check Kubernetes pod logs:
   ```bash
   kubectl logs -n agent-guru-staging -l app=agent-guru-reasoning
   ```
3. Check deployment events:
   ```bash
   kubectl describe deployment agent-guru-reasoning -n agent-guru-staging
   ```

## Best Practices

1. Always create pull requests for code changes
2. Ensure CI passes before merging
3. Use semantic versioning for releases (v1.2.3)
4. Test in staging before production deployment
5. Monitor deployments and rollback if issues detected
6. Keep secrets secure and rotate regularly
