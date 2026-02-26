"""
Example: Messaging Control with Platform Integration System

This example demonstrates how to use the Platform Integration System
for automated messaging through WhatsApp, Telegram, Slack, and other apps.

Performance: O(1) for message operations
Security: All operations validated with permission checks
"""

import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from guru_platform.controllers.messaging import MessagingController
from guru_platform.platform_detector import PlatformDetector


def example_whatsapp_messaging():
    """Example: Send message via WhatsApp."""
    print("=" * 60)
    print("Example 1: WhatsApp Messaging")
    print("=" * 60)
    
    controller = MessagingController()
    
    print(f"\n1. Opening WhatsApp")
    try:
        controller.open_whatsapp()
        print(f"   ✓ WhatsApp opened")
        
        # Wait for WhatsApp to load
        print(f"\n2. Waiting for WhatsApp to load (5 seconds)...")
        time.sleep(5)
        
        # Note: Actual message sending requires contact selection
        print(f"\n3. To send a message:")
        print(f"   - Use search_contact() to find contact")
        print(f"   - Use send_message() to send message")
        print(f"\n   Example:")
        print(f"   controller.search_contact('John Doe')")
        print(f"   controller.send_message('Hello from Agent Guru!')")
        
        # Keep WhatsApp open for manual interaction
        print(f"\n4. WhatsApp remains open for manual interaction")
        print(f"   (Close manually when done)")
        
    except Exception as e:
        print(f"   ✗ Error: {e}")


def example_telegram_messaging():
    """Example: Send message via Telegram."""
    print("\n" + "=" * 60)
    print("Example 2: Telegram Messaging")
    print("=" * 60)
    
    controller = MessagingController()
    
    print(f"\n1. Opening Telegram")
    try:
        controller.open_telegram()
        print(f"   ✓ Telegram opened")
        
        # Wait for Telegram to load
        print(f"\n2. Waiting for Telegram to load (5 seconds)...")
        time.sleep(5)
        
        print(f"\n3. To send a message:")
        print(f"   - Use search_contact() to find contact")
        print(f"   - Use send_message() to send message")
        
        # Keep Telegram open for manual interaction
        print(f"\n4. Telegram remains open for manual interaction")
        print(f"   (Close manually when done)")
        
    except Exception as e:
        print(f"   ✗ Error: {e}")


def example_slack_messaging():
    """Example: Send message via Slack."""
    print("\n" + "=" * 60)
    print("Example 3: Slack Messaging")
    print("=" * 60)
    
    controller = MessagingController()
    
    print(f"\n1. Opening Slack")
    try:
        controller.open_slack()
        print(f"   ✓ Slack opened")
        
        # Wait for Slack to load
        print(f"\n2. Waiting for Slack to load (5 seconds)...")
        time.sleep(5)
        
        print(f"\n3. To send a message:")
        print(f"   - Use search_channel() to find channel")
        print(f"   - Use send_message() to send message")
        
        # Keep Slack open for manual interaction
        print(f"\n4. Slack remains open for manual interaction")
        print(f"   (Close manually when done)")
        
    except Exception as e:
        print(f"   ✗ Error: {e}")


def example_discord_messaging():
    """Example: Send message via Discord."""
    print("\n" + "=" * 60)
    print("Example 4: Discord Messaging")
    print("=" * 60)
    
    controller = MessagingController()
    
    print(f"\n1. Opening Discord")
    try:
        controller.open_discord()
        print(f"   ✓ Discord opened")
        
        # Wait for Discord to load
        print(f"\n2. Waiting for Discord to load (5 seconds)...")
        time.sleep(5)
        
        print(f"\n3. To send a message:")
        print(f"   - Use search_server() to find server")
        print(f"   - Use search_channel() to find channel")
        print(f"   - Use send_message() to send message")
        
        # Keep Discord open for manual interaction
        print(f"\n4. Discord remains open for manual interaction")
        print(f"   (Close manually when done)")
        
    except Exception as e:
        print(f"   ✗ Error: {e}")


def example_contact_search():
    """Example: Search for contacts in messaging apps."""
    print("\n" + "=" * 60)
    print("Example 5: Contact Search")
    print("=" * 60)
    
    controller = MessagingController()
    
    print(f"\n1. Contact search functionality:")
    print(f"   - search_contact(name): Search for contact by name")
    print(f"   - search_channel(name): Search for channel by name")
    print(f"   - search_server(name): Search for server by name")
    
    print(f"\n2. Example usage:")
    print(f"   # Search for WhatsApp contact")
    print(f"   controller.open_whatsapp()")
    print(f"   controller.search_contact('John Doe')")
    print(f"   controller.send_message('Hello!')")
    
    print(f"\n   # Search for Slack channel")
    print(f"   controller.open_slack()")
    print(f"   controller.search_channel('general')")
    print(f"   controller.send_message('Team update!')")


def example_message_templates():
    """Example: Use message templates for common messages."""
    print("\n" + "=" * 60)
    print("Example 6: Message Templates")
    print("=" * 60)
    
    controller = MessagingController()
    
    print(f"\n1. Common message templates:")
    
    templates = {
        "greeting": "Hello! How are you doing today?",
        "meeting_reminder": "Reminder: We have a meeting at {time}",
        "status_update": "Status update: {status}",
        "thank_you": "Thank you for your help!",
        "follow_up": "Following up on our previous conversation..."
    }
    
    for name, template in templates.items():
        print(f"   {name}: {template}")
    
    print(f"\n2. Example usage:")
    print(f"   # Send greeting")
    print(f"   controller.send_message(templates['greeting'])")
    
    print(f"\n   # Send meeting reminder with time")
    print(f"   message = templates['meeting_reminder'].format(time='3:00 PM')")
    print(f"   controller.send_message(message)")


def example_platform_specific_messaging():
    """Example: Platform-specific messaging features."""
    print("\n" + "=" * 60)
    print("Example 7: Platform-Specific Features")
    print("=" * 60)
    
    platform_info = PlatformDetector.detect()
    controller = MessagingController()
    
    print(f"\nCurrent platform: {platform_info.os_name}")
    
    if platform_info.os_name == "Windows":
        print(f"\n1. Windows-specific features:")
        print(f"   - Native notifications")
        print(f"   - System tray integration")
        print(f"   - Windows shortcuts")
        
    elif platform_info.os_name == "macOS":
        print(f"\n1. macOS-specific features:")
        print(f"   - iMessage integration")
        print(f"   - Notification Center")
        print(f"   - Spotlight search")
        
    else:  # Linux
        print(f"\n1. Linux-specific features:")
        print(f"   - D-Bus notifications")
        print(f"   - Desktop environment integration")
        print(f"   - Command-line tools")


def example_batch_messaging():
    """Example: Send messages to multiple contacts."""
    print("\n" + "=" * 60)
    print("Example 8: Batch Messaging")
    print("=" * 60)
    
    controller = MessagingController()
    
    print(f"\n1. Batch messaging workflow:")
    print(f"   - Open messaging app")
    print(f"   - Iterate through contact list")
    print(f"   - Send personalized message to each")
    
    print(f"\n2. Example code:")
    print(f"   contacts = ['Alice', 'Bob', 'Charlie']")
    print(f"   message_template = 'Hello {{name}}, this is a reminder!'")
    print(f"   ")
    print(f"   controller.open_whatsapp()")
    print(f"   for contact in contacts:")
    print(f"       controller.search_contact(contact)")
    print(f"       message = message_template.format(name=contact)")
    print(f"       controller.send_message(message)")
    print(f"       time.sleep(2)  # Wait between messages")
    
    print(f"\n3. Best practices:")
    print(f"   - Add delays between messages to avoid spam detection")
    print(f"   - Personalize messages for each recipient")
    print(f"   - Verify contact exists before sending")
    print(f"   - Handle errors gracefully")


def main():
    """Run all messaging examples."""
    print("\n" + "=" * 60)
    print("Agent Guru Platform Integration - Messaging Examples")
    print("=" * 60)
    
    print("\n⚠ Note: These examples will open messaging applications.")
    print("   Make sure you are logged in to the apps you want to test.")
    print("   Actual message sending requires manual contact selection.")
    
    input("\nPress Enter to continue...")
    
    try:
        # Run all examples
        example_whatsapp_messaging()
        example_telegram_messaging()
        example_slack_messaging()
        example_discord_messaging()
        example_contact_search()
        example_message_templates()
        example_platform_specific_messaging()
        example_batch_messaging()
        
        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)
        
        print("\n📝 Note: For actual message sending, you need to:")
        print("   1. Be logged in to the messaging app")
        print("   2. Have contacts/channels available")
        print("   3. Grant necessary permissions")
        
    except Exception as e:
        print(f"\n✗ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
