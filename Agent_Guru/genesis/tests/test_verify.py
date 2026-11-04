"""Verification results: six labels, never an invented PASS."""

from __future__ import annotations

import hashlib

import pytest

from Agent_Guru.genesis import actions as act
from Agent_Guru.genesis import verify
from Agent_Guru.genesis.layout import Layout


def ctx_for(tmp_path, run=None):
    return act.ActionContext(layout=Layout(tmp_path / "AG", tmp_path / "app"), emit=lambda k, d: None,
                             run=run or (lambda *a, **k: (0, "")))


def test_only_the_six_labels_exist():
    assert verify.LABELS == ("PASS", "WARNING", "NOT INSTALLED", "NOT CONFIGURED", "FAILED", "NOT APPLICABLE")  # nosec B101
    with pytest.raises(ValueError, match="unknown verification result"):
        verify.Result("OK", "made up")


def test_only_pass_and_warning_count_as_installed():
    assert [verify.Result(label, "").counts_as_installed for label in verify.LABELS] == \
        [True, True, False, False, False, False]  # nosec B101


def test_an_unknown_probe_is_a_failure_not_a_pass(tmp_path):
    r = verify.run("does.not.exist", ctx_for(tmp_path), {})
    assert r.label == "FAILED" and "no probe" in r.detail  # nosec B101


def test_a_probe_that_raises_is_failed_with_its_message(tmp_path, monkeypatch):
    def boom(ctx, c):
        raise RuntimeError("model file locked")

    monkeypatch.setitem(verify.PROBES, "boom", boom)
    r = verify.run("boom", ctx_for(tmp_path), {})
    assert r.label == "FAILED" and "model file locked" in r.detail  # nosec B101


def test_pinned_files_pass_only_when_every_hash_matches(tmp_path):
    ctx = ctx_for(tmp_path)
    data = b"weights"
    comp = {"dest": "runtime:models", "files": [{"name": "m.bin", "size": len(data),
                                                 "sha256": hashlib.sha256(data).hexdigest(), "url": "https://x.test/m"}]}
    assert verify.run("files.pinned", ctx, comp).label == "NOT INSTALLED"  # nosec B101
    folder = ctx.layout.runtime_root / "models"
    folder.mkdir(parents=True)
    (folder / "m.bin").write_bytes(b"WEIGHTS")  # same size, other bytes
    assert verify.run("files.pinned", ctx, comp).label == "FAILED"  # nosec B101
    (folder / "m.bin").write_bytes(data)
    assert verify.run("files.pinned", ctx, comp).label == "PASS"  # nosec B101


def test_a_runtime_check_reports_what_the_runtime_said(tmp_path):
    answers = {"core.import": '{"result": "PASS", "detail": "imports", "seconds": 0.9}',
               "tts.synthesize": '{"result": "PASS", "detail": "48160 samples"}',
               "wake.load": '{"result": "WARNING", "detail": "fallback detector"}',
               "llm.reply": '{"result": "MAYBE", "detail": "?"}'}
    seen = []

    def run(args, **k):
        seen.append(args)
        return 0, answers[args[4]] + "\n"

    ctx = ctx_for(tmp_path, run)
    ctx.layout.venv_python.parent.mkdir(parents=True)
    ctx.layout.venv_python.write_bytes(b"")
    assert verify.run("core.import", ctx, {}).data == {"seconds": 0.9}  # nosec B101
    tts = verify.run("tts.synthesize", ctx, {})
    assert tts.label == "PASS" and "confirm you hear" in tts.needs_person  # nosec B101  a person must listen
    wake = verify.run("wake.load", ctx, {})
    assert wake.label == "WARNING" and wake.needs_person == ""  # nosec B101
    assert verify.run("llm.reply", ctx, {}).label == "FAILED"  # nosec B101  an answer outside the six is a failure


def test_without_the_private_environment_a_runtime_check_is_not_installed(tmp_path):
    assert verify.run("core.import", ctx_for(tmp_path), {}).label == "NOT INSTALLED"  # nosec B101


def test_the_chat_check_gets_the_components_model_or_the_plans(tmp_path):
    asked = []

    def run(args, **k):
        asked.append(args[5:])
        return 0, '{"result": "PASS", "detail": "ok"}'

    ctx = ctx_for(tmp_path, run)
    ctx.model = "qwen2.5:1.5b"
    ctx.layout.venv_python.parent.mkdir(parents=True)
    ctx.layout.venv_python.write_bytes(b"")
    verify.run("llm.reply", ctx, {})
    verify.run("llm.reply", ctx, {"model": "gemma3:4b"})
    assert asked == [["qwen2.5:1.5b"], ["gemma3:4b"]]  # nosec B101
