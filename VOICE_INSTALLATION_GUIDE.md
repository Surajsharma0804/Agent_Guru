# AGENT_GURU Voice Installation Guide

## 🎙️ Voice-Driven AI Companion

AGENT_GURU is a fully voice-enabled AI assistant that you can talk to naturally. No typing required!

---

## 📦 Installation Options

### Option 1: Windows Installer (.exe)

#### Prerequisites
- Windows 10 or later
- Microphone and speakers
- Internet connection (for initial setup)

#### Installation Steps

1. **Download the Installer**
   - Download `AGENT_GURU-Windows-Installer.zip`
   - Extract to a folder (e.g., `C:\AGENT_GURU`)

2. **Run Setup**
   ```cmd
   cd C:\AGENT_GURU
   scripts\setup.bat
   ```

3. **Choose Your Mode**
   
   **LOCAL MODE (Recommended for Privacy)**
   - Uses Ollama (runs on your computer)
   - No data sent to cloud
   - Requires ~8GB disk space for models
   - Setup will:
     - Install Ollama
     - Download AI models (mistral:7b, qwen2.5:14b)
     - Start Ollama service

   **CLOUD MODE (Faster, Requires API Keys)**
   - Uses OpenAI or Google Gemini
   - Requires API keys (paid services)
   - Setup will:
     - Prompt for API keys
     - Save keys to environment variables

4. **Launch AGENT_GURU**
   ```cmd
   AGENT_GURU.bat
   ```
   Or double-click `AGENT_GURU.bat`

5. **Start Talking!**
   - Say "Hey Guru" or "Hey Maya" to wake up
   - Speak naturally
   - AGENT_GURU will respond with voice

---

### Option 2: macOS Installer (.app)

#### Prerequisites
- macOS 10.15 (Catalina) or later
- Microphone and speakers
- Internet connection (for initial setup)

#### Installation Steps

1. **Download the Installer**
   - Download `AGENT_GURU-Installer.dmg`
   - Double-click to mount

2. **Install the App**
   - Drag `AGENT_GURU.app` to Applications folder
   - Eject the DMG

3. **First Launch**
   - Open `AGENT_GURU` from Applications
   - Grant microphone permissions when prompted
   - Setup wizard will launch automatically

4. **Choose Your Mode**
   
   **LOCAL MODE (Recommended for Privacy)**
   - Setup will:
     - Install Homebrew (if needed)
     - Install Ollama via Homebrew
     - Download AI models
     - Configure Ollama service

   **CLOUD MODE (Faster, Requires API Keys)**
   - Setup will:
     - Prompt for API keys
     - Save keys to shell profile (~/.zshrc)

5. **Start Talking!**
   - Say "Hey Guru" or "Hey Maya" to wake up
   - Speak naturally
   - AGENT_GURU will respond with voice

---

### Option 3: Build from Source

#### Prerequisites
- Rust 1.75 or later
- Git
- Microphone and speakers

#### Build Steps

1. **Clone Repository**
   ```bash
   git clone https://github.com/Surajsharma0804/Agent_Guru.git
   cd Agent_Guru
   ```

2. **Build Release Binary**
   ```bash
   cargo build --release --bin agent_guru_voice
   ```

3. **Run Setup**
   
   **Windows:**
   ```cmd
   scripts\create_windows_installer.bat
   cd installers\windows
   scripts\setup.bat
   ```

   **macOS/Linux:**
   ```bash
   chmod +x scripts/create_macos_app.sh
   ./scripts/create_macos_app.sh
   ```

4. **Launch**
   ```bash
   ./target/release/agent_guru_voice
   ```

---

## 🎤 Voice Commands

### Wake Words
- "Hey Guru"
- "Hey Maya"

### Control Commands
- "Stop listening" - Pause voice recognition
- "Exit" / "Goodbye" / "Quit" - Close AGENT_GURU

### Natural Conversation
Just speak naturally! Examples:
- "What's the weather like?"
- "Tell me a joke"
- "Help me write some code"
- "Explain quantum computing"
- "What should I do today?"

---

## ⚙️ Configuration

### LLM Configuration
Edit `.kiro/llm_config.yaml` to customize:

```yaml
mode: local  # or 'api'
default_provider: ollama  # or 'openai', 'gemini'

tasks:
  intent_extraction:
    provider: ollama
    model: "mistral:7b-instruct"
  
  language_help:
    provider: ollama
    model: "qwen2.5:14b-instruct"
```

### Voice Configuration
Edit `.kiro/voice_config.yaml` to customize:

```yaml
wake_word_config:
  wake_words:
    - "guru"
    - "maya"
  sensitivity: 0.7
  confidence_threshold: 0.8

audio_config:
  sample_rate: 16000
  input_device: null  # null = default microphone
  output_device: null  # null = default speakers
```

---

## 🔧 Troubleshooting

### "Wake word not detected"
- Check microphone permissions
- Increase sensitivity in config
- Speak clearly and closer to microphone
- Check microphone is not muted

### "Ollama not found"
**Windows:**
```cmd
where ollama
```
If not found, reinstall from https://ollama.ai/download

**macOS:**
```bash
which ollama
```
If not found:
```bash
brew install ollama
```

### "Models not available"
```bash
ollama pull mistral:7b-instruct
ollama pull qwen2.5:14b-instruct
```

### "API key errors"
**Windows:**
```cmd
setx OPENAI_API_KEY "your-key-here"
setx GEMINI_API_KEY "your-key-here"
```

**macOS/Linux:**
```bash
export OPENAI_API_KEY="your-key-here"
export GEMINI_API_KEY="your-key-here"
```

Add to `~/.zshrc` or `~/.bash_profile` for persistence.

### "Audio device error"
- Check microphone is connected
- Check speakers/headphones are connected
- Grant microphone permissions in system settings
- Try different audio device in config

---

## 📊 Performance Requirements

### Minimum Requirements
- CPU: 4 cores, 2.0 GHz
- RAM: 8 GB
- Disk: 10 GB free space (for local models)
- Microphone: Any USB or built-in mic
- Speakers: Any audio output device

### Recommended Requirements
- CPU: 8 cores, 3.0 GHz
- RAM: 16 GB
- Disk: 20 GB free space
- GPU: Optional (for faster inference)
- Microphone: High-quality USB mic
- Speakers: Good quality speakers or headphones

### Performance Targets
- Wake word detection: ≤50ms
- Speech-to-text: ≤120ms
- LLM response: ≤200ms
- Text-to-speech: ≤100ms
- Total latency: <500ms

---

## 🔐 Privacy & Security

### Local Mode (Ollama)
- ✅ All processing on your computer
- ✅ No data sent to cloud
- ✅ Complete privacy
- ✅ Works offline
- ✅ No API costs

### Cloud Mode (OpenAI/Gemini)
- ⚠️ Voice data sent to API providers
- ⚠️ Subject to provider privacy policies
- ⚠️ Requires internet connection
- ⚠️ API usage costs apply
- ✅ Faster responses
- ✅ More advanced models

### Data Storage
- Conversation history: `~/.kiro/logs/`
- Audio recordings: Not stored (processed in real-time)
- Configuration: `~/.kiro/`
- Audit logs: `~/.kiro/logs/llm_audit.jsonl`

---

## 🆘 Support

### Documentation
- Full docs: https://github.com/Surajsharma0804/Agent_Guru
- API reference: https://docs.rs/agent_guru

### Issues
- Report bugs: https://github.com/Surajsharma0804/Agent_Guru/issues
- Feature requests: https://github.com/Surajsharma0804/Agent_Guru/discussions

### Community
- Discord: [Coming soon]
- Reddit: r/AgentGuru [Coming soon]

---

## 📝 License

AGENT_GURU is licensed under MIT OR Apache-2.0.

---

## 🎉 Quick Start Checklist

- [ ] Download installer for your platform
- [ ] Run setup script
- [ ] Choose LOCAL or CLOUD mode
- [ ] Install Ollama (LOCAL) or add API keys (CLOUD)
- [ ] Launch AGENT_GURU
- [ ] Grant microphone permissions
- [ ] Say "Hey Guru" to test
- [ ] Start chatting!

---

**Ready to talk to your AI companion? Let's go! 🚀**
