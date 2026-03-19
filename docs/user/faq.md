# Agent Guru - FAQ

## General

**Q: Is Agent Guru free?**
A: Agent Guru is free and open source. You only pay for cloud LLM API usage (OpenAI, Gemini, Claude) if you choose those providers. Local Ollama is completely free.

**Q: Does Agent Guru work offline?**
A: Yes, with local Ollama on desktop. Wake word detection, speech recognition, and TTS all work offline. Cloud LLM providers require internet.

**Q: Is my data private?**
A: With local Ollama, no audio or conversation data leaves your device. With cloud providers, your queries are sent to the respective API (OpenAI, Google, Anthropic) per their privacy policies.

**Q: What languages are supported?**
A: English is fully supported. Additional language support depends on your chosen STT and TTS models.

---

## Setup

**Q: Which LLM provider should I choose?**
A: 
- **Local Ollama** - Best for privacy and offline use (desktop only)
- **OpenAI GPT-4** - Best quality responses
- **Google Gemini** - Good balance of speed and quality
- **Anthropic Claude** - Excellent for long conversations

**Q: Do I need a GPU?**
A: No, but a GPU (NVIDIA CUDA) significantly improves performance:
- Speech recognition: 10-50x faster
- Face recognition: 30-60 FPS vs 5-10 FPS
- Local LLM inference: 5-10x faster

**Q: How do I update Agent Guru?**
A: Download and run the latest installer. Your settings and conversation history are preserved.

---

## Voice Commands

**Q: What if Agent Guru doesn't understand my command?**
A: Try rephrasing. Agent Guru uses LLM fallback for ambiguous commands, so natural language works well. If it still fails, check the command reference.

**Q: Can I customize wake words?**
A: Currently "Hey Guru" and "Hey Maya" are the supported wake words. Custom wake word support is planned for a future release.

**Q: Can Agent Guru control any application?**
A: Agent Guru can control most applications through OS-level automation. Some applications with strict security sandboxing may not be controllable.

---

## Privacy & Security

**Q: Does Agent Guru record audio continuously?**
A: Agent Guru only processes audio locally for wake word detection. Full audio is only captured after wake word detection and is not stored.

**Q: Where is conversation history stored?**
A: Conversation history is stored locally in encrypted format:
- Windows: `%APPDATA%\AgentGuru\memory\`
- macOS: `~/Library/Application Support/AgentGuru/memory/`

**Q: How do I delete my data?**
A: Say "Delete my history" or go to Settings → Privacy → Clear History.

---

## Performance

**Q: How fast is Agent Guru?**
A: Target performance:
- Wake word detection: <200ms
- Speech recognition: <1s
- Intent classification: <50ms
- LLM response: <2s (local) / <3s (cloud)
- End-to-end: <2.5s

**Q: Why is the first response slow?**
A: Models are loaded into memory on first use. Subsequent responses are much faster.
