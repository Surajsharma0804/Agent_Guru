"""
Test logging functionality of GuruSpeechEngine.
"""

import logging
from guru_speech import GuruSpeechEngine
from guru_speech.models import TranscriptionResult

# Configure logging to see INFO level messages
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_logging():
    """Test that logging works at INFO level."""
    print("Initializing engine (check for INFO logs)...")
    engine = GuruSpeechEngine()
    
    print("\nInterpreting command (check for INFO logs)...")
    transcription = TranscriptionResult(
        text="play music",
        language="en",
        confidence=0.95,
        segments=[],
        duration=1.5
    )
    
    result = engine.interpret_command(transcription)
    print(f"\nResult: {result.action_id}")

if __name__ == "__main__":
    test_logging()
