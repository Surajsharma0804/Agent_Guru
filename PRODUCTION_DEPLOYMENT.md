# GURU Personal Assistant - Production Deployment Guide

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Pre-Deployment Checklist](#pre-deployment-checklist)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Security Hardening](#security-hardening)
6. [Monitoring & Maintenance](#monitoring--maintenance)
7. [Troubleshooting](#troubleshooting)
8. [Rollback Procedures](#rollback-procedures)

---

## System Requirements

### Windows (Full Support)
- **OS**: Windows 10 (build 1903+) or Windows 11
- **CPU**: Intel Core i5 or AMD Ryzen 5 (4+ cores recommended)
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: 2GB free space (10GB recommended for models)
- **Biometric**: Windows Hello compatible device (fingerprint reader or IR camera)
- **Audio**: Microphone and speakers/headphones
- **Network**: Internet connection for initial setup (optional for operation)

### macOS (Full Support)
- **OS**: macOS 11 Big Sur or later
- **CPU**: Intel or Apple Silicon (M1/M2/M3)
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: 2GB free space (10GB recommended for models)
- **Biometric**: Touch ID or Face ID
- **Audio**: Microphone and speakers/headphones
- **Permissions**: Accessibility, Microphone, Automation

### Android (Partial Support)
- **OS**: Android 10 or later
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 1GB free space
- **Biometric**: Fingerprint or Face Unlock
- **Permissions**: Accessibility Service, Microphone

### iOS (Limited Support)
- **OS**: iOS 15 or later
- **RAM**: 4GB minimum
- **Storage**: 500MB free space
- **Biometric**: Touch ID or Face ID
- **Limitations**: No input automation, app-level authority only

---

## Pre-Deployment Checklist

### Security Verification
- [ ] All 117 property-based tests passing
- [ ] Zero security vulnerabilities in dependency scan
- [ ] Audit log integrity verification passing
- [ ] Biometric authentication tested and working
- [ ] Authority state machine validated
- [ ] Intrusion detection tested

### Performance Verification
- [ ] Application launch time <1 second
- [ ] Text automation time <2 seconds
- [ ] Intent pre-filter time <10 milliseconds
- [ ] TTS synthesis time <5 seconds
- [ ] LLM response time <10 seconds (with fallback)
- [ ] Health check time <5 seconds per component

### Functional Verification
- [ ] Voice recognition working (wake word detection)
- [ ] TTS output working (speech synthesis)
- [ ] Application launching working (100+ apps tested)
- [ ] WhatsApp automation working (if required)
- [ ] Dictation mode working
- [ ] Memory system working (encryption + search)

### Documentation Verification
- [ ] README.md updated
- [ ] CHANGELOG.md complete
- [ ] DEPLOYMENT.md reviewed
- [ ] SECURITY.md reviewed
- [ ] API documentation generated

---

## Installation

### Windows Installation

#### Option 1: Installer (Recommended)
```powershell
# Download installer
Invoke-WebRequest -Uri "https://releases.guru-assistant.com/v1.0.0/GURU-Setup-Windows-x64.exe" -OutFile "GURU-Setup.exe"

# Run installer (requires admin)
.\GURU-Setup.exe
```

#### Option 2: Portable
```powershell
# Download portable package
Invoke-WebRequest -Uri "https://releases.guru-assistant.com/v1.0.0/GURU-Portable-Windows-x64.zip" -OutFile "GURU-Portable.zip"

# Extract
Expand-Archive -Path "GURU-Portable.zip" -DestinationPath "C:\GURU"

# Run
cd C:\GURU
.\launch_guru.exe
```

#### Option 3: From Source
```powershell
# Clone repository
git clone https://github.com/your-org/guru-personal-assistant.git
cd guru-personal-assistant

# Install Python dependencies
cd desktop-agent
pip install -r requirements.txt

# Install Node.js dependencies
cd ..
npm install

# Build
npm run build:desktop

# Run
python desktop-agent/launch_guru.py
```

### macOS Installation

#### Option 1: DMG (Recommended)
```bash
# Download DMG
curl -L "https://releases.guru-assistant.com/v1.0.0/GURU-macOS-x64.dmg" -o GURU.dmg

# Mount and install
hdiutil attach GURU.dmg
cp -R "/Volumes/GURU/GURU.app" /Applications/
hdiutil detach "/Volumes/GURU"
```

#### Option 2: Homebrew
```bash
# Add tap
brew tap your-org/guru

# Install
brew install guru-assistant

# Run
guru
```

### Android Installation

```bash
# Download APK
curl -L "https://releases.guru-assistant.com/v1.0.0/GURU-Android-arm64.apk" -o GURU.apk

# Install (requires adb)
adb install GURU.apk

# Or install from Google Play Store
# https://play.google.com/store/apps/details?id=com.guru.assistant
```

### iOS Installation

```bash
# Install from App Store
# https://apps.apple.com/app/guru-personal-assistant/id123456789

# Or TestFlight (beta)
# https://testflight.apple.com/join/XXXXXXXX
```

---

## Configuration

### First-Time Setup

1. **Launch Application**
   ```bash
   # Windows
   launch_guru.exe
   
   # macOS
   open /Applications/GURU.app
   
   # Linux
   ./launch_guru.sh
   ```

2. **Setup Wizard**
   - Grant microphone permission
   - Grant speaker permission
   - Create user profile
   - Configure biometric authentication
   - Test biometric authentication
   - Set preferences (wake word, timeout, etc.)

3. **LLM Configuration** (Optional)
   
   **Option A: Ollama (Local, Recommended)**
   ```bash
   # Install Ollama
   curl -fsSL https://ollama.com/install.sh | sh
   
   # Pull models
   ollama pull llama3.2:3b  # Conversation
   ollama pull llama3.2:1b  # Intent classification
   ollama pull llama3.2:3b  # Reasoning
   
   # GURU will auto-detect Ollama models
   ```
   
   **Option B: OpenAI (Cloud)**
   ```bash
   # Set API key
   export OPENAI_API_KEY="sk-..."
   
   # Or configure in GUI
   # Settings → LLM → OpenAI → API Key
   ```
   
   **Option C: Gemini (Cloud)**
   ```bash
   # Set API key
   export GEMINI_API_KEY="..."
   
   # Or configure in GUI
   # Settings → LLM → Gemini → API Key
   ```

### Configuration Files

**User Configuration**: `%USERPROFILE%\.guru\config.json` (Windows) or `~/.guru/config.json` (macOS/Linux)

```json
{
  "user": {
    "name": "John Doe",
    "profile_id": "user_12345",
    "language": "en-US"
  },
  "authority": {
    "timeout_seconds": 300,
    "require_biometric": true,
    "lockout_attempts": 3
  },
  "voice": {
    "wake_word": "hey guru",
    "dictation_silence_timeout": 2.0,
    "voice_model": "whisper-base"
  },
  "tts": {
    "voice": "default",
    "rate": 1.0,
    "volume": 1.0
  },
  "memory": {
    "retention_days": 90,
    "enable_encryption": true
  },
  "llm": {
    "provider": "ollama",
    "conversation_model": "llama3.2:3b",
    "intent_model": "llama3.2:1b",
    "reasoning_model": "llama3.2:3b",
    "timeout_seconds": 10
  }
}
```

**LLM Configuration**: `%USERPROFILE%\.guru\llm_config.json`

```json
{
  "providers": {
    "ollama": {
      "enabled": true,
      "base_url": "http://localhost:11434",
      "models": {
        "conversation": "llama3.2:3b",
        "intent": "llama3.2:1b",
        "reasoning": "llama3.2:3b"
      }
    },
    "openai": {
      "enabled": false,
      "api_key": "sk-...",
      "models": {
        "conversation": "gpt-4",
        "intent": "gpt-3.5-turbo",
        "reasoning": "gpt-4"
      }
    },
    "gemini": {
      "enabled": false,
      "api_key": "...",
      "models": {
        "conversation": "gemini-pro",
        "intent": "gemini-pro",
        "reasoning": "gemini-pro"
      }
    }
  }
}
```

---

## Security Hardening

### 1. Biometric Authentication

**Windows Hello Setup:**
```powershell
# Verify Windows Hello is available
Get-WindowsHelloStatus

# Enable Windows Hello
# Settings → Accounts → Sign-in options → Windows Hello
```

**macOS Touch ID/Face ID:**
```bash
# Verify biometric hardware
system_profiler SPBiometricDataType

# Enable in System Preferences
# System Preferences → Touch ID & Password
```

### 2. Audit Log Protection

**Enable Tamper Detection:**
```json
{
  "audit": {
    "enable_signature_chain": true,
    "enable_tamper_detection": true,
    "log_rotation_days": 1,
    "compression_enabled": true
  }
}
```

**Verify Audit Log Integrity:**
```bash
# Run integrity check
python -m src.audit.integrity_verifier --verify-all

# Expected output: "All audit logs verified successfully"
```

### 3. Memory Encryption

**Verify Encryption:**
```bash
# Check encryption status
python -m src.memory.encryption --status

# Expected output: "AES-256-GCM encryption enabled"
```

### 4. Network Security

**Disable Cloud LLMs (Optional):**
```json
{
  "llm": {
    "provider": "ollama",
    "allow_cloud_providers": false
  }
}
```

**Firewall Rules:**
```powershell
# Windows: Block outbound (if local-only)
New-NetFirewallRule -DisplayName "GURU Local Only" -Direction Outbound -Program "C:\Program Files\GURU\guru.exe" -Action Block

# macOS: Use Little Snitch or similar
```

### 5. Skill Sandboxing

**Enable Strict Sandboxing:**
```json
{
  "skills": {
    "enable_sandbox": true,
    "allow_network": false,
    "allow_filesystem": false,
    "max_memory_mb": 256,
    "max_cpu_percent": 50
  }
}
```

---

## Monitoring & Maintenance

### Health Monitoring

**Check System Health:**
```bash
# Run diagnostics
python run_diagnostics.py

# Expected output:
# ✓ TTS synthesis: PASS
# ✓ Voice recognition: PASS
# ✓ Biometric authentication: PASS
# ✓ LLM connectivity: PASS
# ✓ Memory system: PASS
# ✓ Audit logging: PASS
```

**Monitor Component Health:**
```bash
# View health status
curl http://localhost:8080/health

# Expected response:
{
  "status": "healthy",
  "components": {
    "tts_service": "healthy",
    "voice_interface": "healthy",
    "command_executor": "healthy",
    "memory_system": "healthy",
    "audit_logger": "healthy"
  }
}
```

### Log Monitoring

**Audit Logs:**
```bash
# View recent audit events
tail -f ~/.guru/audit_logs/audit_log_2026-01-15.log

# Search for security events
grep "CRITICAL" ~/.guru/audit_logs/*.log
```

**Application Logs:**
```bash
# View application logs
tail -f ~/.guru/logs/guru.log

# Search for errors
grep "ERROR" ~/.guru/logs/*.log
```

### Performance Monitoring

**Intent Pre-Filter Bypass Rate:**
```bash
# Check bypass rate
python -m src.llm.intent_pre_filter --stats

# Expected output: "LLM bypass rate: 75.3% (target: 70%)"
```

**Component Response Times:**
```bash
# Run performance benchmarks
python -m src.production_audit.checkpoint --benchmark

# Expected output:
# Application launch: 0.8s (target: <1s)
# Text automation: 1.2s (target: <2s)
# Intent pre-filter: 8ms (target: <10ms)
# TTS synthesis: 3.5s (target: <5s)
# LLM response: 7.2s (target: <10s)
```

### Maintenance Tasks

**Daily:**
- [ ] Check audit log integrity
- [ ] Monitor component health
- [ ] Review security events

**Weekly:**
- [ ] Run full diagnostic suite
- [ ] Review performance metrics
- [ ] Check disk space usage
- [ ] Update LLM models (if using Ollama)

**Monthly:**
- [ ] Review and archive old audit logs
- [ ] Purge old conversation history (90+ days)
- [ ] Update dependencies
- [ ] Run security scans

**Quarterly:**
- [ ] Full system backup
- [ ] Disaster recovery test
- [ ] Security audit
- [ ] Performance optimization review

---

## Troubleshooting

### Common Issues

#### 1. Voice Recognition Not Working

**Symptoms:**
- Wake word not detected
- No response to voice commands

**Solutions:**
```bash
# Test microphone
python -m src.voice.speech_to_text --test-mic

# Check audio input device
# Windows: Settings → System → Sound → Input
# macOS: System Preferences → Sound → Input

# Verify Whisper model
ls ~/.guru/models/whisper-base.bin

# Re-download if missing
python -m src.voice.whisper_cpp_engine --download-model
```

#### 2. TTS Not Speaking

**Symptoms:**
- No audio output
- Silent responses

**Solutions:**
```bash
# Test TTS
python -m src.gui.tts_service --test

# Check audio output device
# Windows: Settings → System → Sound → Output
# macOS: System Preferences → Sound → Output

# Verify Windows SAPI (Windows only)
Get-Service -Name "AudioSrv" | Restart-Service
```

#### 3. Biometric Authentication Failing

**Symptoms:**
- "Biometric authentication failed" error
- Cannot grant authority

**Solutions:**
```bash
# Test biometric hardware
# Windows:
Get-WindowsHelloStatus

# macOS:
system_profiler SPBiometricDataType

# Re-enroll biometric
# Windows: Settings → Accounts → Sign-in options → Windows Hello
# macOS: System Preferences → Touch ID & Password

# Check audit logs for details
grep "biometric" ~/.guru/audit_logs/*.log
```

#### 4. LLM Timeout

**Symptoms:**
- "LLM request timed out" error
- Slow responses

**Solutions:**
```bash
# Check Ollama status (if using Ollama)
ollama list
curl http://localhost:11434/api/tags

# Restart Ollama
systemctl restart ollama  # Linux
brew services restart ollama  # macOS

# Increase timeout
# Edit config.json:
{
  "llm": {
    "timeout_seconds": 20
  }
}

# Use smaller model
ollama pull llama3.2:1b
```

#### 5. Application Launch Failing

**Symptoms:**
- "Failed to launch application" error
- Application not opening

**Solutions:**
```bash
# Check application database
python -m src.execution.command_executor --list-apps

# Test specific application
python -m src.execution.command_executor --test-launch "notepad"

# Update application database
python -m src.execution.command_executor --rebuild-database

# Check audit logs
grep "application_launch" ~/.guru/audit_logs/*.log
```

#### 6. Memory System Errors

**Symptoms:**
- "Failed to store conversation" error
- "Encryption key not found" error

**Solutions:**
```bash
# Verify encryption key
python -m src.memory.encryption --verify-key

# Re-initialize memory system
python -m src.memory.memory_service --init

# Check database integrity
sqlite3 ~/.guru/memory/conversations.db "PRAGMA integrity_check;"

# Backup and rebuild if corrupted
cp ~/.guru/memory/conversations.db ~/.guru/memory/conversations.db.backup
python -m src.memory.database --rebuild
```

### Debug Mode

**Enable Debug Logging:**
```json
{
  "logging": {
    "level": "DEBUG",
    "console_output": true,
    "file_output": true
  }
}
```

**Run with Debug Output:**
```bash
# Windows
set GURU_DEBUG=1
launch_guru.exe

# macOS/Linux
export GURU_DEBUG=1
./launch_guru.sh
```

---

## Rollback Procedures

### Version Rollback

**Windows:**
```powershell
# Uninstall current version
.\GURU-Uninstall.exe

# Install previous version
.\GURU-Setup-v0.9.0.exe
```

**macOS:**
```bash
# Remove current version
rm -rf /Applications/GURU.app

# Install previous version
hdiutil attach GURU-v0.9.0.dmg
cp -R "/Volumes/GURU/GURU.app" /Applications/
```

### Configuration Rollback

**Restore Previous Configuration:**
```bash
# Backup current config
cp ~/.guru/config.json ~/.guru/config.json.backup

# Restore previous config
cp ~/.guru/config.json.2026-01-14 ~/.guru/config.json

# Restart GURU
```

### Database Rollback

**Restore Previous Database:**
```bash
# Stop GURU
pkill guru

# Backup current database
cp ~/.guru/memory/conversations.db ~/.guru/memory/conversations.db.backup

# Restore previous database
cp ~/.guru/memory/conversations.db.2026-01-14 ~/.guru/memory/conversations.db

# Restart GURU
```

### Audit Log Rollback

**Restore Previous Audit Logs:**
```bash
# Audit logs are append-only and should NOT be rolled back
# Instead, archive current logs and start fresh

# Archive current logs
tar -czf ~/.guru/audit_logs/archive-2026-01-15.tar.gz ~/.guru/audit_logs/*.log

# Clear current logs (DANGEROUS - only if necessary)
rm ~/.guru/audit_logs/*.log

# Restart GURU (will create new log chain)
```

---

## Production Checklist

### Pre-Production
- [ ] All tests passing (395 unit + 117 property)
- [ ] Zero security vulnerabilities
- [ ] Code coverage ≥85%
- [ ] Performance benchmarks met
- [ ] Documentation complete
- [ ] Backup procedures tested
- [ ] Rollback procedures tested

### Production Deployment
- [ ] Install on target system
- [ ] Run setup wizard
- [ ] Configure biometric authentication
- [ ] Test biometric authentication
- [ ] Configure LLM provider
- [ ] Test voice recognition
- [ ] Test TTS output
- [ ] Test application launching
- [ ] Test dictation mode
- [ ] Test memory system
- [ ] Verify audit logging
- [ ] Run full diagnostic suite

### Post-Production
- [ ] Monitor system health (24 hours)
- [ ] Review audit logs (daily)
- [ ] Check performance metrics (weekly)
- [ ] User feedback collection
- [ ] Security incident monitoring
- [ ] Backup verification (weekly)

---

## Support & Resources

### Documentation
- **README.md**: Quick start guide
- **CHANGELOG.md**: Version history
- **SECURITY.md**: Security policy and vulnerability reporting
- **API Documentation**: `docs/api/`
- **Architecture Documentation**: `docs/architecture/`

### Community
- **GitHub Issues**: https://github.com/your-org/guru-personal-assistant/issues
- **Discussions**: https://github.com/your-org/guru-personal-assistant/discussions
- **Discord**: https://discord.gg/guru-assistant

### Security
- **Security Policy**: See SECURITY.md
- **Vulnerability Reporting**: security@guru-assistant.com
- **Security Advisories**: https://github.com/your-org/guru-personal-assistant/security/advisories

### Commercial Support
- **Enterprise Support**: enterprise@guru-assistant.com
- **Training**: training@guru-assistant.com
- **Consulting**: consulting@guru-assistant.com

---

**Built with security, privacy, and user control as first-class requirements.**

**Version 1.0.0 - Production Ready**
