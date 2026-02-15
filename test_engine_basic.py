"""
Basic test to verify GuruSpeechEngine can be instantiated and used.
"""

import numpy as np
from guru_speech import GuruSpeechEngine

def test_engine_initialization():
    """Test that GuruSpeechEngine can be initialized."""
    engine = GuruSpeechEngine()
    assert engine is not None
    assert engine.transcriber is not None
    assert engine.command_interpreter is not None
    print("✓ Engine initialization successful")

def test_engine_with_noise_reduction_disabled():
    """Test that engine can be initialized with noise reduction disabled."""
    engine = GuruSpeechEngine(enable_noise_reduction=False)
    assert engine.noise_cleaner is None
    print("✓ Engine with noise reduction disabled works")

if __name__ == "__main__":
    print("Testing GuruSpeechEngine basic functionality...")
    test_engine_initialization()
    test_engine_with_noise_reduction_disabled()
    print("\nAll basic tests passed!")
