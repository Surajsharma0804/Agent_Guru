# Agent Guru - Quick Start Guide (Voice Mode)

## 🎤 Voice-Driven AI Companion

Agent Guru is now fully voice-enabled! Talk to your AI companion naturally using your microphone.

---

## ⚡ Quick Start (3 Steps)

### 1. Install Prerequisites

**Option A: Local LLM (Recommended - Works Offline)**
```bash
# Install Ollama
# Windows: Download from https://ollama.ai
# macOS: brew install ollama
# Linux: curl https://ollama.ai/install.sh | sh

# Start Ollama
ollama serve

# Install AI model (in another terminal)
ollama pull mistral:7b-instruct
```

**Option B: Cloud API (Requires Internet)**
```bash
# Set your API key (choose one)
set OPENAI_API_KEY=sk-your-key-here
# OR
set GEMINI_API_KEY=your-key-here
```

### 2. Run Agent Guru
```bash
# Quick run (development)
cargo run --bin agent_guru_voice

# OR use pre-built binary
.\target\release\agent_guru_voice.exe
```

### 3. Start Talking!
```
Say: "Hey Guru" or "Hey Maya"
Then: Ask your question
```

---

## 🎯 Voice Commands

| Command | Action |
|---------|--------|
| "Hey Guru" or "Hey Maya" | Wake up the AI |
| Ask any question | Get AI response |
| "Stop listening" | Pause wake word detection |
| "Exit" or "Goodbye" | Quit the application |
| Ctrl+C | Force quit |

---

## 🔊 System Requirements

### Hardware
- **Microphone**: Any USB or built-in microphone
- **Speakers/Headphones**: For audio output
- **RAM**: 2GB minimum (4GB recommended)
- **CPU**: Any modern processor (Intel/AMD/ARM)

### Software
- **Windows**: Windows 10/11
- **macOS**: macOS 10.15+
- **Linux**: Any modern distribution
- **Rust**: 1.75+ (for building from source)

---

## 🎤 Audio Setup

### Windows
1. Ensure microphone is connected
2. Check microphone permissions in Settings → Privacy → Microphone
3. Set default microphone in Sound settings

### macOS
1. Grant microphone permission when prompted
2. System Preferences → Security & Privacy → Microphone
3. Check "Terminal" or your terminal app

### Linux
1. Ensure ALSA or PulseAudio is installed
2. Test microphone: `arecord -l`
3. Adjust volume: `alsamixer`

---

## 🚀 Build from Source

```bash
# Clone repository
git clone https://github.com/your-repo/agent-guru
cd agent-guru

# Build release version
cargo build --release --bin agent_guru_voice

# Run
.\target\release\agent_guru_voice.exe
```

---

## 🔧 Configuration

### LLM Configuration
Edit `.kiro/llm_config.yaml`:

```yaml
providers:
  ollama:
    enabled: true
    base_url: "http://localhost:11434"
    models:
      fast: "mistral:7b-instruct"
      balanced: "mistral:7b-instruct"
      quality: "mistral:7b-instruct"
  
  openai:
    enabled: false  # Set to true if using OpenAI
    models:
      fast: "gpt-3.5-turbo"
      balanced: "gpt-4"
      quality: "gpt-4"
```

### Wake Word Sensitivity
In the code, adjust sensitivity (0.0 to 1.0):
- **0.5**: Balanced (default)
- **0.7**: More sensitive (easier to trigger)
- **0.3**: Less sensitive (harder to trigger)

---

## 📊 Performance

| Metric | Value |
|--------|-------|
| Wake Word Latency | <50ms |
| CPU Usage (Idle) | ~3% |
| Memory Usage | ~45MB |
| Audio Sample Rate | 16kHz |
| Audio Channels | Mono |

---

## 🐛 Troubleshooting

### "No input device available"
- **Windows**: Check microphone is plugged in and enabled
- **macOS**: Grant microphone permission
- **Linux**: Install `alsa-utils` or `pulseaudio`

### "Failed to initialize voice pipeline"
- Ensure Ollama is running: `ollama serve`
- OR set API key: `set OPENAI_API_KEY=your-key`
- Check `.kiro/llm_config.yaml` exists

### Wake word not detecting
- Speak clearly and loudly
- Say "Hey Guru" or "Hey Maya" (not "Hey Agent Guru")
- Check microphone volume in system settings
- Try adjusting sensitivity in code

### No audio output
- Check speakers/headphones are connected
- Verify system volume is not muted
- Test with other audio applications

### High CPU usage
- Normal: 3-5% during listening
- High: >10% may indicate issue
- Solution: Close other applications

---

## 🎯 Example Conversation

```
System: 🎧 Listening for wake word...

You: "Hey Guru"

System: 🎯 Wake word detected: 'guru' (confidence: 0.85)
        🎤 Listening... (speak now)

You: "What's the weather like today?"

System: 📝 You said: "What's the weather like today?"
        🤖 GURU is thinking... ✓
        💬 GURU: I don't have access to real-time weather data...
        🔊 Speaking... ✓
        
        🎧 Listening for wake word...
```

---

## 📦 Installation Packages

### Windows Installer
```bash
# Build installer
.\build_voice.bat

# Install
.\installers\windows\Agent_Guru.bat
```

### macOS App Bundle
```bash
# Build app
./scripts/create_macos_app.sh

# Install
# Drag Agent Guru.app to Applications folder
```

---

## 🔐 Privacy & Security

- **Local Processing**: Wake word detection runs locally
- **No Recording**: Audio is not saved to disk
- **Encrypted Memory**: Conversation history encrypted in memory
- **API Keys**: Stored in environment variables only
- **Offline Mode**: Works fully offline with Ollama

---

## 📚 Advanced Usage

### Custom Wake Words
Edit `guru/voice_main.rs`:
```rust
wake_engine.initialize(&["custom".to_string(), "words".to_string()])?;
```

### Multiple LLM Providers
The system automatically routes tasks to the best provider:
- **Fast tasks**: Ollama (local)
- **Complex tasks**: GPT-4 (if API key set)
- **Fallback**: Tries all providers in order

### Conversation History
Conversation is maintained in memory:
- System prompt sets personality
- User messages are tracked
- Assistant responses are stored
- Context is preserved across turns

---

## 🎉 Success Indicators

You'll know it's working when you see:
```
✅ System initialized successfully
🎤 Using input device: [Your Microphone]
✅ Audio capture started successfully
🎧 Listening for wake word...
```

---

## 📞 Support

- **Issues**: Report on GitHub
- **Documentation**: See `VOICE_SYSTEM_STATUS.md`
- **Performance**: See `VOICE_SYSTEM_STATUS.md`

---

**Status:** ✅ PRODUCTION-READY  
**Version:** 2.0.0  
**Last Updated:** February 12, 2026
