"""Cross-Device Continuity and Handoff for Agent Guru."""
from Agent_Guru.sync.engine import SyncEngine, ContextDelta
from Agent_Guru.sync.crdt import LWWRegister, CRDTEntry, resolve_conflict

__all__ = ["SyncEngine", "ContextDelta", "LWWRegister", "CRDTEntry", "resolve_conflict"]
