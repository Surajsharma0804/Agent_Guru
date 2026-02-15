# Implementation Plan: Platform Integration System

## Overview

This implementation plan breaks down the Platform Integration System into incremental, testable steps. The approach follows a bottom-up strategy: first implementing core abstractions and platform detection, then building platform-specific implementations, and finally integrating everything with comprehensive testing.

Each task builds on previous work, ensuring that code is integrated and functional at every step. Testing tasks are marked as optional with "*" to allow for faster MVP development while maintaining the option for comprehensive test coverage.

## Tasks

- [ ] 1. Set up project structure and core abstractions
  - Create directory structure: `guru_platform/` with subdirectories for `core/`, `windows/`, `macos/`, `linux/`, `hardware/`
  - Define base exception classes in `guru_platform/exceptions.py`
  - Define core data models in `guru_platform/models.py` (PlatformInfo, CommandResult, ProcessInfo, SystemInfo, MemoryInfo, DiskInfo, NetworkInterface, GPUInfo, BatteryInfo, UserInfo, ServiceStatus)
  - Set up logging configuration in `guru_platform/logging_config.py`
  - Create `__init__.py` files for all packages
  - Set up `pyproject.toml` with dependencies: psutil, GPUtil, pywin32 (Windows), pyobjc (macOS), dbus-python (Linux)
  - _Requirements: 10.4_

- [ ]* 1.1 Write unit tests for data models
  - Test that all dataclass fields are properly typed
  - Test dataclass instantiation with valid and invalid data
  - _Requirements: All requirements (data models used throughout)_

- [ ] 2. Implement platform detection
  - [ ] 2.1 Create PlatformDetector class in `guru_platform/core/detector.py`
    - Implement `detect()` method using `platform.system()`, `platform.version()`, `platform.machine()`
    - Implement `is_windows()`, `is_macos()`, `is_linux()` helper methods
    - Raise UnsupportedPlatformError for unsupported platforms
    - _Requirements: 1.1, 1.2, 1.3_

  - [ ]* 2.2 Write property test for platform detection
    - **Property 1: Platform Detection Correctness**
    - **Validates: Requirements 1.1, 1.2**
    - Mock platform.system() with different values and verify correct OS identification
    - Test with Hypothesis generating platform names

  - [ ]* 2.3 Write unit test for unsupported platform error
    - Mock platform.system() to return unsupported OS
    - Verify UnsupportedPlatformError is raised with descriptive message
    - _Requirements: 1.3_

- [ ] 3. Implement permission management
  - [ ] 3.1 Create PermissionManager class in `guru_platform/core/permissions.py`
    - Implement `is_elevated()` using `os.geteuid()` on Unix, `ctypes.windll.shell32.IsUserAnAdmin()` on Windows
    - Implement `require_elevated()` that raises PermissionError if not elevated
    - Implement `can_access_path()` using `os.access()`
    - Implement `get_current_user()` using `os.getuid()`, `pwd` module on Unix, `getpass` module
    - _Requirements: 7.1, 7.2, 7.3, 7.6_

  - [ ]* 3.2 Write property test for elevated privilege detection
    - **Property 17: Elevated Privilege Detection**
    - **Validates: Requirements 7.2**
    - Mock privilege check functions and verify correct detection

  - [ ]* 3.3 Write property test for permission errors
    - **Property 18: Permission Errors When Insufficient**
    - **Property 19: Permission Errors Are Descriptive**
    - **Validates: Requirements 7.3, 7.6**
    - Mock non-elevated status and verify PermissionError is raised with required level in message

- [ ] 4. Implement base platform integration interface
  - [ ] 4.1 Create PlatformIntegration abstract base class in `guru_platform/core/platform_integration.py`
    - Define abstract methods: `execute_command()`, `get_process_list()`, `start_process()`, `terminate_process()`, `get_system_info()`
    - Add permission validation decorator that calls PermissionManager before operations
    - Add error logging decorator that logs failures with context
    - _Requirements: 10.1, 10.6_

  - [ ]* 4.2 Write unit tests for decorators
    - Test permission validation decorator calls PermissionManager
    - Test error logging decorator logs with platform name, operation, and error details
    - _Requirements: 10.1, 10.6_

- [ ] 5. Implement hardware monitoring
  - [ ] 5.1 Create HardwareMonitor class in `guru_platform/hardware/monitor.py`
    - Implement `get_cpu_usage()` using `psutil.cpu_percent()`
    - Implement `get_memory_info()` using `psutil.virtual_memory()`
    - Implement `get_disk_usage()` using `psutil.disk_usage()`
    - Implement `get_network_interfaces()` using `psutil.net_if_addrs()` and `psutil.net_if_stats()`
    - Implement `get_gpu_info()` using GPUtil with try/except to return None if unavailable
    - Implement `get_battery_info()` using `psutil.sensors_battery()` returning None if no battery
    - Add timeout handling to ensure all queries complete within 1 second
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.8_

  - [ ]* 5.2 Write property test for hardware metrics validity
    - **Property 9: Hardware Metrics Are Valid**
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4**
    - Test that CPU percentages are 0-100, memory values are non-negative, all fields present

  - [ ]* 5.3 Write property test for GPU metrics when available
    - **Property 10: GPU Metrics When Available**
    - **Validates: Requirements 5.5**
    - Mock GPUtil to return GPU data and verify valid ranges

  - [ ]* 5.4 Write property test for hardware query performance
    - **Property 11: Hardware Query Performance**
    - **Validates: Requirements 5.6**
    - Use pytest-benchmark to verify queries complete within 1 second

  - [ ]* 5.5 Write property test for unavailable metrics
    - **Property 12: Unavailable Metrics Return None**
    - **Validates: Requirements 5.8**
    - Mock missing hardware and verify None is returned, not exceptions

- [ ] 6. Checkpoint - Ensure core components work
  - Verify PlatformDetector correctly identifies current OS
  - Verify PermissionManager correctly detects current privilege level
  - Verify HardwareMonitor returns valid metrics for current system
  - Run all tests and ensure they pass
  - Ask the user if questions arise

- [ ] 7. Implement Windows integration
  - [ ] 7.1 Create WindowsIntegration class in `guru_platform/windows/integration.py`
    - Inherit from PlatformIntegration
    - Implement `execute_command()` using `subprocess.run()`
    - Implement `get_process_list()` using `psutil.process_iter()`
    - Implement `start_process()` using `subprocess.Popen()` returning PID
    - Implement `terminate_process()` using `psutil.Process(pid).terminate()` or `.kill()` based on force flag
    - Implement `get_system_info()` using `platform` module and `psutil`
    - _Requirements: 2.1, 2.6, 2.7, 6.1, 6.2, 6.3, 6.4, 6.6_

  - [ ] 7.2 Add Windows registry operations to WindowsIntegration
    - Implement `read_registry_key()` using `winreg.OpenKey()` and `winreg.QueryValueEx()`
    - Implement `write_registry_key()` using `winreg.CreateKeyEx()` and `winreg.SetValueEx()`
    - Add permission validation before write operations
    - Handle RegistryKeyNotFoundError when keys don't exist
    - _Requirements: 2.2, 2.3_

  - [ ] 7.3 Add Windows service management to WindowsIntegration
    - Implement `get_service_status()` using `win32service` from pywin32
    - Return ServiceStatus with name, status, and startup_type
    - _Requirements: 2.5_

  - [ ]* 7.4 Write property test for registry operations
    - **Property 3: Registry Operations Return Valid Data**
    - **Validates: Requirements 2.2**
    - Mock winreg and test that reads return values or raise RegistryKeyNotFoundError

  - [ ]* 7.5 Write property test for permission validation before writes
    - **Property 4: Permission Validation Before Writes**
    - **Validates: Requirements 2.3**
    - Verify permission check is called before registry writes

  - [ ]* 7.6 Write property test for service status validity
    - **Property 5: Service Queries Return Valid Status**
    - **Validates: Requirements 2.5**
    - Mock service queries and verify status is one of valid states

  - [ ]* 7.7 Write unit test for Windows permission errors
    - Mock insufficient permissions and verify PermissionError with details
    - _Requirements: 2.7_

- [ ] 8. Implement macOS integration
  - [ ] 8.1 Create MacOSIntegration class in `guru_platform/macos/integration.py`
    - Inherit from PlatformIntegration
    - Implement `execute_command()` using `subprocess.run()`
    - Implement `get_process_list()` using `psutil.process_iter()`
    - Implement `start_process()` using `subprocess.Popen()` returning PID
    - Implement `terminate_process()` using `psutil.Process(pid).terminate()` or `.kill()`
    - Implement `get_system_info()` using `platform` module and `psutil`
    - _Requirements: 3.1, 3.6, 3.7, 6.1, 6.2, 6.3, 6.4, 6.6_

  - [ ] 8.2 Add AppleScript execution to MacOSIntegration
    - Implement `execute_applescript()` using `subprocess.run(['osascript', '-e', script])`
    - Return stdout or raise AppleScriptError with stderr
    - _Requirements: 3.2_

  - [ ] 8.3 Add system preferences to MacOSIntegration
    - Implement `get_system_preference()` using `subprocess.run(['defaults', 'read', domain, key])`
    - Implement `set_system_preference()` using `subprocess.run(['defaults', 'write', domain, key, value])`
    - Add permission validation before write operations
    - _Requirements: 3.3_

  - [ ]* 8.4 Write property test for AppleScript execution
    - **Property 7: Command Execution Returns Complete Result**
    - **Validates: Requirements 3.2**
    - Mock subprocess and verify CommandResult has all fields

  - [ ]* 8.5 Write property test for system preferences
    - **Property 8: System Preferences Return Values**
    - **Validates: Requirements 3.3**
    - Mock defaults command and verify values are returned or errors raised

  - [ ]* 8.6 Write unit test for macOS permission errors
    - Mock insufficient permissions and verify PermissionError with details
    - _Requirements: 3.7_

- [ ] 9. Implement Linux integration
  - [ ] 9.1 Create LinuxIntegration class in `guru_platform/linux/integration.py`
    - Inherit from PlatformIntegration
    - Implement `execute_command()` using `subprocess.run()`
    - Implement `get_process_list()` using `psutil.process_iter()`
    - Implement `start_process()` using `subprocess.Popen()` returning PID
    - Implement `terminate_process()` using `psutil.Process(pid).terminate()` or `.kill()`
    - Implement `get_system_info()` using `platform` module and `psutil`
    - _Requirements: 4.1, 4.6, 4.7, 6.1, 6.2, 6.3, 6.4, 6.6_

  - [ ] 9.2 Add D-Bus integration to LinuxIntegration
    - Implement `query_dbus_service()` using dbus-python with try/except for missing library
    - Implement `get_systemd_service_status()` using D-Bus systemd interface
    - Implement `start_systemd_service()` and `stop_systemd_service()` using D-Bus
    - Fall back to subprocess if dbus-python unavailable
    - _Requirements: 4.2_

  - [ ]* 9.3 Write property test for D-Bus service queries
    - **Property 5: Service Queries Return Valid Status**
    - **Validates: Requirements 4.2**
    - Mock D-Bus and verify service status is valid

  - [ ]* 9.4 Write unit test for Linux permission errors
    - Mock insufficient permissions and verify PermissionError with details
    - _Requirements: 4.7_

- [ ] 10. Implement cross-platform process management
  - [ ]* 10.1 Write property test for process creation
    - **Property 6: Process Creation Returns Valid PID**
    - **Validates: Requirements 2.6, 3.6, 4.6, 6.2**
    - Test on all platforms that starting a process returns positive integer PID

  - [ ]* 10.2 Write property test for process list validity
    - **Property 13: Process List Contains Valid Data**
    - **Validates: Requirements 6.1**
    - Verify all processes have positive PID, non-empty name, valid status

  - [ ]* 10.3 Write property test for process termination
    - **Property 14: Process Termination Removes Process**
    - **Validates: Requirements 6.3**
    - Start test process, terminate it, verify it's no longer in process list

  - [ ]* 10.4 Write property test for process status validity
    - **Property 15: Process Status Is Valid State**
    - **Validates: Requirements 6.4**
    - Verify process status is one of: running, sleeping, stopped, zombie

- [ ] 11. Implement file system operations
  - [ ] 11.1 Add file system methods to PlatformIntegration base class
    - Implement `normalize_path()` using `os.path.normpath()` and platform-specific separators
    - Implement `get_file_permissions()` using `os.stat()` and convert to standard format
    - Implement `set_file_permissions()` using `os.chmod()` with permission validation
    - Implement `resolve_symlink()` using `os.path.realpath()`
    - Add error handling that includes file path and operation in exceptions
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [ ]* 11.2 Write property test for path normalization
    - **Property 20: Path Normalization Is Platform-Appropriate**
    - **Validates: Requirements 8.1, 8.4**
    - Test that paths use correct separators for current platform

  - [ ]* 11.3 Write property test for file permissions format
    - **Property 21: File Permissions Have Standard Format**
    - **Validates: Requirements 8.2**
    - Verify permissions are returned in consistent format across platforms

  - [ ]* 11.4 Write property test for symlink resolution
    - **Property 22: Symbolic Link Resolution**
    - **Validates: Requirements 8.5**
    - Create test symlinks and verify resolution works correctly

  - [ ]* 11.5 Write property test for file operation errors
    - **Property 16: Errors Contain Context**
    - **Validates: Requirements 8.6**
    - Verify file operation errors include path and operation name

- [ ] 12. Implement system information queries
  - [ ] 12.1 Enhance get_system_info() in all platform implementations
    - Add hostname using `platform.node()`
    - Add architecture using `platform.machine()`
    - Add Python version using `platform.python_version()` and `platform.python_implementation()`
    - Add boot time using `psutil.boot_time()`
    - Add CPU counts using `psutil.cpu_count(physical=True)` and `psutil.cpu_count(physical=False)`
    - Ensure all fields are populated in SystemInfo dataclass
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [ ]* 12.2 Write property test for system info completeness
    - **Property 23: System Info Completeness**
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6**
    - Verify all SystemInfo fields are present and non-empty/non-zero

- [ ] 13. Implement platform factory
  - [ ] 13.1 Create PlatformFactory class in `guru_platform/core/factory.py`
    - Implement `create()` static method that uses PlatformDetector
    - Return WindowsIntegration, MacOSIntegration, or LinuxIntegration based on detected OS
    - Raise UnsupportedPlatformError for unsupported platforms
    - _Requirements: 1.5_

  - [ ]* 13.2 Write property test for factory correctness
    - **Property 2: Factory Creates Correct Implementation**
    - **Validates: Requirements 1.5**
    - Mock platform detection and verify correct implementation class is returned

- [ ] 14. Implement error handling and logging
  - [ ] 14.1 Add comprehensive error handling to all operations
    - Ensure all operations log errors before raising exceptions
    - Add retry logic with exponential backoff for transient failures
    - Log retry count when operations succeed after retry
    - Ensure all error messages include platform name, operation, and details
    - _Requirements: 10.1, 10.5, 10.6_

  - [ ] 14.2 Add helpful error messages for missing dependencies
    - Catch ImportError for pywin32, pyobjc, dbus-python
    - Raise ImportError with installation instructions (pip install command)
    - _Requirements: 10.3_

  - [ ]* 14.3 Write property test for error logging
    - **Property 24: Error Logging Includes Context**
    - **Validates: Requirements 10.1, 10.6**
    - Verify log entries contain platform, operation, and error details

  - [ ]* 14.4 Write property test for retry logging
    - **Property 25: Retry Logging Includes Count**
    - **Validates: Requirements 10.5**
    - Mock transient failures and verify retry count is logged

  - [ ]* 14.5 Write unit tests for missing dependency errors
    - Mock missing imports and verify ImportError with installation instructions
    - _Requirements: 10.3_

  - [ ]* 14.6 Write unit test for unsupported operation error
    - Call unimplemented operation and verify NotImplementedError with details
    - _Requirements: 10.2_

- [ ] 15. Create unified facade interface
  - [ ] 15.1 Create PlatformIntegrationFacade in `guru_platform/__init__.py`
    - Initialize with PlatformFactory.create()
    - Expose all platform operations through simple methods
    - Expose HardwareMonitor instance
    - Expose PermissionManager instance
    - Provide convenience methods that combine common operations
    - _Requirements: All requirements (facade provides unified access)_

  - [ ] 15.2 Add module-level convenience functions
    - `get_platform()` - returns current platform integration instance
    - `get_hardware()` - returns hardware monitor instance
    - `get_permissions()` - returns permission manager instance
    - Make these singletons to avoid recreating instances

- [ ] 16. Integration testing
  - [ ]* 16.1 Write integration tests for cross-platform operations
    - Test that process management works on current platform
    - Test that hardware monitoring works on current platform
    - Test that file operations work on current platform
    - Test that system info queries work on current platform

  - [ ]* 16.2 Write integration tests for error handling
    - Test that permission errors are raised correctly
    - Test that missing dependencies are handled gracefully
    - Test that unsupported operations raise NotImplementedError

  - [ ]* 16.3 Write integration tests for end-to-end workflows
    - Test: detect platform → create integration → query hardware → list processes
    - Test: check permissions → execute command → verify result
    - Test: normalize path → check access → read file permissions

- [ ] 17. Final checkpoint - Comprehensive testing
  - Run all unit tests and verify ≥90% coverage
  - Run all property tests with 100 iterations each
  - Run all integration tests on current platform
  - Verify all 25 correctness properties are implemented and passing
  - Run linting (flake8, pylint) and ensure no errors
  - Run type checking (mypy) in strict mode
  - Format code with black
  - Ensure all tests pass, ask the user if questions arise

- [ ] 18. Documentation and examples
  - [ ] 18.1 Add comprehensive docstrings to all public methods
    - Use Google-style docstrings
    - Include Args, Returns, Raises sections
    - Add usage examples in docstrings

  - [ ] 18.2 Create example scripts in `examples/` directory
    - `basic_usage.py` - demonstrate platform detection and basic operations
    - `hardware_monitoring.py` - demonstrate hardware monitoring
    - `process_management.py` - demonstrate process management
    - `permission_checking.py` - demonstrate permission validation

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (25 total)
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end workflows
- All code must pass linting (flake8, pylint ≥9.0), type checking (mypy strict), and formatting (black)
- Git commit and push after completing each major task (not sub-tasks)
