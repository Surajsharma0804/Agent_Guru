"""Machine probes on fake machines: values, "unknown" with a reason, never a guess."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from Agent_Guru.genesis import probes as pr
from Agent_Guru.genesis.layout import Layout

SMI = "NVIDIA GeForce RTX 2050, 4096, 3049, 591.44, P8\n"


def fake(system="Windows", programs=None, http=None, which=None, env=None, memory=(16 * 2**30, 7 * 2**30),
         disk=500 * 2**30, tcp=None, existing=(), webview2="139.0.3405.86", audio=(2, 3), long_paths=True):
    programs = programs or {}
    which = which or {}
    calls: list[list[str]] = []

    def run(args, timeout):
        calls.append(args)
        for prefix, answer in programs.items():
            if " ".join(args).startswith(prefix):
                return answer
        return -1, "FileNotFoundError: not on this fake machine"

    def http_json(url, timeout=3.0, body=None):
        if http is None:
            raise ConnectionRefusedError("refused")
        key = url.rsplit("/api/", 1)[-1]
        return http(key, body)

    seams = pr.Seams(run=run, http_json=http_json, tcp=lambda h, p, t: (tcp or {}).get(h, ""),
                     which=lambda n: which.get(n), system=lambda: system, env=lambda k: (env or {}).get(k),
                     disk_free=lambda p: disk, memory=lambda: memory,
                     exists=lambda p: str(p) in existing, webview2_version=lambda: webview2,
                     audio_counts=lambda: audio, long_paths=lambda: long_paths)
    seams.calls = calls  # type: ignore[attr-defined]
    return seams


def test_an_nvidia_gpu_is_read_with_its_memory_driver_and_pstate():
    s = fake(which={"nvidia-smi": "nvidia-smi"}, programs={"nvidia-smi": (0, SMI)})
    gpu = pr.probe_gpu(s)
    assert gpu.status == "ok"  # nosec B101
    assert gpu.value == {"vendor": "NVIDIA", "name": "NVIDIA GeForce RTX 2050", "vram_total_mb": 4096,  # nosec B101
                         "vram_used_mb": 3049, "driver": "591.44", "pstate": "P8"}


def test_nvidia_tools_that_do_not_answer_give_unknown_not_a_guess():
    s = fake(which={"nvidia-smi": "nvidia-smi"}, programs={"nvidia-smi": (9, "")})
    gpu = pr.probe_gpu(s)
    assert gpu.status == "unknown" and gpu.value is None and "exit 9" in gpu.reason  # nosec B101


def test_another_vendor_is_named_but_its_memory_stays_unknown():
    s = fake(programs={"powershell -NoProfile -NonInteractive -Command (Get-CimInstance Win32_VideoController)":
                       (0, "Intel(R) UHD Graphics 620\n")})
    gpu = pr.probe_gpu(s)
    assert gpu.value["vendor"] == "Intel" and gpu.value["vram_total_mb"] is None  # nosec B101


def test_no_gpu_at_all_is_unknown_with_the_reason():
    gpu = pr.probe_gpu(fake(system="Linux"))
    assert gpu.status == "unknown" and "no NVIDIA tools" in gpu.reason  # nosec B101


def test_memory_that_cannot_be_read_is_unknown():
    ram = pr.probe_ram(fake(system="Darwin", memory=None))
    assert ram.status == "unknown" and ram.value is None  # nosec B101


def test_only_compatible_pythons_count_and_each_is_asked_its_version():
    listing = (" -V:3.14 *        C:\\Py\\314\\python.exe\n -V:3.13          C:\\Py\\313\\python.exe\n"
               " -V:3.10          C:\\Py\\310\\python.exe\n")
    s = fake(programs={"py -0p": (0, listing),
                       "C:\\Py\\314\\python.exe": (0, "3.14.2\n"), "C:\\Py\\313\\python.exe": (0, "3.13.15\n"),
                       "C:\\Py\\310\\python.exe": (0, "3.10.11\n")})
    found = pr.probe_python(s).value
    assert [p["version"] for p in found if p["path"].startswith("C:\\Py")] == ["3.13.15"]  # nosec B101


def test_a_machine_without_python_reports_an_empty_list(monkeypatch):
    monkeypatch.setattr(pr.sys, "frozen", True, raising=False)
    assert pr.probe_python(fake(system="Windows")).value == []  # nosec B101


def test_ollama_absent_says_so_and_why():
    value = pr.probe_ollama(fake(http=None)).value
    assert value["running"] is False and "ConnectionRefusedError" in value["reason"]  # nosec B101


def test_ollama_models_come_with_their_capabilities():
    def http(key, body):
        if key == "version":
            return {"version": "0.40.13"}
        if key == "tags":
            return {"models": [{"name": "gemma4:latest", "size": 9_600 * 2**20, "details": {"parameter_size": "8B"}}]}
        return {"capabilities": ["completion", "tools"]}

    value = pr.probe_ollama(fake(http=http)).value
    assert value["running"] and value["version"] == "0.40.13"  # nosec B101
    assert value["models"] == [{"name": "gemma4:latest", "size_mb": 9600.0, "capabilities": ["completion", "tools"],  # nosec B101
                                "parameters": "8B"}]


def test_a_custom_ollama_host_is_used_but_never_shown():
    seen = []

    def http(key, body):
        seen.append(key)
        return {"version": "1", "models": []}

    s = fake(http=http, env={"OLLAMA_HOST": "http://private-box.lan:4242"})
    host, custom = pr.ollama_host(s)
    assert custom and host == "http://private-box.lan:4242"  # nosec B101
    shown = json.dumps(pr.probe_ollama(s).to_dict())
    assert "private-box" not in shown and "4242" not in shown  # nosec B101


@pytest.mark.parametrize(("target", "measured"), [
    (Path("F:/MY PROJECTS/Agent_Guru/install"), Path("F:/MY PROJECTS")),
    (Path("C:/Users/सूरज/Agent Guru"), Path("C:/")),
    (Path("C:/" + "/".join(["a-folder-with-a-long-name"] * 9)), Path("C:/")),
])
def test_free_disk_is_measured_at_the_nearest_folder_that_exists(target, measured):
    # The repository's own path has a space; the others are non-ASCII and
    # over 200 characters. The target does not exist yet before an install.
    assert len(str(target)) > 200 or " " in str(target) or not str(target).isascii()  # nosec B101
    asked = []
    s = fake(existing={str(Path("C:/")), str(Path("F:/MY PROJECTS"))}, disk=12 * 2**30)
    s.disk_free = lambda p: asked.append(p) or 12 * 2**30  # type: ignore[assignment]
    disk = pr.probe_disk(s, target)
    assert asked == [measured] and disk.value["measured_at"] == str(measured)  # nosec B101
    assert disk.value["free_mb"] == 12 * 1024 and disk.value["target"] == str(target)  # nosec B101


def test_unreachable_hosts_say_why():
    net = pr.probe_network(fake(tcp={"files.pythonhosted.org": "TimeoutError: timed out"}),
                           ["pypi.org", "files.pythonhosted.org"])
    assert net.value == {"pypi.org": "reachable", "files.pythonhosted.org": "TimeoutError: timed out"}  # nosec B101


def test_webview2_present_absent_and_off_windows():
    assert pr.probe_webview2(fake()).value == "139.0.3405.86"  # nosec B101
    assert pr.probe_webview2(fake(webview2=None)).value is None  # nosec B101
    assert pr.probe_webview2(fake(system="Linux")).status == "unsupported"  # nosec B101


def test_a_broken_probe_becomes_unknown_under_its_own_id_and_the_scan_goes_on(tmp_path):
    layout = Layout(tmp_path / "install", tmp_path / "app")
    s = fake()
    s.memory = lambda: 1 / 0  # type: ignore[assignment]
    seen = []
    machine = pr.scan(layout, ["pypi.org"], s, seen.append)
    assert [p.id for p in seen] == ["os", "cpu", "ram", "gpu", "disk", "python", "git", "ollama", "audio",  # nosec B101
                                    "webview2", "existing", "network"]
    ram = machine.probes["ram"]
    assert ram.status == "unknown" and "ZeroDivisionError" in ram.reason  # nosec B101


def test_a_scan_writes_nothing(tmp_path):
    layout = Layout(tmp_path / "install", tmp_path / "app")
    before = sorted(tmp_path.rglob("*"))
    pr.scan(layout, ["pypi.org"], fake())
    assert sorted(tmp_path.rglob("*")) == before  # nosec B101


def test_offline_skips_the_network_probe_with_a_reason(tmp_path):
    machine = pr.scan(Layout(tmp_path, tmp_path), ["pypi.org"], fake(), network=False)
    assert machine.probes["network"].status == "unknown" and "offline" in machine.probes["network"].reason  # nosec B101


def test_the_disk_probe_reports_the_path_length_and_the_long_path_setting():
    target = Path("C:/" + "x" * 120)
    disk = pr.probe_disk(fake(existing={str(Path("C:/"))}, long_paths=False), target)
    assert disk.value["target_chars"] == len(str(target)) and disk.value["long_paths"] is False  # nosec B101


def test_ollama_reports_what_it_holds_in_gpu_memory():
    def http(key, body):
        if key == "ps":
            return {"models": [{"name": "gemma4:latest", "size_vram": 3000 * 2**20}]}
        return {"version": "1", "models": []}

    assert pr.probe_ollama(fake(http=http)).value["loaded"] == [{"name": "gemma4:latest", "vram_mb": 3000.0}]  # nosec B101


def test_pinned_files_already_in_place_are_reported_by_name_and_size(tmp_path):
    layout = Layout(tmp_path / "install", tmp_path / "app")
    voice = tmp_path / "kokoro"
    voice.mkdir()
    (voice / "model.onnx").write_bytes(b"x" * 10)
    (voice / "voices.bin").write_bytes(b"y" * 5)
    pinned = [("voice-model", voice, [("model.onnx", 10), ("voices.bin", 5)]),
              ("short", voice, [("model.onnx", 11)]), ("missing", tmp_path / "none", [("a", 1)])]
    value = pr.probe_existing(fake(), layout, pinned).value
    assert value["files_present"] == ["voice-model"]  # nosec B101
