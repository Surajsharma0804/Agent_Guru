# GURU Personal Assistant - Production Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying the GURU Personal Assistant System in production environments. The system is designed for security-conscious users requiring cryptographic audit logging, multi-factor biometric authentication, and cross-platform automation.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [System Requirements](#system-requirements)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Security Setup](#security-setup)
6. [Testing](#testing)
7. [Deployment](#deployment)
8. [Monitoring](#monitoring)
9. [Maintenance](#maintenance)
10. [Troubleshooting](#troubleshooting)

## Prerequisites

### Windows Desktop

**Required:**
- Windows 10 (version 1809 or later) or Windows 11
- Windows Hello capable device (fingerprint reader or IR camera)
- Python 3.11 or later
- Node.js 18 or later
- 8GB RAM minimum (16GB recommended)
- 10GB free disk space

**Optional:**
- Rust toolchain (for building from source)
- Visual Studio Build Tools (for native modules)

### macOS Desktop

**Required:**
- macOS 11 (Big Sur) or later
- Touch ID or Face ID capable device
- Python 3.11 or later
- Node.js 18 or later
- Xcode Command Line Tools
- 8GB RAM minimum (16GB recommended)
- 10GB free disk space

### Android Phone

**Required:**
- Android 8.0 (API level 26) or later
- Biometric authentication capability (fingerprint or face)
- 2GB RAM minimum (4GB recommended)
- 500MB free storage

### iOS Phone

**Required:**
- iOS 14 or later
- Face ID or Touch ID capable device
- 2GB RAM minimum (4GB recommended)
- 500MB free storage

## System Requirements

### Network Requirements

- **Desktop-to-Phone Communication**: Local network connectivity (Wi-Fi or USB)
- **LLM Access**: Internet connection for cloud LLM providers (optional)
- **Ollama**: Local network access if using remote Ollama instance

### Security Requirements

- **Biometric Hardware**: Functional biometric authentication device
- **Secure Boot**: Recommended for production deployments
- **TPM 2.0**: Recommended for hardware-backed cryptography (Windows)
- **Secure Enclave**: Used automatically on macOS and iOS

### Performance Requirements

- **Application Launch**: <1 second
- **Text Automation**: <2 seconds
- **Intent Processing**: <10 milliseconds (deterministic), <10 seconds (LLM)
- **TTS Synthesis**: <5 seconds
- **Health Checks**: <5 seconds per component

## Installation

### Step 1: Clone Repository

```bash
git clone https://github.com/your-org/guru-personal-assistant.git
cd guru-personal-assistant
```

### Step 2: Install Dependencies

**Root Dependencies:**
```bash
npm install
```

**Desktop Agent (Python):**
```bash
cd desktop-agent
pip install -r requirements.txt
cd ..
```

**Desktop Agent (Node.js):**
```bash
cd agents
npm install
cd ..
```

**Phone Agent (Android):**
```bash
cd phone-agent
./gradlew build
cd ..
```

### Step 3: Build Production Artifacts

**Desktop Agent:**
```bash
cd desktop-agent
python -m build
cd ..
```

**TypeScript Components:**
```bash
npm run build
```

**Android APK:**
```bash
cd phone-agent
./gradlew assembleRelease
cd ..
```

### Step 4: Verify Installation

```bash
# Run diagnostic script
cd desktop-agent
python run_diagnostics.py
cd ..
```

## Configuration

### Desktop Agent Configuration

**Location:** `%USERPROFILE%\.guru\config.yaml` (Windows) or `~/.guru/config.yaml` (macOS)

```yaml
# Security Configuration
security:
  biometric_policy: "medium_risk"  # low_risk, medium_risk, high_risk
  session_timeout: 300             # seconds (5 minutes)
  intrusion_threshold: 3           # failed authentication attempts
  authority_scope: "system_wide"   # system_wide (desktop) or app_level (mobile)

# Cryptography Configuration
cryptography:
  al