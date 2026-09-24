# Changelog

All notable changes to Agent Guru will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-07-26

### 🎉 First Production Release

#### Added
- **Voice Pipeline**: Wake word detection → STT → LLM → TTS with <200ms filler response
- **Dual Persona System**: Guru (analytical, direct) and Maya (warm, empathetic)
- **Full OS Control**: Open/close apps, file operations, system settings, volume, brightness
- **Speaker Verification**: SpeechBrain ECAPA-TDNN biometric auth with MFCC fallback
- **Reaction Rules**: User-taught trigger→response habits with O(1) exact + substring + fuzzy matching
- **User Memory**: LRU-cached facts (name, nickname, language, habits) with pinned key persistence
- **Destructive Action Confirmation**: Verbal confirmation for shutdown, delete, restart operations
- **Companion Prompts**: Context-aware prompt builder with emotion hints, crisis support, anti-manipulation guardrails
- **Hinglish Support**: Default Hindi-English code-mixing with pure-English/Hindi override
- **Emotion Detection**: Real-time emotion analysis from voice + text
- **Self-Improvement Engine**: Meta-learning with conflict resolution and benchmarking
- **Reasoning Engine**: Intent classification, NER, knowledge synthesis, memory retrieval
- **Integration Layer**: Goal manager, memory client, verifier, tracing, metrics exporter
- **Security**: Voice authentication, encryption, audit logging
- **Windows Installer**: PyInstaller .exe (89 MB) + Inno Setup full installer (1.86 GB)

#### Architecture
- 812 Python modules, 970 source files
- 42 functional tests - all passing
- O(1) exact match, O(k) fuzzy match for reaction rules (k ≤ 200)
- LRU eviction with pinned keys for user memory
- Hash-based rule table with capability-table guard

#### Platforms
- Windows 10/11 (primary, fully tested)
- macOS and Linux (supported, community-tested)

---

## [0.1.0] - 2026-07-01

### Initial Development

- Core speech pipeline (faster-whisper STT, edge-tts TTS)
- Basic OS controller
- LLM integration (Ollama local, OpenAI/Anthropic cloud fallback)
- Memory system prototype
- Basic intent recognition
