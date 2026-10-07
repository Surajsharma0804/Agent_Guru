"""The audit log keeps its entries across restarts and shows edits, deletions and reordering.

The orchestrator wrote one signed entry per turn into an in-memory database,
so the whole audit trail was gone when the app exited; and a log kept on disk
would have failed verification after every restart, because each process
made a new signing key. Signatures alone also could not show an entry had
been deleted. These tests had no predecessor: nothing tested the audit
logger before.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import threading

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from Agent_Guru.security.audit.logger import AuditLogger, EventType, LogQuery, signing_key_at


@pytest.fixture
def key():
    return Ed25519PrivateKey.generate().private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption(),
    )


def _log(logger, n=3, start=0):
    for i in range(start, start + n):
        logger.log_event(EventType.POLICY_ALLOWED, "guru_pipeline", f"intent:{i}", "success", {"turn": i})


def test_entries_written_by_one_run_verify_in_the_next(tmp_path, key):
    path = str(tmp_path / "audit.db")
    _log(AuditLogger(path, signing_key=key))
    again = AuditLogger(path, signing_key=key)
    _log(again, start=3)
    assert again.verify_chain() == (True, None)  # nosec B101
    entries = again.query_logs(LogQuery())
    assert [e.target_id for e in entries] == [f"intent:{i}" for i in range(6)]  # nosec B101
    assert not any(e.tampered for e in entries)  # nosec B101


def test_an_edited_entry_is_found(tmp_path, key):
    path = str(tmp_path / "audit.db")
    log = AuditLogger(path, signing_key=key)
    _log(log)
    victim = log.query_logs(LogQuery())[1]
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE audit_logs SET outcome = 'failure' WHERE entry_id = ?", (victim.entry_id,))
    assert log.verify_chain() == (False, victim.entry_id)  # nosec B101
    assert [e.tampered for e in log.query_logs(LogQuery())] == [False, True, False]  # nosec B101


def test_a_deleted_entry_is_found_although_every_signature_is_valid(tmp_path, key):
    path = str(tmp_path / "audit.db")
    log = AuditLogger(path, signing_key=key)
    _log(log, n=4)
    entries = log.query_logs(LogQuery())
    with sqlite3.connect(path) as conn:
        conn.execute("DELETE FROM audit_logs WHERE entry_id = ?", (entries[1].entry_id,))
    assert not any(e.tampered for e in log.query_logs(LogQuery()))  # nosec B101  signatures cannot see it
    assert log.verify_chain() == (False, entries[2].entry_id)  # nosec B101


def test_a_reordered_entry_is_found(tmp_path, key):
    path = str(tmp_path / "audit.db")
    log = AuditLogger(path, signing_key=key)
    _log(log)
    first = log.query_logs(LogQuery())[0]
    with sqlite3.connect(path) as conn:
        row = conn.execute("SELECT * FROM audit_logs WHERE entry_id = ?", (first.entry_id,)).fetchone()
        conn.execute("DELETE FROM audit_logs WHERE entry_id = ?", (first.entry_id,))
        conn.execute(f"INSERT INTO audit_logs VALUES ({','.join('?' * len(row))})", row)  # nosec B608
    ok, where = log.verify_chain()
    assert not ok and where is not None  # nosec B101


def test_entries_from_before_the_chain_still_verify_and_the_chain_continues(tmp_path, key):
    # A log written by the previous code: no hash columns, signed without one.
    path = str(tmp_path / "audit.db")
    signer = Ed25519PrivateKey.from_private_bytes(key)
    with sqlite3.connect(path) as conn:
        conn.execute("""CREATE TABLE audit_logs (entry_id TEXT PRIMARY KEY, timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL, actor_id TEXT, target_id TEXT, outcome TEXT NOT NULL,
            details TEXT NOT NULL, signature BLOB NOT NULL)""")
        content = json.dumps({"entry_id": "old-1", "timestamp": "2026-10-01T10:00:00+00:00",
                              "event_type": "policy_allowed", "actor_id": "guru_pipeline", "target_id": "x",
                              "outcome": "success", "details": {}}, sort_keys=True).encode()
        conn.execute("INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?)",
                     ("old-1", "2026-10-01T10:00:00+00:00", "policy_allowed", "guru_pipeline", "x", "success",
                      "{}", signer.sign(content)))
    log = AuditLogger(path, signing_key=key)
    _log(log, n=2)
    entries = log.query_logs(LogQuery())
    assert [e.prev_hash is None for e in entries] == [True, False, False]  # nosec B101
    assert entries[1].prev_hash == "" and entries[2].prev_hash == entries[1].entry_hash  # nosec B101
    assert log.verify_chain() == (True, None)  # nosec B101


def test_writers_on_many_threads_never_fork_the_chain(tmp_path, key):
    log = AuditLogger(str(tmp_path / "audit.db"), signing_key=key)
    threads = [threading.Thread(target=_log, args=(log, 10, i * 10)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(log.query_logs(LogQuery())) == 40 and log.verify_chain() == (True, None)  # nosec B101


def test_a_different_key_cannot_verify_the_log(tmp_path, key):
    path = str(tmp_path / "audit.db")
    _log(AuditLogger(path, signing_key=key))
    other = Ed25519PrivateKey.generate().private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption(),
    )
    ok, _ = AuditLogger(path, signing_key=other).verify_chain()
    assert not ok  # nosec B101


def test_the_signing_key_is_the_same_on_every_start(tmp_path):
    path = tmp_path / "audit_signing.key"
    first = signing_key_at(path)
    assert signing_key_at(path) == first  # nosec B101
    Ed25519PrivateKey.from_private_bytes(first)


@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI is Windows-only")
def test_on_windows_the_key_file_is_encrypted_for_this_account(tmp_path):
    path = tmp_path / "audit_signing.key"
    key = signing_key_at(path)
    stored = path.read_bytes()
    assert key not in stored and len(stored) > len(key)  # nosec B101


def test_an_unreadable_key_file_is_reported_not_replaced(tmp_path):
    path = tmp_path / "audit_signing.key"
    path.write_bytes(b"not a key")
    with pytest.raises(Exception):  # noqa: B017, PT011  DPAPI, or the key check off Windows
        signing_key_at(path)
    assert path.read_bytes() == b"not a key"  # nosec B101


def test_secrets_in_details_are_still_redacted(tmp_path, key):
    log = AuditLogger(str(tmp_path / "audit.db"), signing_key=key)
    log.log_event(EventType.POLICY_ALLOWED, "a", "b", "success", {"api_key": "sk-123", "items": [{"token": "t"}]})
    [entry] = log.query_logs(LogQuery())
    assert entry.details == {"api_key": "[REDACTED]", "items": [{"token": "[REDACTED]"}]}  # nosec B101
    assert log.verify_chain() == (True, None)  # nosec B101


# ---- wiring ----

async def test_each_turn_is_written_to_the_audit_log_the_assistant_was_given(tmp_path, key):
    import numpy as np

    from Agent_Guru.integration.orchestrator import IntegrationOrchestrator, WakeWordEvent

    class Allow:
        def evaluate(self, intent):
            return True

    path = str(tmp_path / "audit.db")
    orch = IntegrationOrchestrator(
        speech_engine=None, vision_engine=None, llm_runtime=None, platform_controller=None,
        agent_orchestrator=None, memory=None, reasoning=None, security=None, policy=Allow(),
        avatar=None, deployment=None, gpu_pool=None, audit_logger=AuditLogger(path, signing_key=key),
    )

    async def stt(*a, **k):
        return "what time is it", "en"

    async def silent(*a, **k):
        return None

    orch._stage_stt, orch._stage_tts, orch._play_filler = stt, silent, silent
    await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru", audio=np.zeros(16000, np.float32).tobytes()))
    reopened = AuditLogger(path, signing_key=key)
    [entry] = reopened.query_logs(LogQuery())
    assert entry.details["transcript"] == "what time is it" and reopened.verify_chain() == (True, None)  # nosec B101


def test_without_one_the_assistant_keeps_its_audit_log_in_memory():
    from Agent_Guru.integration.orchestrator import IntegrationOrchestrator

    orch = IntegrationOrchestrator(
        speech_engine=None, vision_engine=None, llm_runtime=None, platform_controller=None,
        agent_orchestrator=None, memory=None, reasoning=None, security=None, policy=None,
        avatar=None, deployment=None, gpu_pool=None,
    )
    assert orch._audit_logger._conn.execute("PRAGMA database_list").fetchone()[2] == ""  # nosec B101


def test_an_unreadable_key_leaves_the_log_in_memory_and_the_key_untouched(tmp_path):
    # main.py replaces sys.stdout and sys.stderr when imported, so it runs in
    # its own process, as in test_follow_up_answers.py.
    import os
    import subprocess  # nosec B404
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    key_path = tmp_path / "agent_guru" / "audit_signing.key"
    key_path.parent.mkdir()
    key_path.write_bytes(b"damaged")
    env = dict(os.environ, LOCALAPPDATA=str(tmp_path), XDG_DATA_HOME=str(tmp_path))
    out = subprocess.run(  # nosec B603
        [sys.executable, "-c", "import main; print('RESULT', main._load_audit_logger())"],
        cwd=root, env=env, capture_output=True, text=True, timeout=120, check=False,
    )
    assert "RESULT None" in out.stdout, out.stderr[-2000:]  # nosec B101
    assert key_path.read_bytes() == b"damaged"  # nosec B101


async def test_doctor_reports_a_broken_audit_log(tmp_path, monkeypatch):
    from Agent_Guru.platform.error_handling import doctor
    from Agent_Guru.platform.error_handling.health_check import HealthStatus

    monkeypatch.setattr(doctor, "_app_data", lambda: tmp_path)
    log = AuditLogger(str(tmp_path / "audit.db"), signing_key=signing_key_at(tmp_path / "audit_signing.key"))
    _log(log)
    assert (await doctor.check_audit_log()).status is HealthStatus.HEALTHY  # nosec B101
    victim = log.query_logs(LogQuery())[0]
    with sqlite3.connect(str(tmp_path / "audit.db")) as conn:
        conn.execute("UPDATE audit_logs SET target_id = 'forged' WHERE entry_id = ?", (victim.entry_id,))
    result = await doctor.check_audit_log()
    assert result.status is HealthStatus.UNHEALTHY and victim.entry_id in result.message  # nosec B101
