"""
Example: Command Detection

This example demonstrates how to detect and interpret voice commands from audio.
"""

from guru_speech import GuruSpeechEngine

def main():
    # Initialize the speech engine
    engine = GuruSpeechEngine()
    
    # Process a voice command from a file
    print("Processing voice command from file...")
    command_result = engine.process_voice_command(
        source="file",
        file_path="path/to/your/command.wav"
    )
    
    # Display the command interpretation results
    print(f"\nCommand Interpretation Results:")
    print(f"Raw Text: {command_result.raw_text}")
    print(f"Is Command: {command_result.is_command}")
    
    if command_result.is_command:
        print(f"Action ID: {command_result.action_id}")
        print(f"Parameters: {command_result.parameters}")
        print(f"Confidence: {command_result.confidence:.2f}")
        print(f"Language: {command_result.language}")
        
        # Execute action based on command
        if command_result.action_id == "OPEN_YOUTUBE":
            print("\n→ Opening YouTube...")
        elif command_result.action_id == "SEARCH":
            query = command_result.parameters.get("query", "")
            print(f"\n→ Searching for: {query}")
        elif command_result.action_id == "PLAY_MUSIC":
            print("\n→ Playing music...")
    else:
        print("\nNo command detected. Raw transcription returned.")
    
    # List all registered commands
    print("\n\nRegistered Commands:")
    commands = engine.command_interpreter.get_registered_commands()
    for cmd in commands:
        print(f"  - {cmd['action_id']}: {cmd['description']}")
        print(f"    Patterns: {', '.join(cmd['patterns'][:3])}")
        print(f"    Languages: {', '.join(cmd['languages'])}")

if __name__ == "__main__":
    main()
