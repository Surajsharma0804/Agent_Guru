# AGENT_GURU Architecture Diagram

## Complete System Architecture

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                          AGENT_GURU SYSTEM ARCHITECTURE                    ║
║                              Version 2.0.0                                 ║
╚═══════════════════════════════════════════════════════════════════════════╝

┌───────────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE LAYER                               │
│                                                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Voice I/O  │  │  Visual UI   │  │   Feedback   │  │   CLI        │ │
│  │ (Mic/Speaker)│  │   (Future)   │  │   (Audio)    │  │  Interface   │ │
│  │              │  │              │  │              │  │              │ │
│  │  cpal/rodio  │  │     TBD      │  │   Beeps      │  │   stdout     │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘ │
└───────────────────────────────────────────────────────────────────────────┘
                                    ↕
┌───────────────────────────────────────────────────────────────────────────┐
│                         VOICE PIPELINE LAYER                               │
│                                                                            │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐           │
│  │  Wake Word   │  →   │     STT      │  →   │    Intent    │           │
│  │  Detection   │      │  (Whisper)   │      │    Parser    │           │
│  │              │      │              │      │              │           │
│  │ MFCC + NN    │      │ Transformer  │      │ Pattern +    │           │
│  │ <50ms        │      │ ≤120ms/sec   │      │ LLM Fallback │           │
│  │ Rust         │      │ C++ (opt)    │      │ Rust/Python  │           │
│  └──────────────┘      └──────────────┘      └──────────────┘           │
│                                                       ↓                    │
│                        ┌──────────────────────────────┴─────────┐        │
│                        ↓                                         ↓        │
│              ┌──────────────────┐                    ┌──────────────────┐│
│              │   OS Controller  │                    │   LLM Provider   ││
│              │                  │                    │                  ││
│              │ Win32/Cocoa/X11  │                    │ Ollama/OpenAI/   ││
│              │ App Launch       │                    │ Gemini           ││
│              │ Keyboard/Mouse   │                    │ ≤300ms first tok ││
│              │ Rust             │                    │ Rust             ││
│              └──────────────────┘                    └──────────────────┘│
│                        ↓                                         ↓        │
│              ┌──────────────────┐                    ┌──────────────────┐│
│              │  Audit Logger    │                    │   TTS Synthesis  ││
│              │                  │                    │                  ││
│              │ JSONL Format     │                    │ Neural TTS       ││
│              │ Immutable Log    │                    │ ≤200ms           ││
│              │ Rust             │                    │ Rust/C++         ││
│              └──────────────────┘                    └──────────────────┘│
└───────────────────────────────────────────────────────────────────────────┘
                                    ↕
┌───────────────────────────────────────────────────────────────────────────┐
│                      INFRASTRUCTURE LAYER                                  │
│                                                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  Audio I/O   │  │   Memory     │  │   Security   │  │   Platform   │ │
│  │              │  │   System     │  │  & Crypto    │  │ Integration  │ │
│  │ Ring Buffer  │  │              │  │              │  │              │ │
│  │ Lock-free    │  │ Encrypted    │  │ Ed25519      │  │ Win/Mac/Lin  │ │
│  │ 10s capacity │  │ AES-256-GCM  │  │ X25519       │  │ OS APIs      │ │
│  │ Rust         │  │ LRU Eviction │  │ ChaCha20     │  │ Rust         │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘ │
│                                                                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │    Policy    │  │  Deployment  │  │    Vision    │  │    Avatar    │ │
│  │    Engine    │  │   Manager    │  │   System     │  │   System     │ │
│  │              │  │              │  │              │  │              │ │
│  │ OPA-inspired │  │ Package Mgmt │  │ Object Det.  │  │ Emotion      │ │
│  │ Access Ctrl  │  │ Updates      │  │ Face Recog.  │  │ Lip Sync     │ │
│  │ Rust         │  │ Rollback     │  │ OCR          │  │ Personality  │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘ │
└───────────────────────────────────────────────────────────────────────────┘
                                    ↕
┌───────────────────────────────────────────────────────────────────────────┐
│                        OPERATING SYSTEM LAYER                              │
│                                                                            │
│  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐ │
│  │      Windows       │  │       macOS        │  │       Linux        │ │
│  │                    │  │                    │  │                    │ │
│  │ Win32 API          │  │ Cocoa Framework    │  │ X11/Wayland        │ │
│  │ ShellExecuteW      │  │ NSWorkspace        │  │ Desktop Entries    │ │
│  │ SendInput          │  │ Accessibility API  │  │ AT-SPI             │ │
│  │ FindWindow         │  │ CGEvent            │  │ Input Simulation   │ │
│  └────────────────────┘  └────────────────────┘  └────────────────────┘ │
└───────────────────────────────────────────────────────────────────────────┘
```

## Voice Pipeline Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      VOICE PIPELINE DATA FLOW                            │
└─────────────────────────────────────────────────────────────────────────┘

  USER SPEAKS
      ↓
┌─────────────────┐
│  Microphone     │  OS Audio Device
│  (16kHz, mono)  │
└────────┬────────┘
         ↓
┌─────────────────┐
│  cpal Capture   │  Rust: Cross-platform audio I/O
│  (1024 samples) │  Real-time priority thread
└────────┬────────┘
         ↓
┌─────────────────┐
│  Ring Buffer    │  Rust: Lock-free circular buffer
│  (10 seconds)   │  Continuous audio storage
└────────┬────────┘
         ↓
┌─────────────────┐
│  Wake Word      │  Rust: MFCC + Neural Classifier
│  Detection      │  Latency: ≤50ms, CPU: <10%
│  "Hey Guru"     │  Confidence threshold: 0.6
└────────┬────────┘
         ↓ (Wake word detected)
┌─────────────────┐
│  Audio Buffer   │  Rust: Collect 3-30 seconds
│  Collection     │  Wait for silence or timeout
└────────┬────────┘
         ↓
┌─────────────────┐
│  Whisper STT    │  C++: Transformer-based transcription
│  (Optional)     │  Latency: ≤120ms/sec audio
│                 │  Accuracy: ≥95% WER
└────────┬────────┘
         ↓
┌─────────────────┐
│  Transcription  │  Rust: Text + confidence + timestamps
│  Result         │  Example: "Open YouTube" (0.95)
└────────┬────────┘
         ↓
┌─────────────────┐
│  Intent Parser  │  Rust/Python: Pattern matching + LLM
│                 │  Latency: ≤50ms
│                 │  Output: Intent + parameters
└────────┬────────┘
         ↓
    ┌────┴────┐
    ↓         ↓
┌─────────┐ ┌─────────┐
│OS Action│ │LLM Query│
└────┬────┘ └────┬────┘
     ↓           ↓
┌─────────┐ ┌─────────┐
│Execute  │ │Generate │
│Command  │ │Response │
└────┬────┘ └────┬────┘
     ↓           ↓
┌─────────────────┐
│  TTS Synthesis  │  Rust/C++: Neural TTS
│                 │  Latency: ≤200ms
│                 │  Output: 22kHz audio
└────────┬────────┘
         ↓
┌─────────────────┐
│  rodio Playback │  Rust: Audio playback
│                 │  Streaming output
└────────┬────────┘
         ↓
┌─────────────────┐
│  Speakers       │  OS Audio Device
│                 │
└─────────────────┘
      ↓
  USER HEARS RESPONSE
```

## Language Boundaries and Communication

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   LANGUAGE BOUNDARIES & COMMUNICATION                     │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                              RUST LAYER                                   │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ Core Engine (99% of codebase)                                      │ │
│  │                                                                     │ │
│  │ • Audio I/O (cpal, rodio)                                          │ │
│  │ • Wake Word Detection (MFCC + Neural)                              │ │
│  │ • OS Control (Win32/Cocoa/X11)                                     │ │
│  │ • Security & Cryptography (Ed25519, AES-GCM)                       │ │
│  │ • Memory System (Encrypted storage)                                │ │
│  │ • LLM Provider Management (HTTP clients)                           │ │
│  │ • Policy Engine (Access control)                                   │ │
│  │ • Deployment Manager (Updates, rollback)                           │ │
│  │ • Vision System (Object detection, OCR)                            │ │
│  │ • Avatar System (Emotion, lip sync)                                │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  Communication Methods:                                                   │
│  ┌─────────────────┐         ┌─────────────────┐                        │
│  │  To Python      │         │  To C++         │                        │
│  │  (Planned)      │         │  (Optional)     │                        │
│  │                 │         │                 │                        │
│  │  • PyO3 FFI     │         │  • C ABI        │                        │
│  │  • JSON msgs    │         │  • whisper-rs   │                        │
│  │  • Shared mem   │         │  • Direct calls │                        │
│  └─────────────────┘         └─────────────────┘                        │
└──────────────────────────────────────────────────────────────────────────┘
                    ↕                           ↕
┌──────────────────────────────────────────────────────────────────────────┐
│                            PYTHON LAYER                                   │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ Intelligence Layer (Planned - <1% of codebase)                     │ │
│  │                                                                     │ │
│  │ • Intent Parser (Pattern matching + LLM)                           │ │
│  │ • Command Router (Intent → Action mapping)                         │ │
│  │ • Context Manager (Conversation context)                           │ │
│  │ • Reasoning Engine (High-level decision making)                    │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  Current Usage: Utility scripts only (testing, analysis)                 │
└──────────────────────────────────────────────────────────────────────────┘
                                ↕
┌──────────────────────────────────────────────────────────────────────────┐
│                              C++ LAYER                                    │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ ML Runtime (Optional - via feature flags)                          │ │
│  │                                                                     │ │
│  │ • Whisper.cpp (Speech-to-Text)                                     │ │
│  │   - Model: ggml-base.bin (~140MB)                                  │ │
│  │   - Binding: whisper-rs crate                                      │ │
│  │   - Feature: --features whisper                                    │ │
│  │                                                                     │ │
│  │ • Llama.cpp (via Ollama - indirect)                                │ │
│  │   - No direct bindings                                             │ │
│  │   - HTTP API communication                                         │ │
│  │                                                                     │ │
│  │ • TTS Runtime (Planned)                                            │ │
│  │   - Piper TTS or Coqui TTS                                         │ │
│  │   - C++ bindings to be added                                       │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

## Module Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        MODULE DEPENDENCY GRAPH                           │
└─────────────────────────────────────────────────────────────────────────┘

                          ┌──────────────┐
                          │   lib.rs     │  Main library entry
                          │  (Root)      │
                          └──────┬───────┘
                                 │
                 ┌───────────────┼───────────────┐
                 ↓               ↓               ↓
          ┌──────────┐    ┌──────────┐   ┌──────────┐
          │ main.rs  │    │voice_main│   │ runtime  │
          │  (CLI)   │    │  (Voice) │   │          │
          └──────────┘    └──────────┘   └──────────┘
                                 │
                 ┌───────────────┼───────────────┐
                 ↓               ↓               ↓
          ┌──────────┐    ┌──────────┐   ┌──────────┐
          │  voice   │    │   llm    │   │ platform │
          │          │    │          │   │          │
          └────┬─────┘    └────┬─────┘   └────┬─────┘
               │               │              │
       ┌───────┼───────┐       │              │
       ↓       ↓       ↓       ↓              ↓
   ┌──────┐┌──────┐┌──────┐┌──────┐    ┌──────────┐
   │ wake ││trans-││synth-││biome-│    │ windows  │
   │ word ││crip- ││esis  ││tric  │    │  macos   │
   │      ││tion  ││      ││      │    │  linux   │
   └──────┘└──────┘└──────┘└──────┘    └──────────┘
       │       │       │       │
       └───────┴───────┴───────┘
               ↓
        ┌──────────┐
        │  audio   │  cpal, rodio, hound
        │   I/O    │  rustfft, apodize
        └──────────┘

                 ┌───────────────┐
                 │   security    │
                 └───────┬───────┘
                         │
         ┌───────────────┼───────────────┐
         ↓               ↓               ↓
    ┌────────┐     ┌──────────┐   ┌──────────┐
    │ crypto │     │biometric │   │  audit   │
    │        │     │          │   │          │
    └────┬───┘     └──────────┘   └──────────┘
         │
    ┌────┴────┐
    ↓         ↓
┌────────┐┌────────┐
│identity││zk_proof│
│        ││        │
└────────┘└────────┘

    ┌──────────┐         ┌──────────┐         ┌──────────┐
    │  memory  │         │  vision  │         │  avatar  │
    └────┬─────┘         └────┬─────┘         └────┬─────┘
         │                    │                     │
    ┌────┴────┐          ┌────┴────┐          ┌────┴────┐
    ↓         ↓          ↓         ↓          ↓         ↓
┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐
│encrypt ││semantic││detection││tracking││emotion ││lip_sync│
│        ││        ││        ││        ││        ││        │
└────────┘└────────┘└────────┘└────────┘└────────┘└────────┘

    ┌──────────┐         ┌──────────┐         ┌──────────┐
    │  agents  │         │  policy  │         │deployment│
    └────┬─────┘         └────┬─────┘         └────┬─────┘
         │                    │                     │
    ┌────┴────┐               ↓                ┌────┴────┐
    ↓         ↓          ┌────────┐            ↓         ↓
┌────────┐┌────────┐    │ engine │      ┌────────┐┌────────┐
│orchestr││property│    │        │      │package ││update  │
│        ││        │    └────────┘      │        ││        │
└────────┘└────────┘                    └────────┘└────────┘

Legend:
  ┌────────┐
  │ Module │  Rust module
  └────────┘
      ↓      Dependency (uses)
```

## External Dependencies

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL DEPENDENCIES                             │
└─────────────────────────────────────────────────────────────────────────┘

AGENT_GURU System
        │
        ├─── Rust Crates (Cargo.toml)
        │    │
        │    ├─── Cryptography
        │    │    ├─── ed25519-dalek 2.1 (Signatures)
        │    │    ├─── x25519-dalek 2.0 (Key exchange)
        │    │    ├─── chacha20poly1305 0.10 (Encryption)
        │    │    ├─── aes-gcm 0.10 (AES encryption)
        │    │    ├─── argon2 0.5 (Password hashing)
        │    │    └─── blake3 1.5 (Fast hashing)
        │    │
        │    ├─── Audio
        │    │    ├─── cpal 0.15 (Audio I/O)
        │    │    ├─── rodio 0.17 (Playback)
        │    │    ├─── hound 3.5 (WAV files)
        │    │    ├─── rustfft 6.1 (FFT)
        │    │    └─── apodize 1.0 (Windows)
        │    │
        │    ├─── Async/Network
        │    │    ├─── tokio 1.0 (Async runtime)
        │    │    └─── reqwest 0.11 (HTTP client)
        │    │
        │    ├─── ML/Vision
        │    │    ├─── image 0.24 (Image processing)
        │    │    ├─── nalgebra 0.32 (Linear algebra)
        │    │    └─── ndarray 0.15 (Arrays)
        │    │
        │    └─── Utilities
        │         ├─── serde 1.0 (Serialization)
        │         ├─── thiserror 1.0 (Errors)
        │         ├─── tracing 0.1 (Logging)
        │         └─── uuid 1.6 (UUIDs)
        │
        ├─── Optional C++ Libraries
        │    │
        │    ├─── Whisper.cpp (via whisper-rs 0.12)
        │    │    ├─── Requires: LLVM/Clang
        │    │    ├─── Model: ggml-base.bin (~140MB)
        │    │    └─── Feature: --features whisper
        │    │
        │    └─── TTS Runtime (Planned)
        │         ├─── Piper TTS (Option 1)
        │         └─── Coqui TTS (Option 2)
        │
        ├─── External Services (HTTP APIs)
        │    │
        │    ├─── Ollama (Primary LLM)
        │    │    ├─── URL: http://localhost:11434
        │    │    ├─── Models: mistral:7b, qwen2.5:14b
        │    │    └─── Protocol: HTTP REST
        │    │
        │    ├─── OpenAI (Fallback LLM)
        │    │    ├─── URL: https://api.openai.com
        │    │    ├─── Auth: OPENAI_API_KEY
        │    │    └─── Models: gpt-3.5-turbo, gpt-4
        │    │
        │    └─── Google Gemini (Fallback LLM)
        │         ├─── URL: https://generativelanguage.googleapis.com
        │         ├─── Auth: GEMINI_API_KEY
        │         └─── Models: gemini-pro
        │
        └─── Operating System APIs
             │
             ├─── Windows
             │    ├─── Win32 API (kernel32, user32, shell32)
             │    ├─── ShellExecuteW (App launch)
             │    ├─── SendInput (Input simulation)
             │    └─── FindWindow (Window management)
             │
             ├─── macOS
             │    ├─── Cocoa Framework
             │    ├─── NSWorkspace (App launch)
             │    ├─── Accessibility API (UI automation)
             │    └─── CGEvent (Input simulation)
             │
             └─── Linux
                  ├─── X11/Wayland
                  ├─── Desktop Entries (App launch)
                  ├─── AT-SPI (Accessibility)
                  └─── Input Simulation
```

---

**Document Version**: 1.0  
**Last Updated**: February 12, 2026  
**Purpose**: Visual reference for system architecture and dependencies
