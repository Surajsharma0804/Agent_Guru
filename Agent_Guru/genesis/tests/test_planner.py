"""The planner on fake machines, against the real manifest. It looks at nothing and writes nothing."""

from __future__ import annotations

import socket

import pytest

from Agent_Guru.genesis import manifest as mf
from Agent_Guru.genesis import planner as pl
from Agent_Guru.genesis.probes import Machine, Probe

MB = 2**20
QWEN = {"name": "qwen2.5:1.5b", "size_mb": 940.4, "capabilities": ["completion", "tools"]}
E2B = {"name": "gemma4:e2b", "size_mb": 4374.6, "capabilities": ["completion", "tools", "vision"]}
GEMMA4 = {"name": "gemma4:latest", "size_mb": 9163.2, "capabilities": ["completion", "tools", "vision"]}
CHAT_ONLY = {"name": "gemma3:1b", "size_mb": 768.7, "capabilities": ["completion"]}


def machine(gpu=None, ram_mb=16088, free_mb=47_000, pythons=({"version": "3.13.15", "path": "C:/Py/python.exe"},),
            models=(QWEN, E2B, GEMMA4, CHAT_ONLY), running=True, loaded=(), audio=(1, 1), os_name="Windows 11",
            installed=(), target_chars=40, long_paths=True):
    p = {
        "os": Probe("os", "OS", "ok", f"{os_name} (x, AMD64)"),
        "ram": Probe("ram", "RAM", "ok", {"total_mb": ram_mb, "available_mb": ram_mb // 3}),
        "gpu": Probe("gpu", "GPU", "ok", gpu) if gpu else Probe("gpu", "GPU", "unknown", None, "no NVIDIA tools"),
        "disk": Probe("disk", "Disk", "ok", {"free_mb": free_mb, "target_chars": target_chars, "long_paths": long_paths}),
        "python": Probe("python", "Python", "ok", list(pythons)),
        "ollama": Probe("ollama", "Ollama", "ok", {"running": running, "models": list(models) if running else [],
                                                   "loaded": list(loaded), "reason": "" if running else "no answer"}),
        "audio": Probe("audio", "Audio", "ok", {"inputs": audio[0], "outputs": audio[1]}),
        "existing": Probe("existing", "Existing", "ok", {"installed_components": list(installed)}),
    }
    return Machine(p)


def nvidia(total, used=0):
    return {"vendor": "NVIDIA", "name": "test", "vram_total_mb": total, "vram_used_mb": used, "driver": "1", "pstate": "P8"}


@pytest.fixture(scope="module")
def manifest():
    return mf.load()


def rows(plan):
    return {r["id"]: r for r in plan["components"]}


def test_no_gpu_runs_the_model_on_the_cpu_and_skips_gpu_speech(manifest):
    plan = pl.plan(machine(gpu=None), manifest)
    assert plan["model"]["name"] == "qwen2.5:1.5b" and plan["model"]["gpu_fit"] == "cpu"  # nosec B101
    assert rows(plan)["voice-gpu"]["action"] == "skip" and "NVIDIA" in rows(plan)["voice-gpu"]["reason"]  # nosec B101


def test_a_4_gb_gpu_picks_the_largest_model_that_fits_beside_whisper(manifest):
    # The development laptop: 4096 MB, 3049 MB used of which Ollama itself holds 3000.
    plan = pl.plan(machine(gpu=nvidia(4096, 3049), loaded=[{"name": "gemma4:latest", "vram_mb": 3000}]), manifest)
    model = plan["model"]
    assert plan["gpu_speech"] and model["gpu_free_for_model_mb"] == 4096 - 49 - pl.WHISPER_GPU_MB  # nosec B101
    assert model["name"] == "qwen2.5:1.5b" and model["gpu_fit"] == "fits" and model["reused"]  # nosec B101


def test_a_model_that_splits_between_gpu_and_cpu_says_so(manifest):
    plan = pl.plan(machine(gpu=nvidia(4096)), manifest, pl.Choices(model="gemma4:e2b"))
    assert plan["model"]["gpu_fit"] == "partial"  # nosec B101
    assert "splits between GPU and CPU" in plan["model"]["note"] and "% on the GPU" in plan["model"]["note"]  # nosec B101


def test_a_24_gb_gpu_gets_the_largest_installed_model(manifest):
    plan = pl.plan(machine(gpu=nvidia(24576, 900)), manifest)
    assert plan["model"]["name"] == "gemma4:latest" and plan["model"]["gpu_fit"] == "fits"  # nosec B101


def test_an_installed_model_is_preferred_to_a_download(manifest):
    plan = pl.plan(machine(gpu=nvidia(24576), models=(QWEN,)), manifest)
    assert plan["model"]["name"] == "qwen2.5:1.5b" and rows(plan)["llm-model"]["action"] == "reuse"  # nosec B101
    assert rows(plan)["llm-model"]["download_bytes"] == 0  # nosec B101


def test_with_no_usable_model_installed_it_offers_one_that_fits(manifest):
    plan = pl.plan(machine(gpu=nvidia(4096), models=(CHAT_ONLY,)), manifest)
    assert plan["model"]["name"] == "qwen2.5:1.5b" and not plan["model"]["reused"]  # nosec B101
    assert rows(plan)["llm-model"]["download_bytes"] == 986061892  # nosec B101  the registry's exact bytes


def test_it_never_picks_a_model_too_big_for_ram(manifest):
    plan = pl.plan(machine(ram_mb=2048, models=(GEMMA4, E2B)), manifest)
    assert plan["model"]["name"] == "qwen2.5:1.5b" and not plan["model"]["reused"]  # nosec B101
    too_small = pl.plan(machine(ram_mb=1024, models=()), manifest)
    assert too_small["model"]["name"] == "" and any(u["feature"] == "a chat model" for u in too_small["unavailable"])  # nosec B101


def test_low_disk_marks_the_plan_as_not_fitting(manifest):
    plan = pl.plan(machine(free_mb=200), manifest)
    t = plan["totals"]
    assert t["fits"] is False and t["needed_with_margin_bytes"] > t["free_bytes"]  # nosec B101
    assert t["needed_with_margin_bytes"] == int((t["disk_bytes"] + t["download_bytes"]) * 1.1)  # nosec B101


def test_offline_downloads_from_no_host_and_needs_an_installed_model(manifest):
    plan = pl.plan(machine(models=()), manifest, pl.Choices(offline=True))
    assert plan["hosts"] == [] and plan["model"]["name"] == ""  # nosec B101
    assert "offline" in plan["model"]["error"]  # nosec B101


def test_no_python_means_the_private_runtime_is_downloaded(manifest):
    plan = pl.plan(machine(pythons=()), manifest)
    py = rows(plan)["python-runtime"]
    assert py["action"] == "install" and py["download_bytes"] == 14391248  # nosec B101
    assert "api.nuget.org" in plan["hosts"]  # nosec B101
    reuse = rows(pl.plan(machine(), manifest))["python-runtime"]
    assert reuse["action"] == "reuse" and reuse["python"] == "C:/Py/python.exe"  # nosec B101


def test_ollama_absent_is_named_as_unavailable(manifest):
    plan = pl.plan(machine(running=False), manifest)
    assert any(u["feature"] == "answers from a local model" for u in plan["unavailable"])  # nosec B101
    present = pl.plan(machine(running=True), manifest)
    assert not any(u["feature"] == "answers from a local model" for u in present["unavailable"])  # nosec B101


def test_no_microphone_is_named_and_typed_chat_still_works(manifest):
    plan = pl.plan(machine(audio=(0, 1)), manifest)
    assert any("no microphone" in u["why"] for u in plan["unavailable"])  # nosec B101
    assert rows(plan)["core-packages"]["action"] == "install"  # nosec B101


def test_tier_toggles_turn_components_on_and_off(manifest):
    off = pl.plan(machine(), manifest, pl.Choices(tiers={"voice": False, "browser": True}))
    assert rows(off)["voice-packages"]["action"] == "skip" and rows(off)["browser-packages"]["action"] == "install"  # nosec B101
    assert off["tiers"]["core"] is True  # nosec B101  the core cannot be turned off


def test_every_change_outside_the_install_folder_is_listed(manifest):
    plan = pl.plan(machine(gpu=nvidia(4096)), manifest)
    changed = {o["component"] for o in plan["outside_install"]}
    assert {"data-folder", "memory-model", "voice-model", "whisper-model"} <= changed  # nosec B101
    assert set(plan["irreversible"]) >= {"data-folder"}  # nosec B101


@pytest.mark.parametrize(("chars", "long_paths", "problem"), [(40, False, False), (102, False, False),
                                                                 (103, False, True), (230, True, False)])
def test_a_long_install_path_is_refused_only_without_long_paths(manifest, chars, long_paths, problem):
    plan = pl.plan(machine(target_chars=chars, long_paths=long_paths), manifest)
    assert bool(plan["path_problem"]) is problem  # nosec B101


def test_making_a_plan_writes_nothing_and_opens_no_socket(manifest, tmp_path, monkeypatch):
    def no_socket(*a, **k):
        raise AssertionError("the planner opened a socket")

    monkeypatch.setattr(socket.socket, "connect", no_socket)
    monkeypatch.setattr(socket, "create_connection", no_socket)
    monkeypatch.chdir(tmp_path)
    before = sorted(tmp_path.rglob("*"))
    for m in (machine(), machine(gpu=nvidia(4096)), machine(running=False, pythons=())):
        pl.plan(m, manifest)
    assert sorted(tmp_path.rglob("*")) == before  # nosec B101


def test_the_platform_filter_skips_windows_only_parts_on_macos(manifest):
    plan = pl.plan(machine(os_name="Darwin 24"), manifest)
    assert rows(plan)["voice-gpu"]["action"] == "skip"  # nosec B101
