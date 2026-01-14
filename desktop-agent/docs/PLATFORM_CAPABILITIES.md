# GURU Platform Capability Matrix

**Version:** 1.0.0  
**Last Updated:** January 15, 2026

## Overview

This document provides a comprehensive, **honest** assessment of GURU's capabilities across all supported platforms. We believe in transparency: you deserve to know exactly what GURU can and cannot do on your device.

**Supported Platforms:**
- Windows 10/11 (Full desktop control)
- macOS (Full desktop control with permissions)
- Android (Partial automation via Accessibility Service)
- iOS (Command-limited, no system automation)

---

## Legend

- ✅ **FULL**: Complete functionality with no restrictions
- ⚠️ **PARTIAL**: Reduced functionality or requires special permissions
- 🔶 **LIMITED**: Severely restricted functionality
- ❌ **NONE**: Not available on this platform

---

## Quick Comparison

| Feature Category | Windows | macOS | Android | iOS |
|------------------|---------|-------|---------|-----|
| **Application Control** | ✅ Full | ✅ Full | ✅ Full | 🔶 Limited |
| **Input Automation** | ✅ Full | ✅ Full (with perm) | ⚠️ Partial | ❌ None |
| **Speech (TTS/STT)** | ✅ Full (local) | ✅ Full (local) | ⚠️ Partial | ⚠️ System only |
| **Biometric Auth** | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| **Security Enforcement** | ✅ System-wide | ✅ System-wide | ⚠️ App-level | 🔶 App-only |
| **Authority Scope** | System-wide | System-wide | App-level | App-level |

---

## Detailed Capabilities

### Application Control

#### Open Applications

| Platform | Level | Details |
|----------|-------|---------|
| **Windows** | ✅ FULL | Launch any installed application via Win32 ShellExecute |
| **macOS** | ✅ FULL | Launch any installed application via LaunchServices |
| **Android** | ✅ FULL | Launch any installed application via Intent system |
| **iOS** | 🔶 LIMITED | Can only open apps with registered URL schemes (deep links) |

#### Close Applications

| Platform | Level | Details |
|----------|-------|---------|
| **Windows** | ✅ FULL | Close any running application via Win32 TerminateProcess |
| **macOS** | ✅ FULL | Close any running application via Apple Events |
| **Android** | ✅ FULL | Close applications that support finish() intent |
| **iOS** | ❌ NONE | **iOS does not allow apps to close other apps** |

#### Discover Applications

| Platform | Level | Details |
|----------|-------|---------|
| **Windows** | ✅ FULL | Discover all installed apps via Registry and Start Menu |
| **macOS** | ✅ FULL | Discover all installed apps via NSWorkspace |
| **Android** | ✅ FULL | Discover all installed apps via PackageManager |
| **iOS** | 🔶 LIMITED | Can only check if specific URL schemes are registered |

---

### Input Automation

#### Type Text

| Platform | Level | Details |
|----------|-------|---------|
| **Windows** | ✅ FULL | Type text into any application via Win32 SendInput |
| **macOS** | ✅ FULL | Type text into any application via CGEvent (requires Accessibility permission) |
| **Android** | ⚠️ PARTIAL | Type text via Accessibility Service (requires user permission, limited to accessibility-supported apps) |
| **iOS** | ❌ NONE | **iOS does not allow input automation** |

#### Click UI Elements

| Platform | Level | Details |
|----------|-------|---------|
| **Windows** | ✅ FULL | Click UI elements via Win32 SendInput and UI Automation |
| **macOS** | ✅ FULL | Click UI elements via CGEvent (requires Accessibility permission) |
| **Android** | ⚠️ PARTIAL | Click UI elements via Accessibility Service (requires user permission, limited to accessibility-supported apps) |
| **iOS** | ❌ NONE | **iOS does not allow UI automation** |

---

### Speech (TTS/STT)

#### Text-to-Speech (TTS)

| Platform | Level | Details |
|----------|-------|---------|
| **Windows** | ✅ FULL | Windows SAPI with full voice customization |
| **macOS** | ✅ FULL | NSSpeechSynthesizer with full voice customization |
| **Android** | ✅ FULL | Android TextToSpeech API with voice customization |
| **iOS** | ✅ FULL | AVSpeechSynthesizer with voice customization |

#### Speech-to-Text (STT)

| Platform | Level | Details |
|----------|-------|---------|
| **Windows** | ✅ FULL | **Local Whisper.cpp** - no network required, complete privacy |
| **macOS** | ✅ FULL | **Local Whisper.cpp** - no network required, complete privacy |
| **Android** | ⚠️ PARTIAL | User choice: Local Whisper.cpp OR system STT (system requires network) |
| **iOS** | ⚠️ PARTIAL | **MUST use system STT** - requires network, subject to Apple privacy policy |

#### Wake Word Detection

| Platform | Level | Details |
|----------|-------|---------|
| **Windows** | ✅ FULL | Local Whisper.cpp with custom wake word model |
| **macOS** | ✅ FULL | Local Whisper.cpp with custom wake word model |
| **Android** | ⚠️ PARTIAL | Local Whisper.cpp if available, may fall back to system |
| **iOS** | ⚠️ PARTIAL | System wake word detection only (limited) |

---

### Biometric Authentication

All platforms support biometric authentication with hardware-backed security:

| Platform | Fingerprint | Face Recognition | Hardware-Backed Storage |
|----------|-------------|------------------|-------------------------|
| **Windows** | ✅ Windows Hello | ✅ Windows Hello | ✅ TPM |
| **macOS** | ✅ Touch ID | ✅ Face ID | ✅ Secure Enclave |
| **Android** | ✅ BiometricPrompt | ✅ BiometricPrompt | ✅ Android Keystore |
| **iOS** | ✅ Touch ID | ✅ Face ID | ✅ Secure Enclave |

---

### Security Enforcement

#### Lock Scope

| Platform | Authority Scope | Lock Capability | Details |
|----------|-----------------|-----------------|---------|
| **Windows** | System-wide | ✅ Workstation lock | Locks entire workstation, affects all applications |
| **macOS** | System-wide | ✅ Screen lock | Locks screen, affects all applications |
| **Android** | App-level | ⚠️ App + screen lock | Can lock screen and exit app, but user can access other apps after unlock |
| **iOS** | App-level | 🔶 App exit only | **Cannot lock device**, can only exit GURU app |

#### Intrusion Detection

| Platform | Level | Response Capability |
|----------|-------|---------------------|
| **Windows** | ✅ FULL | Lock workstation on intrusion detection |
| **macOS** | ✅ FULL | Lock screen on intrusion detection |
| **Android** | ⚠️ PARTIAL | Lock screen and exit app (user can access other apps) |
| **iOS** | 🔶 LIMITED | Exit app only (user can immediately reopen) |

---

### Memory & Storage

All platforms support full encrypted storage and semantic search:

| Feature | Windows | macOS | Android | iOS |
|---------|---------|-------|---------|-----|
| **AES-256-GCM Encryption** | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| **Vector Search (FAISS)** | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| **90-Day Auto-Purge** | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| **Hardware-Backed Keys** | ✅ TPM | ✅ Secure Enclave | ✅ Keystore | ✅ Secure Enclave |

---

## Platform Limitations

### Windows

**No significant limitations.** Windows provides full desktop control with no restrictions.

### macOS

**Requires Accessibility Permission:**
- Input automation (typing, clicking) requires user to grant Accessibility permission
- One-time setup required
- Full functionality after permission grant

### Android

**Accessibility Service Required:**
- Input automation requires Accessibility Service permission
- User must manually grant permission in Settings
- Only works in apps that support accessibility
- Cannot interact with system UI

**App-Level Authority:**
- Authority scope limited to app-level
- Cannot enforce system-wide security
- Screen lock can be bypassed by accessing other apps

**STT Options:**
- User choice: Local Whisper.cpp (privacy, resource-intensive) OR system STT (network required)

### iOS

**SEVERE LIMITATIONS** (iOS Platform Restrictions):

**Application Control:**
- ❌ Cannot close apps (iOS restriction)
- 🔶 Can only open apps with URL schemes (deep links)
- 🔶 Cannot enumerate installed apps (privacy restriction)
- ❌ Cannot check if apps are running (privacy restriction)

**Input Automation:**
- ❌ Cannot type text (iOS restriction)
- ❌ Cannot click UI elements (iOS restriction)
- ❌ Cannot simulate keyboard input (iOS restriction)

**Speech:**
- ⚠️ MUST use system STT (cannot use local Whisper.cpp)
- ⚠️ Requires network connection for STT
- ⚠️ Subject to Apple privacy policy

**Security:**
- 🔶 Cannot lock device (iOS restriction)
- 🔶 Can only exit GURU app
- 🔶 Authority scope strictly app-level
- 🔶 User can immediately reopen app after intrusion detection

**Honest Assessment:** iOS is the most restricted platform. GURU's functionality on iOS is severely limited compared to other platforms.

---

## Authority Scope Explained

### System-Wide Authority (Windows, macOS)

When you grant GURU authority on desktop platforms:
- GURU can control **all applications** on your system
- GURU can automate **any task** across applications
- Security enforcement affects **entire system** (workstation/screen lock)
- This is necessary for full desktop AI assistant functionality

### App-Level Authority (Android, iOS)

When you grant GURU authority on mobile platforms:
- GURU can only control **itself** and limited interactions with other apps
- GURU **cannot** enforce system-wide security
- On intrusion, GURU can only lock screen (Android) or exit (iOS)
- User can access other apps after unlock/reopen

This is a **platform limitation**, not a GURU design choice.

---

## Runtime Capability Query

GURU provides a programmatic API to query capabilities at runtime:

```python
from pal import get_capability_matrix

# Get capability matrix
matrix = get_capability_matrix()

# Query specific platform
windows_caps = matrix.get_platform_capabilities("windows")

# Check specific capability
can_type = windows_caps.get_capability("input_automation", "type_text")
print(f"Level: {can_type.level}")
print(f"Description: {can_type.description}")
print(f"Restrictions: {can_type.restrictions}")

# Get all limitations for a platform
ios_caps = matrix.get_platform_capabilities("ios")
limitations = ios_caps.get_limitations()
for limitation in limitations:
    print(limitation)

# Compare capability across platforms
comparison = matrix.compare_platforms("input_automation", "type_text")
# Returns: {'windows': FULL, 'macos': FULL, 'android': PARTIAL, 'ios': NONE}
```

---

## Recommendations by Use Case

### Full Desktop Control Needed
**Recommended:** Windows or macOS
- Complete application control
- Full input automation
- System-wide authority
- Local speech processing (privacy)

### Mobile Companion
**Recommended:** Android
- Good application control
- Partial input automation (with permission)
- Local or system STT (user choice)
- App-level authority (platform limitation)

### iOS Users
**Understand Limitations:**
- Very limited application control
- No input automation
- System STT only (network required)
- App-level authority only
- Consider using GURU on desktop for full functionality

---

## Privacy Considerations

### Local Processing (Windows, macOS)
- Speech recognition runs **locally** (Whisper.cpp)
- No network required for STT
- Complete privacy - your voice never leaves your device

### Android
- User choice: Local Whisper.cpp OR system STT
- Local option provides complete privacy
- System option requires network and Google services

### iOS
- **Must use system STT** (Apple restriction)
- Requires network connection
- Subject to Apple privacy policy
- Your voice data is processed by Apple servers

---

## Questions?

For detailed technical documentation, see:
- `desktop-agent/src/pal/capability_matrix.py` - Implementation
- `desktop-agent/src/pal/interfaces.py` - PAL interface definitions
- `.kiro/specs/guru-complete-system/requirements.md` - Requirements (41.x)
- `.kiro/specs/guru-complete-system/design.md` - Architecture design

---

**Document Version:** 1.0.0  
**Validates:** Requirements 41.1, 41.2, 41.3, 41.4, 41.5, 41.6, 41.7
