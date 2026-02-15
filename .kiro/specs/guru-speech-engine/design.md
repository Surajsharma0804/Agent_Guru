# Design Document: Speech Recognition & Voice Interface

## Overview

The Speech Recognition & Voice Interface system provides a comprehensive Python-based solution for voice interaction within AGENT_GURU. The system supports dual AI personalities - Guru (male voice) and Maya (female voice) - each with distinct wake words and voice characteristics. The system is architected as a modular pipeline with core components: Dual Wake Word Detection, Speech-to-Text, Voice Biometric Authentication, Gender-Specific Text-to-Speech, Audio Processing, and Command Recognition.

**System Capabilities**:
- **Dual Wake Word Detection**: Detect "Hey Guru" (male) or "Hey Maya" (female) to activate respective personalities
- **Speech-to-Text**: Convert speech to text using OpenAI Whisper
- **Voice Biometric Authentication**: Speaker verification and identification for security
- **Gender-Specific Text-to-Speech**: Male voice for Guru, female voice for Maya
- **Voice Feature Extraction**: Extract voice features for biometric authentication integration
- **Command Recognition**: Parse voice commands for complete laptop control
- **Audio Processing**: Noise reduction, VAD, echo cancellation

**Dual Personality System**:
- **Guru (Male)**: Professional, confident voice with analytical tone
- **Maya (Female)**: Warm, empathetic voice with friendly tone
- Each personality maintains separate conversation context
- Seamless switching between personalities during runtime

**Complete Laptop Control**:
The speech engine enables voice control for ANY laptop operation:
- Open/close applications, type text, send messages
- Control system settings, manage files, execute shortcuts
- Mouse/keyboard control, window management, media control

The design prioritizes low latency, high accuracy, and offline operation where possible.

## Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Speech Engine Core                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Audio Input Manager                         │  │
│  │  (Device enumeration, buffering, format handling)        │  │
│  └────────────────────┬─────────────────────────────────────┘  │
│                       │                                         │
│                       ▼                                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Audio Processor                             │  │
│  │  (VAD, Noise Reduction, Echo Cancellation, AGC)          │  │
│  └────┬─────────────────────────────────────────────────────┘  │
│       │                                                         │
│       ├──────────────┬──────────────┬──────────────┐           │
│       ▼              ▼              ▼              ▼           │
│  ┌─────────┐   ┌─────────┐   ┌──────────┐   ┌──────────┐     │
│  │  Wake   │   │   STT   │   │  Voice   │   │ Command  │     │
│  │  Word   │   │ Engine  │   │ Feature  │   │  Parser  │     │
│  │Detector │   │(Whisper)│   │Extractor │   │          │     │
│  └─────────┘   └─────────┘   └────┬─────┘   └──────────┘     │
│                      │             │              │           │
│                      │             │              │           │
│                      │             └──────────────┼───────────┼──> To Security System
│                      │                            │           │    (for authentication)
│                      └─────────────┬──────────────┘           │
│                                    ▼                           │
│                          ┌──────────────────┐                  │
│                          │   TTS Engine     │                  │
│                          │  (Synthesis)     │                  │
│                          └──────────────────┘                  │
│                                    │                           │
└────────────────────────────────────┼───────────────────────────┘
                                     ▼
                          ┌──────────────────┐
                          │  Audio Output    │
                          └──────────────────┘
```

### Component Interaction Flow

1. **Audio Input Flow**: Audio Input Manager → Audio Processor → Wake Word Detector
2. **Transcription Flow**: Audio Processor → STT Engine → Command Parser
3. **Voice Feature Extraction Flow**: Audio Processor → Voice Feature Extractor → Security System (for authentication)
4. **Synthesis Flow**: TTS Engine → Audio Output
5. **Command Flow**: Command Parser → Application Logic

### Design Principles

- **Modularity**: Each component is independently testable and replaceable
- **Async-First**: All I/O operations are asynchronous to prevent blocking
- **Type Safety**: Comprehensive type hints with mypy strict mode compliance
- **Performance**: Meet or exceed all latency and real-time factor targets
- **Offline-First**: Core functionality works without cloud connectivity
- **Security Integration**: Voice features integrate with guru-security-cryptography for authentication

## Integration Points

This system provides voice processing capabilities for AGENT_GURU, with specific integration for biometric authentication.

### Dependencies

**Upstream Dependencies** (systems this component depends on):
- None (standalone voice processing)

**Downstream Dependencies** (systems that depend on this component):
- **Security System** (guru-security-cryptography): Uses VoiceFeatureExtractor for biometric authentication
- **LLM Runtime** (guru-llm-runtime): Uses transcription for voice commands
- **Agent Orchestration** (guru-agent-orchestration): Uses command interpretation

### API Contracts

**Security System Integration:**
```python
class VoiceFeatureExtractor:
    """Extracts voice biometric features for security system."""
    
    def extract_features(self, audio_data: bytes) -> np.ndarray:
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
transcription = speech_engine.transcribe(audio_data, sample_rate)
command = command_interpreter.interpret(transcription.text)
```

### Data Flow

1. **Voice Authentication Flow:**
   - User provides voice sample
   - Audio Processor cleans audio
   - VoiceFeatureExtractor extracts biometric features
   - Features passed to guru-security-cryptography BiometricAuthenticator
   - Security system performs authentication

2. **Voice Command Flow:**
   - User speaks command
   - Wake Word Detector activates
   - STT Engine transcribes speech
   - Command Interpreter maps to action
   - Action sent to LLM Runtime

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

### Property 1: Transcription Result Completeness

*For any* valid audio input, transcription should return a TranscriptionResult containing non-empty text, a valid language code, a confidence score between 0.0 and 1.0, and a non-negative duration.

**Validates: Requirements 1.4, 7.1, 7.2**

### Property 2: Noise Cleaner Format Compatibility

*For any* audio input (numpy array with sample rate), the Noise_Cleaner output should be a numpy array with the same sample rate and compatible shape for the Whisper_Model.

**Validates: Requirements 2.4**

### Property 3: Command Pattern Matching and Mapping

*For any* registered command pattern and any text that matches that pattern, the Command_Interpreter should return a CommandResult with the correct action_id associated with that pattern.

**Validates: Requirements 4.1, 4.2**

### Property 4: Unrecognized Text Passthrough

*For any* text that does not match any registered command pattern, the Command_Interpreter should return a CommandResult with is_command=False and raw_text equal to the input text.

**Validates: Requirements 4.4**

### Property 5: Error Context Preservation

*For any* component failure during audio processing, the Guru_Speech_Engine should return an error that includes the original error message and identifies which component failed.

**Validates: Requirements 10.1, 10.4**

### Property 6: Model Reuse Across Requests

*For any* sequence of transcription requests to the same GuruSpeechEngine instance, the Whisper model should be loaded exactly once and reused for all subsequent requests.

**Validates: Requirements 11.3**

### Property 7: Command Result Structure Completeness

*For any* command interpretation result where is_command=True, the CommandResult should contain a non-null action_id, a parameters dictionary, the raw_text, a confidence score between 0.0 and 1.0, and a valid language code.

**Validates: Requirements 12.1, 12.3**

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

The Guru Speech Engine will use both unit tests and property-based tests for comprehensive coverage:

- **Unit tests**: Verify specific examples, edge cases, and error conditions
- **Property tests**: Verify universal properties across all inputs

Together, these approaches provide comprehensive coverage where unit tests catch concrete bugs and property tests verify general correctness.

### Property-Based Testing

We will use **Hypothesis** (Python's property-based testing library) for property tests.

**Configuration:**
- Each property test will run a minimum of 100 iterations
- Each test will be tagged with a comment referencing the design property
- Tag format: `# Feature: guru-speech-engine, Property {number}: {property_text}`

**Property Test Examples:**

```python
from hypothesis import given, strategies as st
import numpy as np

@given(
    audio=st.lists(st.floats(min_value=-1.0, max_value=1.0), min_size=1600, max_size=16000),
    sample_rate=st.sampled_from([8000, 16000, 22050, 44100])
)
def test_transcription_result_completeness(audio, sample_rate):
    """
    Feature: guru-speech-engine, Property 1: Transcription Result Completeness
    For any valid audio input, transcription should return complete result.
    """
    engine = GuruSpeechEngine()
    audio_array = np.array(audio, dtype=np.float32)
    
    result = engine.transcribe(audio_array, sample_rate)
    
    assert result.text is not None
    assert len(result.text) >= 0
    assert result.language in ["en", "hi", "pa", "unknown"]
    assert 0.0 <= result.confidence <= 1.0
    assert result.duration >= 0.0

@given(
    pattern=st.text(min_size=1, max_size=50),
    action_id=st.text(min_size=1, max_size=20)
)
def test_command_pattern_matching(pattern, action_id):
    """
    Feature: guru-speech-engine, Property 3: Command Pattern Matching and Mapping
    For any registered pattern, matching text should return correct action_id.
    """
    interpreter = CommandInterpreter()
    interpreter.register_command([pattern], action_id)
    
    result = interpreter.interpret(pattern)
    
    assert result.is_command is True
    assert result.action_id == action_id
```

### Unit Testing

Unit tests will focus on:

1. **Specific Examples**
   - Test "open youtube" → OPEN_YOUTUBE mapping
   - Test English, Hindi, Punjabi language support with sample audio
   - Test configuration with int8 compute type and beam_size=5

2. **Edge Cases**
   - Empty audio input
   - Very short audio (< 1 second)
   - Very long audio (> 60 seconds)
   - Silent audio (all zeros)
   - Audio with extreme noise

3. **Error Conditions**
   - Invalid file paths
   - Unsupported audio formats
   - Microphone access denied
   - Model loading failures
   - Invalid configuration parameters

4. **Integration Points**
   - Pipeline flow: capture → clean → transcribe → interpret
   - File and microphone input produce same output format
   - Custom model loading
   - Command registration and retrieval

### Test Coverage Goals

- **Code coverage**: Minimum 80% line coverage
- **Property coverage**: All 7 correctness properties implemented as property tests
- **Language coverage**: Test samples for English, Hindi, and Punjabi
- **Format coverage**: Test WAV, MP3, and FLAC file formats
- **Error coverage**: Test all error categories with specific examples

### Testing Dependencies

```
pytest>=7.0.0
hypothesis>=6.0.0
pytest-cov>=4.0.0
soundfile>=0.12.0
sounddevice>=0.4.0
```

### Continuous Testing

- Run property tests with 100 iterations in CI/CD
- Run unit tests on every commit
- Generate coverage reports
- Test on multiple Python versions (3.8, 3.9, 3.10, 3.11)
- Test on multiple platforms (Linux, macOS, Windows)
