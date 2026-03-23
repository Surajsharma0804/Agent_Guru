"""Cross-Device Sync Engine with CRDT conflict resolution."""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

from Agent_Guru.sync.crdt import CRDTEntry, resolve_conflict

logger = logging.getLogger(__name__)

PROPAGATION_TARGET_S = 5.0

try:
    pass

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False


@dataclass
class ContextDelta:
    """A signed context delta for cross-device sync."""
    delta_id: str
    device_id: str
    timestamp: float
    payload: dict[str, Any]
    delta_hash: str = ""
    signature: str = ""

    def __post_init__(self) -> None:
        if not self.delta_hash:
            self.delta_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        data = json.dumps({
            "delta_id": self.delta_id,
            "device_id": self.device_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "delta_id": self.delta_id,
            "device_id": self.device_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "delta_hash": self.delta_hash,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ContextDelta":
        obj = cls(
            delta_id=d["delta_id"],
            device_id=d["device_id"],
            timestamp=d["timestamp"],
            payload=d["payload"],
        )
        obj.delta_hash = d.get("delta_hash", obj.delta_hash)
        obj.signature = d.get("signature", "")
        return obj

    def serialize(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def deserialize(cls, data: str) -> "ContextDelta":
        return cls.from_dict(json.loads(data))


class SyncEngine:
    """Manages cross-device context synchronization."""

    def __init__(self, device_id: str, primary: bool = False) -> None:
        self.device_id = device_id
        self.primary = primary
        self._local_deltas: list[ContextDelta] = []
        self._offline_queue: list[ContextDelta] = []
        self._online = True
        self._private_key: Optional[Any] = None
        if _CRYPTO_AVAILABLE:
            self._private_key = Ed25519PrivateKey.generate()

    def _sign(self, data: str) -> str:
        if not _CRYPTO_AVAILABLE or self._private_key is None:
            return ""
        import base64
        sig = self._private_key.sign(data.encode())
        return base64.b64encode(sig).decode()

    def push_delta(self, payload: dict[str, Any]) -> ContextDelta:
        """Create and push a context delta."""
        delta = ContextDelta(
            delta_id=f"{self.device_id}_{int(time.time() * 1000)}",
            device_id=self.device_id,
            timestamp=time.time(),
            payload=payload,
        )
        delta.signature = self._sign(delta.delta_hash)
        if self._online:
            self._local_deltas.append(delta)
        else:
            self._offline_queue.append(delta)
        return delta

    def pull_delta(self, remote_deltas: list[ContextDelta]) -> list[CRDTEntry]:
        """Pull and merge remote deltas using CRDT."""
        local_entries = [
            CRDTEntry(
                key=d.delta_id,
                value=d.payload,
                device_id=d.device_id,
                timestamp=d.timestamp,
            )
            for d in self._local_deltas
        ]
        remote_entries = [
            CRDTEntry(
                key=d.delta_id,
                value=d.payload,
                device_id=d.device_id,
                timestamp=d.timestamp,
            )
            for d in remote_deltas
        ]
        return resolve_conflict(local_entries, remote_entries)

    def resolve_conflict(
        self,
        local: list[ContextDelta],
        remote: list[ContextDelta],
    ) -> list[ContextDelta]:
        """Resolve conflicts; primary device takes precedence."""
        if self.primary:
            # Primary device wins on tie
            merged: dict[str, ContextDelta] = {}
            for d in remote:
                merged[d.delta_id] = d
            for d in local:
                existing = merged.get(d.delta_id)
                if existing is None or d.timestamp >= existing.timestamp:
                    merged[d.delta_id] = d
        else:
            merged = {}
            for d in local:
                merged[d.delta_id] = d
            for d in remote:
                existing = merged.get(d.delta_id)
                if existing is None or d.timestamp > existing.timestamp:
                    merged[d.delta_id] = d
        return sorted(merged.values(), key=lambda x: x.timestamp)

    def handoff(self, task_summary: str) -> dict[str, Any]:
        """Offer conversation resume on another device."""
        return {
            "device_id": self.device_id,
            "task_summary": task_summary,
            "timestamp": time.time(),
            "deltas": [d.to_dict() for d in self._local_deltas[-10:]],
        }

    def set_online(self, online: bool) -> None:
        self._online = online
        if online:
            self._flush_offline_queue()

    def _flush_offline_queue(self) -> None:
        """Replay queued deltas in order."""
        for delta in sorted(self._offline_queue, key=lambda d: d.timestamp):
            self._local_deltas.append(delta)
        self._offline_queue.clear()
        logger.info("Flushed %d offline deltas", len(self._local_deltas))
