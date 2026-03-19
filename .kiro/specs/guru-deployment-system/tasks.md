# Implementation Plan: Deployment System

## Overview

This implementation plan breaks down the Deployment System into discrete coding tasks for implementing professional installers, onboarding flow integration, and auto-update mechanisms for AGENT_GURU.

**Key Features**:
- Professional Windows MSI installer
- Professional macOS DMG installer
- Onboarding flow integration (profile, biometrics, LLM config)
- Auto-update mechanism
- Dependency management

## Task Completion Protocol

After completing EACH task:
1. ✅ Run all tests for that task
2. ✅ Verify all tests pass
3. ✅ Commit changes with descriptive message
4. ✅ Push to GitHub immediately
5. ✅ Mark task as complete in this file

## Tasks

### Phase 1: Project Setup

- [x] **Task 1: Project Structure and Dependencies**
  - Create `guru_deployment/` package directory structure
  - Create `requirements.txt` with dependencies
  - Create `tests/` directory structure
  - _Requirements: Req 12 (Python Implementation)_
  - **Tests Required**: None (setup task)
  - **GitHub Push**: ✅ Required after completion

### Phase 2: Installer Creation

- [x] **Task 2: Windows MSI Installer**
  - Implement Windows installer using WiX Toolset
  - Include all dependencies
  - Registry entries
  - Start menu shortcuts
  - Auto-launch onboarding on first run
  - _Requirements: Req 14 (Desktop Installer)_
  - **Tests Required**:
    - Unit tests for installer generation
    - Integration tests for installation
  - **GitHub Push**: ✅ Required after completion

- [x] **Task 3: macOS DMG Installer**
  - Implement macOS installer
  - Application bundle creation
  - Code signing
  - Notarization
  - Auto-launch onboarding on first run
  - _Requirements: Req 14 (Desktop Installer)_
  - **Tests Required**:
    - Unit tests for installer generation
    - Integration tests for installation
  - **GitHub Push**: ✅ Required after completion

- [x] **Task 4: Linux Package Creation**
  - Implement Linux packages (DEB, RPM, AppImage)
  - Dependency management
  - Desktop integration
  - Auto-launch onboarding on first run
  - _Requirements: Req 14 (Desktop Installer)_
  - **Tests Required**:
    - Unit tests for package generation
    - Integration tests for installation
  - **GitHub Push**: ✅ Required after completion

- [x] **Task 5: Android APK/AAB Builder** ⚠️ CRITICAL FOR MOBILE
  - Implement `mobile/android_builder.py`:
    - `AndroidAppBuilder` class
    - buildozer/python-for-android integration
    - APK generation for sideloading
    - AAB generation for Play Store
    - Code signing with release keystore
    - ProGuard/R8 obfuscation
    - Firebase Crashlytics integration
  - Create `buildozer.spec` configuration
  - Create `AndroidManifest.xml` template
  - _Requirements: Req 11 (Android App Deployment)_
  - **Tests Required**:
    - Unit tests for build configuration
    - Integration tests for APK/AAB generation
    - Signing tests
  - **GitHub Push**: ✅ Required after completion

- [x] **Task 6: iOS IPA Builder** ⚠️ CRITICAL FOR MOBILE
  - Implement `mobile/ios_builder.py`:
    - `IOSAppBuilder` class
    - Kivy-iOS/BeeWare integration
    - IPA generation for TestFlight/App Store
    - Code signing with Apple Developer certificate
    - Provisioning profile management
    - Firebase Crashlytics integration
  - Create `Info.plist` template
  - Create Xcode project configuration
  - _Requirements: Req 12 (iOS App Deployment)_
  - **Tests Required**:
    - Unit tests for build configuration
    - Integration tests for IPA generation
    - Signing tests
  - **GitHub Push**: ✅ Required after completion

- [x] **Task 7: Play Store / App Store Upload** ⚠️ CRITICAL FOR MOBILE
  - Implement `mobile/store_uploader.py`:
    - `PlayStoreUploader` class (Google Play Developer API)
    - `AppStoreUploader` class (App Store Connect API)
    - Automated upload with release tracks
    - Release notes generation
    - Screenshot and metadata upload
  - _Requirements: Req 11, Req 12 (App Store Deployment)_
  - **Tests Required**:
    - Unit tests for API integration
    - Mock tests for upload flow
  - **GitHub Push**: ✅ Required after completion

### Phase 3: Onboarding Integration

- [x] **Task 8: Onboarding Flow** ⚠️ CRITICAL FOR UX
  - Implement onboarding UI (PyQt5 or Tkinter for desktop, Kivy for mobile)
  - Profile setup (gender, age, DOB, name)
  - Biometric enrollment integration (guru-security-cryptography)
  - LLM configuration (Ollama vs cloud APIs, API key input)
  - API key management (secure storage in OS keychain)
  - Permission granting flows
  - Progress indicator and navigation
  - Platform-specific UI (Material Design on Android, HIG on iOS)
  - _Requirements: Req 13 (Onboarding Integration)_
  - **Tests Required**:
    - Unit tests for all onboarding steps
    - Integration tests with security system
    - Integration tests with LLM runtime
    - UI tests for all platforms
  - **GitHub Push**: ✅ Required after completion

### Phase 4: Auto-Update System

- [x] **Task 9: Update Manager**
  - Implement update checking
  - Download and verify updates
  - Apply updates safely
  - Rollback on failure
  - In-app updates for mobile (Play Core Library, App Store mechanisms)
  - _Requirements: Req 14 (Auto-Update)_
  - **Tests Required**:
    - Unit tests for update checking
    - Unit tests for update application
    - Integration tests for rollback
  - **GitHub Push**: ✅ Required after completion

### Phase 5: Testing and Documentation

- [x] **Task 10: Comprehensive Test Suite**
  - Implement all tests
  - Achieve minimum 80% code coverage
  - Test all platforms (Windows, macOS, Linux, Android, iOS)
  - _Requirements: All testing requirements_
  - **Tests Required**:
    - All tests passing
    - Coverage report >80%
  - **GitHub Push**: ✅ Required after completion

- [x] **Task 11: Documentation**
  - Create installation guide for all platforms
  - Create app store submission guide
  - Create README.md
  - _Requirements: Documentation requirements_
  - **Tests Required**: None (documentation task)
  - **GitHub Push**: ✅ Required after completion

## Testing Summary

### Unit Tests
- Installer generation (all platforms)
- Mobile app building (APK/AAB, IPA)
- Onboarding workflows
- Update mechanisms

### Integration Tests
- End-to-end installation (all platforms)
- Onboarding integration with security and LLM
- Update application
- App store upload

### Coverage Goals
- Minimum 80% line coverage

## Dependencies

This component depends on:
- guru-security-cryptography (for biometric enrollment)
- guru-llm-runtime (for LLM configuration)
- guru-platform-integration (for platform detection and permissions)

This component is used by:
- End users (installation)

## Mobile Deployment Summary

### New Mobile Tasks (5-7):
- Task 5: Android APK/AAB Builder (buildozer, signing, Play Store)
- Task 6: iOS IPA Builder (Kivy-iOS/BeeWare, signing, App Store)
- Task 7: Play Store / App Store Upload (automated submission)

### Mobile-Specific Requirements:
- Android: buildozer or python-for-android, ProGuard/R8, Firebase Crashlytics
- iOS: Kivy-iOS or BeeWare, Apple Developer certificate, provisioning profiles
- Onboarding: Platform-specific UI (Material Design, HIG)
- In-app updates: Play Core Library (Android), App Store mechanisms (iOS)
- Automated CI/CD: GitHub Actions with macOS runner for iOS builds

### Total Tasks: 11 (was 7, added 4 mobile tasks + extended 1 onboarding task)

