"""
Agent Guru - AI Voice Assistant Platform

An always-on, cross-platform AI voice assistant with wake word detection,
speech recognition, face recognition, and intelligent conversation capabilities.

Components:
- speech: Speech engine (wake word, STT, TTS, voice biometrics)
- vision: Vision engine (face detection, recognition, emotion)
- llm: LLM runtime (multi-provider support)
- platform: Platform integration (OS control)
- agents: Agent orchestration
- memory: Memory system
- deployment: Deployment system
- policy: Policy engine
- security: Security & cryptography
- avatar: Avatar & emotion engine
"""

__version__ = "0.1.0"
__author__ = "Agent Guru Team"

# Lazy imports — sub-packages are only loaded when accessed.
# This prevents heavy ML libraries (TTS, insightface, vosk, etc.) from
# being imported at package import time, which would crash on platforms
# where optional dependencies are not installed.

def __getattr__(name: str):  # noqa: ANN201
    """Lazy-load sub-packages on first access."""
    _subpackages = {
        "speech", "vision", "llm", "platform",
        "agents", "memory", "deployment", "policy",
        "security", "avatar",
    }
    if name in _subpackages:
        import importlib
        module = importlib.import_module(f"Agent_Guru.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module 'Agent_Guru' has no attribute {name!r}")


__all__ = [
    "speech",
    "vision",
    "llm",
    "platform",
    "agents",
    "memory",
    "deployment",
    "policy",
    "security",
    "avatar",
]
