"""
Example: System Settings Control with Platform Integration System

This example demonstrates how to use the Platform Integration System
for controlling system settings like volume, brightness, network, and display.

Performance: O(1) for settings operations
Security: All operations validated with permission checks
"""

import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from guru_platform.controllers.system_settings import SystemSettingsController
from guru_platform.platform_detector import PlatformDetector
from guru_platform.permissions.manager import PermissionManager


def example_volume_control():
    """Example: Control system volume."""
    print("=" * 60)
    print("Example 1: Volume Control")
    print("=" * 60)
    
    controller = SystemSettingsController()
    
    print(f"\n1. Getting current volume")
    try:
        current_volume = controller.get_volume()
        print(f"   Current volume: {current_volume}%")
        
        # Save original volume
        original_volume = current_volume
        
        # Set volume to 50%
        print(f"\n2. Setting volume to 50%")
        controller.set_volume(50)
        time.sleep(1)
        new_volume = controller.get_volume()
        print(f"   New volume: {new_volume}%")
        
        # Increase volume
        print(f"\n3. Increasing volume by 10%")
        controller.increase_volume(10)
        time.sleep(1)
        increased_volume = controller.get_volume()
        print(f"   Volume after increase: {increased_volume}%")
        
        # Decrease volume
        print(f"\n4. Decreasing volume by 10%")
        controller.decrease_volume(10)
        time.sleep(1)
        decreased_volume = controller.get_volume()
        print(f"   Volume after decrease: {decreased_volume}%")
        
        # Mute
        print(f"\n5. Muting volume")
        controller.mute()
        time.sleep(1)
        print(f"   ✓ Volume muted")
        
        # Unmute
        print(f"\n6. Unmuting volume")
        controller.unmute()
        time.sleep(1)
        print(f"   ✓ Volume unmuted")
        
        # Restore original volume
        print(f"\n7. Restoring original volume: {original_volume}%")
        controller.set_volume(original_volume)
        print(f"   ✓ Volume restored")
        
    except Exception as e:
        print(f"   ✗ Error: {e}")


def example_brightness_control():
    """Example: Control screen brightness."""
    print("\n" + "=" * 60)
    print("Example 2: Brightness Control")
    print("=" * 60)
    
    controller = SystemSettingsController()
    
    print(f"\n1. Getting current brightness")
    try:
        current_brightness = controller.get_brightness()
        print(f"   Current brightness: {current_brightness}%")
        
        # Save original brightness
        original_brightness = current_brightness
        
        # Set brightness to 50%
        print(f"\n2. Setting brightness to 50%")
        controller.set_brightness(50)
        time.sleep(1)
        new_brightness = controller.get_brightness()
        print(f"   New brightness: {new_brightness}%")
        
        # Increase brightness
        print(f"\n3. Increasing brightness by 10%")
        controller.increase_brightness(10)
        time.sleep(1)
        increased_brightness = controller.get_brightness()
        print(f"   Brightness after increase: {increased_brightness}%")
        
        # Decrease brightness
        print(f"\n4. Decreasing brightness by 10%")
        controller.decrease_brightness(10)
        time.sleep(1)
        decreased_brightness = controller.get_brightness()
        print(f"   Brightness after decrease: {decreased_brightness}%")
        
        # Restore original brightness
        print(f"\n5. Restoring original brightness: {original_brightness}%")
        controller.set_brightness(original_brightness)
        print(f"   ✓ Brightness restored")
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        print(f"   Note: Brightness control may require special permissions")


def example_network_settings():
    """Example: Control network settings."""
    print("\n" + "=" * 60)
    print("Example 3: Network Settings")
    print("=" * 60)
    
    controller = SystemSettingsController()
    
    print(f"\n1. Getting WiFi status")
    try:
        wifi_enabled = controller.is_wifi_enabled()
        print(f"   WiFi enabled: {wifi_enabled}")
        
        # Get available networks
        print(f"\n2. Getting available WiFi networks")
        networks = controller.get_available_wifi_networks()
        print(f"   Found {len(networks)} networks:")
        for i, network in enumerate(networks[:5]):
            print(f"   {i+1}. {network['ssid']} (Signal: {network['signal']}%)")
        
        # Get current network
        print(f"\n3. Getting current WiFi network")
        current_network = controller.get_current_wifi_network()
        if current_network:
            print(f"   Connected to: {current_network['ssid']}")
            print(f"   Signal strength: {current_network['signal']}%")
        else:
            print(f"   Not connected to any network")
        
        # Bluetooth status
        print(f"\n4. Getting Bluetooth status")
        bluetooth_enabled = controller.is_bluetooth_enabled()
        print(f"   Bluetooth enabled: {bluetooth_enabled}")
        
        # Airplane mode status
        print(f"\n5. Getting Airplane mode status")
        airplane_mode = controller.is_airplane_mode_enabled()
        print(f"   Airplane mode: {airplane_mode}")
        
    except Exception as e:
        print(f"   ✗ Error: {e}")


def example_display_settings():
    """Example: Control display settings."""
    print("\n" + "=" * 60)
    print("Example 4: Display Settings")
    print("=" * 60)
    
    controller = SystemSettingsController()
    
    print(f"\n1. Getting display information")
    try:
        displays = controller.get_displays()
        print(f"   Found {len(displays)} display(s):")
        
        for i, display in enumerate(displays):
            print(f"\n   Display {i+1}:")
            print(f"   - Resolution: {display['width']}x{display['height']}")
            print(f"   - Refresh rate: {display['refresh_rate']}Hz")
            print(f"   - Primary: {display['is_primary']}")
        
        # Get current resolution
        print(f"\n2. Getting current resolution")
        resolution = controller.get_resolution()
        print(f"   Current resolution: {resolution['width']}x{resolution['height']}")
        
        # Get orientation
        print(f"\n3. Getting display orientation")
        orientation = controller.get_orientation()
        print(f"   Current orientation: {orientation}")
        
    except Exception as e:
        print(f"   ✗ Error: {e}")


def example_power_settings():
    """Example: Control power settings."""
    print("\n" + "=" * 60)
    print("Example 5: Power Settings")
    print("=" * 60)
    
    controller = SystemSettingsController()
    
    print(f"\n1. Getting battery information")
    try:
        battery_info = controller.get_battery_info()
        if battery_info:
            print(f"   Battery level: {battery_info['percent']}%")
            print(f"   Power plugged: {battery_info['power_plugged']}")
            if battery_info['time_remaining']:
                hours = battery_info['time_remaining'] // 3600
                minutes = (battery_info['time_remaining'] % 3600) // 60
                print(f"   Time remaining: {hours}h {minutes}m")
        else:
            print(f"   No battery detected (desktop system)")
        
        # Get power plan
        print(f"\n2. Getting power plan")
        power_plan = controller.get_power_plan()
        print(f"   Current power plan: {power_plan}")
        
        # Get sleep settings
        print(f"\n3. Getting sleep settings")
        sleep_timeout = controller.get_sleep_timeout()
        print(f"   Sleep timeout: {sleep_timeout} minutes")
        
    except Exception as e:
        print(f"   ✗ Error: {e}")


def example_permission_requirements():
    """Example: Check permission requirements for settings."""
    print("\n" + "=" * 60)
    print("Example 6: Permission Requirements")
    print("=" * 60)
    
    permission_manager = PermissionManager()
    
    print(f"\n1. Checking current permissions")
    is_elevated = permission_manager.is_elevated()
    print(f"   Running with elevated privileges: {is_elevated}")
    
    print(f"\n2. Settings that require elevated permissions:")
    elevated_settings = [
        "Network configuration",
        "System-wide power settings",
        "Display resolution changes",
        "Bluetooth enable/disable",
        "WiFi enable/disable"
    ]
    
    for setting in elevated_settings:
        print(f"   - {setting}")
    
    print(f"\n3. Settings that work without elevation:")
    normal_settings = [
        "Volume control",
        "Brightness control (user session)",
        "Get network information",
        "Get display information",
        "Get battery information"
    ]
    
    for setting in normal_settings:
        print(f"   - {setting}")
    
    if not is_elevated:
        print(f"\n⚠ Note: Some operations may fail without elevated privileges")
        print(f"   Run as administrator/root for full functionality")


def example_platform_specific_settings():
    """Example: Platform-specific settings."""
    print("\n" + "=" * 60)
    print("Example 7: Platform-Specific Settings")
    print("=" * 60)
    
    platform_info = PlatformDetector.detect()
    controller = SystemSettingsController()
    
    print(f"\nCurrent platform: {platform_info.os_name}")
    
    if platform_info.os_name == "Windows":
        print(f"\n1. Windows-specific settings:")
        print(f"   - Windows Update settings")
        print(f"   - Windows Defender settings")
        print(f"   - Taskbar configuration")
        print(f"   - Start menu customization")
        
    elif platform_info.os_name == "macOS":
        print(f"\n1. macOS-specific settings:")
        print(f"   - Dock configuration")
        print(f"   - Mission Control settings")
        print(f"   - Spotlight preferences")
        print(f"   - Time Machine settings")
        
    else:  # Linux
        print(f"\n1. Linux-specific settings:")
        print(f"   - Desktop environment settings")
        print(f"   - Window manager configuration")
        print(f"   - System services (systemd)")
        print(f"   - Package manager settings")


def example_settings_automation():
    """Example: Automate settings based on conditions."""
    print("\n" + "=" * 60)
    print("Example 8: Settings Automation")
    print("=" * 60)
    
    controller = SystemSettingsController()
    
    print(f"\n1. Example automation scenarios:")
    
    print(f"\n   Scenario 1: Low battery mode")
    print(f"   - Reduce brightness to 30%")
    print(f"   - Lower volume to 50%")
    print(f"   - Disable Bluetooth")
    print(f"   - Enable power saver mode")
    
    print(f"\n   Scenario 2: Presentation mode")
    print(f"   - Set brightness to 100%")
    print(f"   - Disable sleep mode")
    print(f"   - Disable notifications")
    print(f"   - Set volume to 75%")
    
    print(f"\n   Scenario 3: Night mode")
    print(f"   - Reduce brightness to 20%")
    print(f"   - Enable blue light filter")
    print(f"   - Lower volume to 30%")
    print(f"   - Enable do not disturb")
    
    print(f"\n2. Example implementation:")
    print(f"   def enable_low_battery_mode():")
    print(f"       controller.set_brightness(30)")
    print(f"       controller.set_volume(50)")
    print(f"       controller.disable_bluetooth()")
    print(f"       controller.enable_power_saver()")


def main():
    """Run all system settings examples."""
    print("\n" + "=" * 60)
    print("Agent Guru Platform Integration - System Settings Examples")
    print("=" * 60)
    
    print("\n⚠ Note: These examples will modify system settings.")
    print("   Settings will be restored to original values when possible.")
    print("   Some operations may require elevated permissions.")
    
    input("\nPress Enter to continue...")
    
    try:
        # Run all examples
        example_volume_control()
        example_brightness_control()
        example_network_settings()
        example_display_settings()
        example_power_settings()
        example_permission_requirements()
        example_platform_specific_settings()
        example_settings_automation()
        
        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
