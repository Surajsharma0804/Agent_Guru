"""
Example: Application Control with Platform Integration System

This example demonstrates how to use the Platform Integration System
for cross-platform application launching, window management, and control.

Performance: O(1) for application operations
Security: All operations validated with permission checks
"""

import sys
import time
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from guru_platform.controllers.application_control import ApplicationController
from guru_platform.platform_detector import PlatformDetector


def example_launch_applications():
    """Example: Launch applications by name."""
    print("=" * 60)
    print("Example 1: Launch Applications")
    print("=" * 60)
    
    controller = ApplicationController()
    platform_info = PlatformDetector.detect()
    
    print(f"\nCurrent platform: {platform_info.os_name}")
    
    # Platform-specific application names
    if platform_info.os_name == "Windows":
        apps = ["notepad", "calc"]
    elif platform_info.os_name == "macOS":
        apps = ["TextEdit", "Calculator"]
    else:  # Linux
        apps = ["gedit", "gnome-calculator"]
    
    print(f"\n1. Launching applications:")
    launched_apps = []
    
    for app_name in apps:
        try:
            print(f"   Launching: {app_name}")
            success = controller.open_application(app_name)
            if success:
                print(f"   ✓ {app_name} launched successfully")
                launched_apps.append(app_name)
            else:
                print(f"   ✗ Failed to launch {app_name}")
        except Exception as e:
            print(f"   ✗ Error launching {app_name}: {e}")
    
    # Wait for applications to open
    if launched_apps:
        print(f"\n2. Waiting 3 seconds for applications to open...")
        time.sleep(3)
        
        # Close applications
        print(f"\n3. Closing applications:")
        for app_name in launched_apps:
            try:
                controller.close_application(app_name)
                print(f"   ✓ {app_name} closed")
            except Exception as e:
                print(f"   ✗ Error closing {app_name}: {e}")


def example_window_management():
    """Example: Window management operations."""
    print("\n" + "=" * 60)
    print("Example 2: Window Management")
    print("=" * 60)
    
    controller = ApplicationController()
    platform_info = PlatformDetector.detect()
    
    # Launch a test application
    if platform_info.os_name == "Windows":
        app_name = "notepad"
    elif platform_info.os_name == "macOS":
        app_name = "TextEdit"
    else:
        app_name = "gedit"
    
    print(f"\n1. Launching {app_name} for window management demo")
    try:
        controller.open_application(app_name)
        print(f"   ✓ Application launched")
        time.sleep(2)
        
        # Minimize window
        print(f"\n2. Minimizing window")
        controller.minimize_window(app_name)
        print(f"   ✓ Window minimized")
        time.sleep(1)
        
        # Restore window
        print(f"\n3. Restoring window")
        controller.restore_window(app_name)
        print(f"   ✓ Window restored")
        time.sleep(1)
        
        # Maximize window
        print(f"\n4. Maximizing window")
        controller.maximize_window(app_name)
        print(f"   ✓ Window maximized")
        time.sleep(1)
        
        # Focus window
        print(f"\n5. Focusing window")
        controller.focus_window(app_name)
        print(f"   ✓ Window focused")
        time.sleep(1)
        
        # Close application
        print(f"\n6. Closing application")
        controller.close_application(app_name)
        print(f"   ✓ Application closed")
        
    except Exception as e:
        print(f"   ✗ Error: {e}")


def example_application_switching():
    """Example: Switch between multiple applications."""
    print("\n" + "=" * 60)
    print("Example 3: Application Switching")
    print("=" * 60)
    
    controller = ApplicationController()
    platform_info = PlatformDetector.detect()
    
    # Launch multiple applications
    if platform_info.os_name == "Windows":
        apps = ["notepad", "calc"]
    elif platform_info.os_name == "macOS":
        apps = ["TextEdit", "Calculator"]
    else:
        apps = ["gedit", "gnome-calculator"]
    
    print(f"\n1. Launching multiple applications:")
    launched = []
    for app in apps:
        try:
            controller.open_application(app)
            launched.append(app)
            print(f"   ✓ Launched: {app}")
            time.sleep(1)
        except Exception as e:
            print(f"   ✗ Error launching {app}: {e}")
    
    if len(launched) >= 2:
        print(f"\n2. Switching between applications:")
        
        # Switch to first app
        print(f"   Switching to: {launched[0]}")
        controller.focus_window(launched[0])
        time.sleep(1)
        
        # Switch to second app
        print(f"   Switching to: {launched[1]}")
        controller.focus_window(launched[1])
        time.sleep(1)
        
        # Use Alt+Tab to switch
        print(f"\n3. Using Alt+Tab to switch")
        controller.alt_tab()
        time.sleep(1)
        
        # Close all applications
        print(f"\n4. Closing all applications:")
        for app in launched:
            try:
                controller.close_application(app)
                print(f"   ✓ Closed: {app}")
            except Exception as e:
                print(f"   ✗ Error closing {app}: {e}")


def example_browser_control():
    """Example: Open browser and navigate to URL."""
    print("\n" + "=" * 60)
    print("Example 4: Browser Control")
    print("=" * 60)
    
    controller = ApplicationController()
    
    # Open browser with URL
    url = "https://www.example.com"
    print(f"\n1. Opening browser with URL: {url}")
    
    try:
        controller.open_url(url)
        print(f"   ✓ Browser opened with URL")
        
        # Wait for browser to open
        print(f"\n2. Waiting 5 seconds...")
        time.sleep(5)
        
        # Note: Browser will remain open for user to close manually
        print(f"\n3. Browser remains open (close manually)")
        
    except Exception as e:
        print(f"   ✗ Error: {e}")


def example_get_running_applications():
    """Example: List all running applications."""
    print("\n" + "=" * 60)
    print("Example 5: List Running Applications")
    print("=" * 60)
    
    controller = ApplicationController()
    
    print(f"\n1. Getting list of running applications:")
    try:
        apps = controller.get_running_applications()
        
        print(f"\n   Found {len(apps)} running applications:")
        # Show first 10 applications
        for i, app in enumerate(apps[:10]):
            print(f"   {i+1}. {app['name']} (PID: {app['pid']})")
        
        if len(apps) > 10:
            print(f"   ... and {len(apps) - 10} more")
            
    except Exception as e:
        print(f"   ✗ Error: {e}")


def example_application_by_path():
    """Example: Launch application by full path."""
    print("\n" + "=" * 60)
    print("Example 6: Launch Application by Path")
    print("=" * 60)
    
    controller = ApplicationController()
    platform_info = PlatformDetector.detect()
    
    # Platform-specific application paths
    if platform_info.os_name == "Windows":
        app_path = "C:\\Windows\\System32\\notepad.exe"
    elif platform_info.os_name == "macOS":
        app_path = "/System/Applications/TextEdit.app"
    else:
        app_path = "/usr/bin/gedit"
    
    print(f"\n1. Launching application by path:")
    print(f"   Path: {app_path}")
    
    try:
        if Path(app_path).exists():
            controller.open_application_by_path(app_path)
            print(f"   ✓ Application launched")
            
            # Wait and close
            time.sleep(2)
            app_name = Path(app_path).stem
            controller.close_application(app_name)
            print(f"   ✓ Application closed")
        else:
            print(f"   ⚠ Application path does not exist")
            
    except Exception as e:
        print(f"   ✗ Error: {e}")


def main():
    """Run all application control examples."""
    print("\n" + "=" * 60)
    print("Agent Guru Platform Integration - Application Control Examples")
    print("=" * 60)
    
    print("\n⚠ Note: These examples will launch and close applications.")
    print("   Make sure you have saved any important work before continuing.")
    
    input("\nPress Enter to continue...")
    
    try:
        # Run all examples
        example_launch_applications()
        example_window_management()
        example_application_switching()
        example_browser_control()
        example_get_running_applications()
        example_application_by_path()
        
        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
