# Design Document: AGENT_GURU Production Engineering

## Overview

AGENT_GURU is a production-grade voice-controlled AI assistant that combines Rust (core engine, OS control, audio pipeline), Python (reasoning, memory, LLM control), and C++ (ML runtime integration) to deliver a complete voice assistant experience. This design document outlines the architecture, components, and implementation strategy for transforming the current operational system into a fully functional, production-ready application.

The system follows a pipeline architecture where audio flows through distinct stages: wake word detection → speech-to-text → intent parsing → action execution → LLM response generation → text-to-speech → audio playback. Each stage is optimized for low latency and high accuracy, with comprehensive error handling and graceful degradation.

### Design Goals

1. **Zero-Error Production Quality**: Eliminate all compilation errors, warnings, and dead code
2. **Low-Latency Voice Pipeline**: Achieve sub-second end-to-end response times
3. **Cross-Platform Support**: Deliver consistent functionality on Windows and macOS
4. **Offline-First Operation**: Support local models for privacy and reliability
5. **Extensible Architecture**: Enable easy addition of new commands and capabilities
6. **Production-Ready Installers**: Provide user-friendly installation packages

## Architecture

### System Architecture

The AGENT_GURU system follows a layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                     User Interface Layer                     │
│              (Voice Input/Output, Visual Feedback)           │
└─────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────┐
│                   Voice Pipeline Layer                       │
│  ┌──────────┐  ┌──────┐  ┌────────┐  ┌──────┐  ┌──────┐   │
│  │  Wake    │→ │ STT  │→ │ Intent │→ │ LLM  │→ │ TTS  │   │
│  │  Word    │  │      │  │ Parser │  │      │  │      │   │
│  └──────────┘  └──────┘  └────────┘  └──────┘  └──────┘   │
└─────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────┐
│                   Action Execution Layer                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ OS Control   │  │ App Launcher │  │ UI Automation│     │
│  │ (Win/macOS)  │  │              │  │              │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────┐
│                    Infrastructure Layer                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Audio I/O    │  │ Memory       │  │ Security     │     │
│  │ (cpal/rodio) │  │ System       │  │ & Crypto     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### Language Boundaries

The system uses three languages with clear responsibilities:

**Rust (Core Engine)**:
- Audio capture and playback (cpal, rodio)
- Wake word detection (MFCC-based neural classifier)
- OS-level control (Windows/macOS APIs)
- Security and cryptography
- Policy enforcement
- Performance-critical paths

**Python (Intelligence Layer)**:
- LLM provider management (Ollama, OpenAI, Gemini)
- Intent classification and routing
- Conversation memory and context
- Reasoning and decision-making
- High-level orchestration

**C++ (ML Runtime)**:
- Whisper.cpp integration (STT)
- Llama.cpp integration (local LLM)
- TTS runtime (Coqui/Piper)
- Optimized inference engines

### Communication Patterns

**Rust ↔ Python**: 
- FFI bindings using PyO3 or ctypes
- JSON-based message passing for complex data
- Shared memory for audio buffers (zero-copy)

**Rust ↔ C++**:
- C ABI bindings
- Direct function calls for performance
- Minimal data marshaling overhead

**Python ↔ C++**:
- Python bindings (pybind11)
- Used only for model loading and configuration
- Rust handles runtime inference calls

## Components and Interfaces

### 1. Wake Word Detection Engine

**Responsibility**: Continuously monitor audio stream for activation phrases with minimal CPU usage.

**Implementation**: Rust module using MFCC feature extraction and lightweight neural classifier.

**Interface**:
```rust
pub trait WakeWordEngine {
    fn initialize(&mut self, wake_words: &[String]) -> Result<(), WakeWordError>;
    fn set_sensitivity(&mut self, sensitivity: f32) -> Result<(), WakeWordError>;
    fn process_audio_stream(&mut self, audio: &[f32]) -> Result<Option<WakeWordEvent>, WakeWordError>;
    fn get_metrics(&self) -> WakeWordMetrics;
}

pub struct WakeWordEvent {
    pub wake_word: String,
    pub confidence: f32,
    pub timestamp: Instant,
}
```

**Performance Requirements**:
- Detection latency: ≤50ms (99th percentile)
- CPU usage: <10% during idle monitoring
- Memory footprint: <50MB
- False positive rate: <5%

**Key Design Decisions**:
- Use MFCC features (13 coefficients) for acoustic representation
- Sliding window approach (1-second windows, 100ms stride)
- Confidence threshold filtering to reduce false positives
- Lock-free ring buffer for audio data to avoid blocking audio thread

### 2. Speech-to-Text Engine

**Responsibility**: Convert spoken audio to text with high accuracy and low latency.

**Implementation**: C++ Whisper.cpp integration with Rust bindings.

**Interface**:
```rust
pub trait SpeechToTextEngine {
    fn transcribe(&mut self, audio: &AudioBuffer) -> Result<Transcription, STTError>;
    fn transcribe_streaming(&mut self, audio_stream: AudioStream) -> Result<TranscriptionStream, STTError>;
    fn set_language(&mut self, language: &str) -> Result<(), STTError>;
    fn get_metrics(&self) -> STTMetrics;
}

pub struct Transcription {
    pub text: String,
    pub confidence: f32,
    pub word_timestamps: Vec<WordTimestamp>,
    pub processing_time: Duration,
}
```

**Performance Requirements**:
- Processing speed: ≤120ms per second of audio
- Accuracy: ≥95% word error rate (WER) for clear speech
- Model size: Base model (~140MB) for balance of speed/accuracy
- Offline operation: Full functionality without internet

**Key Design Decisions**:
- Use Whisper base model (74M parameters) for optimal speed/accuracy tradeoff
- Implement VAD (Voice Activity Detection) to skip silent segments
- Support streaming transcription for real-time feedback
- Cache model in memory to avoid reload overhead

### 3. Intent Parser and Command Router

**Responsibility**: Analyze transcribed text to determine user intent and extract parameters.

**Implementation**: Python module using pattern matching and optional LLM-based classification.

**Interface**:
```python
class IntentParser:
    def parse_intent(self, text: str) -> Intent:
        """Parse user text and return structured intent."""
        
    def register_command_pattern(self, pattern: CommandPattern) -> None:
        """Register a new command pattern for recognition."""
        
    def get_confidence(self, text: str, intent: Intent) -> float:
        """Get confidence score for intent classification."""

@dataclass
class Intent:
    intent_type: IntentType
    parameters: Dict[str, Any]
    confidence: float
    raw_text: str
```

**Intent Categories**:
- `OPEN_APPLICATION`: Launch applications
- `TYPE_TEXT`: Simulate keyboard input
- `SEND_MESSAGE`: Compose and send messages
- `QUERY_INFORMATION`: Ask questions (route to LLM)
- `CONTROL_SYSTEM`: System-level operations
- `MEDIA_CONTROL`: Play/pause/skip media
- `FILE_OPERATION`: File management
- `WEB_NAVIGATION`: Browser control

**Key Design Decisions**:
- Use regex patterns for common commands (fast path)
- Fall back to LLM for ambiguous or complex queries
- Maintain command history for context-aware parsing
- Support command aliases and variations

### 4. OS-Level Action Executor

**Responsibility**: Execute system-level operations across Windows and macOS platforms.

**Implementation**: Rust modules with platform-specific implementations.

**Interface**:
```rust
pub trait OSController {
    fn launch_application(&self, app_name: &str) -> Result<ProcessHandle, OSError>;
    fn type_text(&self, text: &str) -> Result<(), OSError>;
    fn simulate_click(&self, x: i32, y: i32) -> Result<(), OSError>;
    fn get_active_window(&self) -> Result<WindowInfo, OSError>;
    fn send_keys(&self, keys: &[KeyCode]) -> Result<(), OSError>;
}

// Platform-specific implementations
#[cfg(target_os = "windows")]
pub struct WindowsController { /* ... */ }

#[cfg(target_os = "macos")]
pub struct MacOSController { /* ... */ }
```

**Windows Implementation**:
- Use Win32 API for application launching (`ShellExecuteW`)
- Use `SendInput` for keyboard/mouse simulation
- Use `FindWindow`/`GetForegroundWindow` for window management
- Require appropriate permissions (UAC considerations)

**macOS Implementation**:
- Use `NSWorkspace` for application launching
- Use Accessibility API for UI automation
- Use `CGEvent` for keyboard/mouse simulation
- Require accessibility permissions

**Key Design Decisions**:
- Abstract platform differences behind common trait
- Implement permission checking before operations
- Provide detailed error messages for permission issues
- Log all OS operations for security audit

### 5. LLM Provider Manager

**Responsibility**: Manage multiple LLM providers with runtime switching and fallback.

**Implementation**: Rust module with provider-specific clients.

**Interface**:
```rust
pub trait LLMProvider {
    async fn generate_response(&self, messages: &[ChatMessage]) -> Result<String, LLMError>;
    async fn generate_streaming(&self, messages: &[ChatMessage]) -> Result<ResponseStream, LLMError>;
    fn get_provider_type(&self) -> ProviderType;
    fn is_available(&self) -> bool;
}

pub struct UnifiedProvider {
    providers: HashMap<ProviderType, Box<dyn LLMProvider>>,
    config: LlmRuntimeConfig,
    audit_logger: AuditLogger,
}
```

**Supported Providers**:
- **Ollama**: Local models (Mistral, Llama, etc.)
- **OpenAI**: GPT-3.5/GPT-4 via API
- **Gemini**: Google's Gemini models via API

**Key Design Decisions**:
- Prioritize local models (Ollama) for privacy and offline operation
- Fall back to cloud APIs when local models unavailable
- Stream responses token-by-token for real-time feedback
- Implement request/response audit logging
- Support provider switching without conversation loss

### 6. Text-to-Speech Engine

**Responsibility**: Synthesize natural-sounding speech from text responses.

**Implementation**: Rust module with C++ TTS runtime integration.

**Interface**:
```rust
pub trait TextToSpeechEngine {
    fn synthesize(&self, text: &str) -> Result<Vec<f32>, TTSError>;
    fn synthesize_with_emotion(&self, text: &str, emotion: Emotion) -> Result<Vec<f32>, TTSError>;
    fn set_voice(&mut self, voice: VoiceProfile) -> Result<(), TTSError>;
    fn set_speaking_rate(&mut self, rate: f32) -> Result<(), TTSError>;
}

pub struct SynthesisEngine {
    config: SynthesisConfig,
    voice_model: VoiceModel,
}
```

**TTS Options**:
- **Piper TTS**: Fast, high-quality, offline
- **Coqui TTS**: Emotion-aware synthesis
- **System TTS**: Platform native (fallback)

**Key Design Decisions**:
- Use Piper TTS for primary synthesis (fast, good quality)
- Support multiple voice profiles (male, female, neutral)
- Implement prosody control for natural intonation
- Handle punctuation for appropriate pauses
- Output at 22kHz for good quality with reasonable size

### 7. Conversation Memory System

**Responsibility**: Maintain conversation history and context for multi-turn interactions.

**Implementation**: Rust module with encrypted storage.

**Interface**:
```rust
pub trait MemorySystem {
    fn add_message(&mut self, message: ChatMessage) -> Result<(), MemoryError>;
    fn get_conversation_history(&self, limit: usize) -> Vec<ChatMessage>;
    fn search_context(&self, query: &str) -> Result<Vec<ChatMessage>, MemoryError>;
    fn clear_history(&mut self) -> Result<(), MemoryError>;
    fn persist_to_disk(&self) -> Result<(), MemoryError>;
}

pub struct ConversationMemory {
    messages: VecDeque<ChatMessage>,
    max_history: usize,
    encryption_key: EncryptionKey,
    storage_path: PathBuf,
}
```

**Key Design Decisions**:
- Use LRU eviction when history exceeds limit (50 turns)
- Encrypt conversation data at rest using AES-256-GCM
- Support semantic search over history (future enhancement)
- Persist to disk for cross-session continuity
- Provide user controls for history deletion

### 8. Audio Pipeline Manager

**Responsibility**: Manage audio capture, processing, and playback with low latency.

**Implementation**: Rust module using cpal (capture) and rodio (playback).

**Interface**:
```rust
pub struct AudioPipeline {
    capture_stream: InputStream,
    playback_sink: Sink,
    ring_buffer: RingBuffer<f32>,
    sample_rate: u32,
}

impl AudioPipeline {
    pub fn new(config: AudioConfig) -> Result<Self, AudioError>;
    pub fn start_capture(&mut self) -> Result<(), AudioError>;
    pub fn stop_capture(&mut self) -> Result<(), AudioError>;
    pub fn play_audio(&self, audio: &[f32]) -> Result<(), AudioError>;
    pub fn get_audio_chunk(&mut self, duration: Duration) -> Option<Vec<f32>>;
}
```

**Key Design Decisions**:
- Use lock-free ring buffer for audio data (avoid blocking audio thread)
- Process audio in 1024-sample chunks (64ms at 16kHz)
- Maintain 10-second ring buffer for wake word detection
- Handle device disconnection gracefully with automatic reconnection
- Prevent audio feedback loops during simultaneous capture/playback

## Data Models

### Audio Data Structures

```rust
pub struct AudioBuffer {
    pub samples: Vec<f32>,        // Normalized to [-1.0, 1.0]
    pub sample_rate: u32,          // Hz (typically 16000)
    pub channels: u16,             // 1 (mono) or 2 (stereo)
    pub duration: Duration,        // Calculated from samples
}

pub struct AudioConfig {
    pub input_device: Option<String>,
    pub output_device: Option<String>,
    pub sample_rate: u32,
    pub buffer_size: u32,
    pub input_channels: u16,
    pub output_channels: u16,
}
```

### Voice Pipeline Data Structures

```rust
pub struct WakeWordEvent {
    pub wake_word: String,
    pub confidence: f32,
    pub timestamp: Instant,
}

pub struct Transcription {
    pub text: String,
    pub confidence: f32,
    pub word_timestamps: Vec<WordTimestamp>,
    pub processing_time: Duration,
}

pub struct WordTimestamp {
    pub word: String,
    pub start_time: Duration,
    pub end_time: Duration,
    pub confidence: f32,
}
```

### Intent and Command Data Structures

```python
@dataclass
class Intent:
    intent_type: IntentType
    parameters: Dict[str, Any]
    confidence: float
    raw_text: str
    timestamp: datetime

class IntentType(Enum):
    OPEN_APPLICATION = "open_application"
    TYPE_TEXT = "type_text"
    SEND_MESSAGE = "send_message"
    QUERY_INFORMATION = "query_information"
    CONTROL_SYSTEM = "control_system"
    MEDIA_CONTROL = "media_control"
    FILE_OPERATION = "file_operation"
    WEB_NAVIGATION = "web_navigation"

@dataclass
class CommandPattern:
    pattern: str              # Regex pattern
    intent_type: IntentType
    parameter_extractors: Dict[str, Callable]
    examples: List[str]
```

### LLM Data Structures

```rust
pub struct ChatMessage {
    pub role: String,          // "system", "user", "assistant"
    pub content: String,
    pub timestamp: Option<DateTime<Utc>>,
}

pub struct LlmRuntimeConfig {
    pub default_provider: ProviderType,
    pub fallback_providers: Vec<ProviderType>,
    pub task_routing: HashMap<TaskType, ProviderType>,
    pub ollama_base_url: String,
    pub max_tokens: u32,
    pub temperature: f32,
}

pub enum ProviderType {
    Ollama,
    OpenAI,
    Gemini,
}

pub enum TaskType {
    LanguageHelp,
    CodeGeneration,
    Conversation,
    QuestionAnswering,
}
```

### Performance Metrics Data Structures

```rust
pub struct VoiceMetrics {
    pub wake_word_metrics: WakeWordMetrics,
    pub speech_recognition_metrics: SpeechRecognitionMetrics,
    pub tts_metrics: TTSMetrics,
    pub system_metrics: SystemMetrics,
}

pub struct WakeWordMetrics {
    pub total_detections: u64,
    pub false_positives: u64,
    pub avg_detection_latency_ms: f64,
    pub cpu_utilization: f32,
}

pub struct SpeechRecognitionMetrics {
    pub total_transcriptions: u64,
    pub avg_processing_time_ms: f64,
    pub avg_accuracy: f32,
    pub words_per_minute: f64,
}

pub struct TTSMetrics {
    pub total_syntheses: u64,
    pub avg_synthesis_time_ms: f64,
    pub avg_quality_score: f32,
    pub chars_per_second: f64,
}

pub struct SystemMetrics {
    pub memory_usage_bytes: u64,
    pub peak_memory_usage_bytes: u64,
    pub avg_cpu_utilization: f32,
    pub uptime_seconds: u64,
}
```

### Configuration Data Structures

```rust
pub struct VoiceConfig {
    pub wake_word_config: WakeWordConfig,
    pub speech_recognition_config: SpeechRecognitionConfig,
    pub tts_config: TTSConfig,
    pub audio_config: AudioConfig,
}

pub struct WakeWordConfig {
    pub wake_words: Vec<String>,
    pub sensitivity: f32,
    pub confidence_threshold: f32,
    pub buffer_size_ms: u32,
}

pub struct SpeechRecognitionConfig {
    pub model_path: String,
    pub language: String,
    pub continuous: bool,
    pub max_audio_length: f32,
}

pub struct TTSConfig {
    pub voice_model_path: String,
    pub speaking_rate: f32,
    pub pitch: f32,
    pub emotion_synthesis: bool,
}
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property Reflection

After analyzing all acceptance criteria, I identified several redundant properties:
- Requirements 14.2, 14.3, 14.4 duplicate performance requirements from 6.1, 9.1, and 10.1
- Requirements 19.1 and 19.5 duplicate 11.5 and 8.8
- Requirement 20.2 duplicates 9.7

These redundancies have been eliminated in the properties below to ensure each property provides unique validation value.

### Wake Word Detection Properties

**Property 1: Wake word detection latency**
*For any* wake word detection event, the system should activate listening mode within 50ms of detection.
**Validates: Requirements 5.1, 14.1**

**Property 2: Wake word detection with noise**
*For any* audio stream with background noise, the wake word engine should maintain detection accuracy above 90%.
**Validates: Requirements 5.4**

**Property 3: Wake word feedback latency**
*For any* wake word detection, the system should provide audio or visual feedback within 100ms.
**Validates: Requirements 5.5**

**Property 4: Multiple wake word support**
*For any* set of configured wake words, the wake word engine should detect any phrase in the configuration.
**Validates: Requirements 5.8**

### Speech-to-Text Properties

**Property 5: STT processing latency**
*For any* audio segment, the STT engine should transcribe speech within 120ms per second of audio.
**Validates: Requirements 6.1**

**Property 6: STT transcription accuracy**
*For any* clear English speech sample, the STT engine should achieve at least 95% word accuracy.
**Validates: Requirements 6.2**

**Property 7: STT interface contract**
*For any* completed transcription, the STT engine should return the complete text to the intent parser.
**Validates: Requirements 6.6**

**Property 8: STT confidence scoring**
*For any* poor quality audio input, the STT engine should return a confidence score below 0.7.
**Validates: Requirements 6.7**

### Intent Parsing Properties

**Property 9: Intent classification latency**
*For any* transcribed text input, the intent parser should classify the intent within 50ms.
**Validates: Requirements 7.1**

**Property 10: Application name extraction**
*For any* "open_application" intent, the intent parser should extract the application name parameter.
**Validates: Requirements 7.2**

**Property 11: Text extraction for typing**
*For any* "type_text" intent, the intent parser should extract the text to type parameter.
**Validates: Requirements 7.3**

**Property 12: Message parameter extraction**
*For any* "send_message" intent, the intent parser should extract both recipient and message content parameters.
**Validates: Requirements 7.4**

**Property 13: Query routing to LLM**
*For any* "query_information" intent, the intent parser should route the request to the LLM provider.
**Validates: Requirements 7.5**

**Property 14: System action extraction**
*For any* "control_system" intent, the intent parser should extract the system action and its parameters.
**Validates: Requirements 7.6**

**Property 15: Low confidence clarification**
*For any* intent classification with confidence below 0.6, the intent parser should request clarification from the user.
**Validates: Requirements 7.8**

### OS Control Properties

**Property 16: Windows application launching**
*For any* valid application name on Windows, the OS controller should launch the application using Windows APIs.
**Validates: Requirements 8.1**

**Property 17: macOS application launching**
*For any* valid application name on macOS, the OS controller should launch the application using macOS APIs.
**Validates: Requirements 8.2**

**Property 18: Keyboard input simulation**
*For any* text string, the OS controller should simulate keyboard input in the active window.
**Validates: Requirements 8.3**

**Property 19: Mouse click simulation**
*For any* valid screen coordinates, the OS controller should simulate mouse clicks at those coordinates.
**Validates: Requirements 8.4**

**Property 20: Message sending automation**
*For any* valid recipient and message content, the OS controller should open the messaging application and populate the message.
**Validates: Requirements 8.5**

**Property 21: Application launch verification**
*For any* application launch attempt, the OS controller should verify success within 2 seconds.
**Validates: Requirements 8.6**

**Property 22: Permission error handling**
*For any* OS operation that encounters permission errors, the OS controller should handle the error gracefully and report to the user.
**Validates: Requirements 8.7**

**Property 23: OS operation audit logging**
*For any* OS-level action execution, the OS controller should log the operation for audit purposes.
**Validates: Requirements 8.8**

### LLM Provider Properties

**Property 24: LLM first token latency**
*For any* conversational query, the LLM provider should generate the first response token within 300ms.
**Validates: Requirements 9.1**

**Property 25: Provider switching context preservation**
*For any* provider switch operation, the system should maintain the complete conversation context.
**Validates: Requirements 9.5**

**Property 26: LLM response streaming**
*For any* LLM response generation, the provider should stream responses token-by-token for real-time feedback.
**Validates: Requirements 9.6**

**Property 27: LLM fallback behavior**
*For any* situation where the LLM provider is unavailable, the system should fall back to rule-based responses.
**Validates: Requirements 9.7**

**Property 28: Conversation history maintenance**
*For any* LLM interaction, the provider should maintain conversation history for context-aware responses.
**Validates: Requirements 9.8**

### Text-to-Speech Properties

**Property 29: TTS synthesis latency**
*For any* text response, the TTS engine should synthesize speech within 200ms.
**Validates: Requirements 10.1**

**Property 30: Speech rate adjustment**
*For any* speech rate setting between 0.5x and 2.0x, the TTS engine should adjust the speaking rate accordingly.
**Validates: Requirements 10.4**

**Property 31: Punctuation handling**
*For any* text containing punctuation, the TTS engine should insert natural pauses at punctuation marks.
**Validates: Requirements 10.6**

**Property 32: TTS interruption handling**
*For any* audio playback interruption, the TTS engine should stop synthesis immediately.
**Validates: Requirements 10.8**

### Memory System Properties

**Property 33: Conversation storage**
*For any* conversation message, the memory system should store it in the current session history.
**Validates: Requirements 11.1**

**Property 34: Context preservation across queries**
*For any* sequence of user queries, the memory system should maintain context across all queries.
**Validates: Requirements 11.2**

**Property 35: LRU eviction strategy**
*For any* situation where memory capacity (50 turns) is reached, the memory system should prune the oldest entries using LRU strategy.
**Validates: Requirements 11.4**

**Property 36: Conversation data encryption**
*For any* stored conversation data, the memory system should encrypt it at rest using AES-256-GCM.
**Validates: Requirements 11.5**

**Property 37: Cross-session persistence**
*For any* conversation history, the memory system should support persistence across application sessions.
**Validates: Requirements 11.6**

**Property 38: Memory retrieval latency**
*For any* memory query, the memory system should retrieve relevant context within 10ms.
**Validates: Requirements 11.7**

### Audio Pipeline Properties

**Property 39: Audio device disconnection handling**
*For any* audio device disconnection event, the audio pipeline should handle it gracefully and attempt reconnection.
**Validates: Requirements 12.6**

**Property 40: Audio feedback prevention**
*For any* simultaneous capture and playback operation, the audio pipeline should prevent audio feedback loops.
**Validates: Requirements 12.7**

### Performance Properties

**Property 41: End-to-end latency for simple commands**
*For any* simple command (non-LLM), the system should maintain total end-to-end latency below 1 second.
**Validates: Requirements 14.5**

**Property 42: Startup time optimization**
*For any* system startup, the system should complete model loading and initialization in under 5 seconds.
**Validates: Requirements 14.8**

### Cross-Platform Properties

**Property 43: Audio device detection across platforms**
*For any* supported platform (Windows or macOS), the audio pipeline should detect and use system audio devices.
**Validates: Requirements 15.5**

**Property 44: Graceful degradation**
*For any* platform-specific feature that is unavailable, the system should degrade gracefully without crashing.
**Validates: Requirements 15.7**

### Security Properties

**Property 45: Local model data privacy**
*For any* operation using local models, the system should not transmit audio data to external services.
**Validates: Requirements 19.2**

**Property 46: HTTPS for cloud APIs**
*For any* cloud LLM provider communication, the system should use HTTPS for all API calls.
**Validates: Requirements 19.3**

**Property 47: Sensitive action confirmation**
*For any* sensitive action (file deletion, system shutdown), the system should require user confirmation before execution.
**Validates: Requirements 19.6**

**Property 48: Rate limiting**
*For any* sequence of requests, the system should implement rate limiting to prevent abuse.
**Validates: Requirements 19.7**

**Property 49: Input validation**
*For any* user input, the system should validate it to prevent injection attacks.
**Validates: Requirements 19.8**

### Error Handling Properties

**Property 50: Microphone error recovery**
*For any* microphone unavailability, the system should display an error message and retry connection.
**Validates: Requirements 20.1**

**Property 51: OS action error reporting**
*For any* failed OS action, the system should report the error to the user via speech.
**Validates: Requirements 20.3**

**Property 52: Audio playback error handling**
*For any* audio playback failure, the system should log the error and continue operation without crashing.
**Validates: Requirements 20.4**

**Property 53: Exponential backoff for transient failures**
*For any* transient failure, the system should implement exponential backoff for retry attempts.
**Validates: Requirements 20.5**

**Property 54: Detailed error logging**
*For any* error condition, the system should provide detailed error messages in log files for debugging.
**Validates: Requirements 20.6**

**Property 55: Automatic recovery**
*For any* critical component failure, the system should attempt automatic recovery before reporting failure.
**Validates: Requirements 20.7**

**Property 56: Crash prevention**
*For any* user input or external service failure, the system should never crash.
**Validates: Requirements 20.8**

## Error Handling

### Error Categories

The system implements comprehensive error handling across four categories:

**1. Recoverable Errors**
- Audio device disconnection → Automatic reconnection with exponential backoff
- LLM provider unavailability → Fallback to alternative providers or rule-based responses
- Network timeouts → Retry with exponential backoff (max 3 attempts)
- Low confidence transcriptions → Request user clarification

**2. User-Reportable Errors**
- Permission denied for OS operations → Speech notification with guidance
- Application not found → Speech notification with suggestions
- Invalid command syntax → Speech notification with examples
- Microphone not available → Visual and speech notification with troubleshooting steps

**3. Critical Errors**
- Model loading failure → Display error dialog and exit gracefully
- Configuration file corruption → Reset to defaults and notify user
- Encryption key unavailable → Prompt for recovery or reset
- Memory allocation failure → Log error and attempt graceful shutdown

**4. Security Errors**
- Injection attack detected → Block input and log security event
- Rate limit exceeded → Temporary lockout with notification
- Unauthorized file access attempt → Block and log security event
- Invalid API credentials → Disable cloud providers and notify user

### Error Handling Strategies

**Graceful Degradation**:
- If Whisper STT fails, fall back to simpler audio analysis
- If TTS fails, display text response instead
- If wake word detection fails, provide manual activation button
- If LLM unavailable, use rule-based command processing

**User Communication**:
- All errors communicated via speech when possible
- Visual error messages for critical failures
- Detailed logs for debugging (stored in `.kiro/logs/`)
- User-friendly error messages without technical jargon

**Recovery Mechanisms**:
- Automatic reconnection for audio devices (exponential backoff: 1s, 2s, 4s, 8s)
- Provider failover for LLM (Ollama → OpenAI → Gemini → Rule-based)
- Model reload on corruption detection
- Configuration reset on validation failure

**Logging and Monitoring**:
- All errors logged with timestamp, component, and context
- Performance metrics tracked for anomaly detection
- Security events logged separately for audit
- Log rotation to prevent disk space issues (max 100MB per log file)

## Testing Strategy

### Dual Testing Approach

The system requires both unit testing and property-based testing for comprehensive coverage:

**Unit Tests**: Verify specific examples, edge cases, and error conditions
**Property Tests**: Verify universal properties across all inputs

Together, these approaches provide comprehensive coverage where unit tests catch concrete bugs and property tests verify general correctness.

### Property-Based Testing Configuration

**Library Selection**:
- **Rust**: Use `proptest` crate (already in dev-dependencies)
- **Python**: Use `hypothesis` library
- **C++**: Use `RapidCheck` library

**Test Configuration**:
- Minimum 100 iterations per property test (due to randomization)
- Each property test must reference its design document property
- Tag format: `// Feature: agent-guru-production-engineering, Property N: [property text]`

**Property Test Implementation**:
- Each correctness property must be implemented by a SINGLE property-based test
- Tests should generate random valid inputs within the domain
- Tests should verify the property holds for all generated inputs
- Tests should report counterexamples when properties fail

### Unit Testing Strategy

**Focus Areas for Unit Tests**:
- Specific command examples (e.g., "Open YouTube", "What is the time")
- Edge cases (empty audio, very long text, special characters)
- Error conditions (device unavailable, permission denied)
- Integration points between components
- Platform-specific behavior verification

**Coverage Goals**:
- Rust modules: 80% code coverage minimum
- Python modules: 80% code coverage minimum
- Critical paths: 100% code coverage (wake word, STT, intent parsing)

### Integration Testing

**End-to-End Workflows**:
1. Wake word → STT → Intent → OS Action → Feedback
2. Wake word → STT → Intent → LLM → TTS → Playback
3. Error scenarios → Recovery → Retry → Success
4. Provider switching → Context preservation → Response generation

**Platform-Specific Testing**:
- Windows: Test with Windows 10, 11
- macOS: Test with macOS 11, 12, 13, 14
- Audio devices: Test with multiple microphone/speaker configurations
- Permissions: Test with various permission states

### Performance Testing

**Latency Benchmarks**:
- Wake word detection: ≤50ms (99th percentile)
- STT processing: ≤120ms per second of audio
- Intent classification: ≤50ms
- LLM first token: ≤300ms
- TTS synthesis: ≤200ms
- End-to-end simple command: ≤1 second

**Resource Benchmarks**:
- Idle CPU usage: <10%
- Active CPU usage: <20%
- Memory usage: <500MB
- Startup time: <5 seconds

**Stress Testing**:
- Continuous operation for 24 hours
- 1000 consecutive commands without restart
- Rapid wake word triggers (10 per second)
- Large conversation history (1000+ turns)

### Test Automation

**Continuous Integration**:
- Run all tests on every commit
- Platform-specific tests on respective CI runners
- Performance regression detection
- Code coverage reporting

**Test Organization**:
```
tests/
├── unit/
│   ├── rust/
│   ├── python/
│   └── cpp/
├── property/
│   ├── wake_word_properties.rs
│   ├── stt_properties.rs
│   ├── intent_properties.py
│   └── memory_properties.rs
├── integration/
│   ├── voice_pipeline_tests.rs
│   ├── os_control_tests.rs
│   └── llm_integration_tests.rs
└── performance/
    ├── latency_benchmarks.rs
    └── resource_benchmarks.rs
```

### Example Property Test

```rust
// Feature: agent-guru-production-engineering, Property 1: Wake word detection latency
#[cfg(test)]
mod wake_word_properties {
    use proptest::prelude::*;
    use std::time::Instant;
    
    proptest! {
        #[test]
        fn wake_word_detection_latency(
            wake_word in prop::sample::select(vec!["guru", "maya"]),
            noise_level in 0.0f32..0.5f32
        ) {
            let mut engine = MFCCWakeWordEngine::new();
            engine.initialize(&[wake_word.clone()]).unwrap();
            
            // Generate audio with wake word
            let audio = generate_wake_word_audio(&wake_word, noise_level);
            
            // Measure detection latency
            let start = Instant::now();
            let result = engine.process_audio_stream(&audio).unwrap();
            let latency = start.elapsed();
            
            // Property: Detection should occur within 50ms
            if let Some(event) = result {
                prop_assert!(latency.as_millis() <= 50, 
                    "Wake word detection took {}ms, expected ≤50ms", 
                    latency.as_millis());
            }
        }
    }
}
```

### Test Execution

**Development Workflow**:
1. Run unit tests during development: `cargo test --lib`
2. Run property tests before commit: `cargo test --release`
3. Run integration tests before PR: `cargo test --test integration`
4. Run performance tests weekly: `cargo bench`

**CI/CD Pipeline**:
1. Lint and format checks
2. Unit tests (parallel execution)
3. Property tests (100 iterations minimum)
4. Integration tests (sequential execution)
5. Performance regression tests
6. Code coverage report generation
7. Security audit (cargo audit, safety)

This comprehensive testing strategy ensures the AGENT_GURU system meets all correctness properties, performance requirements, and quality standards for production deployment.

## Deployment Architecture

### Installer Design

The production deployment delivers native installers for Windows and macOS, bundling all required components (models, libraries, binaries) into a single distributable package.

**Windows Installer (MSI via WiX Toolset)**:
```
AgentGuru-Setup-{version}-x64.msi
├── guru.exe                    # Main Rust binary
├── models/
│   ├── whisper-base.bin        # STT model (~140MB)
│   ├── wake_word.onnx          # Wake word model (~5MB)
│   └── piper-voice.onnx        # TTS voice model (~60MB)
├── lib/
│   ├── whisper.dll             # Whisper C++ runtime
│   ├── onnxruntime.dll         # ONNX inference runtime
│   └── python312.dll           # Python runtime
├── python/                     # Python intelligence layer
│   ├── site-packages/          # All Python dependencies
│   └── agent_guru/             # Agent Guru Python modules
└── config/
    └── default_config.toml     # Default configuration
```

**macOS Installer (DMG with App Bundle)**:
```
AgentGuru-{version}-macOS.dmg
└── AgentGuru.app/
    └── Contents/
        ├── MacOS/
        │   └── guru             # Main Rust binary (universal binary: x86_64 + arm64)
        ├── Resources/
        │   ├── models/          # Same model files as Windows
        │   └── python/          # Python runtime and packages
        ├── Frameworks/
        │   ├── libwhisper.dylib
        │   └── libonnxruntime.dylib
        └── Info.plist           # App metadata
```

### Packaging Strategy

**Model Bundling**:
- Whisper base model (~140MB) bundled in installer — no download required
- Wake word ONNX model (~5MB) bundled
- Piper TTS voice model (~60MB) bundled
- Total installer size target: <400MB

**Dependency Isolation**:
- Python runtime embedded (no system Python required)
- All native libraries bundled (no system library conflicts)
- Self-contained: works on clean OS install with no prerequisites

**Version Management**:
```toml
# Embedded in binary at build time
[build_info]
version = "1.0.0"
build_date = "2025-01-01"
git_commit = "abc1234"
rust_version = "1.75.0"
python_version = "3.12.0"
whisper_model = "base"
```

### Installation Flow

**Windows Installation Sequence**:
1. Verify OS version (Windows 10 1903+ or Windows 11)
2. Check available disk space (minimum 1GB)
3. Extract all files to `%ProgramFiles%\AgentGuru\`
4. Register application in Windows registry
5. Create desktop shortcut and Start Menu entry
6. Register autostart entry (optional, user choice)
7. Run first-launch setup wizard
8. Verify microphone permissions

**macOS Installation Sequence**:
1. Verify macOS version (11.0+)
2. Mount DMG and copy app bundle to `/Applications/`
3. Verify code signature (Gatekeeper compatibility)
4. On first launch: request microphone and accessibility permissions
5. Run first-launch setup wizard
6. Optionally add to Login Items

**First-Launch Setup Wizard**:
```
Step 1: Welcome screen (product overview)
Step 2: Microphone permission request + test
Step 3: LLM provider selection (Ollama local / Cloud API)
Step 4: API key entry (if cloud selected)
Step 5: Wake word selection ("Hey Guru" / "Hey Maya")
Step 6: Voice test (say wake word to verify)
Step 7: Ready screen with quick-start guide
```

### Update Mechanism

**Auto-Update Strategy**:
- Check for updates on startup (background, non-blocking)
- Download update package in background
- Prompt user to install when ready
- Support silent update for minor versions
- Require user confirmation for major versions

**Update Package Structure**:
- Delta updates for model files (only changed bytes)
- Full binary replacement for Rust/Python components
- Configuration migration scripts for breaking changes
- Rollback support: keep previous version for 7 days

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| OS (Windows) | Windows 10 1903 | Windows 11 |
| OS (macOS) | macOS 11.0 | macOS 13+ |
| RAM | 4GB | 8GB+ |
| Disk Space | 1GB | 2GB+ |
| CPU | x86_64 (any) | Modern multi-core |
| Microphone | Any USB/built-in | Noise-canceling |
| Internet | Optional (local LLM) | Required (cloud LLM) |

## CI/CD Pipeline Design

### Pipeline Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Developer Workflow                        │
│  git push → GitHub Actions → Build → Test → Package → Release│
└─────────────────────────────────────────────────────────────┘

Stages:
1. Lint & Format    (parallel, ~2 min)
2. Build            (parallel per platform, ~10 min)
3. Unit Tests       (parallel, ~5 min)
4. Property Tests   (parallel, ~15 min)
5. Integration Tests(sequential, ~20 min)
6. Performance Tests(weekly only, ~30 min)
7. Security Audit   (parallel, ~5 min)
8. Package          (on main branch only, ~15 min)
9. Release          (manual trigger, ~5 min)
```

### GitHub Actions Workflow

**Trigger Conditions**:
- `push` to any branch → Stages 1-4 (fast feedback)
- `pull_request` to `main` → Stages 1-7 (full validation)
- `push` to `main` → Stages 1-8 (build packages)
- Manual trigger → Stage 9 (release)
- Weekly schedule → Stage 6 (performance regression)

**Stage 1: Lint and Format**
```yaml
# Runs in parallel across languages
jobs:
  rust-lint:
    - cargo fmt --check
    - cargo clippy --all-features -- -D warnings
    - cargo audit
  
  python-lint:
    - black --check Agent_Guru/
    - ruff check Agent_Guru/
    - mypy Agent_Guru/ --strict
    - bandit -r Agent_Guru/
```

**Stage 2: Build**
```yaml
# Cross-platform build matrix
strategy:
  matrix:
    os: [windows-latest, macos-latest]
    
steps:
  - cargo build --release --all-features
  - Verify zero warnings (RUSTFLAGS="-D warnings")
  - Build Python wheel
  - Verify all imports succeed
```

**Stage 3: Unit Tests**
```yaml
# Fast unit tests with coverage
- cargo test --lib --release
- pytest Agent_Guru/ -m unit --cov=Agent_Guru --cov-report=xml
- Enforce 80% minimum coverage
- Upload coverage to Codecov
```

**Stage 4: Property Tests**
```yaml
# Property-based tests (100 iterations minimum)
- cargo test --release -- --test-threads=4
- pytest Agent_Guru/ -m property --hypothesis-seed=0
- Minimum 100 examples per property
- Fail on any counterexample found
```

**Stage 5: Integration Tests**
```yaml
# End-to-end pipeline tests (sequential)
- cargo test --test integration --release
- pytest Agent_Guru/ -m integration
- Test voice pipeline with mock audio
- Test OS control with sandboxed environment
```

**Stage 6: Performance Tests (Weekly)**
```yaml
# Regression detection against baseline
- cargo bench --bench latency_benchmarks
- pytest Agent_Guru/ -m performance
- Compare against stored baseline
- Fail if any metric regresses >10%
- Update baseline on main branch
```

**Stage 7: Security Audit**
```yaml
# Automated security scanning
- cargo audit --deny warnings
- safety check -r requirements.txt
- bandit -r Agent_Guru/ -ll  # High severity only
- trivy fs . --severity HIGH,CRITICAL
```

**Stage 8: Package (main branch only)**
```yaml
# Build production installers
windows:
  - cargo build --release --target x86_64-pc-windows-msvc
  - Bundle models and Python runtime
  - Build MSI with WiX Toolset
  - Sign with code signing certificate
  - Upload artifact: AgentGuru-{version}-x64.msi

macos:
  - cargo build --release --target universal-apple-darwin
  - Bundle models and Python runtime
  - Build app bundle and DMG
  - Sign and notarize with Apple Developer ID
  - Upload artifact: AgentGuru-{version}-macOS.dmg
```

**Stage 9: Release (manual trigger)**
```yaml
# Publish release
- Download installer artifacts from Stage 8
- Create GitHub Release with changelog
- Upload installers as release assets
- Publish release notes
- Notify team via Slack/email
```

### Quality Gates

Every stage must pass before proceeding to the next. The following gates are enforced:

| Gate | Threshold | Action on Failure |
|------|-----------|-------------------|
| Rust compilation | Zero warnings | Block PR merge |
| Python type checking | Zero mypy errors | Block PR merge |
| Unit test coverage | ≥80% | Block PR merge |
| Property test iterations | ≥100 per property | Block PR merge |
| Security audit | Zero high/critical | Block PR merge |
| Performance regression | ≤10% degradation | Alert + block release |
| Code duplication | <3% | Warning (non-blocking) |

### Branch Strategy

```
main          ← Production-ready code, triggers package builds
  └── develop ← Integration branch, full test suite
        ├── feature/wake-word-optimization
        ├── feature/llm-provider-gemini
        └── fix/audio-device-reconnection
```

**Merge Requirements for `main`**:
- All CI stages pass (1-7)
- Two reviewer approvals
- No unresolved review comments
- Branch up-to-date with main

### Artifact Management

**Build Artifacts** (retained 30 days):
- `AgentGuru-{version}-{commit}-x64.msi` — Windows installer
- `AgentGuru-{version}-{commit}-macOS.dmg` — macOS installer
- `coverage-report-{commit}.xml` — Test coverage
- `benchmark-results-{commit}.json` — Performance baseline

**Release Artifacts** (retained indefinitely):
- Tagged release installers (MSI + DMG)
- SHA256 checksums for all installers
- Release notes and changelog
- Source code archive (zip + tar.gz)

### Monitoring and Alerting

**CI Health Metrics**:
- Build success rate (target: >95%)
- Average build duration (target: <30 min total)
- Test flakiness rate (target: <1%)
- Security vulnerability count (target: 0 high/critical)

**Alerts**:
- Build failure on `main` → Immediate Slack notification
- Performance regression detected → Email to team lead
- Security vulnerability found → Immediate email + Slack
- Coverage drops below 80% → PR blocked + notification
