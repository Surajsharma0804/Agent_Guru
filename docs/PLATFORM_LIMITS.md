# Platform Distribution Limits and Store Compliance

This document defines the comprehensive platform-specific limitations and store compliance requirements for GURU AI Assistant distribution across all supported platforms.

## Executive Summary

GURU AI Assistant implements **zero-tolerance policy enforcement** to ensure compliance with all major application store requirements while maintaining maximum user privacy and security. The system automatically detects execution context and enforces appropriate restrictions without user intervention.

### Core Compliance Principles

1. **Store-installed applications MUST use API-only LLM providers**
2. **Sideloaded applications MAY use local models with explicit user consent**
3. **All credential storage uses platform-native secure mechanisms**
4. **Tamper detection results in immediate security lockdown**
5. **User consent is required for all cloud API usage**

---

## Platform-Specific Requirements

### Windows Platform

#### Microsoft Store Distribution
- **Execution Context**: `STORE_INSTALLED`
- **LLM Providers**: API-only (OpenAI, Gemini)
- **Local Models**: Completely disabled
- **Credential Storage**: Windows Credential Manager + encryption
- **Security Requirements**:
  - BitLocker encryption recommended
  - Windows Defender integration
  - User Account Control compliance
  - TPM utilization when available

#### Sideloaded Distribution
- **Execution Context**: `SIDELOADED_DESKTOP`
- **LLM Providers**: Local (Ollama) + API with consent
- **Local Models**: Allowed with user consent
- **Credential Storage**: Windows Credential Manager + encryption
- **Security Requirements**:
  - Manual installation warnings
  - SmartScreen compatibility
  - Code signing recommended

#### Enterprise Distribution
- **Execution Context**: `ENTERPRISE`
- **LLM Providers**: Policy-controlled
- **Local Models**: Administrator-controlled
- **Credential Storage**: Enterprise credential management
- **Security Requirements**:
  - Group Policy compliance
  - Active Directory integration
  - Enterprise certificate validation

### macOS Platform

#### Mac App Store Distribution
- **Execution Context**: `STORE_INSTALLED`
- **LLM Providers**: API-only (OpenAI, Gemini)
- **Local Models**: Completely disabled
- **Credential Storage**: macOS Keychain Services
- **Security Requirements**:
  - App Store signature validation
  - Sandboxing compliance
  - FileVault encryption recommended
  - System Integrity Protection compliance
  - Notarization required

#### Sideloaded Distribution
- **Execution Context**: `SIDELOADED_DESKTOP`
- **LLM Providers**: Local (Ollama) + API with consent
- **Local Models**: Allowed with user consent
- **Credential Storage**: macOS Keychain Services
- **Security Requirements**:
  - Developer ID signature required
  - Gatekeeper compatibility
  - User consent for network access
  - Privacy permission requests

### Linux Platform

#### Distribution Package Stores (Snap, Flatpak, AppImage)
- **Execution Context**: `STORE_INSTALLED`
- **LLM Providers**: API-only (OpenAI, Gemini)
- **Local Models**: Completely disabled
- **Credential Storage**: libsecret/keyring + encrypted fallback
- **Security Requirements**:
  - Sandboxing compliance (Snap/Flatpak)
  - AppArmor/SELinux compatibility
  - Secure Boot compatibility
  - LUKS encryption recommended

#### Direct Installation
- **Execution Context**: `SIDELOADED_DESKTOP`
- **LLM Providers**: Local (Ollama) + API with consent
- **Local Models**: Allowed with user consent
- **Credential Storage**: libsecret/keyring + encrypted fallback
- **Security Requirements**:
  - Package signature verification
  - Dependency management
  - User permission management

### iOS Platform

#### App Store Distribution
- **Execution Context**: `STORE_INSTALLED`
- **LLM Providers**: API-only (OpenAI, Gemini)
- **Local Models**: Completely prohibited
- **Credential Storage**: iOS Keychain Services
- **Security Requirements**:
  - App Store Review Guidelines compliance
  - iOS Sandboxing mandatory
  - Network usage disclosure
  - Privacy manifest required
  - No background processing
  - No local model downloads

#### Enterprise Distribution (iOS)
- **Execution Context**: `ENTERPRISE`
- **LLM Providers**: Policy-controlled
- **Local Models**: Prohibited by iOS limitations
- **Credential Storage**: iOS Keychain Services + MDM
- **Security Requirements**:
  - Enterprise certificate validation
  - MDM compliance
  - Corporate network restrictions

### Android Platform

#### Google Play Store Distribution
- **Execution Context**: `STORE_INSTALLED`
- **LLM Providers**: API-only (OpenAI, Gemini)
- **Local Models**: Completely disabled
- **Credential Storage**: Android Keystore System
- **Security Requirements**:
  - Google Play Protect compliance
  - Android App Bundle format
  - Privacy policy disclosure
  - Permissions minimization
  - No background model downloads
  - SafetyNet attestation

#### Sideloaded Distribution (APK)
- **Execution Context**: `SIDELOADED_DESKTOP`
- **LLM Providers**: Local (limited) + API with consent
- **Local Models**: Limited by Android storage/performance
- **Credential Storage**: Android Keystore System
- **Security Requirements**:
  - Unknown sources warning
  - APK signature verification
  - Runtime permissions
  - Network security config

---

## LLM Provider Restrictions by Context

### Store-Installed Applications

| Provider | Allowed | Configuration | User Consent Required |
|----------|---------|---------------|----------------------|
| Ollama (Local) | ❌ Never | N/A | N/A |
| OpenAI API | ✅ Yes | Environment variables only | ✅ Required |
| Gemini API | ✅ Yes | Environment variables only | ✅ Required |
| Custom APIs | ❌ Never | N/A | N/A |

### Sideloaded Applications

| Provider | Allowed | Configuration | User Consent Required |
|----------|---------|---------------|----------------------|
| Ollama (Local) | ✅ Yes | User-configurable | ✅ Required |
| OpenAI API | ✅ Yes | Environment variables only | ✅ Required |
| Gemini API | ✅ Yes | Environment variables only | ✅ Required |
| Custom APIs | ⚠️ Limited | Advanced users only | ✅ Required |

### Enterprise Applications

| Provider | Allowed | Configuration | User Consent Required |
|----------|---------|---------------|----------------------|
| Ollama (Local) | ⚠️ Policy | Administrator-controlled | ⚠️ Policy |
| OpenAI API | ⚠️ Policy | Administrator-controlled | ⚠️ Policy |
| Gemini API | ⚠️ Policy | Administrator-controlled | ⚠️ Policy |
| Custom APIs | ⚠️ Policy | Administrator-controlled | ⚠️ Policy |

---

## Security and Privacy Requirements

### Credential Management

#### Windows
- **Primary**: Windows Credential Manager API
- **Encryption**: DPAPI + additional AES encryption
- **Key Derivation**: Machine GUID + User SID
- **Backup**: Encrypted local files with machine binding

#### macOS
- **Primary**: Keychain Services API
- **Encryption**: Hardware Security Module when available
- **Key Derivation**: System keychain + user keychain
- **Backup**: iCloud Keychain (user-controlled)

#### Linux
- **Primary**: libsecret/GNOME Keyring or KDE Wallet
- **Encryption**: AES-256 with PBKDF2 key derivation
- **Key Derivation**: Machine ID + User ID
- **Backup**: Encrypted local files with user binding

#### iOS
- **Primary**: iOS Keychain Services
- **Encryption**: Secure Enclave when available
- **Key Derivation**: Device-specific hardware keys
- **Backup**: iCloud Keychain (user-controlled)

#### Android
- **Primary**: Android Keystore System
- **Encryption**: Hardware Security Module when available
- **Key Derivation**: Android ID + User profile
- **Backup**: Android Backup Service (encrypted)

### Network Security

#### API Communication
- **Protocol**: HTTPS only (TLS 1.3 preferred)
- **Certificate Pinning**: Enabled for known providers
- **Request Signing**: HMAC-SHA256 for sensitive requests
- **Rate Limiting**: Provider-specific limits enforced
- **Timeout Handling**: Fail-closed on network errors

#### Local Model Communication
- **Protocol**: HTTP over localhost only
- **Port Binding**: 127.0.0.1 interface only
- **Authentication**: API key or token-based
- **Encryption**: Optional TLS for sensitive data
- **Process Isolation**: Separate process boundaries

### Data Privacy

#### User Data Handling
- **Prompt Data**: Never logged in plain text
- **Response Data**: Cached locally with encryption
- **Metadata Only**: Audit logs contain no user content
- **Retention Policy**: User-configurable data retention
- **Right to Deletion**: Complete data removal on request

#### Telemetry and Analytics
- **Store Apps**: Minimal telemetry (crash reports only)
- **Sideloaded Apps**: User-controlled telemetry
- **Enterprise Apps**: Administrator-controlled telemetry
- **Data Minimization**: Only essential metrics collected
- **Anonymization**: All telemetry data anonymized

---

## Compliance Validation

### Automated Testing

The system includes comprehensive automated testing to validate compliance:

```bash
# Run store compliance validation
python desktop-agent/src/test_store_compliance.py

# Expected output for compliant system:
# ✅ ALL STORE COMPLIANCE VALIDATIONS PASSED
# ✅ READY FOR STORE DISTRIBUTION
# 🔒 ZERO-COMPROMISE POLICY ENFORCEMENT VERIFIED
```

### Manual Verification Checklist

#### Pre-Distribution Checklist

- [ ] Execution context detection working correctly
- [ ] Store policy enforcement operational
- [ ] Platform-specific credential management functional
- [ ] API-only mode enforced for store builds
- [ ] User consent management operational
- [ ] Security boundaries properly enforced
- [ ] Audit logging compliance verified
- [ ] Platform-specific requirements met
- [ ] Tamper resistance mechanisms active
- [ ] Store distribution compliance validated

#### Platform-Specific Verification

##### Windows Microsoft Store
- [ ] App passes Windows App Certification Kit
- [ ] No local model binaries included
- [ ] Windows Credential Manager integration working
- [ ] Privacy policy updated for API usage
- [ ] Age rating appropriate for AI assistant

##### macOS App Store
- [ ] App passes App Store validation
- [ ] Sandboxing entitlements minimal
- [ ] Keychain access properly configured
- [ ] Privacy usage descriptions complete
- [ ] Notarization successful

##### Linux Package Stores
- [ ] Snap/Flatpak confinement working
- [ ] Desktop integration files correct
- [ ] Dependencies properly declared
- [ ] Security policy compliance verified

##### iOS App Store
- [ ] App Store Review Guidelines compliance
- [ ] Privacy manifest complete and accurate
- [ ] No prohibited background processing
- [ ] Network usage properly disclosed
- [ ] Age rating appropriate

##### Google Play Store
- [ ] Play Console policy compliance
- [ ] Android App Bundle optimized
- [ ] Permissions justified and minimal
- [ ] Privacy policy comprehensive
- [ ] SafetyNet attestation passing

---

## Troubleshooting Common Issues

### Execution Context Detection Issues

**Problem**: Wrong execution context detected
**Solution**: 
1. Check installation path patterns
2. Verify environment variables
3. Validate platform-specific signatures
4. Review tamper detection logs

**Problem**: Tamper detection false positives
**Solution**:
1. Ensure clean installation environment
2. Remove debugging tools
3. Check for suspicious environment variables
4. Validate executable integrity

### Credential Management Issues

**Problem**: Credential storage failing
**Solution**:
1. Verify platform security requirements
2. Check user permissions
3. Validate keychain/credential manager access
4. Test with minimal credentials first

**Problem**: Credential retrieval failing
**Solution**:
1. Check credential existence
2. Verify access permissions
3. Test key derivation consistency
4. Validate encryption/decryption

### API-Only Mode Issues

**Problem**: Local models still accessible
**Solution**:
1. Verify execution context detection
2. Check configuration compliance
3. Validate provider routing logic
4. Review security policy enforcement

**Problem**: API consent not working
**Solution**:
1. Check consent storage permissions
2. Verify UI integration
3. Test consent persistence
4. Validate revocation mechanism

---

## Future Platform Considerations

### Emerging Platforms

#### Web Assembly (WASM)
- **Execution Context**: `BROWSER_EXTENSION` or `WEB_APP`
- **LLM Providers**: API-only (browser security model)
- **Local Models**: Limited by WASM constraints
- **Credential Storage**: Browser credential management APIs

#### Progressive Web Apps (PWA)
- **Execution Context**: `WEB_APP`
- **LLM Providers**: API-only (network-dependent)
- **Local Models**: Service Worker limitations
- **Credential Storage**: Web Credential Management API

#### Embedded Systems
- **Execution Context**: `EMBEDDED`
- **LLM Providers**: Local-only (offline requirement)
- **Local Models**: Optimized for resource constraints
- **Credential Storage**: Hardware security modules

### Regulatory Compliance

#### GDPR (European Union)
- Right to data portability
- Right to be forgotten
- Data processing consent
- Privacy by design requirements

#### CCPA (California)
- Consumer privacy rights
- Data sale opt-out
- Transparent data practices
- Non-discrimination requirements

#### SOC 2 (Enterprise)
- Security controls
- Availability requirements
- Processing integrity
- Confidentiality measures

---

## Contact and Support

For platform-specific compliance questions or issues:

- **Technical Support**: [Technical documentation and issue tracking]
- **Compliance Questions**: [Legal and compliance team contact]
- **Security Issues**: [Security team contact for vulnerability reports]
- **Platform Certification**: [Platform-specific certification support]

---

**Document Version**: 1.0.0  
**Last Updated**: January 2026  
**Next Review**: Quarterly or upon platform policy changes