"""Agent Guru - AI Voice Assistant Platform.

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


def __getattr__(name: str):
    """Lazy-load sub-packages on first access.

    Uses an explicit match statement so the module path passed to
    import_module is always a hardcoded string literal — never derived
    from the caller-supplied ``name``.  This makes it structurally
    impossible for external input to influence the import target.
    """
    import importlib

    match name:
        case "speech":
            _path = "Agent_Guru.speech"
        case "vision":
            _path = "Agent_Guru.vision"
        case "llm":
            _path = "Agent_Guru.llm"
        case "platform":
            _path = "Agent_Guru.platform"
        case "agents":
            _path = "Agent_Guru.agents"
        case "memory":
            _path = "Agent_Guru.memory"
        case "deployment":
            _path = "Agent_Guru.deployment"
        case "policy":
            _path = "Agent_Guru.policy"
        case "security":
            _path = "Agent_Guru.security"
        case "avatar":
            _path = "Agent_Guru.avatar"
        case "reasoning":
            _path = "Agent_Guru.reasoning"
        case "integration":
            _path = "Agent_Guru.integration"
        case _:
            msg = f"module 'Agent_Guru' has no attribute {name!r}"
            raise AttributeError(msg)

    module = importlib.import_module(_path)
    globals()[name] = module
    return module


__all__ = [
    "agents",
    "avatar",
    "deployment",
    "integration",
    "llm",
    "memory",
    "platform",
    "policy",
    "reasoning",
    "security",
    "speech",
    "vision",
]
