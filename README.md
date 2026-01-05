# GURU Personal Assistant

**Production-Grade, Cross-Device Personal Automation System**

GURU is a security-hardened, local-first personal assistant system that provides voice-driven automation while maintaining strict security boundaries and user control. Built for advanced users who demand cryptographic security, privacy by default, and explicit consent for all automation.

## 🔒 Security-First Design

**Core Philosophy:** *"GURU treats authority as sacred and convenience as optional."*

- **Authority State Machine**: Eliminates permission fatigue while ensuring no unauthorized automation
- **Multi-Factor Biometric Verification**: Voice + face + fingerprint authentication
- **Cryptographically Signed Audit Logs**: Tamper-evident logging of all actions
- **Fail-Safe Defaults**: System halts on any security boundary violation
- **Local-First Processing**: No cloud dependencies for core security functions

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐
│   Android       │    │   Windows       │
│   Phone Agent   │◄──►│ Desktop Agent   │
│                 │    │                 │
│ • Voice Input   │    │ • Authority     │
│ • Secure Comms  │    │ • Input Control │
│ • Mobile Skills │    │ • Screen Obs    │
└─────────────────┘    └─────────────────┘
                              │
                    ┌─────────┼─────────┐
                    │         │         │
            ┌───────▼───┐ ┌───▼───┐ ┌───▼────┐
            │  Memory   │ │ Skill │ │  LLM   │
            │ Service   │ │Runner │ │Adapter │
            │           │ │       │ │        │
            │• MIRIX    │ │•Sandbox│ │•Multi- │
            │• Local DB │ │•Isolate│ │ Provider│
            │• Encrypted│ │•Secure │ │•Advisory│
            └───────────┘ └───────┘ └────────┘
```

## 🎯 Key Features

### 🔐 **Authority & Security**
- **Multi-Factor Authentication**: Voice recognition + Windows Hello biometrics
- **Intrusion Detection**: Automatic workstation locking on unauthorized access attempts
- **Cryptographic Command Channel**: ECDSA-P256 signed inter-device communication
- **Hardware Security Integration**: TPM 2.0 and HSM support where available

### 🎤 **Voice-Driven Control**
- **Complete Input Simulation**: Full keyboard and mouse control via voice
- **Exact Text Dictation**: Type exactly what you speak, no interpretation
- **Command vs Dictation Modes**: Clear separation between commands and text input
- **Local Speech Processing**: whisper.cpp for privacy-preserving speech-to-text

### 🛡️ **Sandboxed Skills**
- **Process Isolation**: Each skill runs in complete isolation
- **Permission Manifests**: Explicit declaration of required capabilities
- **Rate Limiting**: Per-skill execution limits and resource controls
- **Rollback Capabilities**: Undo skill actions where possible

### 🧠 **Intelligent Memory**
- **MIRIX Architecture**: Six specialized memory types (Core, Episodic, Semantic, Procedural, Resource, Knowledge Vault)
- **Local Vector Search**: Similarity search without external dependencies
- **Configurable Retention**: User-controlled data lifecycle policies
- **Instant Purging**: Complete data deletion capabilities

### 🤖 **LLM Integration**
- **Advisory Only**: LLMs produce structured intents, never execute actions directly
- **Multi-Provider Support**: Gemini, local models, extensible architecture
- **Safety Filtering**: Content validation and intent sanitization
- **Isolation Boundaries**: Strict separation between AI and system control

## 📁 Repository Structure

```
guru-personal-assistant/
├── desktop-agent/          # Windows Desktop Agent (FastAPI + Tauri)
├── phone-agent/            # Android Phone Agent (Kotlin + Compose)
├── shared/                 # Common utilities and protocols
├── memory/                 # MIRIX memory service implementation
├── skills/                 # Sandboxed skill system
├── agents/                 # LLM adapter and planning system
├── infra/ci/              # CI/CD and deployment automation
├── docs/                  # Documentation and security guides
└── tests/                 # Integration and security tests
```

## 🚀 Quick Start

### Prerequisites

**Windows Desktop:**
- Windows 10/11 with Windows Hello support
- Python 3.11+
- Node.js 18+
- Rust (for Tauri components)

**Android Phone:**
- Android 8.0+ (API level 26+)
- Biometric authentication capability
- Kotlin development environment

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-org/guru-personal-assistant.git
   cd guru-personal-assistant
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Set up desktop agent:**
   ```bash
   cd desktop-agent
   pip install -r requirements.txt
   ```

4. **Build phone agent:**
   ```bash
   cd phone-agent
   ./gradlew build
   ```

5. **Initialize secure pairing:**
   - Start desktop agent
   - Install phone agent APK
   - Follow QR code pairing process

## 🔧 Configuration

### Security Configuration

GURU uses secure defaults and requires minimal configuration:

```yaml
# config/security.yaml
authority:
  biometric_policy: "medium_risk"  # low_risk, medium_risk, high_risk
  session_timeout: 300             # seconds
  intrusion_threshold: 3           # failed attempts

cryptography:
  algorithm: "ECDSA-P256"
  key_rotation_days: 90
  hardware_backing: true

audit:
  retention_days: 365
  integrity_checking: true
  export_format: "json"
```

### Privacy Configuration

```yaml
# config/privacy.yaml
data_collection:
  screen_observation: false        # Opt-in only
  voice_samples: false            # For training improvement
  usage_analytics: false          # Never enabled by default

retention:
  episodic_memory_days: 30
  semantic_memory_days: 365
  audit_logs_days: 1095          # 3 years minimum

encryption:
  at_rest: "AES-256-GCM"
  in_transit: "TLS-1.3"
  key_derivation: "PBKDF2"
```

## 🧪 Testing

GURU implements comprehensive testing including property-based testing for security invariants:

```bash
# Run all tests
npm test

# Run security tests only
npm run test:security

# Run property-based tests
npm run test:properties

# Run integration tests
npm run test:integration
```

### Security Test Categories

- **Authority Enforcement Tests**: Verify no unauthorized automation occurs
- **Cryptographic Protocol Tests**: Validate signature and encryption correctness
- **Intrusion Detection Tests**: Confirm proper response to security violations
- **Sandbox Escape Tests**: Verify skill isolation boundaries
- **Audit Integrity Tests**: Ensure tamper-evident logging

## 📚 Documentation

- **[Security Architecture](docs/security-architecture.md)**: Detailed security model and threat analysis
- **[API Reference](docs/api-reference.md)**: Complete API documentation
- **[Deployment Guide](docs/deployment.md)**: Production deployment instructions
- **[Skill Development](docs/skill-development.md)**: Creating custom skills
- **[Troubleshooting](docs/troubleshooting.md)**: Common issues and solutions

## 🛡️ Security Considerations

### What GURU Does NOT Do

- **Never unlocks Windows or bypasses OS authentication**
- **Never operates on the Windows lock screen**
- **Never stores raw biometric data**
- **Never allows LLMs to execute actions directly**
- **Never operates without comprehensive audit logging**
- **Never degrades security for convenience**

### Security Boundaries

- **Windows Lock Screen**: Complete system disable when Windows is locked
- **User Session Only**: All automation occurs within unlocked user sessions
- **OS API Compliance**: Uses only standard Windows APIs, never bypasses security
- **UAC Integration**: Admin actions use native Windows UAC prompts

### Threat Model

GURU is designed to resist:
- Voice spoofing and replay attacks
- Biometric spoofing attempts
- Command injection and privilege escalation
- Skill sandbox escape attempts
- Audit log tampering
- LLM prompt injection attacks
- Network interception and MITM attacks

## 🤝 Contributing

We welcome contributions that strengthen security and improve functionality:

1. **Security-First**: All contributions must maintain or improve security posture
2. **Zero-Defect Policy**: Code must pass all tests including property-based security tests
3. **Documentation Required**: Security-relevant changes require documentation updates
4. **Audit Trail**: All changes must be compatible with audit logging requirements

### Development Workflow

1. Fork the repository
2. Create a feature branch
3. Implement changes with comprehensive tests
4. Run security test suite
5. Submit pull request with security impact analysis

## 📄 License

MIT License with security and privacy notices. See [LICENSE](LICENSE) for details.

## ⚠️ Disclaimers

- **Security**: Users are responsible for compliance with applicable laws regarding cryptography and biometric data
- **Privacy**: Review all optional features and configure according to your privacy requirements
- **Audit**: Manage audit logs according to your security and compliance requirements
- **Jurisdiction**: Ensure compliance with local laws regarding automation and biometric processing

## 🆘 Support

- **Documentation**: Check the [docs/](docs/) directory for comprehensive guides
- **Issues**: Report bugs and security issues through GitHub Issues
- **Security**: For security vulnerabilities, see [SECURITY.md](SECURITY.md)
- **Community**: Join discussions in GitHub Discussions

---

**Built with security, privacy, and user control as first-class requirements.**