# GURU Phone Agent

Production-grade Android application for secure personal automation and device communication.

## Overview

GURU Phone Agent is the mobile component of the GURU personal assistant system, providing secure voice-driven automation capabilities with enterprise-level security controls and comprehensive audit logging.

## Key Features

### Security-First Architecture
- **Hardware-backed cryptography** using Android Keystore
- **Multi-factor biometric authentication** with Windows Hello integration
- **Cryptographically signed audit logging** with tamper detection
- **Zero-trust security model** with explicit consent requirements
- **Fail-safe defaults** with secure degradation

### Production-Grade Implementation
- **Jetpack Compose** modern UI with Material Design 3
- **Hilt dependency injection** for modular architecture
- **Kotlin Coroutines** for reactive programming
- **Comprehensive testing** with unit, integration, and UI tests
- **Enterprise security standards** compliance

### Core Capabilities
- **Secure device pairing** via QR code with cryptographic verification
- **Voice command processing** with speaker verification
- **Real-time communication** with desktop GURU agent
- **Comprehensive audit logging** for compliance and forensics
- **Emergency security controls** with immediate system lockdown

## Architecture

### Security Components
- `SecurityManager`: Hardware-backed cryptographic operations
- `AuditLogger`: Tamper-evident logging with digital signatures
- `BiometricAuthority`: Multi-factor authentication management
- `CommunicationSecurity`: Encrypted device-to-device communication

### UI Components
- `MainActivity`: Main application interface with security controls
- `PermissionsScreen`: Security-focused permission management
- `PairingScreen`: Secure device pairing interface
- `SecurityScreen`: Audit log viewing and security monitoring
- `SettingsScreen`: Application configuration and preferences

### Data Layer
- **Encrypted SharedPreferences** for sensitive configuration
- **Local SQLite database** for audit logs and application data
- **Hardware security module** integration when available
- **Secure key derivation** using Android Keystore

## Security Model

### Authority States
- `LOCKED`: No automation authority granted
- `VERIFICATION`: Multi-factor authentication in progress
- `ARMED`: Full automation authority with comprehensive logging
- `INTRUSION_DETECTED`: Security breach detected, system locked

### Cryptographic Standards
- **ECDSA-P256** for digital signatures and device authentication
- **AES-256-GCM** for symmetric encryption of sensitive data
- **SHA-256** for cryptographic hashing and integrity verification
- **Hardware-backed key storage** using Android Keystore

### Audit Logging
- **Append-only log structure** with cryptographic integrity
- **Hash chaining** for tamper detection
- **Digital signatures** on all audit entries
- **Comprehensive event coverage** for security and compliance

## Development Setup

### Prerequisites
- Android Studio Arctic Fox or later
- Android SDK API 26+ (Android 8.0)
- Kotlin 1.9.22+
- Gradle 8.4+

### Build Configuration
```bash
# Clone the repository
git clone <repository-url>
cd phone-agent

# Build debug version
./gradlew assembleDebug

# Run unit tests
./gradlew testDebugUnitTest

# Run instrumented tests
./gradlew connectedDebugAndroidTest

# Build release version (requires signing configuration)
./gradlew assembleRelease
```

### Security Configuration
1. Configure code signing certificates for release builds
2. Set up hardware security module integration (optional)
3. Configure network security policies for production
4. Review and customize security settings in `SecurityManager`

## Testing

### Test Coverage
- **Unit Tests**: Core business logic and security components
- **Integration Tests**: Component interaction and data flow
- **UI Tests**: User interface and interaction testing
- **Security Tests**: Cryptographic operations and security controls

### Test Execution
```bash
# Run all tests
./gradlew test

# Run specific test suite
./gradlew testDebugUnitTest
./gradlew connectedDebugAndroidTest

# Generate test coverage report
./gradlew jacocoTestReport
```

## Deployment

### Production Checklist
- [ ] Configure release signing with production certificates
- [ ] Enable ProGuard/R8 obfuscation for security
- [ ] Review and update network security configuration
- [ ] Validate hardware security integration
- [ ] Test on target device configurations
- [ ] Perform security audit and penetration testing
- [ ] Configure crash reporting and monitoring
- [ ] Set up secure update distribution

### Security Hardening
- **Code obfuscation** enabled for release builds
- **Certificate pinning** for network communications
- **Root detection** and tamper protection
- **Anti-debugging** measures in production
- **Secure backup exclusion** for sensitive data

## Compliance

### Standards Adherence
- **OWASP Mobile Security** best practices
- **Android Security Guidelines** compliance
- **NIST Cryptographic Standards** (SP 800-57, FIPS 140-2)
- **Enterprise Security Policies** alignment

### Audit Requirements
- **Comprehensive audit logging** for all security events
- **Tamper-evident log structure** with cryptographic integrity
- **Export capabilities** for compliance reporting
- **Retention policies** configurable by organization

## Support

### Documentation
- [Security Architecture](docs/security-architecture.md)
- [API Documentation](docs/api-documentation.md)
- [Deployment Guide](docs/deployment-guide.md)
- [Troubleshooting](docs/troubleshooting.md)

### Contact
For security issues or enterprise support, contact the GURU development team.

## License

This project is licensed under the terms specified in the LICENSE file.

---

**GURU Phone Agent** - Secure personal automation with enterprise-grade security controls.