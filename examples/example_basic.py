"""
Example: Basic Transcription

This example demonstrates simple audio transcription from a file.
"""

from guru_speech import GuruSpeechEngine

def main():
    # Initialize the speech engine with default settings
    engine = GuruSpeechEngine()
    
    # Transcribe an audio file
    print("Transcribing audio file...")
    result = engine.transcribe_file("path/to/your/audio.wav")
    
    # Display the results
    print(f"\nTranscription Results:")
    print(f"Text: {result.text}")
    print(f"Language: {result.language}")
    print(f"Confidence: {result.confidence:.2f}")
    print(f"Duration: {result.duration:.2f} seconds")
    
    # Display segments with timestamps
    print(f"\nSegments ({len(result.segments)}):")
    for i, segment in enumerate(result.segments, 1):
        print(f"  {i}. [{segment.start:.2f}s - {segment.end:.2f}s] {segment.text}")

if __name__ == "__main__":
    main()
