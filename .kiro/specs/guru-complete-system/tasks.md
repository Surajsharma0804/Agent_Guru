# Implementation Plan: GURU Complete Desktop AI Assistant System

## Overview

This implementation plan transforms the GURU design into a series of incremental, testable tasks. The system is already partially implemented, so tasks focus on completing missing features, fixing critical bugs, adding the new requirements (28-32) that address current issues, and implementing the Platform Abstraction Layer (PAL) for cross-platform support (Windows, macOS, Android, iOS).

## Git Workflow Requirements

**CRITICAL**: After completing each task or sub-task, you MUST:

1. **Stage changes**: `git add .` (or specific files)
2. **Commit with descriptive message**: `git commit -m "[Task X.Y] Description"`
3. **Push to remote**: `git push origin main` (or current branch)
4. **Verify push success**: Check for errors before proceeding
5. **Only then proceed** to the next task

### Commit Message Format

```
[Task X.Y] Brief description (50 chars max)

- Detailed change 1
- Detailed change 2
- Requirements validated: X.Y, X.Z
- Properties tested: N, M

Validates: Requirements X.Y, X.Z
Tests: Property N, Property M
```

### Example Commit Messages

```bash
# Task completion
git commit -m "[Task 1.1] Create PAL interface definitions

- Defined Application_Controller abstract interface
- Defined Input_Automation abstract interface
- Defined Speech_Output abstract interface
- Defined Speech_Input abstract interface
- Defined Biometric_Authenticator abstract interface
- Defined Security_Enforcer abstract interface

Validates: Requirements 33.1, 34.1-34.4, 35.1-35.3, 36.1, 37.1-37.3, 38.1, 40.1"

# Sub-task completion
git commit -m "[Task 1.2] Implement Windows backend

- Implemented WindowsApplicationController using Win32/Shell/UIAutomation
- Implemented WindowsInputAutomation using Win32 SendInput
- Implemented WindowsSpeechOutput using Windows SAPI
- Implemented WindowsSpeechInput using Whisper.cpp
- Implemented WindowsBiometricAuthenticator using Windows Hello
- Implemented WindowsSecurityEnforcer using LockWorkStation API

Validates: Requirements 34.5, 35.4, 36.3, 37.4, 38.2, 40.2"

# Property test completion
git commit -m "[Task 1.3] Write property tests for PAL interfaces

- Property 94: Core Logic Platform Isolation
- Property 95: PAL Interface Communication
- Property 96: Application Controller Consistency
- Property 97: Input Automation Capability Declaration
- Property 112: Core Logic Platform-Agnostic Testing

All tests passing with 100+ iterations each.

Validates: Requirements 33.1, 33.2, 34.9, 35.8, 42.1, 42.2, 42.6"
```

### Branch Strategy

**For Production-Grade Development**:

```
main (protected)
├── develop (integration branch)
│   ├── feature/pal-foundation (Task 1)
│   ├── feature/core-refactoring (Task 2)
│   ├── feature/authority-scope (Task 3)
│   ├── feature/macos-backend (Task 4)
│   ├── feature/android-backend (Task 5)
│   └── feature/ios-backend (Task 6)
```

**Workflow**:
1. Create feature branch: `git checkout -b feature/task-name`
2. Complete sub-task → commit → push
3. Complete all sub-tasks → merge to develop
4. Test on develop → merge to main (after review)

### Rollback Safety

Each commit provides a rollback point:
```bash
# View commit history
git log --oneline

# Rollback to specific commit
git reset --hard <commit-hash>

# Rollback last commit (keep changes)
git reset --soft HEAD~1
```

### CI/CD Integration

Each push triggers:
- Automated tests (unit, property, integration)
- Security scans (dependency audit, code analysis)
- Build verification (all platforms)
- Documentation generation

**Push will fail if**:
- Tests fail
- Security vulnerabilities detected
- Code coverage drops below 85%
- Linting errors present

## Tasks

- [-] 1. Implement Platform Abstraction Layer (PAL) Foundation
  - Create PAL interface definitions
  - Implement Windows backend (reference implementation)
  - Create platform capability matrix
  - _Requirements: 33, 34, 35, 36, 37, 38, 39, 40, 41, 42_

- [x] 1.1 Create PAL interface definitions
  - Define Application_Controller abstract interface
  - Define Input_Automation abstract interface
  - Define Speech_Output abstract interface
  - Define Speech_Input abstract interface
  - Define Biometric_Authenticator abstract interface
  - Define Security_Enforcer abstract interface
  - _Requirements: 33.1, 34.1-34.4, 35.1-35.3, 36.1, 37.1-37.3, 38.1, 40.1_
  - **Git: Commit and push after completion**
  - **Commit message**: `[Task 1.1] Create PAL interface definitions`

- [x] 1.2 Implement Windows backend (reference implementation)
  - Implement WindowsApplicationController using Win32/Shell/UIAutomation
  - Implement WindowsInputAutomation using Win32 SendInput
  - Implement WindowsSpeechOutput using Windows SAPI
  - Implement WindowsSpeechInput using Whisper.cpp
  - Implement WindowsBiometricAuthenticator using Windows Hello
  - Implement WindowsSecurityEnforcer using LockWorkStation API
  - _Requirements: 34.5, 35.4, 36.3, 37.4, 38.2, 40.2_
  - **Git: Commit and push after completion**
  - **Commit message**: `[Task 1.2] Implement Windows backend`

- [x] 1.3 Write property tests for PAL interfaces
  - **Property 94: Core Logic Platform Isolation**
  - **Property 95: PAL Interface Communication**
  - **Property 96: Application Controller Consistency**
  - **Property 97: Input Automation Capability Declaration**
  - **Property 112: Core Logic Platform-Agnostic Testing**
  - **Validates: Requirements 33.1, 33.2, 34.9, 35.8, 42.1, 42.2, 42.6**
  - **Git: Commit and push after completion**
  - **Commit message**: `[Task 1.3] Write property tests for PAL interfaces`

- [x] 1.4 Create platform capability matrix
  - Document Windows capabilities (full desktop control)
  - Document macOS capabilities (full with permissions)
  - Document Android capabilities (partial automation)
  - Document iOS capabilities (command-limited)
  - Implement runtime capability query API
  - _Requirements: 41.1-41.7_
  - **Git: Commit and push after completion**
  - **Commit message**: `[Task 1.4] Create platform capability matrix`

- [x] 1.5 Write property tests for capability matrix
  - **Property 108: Capability Matrix Runtime Query**
  - **Validates: Requirements 41.7**
  - **Git: Commit and push after completion**
  - **Commit message**: `[Task 1.5] Write property tests for capability matrix`

- [x] 1.6 Implement platform detection and backend factory
  - Implement PlatformDetector class
  - Implement PlatformBackendFactory class
  - Implement backend creation methods for all 6 interfaces
  - Implement error handling for unsupported platforms
  - _Requirements: 43.1, 43.2, 43.3, 43.4_
  - **Git: Commit and push after completion**
  - **Commit message**: `[Task 1.6] Implement platform detection and backend factory`

- [x] 1.7 Write property tests for platform detection
  - **Property 113: Automatic Platform Detection**
  - **Property 114: Unsupported Platform Error**
  - **Property 115: Backend Factory Creation**
  - **Validates: Requirements 43.1, 43.2, 43.3, 43.4**
  - **Git: Commit and push after completion**
  - **Commit message**: `[Task 1.7] Write property tests for platform detection`
  - **Final: Push entire Task 1 feature branch to remote**

- [x] 2. Refactor Core Logic to Use PAL
  - Remove platform-specific imports from core logic
  - Update Command_Executor to use Application_Controller interface
  - Update TTS_Service to use Speech_Output interface
  - Update Voice_Interface to use Speech_Input interface
  - Update Authority_State_Machine to use Biometric_Authenticator interface
  - Update Intrusion_Detector to use Security_Enforcer interface
  - _Requirements: 42.1, 42.2_
  - **Git: Create feature branch** `git checkout -b feature/core-refactoring`

- [x] 2.1 Remove platform-specific imports from core logic
  - Audit all core logic modules for platform-specific imports
  - Replace Win32 imports with PAL interface calls
  - Replace Windows SAPI imports with Speech_Output interface
  - Replace Windows Hello imports with Biometric_Authenticator interface
  - _Requirements: 42.1_
  - **Git: Commit and push after completion**
  - **Commit message**: `[Task 2.1] Remove platform-specific imports from core logic`

- [x] 2.2 Update core logic files to use PAL interfaces
  - Refactored TTS_Service to use Speech_Output interface
  - Refactored Voice_Interface to use Speech_Input interface
  - Verified Authority_State_Machine is already platform-agnostic
  - Refactored Intrusion_Detector to use Security_Enforcer interface
  - All files pass diagnostics (no syntax errors)
  - _Requirements: 34.1-34.4, 35.1-35.3, 36.1, 37.1-37.3, 38.1, 40.1, 42.2_
  - **Git: Commit and push after completion**
  - **Commit message**: `[Task 2.2] Update core logic files to use PAL interfaces`

- [x] 2.3 Write property tests for refactored core logic
  - **Property 94: Core Logic Platform Isolation**
  - **Property 109: Core Logic State Machine Consistency**
  - **Property 110: Core Logic Security Invariants**
  - **Property 111: Core Logic Audit Logging Consistency**
  - **Property 116: Dependency Injection**
  - **Property 117: Platform Logging at Startup**
  - **Validates: Requirements 42.1, 42.3, 42.4, 42.5, 43.5, 43.6, 43.7**
  - **Git: Commit and push after completion**
  - **Commit message**: `[Task 2.3] Write property tests for refactored core logic`
  - **Final: Push entire Task 2 feature branch to remote**

- [x] 3. Implement Authority Scope Separation
  - Add authority scope tracking (system-wide vs app-level)
  - Implement platform-specific authority scope logic
  - Update audit logging to include authority scope
  - _Requirements: 39_

- [x] 3.1 Add authority scope tracking
  - Extend Authority_State_Machine with scope field
  - Implement get_authority_scope() method
  - Implement platform detection logic
  - _Requirements: 39.1_

- [x] 3.2 Implement platform-specific authority scope
  - On Windows/macOS: Set scope to "system-wide"
  - On Android/iOS: Set scope to "app-level"
  - Enforce scope restrictions in Command_Executor
  - _Requirements: 39.2, 39.3, 39.4_

- [x] 3.3 Update audit logging for authority scope
  - Log platform in authority grant events
  - Log authority scope in authority grant events
  - Log capability limitations in authority grant events
  - _Requirements: 39.7_

- [x] 3.4 Write property tests for authority scope
  - **Property 103: Authority Scope Logging**
  - **Property 104: Mobile Authority Scope Restriction**
  - **Property 105: Desktop Authority Scope Permission**
  - **Validates: Requirements 39.2, 39.3, 39.4, 39.7**

- [x] 4. Implement macOS Backend
  - Implement macOSApplicationController using LaunchServices
  - Implement macOSInputAutomation using CGEvent
  - Implement macOSSpeechOutput using NSSpeechSynthesizer
  - Implement macOSSpeechInput using Whisper.cpp
  - Implement macOSBiometricAuthenticator using Touch ID/Face ID
  - Implement macOSSecurityEnforcer using CGSession
  - _Requirements: 34.6, 35.5, 36.4, 37.4, 38.3, 40.3_

- [x] 4.1 Implement macOS application control
  - Use LaunchServices for app launching
  - Use Apple Events for app control
  - Use NSWorkspace for app discovery
  - _Requirements: 34.6_

- [x] 4.2 Implement macOS input automation
  - Use CGEvent for keyboard simulation
  - Use CGEvent for mouse simulation
  - Require Accessibility permission
  - _Requirements: 35.5_

- [x] 4.3 Write property tests for macOS backend
  - **Property 96: Application Controller Consistency**
  - **Property 98: Speech Output Personality Consistency**
  - **Property 99: Speech Output Priority Queue Cross-Platform**
  - **Property 100: Speech Input State Machine Consistency**
  - **Property 101: Biometric Authentication Result Consistency**
  - **Validates: Requirements 34.9, 36.2, 36.7, 37.7, 38.6**

- [x] 5. Implement Android Backend
  - Implement AndroidApplicationController using Intent system
  - Implement AndroidInputAutomation using Accessibility Service
  - Implement AndroidSpeechOutput using Android TTS
  - Implement AndroidSpeechInput using Whisper or system STT
  - Implement AndroidBiometricAuthenticator using BiometricPrompt
  - Implement AndroidSecurityEnforcer for app + screen lock
  - _Requirements: 34.7, 35.6, 36.5, 37.5, 38.4, 40.4_

- [x] 5.1 Implement Android application control
  - Use Intent system for app launching (startActivity)
  - Use PackageManager for app discovery
  - Use ActivityManager for running app detection
  - _Requirements: 34.7_

- [x] 5.2 Implement Android input automation
  - Use Accessibility Service for UI automation
  - Require user permission grant
  - Document partial automation capabilities
  - _Requirements: 35.6_

- [x] 5.3 Write property tests for Android backend
  - **Property 97: Input Automation Capability Declaration**
  - **Property 102: Biometric Failure Lockout Cross-Platform**
  - **Property 106: Security Enforcer Lock Scope Declaration**
  - **Property 107: Security Violation Detection Cross-Platform**
  - **Validates: Requirements 35.8, 38.7, 40.4, 40.6**

- [x] 6. Implement iOS Backend
  - Implement iOSApplicationController using deep links
  - Implement iOSSpeechOutput using AVSpeechSynthesizer
  - Implement iOSSpeechInput using system STT
  - Implement iOSBiometricAuthenticator using Face ID/Touch ID
  - Implement iOSSecurityEnforcer for app-only lock
  - Document severe iOS limitations
  - _Requirements: 34.8, 36.6, 37.6, 38.5, 40.5_

- [x] 6.1 Implement iOS application control (limited)
  - Use openURL for deep links only
  - Document inability to close apps
  - Document limited app discovery
  - _Requirements: 34.8_

- [x] 6.2 Document iOS limitations explicitly
  - No input automation capability
  - No system-wide control
  - App-level authority only
  - System STT mandatory (no local models)
  - _Requirements: 35.7, 39.3, 39.6_

- [x] 6.3 Write property tests for iOS backend
  - **Property 104: Mobile Authority Scope Restriction**
  - **Property 106: Security Enforcer Lock Scope Declaration**
  - **Validates: Requirements 39.2, 40.5**

- [x] 7. Checkpoint - Test Cross-Platform PAL
  - Ensure all PAL interface tests pass
  - Ensure all platform backend tests pass
  - Verify core logic is platform-agnostic
  - Verify capability matrix is accurate
  - Ask the user if questions arise

- [x] 8. Fix Critical Voice Interface Issues
  - Implement wake word stripping to prevent downstream interference
  - Add DICTATION_MODE state to voice interface state machine
  - Implement dictation mode entry/exit logic
  - _Requirements: 29, 30_

- [x] 1.1 Implement wake word stripping algorithm
  - Add wake word removal function to voice interface
  - Strip "hey guru", "hello guru", "hi guru" (case-insensitive)
  - Ensure stripped text is passed to all downstream systems
  - _Requirements: 30.1, 30.2, 30.3, 30.4, 30.5_

- [x] 1.2 Write property test for wake word stripping
  - **Property 79: Wake Word Removal in Active State**
  - **Property 80: Intent Pre-Filter Never Sees Wake Word**
  - **Property 81: Command Executor Never Sees Wake Word**
  - **Property 82: LLM Never Sees Wake Word**
  - **Validates: Requirements 30.1, 30.2, 30.3, 30.4**

- [x] 1.3 Add DICTATION_MODE to voice interface state machine
  - Extend VoiceState enum with DICTATION_MODE
  - Implement state transition logic for dictation entry/exit
  - Add 2-second silence timeout for dictation mode
  - Add "done"/"stop writing" command detection
  - _Requirements: 29.1, 29.2, 29.6, 29.7_

- [x] 1.4 Write property tests for dictation mode
  - **Property 73: Dictation Mode Entry**
  - **Property 77: Dictation Mode Exit on Silence**
  - **Property 78: Dictation Mode Exit on Command**
  - **Validates: Requirements 29.2, 29.6, 29.7**

- [x] 2. Implement Single Response Ownership System
  - Create response ownership coordinator
  - Implement subsystem suppression logic
  - Add response priority enforcement
  - _Requirements: 28_

- [x] 2.1 Create ResponseOwnershipCoordinator class
  - Track which subsystem currently owns response
  - Implement ownership priority: Command_Executor > Error_Handler > Conversation_Manager
  - Add methods to claim/release ownership
  - _Requirements: 28.1_

- [x] 2.2 Integrate ownership coordinator with Command_Executor
  - Claim ownership when action execution starts
  - Suppress Conversation_Manager responses during execution
  - Release ownership when action completes
  - _Requirements: 28.2, 28.4_

- [x] 2.3 Integrate ownership coordinator with TTS_Service
  - Limit TTS to action phrases when Command_Executor owns response
  - Allow conversational speech only when Conversation_Manager owns response
  - _Requirements: 28.3_

- [x] 2.4 Write property tests for response ownership
  - **Property 68: Exclusive Response Ownership**
  - **Property 69: Action Execution Suppresses Conversation**
  - **Property 70: Action Success Speaks Only Result**
  - **Property 71: Action Failure Speaks Only Reason**
  - **Property 72: No Duplicate Responses**
  - **Validates: Requirements 28.1, 28.2, 28.4, 28.5, 28.6, 28.7**

- [-] 3. Enhance Intent Pre-Filter with Deterministic-First Guarantee
  - Implement confidence threshold enforcement (≥ 0.7)
  - Add LLM bypass tracking and logging
  - Implement bypass rate monitoring
  - _Requirements: 31_

- [x] 3.1 Update Intent_Pre_Filter classification logic
  - Enforce confidence ≥ 0.7 threshold for deterministic routing
  - Add bypass_llm flag to ActionIntent
  - Implement parameter completeness check
  - _Requirements: 31.1, 31.2_

- [x] 3.2 Add LLM bypass logging and monitoring
  - Log whether LLM was bypassed for each command
  - Track bypass rate over rolling window of 100 commands
  - Alert if bypass rate drops below 70%
  - _Requirements: 31.4, 31.5_

- [x] 3.3 Restrict LLM usage to genuine ambiguity
  - Only invoke LLM for ambiguous targets, vague pronouns, or clarification
  - Add explicit checks before LLM invocation
  - _Requirements: 31.3_

- [x] 3.4 Write property tests for deterministic-first guarantee
  - **Property 84: High Confidence Bypasses LLM**
  - **Property 85: Complete Parameters Bypass LLM**
  - **Property 86: LLM Only for Ambiguity**
  - **Property 88: High Bypass Rate Target**
  - **Validates: Requirements 31.1, 31.2, 31.3, 31.6**

- [x] 4. Implement Human Co-Worker Speech Contract
  - Create speech phrase validator
  - Implement approved/forbidden phrase enforcement
  - Update TTS_Service to enforce contract
  - _Requirements: 32_

- [x] 4.1 Create SpeechContractValidator class
  - Define approved action phrases: "Opening [app]", "Done", "Typed", "Sent", "Failed: [reason]"
  - Define forbidden phrases: "How can I help you?", "Sure, I can...", "Let me know if..."
  - Implement validation logic
  - _Requirements: 32.4, 32.5, 32.6, 32.7_

- [x] 4.2 Integrate speech contract with TTS_Service
  - Validate all TTS output against speech contract
  - Enforce verb-first ≤ 5 words during action execution
  - Reject forbidden phrases
  - _Requirements: 32.1, 32.2_

- [x] 4.3 Write property tests for speech contract
  - **Property 89: Action Speech Brevity**
  - **Property 90: No Questions During Actions**
  - **Property 91: No Chatbot Greeting Phrases**
  - **Property 92: No Chatbot Confirmation Phrases**
  - **Property 93: Approved Action Phrases Only**
  - **Validates: Requirements 32.1, 32.2, 32.4, 32.5, 32.6, 32.7**

- [-] 5. Complete Command Executor Implementation
  - Verify universal application support
  - Implement WhatsApp automation with fallback
  - Add exact text dictation support
  - _Requirements: 2, 15, 26_

- [x] 5.1 Verify and test universal application launcher
  - Test 100+ application database
  - Test dynamic discovery for unlisted apps
  - Verify 1-second launch performance
  - _Requirements: 2.1, 2.2, 2.3, 2.7_

- [x] 5.2 Implement WhatsApp Desktop automation with fallback
  - Implement UI Automation for WhatsApp Desktop
  - Add fallback to manual prompt if automation fails
  - Implement contact fuzzy matching (80% threshold)
  - Implement message send verification
  - _Requirements: 26.1, 26.2, 26.3, 26.4, 26.5, 26.6_

- [x] 5.3 Write property tests for WhatsApp automation
  - **Property 60: WhatsApp Desktop Targeting**
  - **Property 61: Startup Delay Handling**
  - **Property 62: Message Send Verification**
  - **Property 63: Contact Name Fuzzy Matching**
  - **Validates: Requirements 26.1, 26.4, 26.5, 26.6**

- [x] 5.4 Implement exact text dictation
  - Integrate with DICTATION_MODE from voice interface
  - Bypass Intent_Pre_Filter and LLM in dictation mode
  - Type exact text without interpretation
  - _Requirements: 2.5, 14, 21.6, 29.3, 29.4_

- [x] 5.5 Write property tests for exact text dictation
  - **Property 9: Exact Text Dictation**
  - **Property 74: Intent Pre-Filter Bypass in Dictation**
  - **Property 75: LLM Bypass in Dictation**
  - **Validates: Requirements 2.5, 14, 21.6, 29.3, 29.4**

- [x] 6. Checkpoint - Test Voice and Command Integration
  - Ensure all voice interface tests pass
  - Ensure all command execution tests pass
  - Verify wake word stripping works end-to-end
  - Verify dictation mode works end-to-end
  - Ask the user if questions arise

- [x] 7. Complete Authority State Machine and Security
  - Verify biometric authentication integration
  - Test authority timeout and revocation
  - Test security lockout scenarios
  - _Requirements: 3, 4, 6_

- [x] 7.1 Verify biometric authentication flow
  - Test Windows Hello integration
  - Test fingerprint and face recognition
  - Test failed authentication lockout (3 attempts)
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 7.2 Write property tests for authority state machine
  - **Property 18: Initial State is UNARMED**
  - **Property 19: Biometric Authentication Grants Authority**
  - **Property 20: Commands Require ARMED State**
  - **Property 21: Inactivity Timeout Revokes Authority**
  - **Property 22: Security Violations Trigger Lockdown**
  - **Property 23: LOCKED State Blocks All Commands**
  - **Property 25: Failed Authentication Lockout**
  - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.5, 6.2**

- [x] 7.3 Test intrusion detection and response
  - Test repeated failed authentication detection
  - Test suspicious command pattern detection
  - Test workstation lock invocation
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 7.4 Write property tests for intrusion detection
  - **Property 25: Failed Authentication Lockout**
  - **Validates: Requirements 6.2**

- [x] 8. Complete Audit Logger Implementation
  - Verify cryptographic signature chain
  - Test tamper detection
  - Test log rotation and compression
  - _Requirements: 5_

- [x] 8.1 Verify audit log signature chain
  - Test HMAC-SHA256 signature computation
  - Test signature chain integrity
  - Test tamper detection
  - _Requirements: 5.4, 5.5, 5.6_

- [x] 8.2 Write property tests for audit logging
  - **Property 26: Command Execution Logging Completeness**
  - **Property 27: Cryptographic Signature Integrity**
  - **Property 28: Signature Chain Integrity**
  - **Property 29: Tamper Detection**
  - **Property 30: Sensitive Data Redaction**
  - **Validates: Requirements 5.1, 5.4, 5.5, 5.6, 5.8**

- [x] 8.3 Test log rotation and compression
  - Test daily log rotation
  - Test old log compression
  - _Requirements: 5.7_

- [x] 9. Complete LLM Adapter with Timeout and Fallback
  - Implement multi-provider support (Ollama, OpenAI, Gemini)
  - Implement 10-second timeout with template fallback
  - Implement response caching
  - _Requirements: 7, 24_

- [x] 9.1 Implement LLM provider abstraction
  - Create provider interface
  - Implement Ollama provider
  - Implement OpenAI provider (optional)
  - Implement Gemini provider (optional)
  - _Requirements: 7.1_

- [x] 9.2 Implement timeout and fallback mechanism
  - Add 10-second timeout to all LLM requests
  - Implement template response fallback
  - _Requirements: 7.5_

- [x] 9.3 Write property tests for LLM adapter
  - **Property 37: Timeout Fallback to Templates**
  - **Property 38: No Cloud Data Without Consent**
  - **Property 39: Response Caching**
  - **Validates: Requirements 7.5, 7.6, 7.7**

- [x] 10. Complete TTS Service with Priority Queue
  - Verify Windows SAPI integration
  - Test priority queue ordering
  - Test volume bypass (avoid 1% lock)
  - _Requirements: 9, 23_

- [x] 10.1 Verify TTS priority queue
  - Test CRITICAL > HIGH > NORMAL > LOW ordering
  - Test interrupt functionality
  - _Requirements: 9.3, 9.4_

- [x] 10.2 Write property tests for TTS service
  - **Property 33: Priority Queue Ordering**
  - **Property 34: Silence During Dictation**
  - **Property 35: Concise Action Speech**
  - **Property 36: No Chatbot Phrases**
  - **Validates: Requirements 9.4, 23.2, 23.1, 23.6, 23.7**

- [x] 10.3 Verify Windows SAPI volume bypass
  - Test that TTS speaks at full volume
  - Verify Volume Mixer is bypassed
  - _Requirements: 9.2, 9.5_

- [x] 11. Checkpoint - Test Security and Audio Systems
  - Ensure all authority tests pass
  - Ensure all audit logging tests pass
  - Ensure all TTS tests pass
  - Verify security lockout works end-to-end
  - Ask the user if questions arise

- [x] 12. Complete Memory System with Encryption
  - Implement AES-256-GCM encryption ✓
  - Implement vector search with FAISS ✓ (TF-IDF local implementation)
  - Implement automatic purging (90 days) ✓
  - Verify memory isolation from commands ✓
  - _Requirements: 10, 27_
  - **Status: COMPLETED - All sub-tasks completed, all property tests passing**

- [x] 12.1 Implement conversation encryption
  - Implement AES-256-GCM encryption
  - Derive encryption keys from biometric authentication
  - Store encrypted conversations in SQLite
  - _Requirements: 10.1, 10.2_
  - **Status: COMPLETED**

- [x] 12.2 Implement vector search
  - Integrate sentence-transformers for embeddings
  - Implement FAISS index for semantic search
  - _Requirements: 10.3_
  - **Status: COMPLETED (using TF-IDF local implementation)**

- [x] 12.3 Write property tests for memory system
  - **Property 43: Conversation Encryption** ✓
  - **Property 44: Semantic Search Accuracy** ✓
  - **Property 45: Conversation Retrieval Round-Trip** ✓
  - **Property 46: Automatic Purging** ✓
  - **Property 47: No Plaintext Keys** ✓
  - **Property 48: Memory Isolation from Commands** ✓
  - **Property 49: Separate Storage for Audit and Conversation** ✓
  - **Validates: Requirements 10.1, 10.3, 10.4, 10.5, 10.6, 27.2, 27.3, 27.6**
  - **Status: COMPLETED - All 7 properties passing with 100+ iterations each**

- [x] 12.4 Implement automatic purging
  - Implement 90-day retention policy
  - Schedule periodic purge checks
  - _Requirements: 10.5_
  - **Status: COMPLETED**

- [x] 13. Complete Failure Orchestrator
  - Implement component health monitoring (30-second intervals)
  - Implement automatic restart (up to 3 attempts)
  - Implement graceful degradation
  - _Requirements: 11_

- [x] 13.1 Implement health monitoring
  - Create health check interface for all components
  - Implement 30-second periodic health checks
  - Track failure counts per component
  - _Requirements: 11.1_

- [x] 13.2 Implement automatic recovery
  - Attempt restart on first and second failures
  - Mark as permanently failed after third failure
  - Implement graceful degradation for dependent features
  - _Requirements: 11.2, 11.3, 11.5_

- [x] 13.3 Write property tests for failure orchestrator
  - **Property 50: Periodic Health Monitoring**
  - **Property 51: Automatic Component Restart**
  - **Property 52: Permanent Failure After Three Attempts**
  - **Property 53: Graceful Degradation**
  - **Property 54: Failure Logging**
  - **Validates: Requirements 11.1, 11.2, 11.3, 11.5, 11.6**

- [x] 14. Complete Thread Safety Implementation
  - Verify Thread_Safe_Bridge signal/slot connections
  - Test cross-thread communication
  - Verify no direct Qt widget access from background threads
  - _Requirements: 8_

- [x] 14.1 Verify thread-safe bridge
  - Test signal emission from background threads
  - Test slot execution in main thread
  - Verify QueuedConnection usage
  - _Requirements: 8.1, 8.2_

- [x] 14.2 Write property tests for thread safety
  - **Property 31: Cross-Thread Signal Delivery**
  - **Property 32: No Direct Widget Access from Background Threads**
  - **Validates: Requirements 8.2, 8.3, 8.6**

- [x] 15. Complete Permission Model
  - Implement UAC prompt integration
  - Implement permission elevation logging
  - Implement skill permission validation
  - _Requirements: 25_

- [x] 15.1 Implement UAC integration
  - Trigger UAC prompt for admin-level actions
  - Pause execution until user responds
  - Log all elevation requests
  - _Requirements: 25.2, 25.3, 25.4_

- [x] 15.2 Write property tests for permission model
  - **Property 55: UAC Prompt for Admin Actions** ✓ PASSING
  - **Property 56: Execution Pause During UAC** ✓ PASSING
  - **Property 57: Permission Elevation Logging** ✓ PASSING
  - **Validates: Requirements 25.2, 25.3, 25.4**

- [x] 15.3 Implement skill permission validation
  - Require explicit permission declarations in skill manifests
  - Reject skills with excessive permissions
  - _Requirements: 25.5, 25.6_

- [x] 15.4 Write property tests for skill permissions
  - **Property 58: Skill Permission Declaration** ✓ PASSING
  - **Property 59: Excessive Permission Rejection** ✓ PASSING
  - **Validates: Requirements 25.5, 25.6**

- [x] 16. Checkpoint - Test All Core Systems
  - Ensure all memory system tests pass
  - Ensure all failure orchestrator tests pass
  - Ensure all thread safety tests pass
  - Ensure all permission model tests pass
  - Ask the user if questions arise

- [x] 17. Complete Configuration Management
  - Implement configuration hierarchy (user > workspace > system)
  - Implement Ollama model auto-detection
  - Implement configuration validation
  - _Requirements: 17, 18_

- [x] 17.1 Implement configuration hierarchy
  - Load configuration from %USERPROFILE%\.guru\
  - Support user, workspace, and system defaults
  - Implement configuration merging
  - _Requirements: 17.1, 17.2, 17.3, 17.6_

- [x] 17.2 Implement Ollama model auto-detection
  - Query Ollama for installed models
  - Select appropriate models for conversation, intent, reasoning
  - Generate llm_config.json automatically
  - _Requirements: 18.1, 18.2, 18.3, 18.4_

- [x] 18. Complete Setup Wizard
  - Implement first-run detection
  - Implement biometric configuration page
  - Implement biometric testing
  - _Requirements: 16_

- [x] 18.1 Implement setup wizard flow
  - Detect first run
  - Guide through microphone/speaker permissions
  - Guide through profile creation
  - Guide through biometric configuration
  - Guide through preferences
  - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.6_

- [x] 18.2 Implement biometric testing
  - Detect Windows Hello availability
  - Detect fingerprint/face hardware
  - Provide "Test Biometric Authentication" button
  - _Requirements: 16.5_

- [x] 19. Complete Diagnostic Tools
  - Implement comprehensive diagnostic script
  - Test all components
  - Provide detailed error messages
  - _Requirements: 19_

- [x] 19.1 Implement diagnostic script
  - Test TTS synthesis and audio output
  - Test voice recognition and wake word detection
  - Test biometric authentication availability
  - Test LLM connectivity and response times
  - Report pass/fail for each test
  - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6_

- [x] 20. Complete Error Handling
  - Implement error classification
  - Implement recovery procedures
  - Implement actionable error messages
  - _Requirements: 20_

- [x] 20.1 Implement error handling strategy
  - Implement error classification (RECOVERABLE, DEGRADED, CRITICAL, FATAL)
  - Implement automatic retry for transient failures
  - Never retry security failures
  - _Requirements: 20.1, 20.2, 20.5, 20.6_

- [x] 20.2 Write property tests for error handling
  - **Property 64: Exception Isolation**
  - **Property 65: Actionable Error Messages**
  - **Property 66: Transient Failure Retry**
  - **Property 67: No Security Failure Retry**
  - **Validates: Requirements 20.1, 20.2, 20.3, 20.4, 20.5, 20.6**

- [x] 28. Final Integration Testing
  - Test complete voice command flow (wake word → action → confirmation)
  - Test security lockout flow (3 failed auth → locked → unlock)
  - Test component failure recovery flow
  - Test all 112 correctness properties
  - Test cross-platform PAL behavior
  - _All Requirements_

- [x] 28.1 Run full integration test suite
  - Test end-to-end voice command execution
  - Test security lockout and recovery
  - Test component failure and recovery
  - Test all critical paths
  - Test cross-platform capability matrix

- [x] 28.2 Run all property-based tests
  - Execute all 117 property tests with 100+ iterations each
  - Verify all properties pass
  - Fix any failing properties

- [x] 29. Final Checkpoint - System Ready for Production
  - All tests pass (unit, property, integration)
  - All 43 requirements validated
  - All 117 properties verified
  - System performs within specified metrics
  - Cross-platform PAL verified on all target platforms
  - Ask the user for final approval

- [x] 30. Production Cleanup and Optimization
  - Remove all unnecessary files, dead code, and unwanted artifacts
  - Optimize codebase for production deployment
  - Verify zero errors, zero warnings, zero failed tests
  - _Requirements: All (final validation)_
  - **Git: Create cleanup branch** `git checkout -b cleanup/production-ready`

- [x] 30.1 Identify and remove dead code
  - Scan all source files for unused functions
  - Scan all source files for unused classes
  - Scan all source files for unused imports
  - Scan all source files for commented-out code
  - Remove unreachable code paths
  - Remove deprecated functions and classes
  - _Tools: pylint --disable=all --enable=W0612,W0613 (Python), ts-prune (TypeScript)_
  - **Git: Commit and push after completion**
  - **Commit message**: `[Task 30.1] Remove dead code`

- [x] 30.2 Remove unnecessary test files
  - Identify duplicate test files
  - Remove obsolete test fixtures
  - Remove unused mock objects
  - Remove test files for removed features
  - Consolidate redundant test cases
  - Keep only essential property tests and unit tests
  - _Verify: All remaining tests still pass_
  - **Git: Commit and push after completion**
  - **Commit message**: `[Task 30.2] Remove unnecessary test files`

- [x] 30.3 Clean up configuration files
  - Remove unused configuration entries
  - Remove obsolete environment variables
  - Remove deprecated configuration files
  - Consolidate duplicate configurations
  - Validate all remaining configurations
  - _Files: .env, config.json, llm_config.json, user_config.json_
  - **Git: Commit and push after completion**
  - **Commit message**: `[Task 30.3] Clean up configuration files`

- [x] 30.4 Remove temporary and build artifacts
  - Remove all __pycache__ directories
  - Remove all .pyc files
  - Remove all node_modules (will be reinstalled)
  - Remove all build/ and dist/ directories (except production builds)
  - Remove all .pytest_cache directories
  - Remove all .mypy_cache directories
  - Remove all .tsbuildinfo files
  - Remove all log files (except audit logs)
  - Remove all temporary files (*.tmp, *.temp, *.bak)
  - _Command: npm run clean_
  - **Git: Commit and push after completion**
  - **Commit message**: `[Task 30.4] Remove temporary and build artifacts`

- [x] 30.5 Remove unused dependencies
  - Analyze Python dependencies (pip-autoremove, pipdeptree)
  - Analyze Node.js dependencies (depcheck, npm-check)
  - Remove unused Python packages from requirements.txt
  - Remove unused Node.js packages from package.json
  - Update dependency versions to latest stable
  - Run security audit after cleanup
  - _Commands: pip-autoremove, npm prune, npm audit fix_
  - **Git: Commit and push after completion**
  - **Commit message**: `[Task 30.5] Remove unused dependencies`

- [x] 30.6 Optimize import statements
  - Remove unused imports (Python: autoflake, TypeScript: ts-unused-exports)
  - Sort imports alphabetically (Python: isort, TypeScript: organize-imports)
  - Group imports by category (stdlib, third-party, local)
  - Remove wildcard imports (from module import *)
  - _Commands: autoflake --remove-all-unused-imports, organize-imports_
  - **Git: Commit and push after completion**
  - **Commit message**: `[Task 30.6] Optimize import statements`

- [x] 30.7 Remove debug and development code
  - Remove all print() statements (use logging instead)
  - Remove all console.log() statements (use proper logging)
  - Remove all debugger statements
  - Remove all TODO comments (create issues for remaining work)
  - Remove all FIXME comments (fix or create issues)
  - Remove all development-only code paths
  - Remove all test data generators (keep only for tests)
  - _Search: grep -r "print\(", grep -r "console\.log", grep -r "debugger"_
  - **Git: Commit and push after completion**
  - **Commit message**: `[Task 30.7] Remove debug and development code`

- [x] 30.8 Clean up documentation files
  - Remove outdated documentation
  - Remove duplicate README files
  - Consolidate scattered documentation
  - Update all documentation to reflect final state
  - Remove draft documents
  - Remove migration guides (keep only CHANGELOG)
  - Archive old design documents
  - _Keep: README.md, CHANGELOG.md, LICENSE, SECURITY.md, API docs_
  - **Git: Commit and push after completion**
  - **Commit message**: `[Task 30.8] Clean up documentation files`

- [x] 30.9 Remove unused assets and resources
  - Remove unused images
  - Remove unused icons (keep only platform-required)
  - Remove unused fonts
  - Remove unused audio files
  - Remove duplicate assets
  - Optimize remaining images (compress without quality loss)
  - _Tools: imageoptim, svgo, pngquant_
  - **Git: Commit and push after completion**
  - **Commit message**: `[Task 30.9] Remove unused assets and resources`

- [x] 30.10 Optimize database and storage
  - Remove test databases
  - Remove old audit logs (archive if needed)
  - Remove old conversation history (archive if needed)
  - Vacuum SQLite databases (VACUUM command)
  - Optimize database indexes
  - Compress archived data
  - _Files: audit_logs/, memory/, *.db_
  - **Git: Commit and push after completion**
  - **Commit message**: `[Task 30.10] Optimize database and storage`

- [x] 30.11 Remove development tools and scripts
  - Remove development-only scripts
  - Remove test data generation scripts
  - Remove migration scripts (after successful migration)
  - Remove debugging utilities
  - Keep only production-necessary scripts
  - _Directory: scripts/ (review each file)_
  - **Git: Commit and push after completion**
  - **Commit message**: `[Task 30.11] Remove development tools and scripts`

- [x] 30.12 Verify zero errors, warnings, and failures
  - Run full linting (zero errors, zero warnings)
  - Run full type checking (zero errors)
  - Run full test suite (zero failures)
  - Run security scans (zero vulnerabilities)
  - Run code coverage (≥ 85%)
  - Run performance benchmarks (all metrics met)
  - _Commands: npm run lint, npm run test, npm run security:scan_
  - **Git: Commit and push after completion**
  - **Commit message**: `[Task 30.12] Verify zero errors, warnings, and failures`

- [x] 30.13 Generate production build
  - Build for all platforms (Windows, macOS, Android, iOS)
  - Verify build sizes are optimal
  - Verify no debug symbols in production builds
  - Verify all assets are included
  - Test production builds on all platforms
  - _Commands: npm run build, npm run build:desktop, npm run build:android_
  - **Git: Commit and push after completion**
  - **Commit message**: `[Task 30.13] Generate production build`

- [x] 30.14 Update .gitignore and cleanup rules
  - Add all build artifacts to .gitignore
  - Add all temporary files to .gitignore
  - Add all cache directories to .gitignore
  - Add all log files to .gitignore (except audit logs)
  - Add all IDE-specific files to .gitignore
  - Verify no ignored files are tracked
  - _File: .gitignore_
  - **Git: Commit and push after completion**
  - **Commit message**: `[Task 30.14] Update .gitignore and cleanup rules`

- [x] 30.15 Final verification and documentation
  - Run complete test suite one final time
  - Verify all 43 requirements are met
  - Verify all 117 properties pass
  - Generate final code coverage report
  - Generate final security audit report
  - Generate final performance benchmark report
  - Update CHANGELOG.md with all changes
  - Update README.md with final instructions
  - Create production deployment guide
  - **Git: Commit and push after completion**
  - **Commit message**: `[Task 30.15] Final verification and documentation`
  - **Final: Merge cleanup branch to develop, then to main**

- [-] 31. Production Release
  - Tag release version
  - Generate release notes
  - Create production deployment package
  - Archive development artifacts
  - Celebrate successful completion! 🎉
  - **Git: Tag release** `git tag -a v1.0.0 -m "Production Release v1.0.0"`
  - **Git: Push tag** `git push origin v1.0.0`

## Notes

### Implementation Requirements

- All tasks are required for comprehensive cross-platform system implementation
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (100+ iterations each)
- Unit tests validate specific examples and edge cases
- PAL implementation (tasks 1-7) establishes cross-platform foundation
- Core logic refactoring (tasks 8-14) fixes critical bugs
- Platform backends (tasks 4-6) enable Windows, macOS, Android, iOS support
- Total: 29 major tasks with 95+ sub-tasks covering all 43 requirements and 117 properties
- Cross-platform support: Windows (full), macOS (full), Android (partial), iOS (limited)

### Git Workflow (MANDATORY)

**After EVERY task and sub-task completion**:

1. ✅ **Stage changes**: `git add .` or `git add <specific-files>`
2. ✅ **Commit with message**: `git commit -m "[Task X.Y] Description"`
3. ✅ **Push to remote**: `git push origin <branch-name>`
4. ✅ **Verify success**: Check for errors, CI/CD status
5. ✅ **Only then proceed** to next task

**Commit Message Template**:
```
[Task X.Y] Brief description (50 chars max)

- Detailed change 1
- Detailed change 2
- Requirements validated: X.Y, X.Z
- Properties tested: N, M (if applicable)

Validates: Requirements X.Y, X.Z
Tests: Property N, Property M (if applicable)
```

**Branch Strategy**:
- `main` - Production-ready code (protected)
- `develop` - Integration branch
- `feature/task-name` - Feature branches for each major task
- Merge feature → develop → main (after review)

**Rollback Safety**:
- Each commit = rollback point
- Use `git log --oneline` to view history
- Use `git reset --hard <commit>` to rollback if needed

**CI/CD Triggers**:
- Each push triggers automated tests
- Security scans run on every commit
- Build verification for all platforms
- Documentation auto-generation

**Push Failures**:
Push will be rejected if:
- ❌ Tests fail (unit, property, integration)
- ❌ Security vulnerabilities detected
- ❌ Code coverage drops below 85%
- ❌ Linting errors present
- ❌ Property tests fail (< 100 iterations)

### Quality Gates

**Before Proceeding to Next Task**:
1. ✅ All sub-tasks completed
2. ✅ All tests passing (unit + property + integration)
3. ✅ Code coverage ≥ 85%
4. ✅ No security vulnerabilities
5. ✅ All changes committed and pushed
6. ✅ CI/CD pipeline green
7. ✅ Code review approved (for main merges)

### Task Execution Order

**CRITICAL**: Tasks must be executed in order:
1. Tasks 1-7: PAL Foundation (enables cross-platform)
2. Tasks 8-14: Core Logic Fixes (critical bugs)
3. Tasks 15-29: Feature Completion (remaining requirements)

**Do NOT skip tasks** - each task builds on previous work.

### Testing Requirements

**Property-Based Tests**:
- Minimum 100 iterations per property
- Use Hypothesis (Python) or fast-check (TypeScript)
- Tag with feature name and property number
- Must pass before commit

**Unit Tests**:
- Cover specific examples and edge cases
- Test error conditions
- Verify integration points
- Must pass before commit

**Integration Tests**:
- Test end-to-end flows
- Verify cross-component communication
- Test on all target platforms
- Run at checkpoints (tasks 7, 13, 16, 29)

### Documentation Requirements

**Update After Each Task**:
- Code comments (inline documentation)
- API documentation (docstrings)
- Architecture diagrams (if structure changes)
- README files (if new features added)
- CHANGELOG.md (track all changes)

### Security Requirements

**Every Commit Must**:
- Pass security scans (no vulnerabilities)
- Maintain audit logging integrity
- Preserve authority model invariants
- Not introduce privilege escalation
- Not leak sensitive data

### Performance Requirements

**Verify After Each Task**:
- Application launch time < 1 second
- Text automation time < 2 seconds
- Intent pre-filter time < 10 milliseconds
- TTS synthesis time < 5 seconds
- LLM response time < 10 seconds (with fallback)
- Health check time < 5 seconds per component

### Platform Testing

**Test on All Platforms**:
- Windows 10/11 (primary)
- macOS (if available)
- Android (if available)
- iOS (if available)

**Minimum Testing**:
- Windows backend must work perfectly
- Other platforms tested via mock backends
- Cross-platform PAL verified via property tests

### Checkpoint Requirements

**At Each Checkpoint (Tasks 7, 13, 16, 29)**:
1. Run full test suite (all tests)
2. Verify all properties pass
3. Check code coverage ≥ 85%
4. Run security scans
5. Test on all available platforms
6. Review audit logs for integrity
7. Verify performance metrics
8. Ask user for approval before proceeding

### Final Approval (Task 29)

**Before Production Release**:
- ✅ All 43 requirements validated
- ✅ All 117 properties verified (100+ iterations each)
- ✅ All tests passing (unit, property, integration)
- ✅ Code coverage ≥ 85%
- ✅ Zero security vulnerabilities
- ✅ Performance metrics met
- ✅ Cross-platform PAL verified
- ✅ Documentation complete
- ✅ User approval obtained

---

**Remember**: This is production-grade, civilization-scale software. Every commit matters. Every test matters. Every security check matters. Build it right the first time.

