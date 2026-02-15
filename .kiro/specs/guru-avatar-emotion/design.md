# Design Document: Avatar and Emotion Engine

## Overview

The Avatar and Emotion Engine is a Python-based system that provides real-time visual representation of the AGENT_GURU AI with emotion recognition, lip synchronization, and personality-driven behavior. The system integrates multiple ML models (DeepFace for emotion recognition, Wav2Lip/MediaPipe for lip sync) with a rule-based personality engine and real-time rendering using OpenCV and PyQt.

The architecture follows a modular pipeline design where each component (emotion recognition, lip sync, personality, rendering) operates independently but shares a unified state through a central state manager. This enables concurrent processing, graceful degradation, and easy testing of individual components.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Avatar System                            │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              State Manager (Thread-Safe)                │ │
│  │  - Current Emotion State                                │ │
│  │  - Personality Profile                                  │ │
│  │  - Lip Sync Data                                        │ │
│  │  - Rendering Parameters                                 │ │
│  └────────────────────────────────────────────────────────┘ │
│                           ▲                                  │
│                           │                                  │
│  ┌────────────┬──────────┴──────────┬────────────┐         │
│  │            │                      │            │         │
│  ▼            ▼                      ▼            ▼         │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│ │ Emotion  │ │   Lip    │ │Personality│ │ Renderer │       │
│ │Recognizer│ │   Sync   │ │  Engine  │ │          │       │
│ │          │ │Controller│ │          │ │          │       │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│      ▲            ▲             ▲            │              │
└──────┼────────────┼─────────────┼────────────┼──────────────┘
       │            │             │            │
   Video Input  Audio Input  Config Files  Display Output
```

### Component Interaction Flow

1. **Emotion Recognition Pipeline**: Video frames → Face detection → Emotion classification → State update
2. **Lip Sync Pipeline**: Audio input → Feature extraction → Landmark generation → State update
3. **Personality Pipeline**: State changes → Personality rules → Behavior modulation → State update
4. **Rendering Pipeline**: State polling → Frame generation → Display update

### Threading Model

- **Main Thread**: State manager and coordination
- **Emotion Thread**: Continuous video processing (optional, can be synchronous)
- **Lip Sync Thread**: Audio processing and landmark generation
- **Render Thread**: Display updates at target FPS
- **Thread Safety**: All state access protected by threading.Lock

## Components and Interfaces

### 1. State Manager

**Purpose**: Central state management with thread-safe access and validation.

**Interface**:
```python
class EmotionState:
    emotion: str  # One of: happy, sad, angry, fear, surprise, disgust, neutral
    confidence: float  # 0.0 to 1.0
    timestamp: float  # Unix timestamp

class LipSyncState:
    landmarks: List[Tuple[float, float]]  # Facial landmark coordinates
    timestamp: float
    audio_position: float  # Current position in audio (seconds)

class PersonalityProfile:
    friendliness: float  # 0.0 to 1.0
    formality: float
    expressiveness: float
    responsiveness: float
    humor: float

class AvatarState:
    emotion: EmotionState
    lip_sync: LipSyncState
    personality: PersonalityProfile
    rendering_params: Dict[str, Any]

class StateManager:
    def get_state() -> AvatarState:
        """Thread-safe state retrieval"""
        
    def update_emotion(emotion: EmotionState) -> bool:
        """Update emotion state with validation"""
        
    def update_lip_sync(lip_sync: LipSyncState) -> bool:
        """Update lip sync state with validation"""
        
    def update_personality(personality: PersonalityProfile) -> bool:
        """Update personality profile with validation"""
        
    def serialize() -> Dict[str, Any]:
        """Serialize state to dictionary"""
        
    def deserialize(data: Dict[str, Any]) -> bool:
        """Deserialize and validate state from dictionary"""
```

### 2. Emotion Recognizer

**Purpose**: Detect and classify emotions from video frames using DeepFace.

**Dependencies**: DeepFace, OpenCV, NumPy

**Interface**:
```python
class EmotionRecognizer:
    def __init__(self, model: str = "DeepFace", confidence_threshold: float = 0.5):
        """Initialize emotion recognition model"""
        
    def detect_emotion(frame: np.ndarray) -> EmotionState:
        """
        Detect emotion from a single frame.
        Returns EmotionState with detected emotion and confidence.
        Returns neutral emotion if no face detected or confidence too low.
        """
        
    def detect_emotion_smooth(frame: np.ndarray, history_size: int = 5) -> EmotionState:
        """
        Detect emotion with temporal smoothing.
        Maintains history of recent detections to reduce jitter.
        """
        
    def set_confidence_threshold(threshold: float) -> None:
        """Update confidence threshold for emotion detection"""
```

**Implementation Details**:
- Use DeepFace.analyze() with emotion detection enabled
- Face detection using OpenCV Haar cascades or DeepFace built-in detector
- Temporal smoothing using exponential moving average or majority voting
- Fallback to neutral emotion when confidence < threshold
- Support for multiple emotion models (DeepFace, FER) via strategy pattern

### 3. Lip Sync Controller

**Purpose**: Generate lip movements synchronized with audio using Wav2Lip or MediaPipe.

**Dependencies**: Wav2Lip (or MediaPipe), librosa, NumPy

**Interface**:
```python
class LipSyncController:
    def __init__(self, model_path: str, sync_threshold_ms: float = 50.0):
        """Initialize lip sync model"""
        
    def extract_audio_features(audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """Extract audio features (MFCCs or mel spectrograms)"""
        
    def generate_landmarks(audio_features: np.ndarray, timestamp: float) -> LipSyncState:
        """
        Generate facial landmarks for lip movements.
        Returns LipSyncState with landmarks and timing information.
        """
        
    def process_audio_stream(audio_stream: Iterator[np.ndarray], 
                            sample_rate: int,
                            callback: Callable[[LipSyncState], None]) -> None:
        """
        Process streaming audio and invoke callback with lip sync states.
        Maintains synchronization within sync_threshold_ms.
        """
        
    def reset() -> None:
        """Reset to neutral mouth position"""
```

**Implementation Details**:
- Audio feature extraction using librosa (MFCCs, mel spectrograms)
- Wav2Lip model for generating lip movements from audio
- Alternative: MediaPipe Face Mesh for landmark-based approach
- Buffering strategy to maintain sync within 50ms
- Graceful degradation for poor audio quality
- Support for multiple audio formats via librosa

### 4. Personality Engine

**Purpose**: Apply personality traits to avatar behavior and emotion expression.

**Dependencies**: NumPy (for trait calculations)

**Interface**:
```python
class PersonalityEngine:
    def __init__(self, profile_path: str):
        """Load personality profile from configuration file"""
        
    def load_profile(profile_path: str) -> PersonalityProfile:
        """Load and validate personality profile"""
        
    def modulate_emotion(emotion: EmotionState, 
                        personality: PersonalityProfile) -> EmotionState:
        """
        Apply personality traits to emotion intensity.
        High expressiveness increases emotion intensity.
        High formality reduces extreme emotions.
        """
        
    def generate_response_emotion(user_emotion: EmotionState,
                                  personality: PersonalityProfile) -> EmotionState:
        """
        Generate appropriate avatar emotional response to user emotion.
        High friendliness mirrors positive emotions.
        High responsiveness increases reaction speed.
        """
        
    def apply_behavior_rules(state: AvatarState) -> AvatarState:
        """
        Apply rule-based behavior patterns.
        Examples: smile when greeting, concerned when user is sad.
        """
```

**Implementation Details**:
- Rule-based system using if-then patterns
- Personality traits modulate emotion intensity (0.0-1.0 multipliers)
- Behavior rules stored in configuration files (JSON/YAML)
- Optional ML enhancement using trained models for personality expression
- Validation of personality trait ranges (0.0 to 1.0)

### 5. Renderer

**Purpose**: Display avatar with real-time updates using OpenCV or PyQt.

**Dependencies**: OpenCV, PyQt5 (optional), NumPy

**Interface**:
```python
class Renderer:
    def __init__(self, backend: str = "opencv", target_fps: int = 30):
        """Initialize renderer with specified backend"""
        
    def initialize_display(width: int, height: int, title: str) -> bool:
        """Initialize display window or widget"""
        
    def render_frame(state: AvatarState) -> np.ndarray:
        """
        Generate frame from current avatar state.
        Applies emotion expression and lip sync landmarks.
        Returns rendered frame as numpy array.
        """
        
    def display_frame(frame: np.ndarray) -> bool:
        """Display frame in window or widget"""
        
    def start_render_loop(state_manager: StateManager, 
                         target_fps: int) -> None:
        """
        Start continuous rendering loop.
        Polls state manager and updates display at target FPS.
        """
        
    def stop_render_loop() -> None:
        """Stop rendering loop and release resources"""
        
    def set_target_fps(fps: int) -> None:
        """Update target frame rate"""
```

**Implementation Details**:
- OpenCV backend: cv2.imshow() for simple windowed display
- PyQt backend: QLabel with QPixmap for embeddable widget
- Headless backend: render to memory without display (for testing)
- Frame blending for smooth emotion transitions (linear interpolation)
- FPS limiting using time.sleep() or QTimer
- Graceful degradation: reduce FPS when resources constrained

### 6. Avatar System (Main Coordinator)

**Purpose**: Coordinate all components and manage lifecycle.

**Interface**:
```python
class AvatarSystem:
    def __init__(self, config_path: str):
        """Initialize avatar system from configuration"""
        
    def start(video_source: Optional[int] = None) -> bool:
        """
        Start all components.
        video_source: camera index for emotion recognition (None to disable)
        """
        
    def stop() -> None:
        """Stop all components and release resources"""
        
    def process_audio(audio: np.ndarray, sample_rate: int) -> None:
        """Process audio for lip sync"""
        
    def get_current_state() -> AvatarState:
        """Get current avatar state"""
        
    def set_personality(profile: PersonalityProfile) -> bool:
        """Update personality profile"""
        
    def register_error_callback(callback: Callable[[Exception], None]) -> None:
        """Register callback for error notifications"""
        
    def get_performance_metrics() -> Dict[str, float]:
        """Get performance metrics (FPS, latency, CPU/memory usage)"""
```

## Data Models

### Configuration Schema

```python
class AvatarConfig:
    # Emotion Recognition
    emotion_model: str = "DeepFace"  # DeepFace, FER
    emotion_confidence_threshold: float = 0.5
    emotion_smoothing_window: int = 5
    
    # Lip Sync
    lip_sync_model_path: str = "models/wav2lip.pth"
    lip_sync_threshold_ms: float = 50.0
    audio_buffer_size: int = 4096
    
    # Personality
    personality_profile_path: str = "config/personality.json"
    
    # Rendering
    render_backend: str = "opencv"  # opencv, pyqt, headless
    target_fps: int = 30
    display_width: int = 640
    display_height: int = 480
    
    # Performance
    max_cpu_percent: float = 50.0
    max_memory_mb: float = 512.0
    enable_gpu: bool = True
    
    # Paths
    avatar_model_path: Optional[str] = None  # Custom avatar model
```

### Emotion Mapping

```python
EMOTION_CATEGORIES = [
    "happy",
    "sad", 
    "angry",
    "fear",
    "surprise",
    "disgust",
    "neutral"
]

# Emotion intensity modulation based on personality
def calculate_emotion_intensity(
    base_emotion: EmotionState,
    personality: PersonalityProfile
) -> float:
    intensity = base_emotion.confidence
    
    # Expressiveness increases intensity
    intensity *= (0.5 + personality.expressiveness * 0.5)
    
    # Formality reduces extreme emotions
    if base_emotion.emotion in ["angry", "fear", "disgust"]:
        intensity *= (1.0 - personality.formality * 0.3)
    
    return min(1.0, max(0.0, intensity))
```

### Lip Sync Landmarks

```python
# MediaPipe Face Mesh landmark indices for mouth region
MOUTH_LANDMARK_INDICES = [
    61, 185, 40, 39, 37, 0, 267, 269, 270, 409,  # Upper lip
    146, 91, 181, 84, 17, 314, 405, 321, 375, 291  # Lower lip
]

class LipSyncLandmarks:
    """Normalized landmark coordinates (0.0 to 1.0)"""
    upper_lip: List[Tuple[float, float]]
    lower_lip: List[Tuple[float, float]]
    mouth_open_ratio: float  # 0.0 (closed) to 1.0 (fully open)
```

## Data Flow

### Emotion Recognition Flow

```
Video Frame (np.ndarray)
    ↓
Face Detection (OpenCV/DeepFace)
    ↓
Emotion Classification (DeepFace.analyze)
    ↓
Confidence Filtering (threshold check)
    ↓
Temporal Smoothing (moving average)
    ↓
EmotionState
    ↓
Personality Modulation (PersonalityEngine)
    ↓
StateManager.update_emotion()
    ↓
Renderer (displays updated emotion)
```

### Lip Sync Flow

```
Audio Input (np.ndarray, sample_rate)
    ↓
Audio Feature Extraction (librosa MFCCs)
    ↓
Landmark Generation (Wav2Lip/MediaPipe)
    ↓
Timing Synchronization (buffer management)
    ↓
LipSyncState
    ↓
StateManager.update_lip_sync()
    ↓
Renderer (displays lip movements)
```

### Rendering Flow

```
Render Loop (target FPS)
    ↓
StateManager.get_state()
    ↓
Emotion → Facial Expression Mapping
    ↓
Lip Sync → Mouth Landmark Application
    ↓
Frame Generation (avatar model + landmarks)
    ↓
Transition Blending (smooth emotion changes)
    ↓
Display Output (cv2.imshow or PyQt)
```


## Correctness Properties

A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.

### Emotion Recognition Properties

**Property 1: Valid emotion detection output**
*For any* video frame with a detectable face, emotion recognition should return an EmotionState with a valid emotion category (one of the seven supported emotions) and a confidence score between 0.0 and 1.0.
**Validates: Requirements 1.1, 1.4, 1.5**

**Property 2: Primary face selection consistency**
*For any* frame containing multiple faces, emotion recognition should consistently select the same face as primary (largest or closest to center) across multiple invocations with the same frame.
**Validates: Requirements 1.2**

**Property 3: Confidence threshold enforcement**
*For any* emotion detection result with confidence below the configured threshold, the system should return neutral emotion regardless of the detected emotion category.
**Validates: Requirements 1.6**

**Property 4: Temporal smoothing reduces jitter**
*For any* sequence of video frames, emotion detection with smoothing enabled should produce fewer emotion transitions than without smoothing, while maintaining the same final emotion state.
**Validates: Requirements 1.7**

### Lip Sync Properties

**Property 5: Audio feature extraction completeness**
*For any* valid audio input, feature extraction should return a non-empty array of features with dimensions matching the expected feature size for the model.
**Validates: Requirements 2.1**

**Property 6: Landmark validity**
*For any* generated lip sync landmarks, all coordinate values should be within the normalized range [0.0, 1.0] and the number of landmarks should match the expected mouth landmark count.
**Validates: Requirements 2.2**

**Property 7: Synchronization timing accuracy**
*For any* audio input with speech, the timestamp difference between audio position and corresponding lip sync state should be less than or equal to the configured sync threshold (50ms).
**Validates: Requirements 2.3**

**Property 8: Processing latency bound**
*For any* audio chunk processed in real-time mode, the processing time from input to lip sync state generation should be less than 100ms.
**Validates: Requirements 2.5**

### Personality Engine Properties

**Property 9: Personality profile validation**
*For any* personality profile loaded from configuration, all required traits (friendliness, formality, expressiveness, responsiveness, humor) should be present with values in the range [0.0, 1.0], or loading should fail with a validation error.
**Validates: Requirements 3.2, 3.3**

**Property 10: Emotion intensity modulation**
*For any* emotion state and personality profile, applying personality modulation should produce an emotion with intensity (confidence) that is influenced by expressiveness and formality traits, with the result remaining in the valid range [0.0, 1.0].
**Validates: Requirements 3.4**

**Property 11: Personality-based response generation**
*For any* user emotion and personality profile, the generated avatar response emotion should reflect personality traits (e.g., high friendliness increases positive response to positive user emotions).
**Validates: Requirements 3.5**

### Rendering Properties

**Property 12: Minimum frame rate maintenance**
*For any* rendering session under normal system load, the measured frame rate over a 5-second window should be at least 24 FPS.
**Validates: Requirements 4.1**

**Property 13: Emotion update latency**
*For any* emotion state change, the time from state update to visible frame update should be less than or equal to 100ms.
**Validates: Requirements 4.2**

**Property 14: Lip sync rendering synchronization**
*For any* lip sync state update, the rendered mouth position should correspond to the audio position within the sync threshold, maintaining audio-visual synchronization.
**Validates: Requirements 4.3**

**Property 15: Smooth emotion transitions**
*For any* emotion state change, the transition should be blended over 200-500ms, meaning intermediate frames should show gradual changes rather than abrupt jumps.
**Validates: Requirements 4.6**

### State Management Properties

**Property 16: State propagation timing**
*For any* state update from any component, all dependent components should receive the updated state within 50ms.
**Validates: Requirements 5.2**

**Property 17: State transition validation**
*For any* attempted state update, if the new state contains invalid values (e.g., emotion confidence > 1.0, personality trait < 0.0), the update should be rejected and the previous valid state should be maintained.
**Validates: Requirements 5.3**

**Property 18: State serialization round-trip**
*For any* valid AvatarState, serializing then deserializing should produce an equivalent state with all fields matching the original values.
**Validates: Requirements 5.5**

**Property 19: Deserialization validation**
*For any* serialized state data, deserialization should validate all fields before applying the state, rejecting invalid data and returning an error.
**Validates: Requirements 5.6**

**Property 20: Thread-safe state access**
*For any* concurrent state access operations (reads and writes from multiple threads), the state should remain consistent with no race conditions or data corruption.
**Validates: Requirements 5.7**

### Audio Integration Properties

**Property 21: Audio buffering smoothness**
*For any* audio stream input, the buffering mechanism should maintain smooth playback without gaps or stuttering, even with variable input timing.
**Validates: Requirements 6.2**

**Property 22: Audio-lip sync timing**
*For any* audio playback, lip movements should be synchronized with audio within the configured threshold, measured as the difference between audio timestamp and lip sync timestamp.
**Validates: Requirements 6.3**

### Resource Management Properties

**Property 23: Resource usage bounds**
*For any* avatar system operation, CPU usage should remain below the configured maximum percentage and memory usage should remain below the configured maximum size over any 10-second measurement window.
**Validates: Requirements 7.1, 7.2**

### Configuration Properties

**Property 24: Configuration validation**
*For any* configuration file loaded, all parameters should be validated against the schema, with invalid configurations rejected and detailed error messages provided.
**Validates: Requirements 8.2**

**Property 25: Custom model validation**
*For any* custom avatar model provided, the system should validate model compatibility (file format, expected inputs/outputs) before attempting to use it, rejecting incompatible models with clear error messages.
**Validates: Requirements 8.7**

### Error Handling Properties

**Property 26: Error logging completeness**
*For any* error that occurs in any component, the error should be logged with sufficient context including component name, error type, timestamp, and relevant state information.
**Validates: Requirements 9.5**

## Error Handling

### Error Categories

1. **Input Errors**: Invalid video frames, corrupted audio, malformed configuration
2. **Model Errors**: Failed model loading, inference errors, out-of-memory
3. **Resource Errors**: Camera unavailable, GPU unavailable, insufficient memory
4. **Timing Errors**: Synchronization failures, timeout errors
5. **State Errors**: Invalid state transitions, serialization failures

### Error Handling Strategy

**Graceful Degradation**:
- Camera failure → Continue with last known emotion or neutral
- Emotion recognition failure → Default to neutral emotion
- Lip sync failure → Static mouth position
- Rendering failure → Attempt reinitialize once, then disable display
- GPU unavailable → Fall back to CPU processing

**Error Recovery**:
- Transient errors: Automatic retry with exponential backoff
- Persistent errors: Log and notify via error callbacks
- Critical errors: Graceful shutdown with resource cleanup

**Error Logging**:
- All errors logged with Python logging module
- Log levels: DEBUG (verbose), INFO (state changes), WARNING (degradation), ERROR (failures), CRITICAL (shutdown)
- Structured logging with JSON format for machine parsing
- Include stack traces for unexpected errors

**Error Callbacks**:
```python
class ErrorCallback(Protocol):
    def on_error(self, error: Exception, component: str, context: Dict[str, Any]) -> None:
        """Called when errors occur in avatar system"""
```

### Specific Error Handling

**Emotion Recognition**:
- No face detected → Return neutral emotion (not an error)
- Multiple faces → Select primary face (not an error)
- Model inference failure → Log error, return neutral, continue
- Invalid frame format → Log error, skip frame, continue

**Lip Sync**:
- Audio format unsupported → Try conversion, if fails log error and skip
- Sync threshold exceeded → Log warning, continue with best effort
- Model inference failure → Log error, return neutral mouth, continue

**Personality Engine**:
- Invalid personality profile → Log error, use default profile
- Missing traits → Log warning, use default values for missing traits
- Rule evaluation error → Log error, skip rule, continue

**Rendering**:
- Display initialization failure → Try once more, if fails switch to headless
- Frame generation failure → Log error, reuse last frame
- FPS below target → Log warning, continue with reduced FPS

**State Management**:
- Invalid state update → Log error, reject update, maintain previous state
- Serialization failure → Log error, return error to caller
- Deserialization failure → Log error, return error to caller
- Thread synchronization timeout → Log error, retry once

## Testing Strategy

### Dual Testing Approach

The avatar system requires both unit tests and property-based tests for comprehensive coverage:

- **Unit tests**: Verify specific examples, edge cases, and error conditions
- **Property tests**: Verify universal properties across all inputs

Both testing approaches are complementary and necessary. Unit tests catch concrete bugs in specific scenarios, while property tests verify general correctness across a wide range of inputs.

### Property-Based Testing

**Framework**: Use `hypothesis` library for Python property-based testing

**Configuration**: Each property test should run a minimum of 100 iterations to ensure comprehensive input coverage

**Test Tagging**: Each property test must include a comment referencing the design document property:
```python
# Feature: guru-avatar-emotion, Property 1: Valid emotion detection output
@given(video_frame=valid_video_frames())
def test_emotion_detection_output_validity(video_frame):
    ...
```

**Property Test Coverage**:
- All 26 correctness properties must be implemented as property-based tests
- Each property maps to a single test function
- Tests should use hypothesis strategies to generate diverse inputs
- Tests should verify the property holds across all generated inputs

### Unit Testing

**Framework**: Use `pytest` for all unit tests

**Unit Test Focus**:
- Specific examples demonstrating correct behavior
- Edge cases (no face, silence, empty config)
- Error conditions (invalid input, model failures)
- Integration between components
- Configuration loading and validation

**Coverage Target**: 90%+ code coverage measured with `pytest-cov`

### Test Organization

```
tests/
├── unit/
│   ├── test_emotion_recognizer.py
│   ├── test_lip_sync_controller.py
│   ├── test_personality_engine.py
│   ├── test_renderer.py
│   ├── test_state_manager.py
│   └── test_avatar_system.py
├── property/
│   ├── test_emotion_properties.py
│   ├── test_lip_sync_properties.py
│   ├── test_personality_properties.py
│   ├── test_rendering_properties.py
│   ├── test_state_properties.py
│   └── test_integration_properties.py
├── integration/
│   ├── test_end_to_end.py
│   └── test_speech_integration.py
├── fixtures/
│   ├── emotion_images/
│   ├── audio_samples/
│   └── config_files/
└── conftest.py
```

### Test Fixtures

**Emotion Recognition Fixtures**:
- Images with known emotions (happy, sad, angry, etc.)
- Images with no faces
- Images with multiple faces
- Images with poor quality/lighting

**Lip Sync Fixtures**:
- Audio samples with known phonemes
- Silent audio
- Audio in various formats (WAV, MP3, PCM)
- Poor quality audio

**Configuration Fixtures**:
- Valid configuration files
- Invalid configuration files (missing fields, wrong types)
- Custom personality profiles
- Custom avatar models

### Hypothesis Strategies

```python
from hypothesis import strategies as st

# Emotion states
@st.composite
def emotion_states(draw):
    emotion = draw(st.sampled_from(EMOTION_CATEGORIES))
    confidence = draw(st.floats(min_value=0.0, max_value=1.0))
    timestamp = draw(st.floats(min_value=0.0, max_value=1e10))
    return EmotionState(emotion, confidence, timestamp)

# Personality profiles
@st.composite
def personality_profiles(draw):
    return PersonalityProfile(
        friendliness=draw(st.floats(min_value=0.0, max_value=1.0)),
        formality=draw(st.floats(min_value=0.0, max_value=1.0)),
        expressiveness=draw(st.floats(min_value=0.0, max_value=1.0)),
        responsiveness=draw(st.floats(min_value=0.0, max_value=1.0)),
        humor=draw(st.floats(min_value=0.0, max_value=1.0))
    )

# Video frames
@st.composite
def video_frames(draw):
    height = draw(st.integers(min_value=240, max_value=1080))
    width = draw(st.integers(min_value=320, max_value=1920))
    channels = 3
    return np.random.randint(0, 256, (height, width, channels), dtype=np.uint8)

# Audio samples
@st.composite
def audio_samples(draw):
    duration = draw(st.floats(min_value=0.1, max_value=10.0))
    sample_rate = draw(st.sampled_from([16000, 22050, 44100, 48000]))
    num_samples = int(duration * sample_rate)
    return np.random.randn(num_samples).astype(np.float32), sample_rate
```

### Integration Testing

**End-to-End Tests**:
- Start avatar system with camera input
- Process video and audio simultaneously
- Verify all components work together
- Measure overall system performance

**Speech System Integration**:
- Connect to speech synthesis system
- Verify audio routing works correctly
- Verify lip sync synchronization with synthesized speech
- Test error handling when speech system unavailable

### Performance Testing

**Benchmarks** (using `pytest-benchmark`):
- Emotion recognition latency
- Lip sync processing latency
- State update propagation time
- Rendering frame time
- Memory usage over time

**Performance Targets**:
- Emotion recognition: < 50ms per frame
- Lip sync processing: < 100ms per audio chunk
- State propagation: < 50ms
- Rendering: 30 FPS (33ms per frame)
- Memory usage: < 512 MB

### Headless Testing

All tests must support headless mode (no display required):
- Use headless rendering backend
- Mock camera input with test fixtures
- Mock audio input with test samples
- Verify all functionality without GUI

### Continuous Integration

**Pre-commit Checks**:
- `black` formatting (zero tolerance)
- `flake8` linting (zero errors)
- `mypy` type checking (strict mode)
- `pylint` score ≥ 9.0/10

**CI Pipeline**:
1. Run all unit tests
2. Run all property tests (100 iterations each)
3. Run integration tests
4. Measure code coverage (target: 90%+)
5. Run performance benchmarks
6. Generate test report

**Test Execution Time**:
- Unit tests: < 2 minutes
- Property tests: < 10 minutes
- Integration tests: < 5 minutes
- Total: < 20 minutes
