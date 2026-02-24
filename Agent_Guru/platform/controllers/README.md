# Platform Integration Controllers

This package provides specialized controllers for different types of platform operations, enabling complete laptop control through voice commands for the AGENT_GURU AI operating system.

## Available Controllers

### 1. FileOperationsController

Complete file and directory operations with audit logging and permission management.

**Features:**
- Create, read, update, delete files
- Move, copy, rename files
- Directory operations
- Permission checks before destructive operations
- Comprehensive audit logging

**Usage:**
```python
from Agent_Guru.platform.controllers import FileOperationsController

controller = FileOperationsController(audit_log_path="audit.log")

# Create a file
controller.create_file("test.txt", "Hello, World!")

# Read file content
content = controller.read_file("test.txt")

# Copy file
controller.copy_file("test.txt", "test_copy.txt")

# Delete file
controller.delete_file("test_copy.txt", confirm=True)
```

### 2. ApplicationController

Complete application and window management across all platforms.

**Features:**
- Open applications by name
- Close applications (graceful or force)
- Minimize, maximize, restore windows
- Focus specific windows
- Switch between applications (Alt+Tab simulation)
- List running applications and windows
- Get active window information
- Platform-specific optimizations (Windows, macOS, Linux)

**Usage:**
```python
from Agent_Guru.platform.controllers import ApplicationController

controller = ApplicationController()

# Open application
pid = controller.open_application("notepad")

# Minimize window
controller.minimize_window("Notepad")

# Maximize window
controller.maximize_window("Notepad")

# Focus window
controller.focus_window("Chrome")

# Switch to application
controller.switch_to_application("Chrome")

# List all windows
windows = controller.list_windows()
for window in windows:
    print(f"{window.title} - {window.state.value}")

# Get active window
active = controller.get_active_window()
if active:
    print(f"Active: {active.title}")

# Close application
controller.close_application("notepad")
```

## Platform Support

### Windows
- Uses `pywin32` for native Windows API access
- Full window management support
- Application resolution from Program Files
- Registry-based application discovery

### macOS
- Uses AppleScript for window management
- Application bundle (.app) support
- Native macOS window operations
- Accessibility API integration

### Linux
- Uses `wmctrl` for window management (primary)
- Falls back to `xdotool` if wmctrl unavailable
- Standard Linux application paths
- Desktop environment integration

## Performance Characteristics

### ApplicationController

| Operation | Time Complexity | Space Complexity | Latency Target |
|-----------|----------------|------------------|----------------|
| Application launch | O(1) | O(1) | <100ms |
| Window enumeration | O(n) | O(n) | <50ms |
| Window operations | O(1) | O(1) | <50ms |
| Process search | O(n) | O(1) | <50ms |

Where n = number of windows or processes

## Error Handling

All controllers provide comprehensive error handling:

- `FileNotFoundError`: Application or file not found
- `PermissionError`: Insufficient permissions
- `ProcessLookupError`: Process not found
- `RuntimeError`: General operation failure

All errors include detailed context about what failed and why.

## Testing

Comprehensive test suites are provided for all controllers:

```bash
# Run all controller tests
pytest Agent_Guru/platform/controllers/tests/ -v

# Run specific controller tests
pytest Agent_Guru/platform/controllers/tests/test_application_control.py -v

# Run with coverage
pytest Agent_Guru/platform/controllers/tests/ --cov=Agent_Guru.platform.controllers
```

## Examples

See the `examples/` directory for complete demonstrations:

- `examples/application_control_demo.py` - Application control demonstration

## Architecture

Controllers follow a consistent pattern:

1. **Platform Detection**: Automatically detect current OS
2. **Platform Integration**: Load platform-specific implementation
3. **Unified API**: Provide consistent interface across platforms
4. **Error Handling**: Comprehensive error handling with context
5. **Logging**: Detailed logging for debugging

## Future Controllers

Planned controllers for complete laptop control:

- TextInputController: Text input and clipboard management
- MessagingController: Messaging app integration
- SystemSettingsController: System settings control
- MouseController: Mouse operations
- KeyboardController: Keyboard shortcuts
- WindowManagerController: Advanced window management
- MediaController: Media playback control
- ScreenCaptureController: Screenshots and recording

## Contributing

When adding new controllers:

1. Follow the existing controller pattern
2. Provide platform-specific implementations
3. Include comprehensive tests (unit + integration)
4. Document all public APIs
5. Add usage examples
6. Update this README

## License

Part of the AGENT_GURU AI Operating System.
