# iOS Platform Limitations

## Executive Summary

**CRITICAL**: iOS is the most restricted platform supported by GURU. This document provides an **honest assessment** of iOS capabilities and limitations to set accurate user expectations.

**Authority Scope**: App-level only (NO system-wide control)  
**Automation Capability**: Severely restricted (NO system automation)  
**Security Enforcement**: App lock only (NO system lock)

---

## Platform Comparison

| Feature | Windows | macOS | Android | iOS |
|---------|---------|-------|---------|-----|
| **Application Control** |
| Open apps | ✅ Full | ✅ Full | ✅ Full | ⚠️ Deep links only |
| Close apps | ✅ Full | ✅ Full | ✅ Full | ❌ Not allowed |
| Discover apps | ✅ Full | ✅ Full | ✅ Full | ❌ Privacy restriction |
| Query running apps | ✅ Full | ✅ Full | ✅ Full | ❌ Privacy restriction |
| **Input Automation** |
| Type text | ✅ Full | ✅ Full (with perm) | ⚠️ Partial (Accessibility) | ❌ Severely restricted |
| Click UI | ✅ Full | ✅ Full (with perm) | ⚠️ Partial (Accessibility) | ❌ Not allowed |
| Focus apps | ✅ Full | ✅ Full | ✅ Full | ⚠️ Limited |
| **Speech** |
| TTS | ✅ SAPI | ✅ NSSpeech | ✅ Android TTS | ✅ AVSpeech |
| STT | ✅ Whisper.cpp | ✅ Whisper.cpp | ⚠️ Whisper or system | ⚠️ System only |
| Wake word | ✅ Local | ✅ Local | ⚠️ Local or system | ⚠️ System only |
| **Biometrics** |
| Fingerprint | ✅ Windows Hello | ✅ Touch ID | ✅ BiometricPrompt | ✅ Touch ID |
| Face | ✅ Windows Hello | ✅ Face ID | ✅ BiometricPrompt | ✅ Face ID |
| **Security** |
| Lock scope | ✅ Workstation | ✅ Screen | ⚠️ App + screen | ⚠️ App only |
| Authority scope | ✅ System-wide | ✅ System-wide | ⚠️ App-level | ⚠️ App-level |

**Legend**:
- ✅ Full: Complete functionality
- ⚠️ Partial/Limited: Reduced functionality or requires special permissions
- ❌ Not allowed: Platform restriction

---

## Detailed Limitations

### 1. Application Control (SEVERE RESTRICTIONS)

#### 1.1 Opening Apps
**Capability**: ⚠️ Deep links only

**How it works**:
- iOS only allows opening apps via URL schemes (deep links)
- Example: `maps://` opens Apple Maps, `mailto:` opens Mail
- Requires knowing the app's URL scheme (not discoverable)

**Limitations**:
- Only works for apps with registered URL schemes
- No way to discover available URL schemes programmatically
- No feedback on whether app actually opened
- Cannot pass complex parameters to most apps

**Example**:
```python
# Works (if app has URL scheme)
controller.open_app("safari")  # Opens Safari via http://

# Fails (no URL scheme known)
controller.open_app("custom-app")  # Cannot discover URL scheme
```

#### 1.2 Closing Apps
**Capability**: ❌ Not allowed

**iOS Restriction**: Apps cannot close other apps. This is a fundamental iOS security policy.

**Impact**:
- `close_app()` always returns `False`
- Users must manually close apps via App Switcher
- No programmatic way to terminate apps

#### 1.3 Discovering Apps
**Capability**: ❌ Privacy restriction

**iOS Restriction**: Apps cannot enumerate installed apps. This is a fundamental iOS privacy policy.

**Impact**:
- `discover_apps()` always returns empty list
- Cannot build application database
- Cannot suggest apps to user
- Must rely on user knowing app names

#### 1.4 Querying Running Apps
**Capability**: ❌ Privacy restriction

**iOS Restriction**: Apps cannot query which apps are running. This is a fundamental iOS privacy policy.

**Impact**:
- `is_running()` always returns `False`
- Cannot detect if app is already open
- Cannot avoid duplicate launches

---

### 2. Input Automation (SEVERELY RESTRICTED)

#### 2.1 Text Typing
**Capability**: ❌ Severely restricted

**iOS Restriction**: Apps cannot simulate keyboard input to other apps or the system.

**Impact**:
- `type_text()` raises `PlatformCapabilityError`
- Cannot automate text entry
- Cannot fill forms programmatically
- Cannot send messages automatically

**Workaround**: None. This is a fundamental iOS security restriction.

#### 2.2 UI Clicking
**Capability**: ❌ Not allowed

**iOS Restriction**: Apps cannot simulate touch events to other apps or the system.

**Impact**:
- `click()` raises `PlatformCapabilityError`
- Cannot automate UI interactions
- Cannot click buttons programmatically
- Cannot navigate app interfaces

**Workaround**: None. This is a fundamental iOS security restriction.

#### 2.3 App Focusing
**Capability**: ⚠️ Limited

**iOS Restriction**: Apps can only bring themselves to foreground, not other apps.

**Impact**:
- `focus_app()` only works for GURU itself
- Cannot bring other apps to foreground
- Cannot switch between apps programmatically

---

### 3. Speech Recognition (RESTRICTED)

#### 3.1 Local Processing
**Capability**: ❌ Not allowed

**iOS Restriction**: Apps cannot run local speech recognition models (Whisper.cpp).

**Impact**:
- Must use system STT (requires internet)
- Cannot process speech offline
- Cannot use custom wake words
- Privacy concerns (speech sent to Apple servers)

**Workaround**: Use Apple's Speech framework (requires user permission and internet).

#### 3.2 Wake Word Detection
**Capability**: ⚠️ System only

**iOS Restriction**: Apps cannot implement custom wake word detection.

**Impact**:
- Must use "Hey Siri" (system wake word)
- Cannot use "Hey GURU" on iOS
- Cannot customize wake word
- Wake word detection controlled by Apple

**Workaround**: Use system wake word or manual activation.

---

### 4. Security Enforcement (APP-LEVEL ONLY)

#### 4.1 Session Locking
**Capability**: ⚠️ App lock only

**iOS Restriction**: Apps cannot lock the device or screen.

**Impact**:
- `lock_session()` only locks GURU app
- Cannot lock device on security violation
- Cannot prevent access to other apps
- Reduced security compared to desktop

**Workaround**: Lock GURU app and require biometric re-authentication.

#### 4.2 Authority Scope
**Capability**: ⚠️ App-level only

**iOS Restriction**: Apps have no system-wide authority.

**Impact**:
- GURU authority only applies within GURU app
- Cannot control system settings
- Cannot access other apps' data
- Cannot perform system-level actions

**Security Implication**: This is actually a **security feature** of iOS. GURU cannot be used for system-wide automation on iOS.

---

### 5. Memory and Storage (SANDBOXED)

#### 5.1 File System Access
**Capability**: ⚠️ Sandboxed

**iOS Restriction**: Apps can only access their own sandbox directory.

**Impact**:
- Cannot access system files
- Cannot access other apps' files
- Cannot read/write to arbitrary locations
- All data stored in app sandbox

**Workaround**: Use iOS document picker for user-selected files.

#### 5.2 Background Execution
**Capability**: ⚠️ Limited

**iOS Restriction**: Apps have limited background execution time.

**Impact**:
- Voice interface may be suspended in background
- Cannot run continuous monitoring
- May miss wake word when app is backgrounded
- Reduced responsiveness compared to desktop

**Workaround**: Use iOS background modes (audio, VoIP) with limitations.

---

## What Works on iOS

Despite severe limitations, iOS still supports:

### ✅ Core Features
1. **Biometric Authentication**: Full support via Face ID/Touch ID
2. **Text-to-Speech**: Full support via AVSpeechSynthesizer
3. **Speech Recognition**: Via system STT (requires internet)
4. **Conversation**: Full LLM integration (local or cloud)
5. **Memory System**: Full encrypted conversation history
6. **Audit Logging**: Full cryptographic audit trail
7. **Authority State Machine**: Full security model (app-level)

### ✅ Limited Features
1. **App Opening**: Via URL schemes only (known apps)
2. **App Focusing**: GURU app only
3. **Security Enforcement**: App lock only

### ❌ Not Supported
1. **App Closing**: iOS restriction
2. **App Discovery**: iOS restriction
3. **Text Automation**: iOS restriction
4. **UI Clicking**: iOS restriction
5. **Local Speech Models**: iOS restriction
6. **Custom Wake Words**: iOS restriction
7. **System Lock**: iOS restriction
8. **System-Wide Control**: iOS restriction

---

## Recommended Use Cases for iOS

### ✅ Good Use Cases
1. **Voice Conversations**: Full conversational AI capabilities
2. **Information Retrieval**: Ask questions, get answers
3. **Personal Assistant**: Reminders, notes, scheduling (within GURU)
4. **Knowledge Base**: Encrypted conversation history
5. **Biometric Security**: Secure authentication

### ⚠️ Limited Use Cases
1. **App Launching**: Only for apps with known URL schemes
2. **Quick Actions**: Limited to GURU app itself
3. **Voice Commands**: No system automation

### ❌ Not Recommended
1. **Desktop Automation**: Use Windows/macOS instead
2. **System Control**: Use Windows/macOS instead
3. **Multi-App Workflows**: Use Windows/macOS instead
4. **Text Automation**: Use Windows/macOS instead

---

## Platform Selection Guide

### Choose Windows/macOS if you need:
- Full desktop automation
- System-wide control
- Multi-app workflows
- Text automation
- UI clicking
- App management
- Local speech processing
- Custom wake words

### Choose Android if you need:
- Partial automation (with Accessibility Service)
- App launching and management
- Mobile convenience
- Local or cloud speech processing

### Choose iOS if you need:
- Conversational AI only
- Biometric security
- Encrypted conversation history
- Mobile convenience
- **AND** you accept severe automation limitations

---

## Security Implications

### iOS Security Model
iOS's restrictions are **security features**, not bugs:
- Prevents malicious apps from controlling system
- Protects user privacy (no app enumeration)
- Prevents unauthorized automation
- Enforces app sandboxing

### GURU on iOS
GURU respects iOS security model:
- No attempts to bypass restrictions
- Honest capability declaration
- App-level authority only
- No security illusions

**CRITICAL**: GURU on iOS is a **conversational assistant**, not a **desktop automation tool**.

---

## Technical Implementation Notes

### Platform Detection
```python
import platform

def is_ios():
    return platform.system() == "Darwin" and platform.machine().startswith("iP")
```

### Capability Queries
All iOS backends implement `get_capabilities()` to honestly declare limitations:

```python
# Application Controller
{
    'can_open_apps': True,           # Via URL schemes only
    'can_close_apps': False,         # iOS restriction
    'can_discover_apps': False,      # iOS restriction
    'can_query_running': False,      # iOS restriction
    'has_full_control': False,       # iOS restriction
    'requires_url_schemes': True,    # iOS-specific requirement
    'platform_limitations': 'severe' # Honest assessment
}

# Input Automation
{
    'can_type_text': False,          # iOS restriction
    'can_click': False,              # iOS restriction
    'can_focus_apps': False,         # iOS restriction (self only)
    'has_full_automation': False,    # iOS restriction
    'requires_permission': False     # Not applicable (not supported)
}

# Security Enforcer
{
    'can_lock_system': False,        # iOS restriction
    'can_lock_screen': False,        # iOS restriction
    'can_lock_app': True,            # Supported
    'has_system_authority': False    # iOS restriction
}
```

### Error Handling
iOS backends raise `PlatformCapabilityError` for unsupported operations:

```python
from ...interfaces import PlatformCapabilityError

def type_text(self, text: str, target=None) -> bool:
    raise PlatformCapabilityError(
        "Text automation is not supported on iOS due to platform restrictions. "
        "iOS does not allow apps to simulate keyboard input to other apps or the system."
    )
```

---

## User Communication

### Setting Expectations
When users install GURU on iOS, they must be informed:

1. **iOS is the most restricted platform**
2. **No desktop automation capabilities**
3. **Conversational AI only**
4. **App launching limited to URL schemes**
5. **No system-wide control**

### Recommended Messaging
```
GURU on iOS

GURU provides conversational AI capabilities on iOS, but with significant 
limitations due to iOS platform restrictions:

✅ What works:
- Voice conversations with AI
- Biometric authentication
- Encrypted conversation history
- Opening apps (limited to URL schemes)

❌ What doesn't work:
- Desktop automation
- Text typing automation
- UI clicking
- App closing
- App discovery
- System control
- Local speech models

For full GURU capabilities, use Windows or macOS.
```

---

## Conclusion

iOS is supported by GURU for **conversational AI use cases only**. Users requiring desktop automation, system control, or multi-app workflows should use Windows or macOS.

This honest assessment ensures users have accurate expectations and prevents frustration from attempting unsupported operations.

**Remember**: iOS restrictions are **security features**, not limitations of GURU. We respect and work within iOS's security model.

---

## Requirements Validated

This documentation validates:
- **Requirement 35.7**: iOS input automation severely restricted (documented)
- **Requirement 39.3**: Mobile authority scope is app-level only (documented)
- **Requirement 39.6**: iOS authority scope limitations (documented)
- **Requirement 41.5**: iOS capabilities explicitly stated (documented)

---

**Last Updated**: January 2026  
**Platform**: iOS 14.0+  
**GURU Version**: 1.0.0
