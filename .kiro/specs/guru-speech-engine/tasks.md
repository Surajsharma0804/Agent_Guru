# Implementation Plan: Guru Speech Engine

## Overview

This implementation plan breaks down the Guru Speech Engine into discrete coding tasks. The approach follows a bottom-up strategy: build core components first (noise reduction, transcription, command interpretation), then integrate them into the main facade, and finally add real-time audio capture capabilities.

## Tasks

- [x] 1. Set up project structure and dependencies
  - Create guru_speech package directory structure
  - Create __init__.py files for package initialization
  - Create requirements.txt with all dependencies (faster-whisper, noisereduce, sounddevice, soundfile, numpy, hypothesis, pytest)
  - Create model/ directory for model files
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 2. Implement data models and exceptions
  - [x] 2.1 Create data model classes in a models.py file
    - Implement TranscriptionResult dataclass with text, language, confidence, segments, duration
    - Implement TranscriptionSegment dataclass with text, start, end, confidence
    - Implement CommandResult dataclass with action_id, parameters, raw_text, confidence, language, is_command
    - Implement CommandPattern dataclass with patterns, action_id, description, languages, parameter_extractors
    - Implement ModelConfig, NoiseReductionConfig, AudioConfig dataclasses
    - _Requirements: 1.4, 4.2, 6.1, 6.2_
  
  - [x] 2.2 Create exception classes in exceptions.py
    - Implement GuruSpeechError base exception with component tracking and error context
    - Implement AudioCaptureError, ModelLoadError, TranscriptionError, CommandInterpretationError
    - _Requirements: 10.1, 10.4_

- [-] 3. Implement noise reduction module (noise.py)
  - [x] 3.1 Create NoiseCleaner class
    - Implement __init__ with stationary and prop_decrease parameters
    - Implement clean() method that applies noisereduce to numpy audio arrays
    - Implement clean_file() method for file-based noise reduction
    - Add error handling with GuruSpeechError wrapping
    - _Requirements: 2.1, 2.2, 2.4_
  
  - [x] 3.2 Write property test for noise cleaner format compatibility
    - **Property 2: Noise Cleaner Format Compatibility**
    - **Validates: Requirements 2.4**
  
  - [ ]* 3.3 Write unit tests for NoiseCleaner
    - Test clean() with various audio inputs
    - Test clean_file() with sample audio files
    - Test error handling for invalid inputs
    - _Requirements: 2.4_

- [ ] 4. Implement Whisper transcription module (speech.py)
  - [ ] 4.1 Create WhisperTranscriber class
    - Implement __init__ with model loading using faster-whisper
    - Configure model with int8 compute type and beam_size=5
    - Implement transcribe() method for numpy array input
    - Implement transcribe_file() method for file input
    - Add language detection and return TranscriptionResult
    - Add error handling with ModelLoadError and TranscriptionError
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 7.1_
  
  - [ ]* 4.2 Write property test for transcription result completeness
    - **Property 1: Transcription Result Completeness**
    - **Validates: Requirements 1.4, 7.1, 7.2**
  
  - [ ]* 4.3 Write unit tests for WhisperTranscriber
    - Test model initialization with int8 and beam_size=5
    - Test transcription with English audio sample
    - Test transcription with Hindi audio sample
    - Test transcription with Punjabi audio sample
    - Test file format support (WAV, MP3, FLAC)
    - Test model loading error handling
    - Test custom model path loading
    - _Requirements: 1.2, 1.3, 1.5, 6.1, 6.2, 6.3, 6.4, 7.3, 7.4, 7.5, 8.1, 8.4, 9.2_

- [ ] 5. Checkpoint - Ensure core transcription works
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement command interpretation module (commands.py)
  - [ ] 6.1 Create CommandInterpreter class
    - Implement __init__ with default command registry
    - Implement register_command() for adding new command patterns
    - Implement interpret() method with pattern matching logic
    - Implement get_registered_commands() to list all commands
    - Add support for multi-language patterns (English, Hindi, Punjabi)
    - Add fuzzy matching for command detection
    - Return CommandResult with action_id and parameters
    - _Requirements: 4.1, 4.2, 4.4, 4.5_
  
  - [ ] 6.2 Add default command registry
    - Register OPEN_YOUTUBE command with patterns in English, Hindi, Punjabi
    - Register SEARCH command with parameter extraction
    - Register PLAY_MUSIC command with multi-language patterns
    - _Requirements: 4.3_
  
  - [ ]* 6.3 Write property test for command pattern matching
    - **Property 3: Command Pattern Matching and Mapping**
    - **Validates: Requirements 4.1, 4.2**
  
  - [ ]* 6.4 Write property test for unrecognized text passthrough
    - **Property 4: Unrecognized Text Passthrough**
    - **Validates: Requirements 4.4**
  
  - [ ]* 6.5 Write property test for command result structure
    - **Property 7: Command Result Structure Completeness**
    - **Validates: Requirements 12.1, 12.3**
  
  - [ ]* 6.6 Write unit tests for CommandInterpreter
    - Test "open youtube" → OPEN_YOUTUBE mapping
    - Test command registration and retrieval
    - Test unrecognized text returns raw text
    - Test multi-language command patterns
    - Test parameter extraction from commands
    - _Requirements: 4.3, 4.4, 4.5_

- [ ] 7. Implement audio capture components
  - [ ] 7.1 Create audio capture base classes in capture.py
    - Implement AudioCapture base class with capture() method
    - Implement FileCapture class using soundfile for loading audio files
    - Implement MicrophoneCapture class using sounddevice for real-time capture
    - Add support for configurable sample rate and channels
    - Add error handling with AudioCaptureError
    - _Requirements: 3.1, 3.3, 9.1_
  
  - [ ]* 7.2 Write unit tests for audio capture
    - Test FileCapture with various audio formats
    - Test MicrophoneCapture initialization
    - Test error handling for invalid files
    - Test error handling for unavailable microphone
    - _Requirements: 3.1, 3.4, 9.1, 9.4, 10.2_

- [ ] 8. Implement main GuruSpeechEngine facade
  - [ ] 8.1 Create GuruSpeechEngine class in __init__.py
    - Implement __init__ with configuration parameters
    - Initialize NoiseCleaner, WhisperTranscriber, CommandInterpreter components
    - Implement transcribe_microphone() method
    - Implement transcribe_file() method
    - Implement interpret_command() method
    - Implement process_voice_command() for end-to-end processing
    - Add pipeline orchestration: capture → clean → transcribe → interpret
    - Add error handling that preserves context from all components
    - Add logging at INFO level for operations
    - _Requirements: 1.4, 2.2, 3.1, 4.1, 9.1, 9.3, 10.1, 10.5, 12.2_
  
  - [ ]* 8.2 Write property test for error context preservation
    - **Property 5: Error Context Preservation**
    - **Validates: Requirements 10.1, 10.4**
  
  - [ ]* 8.3 Write property test for model reuse
    - **Property 6: Model Reuse Across Requests**
    - **Validates: Requirements 11.3**
  
  - [ ]* 8.4 Write integration tests for GuruSpeechEngine
    - Test end-to-end pipeline with file input
    - Test end-to-end pipeline with microphone input (mocked)
    - Test process_voice_command() returns CommandResult
    - Test pipeline processes files and microphone input consistently
    - Test resource cleanup after processing
    - Test configuration options (compute type, beam size, noise reduction)
    - _Requirements: 9.3, 11.2, 11.4_

- [ ] 9. Checkpoint - Ensure integration works
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Add async support for non-blocking integration
  - [ ] 10.1 Add async versions of main methods
    - Implement async transcribe_microphone_async()
    - Implement async transcribe_file_async()
    - Implement async process_voice_command_async()
    - Use asyncio for non-blocking execution
    - _Requirements: 12.4_
  
  - [ ]* 10.2 Write unit tests for async methods
    - Test async transcription methods
    - Test async command processing
    - Test concurrent async requests
    - _Requirements: 12.4_

- [ ] 11. Create example scripts and documentation
  - [ ] 11.1 Create example usage scripts
    - Create example_basic.py demonstrating simple transcription
    - Create example_commands.py demonstrating command detection
    - Create example_microphone.py demonstrating real-time capture
    - Create example_custom_commands.py demonstrating command registration
    - _Requirements: 4.5, 12.2_
  
  - [ ] 11.2 Create README.md with usage documentation
    - Document installation instructions
    - Document basic usage examples
    - Document configuration options
    - Document command registration
    - Document multi-language support
    - Document error handling
    - _Requirements: 12.2_

- [ ] 12. Final checkpoint - Ensure all tests pass
  - Run full test suite with coverage report
  - Verify all 7 property tests are implemented and passing
  - Verify unit tests cover edge cases and error conditions
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties with 100+ iterations
- Unit tests validate specific examples, edge cases, and error conditions
- The implementation follows a bottom-up approach: components first, then integration
- Checkpoints ensure incremental validation at key milestones
