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

# Static dispatch table: maps attribute name → fully-qualified module path.
# All values are hardcoded string literals defined at module load time.
# The user-supplied attribute name is ONLY used as a dict key; the value
# passed to import_module is always one of these literals, never derived
# from external input.  Suppression below is justified: the argument to
# import_module is a compile-time constant retrieved from this table.
_SUBPACKAGE_MODULES: dict[str, str] = {
    "speech":     "Agent_Guru.speech",
    "vision":     "Agent_Guru.vision",
    "llm":        "Agent_Guru.llm",
    "platform":   "Agent_Guru.platform",
    "agents":     "Agent_Guru.agents",
    "memory":     "Agent_Guru.memory",
    "deployment": "Agent_Guru.deployment",
    "policy":     "Agent_Guru.policy",
    "security":   "Agent_Guru.security",
    "avatar":     "Agent_Guru.avatar",
}


def __getattr__(name: str):  # noqa: ANN201
    """Lazy-load sub-packages on first access."""
    if name not in _SUBPACKAGE_MODULES:
        raise AttributeError(f"module 'Agent_Guru' has no attribute {name!r}")

    import importlib

    # `module_path` is a hardcoded literal from _SUBPACKAGE_MODULES, not
    # derived from `name`.  nosec: B302 — import_module argument is a
    # compile-time constant; taint from `name` does not reach this call.
    module_path: str = _SUBPACKAGE_MODULES[name]
    module = importlib.import_module(module_path)  # nosec B302
    globals()[name] = module
    return module


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
