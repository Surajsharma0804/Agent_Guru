# Tasks File Template for All AGENT_GURU Specs

## Standard Structure for All Tasks Files

Every tasks.md file should follow this structure:

### Header Section
```markdown
# Implementation Plan: [Component Name]

## Overview

Brief description of the component and its role in AGENT_GURU.

**Key Features**:
- Feature 1 (related to dual personalities if applicable)
- Feature 2 (related to laptop control if applicable)
- Feature 3 (related to onboarding if applicable)
- Feature 4 (related to LLM configuration if applicable)

## Task Completion Protocol

After completing EACH task:
1. ✅ Run all tests for that task
2. ✅ Verify all tests pass
3. ✅ Commit changes with descriptive message
4. ✅ Push to GitHub immediately
5. ✅ Mark task as complete in this file
```

### Task Format
```markdown
- [ ] **Task N: Task Title**
  - Detailed description of what to implement
  - File names and class names
  - Key methods and functionality
  - _Requirements: Req X, Req Y (reference to requirements.md)_
  - **Tests Required**:
    - Unit tests for [specific functionality]
    - Property tests for [correctness properties]
    - Integration tests for [cross-component features]
    - Performance tests for [latency/throughput targets]
    - Security tests for [attack vectors] (if applicable)
  - **GitHub Push**: ✅ Required after completion
```

### Testing Summary Section
```markdown
## Testing Summary

### Property-Based Tests (Hypothesis)
- List of all correctness properties to test
- Minimum 100 iterations per property test

### Unit Tests
- List of all unit test categories
- Edge cases and error conditions

### Integration Tests
- Cross-component integration points
- End-to-end workflows

### Performance Tests
- Latency targets
- Throughput targets
- Resource usage limits

### Coverage Goals
- Minimum coverage percentage
- Specific areas requiring high coverage
```

### Dependencies Section
```markdown
## Dependencies

This component depends on:
- [Component 1] (for [purpose])
- [Component 2] (for [purpose])

This component is used by:
- [Component 1] (for [purpose])
- [Component 2] (for [purpose])
```

## Key Requirements for All Tasks Files

### 1. Dual Personality Support (where applicable)
- Tasks must explicitly mention Guru (male) and Maya (female) personalities
- Wake word detection tasks must include both "Hey Guru" and "Hey Maya"
- TTS tasks must include male and female voice configuration
- Avatar tasks must include separate models for each personality

### 2. Complete Laptop Control (where applicable)
- Platform integration tasks must include ALL system operations:
  - Application control (open, close, switch)
  - Text input (type anywhere)
  - Messaging (WhatsApp, Telegram, Slack, etc.)
  - File operations (create, delete, move, copy)
  - System settings (volume, brightness, network)
  - Mouse/keyboard control
  - Window management
  - Media control
  - Screenshots/recording

### 3. Onboarding System (security component)
- Profile setup (gender, age, DOB, name)
- Multi-factor biometric enrollment (fingerprint, face, voice, passphrase)
- LLM configuration (local Ollama vs cloud APIs)
- API key management (OpenAI, Gemini, DeepSeek, Anthropic)
- Permission granting (microphone, camera, accessibility, automation)

### 4. Test Requirements
Every task must specify:
- **Unit Tests**: Specific functionality to test
- **Property Tests**: Correctness properties to verify
- **Integration Tests**: Cross-component interactions
- **Performance Tests**: Latency/throughput targets
- **Security Tests**: Attack vectors (for security-critical components)

### 5. GitHub Push Requirement
Every task must end with:
```markdown
- **GitHub Push**: ✅ Required after completion
```

## Component-Specific Additions

### guru-speech-engine
- Dual wake word detection ("Hey Guru" / "Hey Maya")
- Gender-specific TTS (male/female voices)
- Voice biometric authentication
- Multi-language support (English, Hindi, Punjabi)

### guru-avatar-emotion
- Dual personality engine (Guru/Maya traits)
- Separate male/female avatar models
- Personality-driven behavior
- Emotion recognition and expression

### guru-security-cryptography
- Multi-factor biometric authentication
- Comprehensive onboarding system
- User profile management
- Secure API key storage for LLM providers

### guru-llm-runtime
- Flexible LLM configuration (local/cloud)
- Support for multiple providers (OpenAI, Gemini, DeepSeek, Anthropic)
- Secure API key management
- Cost tracking for cloud APIs

### guru-platform-integration
- Comprehensive system control operations
- File, application, text input, messaging control
- Mouse, keyboard, window management
- System settings control

### guru-policy-engine
- Permission management for system operations
- User confirmation for sensitive operations
- Safety policies to prevent dangerous operations
- Audit logging for all operations

### guru-deployment-system
- Professional Windows MSI installer
- Professional macOS DMG installer
- Onboarding flow integration
- Auto-update mechanism

### guru-memory-system
- User profile and preference storage
- Conversation history for both personalities
- Learning user patterns over time
- Context maintenance across sessions

### guru-agent-orchestration
- Multi-step command coordination
- Complex operation execution
- Cross-component integration
- Task decomposition for voice commands

## Example Task (Complete)

```markdown
- [ ] **Task 5: Dual Wake Word Detection**
  - Implement `wake_word.py`:
    - `WakeWordDetector` class
    - Support for "Hey Guru" and "Hey Maya" detection
    - `detect()` method returning personality identifier (PersonalityType.GURU or PersonalityType.MAYA)
    - Configurable sensitivity per wake word
    - MFCC-based feature extraction
    - False positive rate <1 detection per hour
  - Train or integrate wake word models for both personalities
  - _Requirements: Req 1 (Dual Personality Wake Word Detection)_
  - **Tests Required**:
    - Unit tests for "Hey Guru" detection with sample audio
    - Unit tests for "Hey Maya" detection with sample audio
    - Unit tests for false positive rate (<1/hour)
    - Property tests for detection latency (<200ms)
    - Unit tests for personality identification accuracy (>95%)
    - Unit tests for simultaneous wake word support
    - Integration tests with audio processor
  - **GitHub Push**: ✅ Required after completion
```

## Applying This Template

For each spec that needs tasks.md updated:

1. Read the requirements.md to understand all requirements
2. Break down requirements into discrete implementation tasks
3. Group tasks into logical phases (setup, core features, integration, testing)
4. For each task, specify:
   - What to implement (files, classes, methods)
   - Which requirements it addresses
   - What tests are required
   - GitHub push requirement
5. Add testing summary section
6. Add dependencies section
7. Include component-specific features (dual personalities, laptop control, onboarding)

## Priority Order for Updates

1. ✅ guru-speech-engine (DONE)
2. ✅ guru-security-cryptography (DONE)
3. guru-avatar-emotion
4. guru-llm-runtime
5. guru-platform-integration
6. guru-policy-engine
7. guru-deployment-system
8. guru-memory-system
9. guru-agent-orchestration
10. biometric-consolidation
11. guruvision-facial-recognition (already has tasks, may need updates)

## Notes

- All tasks files should be comprehensive enough that developers don't need to constantly reference requirements.md
- Each task should be completable in 1-4 hours
- Tests should be specified in detail so developers know exactly what to test
- GitHub push after each task ensures incremental progress is saved
- Integration tasks should clearly specify which other components are involved
