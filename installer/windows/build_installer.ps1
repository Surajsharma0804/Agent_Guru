#!/usr/bin/env pwsh
# Agent Guru - build the small Windows installer.
#
# Freezes the launcher with PyInstaller (AgentGuru.spec) and packs it with the
# application source using Inno Setup (AgentGuru_setup.iss). Packages and models
# are not in the installer: GENESIS fetches them after the person approves a plan.
#
# Prerequisites:
#   - A venv holding only PyInstaller and pywebview, named with -BuildVenv, so
#     nothing else in an environment can be frozen by accident. Versions come
#     from the lock:
#         py -3.13 -m venv .buildvenv
#         .buildvenv\Scripts\python -m pip install pyinstaller pywebview -c requirements-lock.txt
#   - Inno Setup 6 or 7 (https://jrsoftware.org/isinfo.php). ISCC.exe on PATH,
#     or in its default folder.
#
# Usage:
#   .\installer\windows\build_installer.ps1 -BuildVenv .buildvenv

param(
    [string]$BuildVenv = ".buildvenv",
    [switch]$SkipFreeze = $false
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Root
$started = Get-Date

if (-not $SkipFreeze) {
    $python = Join-Path $BuildVenv "Scripts\python.exe"
    if (-not (Test-Path $python)) { throw "No build venv at $BuildVenv. See the top of this script." }
    & $python -m PyInstaller AgentGuru.spec --noconfirm
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }
}

$iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
$candidates = @(
    $(if ($iscc) { $iscc.Source }),
    "$env:ProgramFiles\Inno Setup 7\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) }
if (-not $candidates) { throw "Inno Setup was not found. Install it from https://jrsoftware.org/isinfo.php" }

# One version number: pyproject.toml's.
$version = (Select-String -Path pyproject.toml -Pattern '^version = "(.*)"').Matches[0].Groups[1].Value
& @($candidates)[0] "/DMyAppVersion=$version" AgentGuru_setup.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed." }

$setup = Get-ChildItem dist\AgentGuru-*-Setup.exe | Sort-Object LastWriteTime | Select-Object -Last 1
"{0}: {1:N1} MB in {2:N0} s" -f $setup.Name, ($setup.Length / 1MB), ((Get-Date) - $started).TotalSeconds
