#!/usr/bin/env pwsh
# Agent Guru - Windows Installer Build Script
# Builds a self-contained Windows installer using PyInstaller + NSIS
#
# Prerequisites:
#   - Python 3.11+ with Agent Guru dependencies installed
#   - PyInstaller: pip install pyinstaller
#   - NSIS 3.x: https://nsis.sourceforge.io/
#
# Usage:
#   .\installer\windows\build_installer.ps1
#   .\installer\windows\build_installer.ps1 -Version "1.0.1" -Silent

param(
    [string]$Version = "1.0.0",
    [switch]$Silent = $false,
    [switch]$SkipBuild = $false
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ROOT = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$DIST_DIR = Join-Path $ROOT "dist\windows"
$INSTALLER_DIR = Join-Path $ROOT "installer\windows"

Write-Host "=== Agent Guru Windows Installer Build ===" -ForegroundColor Cyan
Write-Host "Version: $Version"
Write-Host "Root: $ROOT"

# -------------------------------------------------------
# Step 1: Verify system requirements
# -------------------------------------------------------
Write-Host "`n[1/4] Verifying requirements..." -ForegroundColor Yellow

& python installer\verify_requirements.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "System requirements check failed. Aborting."
    exit 1
}

# Check PyInstaller
$pyinstaller = Get-Command pyinstaller -ErrorAction SilentlyContinue
if (-not $pyinstaller) {
    Write-Host "Installing PyInstaller..." -ForegroundColor Yellow
    pip install pyinstaller --quiet
}

# Check NSIS
$makensis = Get-Command makensis -ErrorAction SilentlyContinue
if (-not $makensis) {
    Write-Error "NSIS not found. Install from https://nsis.sourceforge.io/ and add to PATH."
    exit 1
}

Write-Host "Requirements OK" -ForegroundColor Green

# -------------------------------------------------------
# Step 2: Build Python executable with PyInstaller
# -------------------------------------------------------
if (-not $SkipBuild) {
    Write-Host "`n[2/4] Building Python executable..." -ForegroundColor Yellow

    $specFile = Join-Path $INSTALLER_DIR "agent_guru.spec"

    pyinstaller `
        --name "agent_guru" `
        --onedir `
        --windowed `
        --icon "assets\icon.ico" `
        --add-data "models;models" `
        --add-data "assets;assets" `
        --add-data "Agent_Guru;Agent_Guru" `
        --hidden-import "Agent_Guru.speech" `
        --hidden-import "Agent_Guru.vision" `
        --hidden-import "Agent_Guru.llm" `
        --hidden-import "Agent_Guru.platform" `
        --hidden-import "Agent_Guru.agents" `
        --hidden-import "Agent_Guru.memory" `
        --hidden-import "Agent_Guru.security" `
        --hidden-import "Agent_Guru.policy" `
        --hidden-import "Agent_Guru.avatar" `
        --distpath $DIST_DIR `
        --workpath "build\windows" `
        --noconfirm `
        "Agent_Guru\__main__.py"

    if ($LASTEXITCODE -ne 0) {
        Write-Error "PyInstaller build failed."
        exit 1
    }

    Write-Host "PyInstaller build complete" -ForegroundColor Green
} else {
    Write-Host "`n[2/4] Skipping PyInstaller build (--SkipBuild)" -ForegroundColor Yellow
}

# -------------------------------------------------------
# Step 3: Copy additional files to dist
# -------------------------------------------------------
Write-Host "`n[3/4] Copying additional files..." -ForegroundColor Yellow

$appDist = Join-Path $DIST_DIR "agent_guru"
Copy-Item "README.md" -Destination (Join-Path $appDist "README.txt") -Force
Copy-Item "LICENSE" -Destination (Join-Path $appDist "LICENSE.txt") -Force -ErrorAction SilentlyContinue

Write-Host "Files copied" -ForegroundColor Green

# -------------------------------------------------------
# Step 4: Build NSIS installer
# -------------------------------------------------------
Write-Host "`n[4/4] Building NSIS installer..." -ForegroundColor Yellow

$nsiScript = Join-Path $INSTALLER_DIR "agent_guru.nsi"

$nsisArgs = @(
    "/DAPP_VERSION=$Version",
    $nsiScript
)

if ($Silent) {
    $nsisArgs = @("/V2") + $nsisArgs
}

& makensis @nsisArgs

if ($LASTEXITCODE -ne 0) {
    Write-Error "NSIS build failed."
    exit 1
}

$outputExe = Join-Path $INSTALLER_DIR "AgentGuru-Setup-x64.exe"
Write-Host "`n=== Build Complete ===" -ForegroundColor Green
Write-Host "Installer: $outputExe" -ForegroundColor Cyan
Write-Host "Size: $([math]::Round((Get-Item $outputExe).Length / 1MB, 1)) MB"
