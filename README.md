# Agent Guru - AI Voice Assistant

An always-on, cross-platform AI voice assistant with wake word detection, speech recognition, and intelligent conversation capabilities.

## Overview

Agent Guru is a production-ready AI assistant that works like Siri, Google Assistant, or Alexa. Just say "Hey Guru" or "Hey Maya" to wake it up - no need to open the app after installation.

## Key Features

- **Always-On Wake Word Detection**: Responds to "Hey Guru" or "Hey Maya"
- **Cross-Platform Support**: Windows, macOS, Linux, Android, iOS
- **Flexible LLM Options**:
  - Desktop: Choose local (Ollama) or cloud API during installation
  - Mobile: Cloud API only (OpenAI, Gemini, DeepSeek, Anthropic)
- **Battery Optimized**: <5% battery in sleep mode, <10% when active
- **Privacy First**: Your API keys, your data
- **Background Service**: Runs automatically on boot

## Platform-Specific Features

### Desktop (Windows/macOS/Linux)
- Choose during installation:
  - **Local Ollama**: FREE, private, offline
  - **Cloud API**: Use your own API key
- System tray service
- Always listening in background

### Mobile (Android/iOS)
- API-only (devices lack resources for local LLMs)
- Provide your own API keys
- Background audio mode
- Persistent notification (Android)

## Quick Start

### Installation

1. Download installer for your platform
2. Choose LLM option (desktop only):
   - Local Ollama (recommended for privacy)
   - Cloud API (requires your API key)
3. Complete setup

### First Use

After installation, just say:
- "Hey Guru" or "Hey Maya" to wake up
- Ask your question
- Assistant goes back to sleep after 30s of inactivity

No need to open the app again!

## Project Structure

```
Agent_Guru/
├── .kiro/specs/              # Complete specifications (START HERE)
│   ├── README.md             # Project overview
│   ├── VERIFICATION_COMPLETE.md
│   ├── guru-complete-integration/
│   ├── guru-speech-engine/
│   ├── guru-llm-runtime/
│   ├── guru-platform-integration/
│   ├── guru-deployment-system/
│   └── guru-agent-orchestration/
├── guru/                     # Rust implementation
│   ├── agents/
│   ├── avatar/
│   ├── deployment/
│   ├── llm/
│   ├── memory/
│   ├── platform/
│   ├── policy/
│   └── security/
├── guru_speech/              # Python speech engine
├── guru_vision/              # Python vision engine
├── guru_deployment/          # Python deployment tools
└── guru_face/                # Face recognition data
```

## Getting Started with Development

All specifications are complete and ready for implementation:

1. Read `.kiro/specs/README.md` for project overview
2. Start with `.kiro/specs/guru-complete-integration/tasks.md` (Task 1)
3. Follow the task sequence across all specs

## Battery Optimization

- **Sleep Mode**: <5% battery/hour (wake word detection only)
- **Wake Mode**: <10% battery/hour (full processing)
- **Auto Transitions**: Sleep→Wake on wake word, Wake→Sleep after 30s

## API Key Management

- API keys NEVER bundled in application
- Users provide their own keys
- Stored securely in OS keychain
- Validated immediately after entry

## Supported LLM Providers

- OpenAI (GPT-4, GPT-3.5)
- Google Gemini
- DeepSeek
- Anthropic (Claude)
- Local Ollama (desktop only)

## License

MIT License - see LICENSE file for details

## Status

✅ All specifications complete (100%)
🚧 Implementation in progress
📋 Start with Task 1 in guru-complete-integration spec
