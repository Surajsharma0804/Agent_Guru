"""Runtime tasks: one JSON line each, NOT INSTALLED when a package is missing, never a silent pass."""

from __future__ import annotations

import json
import sys
import wave

from Agent_Guru.genesis import runtime_tasks as rt


def test_an_unknown_task_prints_a_failure_and_exits_2(capsys):
    assert rt.main(["rm", "-rf"]) == 2  # nosec B101
    assert json.loads(capsys.readouterr().out)["result"] == "FAILED"  # nosec B101


def test_a_missing_package_is_not_installed_not_failed(monkeypatch):
    monkeypatch.setitem(sys.modules, "cv2", None)
    out = rt.vision_check([])
    assert out["result"] == "NOT INSTALLED" and "cv2" in out["detail"]  # nosec B101


def test_a_task_that_raises_is_reported_as_one_failed_line(monkeypatch, capsys):
    def boom(args):
        raise OSError("disk full")

    monkeypatch.setitem(rt.TASKS, "boom", boom)
    assert rt.main(["boom"]) == 1  # nosec B101
    line = capsys.readouterr().out.strip().splitlines()[-1]
    assert json.loads(line) == {"result": "FAILED", "detail": "OSError: disk full"}  # nosec B101


def test_the_chat_check_refuses_a_model_name_before_loading_anything(monkeypatch):
    monkeypatch.setitem(sys.modules, "ollama", None)  # would be NOT INSTALLED if it got that far
    for bad in ("", "; whoami", "Qwen", "http://x/y"):
        assert rt.llm_reply([bad])["result"] == "NOT CONFIGURED"  # nosec B101


def test_whisper_refuses_an_unknown_size_before_loading_anything(monkeypatch):
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    assert rt.whisper_fetch(["tiny", "gigantic"])["result"] == "FAILED"  # nosec B101
    assert rt.whisper_fetch([])["result"] == "NOT INSTALLED"  # nosec B101


def test_whisper_fetches_both_sizes_the_assistant_loads(monkeypatch):
    import types

    asked = []
    utils = types.SimpleNamespace(download_model=lambda size: asked.append(size) or size)
    monkeypatch.setitem(sys.modules, "faster_whisper", types.ModuleType("faster_whisper"))
    monkeypatch.setitem(sys.modules, "faster_whisper.utils", utils)
    assert rt.whisper_fetch([])["result"] == "PASS" and asked == ["tiny", "base"]  # nosec B101


def test_the_voice_check_fails_when_one_library_is_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "kokoro_onnx", None)
    assert rt.voice_import([])["result"] == "NOT INSTALLED"  # nosec B101


def test_the_bundled_speech_clip_is_about_a_second_of_16_khz_mono():
    with wave.open(str(rt.STT_CLIP)) as w:
        assert (w.getnchannels(), w.getframerate(), w.getsampwidth()) == (1, 16000, 2)  # nosec B101
        assert 1.0 <= w.getnframes() / 16000 <= 1.5  # nosec B101


def test_the_core_check_passes_in_an_environment_that_has_the_core():
    out = rt.core_import([])
    assert out["result"] == "PASS" and out["seconds"] >= 0  # nosec B101


def test_a_check_that_writes_isolates_the_profile_first():
    # memory.persist and vault.check store something; both must call
    # _isolated() before they import what they store with.
    import inspect

    for task in (rt.memory_persist, rt.vault_check):
        src = inspect.getsource(task)
        assert src.index("_isolated()") < src.index("from Agent_Guru")  # nosec B101
