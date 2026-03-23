"""Cross-Device Continuity and Handoff for Agent Guru."""
from Agent_Guru.sync.crdt import CRDTEntry, LWWRegister, resolve_conflict
from Agent_Guru.sync.engine import ContextDelta, SyncEngine

__all__ = ["SyncEngine", "ContextDelta", "LWWRegister", "CRDTEntry", "resolve_conflict"]
