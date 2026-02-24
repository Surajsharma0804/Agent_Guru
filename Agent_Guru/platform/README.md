# Platform Integration System

## Overview

The Platform Integration System provides comprehensive cross-platform OS control, hardware abstraction, and permission management for AGENT_GURU. This component enables complete laptop and mobile device control through voice commands.

## Directory Structure

```
Agent_Guru/platform/
├── __init__.py              # Package initialization and documentation
├── README.md                # This file
│
├── windows/                 # Windows-specific integration
│   └── __init__.py
│
├── macos/                   # macOS-specific integration
│   └── __init__.py
│
├── linux/                   # Linux-specific integration
│   └── __init__.py
│
├── android/                 # Android-specific integration
│   └── __init__.py
│
├── ios/                     # iOS-specific integration
│   └── __init__.py
│
├── hardware/                # Hardware abstraction layer
│   └── __init__.py
│
├── permissions/             # Permission management
│   └── __init__.py
│
├── controllers/             # Specialized operation controllers
│   └── __init__.py
│
├── mobile/                  # Mobile-specific functionality
│   └── __init__.py
│
└── tests/                   # Test suite
    ├── __init__.py
    └── conftest.py          # Pytest fixtures
```

## Dependencies

All dependencies are managed in the root `requirements.txt` file:

### Core Dependencies
- **psutil** (>=5.9.0): Cross-platform system utilities
- **GPUtil** (>=1.4.0): GPU monitoring

### Platform-Specific Dependencies
- **pywin32** (>=306): Windows API access (Windows only)
- **pyobjc-framework-Cocoa** (>=9.2): macOS Objective-C bridge (macOS only)
- **pyobjc-framework-Quartz** (>=9.2): macOS Quartz framework (macOS only)
- **dbus-python** (>=1.3.2): Linux D-Bus integration (Linux only)

### Input Control Dependencies
- **pyautogui** (>=0.9.54): Mouse/keyboard control
- **pynput** (>=1.7.6): Keyboard/mouse input monitoring

### Testing Dependencies
- **pytest** (>=7.4.0): Test framework
- **pytest-asyncio** (>=0.21.0): Async test support
- **pytest-cov** (>=4.1.0): Coverage reporting
- **hypothesis** (>=6.92.0): Property-based testing

## Installation

Install all dependencies:

```bash
pip install -r requirements.txt
```

For platform-specific dependencies, pip will automatically install only the packages compatible with your operating system.

## Module Descriptions

### windows/
Windows-specific operations using pywin32:
- Registry access (read/write/delete keys)
- Windows service management
- Process management via Windows APIs

### macos/
macOS-specific operations using pyobjc:
- AppleScript execution
- System preferences access
- Launch services interaction
- Process management via macOS APIs

### linux/
Linux-specific operations using dbus-python:
- D-Bus service interaction
- systemd service management
- Desktop environment integration
- Process management via Linux APIs

### android/
Android-specific operations using pyjnius:
- Intent-based app launching
- Accessibility Service for UI automation
- Storage Access Framework for file operations
- Background service management

### ios/
iOS-specific operations using pyobjus:
- URL scheme app launching
- Shortcuts automation
- Files app integration
- Background modes management

### hardware/
Cross-platform hardware monitoring:
- CPU usage metrics
- Memory usage metrics
- Disk usage metrics
- Network interface information
- GPU metrics (if available)
- Mobile-specific hardware (battery, sensors, etc.)

### permissions/
Permission validation and management:
- Detect administrator/root status
- Validate required permissions
- Platform-specific permission checks
- Mobile permission request flows

### controllers/
Specialized controllers for operations:
- File operations
- Application control
- Text input
- Messaging
- System settings
- Mouse/keyboard control
- Window management
- Media control
- Screen capture

### mobile/
Mobile-specific functionality:
- Background service management
- Sleep/wake cycles
- Battery optimization
- Mobile hardware monitoring

## Testing

Run all platform integration tests:

```bash
# Run all tests
pytest Agent_Guru/platform/tests/

# Run with coverage
pytest Agent_Guru/platform/tests/ --cov=Agent_Guru.platform --cov-report=html

# Run specific test types
pytest Agent_Guru/platform/tests/ -m unit          # Unit tests
pytest Agent_Guru/platform/tests/ -m property      # Property-based tests
pytest Agent_Guru/platform/tests/ -m integration   # Integration tests
```

## Development Status

This is the initial project structure setup. Implementation tasks are tracked in:
- `.kiro/specs/guru-platform-integration/requirements.md`
- `.kiro/specs/guru-platform-integration/design.md`
- `.kiro/specs/guru-platform-integration/tasks.md`

## Next Steps

Follow the implementation tasks in order:
1. ✅ Task 1: Project Structure and Dependencies (COMPLETE)
2. Task 2: Platform Detection
3. Task 3: Windows Integration
4. Task 4: macOS Integration
5. Task 5: Linux Integration
6. Task 6: Android Integration
7. Task 7: iOS Integration
8. ... (see tasks.md for complete list)

## Performance Targets

- Platform detection: <10ms
- Hardware queries: <1s
- Permission checks: <100ms
- Command execution: Platform-dependent

## Architecture

The system uses a strategy pattern where platform-specific implementations are abstracted behind common interfaces, with specialized controllers for each operation category.
