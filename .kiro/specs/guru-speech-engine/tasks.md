# Implementation Plan: Guru Speech Engine

## Overview

This implementation plan breaks down the Guru Speech Engine into discrete coding tasks for implementing a voice-controlled AI assistant with dual personalities (Guru - male, Maya - female). Each task includes test requirements and must be pushed to GitHub upon completion.

**Key Features**:
- Dual wake word detection ("Hey Guru" / "Hey Maya")
- Gender-specific text-to-speech (male/female voices)
- Voice biometric authentication
- Complete laptop control through voice commands
- Multi-language support (English, Hindi, Punjabi)

## Task Completion Protocol

After completing EACH task:
1. ✅ Run all tests for that task
2. ✅ Verify all tests pass
3. ✅ Commit changes with descriptive message
4. ✅ Push to GitHub immediately
5. ✅ Mark task as complete in this file

## Tasks

### Phase 1: Project Setup and Core Infrastructure

- [ ] **Task 1: Project Structure and Dependencies**
  - Create `guru_speech/` package directory structure
  - Create `__init__.py`, `models.py`, `exceptions.py`, `config.py`
  - Create `requirements.txt` with dependencies:
    - faster-whisper (STT)
    - noisereduce (audio processing)
    - sounddevice, soundfile (audio I/O)
    - pyttsx3 or TTS library (text-to-speech)
    - numpy, scipy (audio processing)
    - hypothesis, pytest, pytest-cov (testing)
  - Create `model/` directory for model files
  - Create `tests/` directory structure
  - _Requirements: Req 1 (Dual Wake Word), Req 4 (Gender TTS)_
  - **Tests Required**: None (setup task)
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 2: Data Models and Configuration**
  - Implement data models in `models.py`:
    - `PersonalityType` enum (GURU, MAYA)
    - `WakeWordDetection` dataclass (wake_word, personality, confidence, timestamp)
    - `TranscriptionResult` dataclass (text, language, confidence, segments, duration)
    - `VoiceFeatures` dataclass (feature_vector, sample_rate, duration, quality_score)
    - `TTSConfig` dataclass (voice_gender, rate, pitch, volume)
    - `CommandResult` dataclass (action_id, parameters, raw_text, confidence)
  - Implement exceptions in `exceptions.py`:
    - `GuruSpeechError` (base exception)
    - `AudioCaptureError`, `ModelLoadError`, `TranscriptionError`
    - `WakeWordError`, `TTSError`, `BiometricError`
  - Implement configuration in `config.py`:
    - `SpeechEngineConfig` with all component settings
    - Default configurations for Guru and Maya personalities
  - _Requirements: Req 1, 2, 3, 4_
  - **Tests Required**:
    - Unit tests for dataclass validation
    - Unit tests for exception formatting
    - Unit tests for configuration loading
  - **GitHub Push**: ✅ Required after completion

### Phase 2: Audio Processing and Wake Word Detection

- [ ] **Task 3: Audio Input and Processing**
  - Implement `audio_processor.py`:
    - `AudioProcessor` class with VAD, noise reduction, AGC
    - `process_chunk()` method for real-time processing
    - `detect_voice_activity()` method
    - `reduce_noise()` method using noisereduce
  - Implement `capture.py`:
    - `AudioCapture` base class
    - `MicrophoneCapture` class using sounddevice
    - `FileCapture` class using soundfile
  - _Requirements: Req 5 (Audio Processing)_
  - **Tests Required**:
    - Unit tests for noise reduction with sample audio
    - Unit tests for VAD with speech/silence samples
    - Property tests for audio format compatibility
    - Unit tests for microphone/file capture
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 4: Dual Wake Word Detection**
  - Implement `wake_word.py`:
    - `WakeWordDetector` class
    - Support for "Hey Guru" and "Hey Maya" detection
    - `detect()` method returning personality identifier
    - Configurable sensitivity per wake word
    - MFCC-based feature extraction
  - Train or integrate wake word models for both personalities
  - _Requirements: Req 1 (Dual Personality Wake Word Detection)_
  - **Tests Required**:
    - Unit tests for "Hey Guru" detection
    - Unit tests for "Hey Maya" detection
    - Unit tests for false positive rate (<1/hour)
    - Property tests for detection latency (<200ms)
    - Unit tests for personality identification accuracy
  - **GitHub Push**: ✅ Required after completion

### Phase 3: Speech-to-Text and Voice Biometrics

- [ ] **Task 5: Whisper STT Integration**
  - Implement `speech.py`:
    - `WhisperTranscriber` class using faster-whisper
    - `transcribe()` method for numpy arrays
    - `transcribe_file()` method for files
    - Support for English, Hindi, Punjabi
    - Real-time factor <0.5
  - _Requirements: Req 2 (Speech-to-Text Transcription)_
  - **Tests Required**:
    - Unit tests with English audio samples
    - Unit tests with Hindi audio samples
    - Unit tests with Punjabi audio samples
    - Property tests for transcription completeness
    - Performance tests for real-time factor
    - Unit tests for multi-language detection
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 6: Voice Biometric Feature Extraction**
  - Implement `biometric.py`:
    - `VoiceFeatureExtractor` class
    - `extract_features()` method for biometric features
    - `compute_quality_score()` method
    - Integration interface for guru-security-cryptography
    - Liveness detection (anti-spoofing)
  - _Requirements: Req 3 (Voice Biometrics)_
  - **Tests Required**:
    - Unit tests for feature extraction
    - Unit tests for quality scoring
    - Unit tests for liveness detection
    - Property tests for feature vector consistency
    - Unit tests for recorded/synthesized voice rejection
  - **GitHub Push**: ✅ Required after completion

### Phase 4: Text-to-Speech with Gender Support

- [ ] **Task 7: Gender-Specific TTS Engine**
  - Implement `tts.py`:
    - `TTSEngine` class
    - `synthesize()` method with gender parameter
    - Male voice configuration for Guru personality
    - Female voice configuration for Maya personality
    - Support for emotion and tone control
    - SSML markup support
    - Real-time factor <0.3
  - Integrate TTS library (pyttsx3, gTTS, or ElevenLabs)
  - _Requirements: Req 4 (Gender-Specific TTS)_
  - **Tests Required**:
    - Unit tests for male voice synthesis (Guru)
    - Unit tests for female voice synthesis (Maya)
    - Unit tests for emotion control
    - Property tests for synthesis latency
    - Unit tests for SSML markup handling
    - Unit tests for speech rate/pitch adjustment
  - **GitHub Push**: ✅ Required after completion

### Phase 5: Command Recognition and Integration

- [ ] **Task 8: Command Interpretation**
  - Implement `commands.py`:
    - `CommandInterpreter` class
    - `interpret()` method with pattern matching
    - `register_command()` for custom commands
    - Default command registry for laptop control:
      - Open applications (YouTube, Notepad, WhatsApp, etc.)
      - Type text
      - Send messages
      - Control system settings
      - File operations
      - Mouse/keyboard control
    - Multi-language pattern support
    - Fuzzy matching for command detection
  - _Requirements: Req 6 (Command Recognition), Platform Integration_
  - **Tests Required**:
    - Unit tests for all default commands
    - Unit tests for multi-language patterns
    - Property tests for command pattern matching
    - Unit tests for parameter extraction
    - Unit tests for unrecognized text passthrough
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 9: Main Speech Engine Facade**
  - Implement `engine.py`:
    - `GuruSpeechEngine` class (main facade)
    - `initialize()` method loading all components
    - `process_voice_input()` end-to-end pipeline
    - `transcribe_with_personality()` method
    - `synthesize_response()` with personality voice
    - `extract_voice_features()` for authentication
    - Pipeline: capture → process → wake word → STT → interpret
    - Error handling with context preservation
    - Logging at INFO level
  - _Requirements: All speech engine requirements_
  - **Tests Required**:
    - Integration tests for end-to-end pipeline
    - Unit tests for personality switching
    - Property tests for error context preservation
    - Property tests for model reuse across requests
    - Performance tests for pipeline latency
  - **GitHub Push**: ✅ Required after completion

### Phase 6: Advanced Features and Optimization

- [ ] **Task 10: Streaming and Async Support**
  - Add streaming transcription support
  - Implement async versions of all methods:
    - `transcribe_async()`
    - `synthesize_async()`
    - `process_voice_input_async()`
  - Add concurrent request handling
  - _Requirements: Req 7 (Streaming), Async Operations_
  - **Tests Required**:
    - Unit tests for streaming transcription
    - Unit tests for async methods
    - Property tests for concurrent requests
    - Performance tests for async throughput
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 11: Voice Activity Detection and Optimization**
  - Implement advanced VAD with configurable aggressiveness
  - Add audio preprocessing optimization
  - Implement model caching and warm-up
  - Add performance monitoring and metrics
  - _Requirements: Req 5 (Audio Processing), Performance_
  - **Tests Required**:
    - Unit tests for VAD accuracy
    - Performance tests for processing latency
    - Unit tests for model caching
    - Property tests for resource usage
  - **GitHub Push**: ✅ Required after completion

### Phase 7: Testing, Documentation, and Examples

- [ ] **Task 12: Comprehensive Test Suite**
  - Implement all property-based tests (100+ iterations each)
  - Implement all unit tests for edge cases
  - Add integration tests for all workflows
  - Add performance regression tests
  - Achieve minimum 80% code coverage
  - _Requirements: All testing requirements_
  - **Tests Required**:
    - All property tests passing
    - All unit tests passing
    - Coverage report >80%
    - Performance benchmarks documented
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 13: Example Scripts and Documentation**
  - Create example scripts:
    - `example_basic.py` - Simple transcription
    - `example_dual_personality.py` - Guru and Maya interaction
    - `example_voice_commands.py` - Laptop control commands
    - `example_biometric_auth.py` - Voice authentication
    - `example_custom_commands.py` - Custom command registration
  - Create comprehensive README.md:
    - Installation instructions
    - Quick start guide
    - API documentation
    - Configuration guide
    - Multi-language support guide
    - Troubleshooting guide
  - _Requirements: Documentation requirements_
  - **Tests Required**: None (documentation task)
  - **GitHub Push**: ✅ Required after completion

### Phase 8: Integration with Other Components

- [ ] **Task 14: Security System Integration**
  - Integrate with guru-security-cryptography for voice authentication
  - Implement secure voice profile storage
  - Add biometric enrollment workflow
  - Test end-to-end authentication flow
  - _Requirements: Biometric Consolidation requirements_
  - **Tests Required**:
    - Integration tests with security system
    - Unit tests for voice profile management
    - Unit tests for enrollment workflow
  - **GitHub Push**: ✅ Required after completion

- [ ] **Task 15: Avatar System Integration**
  - Integrate with guru-avatar for lip sync
  - Provide audio timing information for lip sync
  - Coordinate personality switching with avatar
  - _Requirements: Avatar integration requirements_
  - **Tests Required**:
    - Integration tests with avatar system
    - Unit tests for lip sync timing
    - Unit tests for personality coordination
  - **GitHub Push**: ✅ Required after completion

## Testing Summary

### Property-Based Tests (Hypothesis)
- Transcription result completeness
- Audio format compatibility
- Command pattern matching
- Error context preservation
- Model reuse across requests
- Concurrent request handling
- Voice feature consistency

### Unit Tests
- All component initialization
- All public methods
- Error handling for all failure modes
- Multi-language support
- Gender-specific TTS
- Dual wake word detection
- Command interpretation

### Integration Tests
- End-to-end voice pipeline
- Personality switching
- Security system integration
- Avatar system integration
- Performance benchmarks

### Coverage Goals
- Minimum 80% line coverage
- All 7+ correctness properties tested
- All error paths tested
- All language variants tested

## Notes

- Each task must be completed, tested, and pushed to GitHub before moving to the next
- Property tests must run minimum 100 iterations
- All tests must pass before marking task complete
- Integration tasks require coordination with other component teams
- Performance tests must meet specified latency targets
- Multi-language support must be tested with actual audio samples

## Dependencies

This component depends on:
- guru-security-cryptography (for voice authentication)
- guru-avatar (for lip sync coordination)
- guru-platform (for system command execution)

This component is used by:
- Main AGENT_GURU application
- Onboarding system (for voice enrollment)
- Authentication system (for voice verification)
