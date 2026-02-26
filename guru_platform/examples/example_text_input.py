"""
Example: Text Input with Platform Integration System

This example demonstrates how to use the Platform Integration System
for automated text input, typing simulation, and clipboard operations.

Performance: O(n) where n is text length
Security: All operations validated with permission checks
"""

import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from guru_platform.controllers.text_input import TextInputController
from guru_platform.controllers.application_control import ApplicationController
from guru_platform.platform_detector import PlatformDetector


def example_basic_typing():
    """Example: Basic text typing into active application."""
    print("=" * 60)
    print("Example 1: Basic Text Typing")
    print("=" * 60)
    
    controller = TextInputController()
    app_controller = ApplicationController()
    platform_info = PlatformDetector.detect()
    
    # Launch text editor
    if platform_info.os_name == "Windows":
        app_name = "notepad"
    elif platform_info.os_name == "macOS":
        app_name = "TextEdit"
    else:
        app_name = "gedit"
    
    print(f"\n1. Launching {app_name}")
    try:
        app_controller.open_application(app_name)
        print(f"   ✓ Application launched")
        time.sleep(2)
        
        # Type text
        text = "Hello from Agent Guru Platform Integration!"
        print(f"\n2. Typing text: '{text}'")
        controller.type_text(text)
        print(f"   ✓ Text typed successfully")
        
        # Wait to see result
        time.sleep(2)
        
        # Close application
        print(f"\n3. Closing application")
        app_controller.close_application(app_name)
        print(f"   ✓ Application closed")
        
    except Exception as e:
        print(f"   ✗ Error: {e}")


def example_typing_with_speed():
    """Example: Control typing speed."""
    print("\n" + "=" * 60)
    print("Example 2: Typing with Speed Control")
    print("=" * 60)
    
    controller = TextInputController()
    app_controller = ApplicationController()
    platform_info = PlatformDetector.detect()
    
    # Launch text editor
    if platform_info.os_name == "Windows":
        app_name = "notepad"
    elif platform_info.os_name == "macOS":
        app_name = "TextEdit"
    else:
        app_name = "gedit"
    
    print(f"\n1. Launching {app_name}")
    try:
        app_controller.open_application(app_name)
        time.sleep(2)
        
        # Fast typing
        print(f"\n2. Fast typing (0.01s per character)")
        controller.type_text("Fast typing example", interval=0.01)
        time.sleep(1)
        
        # Press Enter
        controller.press_key("enter")
        time.sleep(0.5)
        
        # Slow typing
        print(f"\n3. Slow typing (0.1s per character)")
        controller.type_text("Slow typing example", interval=0.1)
        time.sleep(1)
        
        # Close application
        print(f"\n4. Closing application")
        app_controller.close_application(app_name)
        
    except Exception as e:
        print(f"   ✗ Error: {e}")


def example_special_characters():
    """Example: Type special characters and Unicode."""
    print("\n" + "=" * 60)
    print("Example 3: Special Characters and Unicode")
    print("=" * 60)
    
    controller = TextInputController()
    app_controller = ApplicationController()
    platform_info = PlatformDetector.detect()
    
    # Launch text editor
    if platform_info.os_name == "Windows":
        app_name = "notepad"
    elif platform_info.os_name == "macOS":
        app_name = "TextEdit"
    else:
        app_name = "gedit"
    
    print(f"\n1. Launching {app_name}")
    try:
        app_controller.open_application(app_name)
        time.sleep(2)
        
        # Type special characters
        print(f"\n2. Typing special characters")
        special_text = "Special: !@#$%^&*()_+-=[]{}|;':\",./<>?"
        controller.type_text(special_text)
        controller.press_key("enter")
        time.sleep(1)
        
        # Type Unicode characters
        print(f"\n3. Typing Unicode characters")
        unicode_text = "Unicode: 你好 مرحبا Привет 🚀 ✓ ♥"
        controller.type_text(unicode_text)
        time.sleep(2)
        
        # Close application
        print(f"\n4. Closing application")
        app_controller.close_application(app_name)
        
    except Exception as e:
        print(f"   ✗ Error: {e}")


def example_clipboard_operations():
    """Example: Clipboard copy and paste operations."""
    print("\n" + "=" * 60)
    print("Example 4: Clipboard Operations")
    print("=" * 60)
    
    controller = TextInputController()
    
    # Copy text to clipboard
    text_to_copy = "This text is copied to clipboard!"
    print(f"\n1. Copying to clipboard: '{text_to_copy}'")
    controller.copy_to_clipboard(text_to_copy)
    print(f"   ✓ Text copied to clipboard")
    
    # Read from clipboard
    print(f"\n2. Reading from clipboard")
    clipboard_content = controller.get_clipboard_content()
    print(f"   Clipboard content: '{clipboard_content}'")
    
    # Verify
    if clipboard_content == text_to_copy:
        print(f"   ✓ Clipboard content matches")
    else:
        print(f"   ✗ Clipboard content does not match")


def example_keyboard_shortcuts():
    """Example: Execute keyboard shortcuts."""
    print("\n" + "=" * 60)
    print("Example 5: Keyboard Shortcuts")
    print("=" * 60)
    
    controller = TextInputController()
    app_controller = ApplicationController()
    platform_info = PlatformDetector.detect()
    
    # Launch text editor
    if platform_info.os_name == "Windows":
        app_name = "notepad"
    elif platform_info.os_name == "macOS":
        app_name = "TextEdit"
    else:
        app_name = "gedit"
    
    print(f"\n1. Launching {app_name}")
    try:
        app_controller.open_application(app_name)
        time.sleep(2)
        
        # Type some text
        print(f"\n2. Typing text")
        controller.type_text("This text will be selected and copied.")
        time.sleep(1)
        
        # Select all (Ctrl+A or Cmd+A)
        print(f"\n3. Selecting all text (Ctrl+A / Cmd+A)")
        if platform_info.os_name == "macOS":
            controller.hotkey("command", "a")
        else:
            controller.hotkey("ctrl", "a")
        time.sleep(0.5)
        
        # Copy (Ctrl+C or Cmd+C)
        print(f"\n4. Copying text (Ctrl+C / Cmd+C)")
        if platform_info.os_name == "macOS":
            controller.hotkey("command", "c")
        else:
            controller.hotkey("ctrl", "c")
        time.sleep(0.5)
        
        # Press Enter to move to new line
        controller.press_key("enter")
        time.sleep(0.5)
        
        # Paste (Ctrl+V or Cmd+V)
        print(f"\n5. Pasting text (Ctrl+V / Cmd+V)")
        if platform_info.os_name == "macOS":
            controller.hotkey("command", "v")
        else:
            controller.hotkey("ctrl", "v")
        time.sleep(2)
        
        # Close application
        print(f"\n6. Closing application")
        app_controller.close_application(app_name)
        
    except Exception as e:
        print(f"   ✗ Error: {e}")


def example_multiline_text():
    """Example: Type multiline text with formatting."""
    print("\n" + "=" * 60)
    print("Example 6: Multiline Text")
    print("=" * 60)
    
    controller = TextInputController()
    app_controller = ApplicationController()
    platform_info = PlatformDetector.detect()
    
    # Launch text editor
    if platform_info.os_name == "Windows":
        app_name = "notepad"
    elif platform_info.os_name == "macOS":
        app_name = "TextEdit"
    else:
        app_name = "gedit"
    
    print(f"\n1. Launching {app_name}")
    try:
        app_controller.open_application(app_name)
        time.sleep(2)
        
        # Type multiline text
        print(f"\n2. Typing multiline text")
        lines = [
            "Agent Guru Platform Integration",
            "===================================",
            "",
            "Features:",
            "- Cross-platform support",
            "- Text input automation",
            "- Clipboard operations",
            "- Keyboard shortcuts",
            "",
            "Thank you for using Agent Guru!"
        ]
        
        for line in lines:
            controller.type_text(line)
            controller.press_key("enter")
            time.sleep(0.2)
        
        print(f"   ✓ Multiline text typed successfully")
        time.sleep(2)
        
        # Close application
        print(f"\n3. Closing application")
        app_controller.close_application(app_name)
        
    except Exception as e:
        print(f"   ✗ Error: {e}")


def main():
    """Run all text input examples."""
    print("\n" + "=" * 60)
    print("Agent Guru Platform Integration - Text Input Examples")
    print("=" * 60)
    
    print("\n⚠ Note: These examples will control keyboard and mouse.")
    print("   Do not move the mouse or type during execution.")
    print("   Make sure you have saved any important work.")
    
    input("\nPress Enter to continue...")
    
    try:
        # Run all examples
        example_basic_typing()
        example_typing_with_speed()
        example_special_characters()
        example_clipboard_operations()
        example_keyboard_shortcuts()
        example_multiline_text()
        
        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
