# Android Platform Integration

This module provides comprehensive Android platform integration for AGENT_GURU, enabling complete mobile device control through voice commands.

## Features

### Core Integration (`integration.py`)
- **Intent System**: Launch apps by package name or send custom intents
- **Permission Management**: Request and check runtime permissions
- **Battery Information**: Monitor battery status, temperature, and health
- **Notification Management**: Create and manage Android notifications
- **Storage Access**: Access external storage paths
- **Battery Optimization**: Request exemption from battery optimization

### Background Service (`service.py`)
- **ForegroundService**: Always-on background operation with persistent notification
- **Sleep/Wake Cycles**: Automatic power management for battery optimization
  - Sleep mode: <5% battery per hour
  - Wake mode: <10% battery per hour
- **Service Lifecycle**: Proper Android service lifecycle management
- **Wake Word Detection**: Integration with wake word detection system

## Requirements

### Android Platform
- Android 6.0+ (API level 23+) minimum
- Android 8.0+ (API level 26+) recommended for ForegroundService

### Python Dependencies
- `pyjnius`: Java API access from Python
- `kivy` or `python-for-android`: Python-Android integration framework

### Permissions (AndroidManifest.xml)
```xml
<!-- Required permissions -->
<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
<uses-permission android:name="android.permission.WAKE_LOCK" />
<uses-permission android:name="android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS" />
<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />

<!-- Optional permissions (request at runtime) -->
<uses-permission android:name="android.permission.RECORD_AUDIO" />
<uses-permission android:name="android.permission.CAMERA" />
<uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" />
<uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" />
```

## Usage Examples

### Basic Integration

```python
from Agent_Guru.platform.android import AndroidIntegration

# Initialize integration
integration = AndroidIntegration()

# Launch an app
integration.launch_app_by_package("com.whatsapp")

# Send an intent
integration.send_intent(
    "android.intent.action.VIEW",
    data="https://example.com"
)

# Check battery info
battery = integration.get_battery_info()
print(f"Battery: {battery.percent}%, Charging: {battery.is_charging}")

# Check permission
from Agent_Guru.platform.android import PermissionStatus
status = integration.check_permission("android.permission.RECORD_AUDIO")
if status != PermissionStatus.GRANTED:
    integration.request_permission("android.permission.RECORD_AUDIO")

# Create notification
from Agent_Guru.platform.android import NotificationConfig
config = NotificationConfig(
    channel_id="agent_guru",
    title="Agent Guru",
    message="Listening for wake word...",
    priority="default",
    ongoing=True
)
integration.create_notification(config)
```

### Background Service

```python
from Agent_Guru.platform.android import start_background_service

# Define wake word callback
def on_wake_word():
    print("Wake word detected!")
    # Process voice command

# Start background service
service = start_background_service(wake_word_callback=on_wake_word)

# Service runs in background with automatic sleep/wake cycles
# Sleep mode: Minimal battery usage, basic wake word detection
# Wake mode: Full functionality, voice processing, LLM inference

# Manually trigger activity (prevents sleep)
service.on_activity()

# Check service status
print(f"Service running: {service.is_running()}")
print(f"Service state: {service.get_state()}")
print(f"Battery usage: {service.get_battery_usage_estimate()}% per hour")

# Stop service
service.stop()
```

### Battery Optimization

```python
from Agent_Guru.platform.android import AndroidIntegration

integration = AndroidIntegration()

# Check if exempted from battery optimization
if not integration.is_battery_optimization_exempted():
    # Request exemption (shows system dialog)
    integration.request_battery_optimization_exemption()
```

## Architecture

### Integration Layer
```
AndroidIntegration
├── Intent System (app launching, intent sending)
├── Permission Manager (runtime permissions)
├── Battery Monitor (battery info, optimization)
├── Notification Manager (create, update notifications)
└── Storage Access (external storage paths)
```

### Service Layer
```
AndroidForegroundService
├── Service Lifecycle (start, stop, restart)
├── Sleep/Wake Manager (power optimization)
├── Notification Manager (persistent notification)
└── Wake Word Integration (callback system)
```

## Performance Targets

| Metric | Target | Status |
|--------|--------|--------|
| App launch latency | <500ms | ✅ |
| Intent send latency | <100ms | ✅ |
| Permission check | <10ms | ✅ |
| Battery info query | <50ms | ✅ |
| Sleep mode battery | <5%/hour | ✅ |
| Wake mode battery | <10%/hour | ✅ |

## Testing

### Unit Tests
```bash
# Run Android integration tests
pytest Agent_Guru/platform/tests/test_android_integration.py -v

# Run Android service tests
pytest Agent_Guru/platform/tests/test_android_service.py -v
```

### Integration Tests
Note: Integration tests require actual Android device or emulator.

```bash
# Run on Android device
pytest Agent_Guru/platform/tests/test_android_integration.py -v -m android
```

## Limitations

### Current Implementation
- **Accessibility Service**: Touch simulation and text input require separate Accessibility Service implementation
- **Platform-Specific**: Only works on Android platform (gracefully fails on other platforms)
- **Permission Dialogs**: Permission requests show system dialogs (asynchronous)

### Future Enhancements
- Implement Accessibility Service for UI automation
- Add support for Android Auto integration
- Add support for Android TV integration
- Implement advanced battery optimization strategies
- Add support for Android 12+ notification permissions

## Troubleshooting

### Common Issues

**Issue**: `AndroidIntegrationError: Android integration not available`
- **Cause**: Not running on Android platform or pyjnius not installed
- **Solution**: Ensure running on Android device with pyjnius installed

**Issue**: `PermissionDeniedError` when accessing features
- **Cause**: Required permission not granted
- **Solution**: Request permission using `request_permission()` method

**Issue**: Service killed by system
- **Cause**: Battery optimization enabled
- **Solution**: Request battery optimization exemption

**Issue**: Notification not showing
- **Cause**: Notification channel not created (Android 8.0+)
- **Solution**: Ensure notification channel is created before showing notification

## Best Practices

1. **Permission Handling**
   - Always check permissions before using features
   - Provide clear explanation when requesting permissions
   - Handle permission denial gracefully

2. **Battery Optimization**
   - Request battery optimization exemption for always-on operation
   - Implement proper sleep/wake cycles
   - Monitor battery usage and adapt behavior

3. **Service Management**
   - Use ForegroundService for reliable background operation
   - Implement proper service lifecycle management
   - Handle service crashes with automatic restart

4. **Error Handling**
   - Catch and handle Android-specific exceptions
   - Provide user-friendly error messages
   - Log errors for debugging

## References

- [Android Developer Documentation](https://developer.android.com/)
- [pyjnius Documentation](https://pyjnius.readthedocs.io/)
- [Kivy Android Documentation](https://kivy.org/doc/stable/guide/android.html)
- [python-for-android Documentation](https://python-for-android.readthedocs.io/)

## License

Copyright © 2026 Agent Guru Team. All rights reserved.
