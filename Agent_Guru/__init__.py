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

# Import main components
from . import speech
from . import vision
from . import llm
from . import platform
from . import agents
from . import memory
from . import deployment
from . import policy
from . import security
from . import avatar

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
