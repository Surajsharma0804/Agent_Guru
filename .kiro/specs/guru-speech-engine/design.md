# Design Document: Speech Engine

## Overview

The Speech Engine is a critical component that enables Agent_Guru to interact through voice, providing natural speech recognition, text-to-speech synthesis, voice biometrics, emotion detection, and multi-language support. This component transforms Agent_Guru from a text-based system into a truly conversational AI that can understand and respond with human-like voice interaction.

The Speech Engine provides comprehensive voice interaction capabilities for Agent_Guru, including dual personality wake word detection (Guru - male, Maya - female), speech-to-text transcription, voice biometrics, emotion detection from voice, gender-specific text-to-speech synthesis, voice cloning, advanced noise cancellation, streaming audio processing, voice commands for complete system control, and conversation context management. This system enables natural voice-based interaction with the AI operating system while maintaining high accuracy, low latency (<500ms for real-time interaction), and robust security through voice biometrics.

**System Capabilities**:
- **Dual Wake Word Detection**: Detect "Hey Guru" (male) or "Hey Maya" (female) to activate respective personalities
- **Speech-to-Text**: Convert speech to text using OpenAI Whisper (desktop) or platform-native APIs (mobile)
- **Voice Biometric Authentication**: Speaker verification and identification for security
- **Emotion Detection**: Analyze voice for emotional state (happy, sad, angry, neutral, surprised, fearful, disgusted)
- **Gender-Specific Text-to-Speech**: Male voice for Guru, female voice for Maya with emotion support
- **Voice Cloning**: Learn and replicate user voice characteristics for personalized responses
- **Advanced Noise Cancellation**: Filter background noise for clear recognition (>20dB reduction)
- **Streaming Audio**: Real-time audio processing with <500ms end-to-end latency
- **Voice Commands**: Complete laptop/system control through voice
- **Conversation Context**: Maintain state across multiple conversation turns
- **Multi-Language Support**: Support for 8+ languages with automatic detection
- **Model Router Integration**: Intelligent selection between local and cloud models

**Dual Personality System**:
- **Guru (Male)**: Professional, confident voice with analytical tone
- **Maya (Female)**: Warm, empathetic voice with friendly tone
- Each personality maintains separate conversation context
- Emotion-aware responses that adapt to user's emotional state
- Seamless switching between personalities during runtime

**Complete System Control**:
The speech engine enables voice control for ANY system operation:
- Open/close applications, type text, send messages
- Control system settings, manage files, execute shortcuts
- Mouse/keyboard control, window management, media control
- Integration with Platform_Integration for cross-platform system access

**Architecture Priorities**:
- **Low Latency**: <500ms end-to-end for real-time interaction
- **High Accuracy**: >95% word accuracy on clean audio, >85% on noisy audio
- **Offline-First**: Core functionality works without cloud connectivity using local models (Whisper, Coqui TTS)
- **Cloud-Enhanced**: Optional cloud models (Google, Azure, AWS) for better accuracy when online
- **Battery Optimized**: <5% battery/hour in sleep mode, <10% in wake mode
- **Security**: Voice biometric integration with Security_System
- **Cross-Platform**: Unified API across desktop (Windows/macOS/Linux) and mobile (Android/iOS)

## Architecture

### System Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          Speech Engine Core                                   │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                    Audio Input Manager                                 │  │
│  │  (Device enumeration, buffering, format handling, streaming)           │  │
│  └──────────────────────────┬─────────────────────────────────────────────┘  │
│                             │                                                 │
│                             ▼                                                 │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                    Audio Processor                                     │  │
│  │  (VAD, Advanced Noise Cancellation, Echo Cancellation, AGC)            │  │
│  └──┬──────────────────────────────────────────────────────────────────────┘  │
│     │                                                                         │
│     ├──────────┬──────────┬──────────┬──────────┬──────────┬──────────┐     │
│     ▼          ▼          ▼          ▼          ▼          ▼          ▼     │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐    │
│  │Wake  │  │ STT  │  │Voice │  │Emotion│  │Voice │  │Command│  │Context│   │
│  │Word  │  │Engine│  │Feature│  │Detect│  │Cloner│  │Parser │  │Manager│   │
│  │Detect│  │      │  │Extract│  │      │  │      │  │       │  │       │   │
│  └──┬───┘  └──┬───┘  └──┬───┘  └──┬───┘  └──┬───┘  └───┬───┘  └───┬───┘   │
│     │         │         │         │         │          │          │        │
│     │         │         │         │         │          │          │        │
│     │         │         └─────────┼─────────┼──────────┼──────────┼────────┼──> To Security System
│     │         │                   │         │          │          │        │    (biometric auth)
│     │         │                   │         │          │          │        │
│     │         └───────────────────┼─────────┼──────────┴──────────┴────────┼──> To Agent Orchestration
│     │                             │         │                              │    (command routing)
│     │                             │         │                              │
│     │                             └─────────┼──────────────────────────────┼──> To Memory System
│     │                                       │                              │    (emotion/preference learning)
│     │                                       │                              │
│     └───────────────────────────────────────┼──────────────────────────────┘
│                                             ▼                                 │
│                                   ┌──────────────────┐                        │
│                                   │   TTS Engine     │                        │
│                                   │  (Synthesis +    │                        │
│                                   │   Emotion +      │                        │
│                                   │   Voice Clone)   │                        │
│                                   └────────┬─────────┘                        │
│                                            │                                  │
└────────────────────────────────────────────┼──────────────────────────────────┘
                                             ▼
                                   ┌──────────────────┐
                                   │  Audio Output    │
                                   │  (Streaming)     │
                                   └──────────────────┘
                                             │
                                             ▼
                                   ┌──────────────────┐
                                   │  Model Router    │
                                   │  (Local/Cloud    │
                                   │   Selection)     │
                                   └──────────────────┘
```

### Component Interaction Flow

1. **Audio Input Flow**: Audio Input Manager → Audio Processor → Wake Word Detector
2. **Transcription Flow**: Audio Processor → STT Engine → Command Parser → Context Manager
3. **Voice Feature Extraction Flow**: Audio Processor → Voice Feature Extractor → Security System
4. **Emotion Detection Flow**: Audio Processor → Emotion Detector → Memory System → TTS Engine
5. **Voice Cloning Flow**: Audio Processor → Voice Cloner → TTS Engine
6. **Synthesis Flow**: TTS Engine → Audio Output (with emotion and cloned voice)
7. **Command Flow**: Command Parser → Context Manager → Agent Orchestration
8. **Model Selection Flow**: Model Router → STT Engine / TTS Engine (local vs cloud)

### Design Principles

- **Modularity**: Each component is independently testable and replaceable
- **Async-First**: All I/O operations are asynchronous to prevent blocking
- **Type Safety**: Comprehensive type hints with mypy strict mode compliance
- **Performance**: Meet or exceed all latency targets (<500ms end-to-end)
- **Offline-First**: Core functionality works without cloud connectivity using local models
- **Cloud-Enhanced**: Optional cloud models for better accuracy when online
- **Security Integration**: Voice features integrate with Security_System for authentication
- **Battery Optimized**: Sleep/wake cycles minimize battery impact on mobile
- **Cross-Platform**: Unified API with platform-specific optimizations

## Integration Points

This system provides voice processing capabilities for Agent_Guru, with specific integrations for biometric authentication, emotion-aware responses, voice-driven task creation, and complete system control.

### Dependencies

**Upstream Dependencies** (systems this component depends on):
- **Model Router** (model-router): Selects optimal STT/TTS models (local vs cloud)
- **Platform Integration** (platform-integration): Provides audio device access and system control APIs
- **Security System** (guru-security-cryptography): Stores voice biometric templates securely

**Downstream Dependencies** (systems that depend on this component):
- **Security System** (guru-security-cryptography): Uses VoiceFeatureExtractor for biometric authentication
- **LLM Runtime** (guru-llm-runtime): Uses transcription for voice commands and conversation
- **Agent Orchestration** (agent-orchestration): Uses command interpretation for action routing
- **Memory System** (guru-memory-system): Uses emotion detection and conversation context for learning
- **Goal Manager** (goal-manager): Uses voice commands for task creation and management
- **Self-Improvement Engine** (self-improvement-engine): Uses recognition accuracy metrics for improvement

### API Contracts

**Security System Integration:**
```python
class VoiceFeatureExtractor:
    """Extracts voice biometric features for security system."""
    
    async def extract_features(self, audio_data: bytes, sample_rate: int) -> VoiceFeatures:
        """
        Extract voice biometric features from audio.
        
        Returns feature vector for authentication by security system.
        Does NOT perform authentication - only feature extraction.
        """
        pass
```

**LLM Runtime Integration:**
```python
# LLM runtime uses transcription for voice commands
transcription = await speech_engine.transcribe(audio_data, sample_rate)
response = await llm_runtime.process(transcription.text, context=conversation_context)
await speech_engine.synthesize(response, emotion=detected_emotion)
```

**Agent Orchestration Integration:**
```python
# Agent orchestration uses command interpretation
command = await speech_engine.interpret_command(transcription.text)
if command.is_command:
    await agent_orchestration.route_action(command.action_id, command.parameters)
```

**Memory System Integration:**
```python
# Memory system uses emotion and conversation context
emotion = await speech_engine.detect_emotion(audio_data)
await memory_system.store_emotion_state(user_id, emotion, timestamp)
await memory_system.store_conversation_turn(user_id, transcription, response, context)
```

**Goal Manager Integration:**
```python
# Goal manager uses voice commands for task creation
command = await speech_engine.interpret_command(transcription.text)
if command.action_id == "CREATE_TASK":
    await goal_manager.create_task(command.parameters["task_description"])
```

**Model Router Integration:**
```python
# Model router selects optimal STT/TTS models
stt_model = await model_router.select_stt_model(
    context={"online": True, "battery_level": 0.8, "accuracy_priority": "high"}
)
tts_model = await model_router.select_tts_model(
    context={"online": True, "voice_gender": "male", "emotion": "happy"}
)
```

### Data Flow

1. **Voice Authentication Flow:**
   - User provides voice sample
   - Audio Processor cleans audio
   - VoiceFeatureExtractor extracts biometric features
   - Features passed to Security_System BiometricAuthenticator
   - Security system performs authentication

2. **Voice Command Flow:**
   - User speaks command
   - Wake Word Detector activates
   - STT Engine transcribes speech
   - Emotion Detector analyzes voice
   - Command Parser interprets command
   - Context Manager updates conversation state
   - Command sent to Agent Orchestration
   - Response generated by LLM Runtime
   - TTS Engine synthesizes response with emotion
   - Audio Output streams response

3. **Voice Task Creation Flow:**
   - User says "Create a task to..."
   - Command Parser extracts task description
   - Goal Manager creates task
   - TTS Engine confirms task creation

4. **Emotion-Aware Response Flow:**
   - Emotion Detector identifies user emotion (e.g., "frustrated")
   - Memory System stores emotion state
   - LLM Runtime adjusts response tone
   - TTS Engine synthesizes with empathetic emotion

5. **Voice Cloning Flow:**
   - User enrolls with 5+ minutes of speech
   - Voice Cloner trains personalized voice model
   - Model stored securely in Security System
   - TTS Engine uses cloned voice for responses

## Components and Interfaces

### 1. Audio Input Manager

**Responsibility**: Manage audio input from various sources with proper buffering and device handling.

**Interface**:
```python
from typing import AsyncIterator, List
from dataclasses import dataclass
import numpy as np

@dataclass
class AudioDevice:
    device_id: int
    name: str
    sample_rate: int
    channels: int
    is_default: bool

@dataclass
class AudioConfig:
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024
    buffer_size: int = 4096
    format: str = "int16"

class AudioInputManager:
    async def list_devices(self) -> List[AudioDevice]:
        """Enumerate available audio input devices."""
        ...
    
    async def open_device(self, device_id: int, config: AudioConfig) -> None:
        """Open an audio input device with specified configuration."""
        ...
    
    async def open_file(self, file_path: str, config: AudioConfig) -> None:
        """Open an audio file as input source."""
        ...
    
    async def stream_audio(self) -> AsyncIterator[np.ndarray]:
        """Stream audio chunks as numpy arrays."""
        ...
    
    async def close(self) -> None:
        """Close the audio input source."""
        ...
```

**Key Features**:
- Device enumeration and selection
- File and microphone input support
- Configurable buffering and chunk sizes
- Async streaming interface
- Format conversion (WAV, MP3, FLAC)

### 2. Audio Processor

**Responsibility**: Enhance audio quality through noise reduction, VAD, echo cancellation, and AGC.

**Interface**:
```python
from typing import Tuple
import numpy as np

@dataclass
class AudioProcessingConfig:
    enable_noise_reduction: bool = True
    enable_vad: bool = True
    enable_echo_cancellation: bool = True
    enable_agc: bool = True
    vad_aggressiveness: int = 2  # 0-3
    noise_reduction_strength: float = 0.5  # 0.0-1.0

class AudioProcessor:
    def __init__(self, config: AudioProcessingConfig):
        ...
    
    async def process_chunk(self, audio: np.ndarray) -> np.ndarray:
        """Process a single audio chunk with all enabled enhancements."""
        ...
    
    async def detect_voice_activity(self, audio: np.ndarray) -> bool:
        """Detect if voice is present in audio chunk."""
        ...
    
    async def reduce_noise(self, audio: np.ndarray) -> np.ndarray:
        """Apply noise reduction to audio."""
        ...
    
    async def cancel_echo(self, audio: np.ndarray, reference: np.ndarray) -> np.ndarray:
        """Cancel echo using reference signal."""
        ...
    
    async def apply_agc(self, audio: np.ndarray) -> np.ndarray:
        """Apply automatic gain control."""
        ...
    
    def convert_format(self, audio: np.ndarray, target_rate: int) -> np.ndarray:
        """Convert audio sample rate."""
        ...
```

**Key Features**:
- Noise reduction using spectral subtraction or deep learning
- Voice activity detection with configurable aggressiveness
- Echo cancellation for full-duplex scenarios
- Automatic gain control for level normalization
- Sample rate conversion

### 2.5. Voice Feature Extractor

**Responsibility**: Extract voice biometric features for authentication by security system.

**IMPORTANT**: This component does NOT perform authentication. It only extracts features that are passed to guru-security-cryptography for authentication.

**Interface**:
```python
import numpy as np
from typing import Optional
from dataclasses import dataclass

@dataclass
class VoiceFeatures:
    """Voice biometric features."""
    feature_vector: np.ndarray  # Feature representation
    sample_rate: int
    duration: float
    quality_score: float  # 0.0 to 1.0

class VoiceFeatureExtractor:
    """Extracts voice biometric features for security system."""
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize voice feature extractor.
        
        Args:
            model_path: Path to feature extraction model
        """
        pass
    
    async def extract_features(self, audio: np.ndarray, sample_rate: int) -> VoiceFeatures:
        """
        Extract voice biometric features from audio.
        
        Features are passed to guru-security-cryptography for authentication.
        This method does NOT perform authentication.
        
        Args:
            audio: Audio data as numpy array
            sample_rate: Sample rate in Hz
            
        Returns:
            VoiceFeatures with feature vector and metadata
        """
        pass
    
    def compute_quality_score(self, audio: np.ndarray) -> float:
        """
        Compute quality score for voice sample.
        
        Considers SNR, duration, and voice activity.
        
        Returns:
            Quality score between 0.0 and 1.0
        """
        pass
```

**Key Features**:
- Voice feature extraction for biometric authentication
- Quality scoring for sample selection
- Integration with guru-security-cryptography
- No authentication logic (delegated to security system)

### 3. Wake Word Detector

**Responsibility**: Detect custom wake words with low latency and high accuracy.

**Interface**:
```python
from typing import Optional
from dataclasses import dataclass

@dataclass
class WakeWordConfig:
    wake_words: List[str]
    sensitivity: float = 0.5  # 0.0-1.0
    model_path: Optional[str] = None

@dataclass
class WakeWordDetection:
    wake_word: str
    confidence: float
    timestamp: float
    audio_chunk: np.ndarray

class WakeWordDetector:
    def __init__(self, config: WakeWordConfig):
        ...
    
    async def detect(self, audio: np.ndarray) -> Optional[WakeWordDetection]:
        """Detect wake word in audio chunk."""
        ...
    
    async def add_wake_word(self, wake_word: str) -> None:
        """Register a new wake word."""
        ...
    
    async def remove_wake_word(self, wake_word: str) -> None:
        """Unregister a wake word."""
        ...
    
    def get_wake_words(self) -> List[str]:
        """Get list of registered wake words."""
        ...
```

**Key Features**:
- Multiple wake word support
- Configurable sensitivity threshold
- Sub-200ms detec_size: Whisper model size ("tiny", "base", "small", "medium", "large")
            model_path: Path to custom model (overrides model_size)
            compute_type: Compute type for inference
            beam_size: Beam size for decoding
            device: Device to run on ("cpu", "cuda")
        """
        pass
    
    def transcribe(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
        language: Optional[str] = None
    ) -> TranscriptionResult:
        """
        Transcribe audio to text.
        
        Args:
            audio_data: Audio as numpy array
            sample_rate: Sample rate in Hz
            language: Force language (None for auto-detect)
            
        Returns:
            TranscriptionResult with text, language, confidence
        """
        pass
    
    def transcribe_file(
        self,
        file_path: str,
        language: Optional[str] = None
    ) -> TranscriptionResult:
        """
        Transcribe audio file.
        
        Args:
            file_path: Path to audio file
            language: Force language (None for auto-detect)
            
        Returns:
            TranscriptionResult with text, language, confidence
        """
        pass
```

### 4. CommandInterpreter (commands.py)

Maps transcribed text to agent actions.

```python
class CommandInterpreter:
    """
    Interprets transcribed text as commands for the Guru Agent.
    Uses pattern matching and fuzzy matching for command detection.
    """
    
    def __init__(self):
        """Initialize command interpreter with default command registry."""
        pass
    
    def register_command(
        self,
        patterns: List[str],
        action_id: str,
        description: str = ""
    ) -> None:
        """
        Register a new command pattern.
        
        Args:
            patterns: List of text patterns that trigger this command
            action_id: Action identifier for Guru Agent
            description: Human-readable description
        """
        pass
    
    def interpret(
        self,
        text: str,
        language: str = "en"
    ) -> CommandResult:
        """
        Interpret text as a command.
        
        Args:
            text: Transcribed text
            language: Language code for language-specific matching
            
        Returns:
            CommandResult with action_id and parameters
        """
        pass
    
    def get_registered_commands(self) -> List[Dict[str, Any]]:
        """
        Get list of all registered commands.
        
        Returns:
            List of command definitions
        """
        pass
```

### 5. Audio Capture Components

```python
class AudioCapture:
    """Base class for audio capture."""
    
    def capture(self, duration: Optional[float] = None) -> Tuple[np.ndarray, int]:
        """
        Capture audio.
        
        Args:
            duration: Duration in seconds (None for continuous)
            
        Returns:
            Tuple of (audio_data, sample_rate)
        """
        pass

class MicrophoneCapture(AudioCapture):
    """Captures audio from system microphone using sounddevice."""
    
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1
    ):
        """
        Initialize microphone capture.
        
        Args:
            sample_rate: Sample rate in Hz
            channels: Number of audio channels
        """
        pass

class FileCapture(AudioCapture):
    """Loads audio from files using soundfile."""
    
    def load_file(self, file_path: str) -> Tuple[np.ndarray, int]:
        """
        Load audio from file.
        
        Args:
            file_path: Path to audio file
            
        Returns:
            Tuple of (audio_data, sample_rate)
        """
        pass
```

### 8. Emotion Detector

**Responsibility**: Analyze voice for emotional state to enable empathetic responses.

**Interface**:
```python
from typing import Dict, List
from dataclasses import dataclass
from enum import Enum

class EmotionType(Enum):
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    NEUTRAL = "neutral"
    SURPRISED = "surprised"
    FEARFUL = "fearful"
    DISGUSTED = "disgusted"

@dataclass
class EmotionResult:
    primary_emotion: EmotionType
    emotion_scores: Dict[EmotionType, float]  # Confidence for each emotion
    confidence: float  # Confidence in primary emotion
    timestamp: float
    audio_quality: float  # Quality of audio for emotion detection

@dataclass
class EmotionHistory:
    emotions: List[EmotionResult]
    dominant_emotion: EmotionType
    emotion_transitions: List[tuple[EmotionType, EmotionType, float]]  # (from, to, timestamp)

class EmotionDetector:
    """
    Detect emotional state from voice patterns.
    
    Uses acoustic features (pitch, energy, tempo, spectral features)
    to classify emotional state.
    """
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize emotion detector.
        
        Args:
            model_path: Path to emotion detection model
        """
        pass
    
    async def detect_emotion(
        self,
        audio: np.ndarray,
        sample_rate: int
    ) -> EmotionResult:
        """
        Detect emotion from audio.
        
        Args:
            audio: Audio data as numpy array
            sample_rate: Sample rate in Hz
            
        Returns:
            EmotionResult with primary emotion and confidence scores
        """
        pass
    
    async def detect_emotion_streaming(
        self,
        audio_stream: AsyncIterator[np.ndarray],
        sample_rate: int
    ) -> AsyncIterator[EmotionResult]:
        """
        Detect emotion from streaming audio.
        
        Yields emotion results as audio is processed.
        """
        pass
    
    async def track_emotion_history(
        self,
        emotions: List[EmotionResult],
        window_seconds: float = 60.0
    ) -> EmotionHistory:
        """
        Track emotion changes over time.
        
        Args:
            emotions: List of emotion results
            window_seconds: Time window for analysis
            
        Returns:
            EmotionHistory with transitions and dominant emotion
        """
        pass
    
    def extract_acoustic_features(
        self,
        audio: np.ndarray,
        sample_rate: int
    ) -> Dict[str, float]:
        """
        Extract acoustic features for emotion detection.
        
        Features include: pitch, energy, tempo, MFCC, spectral features
        """
        pass

### 9. Voice Cloner

**Responsibility**: Learn and replicate user voice characteristics for personalized responses.

**Interface**:
```python
from typing import Optional, List
from dataclasses import dataclass

@dataclass
class VoiceModel:
    model_id: str
    user_id: str
    voice_characteristics: Dict[str, float]  # Pitch, tone, speaking rate, etc.
    training_duration_seconds: float
    similarity_score: float  # Similarity to original voice (0.0-1.0)
    created_at: float
    updated_at: float

@dataclass
class VoiceCloneConfig:
    target_similarity: float = 0.85
    training_epochs: int = 100
    use_gpu: bool = True
    model_architecture: str = "tacotron2"  # or "fastspeech2", "vits"

class VoiceCloner:
    """
    Clone user voice for personalized TTS.
    
    Requires 5+ minutes of speech samples for training.
    Integrates with TTS Engine for synthesis.
    """
    
    def __init__(self, config: VoiceCloneConfig):
        """
        Initialize voice cloner.
        
        Args:
            config: Voice cloning configuration
        """
        pass
    
    async def enroll_voice(
        self,
        user_id: str,
        audio_samples: List[np.ndarray],
        sample_rate: int
    ) -> VoiceModel:
        """
        Enroll user voice for cloning.
        
        Args:
            user_id: User identifier
            audio_samples: List of audio samples (5+ minutes total)
            sample_rate: Sample rate in Hz
            
        Returns:
            VoiceModel with trained voice characteristics
        """
        pass
    
    async def update_voice_model(
        self,
        model_id: str,
        additional_samples: List[np.ndarray],
        sample_rate: int
    ) -> VoiceModel:
        """
        Update existing voice model with additional samples.
        
        Enables incremental learning for improved quality.
        """
        pass
    
    async def synthesize_with_cloned_voice(
        self,
        model_id: str,
        text: str,
        emotion: Optional[EmotionType] = None
    ) -> bytes:
        """
        Synthesize speech using cloned voice.
        
        Args:
            model_id: Voice model identifier
            text: Text to synthesize
            emotion: Optional emotion to apply
            
        Returns:
            Audio data as bytes
        """
        pass
    
    async def compute_similarity(
        self,
        original_audio: np.ndarray,
        synthesized_audio: np.ndarray,
        sample_rate: int
    ) -> float:
        """
        Compute similarity between original and synthesized voice.
        
        Returns similarity score (0.0-1.0)
        """
        pass
    
    async def delete_voice_model(self, model_id: str) -> None:
        """Delete voice model and associated data."""
        pass

### 10. Advanced Noise Cancellation

**Responsibility**: Filter background noise for clear recognition with >20dB reduction.

**Interface**:
```python
from typing import Optional
from dataclasses import dataclass
from enum import Enum

class NoiseType(Enum):
    WHITE_NOISE = "white_noise"
    PINK_NOISE = "pink_noise"
    BABBLE = "babble"
    MUSIC = "music"
    TRAFFIC = "traffic"
    WIND = "wind"
    UNKNOWN = "unknown"

class NoiseReductionLevel(Enum):
    LIGHT = "light"  # 10-15dB reduction
    MEDIUM = "medium"  # 15-20dB reduction
    AGGRESSIVE = "aggressive"  # 20-30dB reduction

@dataclass
class NoiseProfile:
    noise_type: NoiseType
    noise_level_db: float
    snr_db: float  # Signal-to-noise ratio
    reduction_applied_db: float

class AdvancedNoiseCancellation:
    """
    Advanced noise cancellation using machine learning.
    
    Targets >20dB noise reduction while preserving speech intelligibility.
    """
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        reduction_level: NoiseReductionLevel = NoiseReductionLevel.MEDIUM
    ):
        """
        Initialize noise cancellation.
        
        Args:
            model_path: Path to noise reduction model
            reduction_level: Noise reduction aggressiveness
        """
        pass
    
    async def reduce_noise(
        self,
        audio: np.ndarray,
        sample_rate: int
    ) -> tuple[np.ndarray, NoiseProfile]:
        """
        Reduce noise from audio.
        
        Args:
            audio: Audio data as numpy array
            sample_rate: Sample rate in Hz
            
        Returns:
            Tuple of (cleaned_audio, noise_profile)
        """
        pass
    
    async def reduce_noise_streaming(
        self,
        audio_stream: AsyncIterator[np.ndarray],
        sample_rate: int
    ) -> AsyncIterator[tuple[np.ndarray, NoiseProfile]]:
        """
        Reduce noise from streaming audio.
        
        Yields cleaned audio chunks with noise profiles.
        """
        pass
    
    async def detect_noise_type(
        self,
        audio: np.ndarray,
        sample_rate: int
    ) -> NoiseType:
        """
        Detect type of background noise.
        
        Enables adaptive noise reduction strategies.
        """
        pass
    
    async def compute_snr(
        self,
        audio: np.ndarray,
        sample_rate: int
    ) -> float:
        """
        Compute signal-to-noise ratio.
        
        Returns SNR in dB.
        """
        pass
    
    async def adapt_to_noise(
        self,
        audio: np.ndarray,
        sample_rate: int
    ) -> None:
        """
        Adapt noise reduction to current noise conditions.
        
        Updates internal noise profile for better reduction.
        """
        pass

### 11. Streaming Audio Manager

**Responsibility**: Manage real-time audio streaming with <500ms end-to-end latency.

**Interface**:
```python
from typing import AsyncIterator, Optional
from dataclasses import dataclass
from enum import Enum

class AudioCodec(Enum):
    PCM = "pcm"
    OPUS = "opus"
    AAC = "aac"

@dataclass
class StreamConfig:
    sample_rate: int = 16000
    channels: int = 1
    chunk_duration_ms: int = 100  # 100-500ms chunks
    codec: AudioCodec = AudioCodec.PCM
    buffer_size_ms: int = 500

@dataclass
class StreamMetrics:
    latency_ms: float
    jitter_ms: float
    packet_loss_percent: float
    buffer_underruns: int
    buffer_overruns: int

class StreamingAudioManager:
    """
    Manage real-time audio streaming.
    
    Targets <500ms end-to-end latency for natural conversation.
    """
    
    def __init__(self, config: StreamConfig):
        """
        Initialize streaming audio manager.
        
        Args:
            config: Streaming configuration
        """
        pass
    
    async def stream_input(
        self,
        audio_source: AsyncIterator[bytes]
    ) -> AsyncIterator[np.ndarray]:
        """
        Stream audio input with buffering and format conversion.
        
        Yields audio chunks as numpy arrays.
        """
        pass
    
    async def stream_output(
        self,
        audio_data: AsyncIterator[np.ndarray],
        sample_rate: int
    ) -> AsyncIterator[bytes]:
        """
        Stream audio output with encoding.
        
        Yields encoded audio chunks.
        """
        pass
    
    async def get_metrics(self) -> StreamMetrics:
        """Get streaming performance metrics."""
        pass
    
    async def adapt_buffer_size(
        self,
        network_latency_ms: float
    ) -> None:
        """
        Adapt buffer size based on network conditions.
        
        Balances latency vs reliability.
        """
        pass

### 12. Conversation Context Manager

**Responsibility**: Maintain conversation state across multiple turns.

**Interface**:
```python
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class ConversationTurn:
    turn_id: str
    user_input: str
    agent_response: str
    emotion: Optional[EmotionType]
    timestamp: float
    metadata: Dict[str, Any]

@dataclass
class ConversationContext:
    conversation_id: str
    personality: str  # "guru" or "maya"
    turns: List[ConversationTurn]
    current_topic: Optional[str]
    user_preferences: Dict[str, Any]
    emotion_history: List[EmotionResult]

class ConversationContextManager:
    """
    Manage conversation context across multiple turns.
    
    Tracks history, resolves references, detects topic shifts.
    """
    
    def __init__(self, max_history_turns: int = 10):
        """
        Initialize conversation context manager.
        
        Args:
            max_history_turns: Maximum turns to keep in memory
        """
        pass
    
    async def create_context(
        self,
        user_id: str,
        personality: str
    ) -> ConversationContext:
        """Create new conversation context."""
        pass
    
    async def add_turn(
        self,
        context_id: str,
        user_input: str,
        agent_response: str,
        emotion: Optional[EmotionType] = None
    ) -> ConversationContext:
        """Add conversation turn to context."""
        pass
    
    async def resolve_reference(
        self,
        context_id: str,
        reference: str
    ) -> Optional[str]:
        """
        Resolve pronoun or reference to previous context.
        
        Examples: "it", "that", "the one I mentioned"
        """
        pass
    
    async def detect_topic_shift(
        self,
        context_id: str,
        new_input: str
    ) -> bool:
        """
        Detect if conversation topic has changed.
        
        Returns True if topic shift detected.
        """
        pass
    
    async def get_context_summary(
        self,
        context_id: str
    ) -> str:
        """Generate summary of conversation context."""
        pass
    
    async def clear_context(self, context_id: str) -> None:
        """Clear conversation context."""
        pass
    
    async def extract_preferences(
        self,
        context_id: str
    ) -> Dict[str, Any]:
        """
        Extract user preferences from conversation.
        
        Examples: "I prefer email over calls", "I like morning meetings"
        """
        pass

### 13. Mobile Speech Recognition (UPDATED)

**Responsibility**: Provide platform-specific speech recognition for Android and iOS.

**Android Implementation**:
```python
class AndroidSpeechRecognizer:
    """Android-specific speech recognition using Android Speech Recognition API."""
    
    def __init__(self):
        from jnius import autoclass
        self.SpeechRecognizer = autoclass('android.speech.SpeechRecognizer')
        self.RecognizerIntent = autoclass('android.speech.RecognizerIntent')
        self.recognizer = None
    
    async def initialize(self) -> None:
        """Initialize Android speech recognizer."""
        self.recognizer = self.SpeechRecognizer.createSpeechRecognizer(
            self._get_android_context()
        )
    
    async def recognize(self, audio_data: bytes) -> TranscriptionResult:
        """
        Recognize speech using Android Speech Recognition API.
        
        Falls back to cloud STT if offline recognition unavailable.
        """
        intent = self.RecognizerIntent(self.RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
        intent.putExtra(
            self.RecognizerIntent.EXTRA_LANGUAGE_MODEL,
            self.RecognizerIntent.LANGUAGE_MODEL_FREE_FORM
        )
        # Start recognition and await result
        ...
```

**iOS Implementation**:
```python
class IOSSpeechRecognizer:
    """iOS-specific speech recognition using Apple Speech Framework."""
    
    def __init__(self):
        from pyobjus import autoclass
        self.SFSpeechRecognizer = autoclass('SFSpeechRecognizer')
        self.SFSpeechAudioBufferRecognitionRequest = autoclass(
            'SFSpeechAudioBufferRecognitionRequest'
        )
        self.recognizer = None
    
    async def initialize(self) -> None:
        """Initialize iOS speech recognizer."""
        self.recognizer = self.SFSpeechRecognizer.alloc().init()
        # Request authorization
        await self._request_authorization()
    
    async def recognize(self, audio_data: bytes) -> TranscriptionResult:
        """
        Recognize speech using Apple Speech Framework.
        
        Uses on-device recognition when available (iOS 13+).
        """
        request = self.SFSpeechAudioBufferRecognitionRequest.alloc().init()
        request.shouldReportPartialResults = True
        # Start recognition and await result
        ...
```

### 9. Mobile Text-to-Speech (NEW)

**Responsibility**: Provide platform-specific text-to-speech for Android and iOS.

**Android Implementation**:
```python
class AndroidTTS:
    """Android-specific TTS using Android TextToSpeech."""
    
    def __init__(self):
        from jnius import autoclass
        self.TextToSpeech = autoclass('android.speech.tts.TextToSpeech')
        self.tts = None
    
    async def initialize(self, voice_gender: str) -> None:
        """
        Initialize Android TTS.
        
        Args:
            voice_gender: "male" for Guru, "female" for Maya
        """
        self.tts = self.TextToSpeech(
            self._get_android_context(),
            self._on_init_listener
        )
        # Set voice based on gender
        await self._set_voice(voice_gender)
    
    async def synthesize(self, text: str) -> bytes:
        """Synthesize speech from text."""
        # Use TextToSpeech.synthesizeToFile for audio data
        ...
```

**iOS Implementation**:
```python
class IOSTTS:
    """iOS-specific TTS using AVSpeechSynthesizer."""
    
    def __init__(self):
        from pyobjus import autoclass
        self.AVSpeechSynthesizer = autoclass('AVSpeechSynthesizer')
        self.AVSpeechUtterance = autoclass('AVSpeechUtterance')
        self.synthesizer = None
    
    async def initialize(self, voice_gender: str) -> None:
        """
        Initialize iOS TTS.
        
        Args:
            voice_gender: "male" for Guru, "female" for Maya
        """
        self.synthesizer = self.AVSpeechSynthesizer.alloc().init()
        # Set voice based on gender
        await self._set_voice(voice_gender)
    
    async def synthesize(self, text: str) -> bytes:
        """Synthesize speech from text."""
        utterance = self.AVSpeechUtterance.speechUtteranceWithString_(text)
        # Configure voice and rate
        ...
```

### 10. Background Service Manager (NEW)

**Responsibility**: Manage always-on background service with sleep/wake cycles for battery optimization.

**Interface**:
```python
from enum import Enum
from dataclasses import dataclass

class ServiceState(Enum):
    STOPPED = "stopped"
    SLEEPING = "sleeping"
    WAKING = "waking"
    AWAKE = "awake"

@dataclass
class BatteryUsageStats:
    sleep_mode_percent_per_hour: float
    wake_mode_percent_per_hour: float
    total_uptime_hours: float
    wake_count: int
    average_wake_duration_seconds: float

class BackgroundServiceManager:
    """
    Manage always-on background service with battery optimization.
    
    Targets:
    - Sleep mode: <5% battery per hour
    - Wake mode: <10% battery per hour
    """
    
    def __init__(self, platform: str):
        """
        Initialize background service manager.
        
        Args:
            platform: "android", "ios", "windows", "macos", "linux"
        """
        self.platform = platform
        self.state = ServiceState.STOPPED
        self.wake_word_detector = None
        self.battery_monitor = None
    
    async def start_service(self) -> None:
        """
        Start background service.
        
        - Android: Start ForegroundService with notification
        - iOS: Start background audio mode
        - Desktop: Start system tray service
        """
        if self.platform == "android":
            await self._start_android_foreground_service()
        elif self.platform == "ios":
            await self._start_ios_background_audio()
        else:
            await self._start_desktop_service()
        
        await self.enter_sleep_mode()
    
    async def stop_service(self) -> None:
        """Stop background service and cleanup resources."""
        await self._cleanup_resources()
        self.state = ServiceState.STOPPED
    
    async def enter_sleep_mode(self) -> None:
        """
        Enter sleep mode for battery optimization.
        
        Sleep mode characteristics:
        - Minimal CPU usage (<1%)
        - Lightweight wake word detection only
        - No LLM inference
        - No network activity
        - Target: <5% battery per hour
        """
        self.state = ServiceState.SLEEPING
        
        # Use minimal wake word detection
        await self.wake_word_detector.set_sensitivity("low")
        await self.wake_word_detector.set_buffer_size(512)  # Smaller buffer
        
        # Disable non-essential features
        await self._disable_voice_biometrics()
        await self._disable_command_recognition()
        
        # Monitor battery usage
        await self.battery_monitor.start_tracking("sleep")
    
    async def enter_wake_mode(self) -> None:
        """
        Enter wake mode for full functionality.
        
        Wake mode characteristics:
        - Full voice processing
        - LLM inference
        - Command execution
        - Network activity
        - Target: <10% battery per hour
        """
        self.state = ServiceState.WAKING
        
        # Enable full wake word detection
        await self.wake_word_detector.set_sensitivity("high")
        await self.wake_word_detector.set_buffer_size(2048)
        
        # Enable all features
        await self._enable_voice_biometrics()
        await self._enable_command_recognition()
        
        # Monitor battery usage
        await self.battery_monitor.start_tracking("wake")
        
        self.state = ServiceState.AWAKE
    
    async def handle_wake_word_detected(self, wake_word: str) -> None:
        """
        Handle wake word detection event.
        
        Args:
            wake_word: "hey_guru" or "hey_maya"
        """
        if self.state == ServiceState.SLEEPING:
            await self.enter_wake_mode()
        
        # Process voice command
        await self._process_voice_command(wake_word)
        
        # Return to sleep after timeout (e.g., 30 seconds of inactivity)
        await self._schedule_sleep_timeout()
    
    async def handle_low_battery(self, battery_percent: float) -> None:
        """
        Handle low battery condition.
        
        Args:
            battery_percent: Current battery percentage
        """
        if battery_percent < 20:
            await self.enter_sleep_mode()
        if battery_percent < 10:
            await self.stop_service()
    
    async def handle_thermal_state(self, thermal_state: str) -> None:
        """
        Handle thermal state changes.
        
        Args:
            thermal_state: "normal", "fair", "serious", "critical"
        """
        if thermal_state == "critical":
            await self.enter_sleep_mode()
    
    async def get_battery_usage_stats(self) -> BatteryUsageStats:
        """Get battery usage statistics."""
        return await self.battery_monitor.get_stats()
    
    async def _start_android_foreground_service(self) -> None:
        """Start Android ForegroundService with persistent notification."""
        from jnius import autoclass
        Intent = autoclass('android.content.Intent')
        PendingIntent = autoclass('android.app.PendingIntent')
        NotificationCompat = autoclass('androidx.core.app.NotificationCompat')
        
        # Create notification
        notification = NotificationCompat.Builder(self._get_context(), "guru_service")
        notification.setContentTitle("AGENT_GURU")
        notification.setContentText("Listening for 'Hey Guru' or 'Hey Maya'")
        notification.setSmallIcon(R.drawable.ic_notification)
        notification.setPriority(NotificationCompat.PRIORITY_LOW)
        
        # Start foreground service
        self.service.startForeground(1, notification.build())
    
    async def _start_ios_background_audio(self) -> None:
        """Start iOS background audio mode."""
        from pyobjus import autoclass
        AVAudioSession = autoclass('AVAudioSession')
        
        session = AVAudioSession.sharedInstance()
        session.setCategory_error_("AVAudioSessionCategoryPlayback", None)
        session.setActive_error_(True, None)
```

## Data Models

### TranscriptionResult

```python
@dataclass
class TranscriptionResult:
    """Result from speech transcription."""
    
    text: str
    """Transcribed text"""
    
    language: str
    """Detected or specified language code (e.g., 'en', 'hi', 'pa')"""
    
    confidence: float
    """Confidence score (0.0 to 1.0)"""
    
    segments: List[TranscriptionSegment]
    """Individual segments with timestamps"""
    
    duration: float
    """Audio duration in seconds"""

@dataclass
class TranscriptionSegment:
    """Individual segment of transcription with timing."""
    
    text: str
    start: float  # seconds
    end: float    # seconds
    confidence: float
```

### CommandResult

```python
@dataclass
class CommandResult:
    """Result from command interpretation."""
    
    action_id: Optional[str]
    """Action identifier (None if no command detected)"""
    
    parameters: Dict[str, Any]
    """Extracted parameters for the action"""
    
    raw_text: str
    """Original transcribed text"""
    
    confidence: float
    """Confidence in command detection (0.0 to 1.0)"""
    
    language: str
    """Language of the command"""
    
    is_command: bool
    """Whether a command was detected"""

@dataclass
class CommandPattern:
    """Definition of a command pattern."""
    
    patterns: List[str]
    """Text patterns that trigger this command"""
    
    action_id: str
    """Action identifier"""
    
    description: str
    """Human-readable description"""
    
    languages: List[str]
    """Supported languages for this command"""
    
    parameter_extractors: Dict[str, Callable]
    """Functions to extract parameters from matched text"""
```

### Configuration Models

```python
@dataclass
class ModelConfig:
    """Configuration for Whisper model."""
    
    model_size: str = "small"
    model_path: Optional[str] = None
    compute_type: str = "int8"
    beam_size: int = 5
    device: str = "cpu"
    
@dataclass
class NoiseReductionConfig:
    """Configuration for noise reduction."""
    
    enabled: bool = True
    stationary: bool = True
    prop_decrease: float = 1.0

@dataclass
class AudioConfig:
    """Configuration for audio capture."""
    
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024
```

## Default Command Registry

The system will ship with a default set of commands:

```python
DEFAULT_COMMANDS = [
    CommandPattern(
        patterns=["open youtube", "youtube kholo", "youtube ਖੋਲ੍ਹੋ"],
        action_id="OPEN_YOUTUBE",
        description="Open YouTube",
        languages=["en", "hi", "pa"]
    ),
    CommandPattern(
        patterns=["search for *", "* dhundo", "* ਲੱਭੋ"],
        action_id="SEARCH",
        description="Search for something",
        languages=["en", "hi", "pa"],
        parameter_extractors={"query": lambda text: extract_after_keyword(text)}
    ),
    CommandPattern(
        patterns=["play music", "music chalao", "music ਚਲਾਓ"],
        action_id="PLAY_MUSIC",
        description="Play music",
        languages=["en", "hi", "pa"]
    ),
    # Additional commands can be registered at runtime
]
```


## Correctness Properties

A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.

### Property 1: Wake Word Detection Latency and Accuracy

*For any* wake word ("Hey Guru", "Guru", "Hey Maya", "Maya") embedded in audio, the Wake_Word_Detector should detect it within 200 milliseconds and return the correct personality identifier (guru/maya) with a confidence score in [0.0, 1.0].

**Validates: Requirements 1.1, 1.2, 1.6**

### Property 2: Wake Word False Positive Rate

*For any* background audio without wake words, the Wake_Word_Detector should maintain a false positive rate below 1 detection per hour of continuous audio.

**Validates: Requirements 1.3**

### Property 3: Dual Wake Word Support

*For any* sequence of audio containing both "Hey Guru" and "Hey Maya" wake words, the Wake_Word_Detector should detect both and return the correct personality for each.

**Validates: Requirements 1.4**

### Property 4: STT Transcription Completeness

*For any* valid audio input, the STT_Engine should return a TranscriptionResult containing non-empty text (or empty for silence), a valid language code, a confidence score in [0.0, 1.0], segments with timestamps, and a non-negative duration.

**Validates: Requirements 2.1, 2.14**

### Property 5: STT Real-Time Performance

*For any* audio input, the STT_Engine should achieve a real-time factor below 0.5 (processing time < 0.5 × audio duration) on desktop and latency below 1 second for short commands on mobile.

**Validates: Requirements 2.2, 2.11**

### Property 6: STT Output Format

*For any* transcribed text, the output should include proper punctuation and capitalization where appropriate based on the language model.

**Validates: Requirements 2.3**

### Property 7: Speaker Diarization Completeness

*For any* multi-speaker audio, the STT_Engine should label each segment with a speaker identifier, and segments from the same speaker should have consistent labels.

**Validates: Requirements 2.5**

### Property 8: Voice Biometric Confidence Bounds

*For any* voice comparison, the Voice_Biometrics should return a confidence score in [0.0, 1.0] and complete verification within 500 milliseconds.

**Validates: Requirements 3.2, 3.3**

### Property 9: TTS Personality-Voice Mapping

*For any* text synthesized with Guru personality, the output should have male voice characteristics, and for Maya personality, female voice characteristics, with consistent characteristics across sessions.

**Validates: Requirements 4.1, 4.2, 4.8**

### Property 10: TTS Real-Time Performance

*For any* text input, the TTS_Engine should achieve a real-time factor below 0.3 (synthesis time < 0.3 × audio duration) on desktop and latency below 1 second for short responses (<50 words) on mobile.

**Validates: Requirements 4.3, 4.19**

### Property 11: TTS Output Format

*For any* synthesized audio, the output should have a sample rate of at least 16kHz and support speech rate adjustment in the range [0.5x, 2.0x].

**Validates: Requirements 4.7, 4.24**

### Property 12: Audio Processing Noise Reduction

*For any* audio containing background noise, the Audio_Processor should reduce noise while preserving speech intelligibility, completing processing within 100 milliseconds per chunk.

**Validates: Requirements 5.1, 5.2**

### Property 13: Voice Activity Detection Latency

*For any* audio chunk, the Audio_Processor should perform voice activity detection within 50 milliseconds.

**Validates: Requirements 5.3**

### Property 14: Command Parsing Completeness

*For any* transcribed text, the Command_Parser should extract the primary intent (if present), recognize entities (dates, numbers, names), and return a confidence score in [0.0, 1.0].

**Validates: Requirements 6.1, 6.2, 6.4**

### Property 15: Emotion Detection Completeness

*For any* audio input, the Emotion_Detector should identify an emotional state, return confidence scores for all emotion categories (each in [0.0, 1.0]), and complete analysis within 200 milliseconds.

**Validates: Requirements 13.1, 13.3, 13.4**

### Property 16: Emotion Detection Confidence Calibration

*For any* poor quality audio (low SNR), the Emotion_Detector should return low confidence scores rather than high-confidence guesses.

**Validates: Requirements 13.9**

### Property 17: Voice Cloning Quality

*For any* trained voice model, synthesizing text with the cloned voice should achieve a similarity score above 0.85 compared to the original voice, and similarity should increase with additional training samples (incremental learning).

**Validates: Requirements 14.2, 14.3, 14.5**

### Property 18: Advanced Noise Cancellation Effectiveness

*For any* audio with background noise, the Noise_Cancellation should reduce noise by at least 20dB while preserving speech intelligibility, completing processing within 50 milliseconds per chunk.

**Validates: Requirements 15.1, 15.2, 15.4**

### Property 19: Streaming Audio Latency

*For any* audio stream, the Audio_Stream should process audio in chunks of 100-500 milliseconds, maintain end-to-end latency below 500 milliseconds, and provide incremental STT results.

**Validates: Requirements 16.1, 16.2, 16.3**

### Property 20: Command Recognition Coverage

*For any* system control command (open app, close app, type text, etc.), the Command_Parser should recognize the command and extract parameters correctly.

**Validates: Requirements 17.1**

### Property 21: Command Chaining Support

*For any* valid chained command (e.g., "open browser and search for weather"), the Command_Parser should extract all individual commands in the correct order.

**Validates: Requirements 17.6**

### Property 22: Conversation Context Persistence

*For any* conversation with multiple turns, the Speech_Engine should maintain conversation state, resolve references to previous context (pronouns, "it", "that"), and detect topic shifts.

**Validates: Requirements 18.1, 18.3, 18.5**

### Property 23: Language Detection and Switching

*For any* audio in a supported language, the Speech_Engine should detect the language automatically and switch STT/TTS models accordingly, including support for code-switching (mixed languages).

**Validates: Requirements 19.2, 19.3, 19.4**

### Property 24: Model Router Fallback

*For any* network state (online/offline), the Speech_Engine should use cloud models when online with good connection, local models when offline, and fall back to local models within 1 second when cloud models fail.

**Validates: Requirements 20.2, 20.3, 20.5**

### Property 25: Component Integration Completeness

*For any* voice command that creates a task, the Speech_Engine should integrate with Goal_Manager to create the task and provide verbal confirmation of task creation.

**Validates: Requirements 21.1, 21.7**

### Property 26: Confidence Score Consistency

*For any* component output (STT, Voice Biometrics, Command Parser, Emotion Detector), confidence scores should always be in the range [0.0, 1.0] and should be calibrated such that higher confidence correlates with higher accuracy.

**Validates: Requirements 2.14, 3.3, 6.4, 13.3**

### Property 27: State Transition Latency

*For any* wake word detection event, the Speech_Engine should transition from sleep mode to wake mode within 500 milliseconds.

**Validates: Requirements 1.5.11**

## Error Handling

### Error Categories

1. **Audio Capture Errors**
   - Microphone unavailable or access denied
   - Invalid audio device configuration
   - Audio buffer overflow/underflow

2. **File Processing Errors**
   - File not found or inaccessible
   - Unsupported audio format
   - Corrupted audio data

3. **Model Errors**
   - Model files not found
   - Insufficient memory for model loading
   - Invalid model configuration
   - Inference failures

4. **Processing Errors**
   - Noise reduction failures
   - Transcription timeouts
   - Invalid audio format or sample rate

### Error Handling Strategy

```python
class GuruSpeechError(Exception):
    """Base exception for Guru Speech Engine."""
    
    def __init__(
        self,
        message: str,
        component: str,
        original_error: Optional[Exception] = None
    ):
        self.message = message
        self.component = component
        self.original_error = original_error
        super().__init__(self.format_message())
    
    def format_message(self) -> str:
        """Format error message with context."""
        msg = f"[{self.component}] {self.message}"
        if self.original_error:
            msg += f"\nCaused by: {type(self.original_error).__name__}: {str(self.original_error)}"
        return msg

class AudioCaptureError(GuruSpeechError):
    """Errors during audio capture."""
    pass

class ModelLoadError(GuruSpeechError):
    """Errors during model loading."""
    pass

class TranscriptionError(GuruSpeechError):
    """Errors during transcription."""
    pass

class CommandInterpretationError(GuruSpeechError):
    """Errors during command interpretation."""
    pass
```

### Error Recovery

- **Microphone failures**: Provide clear instructions for checking permissions and device availability
- **Model loading failures**: Include troubleshooting steps (check disk space, verify model files, try different compute type)
- **Transcription failures**: Log audio characteristics (duration, sample rate) for debugging
- **Command interpretation failures**: Fall back to returning raw transcription text

### Logging Strategy

```python
import logging

logger = logging.getLogger("guru_speech")

# Log levels:
# - DEBUG: Detailed processing information (audio characteristics, model parameters)
# - INFO: Normal operations (transcription started/completed, commands detected)
# - WARNING: Recoverable issues (low confidence transcription, no command match)
# - ERROR: Failures that prevent operation (model load failure, audio capture error)
```

## Testing Strategy

### Dual Testing Approach

The Speech Engine will use both unit tests and property-based tests for comprehensive coverage:

- **Unit tests**: Verify specific examples, edge cases, and error conditions
- **Property tests**: Verify universal properties across all inputs

Together, these approaches provide comprehensive coverage where unit tests catch concrete bugs and property tests verify general correctness. Unit tests should focus on specific examples and edge cases, while property-based tests handle covering lots of inputs through randomization.

### Property-Based Testing

We will use **Hypothesis** (Python's property-based testing library) for property tests.

**Configuration:**
- Each property test will run a minimum of 100 iterations (due to randomization)
- Each test will be tagged with a comment referencing the design property
- Tag format: `# Feature: guru-speech-engine, Property {number}: {property_text}`
- Each correctness property MUST be implemented by a SINGLE property-based test

**Property Test Examples:**

```python
from hypothesis import given, strategies as st
import numpy as np

@given(
    wake_word=st.sampled_from(["hey guru", "guru", "hey maya", "maya"]),
    audio=st.lists(st.floats(min_value=-1.0, max_value=1.0), min_size=16000, max_size=48000)
)
def test_wake_word_detection_latency_and_accuracy(wake_word, audio):
    """
    Feature: guru-speech-engine, Property 1: Wake Word Detection Latency and Accuracy
    For any wake word embedded in audio, detection should occur within 200ms with correct personality.
    """
    detector = WakeWordDetector()
    audio_with_wake_word = embed_wake_word(np.array(audio), wake_word)
    
    start_time = time.time()
    result = detector.detect(audio_with_wake_word)
    detection_time = (time.time() - start_time) * 1000  # Convert to ms
    
    assert result is not None
    assert detection_time < 200
    assert result.wake_word == wake_word
    expected_personality = "guru" if "guru" in wake_word else "maya"
    assert result.personality == expected_personality
    assert 0.0 <= result.confidence <= 1.0

@given(
    text=st.text(min_size=1, max_size=500),
    personality=st.sampled_from(["guru", "maya"])
)
def test_tts_personality_voice_mapping(text, personality):
    """
    Feature: guru-speech-engine, Property 9: TTS Personality-Voice Mapping
    For any text with personality, output should have correct gender voice characteristics.
    """
    tts_engine = TTSEngine()
    
    audio1 = tts_engine.synthesize(text, personality=personality)
    audio2 = tts_engine.synthesize(text, personality=personality)
    
    # Check voice gender
    voice_gender = analyze_voice_gender(audio1)
    expected_gender = "male" if personality == "guru" else "female"
    assert voice_gender == expected_gender
    
    # Check consistency across sessions
    similarity = compute_audio_similarity(audio1, audio2)
    assert similarity > 0.9  # High similarity for same text/personality

@given(
    audio=st.lists(st.floats(min_value=-1.0, max_value=1.0), min_size=16000, max_size=160000),
    sample_rate=st.sampled_from([16000, 22050, 44100])
)
def test_stt_transcription_completeness(audio, sample_rate):
    """
    Feature: guru-speech-engine, Property 4: STT Transcription Completeness
    For any valid audio, transcription should return complete result structure.
    """
    stt_engine = STTEngine()
    audio_array = np.array(audio, dtype=np.float32)
    
    result = stt_engine.transcribe(audio_array, sample_rate)
    
    assert result.text is not None
    assert result.language in ["en", "es", "fr", "de", "zh", "ja", "hi", "pa", "unknown"]
    assert 0.0 <= result.confidence <= 1.0
    assert result.duration >= 0.0
    assert len(result.segments) >= 0
    for segment in result.segments:
        assert 0.0 <= segment.start <= segment.end
        assert 0.0 <= segment.confidence <= 1.0

@given(
    audio=st.lists(st.floats(min_value=-1.0, max_value=1.0), min_size=16000, max_size=160000)
)
def test_emotion_detection_completeness(audio):
    """
    Feature: guru-speech-engine, Property 15: Emotion Detection Completeness
    For any audio, emotion detection should return complete result within 200ms.
    """
    emotion_detector = EmotionDetector()
    audio_array = np.array(audio, dtype=np.float32)
    
    start_time = time.time()
    result = emotion_detector.detect_emotion(audio_array, 16000)
    detection_time = (time.time() - start_time) * 1000
    
    assert detection_time < 200
    assert result.primary_emotion in EmotionType
    assert len(result.emotion_scores) == 7  # All emotion types
    for emotion, score in result.emotion_scores.items():
        assert 0.0 <= score <= 1.0
    assert 0.0 <= result.confidence <= 1.0

@given(
    noisy_audio=st.lists(st.floats(min_value=-1.0, max_value=1.0), min_size=16000, max_size=48000)
)
def test_noise_cancellation_effectiveness(noisy_audio):
    """
    Feature: guru-speech-engine, Property 18: Advanced Noise Cancellation Effectiveness
    For any noisy audio, noise reduction should be >= 20dB within 50ms per chunk.
    """
    noise_cancellation = AdvancedNoiseCancellation()
    audio_array = np.array(noisy_audio, dtype=np.float32)
    
    # Measure SNR before
    snr_before = compute_snr(audio_array)
    
    # Apply noise cancellation
    start_time = time.time()
    cleaned_audio, profile = noise_cancellation.reduce_noise(audio_array, 16000)
    processing_time = (time.time() - start_time) * 1000
    
    # Measure SNR after
    snr_after = compute_snr(cleaned_audio)
    
    # Check noise reduction
    snr_improvement = snr_after - snr_before
    assert snr_improvement >= 20.0  # At least 20dB reduction
    
    # Check latency (for 1 second chunk)
    chunk_duration_ms = len(audio_array) / 16000 * 1000
    if chunk_duration_ms <= 1000:
        assert processing_time < 50
    
    # Check speech preservation
    speech_preserved = check_speech_preservation(audio_array, cleaned_audio)
    assert speech_preserved

@given(
    command_text=st.text(min_size=5, max_size=100)
)
def test_conversation_context_persistence(command_text):
    """
    Feature: guru-speech-engine, Property 22: Conversation Context Persistence
    For any conversation, context should be maintained and references resolved.
    """
    context_manager = ConversationContextManager()
    context = context_manager.create_context("user123", "guru")
    
    # Add first turn
    context = context_manager.add_turn(
        context.conversation_id,
        "Open the browser",
        "Opening browser"
    )
    
    # Add second turn with reference
    context = context_manager.add_turn(
        context.conversation_id,
        "Close it",  # Reference to "browser"
        "Closing browser"
    )
    
    # Resolve reference
    resolved = context_manager.resolve_reference(context.conversation_id, "it")
    assert resolved == "browser"
    
    # Check context persistence
    assert len(context.turns) == 2
    assert context.turns[0].user_input == "Open the browser"
    assert context.turns[1].user_input == "Close it"
```

### Unit Testing

Unit tests will focus on:

1. **Specific Examples**
   - Test "open youtube" → OPEN_YOUTUBE mapping
   - Test English, Hindi, Punjabi language support with sample audio
   - Test specific emotion detection with acted samples
   - Test wake word detection with clean audio samples
   - Test voice cloning with known voice samples

2. **Edge Cases**
   - Empty audio input
   - Very short audio (< 1 second)
   - Very long audio (> 60 seconds)
   - Silent audio (all zeros)
   - Audio with extreme noise (SNR < 0dB)
   - Ambiguous commands requiring clarification
   - Code-switched audio (mixed languages)
   - Poor quality audio for emotion detection

3. **Error Conditions**
   - Invalid file paths
   - Unsupported audio formats
   - Microphone access denied
   - Model loading failures
   - Invalid configuration parameters
   - Network failures for cloud models
   - Disk full during voice cloning
   - Audio buffer overflow/underflow

4. **Integration Points**
   - Pipeline flow: capture → clean → transcribe → interpret → respond
   - Voice biometric integration with Security_System
   - Command routing to Agent_Orchestration
   - Emotion storage in Memory_System
   - Task creation via Goal_Manager
   - Model selection via Model_Router

### Test Coverage Goals

- **Code coverage**: Minimum 95% line coverage
- **Property coverage**: All 27 correctness properties implemented as property tests
- **Language coverage**: Test samples for all 8+ supported languages
- **Format coverage**: Test WAV, MP3, FLAC, OGG file formats
- **Platform coverage**: Test on desktop (Windows, macOS, Linux) and mobile (Android, iOS)
- **Error coverage**: Test all error categories with specific examples

### Testing Dependencies

```
pytest>=7.0.0
hypothesis>=6.0.0
pytest-cov>=4.0.0
pytest-asyncio>=0.21.0
soundfile>=0.12.0
sounddevice>=0.4.0
numpy>=1.24.0
librosa>=0.10.0  # For audio analysis
```

### Continuous Testing

- Run property tests with 100 iterations in CI/CD
- Run unit tests on every commit
- Generate coverage reports
- Test on multiple Python versions (3.10, 3.11, 3.12)
- Test on multiple platforms (Linux, macOS, Windows, Android, iOS)
- Performance regression testing for latency targets
- Accuracy regression testing for STT/TTS quality

### Performance Testing

- **Latency Tests**: Verify all latency targets (<500ms end-to-end, <200ms wake word, <1s mobile STT/TTS)
- **Throughput Tests**: Test continuous operation for 24+ hours
- **Battery Tests**: Verify <5% battery/hour in sleep mode, <10% in wake mode
- **Memory Tests**: Verify no memory leaks over 1000+ wake word detections
- **Stress Tests**: Test with 100 commands in 1 minute, 10+ concurrent sessions

### Accuracy Testing

- **STT Accuracy**: >95% word accuracy on clean audio, >85% on noisy audio (SNR 10dB)
- **Wake Word Accuracy**: >99% true positive rate, <1 false positive per hour
- **Voice Biometrics**: <1% false accept rate, <5% false reject rate
- **Emotion Detection**: >80% accuracy on acted emotional speech
- **Voice Cloning**: >0.85 similarity score
- **Speaker Diarization**: >90% accuracy with 2-5 speakers
