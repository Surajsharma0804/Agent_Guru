# Build and push Docker images for Agent_Guru Reasoning Engine
# Usage: .\scripts\build-docker.ps1 [-Version "1.0.0"] [-Registry "ghcr.io/agent-guru"] [-Push]

param(
    [string]$Version = "latest",
    [string]$Registry = "ghcr.io/agent-guru",
    [switch]$Push
)

$ErrorActionPreference = "Stop"

# Configuration
$ImageName = "agent-guru"
$FullImage = "$Registry/$ImageName:$Version"

# Build arguments
$BuildDate = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$VcsRef = (git rev-parse --short HEAD)

Write-Host "Building Docker image..." -ForegroundColor Green
Write-Host "  Image: $FullImage"
Write-Host "  Build Date: $BuildDate"
Write-Host "  VCS Ref: $VcsRef"
Write-Host "  Version: $Version"

# Build the image with layer caching
docker build `
  --build-arg BUILD_DATE="$BuildDate" `
  --build-arg VCS_REF="$VcsRef" `
  --build-arg VERSION="$Version" `
  --cache-from "$FullImage" `
  --tag "$FullImage" `
  --tag "$Registry/$ImageName:latest" `
  --file Dockerfile `
  .

if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker build failed!"
    exit 1
}

Write-Host "`nImage built successfully!" -ForegroundColor Green

# Show image size
Write-Host "`nImage size:"
docker images "$FullImage" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"

# Push to registry if requested
if ($Push) {
    Write-Host "`nPushing image to registry..." -ForegroundColor Yellow
    docker push "$FullImage"
    
    if ($Version -ne "latest") {
        docker push "$Registry/$ImageName:latest"
    }
    
    Write-Host "Image pushed successfully!" -ForegroundColor Green
}

Write-Host "`nDone!" -ForegroundColor Green
