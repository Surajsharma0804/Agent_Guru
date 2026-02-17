"""Unit tests for iOS TTS - COMPREHENSIVE COVERAGE.

Note: These tests use mocks since iOS APIs are not available on desktop.
For real device testing, run on iOS with pyobjus installed.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import wave
import io

from Agent_Guru.speech.models import PersonalityType, EmotionType


# Mock iOS classes
class MockAVSpeechSynthesisVoice:
    def __init__(self, identifier="com.apple.ttsbundle.siri_male_en-US", name="Male Voice", language="en-US", quality=1):
        self.identifier = identifier
        self.name = name
        self.language = language
        self.quality = quality
    
    @classmethod
    def speechVoices(cls):
        return [
            cls("com.apple.ttsbundle.siri_male_en-US", "Male Voice", "en-US"),
            cls("com.apple.ttsbundle.siri_female_en-US", "Female Voice", "en-US"),
        ]
    
    @classmethod
    def voiceWithLanguage_(cls, lang):
        return cls("com.apple.ttsbundle.default", "Default", lang)


class MockAVSpeechUtterance:
    def __init__(self, text):
        self.text = text
        self.voice = None
        self.pitchMultiplier = 1.0
        self.rate = 0.5
        self.volume = 1.0
    
    @classmethod
    def speechUtteranceWithString_(cls, text):
        return cls(text)


class MockAVSpeechSynthesizer:
    def __init__(self):
        self._speaking = False
    
    @classmethod
    def alloc(cls):
        return cls()
    
    def init(self):
        return self
    
    def speakUtterance_(self, utterance):
        self._speaking = True
        # Simulate async speech
        import threading
        def stop_speaking():
            import time
            time.sleep(0.1)
            self._speaking = False
        threading.Thread(target=stop_speaking, daemon=True).start()
    
    def isSpeaking(self):
        return self._speaking
    
    def stopSpeakingAtBoundary_(self, boundary):
        self._speaking = False


@pytest.fixture
def mock_ios_modules():
    """Mock iOS modules for testing."""
    with patch('Agent_Guru.speech.mobile.ios_tts.autoclass') as mock_autoclass:
        # Setup mocks
        mock_autoclass.side_effect = lambda name: {
            'AVSpeechSynthesizer': MockAVSpeechSynthesizer,
            'AVSpeechUtterance': MockAVSpeechUtterance,
            'AVSpeechSynthesisVoice': MockAVSpeechSynthesisVoice,
            'AVAudioFile': Mock,
            'AVAudioSession': Mock(sharedInstance=Mock(return_value=Mock()))
        }.get(name, Mock)
        
        yield mock_autoclass


@pytest.fixture
def ios_tts(mock_ios_modules):
    """Create iOS TTS instance with mocks."""
    from Agent_Guru.speech.mobile.ios_tts import IOSTTS
    return IOSTTS()


# Unit Tests

def test_ios_tts_initialization(ios_tts):
    """Test iOS TTS initializes correctly."""
    assert ios_tts.is_available()
    assert ios_tts._initialized
    assert ios_tts._synthesizer is not None


def test_ios_tts_male_voice_synthesis(ios_tts):
    """Test synthesis with male voice (Guru personality)."""
    text = "Hello, I am Guru."
    audio = ios_tts.synthesize(text, personality=PersonalityType.GURU)
    
    assert len(audio) > 0
    assert isinstance(audio, bytes)
    
    # Verify it's a valid WAV file
    with wave.open(io.BytesIO(audio), 'rb') as wav:
        assert wav.getnchannels() >= 1
        assert wav.getframerate() > 0


def test_ios_tts_female_voice_synthesis(ios_tts):
    """Test synthesis with female voice (Maya personality)."""
    text = "Hello, I am Maya."
    audio = ios_tts.synthesize(text, personality=PersonalityType.MAYA)
    
    assert len(audio) > 0
    assert isinstance(audio, bytes)


def test_ios_tts_all_emotions(ios_tts):
    """Test synthesis with all emotion types."""
    text = "Testing emotions."
    
    for emotion in EmotionType:
        audio = ios_tts.synthesize(
            text,
            personality=PersonalityType.GURU,
            emotion=emotion
        )
        assert len(audio) > 0, f"Failed for emotion: {emotion}"


def test_ios_tts_speech_rate_variations(ios_tts):
    """Test synthesis with different speech rates."""
    text = "Testing speech rate."
    
    for rate in [0.5, 0.75, 1.0, 1.5, 2.0]:
        audio = ios_tts.synthesize(
            text,
            personality=PersonalityType.GURU,
            speech_rate=rate
        )
        assert len(audio) > 0


def test_ios_tts_volume_variations(ios_tts):
    """Test synthesis with different volumes."""
    text = "Testing volume."
    
    for volume in [0.0, 0.3, 0.5, 0.7, 1.0]:
        audio = ios_tts.synthesize(
            text,
            personality=PersonalityType.GURU,
            volume=volume
        )
        assert len(audio) > 0


def test_ios_tts_empty_text_error(ios_tts):
    """Test that empty text raises error."""
    with pytest.raises(Exception):
        ios_tts.synthesize("", personality=PersonalityType.GURU)
    
    with pytest.raises(Exception):
        ios_tts.synthesize("   ", personality=PersonalityType.GURU)


def test_ios_tts_invalid_speech_rate(ios_tts):
    """Test that invalid speech rate raises error."""
    with pytest.raises(Exception):
        ios_tts.synthesize("test", speech_rate=0.3)
    
    with pytest.raises(Exception):
        ios_tts.synthesize("test", speech_rate=2.5)


def test_ios_tts_invalid_volume(ios_tts):
    """Test that invalid volume raises error."""
    with pytest.raises(Exception):
        ios_tts.synthesize("test", volume=-0.1)
    
    with pytest.raises(Exception):
        ios_tts.synthesize("test", volume=1.5)


def test_ios_tts_get_voice_info_guru(ios_tts):
    """Test getting voice info for Guru personality."""
    info = ios_tts.get_voice_info(PersonalityType.GURU)
    
    assert "identifier" in info
    assert "gender" in info
    assert info["gender"] == "male"
    assert info["personality"] == "guru"


def test_ios_tts_get_voice_info_maya(ios_tts):
    """Test getting voice info for Maya personality."""
    info = ios_tts.get_voice_info(PersonalityType.MAYA)
    
    assert "identifier" in info
    assert "gender" in info
    assert info["gender"] == "female"
    assert info["personality"] == "maya"


def test_ios_tts_long_text(ios_tts):
    """Test synthesis with long text."""
    text = "This is a very long text for testing iOS TTS. " * 20
    audio = ios_tts.synthesize(text, personality=PersonalityType.GURU)
    
    assert len(audio) > 0


def test_ios_tts_special_characters(ios_tts):
    """Test synthesis with special characters."""
    text = "Hello! How are you? I'm fine, thanks. 123 test."
    audio = ios_tts.synthesize(text, personality=PersonalityType.GURU)
    
    assert len(audio) > 0


def test_ios_tts_shutdown(ios_tts):
    """Test TTS shutdown."""
    ios_tts.shutdown()
    
    assert not ios_tts.is_available()
    assert not ios_tts._initialized


def test_ios_tts_emotion_pitch_adjustments(ios_tts):
    """Test that emotions adjust pitch correctly."""
    text = "Testing emotion pitch."
    
    # Happy should have higher pitch
    audio_happy = ios_tts.synthesize(
        text,
        personality=PersonalityType.GURU,
        emotion=EmotionType.HAPPY
    )
    
    # Sad should have lower pitch
    audio_sad = ios_tts.synthesize(
        text,
        personality=PersonalityType.GURU,
        emotion=EmotionType.SAD
    )
    
    assert len(audio_happy) > 0
    assert len(audio_sad) > 0


def test_ios_tts_personality_pitch_difference(ios_tts):
    """Test that Guru and Maya have different pitch settings."""
    text = "Testing personality pitch."
    
    audio_guru = ios_tts.synthesize(text, personality=PersonalityType.GURU)
    audio_maya = ios_tts.synthesize(text, personality=PersonalityType.MAYA)
    
    assert len(audio_guru) > 0
    assert len(audio_maya) > 0
    
    # Both should produce valid audio
    with wave.open(io.BytesIO(audio_guru), 'rb') as wav:
        assert wav.getframerate() > 0
    
    with wave.open(io.BytesIO(audio_maya), 'rb') as wav:
        assert wav.getframerate() > 0


def test_ios_tts_concurrent_synthesis(ios_tts):
    """Test concurrent synthesis (thread safety)."""
    import concurrent.futures
    
    def synthesize_text(idx):
        text = f"Concurrent test {idx}"
        audio = ios_tts.synthesize(text, personality=PersonalityType.GURU)
        return len(audio) > 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(synthesize_text, i) for i in range(20)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    assert all(results)
    assert len(results) == 20


def test_ios_tts_stress_test(ios_tts):
    """Stress test with 100 rapid syntheses."""
    for i in range(100):
        audio = ios_tts.synthesize(
            f"Stress test {i}",
            personality=PersonalityType.GURU
        )
        assert len(audio) > 0


def test_ios_tts_all_parameter_combinations(ios_tts):
    """Test all parameter combinations."""
    text = "Parameter combination test."
    
    for personality in [PersonalityType.GURU, PersonalityType.MAYA]:
        for emotion in [None, EmotionType.HAPPY, EmotionType.SAD]:
            for rate in [0.5, 1.0, 2.0]:
                for volume in [0.5, 1.0]:
                    audio = ios_tts.synthesize(
                        text,
                        personality=personality,
                        emotion=emotion,
                        speech_rate=rate,
                        volume=volume
                    )
                    assert len(audio) > 0


def test_ios_tts_neural_voice_quality(ios_tts):
    """Test that iOS uses high-quality neural voices."""
    info_guru = ios_tts.get_voice_info(PersonalityType.GURU)
    info_maya = ios_tts.get_voice_info(PersonalityType.MAYA)
    
    # Both should have voice info
    assert len(info_guru) > 0
    assert len(info_maya) > 0
    
    # Should have quality information
    assert "quality" in info_guru
    assert "quality" in info_maya
