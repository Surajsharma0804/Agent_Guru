# AGENT_GURU Terminology Glossary

## Purpose
This glossary defines standard terminology used throughout the AGENT_GURU codebase to ensure consistency and clarity across all modules, documentation, and comments.

## Core System Terms

### STT (Speech-to-Text)
**Standard Term:** STT, Speech-to-Text, Transcription
**Definition:** The process of converting spoken audio into written text
**Usage:** Use "STT" in code identifiers, "Speech-to-Text" in documentation
**Examples:**
- `STT_Engine`, `stt_processing`, `transcribe()`
- "The STT engine processes audio at 16kHz"

### TTS (Text-to-Speech)
**Standard Term:** TTS, Text-to-Speech, Synthesis
**Definition:** The process of converting written text into spoken audio
**Usage:** Use "TTS" in code identifiers, "Text-to-Speech" in documentation
**Examples:**
- `TTS_Engine`, `tts_synthesis`, `synthesize()`
- "The TTS engine generates natural-sounding speech"

### LLM (Large Language Model)
**Standard Term:** LLM, Language Model
**Definition:** AI model for natural language understanding and generation
**Usage:** Use "LLM" in code identifiers, "Large Language Model" in documentation
**Examples:**
- `LLM_Provider`, `llm_response`, `generate_response()`
- "The LLM provider manages multiple model backends"

### Wake Word
**Standard Term:** Wake Word, Activation Phrase
**Definition:** Spoken phrase that activates the voice assistant
**Usage:** Use "wake_word" in code, "wake word" in documentation
**Examples:**
- `wake_word_detection`, `WakeWordEngine`, `detect_wake_word()`
- "The wake word engine monitors for 'Hey Guru' or 'Hey Maya'"

### Voice Pipeline
**Standard Term:** Voice Pipeline, Audio Pipeline
**Definition:** End-to-end flow from audio input to speech output
**Usage:** Use "voice_pipeline" or "audio_pipeline" consistently
**Examples:**
- `voice_pipeline_manager`, `AudioPipeline`, `process_audio()`
- "The voice pipeline handles wake word → STT → LLM → TTS"

## Audio Processing Terms

### Audio Buffer
**Standard Term:** Audio Buffer
**Definition:** Temporary storage for audio samples
**Usage:** Use "audio_buffer" in code
**Examples:**
- `AudioBuffer`, `audio_buffer_size`, `buffer_audio()`

### Sample Rate
**Standard Term:** Sample Rate
**Definition:** Number of audio samples per second (Hz)
**Usage:** Use "sample_rate" in code, always specify units
**Examples:**
- `sample_rate: u32`, `SAMPLE_RATE_HZ = 16000`
- "Audio captured at 16kHz sample rate"

### Ring Buffer
**Standard Term:** Ring Buffer, Circular Buffer
**Definition:** Fixed-size buffer that overwrites oldest data
**Usage:** Use "ring_buffer" in code
**Examples:**
- `RingBuffer<f32>`, `ring_buffer_capacity`, `push_to_ring_buffer()`

## Intent and Command Terms

### Intent
**Standard Term:** Intent
**Definition:** User's goal or purpose extracted from input
**Usage:** Use "intent" in code
**Examples:**
- `Intent`, `intent_type`, `parse_intent()`
- "The intent parser classifies user requests"

### Intent Type
**Standard Term:** Intent Type, Intent Category
**Definition:** Classification of user intent
**Usage:** Use "intent_type" in code
**Examples:**
- `IntentType`, `OPEN_APPLICATION`, `QUERY_INFORMATION`

### Command Pattern
**Standard Term:** Command Pattern
**Definition:** Regex pattern for matching user commands
**Usage:** Use "command_pattern" in code
**Examples:**
- `CommandPattern`, `register_command_pattern()`

### Action Executor
**Standard Term:** Action Executor, OS Controller
**Definition:** Component that executes system-level operations
**Usage:** Use "action_executor" or "os_controller" consistently
**Examples:**
- `ActionExecutor`, `OSController`, `execute_action()`

## Memory and Context Terms

### Conversation Memory
**Standard Term:** Conversation Memory, Memory System
**Definition:** Storage and retrieval of conversation history
**Usage:** Use "conversation_memory" or "memory_system"
**Examples:**
- `ConversationMemory`, `MemorySystem`, `store_message()`

### Context
**Standard Term:** Context, Conversation Context
**Definition:** Historical information for contextual understanding
**Usage:** Use "context" in code
**Examples:**
- `context`, `conversation_context`, `get_context()`

### LRU (Least Recently Used)
**Standard Term:** LRU, Least Recently Used
**Definition:** Eviction strategy that removes oldest unused items
**Usage:** Use "LRU" in code and documentation
**Examples:**
- `lru_eviction`, `LRU_CACHE_SIZE`, `evict_lru()`

## Platform and OS Terms

### OS Controller
**Standard Term:** OS Controller, Platform Controller
**Definition:** Platform-specific system control interface
**Usage:** Use "os_controller" in code
**Examples:**
- `OSController`, `WindowsController`, `MacOSController`

### Platform
**Standard Term:** Platform, Operating System
**Definition:** Target operating system (Windows, macOS, Linux)
**Usage:** Use "platform" in code
**Examples:**
- `Platform`, `detect_platform()`, `platform_specific`

## Performance and Metrics Terms

### Latency
**Standard Term:** Latency, Response Time
**Definition:** Time delay between input and output
**Usage:** Use "latency" for delays, "response_time" for full duration
**Examples:**
- `detection_latency_ms`, `response_time`, `measure_latency()`

### Throughput
**Standard Term:** Throughput, Requests Per Second
**Definition:** Number of operations processed per unit time
**Usage:** Use "throughput" or "requests_per_second"
**Examples:**
- `throughput`, `requests_per_second`, `measure_throughput()`

### Metrics
**Standard Term:** Metrics, Performance Metrics
**Definition:** Quantitative measurements of system performance
**Usage:** Use "metrics" in code
**Examples:**
- `Metrics`, `performance_metrics`, `collect_metrics()`

## Security and Privacy Terms

### Encryption
**Standard Term:** Encryption
**Definition:** Process of encoding data for security
**Usage:** Use "encryption" in code
**Examples:**
- `encryption_key`, `encrypt_data()`, `EncryptionConfig`

### AES-256-GCM
**Standard Term:** AES-256-GCM
**Definition:** Advanced Encryption Standard with 256-bit key and GCM mode
**Usage:** Use full term in documentation, "aes_gcm" in code
**Examples:**
- `aes_gcm_encrypt()`, "Data encrypted using AES-256-GCM"

### Audit Log
**Standard Term:** Audit Log, Security Log
**Definition:** Immutable record of security-relevant events
**Usage:** Use "audit_log" in code
**Examples:**
- `audit_log`, `AuditLogger`, `log_security_event()`

## Model and AI Terms

### Model
**Standard Term:** Model, AI Model
**Definition:** Trained machine learning model
**Usage:** Use "model" in code
**Examples:**
- `model`, `load_model()`, `ModelConfig`

### Inference
**Standard Term:** Inference, Prediction
**Definition:** Process of using a model to make predictions
**Usage:** Use "inference" for ML operations
**Examples:**
- `run_inference()`, `inference_time`, `InferenceEngine`

### Embedding
**Standard Term:** Embedding, Vector Embedding
**Definition:** Numerical vector representation of data
**Usage:** Use "embedding" in code
**Examples:**
- `embedding`, `generate_embedding()`, `embedding_dimension`

## Configuration Terms

### Config
**Standard Term:** Config, Configuration
**Definition:** System settings and parameters
**Usage:** Use "config" in code, "configuration" in documentation
**Examples:**
- `Config`, `VoiceConfig`, `load_config()`

### Provider
**Standard Term:** Provider
**Definition:** Backend service or implementation
**Usage:** Use "provider" in code
**Examples:**
- `Provider`, `LLMProvider`, `OllamaProvider`

## Error Handling Terms

### Error
**Standard Term:** Error
**Definition:** Unexpected condition or failure
**Usage:** Use "error" in code
**Examples:**
- `Error`, `VoiceError`, `handle_error()`

### Result
**Standard Term:** Result
**Definition:** Return type that can be success or error
**Usage:** Use `Result<T, E>` in Rust
**Examples:**
- `Result<(), Error>`, `Result<String, VoiceError>`

## Abbreviations and Acronyms

### Widely-Recognized Abbreviations (ALLOWED)
- **STT**: Speech-to-Text
- **TTS**: Text-to-Speech
- **LLM**: Large Language Model
- **OS**: Operating System
- **API**: Application Programming Interface
- **CPU**: Central Processing Unit
- **GPU**: Graphics Processing Unit
- **RAM**: Random Access Memory
- **LRU**: Least Recently Used
- **AES**: Advanced Encryption Standard
- **GCM**: Galois/Counter Mode
- **VAD**: Voice Activity Detection
- **MFCC**: Mel-Frequency Cepstral Coefficients
- **OCR**: Optical Character Recognition
- **UI**: User Interface
- **URL**: Uniform Resource Locator
- **JSON**: JavaScript Object Notation
- **YAML**: YAML Ain't Markup Language
- **UUID**: Universally Unique Identifier

### Avoid These Abbreviations (USE FULL TERMS)
- ❌ "msg" → ✅ "message"
- ❌ "cfg" → ✅ "config"
- ❌ "ctx" → ✅ "context"
- ❌ "req" → ✅ "request"
- ❌ "res" → ✅ "response"
- ❌ "auth" → ✅ "authentication" (except in well-known contexts like OAuth)
- ❌ "proc" → ✅ "process"
- ❌ "mgr" → ✅ "manager"
- ❌ "svc" → ✅ "service"

## Naming Patterns

### Module Names
- Use descriptive, full words
- Separate words with underscores in file names
- Examples: `speech_recognition.rs`, `memory_system.rs`, `platform_controller.rs`

### Function Names
- Use verb phrases that describe the action
- Examples: `process_audio()`, `detect_wake_word()`, `generate_response()`

### Struct/Class Names
- Use noun phrases that describe the entity
- Examples: `AudioBuffer`, `WakeWordEngine`, `ConversationMemory`

### Constant Names
- Use SCREAMING_SNAKE_CASE
- Examples: `MAX_BUFFER_SIZE`, `DEFAULT_SAMPLE_RATE`, `ENCRYPTION_KEY_LENGTH`

## Comments and Documentation

### When to Add Comments
1. **Non-obvious naming choices**: Explain why a particular name was chosen if it's not immediately clear
2. **Domain-specific terms**: Define specialized terminology on first use
3. **Complex algorithms**: Explain the approach and reasoning
4. **Performance considerations**: Document optimization decisions
5. **Security implications**: Highlight security-relevant code

### Comment Format
```rust
// Single-line comment for brief explanations

/// Documentation comment for public APIs
/// Explains what the function does, parameters, and return values

/* Multi-line comment for longer explanations
   that span multiple lines */
```

## Consistency Checklist

When adding new code, ensure:
- [ ] Terms match this glossary
- [ ] Abbreviations are from the allowed list
- [ ] Naming follows established patterns
- [ ] Comments explain non-obvious choices
- [ ] Documentation uses full terms, not abbreviations
- [ ] Similar concepts use consistent terminology

## Glossary Maintenance

This glossary should be updated when:
1. New major features are added
2. New domain-specific terms are introduced
3. Naming inconsistencies are discovered
4. Team consensus changes on terminology

**Last Updated:** February 14, 2026
**Version:** 1.0.0
