"""
Example: Custom Command Registration

This example demonstrates how to register custom voice commands with the engine.
"""

from guru_speech import GuruSpeechEngine
import re

def extract_timer_duration(text: str) -> int:
    """Extract duration in minutes from timer command."""
    # Look for patterns like "5 minutes", "10 mins", etc.
    match = re.search(r'(\d+)\s*(minute|min|minutes|mins)', text.lower())
    if match:
        return int(match.group(1))
    return 5  # Default to 5 minutes

def extract_app_name(text: str) -> str:
    """Extract application name from open command."""
    # Remove the command trigger words
    text = re.sub(r'(open|launch|start)\s+', '', text.lower())
    return text.strip()

def main():
    # Initialize the speech engine
    engine = GuruSpeechEngine()
    
    print("Custom Command Registration Demo")
    print("=" * 50)
    
    # Register a custom timer command
    print("\n1. Registering TIMER command...")
    engine.command_interpreter.register_command(
        patterns=[
            "set timer for * minutes",
            "timer * minutes",
            "start timer *",
            "टाइमर * मिनट",  # Hindi
            "ਟਾਈਮਰ * ਮਿੰਟ"   # Punjabi
        ],
        action_id="SET_TIMER",
        description="Set a timer",
        languages=["en", "hi", "pa"],
        parameter_extractors={"duration": extract_timer_duration}
    )
    print("   ✓ TIMER command registered")
    
    # Register a custom app launcher command
    print("\n2. Registering APP_LAUNCHER command...")
    engine.command_interpreter.register_command(
        patterns=[
            "open *",
            "launch *",
            "start *",
            "* खोलो",      # Hindi
            "* ਖੋਲ੍ਹੋ"      # Punjabi
        ],
        action_id="OPEN_APP",
        description="Open an application",
        languages=["en", "hi", "pa"],
        parameter_extractors={"app_name": extract_app_name}
    )
    print("   ✓ APP_LAUNCHER command registered")
    
    # Register a custom weather command
    print("\n3. Registering WEATHER command...")
    engine.command_interpreter.register_command(
        patterns=[
            "what's the weather",
            "weather forecast",
            "how's the weather",
            "मौसम कैसा है",   # Hindi
            "ਮੌਸਮ ਕਿਹੋ ਜਿਹਾ ਹੈ"  # Punjabi
        ],
        action_id="GET_WEATHER",
        description="Get weather information",
        languages=["en", "hi", "pa"]
    )
    print("   ✓ WEATHER command registered")
    
    # Test the custom commands
    print("\n" + "=" * 50)
    print("Testing Custom Commands")
    print("=" * 50)
    
    test_commands = [
        "set timer for 10 minutes",
        "open spotify",
        "what's the weather"
    ]
    
    for test_text in test_commands:
        print(f"\nTest: '{test_text}'")
        
        # Create a mock transcription result
        from guru_speech.models import TranscriptionResult, TranscriptionSegment
        transcription = TranscriptionResult(
            text=test_text,
            language="en",
            confidence=0.95,
            segments=[TranscriptionSegment(
                text=test_text,
                start=0.0,
                end=2.0,
                confidence=0.95
            )],
            duration=2.0
        )
        
        # Interpret the command
        result = engine.interpret_command(transcription)
        
        if result.is_command:
            print(f"  ✓ Command detected: {result.action_id}")
            if result.parameters:
                print(f"    Parameters: {result.parameters}")
        else:
            print(f"  ✗ No command detected")
    
    # Display all registered commands
    print("\n" + "=" * 50)
    print("All Registered Commands")
    print("=" * 50)
    
    commands = engine.command_interpreter.get_registered_commands()
    for i, cmd in enumerate(commands, 1):
        print(f"\n{i}. {cmd['action_id']}")
        print(f"   Description: {cmd['description']}")
        print(f"   Languages: {', '.join(cmd['languages'])}")
        print(f"   Sample patterns: {', '.join(cmd['patterns'][:3])}")

if __name__ == "__main__":
    main()
