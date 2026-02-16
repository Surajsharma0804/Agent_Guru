# Remaining Spec Updates - NO MERCY MODE

## Completed ✅
1. ✅ guru-speech-engine - Always-on background service, mobile platforms, battery optimization
2. ✅ guru-llm-runtime - Explicit mobile API-only, cost tracking, API key management

## Remaining (3/5)

### 3. guru-platform-integration ⚠️ HIGH PRIORITY
**Status**: Needs major mobile platform additions
**Estimated Time**: 8 hours

**Required Updates**:
```markdown
### Requirement X: Android Platform Integration

1. THE Platform_Integration SHALL use Android Intent system for app launching
2. THE Platform_Integration SHALL use Accessibility Service for text input and UI automation
3. THE Platform_Integration SHALL use Storage Access Framework for file operations
4. THE Platform_Integration SHALL use NotificationManager for notifications
5. THE Platform_Integration SHALL use ActivityManager for process management
6. THE Platform_Integration SHALL use AudioManager for volume control
7. THE Platform_Integration SHALL use Settings API for system settings
8. THE Platform_Integration SHALL request appropriate permissions (ACCESSIBILITY_SERVICE, WRITE_SETTINGS, etc.)

### Requirement Y: iOS Platform Integration

1. THE Platform_Integration SHALL use URL schemes for app launching
2. THE Platform_Integration SHALL use Shortcuts automation for complex actions
3. THE Platform_Integration SHALL use Files app integration for file operations
4. THE Platform_Integration SHALL use UserNotifications for notifications
5. THE Platform_Integration SHALL use AVAudioSession for audio control
6. THE Platform_Integration SHALL use Settings bundle for system settings
7. THE Platform_Integration SHALL request appropriate permissions (Automation, Files, etc.)
```

### 4. guru-deployment-system ⚠️ HIGH PRIORITY
**Status**: Needs mobile app deployment
**Estimated Time**: 6 hours

**Required Updates**:
```markdown
### Requirement X: Android App Deployment

1. THE Deployment_System SHALL create APK for sideloading
2. THE Deployment_System SHALL create AAB (Android App Bundle) for Play Store
3. THE Deployment_System SHALL include Play Store listing (title, description, screenshots, icon)
4. THE Deployment_System SHALL pass Play Store security review requirements
5. THE Deployment_System SHALL implement in-app updates using Play Core Library
6. THE Deployment_System SHALL support staged rollouts
7. THE Deployment_System SHALL include crash reporting (Firebase Crashlytics)
8. THE Deployment_System SHALL support multiple APK variants (arm64-v8a, armeabi-v7a, x86_64)

### Requirement Y: iOS App Deployment

1. THE Deployment_System SHALL create IPA for TestFlight distribution
2. THE Deployment_System SHALL create App Store submission package
3. THE Deployment_System SHALL include App Store listing (title, description, screenshots, icon)
4. THE Deployment_System SHALL pass App Store review guidelines
5. THE Deployment_System SHALL implement in-app updates
6. THE Deployment_System SHALL support TestFlight beta testing
7. THE Deployment_System SHALL include crash reporting (Firebase Crashlytics)
8. THE Deployment_System SHALL support universal binary (iPhone + iPad)

### Requirement Z: Onboarding Integration

1. THE Deployment_System SHALL launch onboarding wizard on first run
2. THE Deployment_System SHALL skip onboarding if already completed
3. THE Deployment_System SHALL allow re-running onboarding from settings
4. THE Deployment_System SHALL integrate with platform-specific setup flows
5. THE Deployment_System SHALL handle interrupted onboarding gracefully
```

### 5. guru-agent-orchestration ⚠️ MEDIUM PRIORITY
**Status**: Needs background service coordination
**Estimated Time**: 3 hours

**Required Updates**:
```markdown
### Requirement X: Background Service Orchestration

1. THE Agent_Orchestration SHALL coordinate wake word detection service lifecycle
2. THE Agent_Orchestration SHALL manage sleep/wake transitions across all components
3. THE Agent_Orchestration SHALL optimize battery usage on mobile platforms
4. THE Agent_Orchestration SHALL handle platform-specific lifecycle events (Android: onPause/onResume, iOS: applicationDidEnterBackground)
5. THE Agent_Orchestration SHALL coordinate component shutdown during low battery
6. THE Agent_Orchestration SHALL restart failed components automatically
7. THE Agent_Orchestration SHALL provide health monitoring for all services
8. THE Agent_Orchestration SHALL log all orchestration events for debugging
```

## Implementation Priority

1. **Start Now**: guru-platform-integration (blocks mobile implementation)
2. **Next**: guru-deployment-system (needed for distribution)
3. **Then**: guru-agent-orchestration (nice to have, not blocking)

## Total Remaining Time: 17 hours

All updates follow the same "NO MERCY" approach:
- ✅ Comprehensive requirements
- ✅ Platform-specific details
- ✅ Battery optimization
- ✅ Permissions and privacy
- ✅ Error handling
- ✅ User experience
- ✅ Testing requirements

## Status: 2/5 COMPLETE (40%)
