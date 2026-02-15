"""
Integration test for GuruSpeechEngine full pipeline.
"""

import os
from guru_speech import GuruSpeechEngine

def test_file_transcription():
    """Test transcribing an audio file."""
    # Check if test audio file exists
    test_file = "test_audio/english_sample.wav"
    if not os.path.exists(test_file):
        print(f"⚠ Skipping file transcription test - {test_file} not found")
        return
    
    engine = GuruSpeechEngine()
    result = engine.transcribe_file(test_file)
    
    assert result.text is not None
    assert len(result.text) > 0
    assert result.language in ["en", "hi", "pa", "unknown"]
    assert 0.0 <= result.confidence <= 1.0
    assert result.duration >= 0.0
    
    print(f"✓ File transcription successful: '{result.text}'")
    print(f"  Language: {result.language}, Confidence: {result.confidence:.2f}")

def test_command_interpretation():
    """Test command interpretation from transcription."""
    engine = GuruSpeechEngine()
    
    # Create a mock transcription result
    from guru_speech.models import TranscriptionResult, TranscriptionSegment
    
    transcription = TranscriptionResult(
        text="open youtube",
        language="en",
        confidence=0.95,
        segments=[],
        duration=1.5
    )
    
    command_result = engine.interpret_command(transcription)
    
    assert command_result.is_command is True
    assert command_result.action_id == "OPEN_YOUTUBE"
    assert command_result.raw_text == "open youtube"
    
    print(f"✓ Command interpretation successful: {command_result.action_id}")

def test_unrecognized_text():
    """Test that unrecognized text is passed through."""
    engine = GuruSpeechEngine()
    
    from guru_speech.models import TranscriptionResult
    
    transcription = TranscriptionResult(
        text="this is just random text",
        language="en",
        confidence=0.95,
        segments=[],
        duration=2.0
    )
    
    command_result = engine.interpret_command(transcription)
    
    assert command_result.is_command is False
    assert command_result.action_id is None
    assert command_result.raw_text == "this is just random text"
    
    print(f"✓ Unrecognized text passthrough successful")

def test_error_context_preservation():
    """Test that errors preserve context from components."""
    engine = GuruSpeechEngine()
    
    try:
        # Try to transcribe a non-existent file
        engine.transcribe_file("nonexistent_file.wav")
        assert False, "Should have raised an error"
    except Exception as e:
        # Check that error message contains component information
        error_msg = str(e)
        assert "AudioCapture" in error_msg or "GuruSpeechEngine" in error_msg
        print(f"✓ Error context preservation successful")
        print(f"  Error: {error_msg[:100]}...")

if __name__ == "__main__":
    print("Testing GuruSpeechEngine integration...")
    print()
    
    test_file_transcription()
    test_command_interpretation()
    test_unrecognized_text()
    test_error_context_preservation()
    
    print("\nAll integration tests passed!")
