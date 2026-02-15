"""
Test the complete pipeline: capture → clean → transcribe → interpret
"""

import numpy as np
import soundfile as sf
import os
from guru_speech import GuruSpeechEngine

def create_test_audio():
    """Create a simple test audio file."""
    # Create a simple sine wave audio (1 second at 16kHz)
    sample_rate = 16000
    duration = 1.0
    frequency = 440.0  # A4 note
    
    t = np.linspace(0, duration, int(sample_rate * duration))
    audio = 0.5 * np.sin(2 * np.pi * frequency * t)
    
    # Create test_audio directory if it doesn't exist
    os.makedirs("test_audio", exist_ok=True)
    
    # Save as WAV file
    test_file = "test_audio/test_sine.wav"
    sf.write(test_file, audio, sample_rate)
    
    return test_file

def test_pipeline_with_noise_reduction():
    """Test pipeline with noise reduction enabled."""
    print("Testing pipeline with noise reduction enabled...")
    
    test_file = create_test_audio()
    
    engine = GuruSpeechEngine(enable_noise_reduction=True)
    
    # Transcribe the test file
    result = engine.transcribe_file(test_file)
    
    assert result is not None
    assert result.text is not None
    assert result.language is not None
    assert 0.0 <= result.confidence <= 1.0
    assert result.duration >= 0.0
    
    print(f"✓ Pipeline with noise reduction successful")
    print(f"  Transcription: '{result.text}'")
    print(f"  Language: {result.language}, Duration: {result.duration:.2f}s")

def test_pipeline_without_noise_reduction():
    """Test pipeline with noise reduction disabled."""
    print("\nTesting pipeline with noise reduction disabled...")
    
    test_file = create_test_audio()
    
    engine = GuruSpeechEngine(enable_noise_reduction=False)
    
    # Transcribe the test file
    result = engine.transcribe_file(test_file)
    
    assert result is not None
    assert engine.noise_cleaner is None
    
    print(f"✓ Pipeline without noise reduction successful")
    print(f"  Transcription: '{result.text}'")

def test_process_voice_command_from_file():
    """Test end-to-end process_voice_command with file source."""
    print("\nTesting process_voice_command from file...")
    
    test_file = create_test_audio()
    
    engine = GuruSpeechEngine()
    
    # Process voice command from file
    result = engine.process_voice_command(source="file", file_path=test_file)
    
    assert result is not None
    assert result.raw_text is not None
    assert result.language is not None
    assert 0.0 <= result.confidence <= 1.0
    
    print(f"✓ process_voice_command from file successful")
    print(f"  Raw text: '{result.raw_text}'")
    print(f"  Is command: {result.is_command}")
    if result.is_command:
        print(f"  Action: {result.action_id}")

def test_model_reuse():
    """Test that model is reused across multiple requests."""
    print("\nTesting model reuse across requests...")
    
    test_file = create_test_audio()
    
    engine = GuruSpeechEngine()
    
    # Store reference to original model
    original_model = engine.transcriber.model
    
    # Make multiple transcription requests
    result1 = engine.transcribe_file(test_file)
    result2 = engine.transcribe_file(test_file)
    
    # Verify model is the same instance
    assert engine.transcriber.model is original_model
    
    print(f"✓ Model reuse verified - same model instance used for multiple requests")

if __name__ == "__main__":
    print("Testing GuruSpeechEngine complete pipeline...\n")
    
    test_pipeline_with_noise_reduction()
    test_pipeline_without_noise_reduction()
    test_process_voice_command_from_file()
    test_model_reuse()
    
    print("\n" + "="*60)
    print("All pipeline tests passed!")
    print("="*60)
