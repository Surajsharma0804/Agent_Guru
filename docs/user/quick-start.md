# Agent Guru - Quick Start Guide

## What is Agent Guru?

Agent Guru is an always-on AI voice assistant with two personalities:
- **Guru** (male voice) - professional, analytical, great for productivity
- **Maya** (female voice) - warm, creative, great for personal tasks

Say "Hey Guru" or "Hey Maya" to activate.

---

## Installation

### Windows
1. Download `AgentGuru-Setup-x64.exe`
2. Run the installer (requires Windows 10 or later)
3. Follow the setup wizard
4. Launch from the desktop shortcut or Start Menu

### macOS
1. Download `AgentGuru-1.0.0.dmg`
2. Open the DMG and drag Agent Guru to Applications
3. Launch from Applications or Spotlight
4. Grant microphone and accessibility permissions when prompted

### System Requirements
- **OS**: Windows 10+ or macOS 11+
- **RAM**: 4 GB minimum (8 GB recommended)
- **Disk**: 2 GB free space
- **Microphone**: Required for voice commands
- **GPU**: Optional but recommended (NVIDIA CUDA for best performance)

---

## First Launch

1. **Choose your AI provider** - On first launch, select your LLM provider:
   - **Local (Ollama)** - Free, private, works offline (desktop only)
   - **OpenAI** - Enter your API key for GPT-4
   - **Google Gemini** - Enter your API key
   - **Anthropic Claude** - Enter your API key

2. **Test your microphone** - Say "Hey Guru, hello" to verify detection

3. **Grant permissions** (macOS) - Allow microphone and accessibility access

---

## Basic Commands

### Voice Activation
```
"Hey Guru"    → Activates Guru (professional mode)
"Hey Maya"    → Activates Maya (creative mode)
```

### Application Control
```
"Open YouTube"
"Open Notepad"
"Open WhatsApp"
"Close this window"
"Minimize everything"
```

### Typing and Text
```
"Type hello world"
"Write an email to [name]"
"Search for Python tutorials"
```

### System Control
```
"Take a screenshot"
"Increase volume"
"Turn on dark mode"
"Lock the screen"
```

### Conversation
```
"What's the weather today?"
"Explain quantum computing"
"Write a poem about autumn"
"Translate 'hello' to Spanish"
```

### Pipeline Control
```
"Stop listening"    → Pause voice detection
"Hey Guru"          → Resume from pause
"Exit" / "Goodbye"  → Quit Agent Guru
```

---

## Tips

- **Speak clearly** - Agent Guru works best with clear speech at normal pace
- **Reduce background noise** - Works in noisy environments but quieter is better
- **Use natural language** - No need for exact command syntax
- **Interrupt anytime** - Say "stop" while Guru/Maya is speaking to interrupt

---

## Troubleshooting

**Wake word not detected?**
- Check microphone is connected and selected as default
- Speak louder or move closer to microphone
- Check microphone permissions in system settings

**Slow responses?**
- Switch to a local Ollama model for faster responses
- Ensure GPU drivers are up to date
- Close other resource-intensive applications

**Can't open applications?**
- macOS: Grant accessibility permissions in System Preferences → Privacy & Security
- Windows: Run Agent Guru as administrator if needed

See the full [Troubleshooting Guide](troubleshooting.md) for more help.
