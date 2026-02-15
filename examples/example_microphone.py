"""
Example: Real-Time Microphone Capture

This example demonstrates real-time audio capture and transcription from the microphone.
"""

from guru_speech import GuruSpeechEngine

def main():
    # Initialize the speech engine
    engine = GuruSpeechEngine()
    
    print("Guru Speech Engine - Microphone Demo")
    print("=" * 50)
    
    # Capture and transcribe from microphone
    duration = 5.0  # Record for 5 seconds
    
    print(f"\nRecording for {duration} seconds...")
    print("Speak now!")
    
    try:
        result = engine.transcribe_microphone(duration=duration)
        
        print("\n✓ Recording complete!")
        print(f"\nTranscription:")
        print(f"  Text: {result.text}")
        print(f"  Language: {result.language}")
        print(f"  Confidence: {result.confidence:.2f}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nTroubleshooting:")
        print("  - Check that your microphone is connected")
        print("  - Verify microphone permissions are granted")
        print("  - Try a different audio device")
    
    # Process voice command from microphone
    print("\n" + "=" * 50)
    print("Voice Command Demo")
    print("=" * 50)
    print(f"\nRecording command for {duration} seconds...")
    print("Try saying: 'open youtube' or 'search for cats'")
    
    try:
        command_result = engine.process_voice_command(
            duration=duration,
            source="microphone"
        )
        
        print("\n✓ Command processed!")
        print(f"\nResults:")
        print(f"  Text: {command_result.raw_text}")
        print(f"  Is Command: {command_result.is_command}")
        
        if command_result.is_command:
            print(f"  Action: {command_result.action_id}")
            print(f"  Parameters: {command_result.parameters}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")

if __name__ == "__main__":
    main()
