# Requirements Document: GURU Complete Desktop AI Assistant System

## Introduction

GURU is a production-grade, security-first desktop AI assistant designed for Windows 10/11. It provides voice-activated automation, application control, biometric authentication, and intelligent conversation capabilities. The system operates as a local-first, authority-gated co-worker that executes desktop actions with military-grade security and comprehensive audit logging.

## Glossary

- **GURU**: The desktop AI assistant system
- **Authority_State_Machine**: Security component that controls command execution permissions
- **Audit_Logger**: Cryptographically-secured logging system with tamper detection
- **Voice_Interface**: Speech recognition and wake word detection system
- **TTS_Service**: Text-to-speech synthesis engine
- **Command_Executor**: System that translates natural language to OS-level actions
- **Biometric_Provider**: Windows Hello integration for fingerprint/face authentication
- **Intrusion_Detector**: Security monitoring system for unauthorized access attempts
- **Failure_Orchestrator**: Component health monitoring and recovery system
- **LLM_Adapter**: Multi-provider AI model integration layer (Ollama, OpenAI, Gemini)
- **Memory_System**: Encrypted conversation history with vector search
- **Skills_Registry**: Plugin architecture for extensible capabilities
- **Thread_Safe_Bridge**: Qt signal/slot bridge for cross-thread communication
- **Wake_Word**: Activation phrase ("Hey GURU") that initiates listening
- **Authority_Session**: Time-limited permission grant for command execution
- **Workstation_Lock**: OS-level screen lock triggered by security violations
- **PAL**: Platform Abstraction Layer - isolates OS-specific behavior behind contracts
- **Platform_Backend**: OS-specific implementation of PAL interfaces
- **Application_Controller**: Platform-agnostic interface for application control
- **Input_Automation**: Platform-agnostic interface for keyboard/mouse automation
- **Speech_Output**: Platform-agnostic interface for text-to-speech
- **Speech_Input**: Platform-agnostic interface for voice recognition
- **Biometric_Authenticator**: Platform-agnostic interface for biometric authentication
- **Security_Enforcer**: Platform-agnostic interface for security lockdown
- **Core_Logic**: Platform-agnostic system components (Voice, Intent, Authority, Memory)
- **Capability_Matrix**: Documentation of platform-specific feature availability

## Requirements

### Requirement 1: Voice Activation and Continuous Conversation

**User Story:** As a user, I want to activate GURU with a wake word and have continuous conversation without repeating the wake word, so that I can interact naturally like with a human co-worker.

#### Acceptance Criteria

1. WHEN a user says "Hey GURU", THE Voice_Interface SHALL activate and begin listening for commands
2. WHILE the Voice_Interface is active, THE System SHALL continue listening without requiring the wake word again
3. WHEN 5 seconds of silence is detected, THE Voice_Interface SHALL remain active but enter idle state
4. WHEN the user says "stop", "sleep", "exit", or "that's all", THE Voice_Interface SHALL deactivate
5. IF the wake word is detected mid-sentence, THE System SHALL ignore it and continue processing the command
6. WHEN the Voice_Interface is inactive, THE System SHALL only listen for the wake word

### Requirement 2: Command Execution with Universal Application Support

**User Story:** As a user, I want to control any application on my computer through voice commands, so that I can automate tasks without using mouse and keyboard.

#### Acceptance Criteria

1. WHEN a user says "open [application]", THE Command_Executor SHALL launch the specified application
2. THE Command_Executor SHALL support 100+ applications including Office, browsers, social media, development tools, and system utilities
3. IF an application is not in the database, THE Command_Executor SHALL search common installation paths and discover the executable
4. WHEN a user says "open notepad and write [text]", THE Command_Executor SHALL launch Notepad and type the exact text
5. WHEN typing text, THE Command_Executor SHALL preserve exact wording without rephrasing or grammar correction
6. WHEN a user says "search for [query]", THE Command_Executor SHALL open the default browser with a Google search
7. THE Command_Executor SHALL complete application launches within 1 second
8. THE Command_Executor SHALL complete text automation within 2 seconds

### Requirement 3: Authority-Gated Security Model

**User Story:** As a security-conscious user, I want all command execution to require explicit authority grants, so that unauthorized access cannot execute commands on my system.

#### Acceptance Criteria

1. WHEN the System starts, THE Authority_State_Machine SHALL initialize in UNARMED state
2. WHEN a user authenticates via biometrics, THE Authority_State_Machine SHALL transition to ARMED state
3. WHILE in ARMED state, THE System SHALL allow command execution
4. WHEN 15 minutes of inactivity occurs, THE Authority_State_Machine SHALL automatically revoke authority
5. WHEN a security violation is detected, THE Authority_State_Machine SHALL immediately transition to LOCKED state and trigger Workstation_Lock
6. WHEN in LOCKED state, THE System SHALL reject all commands until manual unlock
7. THE Authority_State_Machine SHALL log all state transitions to the Audit_Logger

### Requirement 4: Biometric Authentication Integration

**User Story:** As a user, I want to authenticate using Windows Hello fingerprint or face recognition, so that I can securely grant authority without passwords.

#### Acceptance Criteria

1. WHEN the System starts, THE Biometric_Provider SHALL detect available Windows Hello factors
2. THE Biometric_Provider SHALL support fingerprint sensors and face recognition cameras
3. WHEN a user requests authentication, THE Biometric_Provider SHALL invoke Windows Hello verification
4. WHEN biometric verification succeeds, THE System SHALL grant authority for 15 minutes
5. WHEN biometric verification fails 3 times, THE System SHALL trigger security lockout
6. THE Biometric_Provider SHALL work on Windows 10 build 1511+ with Windows Hello configured

### Requirement 5: Cryptographic Audit Logging

**User Story:** As a system administrator, I want all system events logged with cryptographic integrity, so that I can detect tampering and investigate security incidents.

#### Acceptance Criteria

1. THE Audit_Logger SHALL log all command executions with timestamp, user, command text, and result
2. THE Audit_Logger SHALL log all authority state transitions with reason and metadata
3. THE Audit_Logger SHALL log all security violations with severity and context
4. THE Audit_Logger SHALL compute HMAC-SHA256 signatures for each log entry
5. THE Audit_Logger SHALL maintain a chain of signatures to detect tampering
6. WHEN log verification is requested, THE Audit_Logger SHALL validate the entire chain
7. THE Audit_Logger SHALL rotate log files daily and compress old logs
8. THE Audit_Logger SHALL never log sensitive data (passwords, biometric templates, personal information)

### Requirement 6: Intrusion Detection and Response

**User Story:** As a security-conscious user, I want the system to detect unauthorized access attempts and automatically lock my workstation, so that my data remains protected.

#### Acceptance Criteria

1. THE Intrusion_Detector SHALL monitor for repeated failed authentication attempts
2. WHEN 3 failed authentication attempts occur within 5 minutes, THE Intrusion_Detector SHALL trigger security lockout
3. THE Intrusion_Detector SHALL monitor for suspicious command patterns
4. WHEN a security violation is detected, THE Intrusion_Detector SHALL immediately invoke Workstation_Lock
5. THE Intrusion_Detector SHALL log all security events to the Audit_Logger with CRITICAL severity
6. THE Intrusion_Detector SHALL send notifications to the user about security events

### Requirement 7: Multi-Provider LLM Integration

**User Story:** As a user, I want GURU to use the best available AI model for each task, so that I get intelligent responses without being locked to one provider.

#### Acceptance Criteria

1. THE LLM_Adapter SHALL support Ollama (local), OpenAI (cloud), and Google Gemini (cloud)
2. THE LLM_Adapter SHALL use qwen2.5:7b-instruct for intent detection (fast, local)
3. THE LLM_Adapter SHALL use mistral:7b-instruct for action structuring (fast, local)
4. THE LLM_Adapter SHALL use qwen2.5:14b-instruct for deep reasoning (slow, local, only when needed)
5. WHEN an LLM request times out after 10 seconds, THE LLM_Adapter SHALL fall back to template responses
6. THE LLM_Adapter SHALL never send user data to cloud providers without explicit consent
7. THE LLM_Adapter SHALL cache responses to avoid redundant API calls

### Requirement 8: Thread-Safe GUI Architecture

**User Story:** As a developer, I want all GUI operations to be thread-safe, so that voice callbacks don't crash the Qt event loop.

#### Acceptance Criteria

1. THE Thread_Safe_Bridge SHALL use Qt signals with QueuedConnection for all cross-thread communication
2. WHEN a voice command is received in the background thread, THE Thread_Safe_Bridge SHALL emit signals to the main thread
3. THE Thread_Safe_Bridge SHALL never allow direct Qt widget access from background threads
4. THE TTS_Service SHALL operate in a dedicated thread with an internal queue
5. THE Voice_Interface SHALL run in a background daemon thread
6. ALL GUI updates SHALL occur only in the main Qt thread

### Requirement 9: Text-to-Speech with Priority Queue

**User Story:** As a user, I want GURU to speak responses clearly and loudly, so that I can hear feedback without adjusting volume.

#### Acceptance Criteria

1. THE TTS_Service SHALL use Windows SAPI for speech synthesis
2. THE TTS_Service SHALL bypass the Windows Volume Mixer to avoid 1% volume lock
3. THE TTS_Service SHALL support priority levels (CRITICAL, HIGH, NORMAL, LOW)
4. WHEN multiple speech requests are queued, THE TTS_Service SHALL process them in priority order
5. THE TTS_Service SHALL speak at full system volume
6. THE TTS_Service SHALL complete speech synthesis within 5 seconds for typical responses

### Requirement 10: Encrypted Memory and Conversation History

**User Story:** As a privacy-conscious user, I want my conversation history encrypted at rest, so that my data remains private even if my disk is compromised.

#### Acceptance Criteria

1. THE Memory_System SHALL encrypt all conversation history using AES-256-GCM
2. THE Memory_System SHALL derive encryption keys from user biometric authentication
3. THE Memory_System SHALL support vector search for semantic conversation retrieval
4. WHEN a user requests conversation history, THE Memory_System SHALL decrypt and return relevant entries
5. THE Memory_System SHALL automatically purge conversations older than 90 days
6. THE Memory_System SHALL never store encryption keys in plaintext

### Requirement 11: Component Health Monitoring and Failure Recovery

**User Story:** As a system operator, I want automatic detection and recovery from component failures, so that GURU remains operational even when subsystems fail.

#### Acceptance Criteria

1. THE Failure_Orchestrator SHALL monitor health of all system components every 30 seconds
2. WHEN a component fails, THE Failure_Orchestrator SHALL attempt automatic restart
3. WHEN a component fails 3 times, THE Failure_Orchestrator SHALL mark it as permanently failed
4. THE Failure_Orchestrator SHALL maintain a dependency graph of components
5. WHEN a critical component fails, THE Failure_Orchestrator SHALL gracefully degrade dependent features
6. THE Failure_Orchestrator SHALL log all failures to the Audit_Logger

### Requirement 12: Skills Plugin Architecture

**User Story:** As a developer, I want to extend GURU with custom skills, so that I can add domain-specific capabilities without modifying core code.

#### Acceptance Criteria

1. THE Skills_Registry SHALL discover skills from the skills/ directory
2. THE Skills_Registry SHALL load skills in isolated sandboxes
3. WHEN a skill is loaded, THE Skills_Registry SHALL validate its manifest and permissions
4. THE Skills_Registry SHALL provide skills with access to approved APIs only
5. WHEN a skill crashes, THE Skills_Registry SHALL isolate the failure and continue operation
6. THE Skills_Registry SHALL monitor skill resource usage and enforce limits

### Requirement 13: Multilingual Voice Processing

**User Story:** As a multilingual user, I want GURU to understand commands in multiple languages, so that I can speak naturally in my preferred language.

#### Acceptance Criteria

1. THE Voice_Interface SHALL detect the language of each voice command
2. THE Voice_Interface SHALL support English, Spanish, French, German, Hindi, and Mandarin
3. WHEN a command is in a non-English language, THE System SHALL process it using the appropriate language model
4. THE Voice_Interface SHALL maintain separate wake words for each language
5. THE TTS_Service SHALL synthesize speech in the detected language

### Requirement 14: Dictation Mode vs Command Mode

**User Story:** As a user, I want to dictate text exactly as spoken without GURU interpreting it as commands, so that I can write documents naturally.

#### Acceptance Criteria

1. WHEN a user says "open notepad and write [text]", THE System SHALL enter dictation mode for the text portion
2. WHILE in dictation mode, THE System SHALL type exact words without interpretation
3. THE System SHALL preserve grammar, punctuation, and capitalization as spoken
4. THE System SHALL not rephrase or improve dictated text
5. WHEN dictation completes, THE System SHALL return to command mode

### Requirement 15: WhatsApp Automation

**User Story:** As a user, I want to send WhatsApp messages through voice commands, so that I can communicate without touching my phone.

#### Acceptance Criteria

1. WHEN a user says "send whatsapp message to [contact] saying [message]", THE Command_Executor SHALL open WhatsApp
2. THE Command_Executor SHALL search for the specified contact
3. THE Command_Executor SHALL type the exact message text
4. THE Command_Executor SHALL send the message automatically
5. THE Command_Executor SHALL confirm message sent via speech
6. THE Command_Executor SHALL handle contact name variations and fuzzy matching

### Requirement 16: Setup Wizard and First-Run Experience

**User Story:** As a new user, I want a guided setup wizard, so that I can configure GURU correctly on first launch.

#### Acceptance Criteria

1. WHEN GURU launches for the first time, THE System SHALL display the setup wizard
2. THE Setup_Wizard SHALL request microphone and speaker permissions
3. THE Setup_Wizard SHALL guide the user through profile creation (name, password)
4. THE Setup_Wizard SHALL detect and configure Windows Hello biometrics
5. THE Setup_Wizard SHALL allow testing biometric authentication
6. THE Setup_Wizard SHALL configure auto-start and wake phrase preferences
7. WHEN setup completes, THE Setup_Wizard SHALL save configuration and launch GURU

### Requirement 17: Configuration Management

**User Story:** As a user, I want my GURU configuration stored securely and persistently, so that my preferences are preserved across restarts.

#### Acceptance Criteria

1. THE System SHALL store configuration in %USERPROFILE%\.guru\
2. THE System SHALL store LLM configuration in llm_config.json
3. THE System SHALL store user preferences in user_config.json
4. THE System SHALL encrypt sensitive configuration values
5. WHEN configuration is updated, THE System SHALL validate changes before applying
6. THE System SHALL support configuration hierarchy (user > workspace > system defaults)

### Requirement 18: Ollama Model Configuration

**User Story:** As a user, I want GURU to automatically detect and configure my installed Ollama models, so that I don't need to manually edit configuration files.

#### Acceptance Criteria

1. WHEN the configuration script runs, THE System SHALL query Ollama for installed models
2. THE System SHALL select appropriate models for conversation, intent, and reasoning
3. THE System SHALL create llm_config.json with correct model names
4. THE System SHALL set timeout values appropriate for model size (120s for 7B, 180s for 14B)
5. WHEN required models are missing, THE System SHALL provide installation instructions

### Requirement 19: Diagnostic and Verification Tools

**User Story:** As a user, I want diagnostic tools to verify GURU is working correctly, so that I can troubleshoot issues independently.

#### Acceptance Criteria

1. THE System SHALL provide a diagnostic script that tests all components
2. THE Diagnostic_Script SHALL test TTS synthesis and audio output
3. THE Diagnostic_Script SHALL test voice recognition and wake word detection
4. THE Diagnostic_Script SHALL test biometric authentication availability
5. THE Diagnostic_Script SHALL test LLM connectivity and response times
6. THE Diagnostic_Script SHALL report pass/fail for each test with detailed error messages

### Requirement 20: Production-Grade Error Handling

**User Story:** As a user, I want GURU to handle errors gracefully without crashing, so that I can continue working even when subsystems fail.

#### Acceptance Criteria

1. WHEN any component throws an exception, THE System SHALL catch it and log to Audit_Logger
2. THE System SHALL never crash the entire application due to a single component failure
3. WHEN a command fails, THE System SHALL speak an error message explaining what went wrong
4. THE System SHALL provide actionable error messages (not technical stack traces)
5. THE System SHALL automatically retry transient failures (network, LLM timeout)
6. THE System SHALL never retry security-related failures (authentication, authorization)

### Requirement 21: Action Commitment Guarantee

**User Story:** As a user, when I issue a command that implies an OS action, I want GURU to either execute it or explicitly fail—never talk instead, so that I get deterministic behavior.

#### Acceptance Criteria

1. IF user input contains a system action verb (open, type, write, delete, click, send, close, remove), THE System SHALL bypass the conversation LLM
2. THE System SHALL either execute the action successfully OR speak a specific failure reason
3. THE System SHALL NOT respond with conversational text for actionable commands
4. THE System SHALL NOT rephrase user input during action execution
5. THE System SHALL NOT ask follow-up questions unless genuine ambiguity is detected
6. WHEN typing dictation, THE System SHALL type exact words without interpretation
7. WHEN an action completes, THE System SHALL confirm briefly (e.g., "Done", "Opened", "Sent")

### Requirement 22: Wake-Word State Machine

**User Story:** As a user, I want the wake word to work consistently without re-triggering mid-conversation, so that I can have natural continuous dialogue.

#### Acceptance Criteria

1. THE Voice_Interface SHALL implement a state machine with states: INACTIVE, ACTIVE, IDLE, SUSPENDED
2. WHEN the wake word is detected in INACTIVE state, THE Voice_Interface SHALL transition to ACTIVE state
3. WHILE in ACTIVE state, THE Voice_Interface SHALL process all speech as commands without requiring the wake word
4. WHEN 5 seconds of silence occurs in ACTIVE state, THE Voice_Interface SHALL transition to IDLE state
5. WHEN any speech is detected in IDLE state, THE Voice_Interface SHALL transition to ACTIVE state
6. WHEN the user says "stop", "sleep", "exit", or "that's all", THE Voice_Interface SHALL transition to INACTIVE state
7. IF the wake word is detected while in ACTIVE or IDLE state, THE Voice_Interface SHALL ignore it and continue processing
8. THE Voice_Interface SHALL log all state transitions for debugging

### Requirement 23: Task-Aware Speech Policy

**User Story:** As a user, I want GURU to speak concisely during actions and conversationally only when appropriate, so that interactions feel natural and efficient.

#### Acceptance Criteria

1. WHEN executing an action, THE TTS_Service SHALL speak only a short verb phrase (e.g., "Opening WhatsApp", "Typing message")
2. WHEN typing dictation, THE TTS_Service SHALL remain silent
3. WHEN an action completes successfully, THE TTS_Service SHALL confirm briefly (e.g., "Done")
4. WHEN an action fails, THE TTS_Service SHALL speak a concise error message
5. THE TTS_Service SHALL use conversational speech only when no action is pending
6. THE TTS_Service SHALL never speak verbose explanations during action execution
7. THE TTS_Service SHALL never say "How can I help you?" or similar chatbot phrases

### Requirement 24: Intent Pre-Filtering Layer

**User Story:** As a user, I want simple commands to execute instantly without LLM processing, so that GURU responds quickly and doesn't waste resources.

#### Acceptance Criteria

1. BEFORE calling any LLM, THE System SHALL extract verbs and detect OS-action keywords
2. IF a known action pattern is matched (regex or keyword-based), THE System SHALL bypass the conversation LLM
3. THE System SHALL route matched actions directly to Command_Executor
4. THE System SHALL use LLMs only for ambiguous or conversational inputs
5. THE Intent_Pre_Filter SHALL complete pattern matching within 10 milliseconds
6. THE Intent_Pre_Filter SHALL support extensible pattern definitions
7. THE System SHALL log whether LLM was bypassed for each command

### Requirement 25: Desktop Permission Model

**User Story:** As a user, I want GURU to respect OS permission boundaries and request elevation when needed, so that I maintain control over privileged operations.

#### Acceptance Criteria

1. THE System SHALL inherit user-level permissions by default
2. WHEN an admin-level action is requested, THE System SHALL trigger OS UAC prompt
3. THE System SHALL pause execution until the user responds to the UAC prompt
4. THE System SHALL log all permission elevation requests to Audit_Logger
5. THE Skills_Registry SHALL require skills to declare required permissions explicitly
6. THE System SHALL reject skills that request excessive permissions without justification
7. THE System SHALL never attempt to bypass OS security mechanisms

### Requirement 26: WhatsApp Desktop Application Integration

**User Story:** As a user, I want GURU to control the WhatsApp Desktop application specifically, so that automation works reliably without browser dependencies.

#### Acceptance Criteria

1. THE Command_Executor SHALL target WhatsApp Desktop application (not web version)
2. WHEN WhatsApp Desktop is not installed, THE System SHALL inform the user and provide download link
3. THE Command_Executor SHALL use Windows UI Automation API for reliable control
4. THE Command_Executor SHALL handle WhatsApp Desktop startup delays gracefully
5. THE Command_Executor SHALL verify message sent before confirming to user
6. THE Command_Executor SHALL support contact name fuzzy matching with 80% accuracy threshold

### Requirement 27: Memory System Isolation

**User Story:** As a user, I want conversation history to inform responses but never influence command execution, so that actions remain deterministic.

#### Acceptance Criteria

1. THE Memory_System SHALL store conversation history for context retrieval only
2. THE Memory_System SHALL NOT influence command execution logic
3. WHEN processing an action command, THE System SHALL ignore conversation history
4. THE Memory_System SHALL only be queried for conversational responses
5. THE Memory_System SHALL never store command execution results in conversation history
6. THE Memory_System SHALL maintain separate storage for audit logs and conversation history

### Requirement 28: Single Response Ownership Rule

**User Story:** As a user, I want exactly one subsystem to respond to my command at a time, so that I don't get duplicate or conflicting responses.

#### Acceptance Criteria

1. AT ANY TIME, exactly ONE subsystem SHALL produce a user-facing response
2. WHEN the Command_Executor is executing an action, THE Conversation_Manager SHALL suppress all LLM responses
3. WHEN the Command_Executor is executing an action, THE TTS_Service SHALL be limited to short action phrases only
4. WHEN the Intent_Pre_Filter classifies input as ACTION, THE Conversation_Manager SHALL NOT speak
5. WHEN an action succeeds, ONLY the ExecutionResult.message SHALL be spoken
6. WHEN an action fails, ONLY the failure reason SHALL be spoken
7. THE System SHALL never produce both an action confirmation and a conversational response for the same command

### Requirement 29: Dictation State Lock

**User Story:** As a user, I want dictation mode to be a distinct state that prevents any interpretation of my words, so that text is typed exactly as spoken.

#### Acceptance Criteria

1. THE Voice_Interface SHALL implement COMMAND_MODE and DICTATION_MODE states
2. WHEN a command contains "write", "type", or "dictate", THE Voice_Interface SHALL enter DICTATION_MODE
3. WHILE in DICTATION_MODE, THE Intent_Pre_Filter SHALL be bypassed
4. WHILE in DICTATION_MODE, THE LLM_Adapter SHALL be bypassed
5. WHILE in DICTATION_MODE, THE TTS_Service SHALL be muted
6. WHEN 2 seconds of silence occurs in DICTATION_MODE, THE Voice_Interface SHALL exit to COMMAND_MODE
7. WHEN the user says "done" or "stop writing" in DICTATION_MODE, THE Voice_Interface SHALL exit to COMMAND_MODE

### Requirement 30: Wake Word Stripping Rule

**User Story:** As a user, I want the wake word to activate the system but not interfere with command parsing, so that commands are interpreted correctly.

#### Acceptance Criteria

1. ONCE the Voice_Interface is in ACTIVE state, THE System SHALL remove the wake word from transcribed text
2. THE Intent_Pre_Filter SHALL never receive text containing the wake word
3. THE Command_Executor SHALL never receive text containing the wake word
4. THE LLM_Adapter SHALL never receive text containing the wake word
5. WHEN a user says "hey guru open notepad", THE System SHALL process only "open notepad"
6. THE wake word removal SHALL be case-insensitive and handle variations ("hey guru", "hello guru", "hi guru")

### Requirement 31: Deterministic-First Guarantee

**User Story:** As a user, I want simple commands to execute instantly without AI processing, so that the system feels responsive and predictable.

#### Acceptance Criteria

1. WHEN the Intent_Pre_Filter confidence is ≥ 0.7, THE System SHALL never call the LLM
2. WHEN action parameters are fully extractable from the command, THE System SHALL never call the LLM
3. THE LLM_Adapter SHALL only be invoked for ambiguous targets, vague pronouns ("that", "it"), or follow-up clarification
4. THE System SHALL log whether LLM was bypassed for each command
5. THE System SHALL measure and report the percentage of commands that bypass the LLM
6. THE System SHALL aim for ≥ 80% of commands to bypass the LLM through deterministic routing

### Requirement 32: Human Co-Worker Speech Contract

**User Story:** As a user, I want GURU to speak like a human co-worker, not a chatbot, so that interactions feel natural and professional.

#### Acceptance Criteria

1. DURING action execution, THE TTS_Service SHALL use verb-first phrases of ≤ 5 words
2. DURING action execution, THE TTS_Service SHALL never ask questions
3. DURING idle state, THE TTS_Service SHALL use natural but brief language
4. THE TTS_Service SHALL never say "How can I help you?"
5. THE TTS_Service SHALL never say "Sure, I can..."
6. THE TTS_Service SHALL never say "Let me know if..."
7. THE TTS_Service SHALL use only approved action phrases: "Opening [app]", "Done", "Typed", "Sent", "Failed: [reason]"

### Requirement 33: Platform Abstraction Layer (PAL)

**User Story:** As a system architect, I want all OS-specific behavior isolated behind platform contracts, so that GURU can run on Windows, macOS, Android, and iOS without violating security invariants.

#### Acceptance Criteria

1. THE System SHALL isolate all OS-specific behavior behind platform abstraction interfaces
2. THE Core_Logic SHALL NOT directly call Windows-specific APIs (Win32, SAPI, Windows Hello)
3. THE Core_Logic SHALL NOT directly call macOS-specific APIs (LaunchServices, NSSpeechSynthesizer, Touch ID)
4. THE Core_Logic SHALL NOT directly call Android-specific APIs (Intent system, BiometricPrompt)
5. THE Core_Logic SHALL NOT directly call iOS-specific APIs (deep links, Face ID)
6. THE System SHALL implement platform backends for Windows, macOS, Android, and iOS
7. THE System SHALL maintain identical security invariants across all platforms
8. THE System SHALL explicitly declare platform capability limitations in documentation

### Requirement 34: Application Control Contract

**User Story:** As a developer, I want a unified interface for application control across platforms, so that core logic remains platform-agnostic.

#### Acceptance Criteria

1. THE Application_Controller SHALL provide a platform-agnostic interface for opening applications
2. THE Application_Controller SHALL provide a platform-agnostic interface for closing applications
3. THE Application_Controller SHALL provide a platform-agnostic interface for checking if applications are running
4. THE Application_Controller SHALL provide a platform-agnostic interface for discovering installed applications
5. WHEN running on Windows, THE Application_Controller SHALL use Win32/Shell/UIAutomation
6. WHEN running on macOS, THE Application_Controller SHALL use LaunchServices and Apple Events
7. WHEN running on Android, THE Application_Controller SHALL use the Intent system
8. WHEN running on iOS, THE Application_Controller SHALL use deep links only (with explicit limitations)
9. THE Application_Controller SHALL return consistent AppDescriptor objects across all platforms

### Requirement 35: Input Automation Contract

**User Story:** As a developer, I want a unified interface for input automation across platforms, so that text typing and UI control work consistently.

#### Acceptance Criteria

1. THE Input_Automation SHALL provide a platform-agnostic interface for typing text
2. THE Input_Automation SHALL provide a platform-agnostic interface for clicking UI elements
3. THE Input_Automation SHALL provide a platform-agnostic interface for focusing applications
4. WHEN running on Windows, THE Input_Automation SHALL provide full keyboard and mouse control
5. WHEN running on macOS, THE Input_Automation SHALL provide full control with Accessibility permission
6. WHEN running on Android, THE Input_Automation SHALL provide partial control via Accessibility Service
7. WHEN running on iOS, THE Input_Automation SHALL be severely restricted (documented limitation)
8. THE Input_Automation SHALL explicitly declare capability limitations per platform

### Requirement 36: Speech Output Contract

**User Story:** As a developer, I want a unified interface for text-to-speech across platforms, so that speech personality remains consistent.

#### Acceptance Criteria

1. THE Speech_Output SHALL provide a platform-agnostic interface for speech synthesis
2. THE Speech_Output SHALL maintain the Human Co-Worker Speech Contract across all platforms
3. WHEN running on Windows, THE Speech_Output SHALL use Windows SAPI
4. WHEN running on macOS, THE Speech_Output SHALL use NSSpeechSynthesizer
5. WHEN running on Android, THE Speech_Output SHALL use Android TTS
6. WHEN running on iOS, THE Speech_Output SHALL use AVSpeechSynthesizer
7. THE Speech_Output SHALL provide consistent priority queue behavior across all platforms
8. THE Speech_Output SHALL provide consistent volume control across all platforms

### Requirement 37: Speech Input Contract

**User Story:** As a developer, I want a unified interface for speech recognition across platforms, so that voice commands work consistently.

#### Acceptance Criteria

1. THE Speech_Input SHALL provide a platform-agnostic interface for voice recognition
2. THE Speech_Input SHALL provide a platform-agnostic interface for wake word detection
3. THE Speech_Input SHALL provide a platform-agnostic interface for transcription
4. WHEN running on Windows or macOS, THE Speech_Input SHALL use Whisper.cpp for local processing
5. WHEN running on Android, THE Speech_Input SHALL use Whisper or system STT
6. WHEN running on iOS, THE Speech_Input SHALL use system STT (mandatory due to restrictions)
7. THE Speech_Input SHALL maintain identical state machine behavior across all platforms

### Requirement 38: Biometric Authentication Contract

**User Story:** As a developer, I want a unified interface for biometric authentication across platforms, so that authority granting works consistently.

#### Acceptance Criteria

1. THE Biometric_Authenticator SHALL provide a platform-agnostic interface for biometric authentication
2. WHEN running on Windows, THE Biometric_Authenticator SHALL use Windows Hello
3. WHEN running on macOS, THE Biometric_Authenticator SHALL use Touch ID or Face ID
4. WHEN running on Android, THE Biometric_Authenticator SHALL use BiometricPrompt
5. WHEN running on iOS, THE Biometric_Authenticator SHALL use Face ID or Touch ID
6. THE Biometric_Authenticator SHALL return consistent AuthResult objects across all platforms
7. THE Biometric_Authenticator SHALL maintain identical failure lockout behavior across all platforms

### Requirement 39: Authority Scope Separation

**User Story:** As a security architect, I want clear separation between GURU authority and OS-level authority, so that users understand security boundaries on each platform.

#### Acceptance Criteria

1. THE System SHALL clearly distinguish between GURU authority and OS login authority
2. WHEN running on mobile (Android/iOS), THE Authority SHALL be app-level only
3. WHEN running on mobile (Android/iOS), THE Authority SHALL NOT grant system-wide control
4. WHEN running on desktop (Windows/macOS), THE Authority MAY include system-level actions
5. THE System SHALL explicitly document authority scope limitations per platform
6. THE System SHALL never create a security illusion on platforms with limited capabilities
7. THE System SHALL log authority scope in audit logs for each platform

### Requirement 40: Security Enforcement Contract

**User Story:** As a security architect, I want a unified interface for security enforcement across platforms, so that lockdown behavior is consistent.

#### Acceptance Criteria

1. THE Security_Enforcer SHALL provide a platform-agnostic interface for session locking
2. WHEN running on Windows, THE Security_Enforcer SHALL lock the workstation
3. WHEN running on macOS, THE Security_Enforcer SHALL lock the screen
4. WHEN running on Android, THE Security_Enforcer SHALL lock the app and screen if allowed
5. WHEN running on iOS, THE Security_Enforcer SHALL lock the app only
6. THE Security_Enforcer SHALL maintain identical security violation detection across all platforms
7. THE Security_Enforcer SHALL log all lockdown events with platform-specific context

### Requirement 41: Platform Capability Matrix

**User Story:** As a user, I want clear documentation of what GURU can do on each platform, so that I have accurate expectations.

#### Acceptance Criteria

1. THE System SHALL provide a capability matrix documenting features per platform
2. THE Capability_Matrix SHALL explicitly state Windows capabilities (full desktop control)
3. THE Capability_Matrix SHALL explicitly state macOS capabilities (full desktop control with permissions)
4. THE Capability_Matrix SHALL explicitly state Android capabilities (partial automation via Accessibility)
5. THE Capability_Matrix SHALL explicitly state iOS capabilities (command-limited, no system automation)
6. THE Capability_Matrix SHALL be included in user documentation
7. THE Capability_Matrix SHALL be programmatically queryable at runtime

### Requirement 42: Cross-Platform Core Logic

**User Story:** As a developer, I want core logic to be 100% platform-agnostic, so that behavior is predictable and maintainable.

#### Acceptance Criteria

1. THE Core_Logic SHALL NOT contain any platform-specific imports or API calls
2. THE Core_Logic SHALL communicate with platform backends only through PAL interfaces
3. THE Core_Logic SHALL maintain identical state machines across all platforms
4. THE Core_Logic SHALL maintain identical security invariants across all platforms
5. THE Core_Logic SHALL maintain identical audit logging behavior across all platforms
6. THE Core_Logic SHALL be testable without platform-specific dependencies
7. THE System SHALL enforce this separation through code review and automated checks

### Requirement 43: Platform Detection and Backend Selection

**User Story:** As a system architect, I want automatic platform detection and backend selection, so that GURU runs correctly on any supported platform without manual configuration.

#### Acceptance Criteria

1. THE System SHALL automatically detect the current platform at startup
2. THE System SHALL support platform detection for Windows, macOS, Android, and iOS
3. THE System SHALL raise an error for unsupported platforms (e.g., Linux desktop)
4. THE System SHALL use a factory pattern to create platform-specific backends
5. THE System SHALL inject platform backends into core logic via dependency injection
6. THE System SHALL log the detected platform and capabilities at startup
7. THE System SHALL never allow core logic to import platform-specific modules directly

