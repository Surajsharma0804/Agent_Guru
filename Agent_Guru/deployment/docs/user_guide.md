# Agent Guru - User Guide

## Overview

Agent Guru is an always-on AI voice assistant with dual personalities:
- **Guru** (male voice) - professional, analytical, productivity-focused
- **Maya** (female voice) - warm, creative, personal assistance

---

## Installation

### Windows
1. Download `AgentGuru-Setup.msi` from https://agentguru.ai/download
2. Run the installer - Agent Guru starts automatically on boot
3. Say **"Hey Guru"** or **"Hey Maya"** to begin

### macOS
1. Download `AgentGuru.dmg` and drag to Applications
2. Open Agent Guru from Applications
3. Grant microphone and camera permissions when prompted

### Linux
```bash
# Ubuntu/Debian
sudo dpkg -i agent-guru_1.0.0_amd64.deb

# Fedora/RHEL
sudo rpm -i agent-guru-1.0.0.x86_64.rpm

# AppImage (any distro)
chmod +x AgentGuru-1.0.0.AppImage && ./AgentGuru-1.0.0.AppImage
```

### Android
Install from Google Play Store: search **"Agent Guru"**

### iOS
Install from App Store: search **"Agent Guru"**

---

## First-Time Setup (Onboarding)

1. **Welcome** - Choose your preferred personality (Guru or Maya)
2. **Profile** - Enter your name, age, and preferences
3. **Biometric Enrollment** - Enroll face and/or voice for secure authentication
4. **LLM Configuration**:
   - Desktop: Choose local Ollama (free, private) or cloud API
   - Mobile: Enter your cloud API key (OpenAI, Gemini, Anthropic, or DeepSeek)
5. **Permissions** - Grant microphone, camera, and accessibility access
6. **Test** - Say "Hey Guru" to verify everything works

---

## Voice Commands

### System Control
| Command | Action |
|---------|--------|
| "Open [app name]" | Launch application |
| "Close [app name]" | Close application |
| "Take a screenshot" | Capture screen |
| "Set volume to 50%" | Adjust volume |
| "Turn off WiFi" | Toggle WiFi |

### Information
| Command | Action |
|---------|--------|
| "What time is it?" | Current time |
| "What's the weather?" | Weather forecast |
| "Search for [topic]" | Web search |

### Communication
| Command | Action |
|---------|--------|
| "Send message to [name]" | Open messaging |
| "Call [name]" | Initiate call |

### File Operations
| Command | Action |
|---------|--------|
| "Create file [name]" | Create new file |
| "Delete file [name]" | Delete file (with confirmation) |
| "Move [file] to [folder]" | Move file |

---

## Personality Switching

Say **"Hey Guru"** to activate the Guru personality (professional mode).
Say **"Hey Maya"** to activate the Maya personality (personal mode).

---

## Privacy & Security

- **Local LLM (Desktop)**: All processing stays on your device - no data sent to cloud
- **Cloud API**: Your API key is stored securely in the OS keychain
- **Biometric data**: Never leaves your device
- **Audit log**: All actions are logged locally for your review

---

## Troubleshooting

**Wake word not detected**
- Ensure microphone is not muted
- Speak clearly within 2 metres of the microphone
- Check microphone permissions in system settings

**Slow responses**
- Desktop: Ensure Ollama is running (`ollama serve`)
- Mobile: Check internet connection
- Verify API key is valid

**Authentication failing**
- Re-enroll biometrics from Settings → Security → Re-enroll
- Ensure adequate lighting for face recognition

---

## Support

- Email: support@agentguru.ai
- Forum: https://community.agentguru.ai
- Documentation: https://docs.agentguru.ai
