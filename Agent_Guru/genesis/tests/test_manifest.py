"""The component manifest: valid against the real probes, actions and lock, and refused when broken."""

from __future__ import annotations

import copy
import re
from pathlib import Path

import pytest

from Agent_Guru.genesis import actions, manifest as mf, verify
from Agent_Guru.genesis.layout import source_root

LOCK = source_root() / "requirements-lock.txt"


@pytest.fixture(scope="module")
def real():
    return mf.load()


def problems(m):
    return mf.validate(m, verify.PROBES, actions.ACTIONS, mf.lock_pins(LOCK))


def test_the_shipped_manifest_has_no_problems(real):
    assert problems(real) == []  # nosec B101


def test_every_stage_node_has_at_least_one_component(real):
    assert {c["stage"] for c in real.components} == set(mf.STAGES)  # nosec B101


def _with(real, cid, **changes):
    comps = [copy.deepcopy(c) for c in real.components]
    for c in comps:
        if c["id"] == cid:
            c.update(changes)
    return mf.Manifest(tuple(comps))


def test_a_dangling_probe_id_is_reported(real):
    assert "core-packages: probe 'core.imprt' does not exist" in problems(_with(real, "core-packages", probe="core.imprt"))  # nosec B101


def test_a_dangling_install_or_rollback_action_is_reported(real):
    found = problems(_with(real, "voice-model", install="files.fetch", rollback="files.delete"))
    assert "voice-model: install action 'files.fetch' does not exist" in found  # nosec B101
    assert "voice-model: rollback action 'files.delete' does not exist" in found  # nosec B101


def test_a_required_component_without_a_probe_is_reported(real):
    assert "core-packages: no verify probe on a required component" in problems(_with(real, "core-packages", probe=""))  # nosec B101


def test_a_dependency_cycle_is_reported(real):
    found = problems(_with(real, "python-runtime", depends_on=["core-packages"]))
    assert any(p.startswith("dependency cycle: ") and "python-runtime" in p for p in found)  # nosec B101
    with pytest.raises(ValueError, match="cycle"):
        mf.order(_with(real, "python-runtime", depends_on=["core-packages"]), ["core-packages"])


def test_a_required_component_cannot_depend_on_an_optional_one(real):
    found = problems(_with(real, "first-start", depends_on=["voice-packages"]))
    assert "first-start: a required component depends on the optional 'voice-packages'" in found  # nosec B101


def test_a_downloaded_file_must_carry_a_real_hash_and_size(real):
    bad = copy.deepcopy(real.by_id["memory-model"]["files"])
    bad[0]["sha256"] = "unknown"
    bad[1]["size"] = 0
    found = problems(_with(real, "memory-model", files=bad))
    assert "memory-model: model.onnx has no real SHA-256" in found and "memory-model: tokenizer.json has no size" in found  # nosec B101


def test_an_unmeasured_size_must_say_unverified(real):
    size = {"download_bytes": None, "disk_bytes": 5, "measured": "guessed"}
    assert "vision-packages: download_bytes is unknown but not marked UNVERIFIED" in problems(  # nosec B101
        _with(real, "vision-packages", size=size))


def test_every_package_a_tier_installs_is_pinned_in_the_lock(real):
    pins = mf.lock_pins(LOCK)
    for c in real.components:
        for pkg in c.get("packages", []):
            assert mf.normalise(pkg) in pins, f"{c['id']}: {pkg} has no pin in requirements-lock.txt"  # nosec B101
    found = problems(_with(real, "coding-packages", packages=["GitPython", "not-a-pinned-package"]))
    assert "coding-packages: not-a-pinned-package is not pinned in requirements-lock.txt" in found  # nosec B101


def test_the_gpu_variant_is_the_gpu_extra_and_pinned_in_the_lock(real):
    # The hardware variant: the CUDA libraries for Whisper. If the lock's pins
    # drift from what the gpu extra names, or the manifest installs something
    # else, a GPU install would not be the one measured.
    pyproject = (source_root() / "pyproject.toml").read_text(encoding="utf-8")
    extra = pyproject.split("\ngpu = [", 1)[1].split("]", 1)[0]
    named = {mf.normalise(m) for m in re.findall(r'"([A-Za-z0-9._\-]+)', extra)}
    gpu = real.by_id["voice-gpu"]
    assert {mf.normalise(p) for p in gpu["packages"]} >= named and gpu["requires"] == "nvidia"  # nosec B101
    pins = mf.lock_pins(LOCK)
    assert pins["nvidia-cublas-cu12"] == "12.9.2.10" and pins["nvidia-cudnn-cu12"] == "9.27.0.42"  # nosec B101


def test_torch_is_the_cpu_build_everywhere(real):
    pins = mf.lock_pins(LOCK)
    assert pins["torch"].endswith("+cpu")  # nosec B101
    voice = real.by_id["voice-packages"]
    assert voice["extra_index"] == ["https://download.pytorch.org/whl/cpu"]  # nosec B101
    assert all(i in actions.ALLOWED_INDEXES for c in real.components for i in c.get("extra_index", []))  # nosec B101


def test_the_voice_files_are_the_voices_own_pins_and_folder(real):
    from Agent_Guru.speech.tts import tts_engine

    voice = real.by_id["voice-model"]
    assert {(f["name"], f["size"], f["sha256"]) for f in voice["files"]} == \
        {(p.name, p.size, p.digest) for p in tts_engine.KOKORO_PINS}  # nosec B101
    assert {f["url"] for f in voice["files"]} == {tts_engine._MODEL_URL, tts_engine._VOICES_URL}  # nosec B101
    rel = voice["dest"].split(":", 1)[1]
    assert Path.home() / rel == tts_engine._CACHE_DIR  # nosec B101


def test_the_memory_model_lands_where_the_onnx_route_looks(real):
    from Agent_Guru.reasoning.memory import embedding

    rel = real.by_id["memory-model"]["dest"].split(":", 1)[1]
    assert embedding._onnx_folder("sentence-transformers/all-MiniLM-L6-v2").parts[-3:] == Path(rel).parts[-3:]  # nosec B101
    assert {f["name"] for f in real.by_id["memory-model"]["files"]} == {"model.onnx", "tokenizer.json"}  # nosec B101


def test_order_puts_dependencies_first(real):
    seq = mf.order(real, ["first-start"])
    for cid in seq:
        for dep in real.by_id[cid]["depends_on"]:
            assert seq.index(dep) < seq.index(cid)  # nosec B101
    assert seq[0] == "python-runtime" and seq[-1] == "first-start"  # nosec B101
