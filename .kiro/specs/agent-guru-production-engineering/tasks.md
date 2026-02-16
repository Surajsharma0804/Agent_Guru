# Implementation Plan: AGENT_GURU Production Engineering

## Overview

This implementation plan transforms AGENT_GURU from its current operational state into a fully functional, production-ready voice assistant. The approach focuses on systematic cleanup, integration, testing, and optimization to deliver a polished product with production installers for Windows and macOS.

The implementation follows a phased approach: audit and cleanup → core integration → testing → optimization → packaging. Each phase builds on the previous, ensuring incremental progress with validation checkpoints.

## Task Completion Protocol

After completing EACH task:
1. ✅ Run all tests for that task
2. ✅ Verify all tests pass
3. ✅ Commit changes with descriptive message
4. ✅ Push to GitHub immediately
5. ✅ Mark task as complete in this file

## Tasks

- [ ] 1. Repository audit and system mapping
  - Analyze and document all Rust modules in `guru/` directory
  - Analyze and document all Python integration points
  - Analyze and document C++ bindings (Whisper, Llama, TTS)
  - Map inter-language communication boundaries and data flow
  - Document the complete voice pipeline from wake word to TTS
  - Create architecture diagram showing all components and dependencies
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.7, 1.8_

- [ ] 2. Error and warning elimination
  - [ ] 2.1 Fix all Rust compilation errors and warnings
    - Run `cargo build --all-features` and fix all errors
    - Run `cargo clippy --all-features` and fix all warnings
    - Ensure zero warnings with `RUSTFLAGS="-D warnings"`
    - _Requirements: 2.1, 2.2_
  
  - [ ] 2.2 Fix all Python import and runtime errors
    - Test all Python module imports
    - Fix any missing dependencies or import errors
    - Run pylint and fix critical issues
    - _Requirements: 2.3, 2.4_
  
  - [ ] 2.3 Fix all C++ binding compilation issues
    - Verify Whisper.cpp bindings compile cleanly
    - Verify any other C++ integrations compile without warnings
    - _Requirements: 2.5, 2.6_
  
  - [ ] 2.4 Run static analysis tools
    - Run `cargo audit` for security vulnerabilities
    - Run clippy with strict lints
    - Document any remaining issues with justification
    - _Requirements: 2.7_

- [ ] 3. Dead code and file cleanup
  - [ ] 3.1 Remove unreachable code in Rust modules
    - Use `cargo-udeps` to find unused dependencies
    - Remove unused dependencies from Cargo.toml
    - Search for unreachable code using code coverage tools
    - _Requirements: 3.1, 3.4_
  
  - [ ] 3.2 Remove unreachable code in Python modules
    - Identify and remove unused Python modules
    - Remove unused imports
    - _Requirements: 3.2, 3.5_
  
  - [ ] 3.3 Remove duplicate files and commented code
    - Search for duplicate file implementations
    - Remove commented-out code blocks exceeding 10 lines
    - Clean up temporary files and build artifacts
    - _Requirements: 3.3, 3.6_

- [ ] 4. Naming convention standardization
  - [ ] 4.1 Standardize Rust naming conventions
    - Verify all functions and variables use snake_case
    - Verify all structs and enums use PascalCase
    - Run clippy naming lints
    - _Requirements: 4.1, 4.2_
  
  - [ ] 4.2 Standardize Python naming conventions
    - Verify all functions and variables use snake_case
    - Verify all classes use PascalCase
    - Run pylint naming checks
    - _Requirements: 4.3, 4.4_
  
  - [ ] 4.3 Ensure consistent terminology across codebase
    - Create glossary of standard terms (STT, TTS, LLM, etc.)
    - Update code to use consistent terminology
    - Add comments for non-obvious naming choices
    - _Requirements: 4.5, 4.6, 4.7, 4.8_

- [ ] 5. Checkpoint - Ensure clean build
  - Verify `cargo build --release --all-features` succeeds with zero warnings
  - Verify all Python modules import successfully
  - Verify code passes all linting checks
  - Ask the user if questions arise

- [ ] 6. Wake word detection integration
  - [ ] 6.1 Implement wake word engine with MFCC features
    - Verify `MFCCWakeWordEngine` implementation in `guru/voice/wake/`
    - Ensure MFCC feature extraction is working correctly
    - Implement confidence threshold filtering
    - _Requirements: 5.1, 5.6, 5.7_
  
  - [ ] 6.2 Optimize wake word performance
    - Implement lock-free ring buffer for audio data
    - Optimize CPU usage to stay under 10%
    - Optimize memory usage to stay under 50MB
    - Measure and optimize detection latency to ≤50ms
    - _Requirements: 5.2, 5.3, 5.5_
  
  - [ ] 6.3 Write property test for wake word detection latency
    - **Property 1: Wake word detection latency**
    - **Validates: Requirements 5.1, 14.1**
  
  - [ ] 6.4 Write property test for wake word detection with noise
    - **Property 2: Wake word detection with noise**
    - **Validates: Requirements 5.4**
  
  - [ ] 6.5 Write property test for wake word feedback latency
    - **Property 3: Wake word feedback latency**
    - **Validates: Requirements 5.5**
  
  - [ ] 6.6 Write property test for multiple wake word support
    - **Property 4: Multiple wake word support**
    - **Validates: Requirements 5.8**

- [ ] 7. Speech-to-text integration
  - [ ] 7.1 Integrate Whisper.cpp for STT
    - Verify Whisper model loading (base model ~140MB)
    - Implement transcription interface in `guru/voice/transcription/`
    - Add VAD (Voice Activity Detection) to skip silent segments
    - Support streaming transcription for real-time feedback
    - _Requirements: 6.4, 6.5, 6.8_
  
  - [ ] 7.2 Optimize STT performance
    - Measure processing speed (target: ≤120ms per second of audio)
    - Cache model in memory to avoid reload overhead
    - Optimize audio preprocessing
    - _Requirements: 6.1_
  
  - [ ] 7.3 Write property test for STT processing latency
    - **Property 5: STT processing latency**
    - **Validates: Requirements 6.1**
  
  - [ ] 7.4 Write property test for STT transcription accuracy
    - **Property 6: STT transcription accuracy**
    - **Validates: Requirements 6.2**
  
  - [ ] 7.5 Write property test for STT interface contract
    - **Property 7: STT interface contract**
    - **Validates: Requirements 6.6**
  
  - [ ] 7.6 Write property test for STT confidence scoring
    - **Property 8: STT confidence scoring**
    - **Validates: Requirements 6.7**

- [ ] 8. Intent parsing and command routing
  - [ ] 8.1 Implement intent parser with pattern matching
    - Create `IntentParser` class in Python
    - Implement regex patterns for common commands
    - Support 20+ intent categories (open_app, type_text, send_message, etc.)
    - Add LLM fallback for ambiguous queries
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_
  
  - [ ] 8.2 Implement command pattern registry
    - Create command pattern data structures
    - Register patterns for 50+ predefined commands
    - Support command aliases and variations
    - _Requirements: 18.8_
  
  - [ ] 8.3 Write property test for intent classification latency
    - **Property 9: Intent classification latency**
    - **Validates: Requirements 7.1**
  
  - [ ] 8.4 Write property tests for parameter extraction
    - **Property 10: Application name extraction**
    - **Property 11: Text extraction for typing**
    - **Property 12: Message parameter extraction**
    - **Property 14: System action extraction**
    - **Validates: Requirements 7.2, 7.3, 7.4, 7.6**
  
  - [ ] 8.5 Write property test for query routing
    - **Property 13: Query routing to LLM**
    - **Validates: Requirements 7.5**
  
  - [ ] 8.6 Write property test for low confidence clarification
    - **Property 15: Low confidence clarification**
    - **Validates: Requirements 7.8**

- [ ] 9. OS-level action execution
  - [ ] 9.1 Implement Windows OS controller
    - Implement `WindowsController` in `guru/platform/windows.rs`
    - Use Win32 API for application launching (ShellExecuteW)
    - Use SendInput for keyboard/mouse simulation
    - Use FindWindow/GetForegroundWindow for window management
    - Implement permission checking and error handling
    - _Requirements: 8.1, 8.3, 8.4, 8.6, 8.7_
  
  - [ ] 9.2 Implement macOS OS controller
    - Implement `MacOSController` in `guru/platform/macos.rs`
    - Use NSWorkspace for application launching
    - Use Accessibility API for UI automation
    - Use CGEvent for keyboard/mouse simulation
    - Implement permission checking and error handling
    - _Requirements: 8.2, 8.3, 8.4, 8.6, 8.7_
  
  - [ ] 9.3 Implement audit logging for OS operations
    - Log all OS-level actions with timestamp and parameters
    - Store logs in `.kiro/logs/os_audit.jsonl`
    - Implement log rotation (max 100MB per file)
    - _Requirements: 8.8, 19.5_
  
  - [ ] 9.4 Write property tests for OS control
    - **Property 16: Windows application launching**
    - **Property 17: macOS application launching**
    - **Property 18: Keyboard input simulation**
    - **Property 19: Mouse click simulation**
    - **Property 21: Application launch verification**
    - **Property 22: Permission error handling**
    - **Property 23: OS operation audit logging**
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.6, 8.7, 8.8**
  
  - [ ] 9.5 Write unit tests for example commands
    - Test "Open YouTube" command
    - Test "Open Notepad" command
    - Test "Write hello world" command
    - Test "Open WhatsApp" command
    - _Requirements: 18.1, 18.3, 18.4, 18.5_

- [ ] 10. Checkpoint - Verify OS control functionality
  - Test application launching on target platform
  - Test keyboard input simulation
  - Test mouse click simulation
  - Verify audit logging is working
  - Ask the user if questions arise

- [ ] 11. LLM provider integration
  - [ ] 11.1 Verify multi-provider support
    - Verify Ollama client in `guru/llm/ollama.rs`
    - Verify OpenAI client in `guru/llm/provider_openai.rs`
    - Verify Gemini client in `guru/llm/provider_gemini.rs`
    - Verify UnifiedProvider in `guru/llm/unified_provider.rs`
    - _Requirements: 9.2, 9.3, 9.4_
  
  - [ ] 11.2 Implement provider failover and fallback
    - Implement provider availability checking
    - Implement automatic failover (Ollama → OpenAI → Gemini → Rule-based)
    - Implement rule-based fallback responses
    - _Requirements: 9.7_
  
  - [ ] 11.3 Implement conversation context management
    - Ensure conversation history is maintained across provider switches
    - Implement context window management
    - Add system prompt for voice interaction personality
    - _Requirements: 9.5, 9.8_
  
  - [ ] 11.4 Write property tests for LLM provider
    - **Property 24: LLM first token latency**
    - **Property 25: Provider switching context preservation**
    - **Property 26: LLM response streaming**
    - **Property 27: LLM fallback behavior**
    - **Property 28: Conversation history maintenance**
    - **Validates: Requirements 9.1, 9.5, 9.6, 9.7, 9.8**

- [ ] 12. Text-to-speech synthesis
  - [ ] 12.1 Implement TTS engine
    - Verify `SynthesisEngine` in `guru/voice/synthesis.rs`
    - Integrate Piper TTS or Coqui TTS for synthesis
    - Support multiple voice profiles (male, female, neutral)
    - Implement speech rate adjustment (0.5x to 2.0x)
    - _Requirements: 10.1, 10.3, 10.4, 10.5_
  
  - [ ] 12.2 Implement prosody and punctuation handling
    - Parse punctuation for natural pauses
    - Implement intonation control
    - Ensure output at 22kHz or higher sample rate
    - _Requirements: 10.6, 10.7_
  
  - [ ] 12.3 Write property tests for TTS
    - **Property 29: TTS synthesis latency**
    - **Property 30: Speech rate adjustment**
    - **Property 31: Punctuation handling**
    - **Property 32: TTS interruption handling**
    - **Validates: Requirements 10.1, 10.4, 10.6, 10.8**

- [ ] 13. Conversation memory system
  - [ ] 13.1 Implement conversation memory with encryption
    - Verify `ConversationMemory` in `guru/memory/`
    - Implement AES-256-GCM encryption for stored data
    - Implement LRU eviction strategy (max 50 turns)
    - Support persistence to disk (`.kiro/memory/conversations.enc`)
    - _Requirements: 11.1, 11.3, 11.4, 11.5, 11.6_
  
  - [ ] 13.2 Implement memory retrieval and search
    - Implement fast context retrieval (≤10ms)
    - Add semantic search capability (future enhancement)
    - Implement user controls for history deletion
    - _Requirements: 11.2, 11.7, 11.8, 19.4_
  
  - [ ] 13.3 Write property tests for memory system
    - **Property 33: Conversation storage**
    - **Property 34: Context preservation across queries**
    - **Property 35: LRU eviction strategy**
    - **Property 36: Conversation data encryption**
    - **Property 37: Cross-session persistence**
    - **Property 38: Memory retrieval latency**
    - **Validates: Requirements 11.1, 11.2, 11.4, 11.5, 11.6, 11.7**

- [ ] 14. Audio pipeline integration
  - [ ] 14.1 Verify audio capture and playback
    - Verify cpal integration for audio capture in `guru/voice_main.rs`
    - Verify rodio integration for audio playback
    - Ensure 16kHz sample rate for capture
    - Implement lock-free ring buffer (10 seconds capacity)
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_
  
  - [ ] 14.2 Implement audio device management
    - Implement device detection and selection
    - Handle device disconnection gracefully with auto-reconnection
    - Prevent audio feedback loops during simultaneous capture/playback
    - _Requirements: 12.6, 12.7, 12.8_
  
  - [ ] 14.3 Write property tests for audio pipeline
    - **Property 39: Audio device disconnection handling**
    - **Property 40: Audio feedback prevention**
    - **Validates: Requirements 12.6, 12.7**

- [ ] 15. End-to-end voice pipeline integration
  - [ ] 15.1 Wire all components together
    - Connect wake word → STT → intent → action → LLM → TTS → playback
    - Implement state machine for voice interaction flow
    - Add visual/audio feedback for each stage
    - Handle transitions between listening and speaking states
    - _Requirements: 1.7_
  
  - [ ] 15.2 Implement conversation flow control
    - Add "stop listening" command to pause
    - Add "exit" and "goodbye" commands to quit
    - Implement wake word re-activation after response
    - Add manual activation button as fallback
    - _Requirements: 18.6_
  
  - [ ] 15.3 Write integration tests for voice pipeline
    - Test wake word → STT → intent → OS action → feedback flow
    - Test wake word → STT → intent → LLM → TTS → playback flow
    - Test error scenarios → recovery → retry → success flow
    - Test provider switching → context preservation → response flow

- [ ] 16. Checkpoint - End-to-end voice loop testing
  - Test complete voice pipeline with real audio input
  - Verify wake word detection works reliably
  - Verify STT transcription is accurate
  - Verify intent parsing routes commands correctly
  - Verify OS actions execute successfully
  - Verify LLM responses are appropriate
  - Verify TTS output is natural-sounding
  - Ask the user if questions arise

- [ ] 17. Performance optimization
  - [ ] 17.1 Optimize latency for each pipeline stage
    - Measure and optimize wake word detection (target: ≤50ms)
    - Measure and optimize STT processing (target: ≤120ms/sec)
    - Measure and optimize intent classification (target: ≤50ms)
    - Measure and optimize LLM first token (target: ≤300ms)
    - Measure and optimize TTS synthesis (target: ≤200ms)
    - _Requirements: 14.1, 14.2, 14.3, 14.4_
  
  - [ ] 17.2 Optimize resource usage
    - Optimize idle CPU usage (target: <10%)
    - Optimize active CPU usage (target: <20%)
    - Optimize memory usage (target: <500MB)
    - Optimize startup time (target: <5 seconds)
    - _Requirements: 14.6, 14.7, 14.8_
  
  - [ ] 17.3 Write property tests for performance
    - **Property 41: End-to-end latency for simple commands**
    - **Property 42: Startup time optimization**
    - **Validates: Requirements 14.5, 14.8**
  
  - [ ] 17.4 Write performance benchmarks
    - Create latency benchmarks for each pipeline stage
    - Create resource usage benchmarks
    - Create stress tests (24-hour operation, 1000 commands)

- [ ] 18. Cross-platform support verification
  - [ ] 18.1 Test on Windows platforms
    - Test on Windows 10
    - Test on Windows 11
    - Verify all OS control features work
    - Verify audio pipeline works with various devices
    - _Requirements: 15.1, 15.3_
  
  - [ ] 18.2 Test on macOS platforms
    - Test on macOS 11 (Big Sur)
    - Test on macOS 12 (Monterey)
    - Test on macOS 13 (Ventura)
    - Test on macOS 14 (Sonoma)
    - Verify all OS control features work
    - Verify audio pipeline works with various devices
    - _Requirements: 15.2, 15.4_
  
  - [ ] 18.3 Write property tests for cross-platform support
    - **Property 43: Audio device detection across platforms**
    - **Property 44: Graceful degradation**
    - **Validates: Requirements 15.5, 15.7**

- [ ] 19. Security and privacy implementation
  - [ ] 19.1 Implement data privacy controls
    - Verify no audio data transmitted when using local models
    - Verify HTTPS for all cloud API communications
    - Implement user controls for conversation history deletion
    - _Requirements: 19.2, 19.3, 19.4_
  
  - [ ] 19.2 Implement security controls
    - Implement user confirmation for sensitive actions
    - Implement rate limiting to prevent abuse
    - Implement input validation to prevent injection attacks
    - _Requirements: 19.6, 19.7, 19.8_
  
  - [ ] 19.3 Write property tests for security
    - **Property 45: Local model data privacy**
    - **Property 46: HTTPS for cloud APIs**
    - **Property 47: Sensitive action confirmation**
    - **Property 48: Rate limiting**
    - **Property 49: Input validation**
    - **Validates: Requirements 19.2, 19.3, 19.6, 19.7, 19.8**

- [ ] 20. Error handling and recovery
  - [ ] 20.1 Implement comprehensive error handling
    - Implement microphone error recovery with retry
    - Implement LLM provider fallback (already done in task 11.2)
    - Implement OS action error reporting via speech
    - Implement audio playback error handling
    - _Requirements: 20.1, 20.3, 20.4_
  
  - [ ] 20.2 Implement retry and recovery mechanisms
    - Implement exponential backoff for transient failures
    - Implement automatic recovery for critical component failures
    - Ensure system never crashes due to user input or external failures
    - _Requirements: 20.5, 20.7, 20.8_
  
  - [ ] 20.3 Implement detailed error logging
    - Log all errors with timestamp, component, and context
    - Store logs in `.kiro/logs/errors.log`
    - Implement log rotation (max 100MB per file)
    - _Requirements: 20.6_
  
  - [ ] 20.4 Write property tests for error handling
    - **Property 50: Microphone error recovery**
    - **Property 51: OS action error reporting**
    - **Property 52: Audio playback error handling**
    - **Property 53: Exponential backoff for transient failures**
    - **Property 54: Detailed error logging**
    - **Property 55: Automatic recovery**
    - **Property 56: Crash prevention**
    - **Validates: Requirements 20.1, 20.3, 20.4, 20.5, 20.6, 20.7, 20.8**

- [ ] 21. Checkpoint - Comprehensive testing
  - Run all unit tests and verify 80%+ code coverage
  - Run all property tests with 100 iterations minimum
  - Run all integration tests
  - Run performance benchmarks and verify targets met
  - Run security audit (cargo audit, safety)
  - Ask the user if questions arise

- [ ] 22. Production installer creation
  - [ ] 22.1 Create Windows installer
    - Create MSI installer using WiX Toolset
    - Include all required dependencies (models, libraries)
    - Create desktop shortcuts and start menu entries
    - Register application with Windows
    - Implement silent installation support
    - Create uninstaller
    - _Requirements: 16.1, 16.3, 16.4, 16.5, 16.6, 16.7_
  
  - [ ] 22.2 Create macOS installer
    - Create DMG installer with app bundle
    - Include all required dependencies (models, libraries)
    - Create application icon and metadata
    - Sign application for macOS Gatekeeper
    - Create uninstaller script
    - _Requirements: 16.2, 16.3, 16.7_
  
  - [ ] 22.3 Add system requirements verification
    - Check OS version compatibility
    - Check available disk space
    - Check microphone availability
    - Display clear error messages if requirements not met
    - _Requirements: 16.8_
  
  - [ ] 22.4 Test installers on clean systems
    - Test Windows installer on clean Windows 10 and 11
    - Test macOS installer on clean macOS 11, 12, 13, 14
    - Verify all components install correctly
    - Verify application launches successfully
    - Verify uninstaller removes all components

- [ ] 23. Documentation and final polish
  - [ ] 23.1 Create user documentation
    - Write quick start guide
    - Write command reference
    - Write troubleshooting guide
    - Write FAQ
  
  - [ ] 23.2 Create developer documentation
    - Document architecture and design decisions
    - Document build and development setup
    - Document testing procedures
    - Document contribution guidelines
  
  - [ ] 23.3 Final code cleanup
    - Remove any remaining TODO comments
    - Ensure all code is properly formatted
    - Ensure all public APIs have documentation
    - Run final lint and format checks

- [ ] 24. Final checkpoint - Production readiness verification
  - Verify zero compilation errors and warnings
  - Verify all tests passing (unit, property, integration)
  - Verify performance targets met
  - Verify installers work on all target platforms
  - Verify documentation is complete
  - Ensure all tests pass, ask the user if questions arise

## Notes

- Tasks marked with `*` are optional property-based tests and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- Property tests validate universal correctness properties with 100+ iterations
- Unit tests validate specific examples and edge cases
- The implementation prioritizes production quality: zero errors, comprehensive testing, and polished user experience
