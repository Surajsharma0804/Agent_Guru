"""Agent Guru - Memory System.

Provides Knowledge Graph, Preference Learning, Experience Repository,
Personality Evolution, Deduplication, GitHub Sync, and Metrics engines.

Quick start::

    from Agent_Guru.memory import MemoryManager, MemoryConfig

    mgr = MemoryManager(MemoryConfig())
    await mgr.initialize()
    await mgr.store_interaction("GURU", user_msg, ai_msg)
    results = await mgr.search("weather", limit=5)
    await mgr.shutdown()
"""

__version__ = "0.1.0"

from Agent_Guru.memory.config import MemoryConfig
from Agent_Guru.memory.memory_manager import MemoryManager

__all__ = [
    "MemoryConfig",
    "MemoryManager",
]
