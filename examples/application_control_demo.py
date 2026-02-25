"""
Application Control Demo

This script demonstrates the ApplicationController capabilities for
controlling applications and windows through the Platform Integration System.

Usage:
    python examples/application_control_demo.py
"""

import sys
import time
from Agent_Guru.platform.controllers import ApplicationController


def demo_application_control():
    """Demonstrate application control capabilities."""
    print("=" * 60)
    print("Application Control Demo")
    print("=" * 60)
    print()

    # Initialize controller
    controller = ApplicationController()
    print(f"✓ Initialized ApplicationController for {controller.platform}")
    print()

    # Demo 1: List running applications
    print("Demo 1: List Running Applications")
    print("-" * 60)
    apps = controller.list_running_applications()
    print(f"Found {len(apps)} running applications")
    for i, app in enumerate(apps[:5], 1):  # Show first 5
        print(f"  {i}. {app.name} (PID: {app.pid}, Windows: {len(app.windows)})")
    print()

    # Demo 2: List windows
    print("Demo 2: List All Windows")
    print("-" * 60)
    windows = controller.list_windows()
    print(f"Found {len(windows)} visible windows")
    for i, window in enumerate(windows[:5], 1):  # Show first 5
        state = window.state.value
        active = "ACTIVE" if window.is_active else ""
        print(f"  {i}. {window.title[:50]} [{state}] {active}")
    print()

    # Demo 3: Get active window
    print("Demo 3: Get Active Window")
    print("-" * 60)
    active_window = controller.get_active_window()
    if active_window:
        print(f"Active window: {active_window.title}")
        print(f"  PID: {active_window.pid}")
        print(f"  State: {active_window.state.value}")
        print(f"  Position: {active_window.position}")
    else:
        print("No active window found")
    print()

    # Demo 4: Open and close application (platform-specific)
    if sys.platform == "win32":
        print("Demo 4: Open and Close Notepad (Windows)")
        print("-" * 60)
        try:
            # Open Notepad
            print("Opening Notepad...")
            pid = controller.open_application("notepad")
            print(f"✓ Opened Notepad (PID: {pid})")
            time.sleep(2)

            # List windows to find Notepad
            windows = controller.list_windows()
            notepad_window = None
            for window in windows:
                if "notepad" in window.title.lower():
                    notepad_window = window
                    break

            if notepad_window:
                print(f"✓ Found Notepad window: {notepad_window.title}")

                # Minimize window
                print("Minimizing Notepad...")
                controller.minimize_window(notepad_window.title)
                print("✓ Minimized")
                time.sleep(1)

                # Restore window
                print("Restoring Notepad...")
                controller.restore_window(notepad_window.title)
                print("✓ Restored")
                time.sleep(1)

                # Maximize window
                print("Maximizing Notepad...")
                controller.maximize_window(notepad_window.title)
                print("✓ Maximized")
                time.sleep(1)

                # Restore again
                print("Restoring Notepad...")
                controller.restore_window(notepad_window.title)
                print("✓ Restored")
                time.sleep(1)

            # Close Notepad
            print("Closing Notepad...")
            controller.close_application("notepad")
            print("✓ Closed Notepad")

        except Exception as e:
            print(f"✗ Error: {e}")
        print()

    elif sys.platform == "darwin":
        print("Demo 4: Open and Close TextEdit (macOS)")
        print("-" * 60)
        try:
            # Open TextEdit
            print("Opening TextEdit...")
            pid = controller.open_application("TextEdit")
            print(f"✓ Opened TextEdit (PID: {pid})")
            time.sleep(2)

            # Close TextEdit
            print("Closing TextEdit...")
            controller.close_application("TextEdit")
            print("✓ Closed TextEdit")

        except Exception as e:
            print(f"✗ Error: {e}")
        print()

    else:
        print("Demo 4: Platform-specific demo not available for Linux")
        print("-" * 60)
        print("Linux application control requires wmctrl or xdotool")
        print()

    print("=" * 60)
    print("Demo Complete!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        demo_application_control()
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
