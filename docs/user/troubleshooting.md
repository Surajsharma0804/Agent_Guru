# Agent Guru - Troubleshooting Guide

## Wake Word Issues

### Wake word not detected
1. **Check microphone** - Ensure microphone is connected and set as default input
2. **Check permissions** - macOS: System Preferences → Privacy & Security → Microphone
3. **Reduce noise** - Move away from fans, AC units, or other noise sources
4. **Speak clearly** - Say "Hey Guru" or "Hey Maya" at normal volume
5. **Check logs** - View `.kiro/logs/errors.log` for microphone errors

### Too many false activations
- Adjust wake word sensitivity in Settings → Voice → Sensitivity
- Use a directional microphone to reduce ambient noise pickup

---

## Speech Recognition Issues

### Poor transcription accuracy
1. Speak at a normal pace - not too fast or slow
2. Ensure microphone is within 1-2 meters
3. Reduce background noise
4. Check that the correct language is selected in Settings

### STT not starting after wake word
- Check that microphone permissions are granted
- Restart Agent Guru
- Check `.kiro/logs/errors.log` for STT errors

---

## LLM / AI Response Issues

### Slow responses
1. **Use local Ollama** - Fastest option, no network required
2. **Check internet** - Cloud providers need stable internet
3. **Check API key** - Verify API key is valid in Settings → AI Provider
4. **GPU acceleration** - Ensure CUDA drivers are installed for GPU speedup

### No response / timeout
1. Check internet connection for cloud providers
2. Verify API key hasn't expired or run out of credits
3. Try switching to a different provider in Settings
4. Check `.kiro/logs/errors.log` for LLM errors

### Wrong or irrelevant responses
- Rephrase your question more clearly
- Check that the correct personality (Guru/Maya) is active
- Clear conversation history: say "Delete my history"

---

## OS Control Issues

### Can't open applications (macOS)
1. Go to System Preferences → Privacy & Security → Accessibility
2. Add Agent Guru to the allowed applications list
3. Restart Agent Guru

### Can't open applications (Windows)
1. Right-click Agent Guru → Run as Administrator
2. Check Windows Defender isn't blocking the action
3. Verify the application name is correct

### Keyboard/mouse simulation not working
- macOS: Grant Accessibility permissions (see above)
- Windows: Disable UAC prompts for the target application

---

## Audio Playback Issues

### No voice output
1. Check system volume is not muted
2. Check correct audio output device is selected
3. Restart Agent Guru
4. Check `.kiro/logs/errors.log` for TTS errors

### Distorted or choppy audio
1. Close other audio applications
2. Check audio driver is up to date
3. Try a different audio output device

---

## Performance Issues

### High CPU usage
1. Ensure GPU acceleration is enabled (Settings → Performance → GPU)
2. Close other resource-intensive applications
3. Reduce wake word sensitivity

### High memory usage
1. Clear conversation history: say "Delete my history"
2. Restart Agent Guru to free memory
3. Check for memory leaks in `.kiro/logs/errors.log`

### Slow startup
1. First startup downloads models - this is normal (one-time)
2. Subsequent startups should be under 5 seconds
3. Ensure models are stored on an SSD

---

## Installation Issues

### Installation fails (Windows)
1. Run installer as Administrator
2. Temporarily disable antivirus
3. Ensure 2+ GB free disk space
4. Check Windows Event Log for errors

### Installation fails (macOS)
1. Check macOS version is 11 (Big Sur) or later
2. Allow installation from identified developers in Security settings
3. Ensure 2+ GB free disk space

---

## Log Files

Agent Guru logs are stored in:
- **Windows**: `%APPDATA%\AgentGuru\logs\`
- **macOS**: `~/Library/Logs/AgentGuru/`
- **Development**: `.kiro/logs/`

Key log files:
- `errors.log` - All errors with timestamps
- `os_audit.jsonl` - OS action audit trail

---

## Getting Help

If you can't resolve an issue:
1. Check the [FAQ](faq.md)
2. Search existing issues on GitHub
3. Open a new issue with your log files attached
