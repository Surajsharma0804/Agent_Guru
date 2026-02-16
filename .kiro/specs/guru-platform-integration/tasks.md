# Implementation Plan: Platform Integration System

## Overview

This implementation plan breaks down the Platform Integration System into discrete coding tasks for implementing comprehensive laptop control through voice commands. This system enables AGENT_GURU (Guru and Maya personalities) to execute ANY laptop operation - from opening applications and typing text to sending messages, controlling system settings, and managing files.

**Key Features**:
- Complete laptop control through voice commands
- Cross-platform support (Windows, macOS, Linux)
- File, application, text input, messaging control
- Mouse, keyboard, window management
- System settings control
- Permission management for safe operations

## Task Completion Protocol

After completing EACH task:
1. ✅ Run all tests for that task
2. ✅ Verify all tests pass
3. ✅ Commit changes with descriptive message
4. ✅ Push to GitHub immediately
5. ✅ Mark task as complete in this file

## Tasks

### Phase 1: Project Setup and Core Infrastructure

- [ ] **Task 1: Project Structure and Dependencies**
  - Create `guru_platform/` package directory structure
  - Create subpackages: `windows/`, `macos/`, `linux/`, `hardware/`, `permissions/`
  - Create `requirements.txt` with dependencies:
    - psutil (cross-platform system utilities)
    - pywin32 (Windows API access)
    - pyobjc (macOS Objective-C bridge)
    - dbus-python (Linux D-Bus integration)
    - GPUtil (GPU monitoring)
    - pyautogui (mouse/keyboard control)
    - pynput (keyboard/mouse input)
    - hypothesis, pytest, pytest-cov (testing)
  - Create `tests/` directory structure
  - _Requirements: Req 11 (Python Implementation)_
  - **Tests Required**: None (setup task)
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 2: Platform Detection**
  - Implement `platform_detector.py`:
    - `PlatformDetector` class
    - `detect_os()` method returning OS name and version
    - Support for Windows, macOS, Linux detection
    - Raise error for unsupported platforms
  - _Requirements: Req 1 (Platform Detection)_
  - **Tests Required**:
    - Unit tests for each platform detection
    - Unit tests for unsupported platform error
    - Property tests for OS name validation
  - **GitHub Push**: ✅ Required after completion

### Phase 2: Platform-Specific Implementations

- [ ] **Task 3: Windows Integration**
  - Implement `windows/integration.py`:
    - `WindowsIntegration` class
    - Registry operations (read, write, delete keys)
    - Windows service management
    - Process management using pywin32
    - Permission validation
  - _Requirements: Req 2 (Windows Integration)_
  - **Tests Required**:
    - Unit tests for registry operations (Windows only)
    - Unit tests for service management
    - Unit tests for permission errors
    - Integration tests with Windows API
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 4: macOS Integration**
  - Implement `macos/integration.py`:
    - `MacOSIntegration` class
    - AppleScript execution
    - System preferences access
    - Process management using subprocess
    - Native Objective-C APIs via pyobjc
    - Permission validation
  - _Requirements: Req 3 (macOS Integration)_
  - **Tests Required**:
    - Unit tests for AppleScript execution (macOS only)
    - Unit tests for system preferences
    - Unit tests for permission errors
    - Integration tests with macOS APIs
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 5: Linux Integration**
  - Implement `linux/integration.py`:
    - `LinuxIntegration` class
    - D-Bus service management
    - systemd service control
    - Process management using subprocess
    - Permission validation
  - _Requirements: Req 4 (Linux Integration)_
  - **Tests Required**:
    - Unit tests for D-Bus operations (Linux only)
    - Unit tests for systemd service control
    - Unit tests for permission errors
    - Integration tests with Linux APIs
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 6: Android Integration** ⚠️ CRITICAL FOR MOBILE
  - Implement `android/integration.py`:
    - `AndroidIntegration` class
    - Intent system for app launching (using pyjnius)
    - Accessibility Service for UI automation
    - Storage Access Framework for file operations
    - NotificationManager integration
    - Permission request flows
    - ForegroundService implementation
    - Battery optimization handling
  - Create `android/service.py`:
    - Android ForegroundService class
    - Service lifecycle management
    - Notification creation
  - _Requirements: Req 11 (Android Integration), Req 14 (Background Service)_
  - **Tests Required**:
    - Unit tests for Intent operations (Android only)
    - Unit tests for Accessibility Service
    - Unit tests for permission handling
    - Integration tests with Android APIs
    - Battery usage tests
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 7: iOS Integration** ⚠️ CRITICAL FOR MOBILE
  - Implement `ios/integration.py`:
    - `IOSIntegration` class
    - URL scheme app launching (using pyobjus)
    - Shortcuts automation
    - Files app integration
    - UserNotifications framework
    - Permission request flows
    - Background audio mode implementation
    - Background task scheduling
  - Create `ios/service.py`:
    - iOS background service class
    - Background mode management
    - Task scheduling
  - _Requirements: Req 12 (iOS Integration), Req 14 (Background Service)_
  - **Tests Required**:
    - Unit tests for URL scheme operations (iOS only)
    - Unit tests for Shortcuts execution
    - Unit tests for permission handling
    - Integration tests with iOS frameworks
    - Battery usage tests
  - **GitHub Push**: ✅ Required after completion

### Phase 3: Hardware Abstraction

- [ ] **Task 8: Hardware Monitor**
  - Implement `hardware/monitor.py`:
    - `HardwareMonitor` class using psutil
    - CPU usage metrics
    - Memory usage metrics
    - Disk usage metrics
    - Network interface information
    - GPU metrics using GPUtil (if available)
    - Return None for unavailable metrics
    - Query response time <1 second
  - Implement `hardware/mobile_monitor.py`:
    - Mobile-specific hardware monitoring
    - Battery temperature monitoring
    - Screen brightness control
    - Cellular network information
    - GPS location services
    - Accelerometer/gyroscope data
    - Thermal state monitoring
    - Low power mode detection
  - _Requirements: Req 5 (Hardware Abstraction), Req 13 (Mobile Hardware)_
  - **Tests Required**:
    - Unit tests for all hardware metrics
    - Unit tests for unavailable hardware handling
    - Unit tests for mobile-specific metrics
    - Property tests for metric value ranges
    - Performance tests for query latency
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 9: Mobile Background Service Manager** ⚠️ CRITICAL FOR ALWAYS-ON
  - Implement `mobile/background_service.py`:
    - `MobileBackgroundService` class
    - Sleep/wake cycle management
    - Battery optimization (<5% sleep, <10% wake)
    - Wake word detection integration
    - Service lifecycle management
    - Crash recovery and restart
    - Battery usage tracking
    - Thermal state handling
  - _Requirements: Req 14 (Background Service Architecture)_
  - **Tests Required**:
    - Unit tests for sleep/wake transitions
    - Unit tests for battery optimization
    - Unit tests for service lifecycle
    - Integration tests with wake word detection
    - Battery usage measurement tests
    - Stress tests for 24-hour operation
  - **GitHub Push**: ✅ Required after completion

### Phase 4: Process Management

- [ ] **Task 10: Cross-Platform Process Manager**
  - Implement `process_manager.py`:
    - `ProcessManager` class using psutil
    - List all running processes
    - Start new processes
    - Terminate processes
    - Query process status
    - Cross-platform process operations
  - _Requirements: Req 6 (Process Management)_
  - **Tests Required**:
    - Unit tests for process listing
    - Unit tests for process start/stop
    - Unit tests for process status queries
    - Property tests for process ID validation
    - Integration tests for process lifecycle
  - **GitHub Push**: ✅ Required after completion

### Phase 5: Permission Management

- [ ] **Task 11: Permission Manager**
  - Implement `permissions/manager.py`:
    - `PermissionManager` class
    - Validate current permission level
    - Detect administrator/root status
    - Check required permissions for operations
    - Raise permission errors with clear messages
    - Platform-specific permission checks
  - Implement `permissions/mobile_permissions.py`:
    - Mobile permission request flows
    - Runtime permission handling (Android 6.0+)
    - Permission denial handling
    - Permission status checking
  - _Requirements: Req 7 (Permission Management)_
  - **Tests Required**:
    - Unit tests for permission detection
    - Unit tests for permission validation
    - Unit tests for permission error messages
    - Unit tests for mobile permission flows
    - Integration tests for elevated operations
  - **GitHub Push**: ✅ Required after completion

### Phase 6: Complete Laptop Control Operations

- [ ] **Task 12: File Operations Controller**
  - Implement `controllers/file_operations.py`:
    - `FileOperationsController` class
    - Create, read, update, delete files
    - Move, copy, rename files
    - Directory operations
    - Permission checks before destructive operations
    - Audit logging for all operations
  - _Requirements: Req 8.1 (File Operations)_
  - **Tests Required**:
    - Unit tests for all file operations
    - Unit tests for permission checks
    - Unit tests for error handling
    - Integration tests for file lifecycle
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 10: Application Control**
  - Implement `controllers/application_control.py`:
    - `ApplicationController` class
    - Open applications by name
    - Close applications
    - Minimize, maximize, restore windows
    - Switch between applications (Alt+Tab)
    - Focus specific windows
    - Platform-specific application launching
  - _Requirements: Req 8.2 (Application Control)_
  - **Tests Required**:
    - Unit tests for application launching
    - Unit tests for window management
    - Unit tests for application switching
    - Integration tests with real applications
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 11: Text Input Controller**
  - Implement `controllers/text_input.py`:
    - `TextInputController` class using pyautogui
    - Type text into active application
    - Handle special characters and Unicode
    - Typing speed control
    - Clipboard integration
  - _Requirements: Req 8.3 (Text Input)_
  - **Tests Required**:
    - Unit tests for text typing
    - Unit tests for special characters
    - Unit tests for typing speed
    - Integration tests with text editors
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 12: Messaging Controller**
  - Implement `controllers/messaging.py`:
    - `MessagingController` class
    - Open WhatsApp, Telegram, Slack
    - Send messages to contacts
    - Search for contacts
    - Platform-specific messaging integration
  - _Requirements: Req 8.4 (Messaging)_
  - **Tests Required**:
    - Unit tests for messaging app launching
    - Unit tests for message sending
    - Unit tests for contact search
    - Integration tests with messaging apps
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 13: System Settings Controller**
  - Implement `controllers/system_settings.py`:
    - `SystemSettingsController` class
    - Adjust volume
    - Adjust brightness
    - Network settings (WiFi, Bluetooth)
    - Display settings (resolution, orientation)
    - Platform-specific settings access
  - _Requirements: Req 8.7 (System Settings)_
  - **Tests Required**:
    - Unit tests for all settings operations
    - Unit tests for platform-specific settings
    - Integration tests for settings changes
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 14: Mouse and Keyboard Controller**
  - Implement `controllers/input_control.py`:
    - `MouseController` class using pyautogui
    - Move cursor, click, double-click, right-click
    - Drag and drop operations
    - `KeyboardController` class
    - Execute keyboard shortcuts (Ctrl+C, Ctrl+V, Alt+Tab)
    - Key press, release, hold operations
  - _Requirements: Req 8.8, 8.9 (Mouse/Keyboard Control)_
  - **Tests Required**:
    - Unit tests for mouse operations
    - Unit tests for keyboard shortcuts
    - Integration tests for input simulation
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 15: Window Management Controller**
  - Implement `controllers/window_management.py`:
    - `WindowManager` class
    - Arrange windows (tile, cascade)
    - Snap windows to sides
    - Manage virtual desktops
    - Platform-specific window management
  - _Requirements: Req 8.10 (Window Management)_
  - **Tests Required**:
    - Unit tests for window arrangement
    - Unit tests for window snapping
    - Integration tests for window operations
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 16: Media Control Controller**
  - Implement `controllers/media_control.py`:
    - `MediaController` class
    - Play, pause, skip media
    - Volume control for media
    - Platform-specific media key simulation
  - _Requirements: Req 8.11 (Media Control)_
  - **Tests Required**:
    - Unit tests for media operations
    - Integration tests with media players
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 17: Screenshot and Recording Controller**
  - Implement `controllers/screen_capture.py`:
    - `ScreenCaptureController` class
    - Capture screenshots
    - Start/stop screen recording
    - Save to specified locations
    - Platform-specific capture tools
  - _Requirements: Req 8.12 (Screenshot/Recording)_
  - **Tests Required**:
    - Unit tests for screenshot capture
    - Unit tests for recording start/stop
    - Integration tests for file saving
  - **GitHub Push**: ✅ Required after completion

### Phase 7: Main OS Controller and Integration

- [ ] **Task 18: Main OS Controller**
  - Implement `os_controller.py`:
    - `OSController` class (main facade)
    - Integrate all controllers
    - Route operations to appropriate controller
    - User confirmation for destructive operations
    - Audit logging for all operations
    - Error handling and recovery
  - _Requirements: All system control requirements_
  - **Tests Required**:
    - Integration tests for all operations
    - Unit tests for operation routing
    - Unit tests for confirmation prompts
    - Property tests for audit logging
  - **GitHub Push**: ✅ Required after completion

### Phase 8: Testing and Documentation

- [ ] **Task 19: Comprehensive Test Suite**
  - Implement all property-based tests (100+ iterations each)
  - Implement all unit tests for edge cases
  - Add integration tests for all workflows
  - Add performance regression tests
  - Achieve minimum 80% code coverage
  - _Requirements: All testing requirements_
  - **Tests Required**:
    - All property tests passing
    - All unit tests passing
    - Coverage report >80%
    - Performance benchmarks documented
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 20: Documentation and Examples**
  - Create example scripts:
    - `example_file_operations.py`
    - `example_application_control.py`
    - `example_text_input.py`
    - `example_messaging.py`
    - `example_system_settings.py`
  - Create comprehensive README.md
  - _Requirements: Documentation requirements_
  - **Tests Required**: None (documentation task)
  - **GitHub Push**: ✅ Required after completion

## Testing Summary

### Property-Based Tests (Hypothesis)
- Platform detection consistency
- Permission validation correctness
- Hardware metric value ranges
- Process ID validation
- File operation atomicity
- Audit logging completeness

### Unit Tests
- All platform-specific operations
- All controller methods
- Error handling for all failure modes
- Permission checks
- Confirmation prompts

### Integration Tests
- End-to-end laptop control workflows
- Cross-platform compatibility
- Real application interactions
- Performance benchmarks

### Coverage Goals
- Minimum 80% line coverage
- All error paths tested
- All platform variants tested

## Dependencies

This component depends on:
- guru-policy-engine (for permission policies)
- guru-speech-engine (for voice command interpretation)

This component is used by:
- guru-agent-orchestration (for executing voice commands)
- Main AGENT_GURU application

## Mobile Platform Summary

### New Mobile Tasks (6-9):
- Task 6: Android Integration (Intent system, Accessibility Service, ForegroundService)
- Task 7: iOS Integration (URL schemes, Shortcuts, Background audio)
- Task 8: Hardware Monitor (Extended with mobile-specific metrics)
- Task 9: Mobile Background Service Manager (Sleep/wake cycles, battery optimization)

### Mobile-Specific Requirements:
- Android: pyjnius for Java API access, Chaquopy or Kivy for Python integration
- iOS: pyobjus for Objective-C API access, Kivy or BeeWare for Python integration
- Background service with <5% battery usage in sleep mode, <10% in wake mode
- Always-on wake word detection without opening app
- Proper permission request flows with user-friendly explanations
- Thermal state monitoring and adaptive behavior
- Low power mode detection and adaptation

### Total Tasks: 21 (was 20, added 2 mobile tasks + extended 2 existing tasks)

