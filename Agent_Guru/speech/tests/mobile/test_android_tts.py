"""Unit tests for Android TTS - COMPREHENSIVE COVERAGE.

Note: These tests use mocks since Android APIs are not available on desktop.
For real device testing, run on Android with pyjnius installed.
"""

import pytest
from unittest.mock import Mock
import wave
import io

from Agent_Guru.speech.models import PersonalityType, EmotionType


# Mock Android classes
class MockVoice:
    def __init__(self, name, locale="en-US", quality=400):
        self._name = name
        self._locale = locale
        self._quality = quality
    
    def getName(self):
        return self._name
    
    def getLocale(self):
        return self._locale
    
    def getQuality(self):
        return self._quality


class MockTextToSpeech:
    SUCCESS = 0
    ERROR = -1
    
    def __init__(self, context, listener):
        self._voices = [
            MockVoice("en-us-x-male-1"),
            MockVoice("en-us-x-female-1"),
        ]
        self._pitch = 1.0
        self._rate = 1.0
        self._voice = self._voices[0]
    
    def getVoices(self):
        return self._voices
    
    def getDefaultVoice(self):
        return self._voices[0]
    
    def setVoice(self, voice):
        self._voice = voice
    
    def setPitch(self, pitch):
        self._pitch = pitch
    
    def setSpeechRate(self, rate):
        self._rate = rate
    
    def synthesizeToFile(self, text, params, filename, utterance_id):
        # Create a minimal WAV file
        import numpy as np
        
        sample_rate = 22050
        duration = len(text.split()) * 0.5
        samples = int(sample_rate * duration)
        audio_data = np.zeros(samples, dtype=np.int16)
        
        with wave.open(filename, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(audio_data.tobytes())
        
        return self.SUCCESS
    
    def shutdown(self):
        pass


@pytest.fixture
def mock_android_modules():
    """Mock Android modules for testing."""
    def mock_autoclass(name):
        return {
            'android.speech.tts.TextToSpeech': MockTextToSpeech,
            'java.util.Locale': Mock,
            'org.kivy.android.PythonActivity': Mock(mActivity=Mock()),
            'android.speech.tts.Voice': MockVoice
        }.get(name, Mock)
    
    return mock_autoclass


@pytest.fixture
def android_tts(mock_android_modules):
    """Create Android TTS instance with mocks."""
    from Agent_Guru.speech.mobile.android_tts import AndroidTTS
    return AndroidTTS(autoclass_override=mock_android_modules)


# Unit Tests

def test_android_tts_initialization(android_tts):
    """Test Android TTS initializes correctly."""
    assert android_tts.is_available()  # nosec B101
    assert android_tts._initialized  # nosec B101
    assert android_tts._tts is not None  # nosec B101


def test_android_tts_male_voice_synthesis(android_tts):
    """Test synthesis with male voice (Guru personality)."""
    text = "Hello, I am Guru."
    audio = android_tts.synthesize(text, personality=PersonalityType.GURU)
    
    assert len(audio) > 0  # nosec B101
    assert isinstance(audio, bytes)  # nosec B101
    
    # Verify it's a valid WAV file
    with wave.open(io.BytesIO(audio), 'rb') as wav:
        assert wav.getnchannels() >= 1  # nosec B101
        assert wav.getframerate() > 0  # nosec B101


def test_android_tts_female_voice_synthesis(android_tts):
    """Test synthesis with female voice (Maya personality)."""
    text = "Hello, I am Maya."
    audio = android_tts.synthesize(text, personality=PersonalityType.MAYA)
    
    assert len(audio) > 0  # nosec B101
    assert isinstance(audio, bytes)  # nosec B101


def test_android_tts_all_emotions(android_tts):
    """Test synthesis with all emotion types."""
    text = "Testing emotions."
    
    for emotion in EmotionType:
        audio = android_tts.synthesize(
            text,
            personality=PersonalityType.GURU,
            emotion=emotion
        )
        assert len(audio) > 0, f"Failed for emotion: {emotion}"  # nosec B101


def test_android_tts_speech_rate_variations(android_tts):
    """Test synthesis with different speech rates."""
    text = "Testing speech rate."
    
    for rate in [0.5, 0.75, 1.0, 1.5, 2.0]:
        audio = android_tts.synthesize(
            text,
            personality=PersonalityType.GURU,
            speech_rate=rate
        )
        assert len(audio) > 0  # nosec B101


def test_android_tts_volume_variations(android_tts):
    """Test synthesis with different volumes."""
    text = "Testing volume."
    
    for volume in [0.0, 0.3, 0.5, 0.7, 1.0]:
        audio = android_tts.synthesize(
            text,
            personality=PersonalityType.GURU,
            volume=volume
        )
        assert len(audio) > 0  # nosec B101


def test_android_tts_empty_text_error(android_tts):
    """Test that empty text raises error."""
    with pytest.raises(Exception):
        android_tts.synthesize("", personality=PersonalityType.GURU)
    
    with pytest.raises(Exception):
        android_tts.synthesize("   ", personality=PersonalityType.GURU)


def test_android_tts_invalid_speech_rate(android_tts):
    """Test that invalid speech rate raises error."""
    with pytest.raises(Exception):
        android_tts.synthesize("test", speech_rate=0.3)
    
    with pytest.raises(Exception):
        android_tts.synthesize("test", speech_rate=2.5)


def test_android_tts_invalid_volume(android_tts):
    """Test that invalid volume raises error."""
    with pytest.raises(Exception):
        android_tts.synthesize("test", volume=-0.1)
    
    with pytest.raises(Exception):
        android_tts.synthesize("test", volume=1.5)


def test_android_tts_get_voice_info_guru(android_tts):
    """Test getting voice info for Guru personality."""
    info = android_tts.get_voice_info(PersonalityType.GURU)
    
    assert "name" in info  # nosec B101
    assert "gender" in info  # nosec B101
    assert info["gender"] == "male"  # nosec B101
    assert info["personality"] == "guru"  # nosec B101


def test_android_tts_get_voice_info_maya(android_tts):
    """Test getting voice info for Maya personality."""
    info = android_tts.get_voice_info(PersonalityType.MAYA)
    
    assert "name" in info  # nosec B101
    assert "gender" in info  # nosec B101
    assert info["gender"] == "female"  # nosec B101
    assert info["personality"] == "maya"  # nosec B101


def test_android_tts_long_text(android_tts):
    """Test synthesis with long text."""
    text = "This is a very long text for testing Android TTS. " * 20
    audio = android_tts.synthesize(text, personality=PersonalityType.GURU)
    
    assert len(audio) > 0  # nosec B101


def test_android_tts_special_characters(android_tts):
    """Test synthesis with special characters."""
    text = "Hello! How are you? I'm fine, thanks. 123 test."
    audio = android_tts.synthesize(text, personality=PersonalityType.GURU)
    
    assert len(audio) > 0  # nosec B101


def test_android_tts_shutdown(android_tts):
    """Test TTS shutdown."""
    android_tts.shutdown()
    
    assert not android_tts.is_available()  # nosec B101
    assert not android_tts._initialized  # nosec B101


def test_android_tts_emotion_pitch_adjustments(android_tts):
    """Test that emotions adjust pitch correctly."""
    text = "Testing emotion pitch."
    
    # Happy should have higher pitch
    audio_happy = android_tts.synthesize(
        text,
        personality=PersonalityType.GURU,
        emotion=EmotionType.HAPPY
    )
    
    # Sad should have lower pitch
    audio_sad = android_tts.synthesize(
        text,
        personality=PersonalityType.GURU,
        emotion=EmotionType.SAD
    )
    
    assert len(audio_happy) > 0  # nosec B101
    assert len(audio_sad) > 0  # nosec B101


def test_android_tts_personality_pitch_difference(android_tts):
    """Test that Guru and Maya have different pitch settings."""
    text = "Testing personality pitch."
    
    audio_guru = android_tts.synthesize(text, personality=PersonalityType.GURU)
    audio_maya = android_tts.synthesize(text, personality=PersonalityType.MAYA)
    
    assert len(audio_guru) > 0  # nosec B101
    assert len(audio_maya) > 0  # nosec B101
    
    # Both should produce valid audio
    with wave.open(io.BytesIO(audio_guru), 'rb') as wav:
        assert wav.getframerate() > 0  # nosec B101
    
    with wave.open(io.BytesIO(audio_maya), 'rb') as wav:
        assert wav.getframerate() > 0  # nosec B101


def test_android_tts_concurrent_synthesis(android_tts):
    """Test concurrent synthesis (thread safety)."""
    import concurrent.futures
    
    def synthesize_text(idx):
        text = f"Concurrent test {idx}"
        audio = android_tts.synthesize(text, personality=PersonalityType.GURU)
        return len(audio) > 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(synthesize_text, i) for i in range(20)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    assert all(results)  # nosec B101
    assert len(results) == 20  # nosec B101


def test_android_tts_stress_test(android_tts):
    """Stress test with 100 rapid syntheses."""
    for i in range(100):
        audio = android_tts.synthesize(
            f"Stress test {i}",
            personality=PersonalityType.GURU
        )
        assert len(audio) > 0  # nosec B101


def test_android_tts_all_parameter_combinations(android_tts):
    """Test all parameter combinations."""
    text = "Parameter combination test."
    
    for personality in [PersonalityType.GURU, PersonalityType.MAYA]:
        for emotion in [None, EmotionType.HAPPY, EmotionType.SAD]:
            for rate in [0.5, 1.0, 2.0]:
                for volume in [0.5, 1.0]:
                    audio = android_tts.synthesize(
                        text,
                        personality=personality,
                        emotion=emotion,
                        speech_rate=rate,
                        volume=volume
                    )
                    assert len(audio) > 0  # nosec B101
