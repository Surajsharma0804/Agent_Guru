# AGENT_GURU Specifications

Complete specifications for building AGENT_GURU - a multi-platform, always-on AI voice assistant with dual personalities (Guru and Maya).

## 📋 Quick Start

1. **Read**: `VERIFICATION_COMPLETE.md` - Confirms all requirements are correctly specified
2. **Start**: Begin with `guru-complete-integration/tasks.md` - Task 1
3. **Follow**: Complete each task, test, commit, and push to GitHub

## 🎯 Project Overview

**AGENT_GURU** is a production-ready AI voice assistant that:
- Works on **all platforms**: Windows, macOS, Linux, Android, iOS
- Runs **always-on** in background (like Siri/Alexa)
- Features **dual personalities**: Guru (male) and Maya (female)
- Supports **complete system control** through voice commands
- Optimizes **battery usage**: <5% sleep, <10% wake

## 📁 Specification Structure

Each spec contains 3 files:
- `requirements.md` - What needs to be built (acceptance criteria)
- `design.md` - How to build it (architecture, interfaces, data models)
- `tasks.md` - Step-by-step implementation tasks

## 🔧 Core Specifications

### 1. guru-complete-integration
**Master integration spec** with 29 executable tasks covering the entire system.
- **Start here**: Task 1 - Project setup
- **Purpose**: Complete end-to-end integration
- **Status**: Ready for implementation

### 2. guru-speech-engine
Voice recognition and synthesis with always-on background service.
- Wake word detection ("Hey Guru", "Hey Maya")
- Speech-to-text (Whisper)
- Text-to-speech (gender-specific voices)
- Mobile: Android Speech API, Apple Speech Framework
- **Tasks**: 18 total

### 3. guru-llm-runtime
LLM provider management with flexible configuration.
- **Desktop**: Local Ollama OR Cloud API (user choice)
- **Mobile**: Cloud API ONLY (OpenAI, Gemini, DeepSeek, Anthropic)
- API keys: User provides their own (never bundled)
- Cost tracking and budget limits
- **Tasks**: 19 total

### 4. guru-platform-integration
Cross-platform OS control and hardware abstraction.
- **Desktop**: Windows, macOS, Linux
- **Mobile**: Android, iOS
- Complete laptop/phone control through voice
- Background service with sleep/wake cycles
- **Tasks**: 21 total

### 5. guru-deployment-system
Professional installers and app store deployment.
- **Desktop**: MSI (Windows), DMG (macOS), DEB/RPM/AppImage (Linux)
- **Mobile**: APK/AAB (Android), IPA (iOS)
- Onboarding integration
- Auto-update mechanism
- **Tasks**: 11 total

### 6. guru-agent-orchestration
Multi-agent coordination and background service orchestration.
- Voice command decomposition
- Multi-step operation coordination
- Background service lifecycle management
- Sleep/wake coordination across components
- **Tasks**: 11 total

### 7. guru-security-cryptography
Biometric authentication and cryptographic identity.
- Voice biometric authentication
- Face recognition
- Fingerprint (mobile)
- Secure key storage
- **Tasks**: See spec for details

### 8. guru-memory-system
Conversation context and memory management.
- Semantic memory storage
- Temporal graph for relationships
- Context retrieval for LLM
- **Tasks**: See spec for details

### 9. guru-policy-engine
Permission management and policy enforcement.
- Rule-based access control
- User consent management
- Audit logging
- **Tasks**: See spec for details

### 10. guru-avatar-emotion
Visual avatar with emotion and lip sync.
- Guru and Maya avatars
- Emotion expression
- Lip sync with speech
- **Tasks**: See spec for details

## 🚀 Implementation Workflow

### Phase 1: Setup (Week 1)
```bash
# Start with guru-complete-integration Task 1
cd .kiro/specs/guru-complete-integration
# Read tasks.md and begin Task 1
```

### Phase 2: Core Components (Weeks 2-8)
1. guru-speech-engine (2 weeks)
2. guru-llm-runtime (1 week)
3. guru-platform-integration (3 weeks)
4. guru-security-cryptography (2 weeks)

### Phase 3: Integration (Weeks 9-10)
1. guru-agent-orchestration (1 week)
2. guru-memory-system (1 week)

### Phase 4: Deployment (Weeks 11-12)
1. guru-deployment-system (2 weeks)
2. Testing and polish

### Phase 5: Production (Week 13)
1. App store submissions
2. Documentation
3. Launch

## ✅ Key Requirements

### Platform-Specific LLM Configuration
- **Desktop (Windows/macOS/Linux)**: 
  - User chooses: Local Ollama (free, private) OR Cloud API
  - If Cloud API: User provides own API key
  
- **Mobile (Android/iOS)**:
  - Cloud API ONLY (no local LLMs)
  - User MUST provide own API key
  - Reason: Mobile devices lack resources for local inference

### Always-On Behavior
- After installation: No need to open app
- Just say "Hey Guru" or "Hey Maya"
- Works like Siri/Google Assistant/Alexa
- Background service starts automatically on boot

### Sleep/Wake Cycles
- **Sleep Mode**: <5% battery per hour
  - Minimal CPU, wake word detection only
- **Wake Mode**: <10% battery per hour
  - Full processing, LLM inference, command execution
- Automatic transitions based on voice activity

### API Key Management
- NEVER bundled in application
- User provides their own keys
- Stored securely in OS keychain
- Validated immediately after entry

## 📊 Testing Requirements

Each task requires:
- ✅ Unit tests (all methods, edge cases)
- ✅ Integration tests (component interactions)
- ✅ Property-based tests (100+ iterations)
- ✅ Minimum 80% code coverage
- ✅ All tests passing before GitHub push

## 🔗 Dependencies

```
guru-speech-engine
    ↓
guru-llm-runtime ← guru-memory-system
    ↓
guru-agent-orchestration
    ↓
guru-platform-integration ← guru-policy-engine
    ↓
guru-security-cryptography
```

## 📝 Task Completion Protocol

For EACH task:
1. ✅ Read task requirements
2. ✅ Implement code
3. ✅ Write tests
4. ✅ Run all tests (must pass)
5. ✅ Commit with descriptive message
6. ✅ Push to GitHub immediately
7. ✅ Mark task complete in tasks.md

## 🎯 Success Criteria

- ✅ All 5 platforms working (Windows, macOS, Linux, Android, iOS)
- ✅ Always-on background service operational
- ✅ Battery optimization targets met (<5% sleep, <10% wake)
- ✅ Voice commands working end-to-end
- ✅ Dual personalities (Guru and Maya) functional
- ✅ All tests passing (>80% coverage)
- ✅ Professional installers created
- ✅ App store submissions complete

## 📚 Additional Resources

- **VERIFICATION_COMPLETE.md**: Detailed verification of all requirements
- **guru-complete-integration/**: Master integration spec with 29 tasks
- Each spec's `requirements.md`: Detailed acceptance criteria
- Each spec's `design.md`: Architecture and implementation details
- Each spec's `tasks.md`: Step-by-step implementation guide

## 🚀 Ready to Start!

All specifications are 100% complete and verified. Begin implementation with:

```bash
cd .kiro/specs/guru-complete-integration
cat tasks.md  # Read Task 1 and begin!
```

---

**Status**: Ready for Implementation ✅  
**Date**: 2026-02-16  
**Quality**: Production-Ready  
**Platforms**: Windows, macOS, Linux, Android, iOS  

**Let's build AGENT_GURU!** 🎉

