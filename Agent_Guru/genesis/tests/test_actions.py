"""Install actions: fixed argument lists, refused inputs, and the allow-list itself."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from Agent_Guru.genesis import actions as act
from Agent_Guru.genesis.layout import Layout


class Recorder:
    def __init__(self, answers=None):
        self.calls: list[list[str]] = []
        self.envs: list[dict[str, str]] = []
        self.answers = answers or {}

    def __call__(self, args, cwd=None, env=None, on_line=None, should_stop=None, timeout=0):
        self.calls.append(list(args))
        self.envs.append(env or {})
        for key, (code, out, lines) in self.answers.items():
            if key in " ".join(args):
                for line in lines:
                    if on_line:
                        on_line(line)
                return code, out
        return 0, "3.13.15"


def ctx_for(tmp_path, run=None, **kw):
    layout = Layout(tmp_path / "Agent Guru", tmp_path / "app")
    (tmp_path / "app").mkdir(exist_ok=True)
    (tmp_path / "app" / "requirements-lock.txt").write_text("scipy==1.18.1\n", encoding="utf-8")
    events: list[tuple[str, dict]] = []
    return act.ActionContext(layout=layout, emit=lambda k, d: events.append((k, d)), run=run or Recorder(), **kw), events


def test_every_manifest_action_is_in_the_table_and_nothing_else_is_callable():
    assert set(act.ACTIONS) == {"runtime.python", "runtime.remove_python", "runtime.venv", "runtime.remove_venv",  # nosec B101
                                "pip.tier", "pip.uninstall_tier", "files.download", "files.remove", "ollama.install", "app.files",
                                "ollama.pull", "runtime.task", "data.folder", "nothing"}


def test_pip_gets_an_argument_list_with_versions_from_the_lock_and_real_progress(tmp_path):
    lines = ["Collecting scipy", "Progress 1048576 of 38400000", "Progress 38400000 of 38400000", "Successfully installed scipy"]
    rec = Recorder({"pip install": (0, "", lines)})
    ctx, events = ctx_for(tmp_path, rec)
    act.act_pip_tier(ctx, {"id": "core-packages", "packages": ["scipy", "requests"]})
    args = rec.calls[0]
    assert args[:5] == [str(ctx.layout.venv_python), "-I", "-m", "pip", "install"]  # nosec B101
    assert args[args.index("-c") + 1] == str(ctx.layout.lock_file)  # nosec B101  versions only from the lock
    req = Path(args[args.index("-r") + 1]).read_text(encoding="utf-8").split()
    assert req == ["scipy", "requests"]  # nosec B101  bare names, no versions, no options
    progress = [d for k, d in events if k == "progress"]
    assert progress[-1]["done"] == progress[-1]["total"] == 38400000  # nosec B101


@pytest.mark.parametrize("bad", ["scipy==0.1", "--index-url=http://evil.test/simple", "-e .", "git+https://x/y",
                                 "pkg; os_name=='nt'", "../escape"])
def test_a_package_that_is_not_a_bare_name_is_refused_before_pip_runs(tmp_path, bad):
    rec = Recorder()
    ctx, _ = ctx_for(tmp_path, rec)
    with pytest.raises(act.ActionError, match="only bare names"):
        act.act_pip_tier(ctx, {"id": "x", "packages": ["requests", bad]})
    assert rec.calls == []  # nosec B101


def test_an_extra_index_outside_the_allowed_list_is_refused(tmp_path):
    ctx, _ = ctx_for(tmp_path)
    with pytest.raises(act.ActionError, match="not on the allowed list"):
        act.act_pip_tier(ctx, {"id": "x", "packages": ["torch"], "extra_index": ["https://mirror.example.test/simple"]})


def test_offline_pip_uses_the_folder_and_no_index(tmp_path):
    rec = Recorder()
    ctx, _ = ctx_for(tmp_path, rec, offline_dir=tmp_path / "usb")
    act.act_pip_tier(ctx, {"id": "core-packages", "packages": ["scipy"], "extra_index": ["https://download.pytorch.org/whl/cpu"]})
    args = rec.calls[0]
    assert "--no-index" in args and str(tmp_path / "usb" / "wheels") in args and "--extra-index-url" not in args  # nosec B101


def test_uninstall_removes_only_what_no_other_tier_also_installed(tmp_path):
    rec = Recorder()
    ctx, _ = ctx_for(tmp_path, rec)
    work = ctx.layout.cache_dir / "tiers"
    work.mkdir(parents=True)
    report = lambda names: json.dumps({"install": [{"metadata": {"name": n}} for n in names]})  # noqa: E731
    (work / "voice-packages.report.json").write_text(report(["torch", "numpy", "av"]), encoding="utf-8")
    (work / "core-packages.report.json").write_text(report(["numpy", "scipy"]), encoding="utf-8")
    out = act.act_pip_uninstall_tier(ctx, {"id": "voice-packages"})
    assert out.detail["removed"] == ["torch", "av"]  # nosec B101
    assert rec.calls[0][-3:] == ["-y", "torch", "av"]  # nosec B101


def test_ollama_pull_reports_real_bytes_and_needs_success(tmp_path):
    stream = [{"status": "pulling manifest"},
              {"status": "pulling a1", "digest": "sha256:a1", "total": 1000, "completed": 400},
              {"status": "pulling b2", "digest": "sha256:b2", "total": 3000, "completed": 0},
              {"status": "pulling a1", "digest": "sha256:a1", "total": 1000, "completed": 1000},
              {"status": "pulling b2", "digest": "sha256:b2", "total": 3000, "completed": 3000},
              {"status": "verifying sha256 digest"}, {"status": "success"}]
    ctx, events = ctx_for(tmp_path, http_lines=lambda url, body, timeout=0: iter(stream), model="qwen2.5:1.5b")
    out = act.act_ollama_pull(ctx, {"id": "llm-model"})
    assert out.detail == {"model": "qwen2.5:1.5b", "bytes": 4000}  # nosec B101
    last = [d for k, d in events if k == "progress"][-1]
    assert (last["done"], last["total"]) == (4000, 4000)  # nosec B101


def test_ollama_pull_without_success_or_with_an_error_fails(tmp_path):
    ctx, _ = ctx_for(tmp_path, http_lines=lambda *a, **k: iter([{"status": "pulling manifest"}]), model="qwen2.5:1.5b")
    with pytest.raises(act.ActionError, match="did not finish"):
        act.act_ollama_pull(ctx, {"id": "llm-model"})
    ctx, _ = ctx_for(tmp_path, http_lines=lambda *a, **k: iter([{"error": "file does not exist"}]), model="qwen2.5:1.5b")
    with pytest.raises(act.ActionError, match="file does not exist"):
        act.act_ollama_pull(ctx, {"id": "llm-model"})


@pytest.mark.parametrize("bad", ["qwen2.5:1.5b; rm -rf /", "../../etc", "Qwen", "http://evil.test/model", ""])
def test_a_model_name_outside_the_pattern_never_reaches_ollama(tmp_path, bad):
    asked = []
    ctx, _ = ctx_for(tmp_path, http_lines=lambda *a, **k: asked.append(a) or iter([]), model=bad)
    with pytest.raises(act.ActionError, match="refusing model name"):
        act.act_ollama_pull(ctx, {"id": "llm-model"})
    assert asked == []  # nosec B101


def _nupkg(path: Path, names: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in names.items():
            zf.writestr(name, data)


@pytest.mark.parametrize("escape", ["tools/../../evil.txt", "tools//evil.txt"])
def test_the_private_runtime_refuses_an_archive_with_an_escaping_path(tmp_path, monkeypatch, escape):
    import hashlib

    buf = tmp_path / "python.3.13.15.nupkg"
    _nupkg(buf, {"tools/python.exe": b"MZ", escape: b"x"})
    data = buf.read_bytes()
    comp = {"id": "python-runtime", "files": [{"name": buf.name, "size": len(data),
                                               "sha256": hashlib.sha256(data).hexdigest(), "url": "https://x.test/p"}]}
    ctx, _ = ctx_for(tmp_path)
    monkeypatch.setattr(act.sys, "platform", "win32")
    cached = ctx.layout.cache_dir / "files" / comp["files"][0]["sha256"][:16] / buf.name
    cached.parent.mkdir(parents=True)
    cached.write_bytes(data)
    with pytest.raises(act.ActionError, match="unsafe path"):
        act.act_runtime_python(ctx, comp)
    assert not (tmp_path / "evil.txt").exists() and not ctx.layout.private_python_dir.exists()  # nosec B101


def test_a_reused_python_is_asked_its_version_and_nothing_is_downloaded(tmp_path):
    downloads = []
    ctx, _ = ctx_for(tmp_path, python="C:/Py/313/python.exe", download=lambda *a, **k: downloads.append(a))
    out = act.act_runtime_python(ctx, {"id": "python-runtime", "files": []})
    assert out.reused and out.detail["version"] == "3.13.15" and downloads == []  # nosec B101


@pytest.mark.parametrize("token", ["data:../../Windows", "home:/etc", "data:", "other:models", "runtime:a/../../b"])
def test_a_destination_cannot_climb_out_of_its_folder(tmp_path, token):
    ctx, _ = ctx_for(tmp_path)
    with pytest.raises(act.ActionError):
        act.resolve_dest(token, ctx.layout)


def test_an_unknown_runtime_task_is_refused(tmp_path):
    ctx, _ = ctx_for(tmp_path)
    with pytest.raises(act.ActionError, match="unknown runtime task"):
        act.run_runtime_task(ctx, "shell", ["cmd /c whoami"])


def test_removing_files_deletes_only_the_pinned_names(tmp_path):
    ctx, _ = ctx_for(tmp_path)
    dest = ctx.layout.runtime_root / "models"
    dest.mkdir(parents=True)
    (dest / "model.bin").write_bytes(b"x")
    (dest / "notes.txt").write_text("mine", encoding="utf-8")
    act.act_remove_files(ctx, {"dest": "runtime:models", "files": [{"name": "model.bin", "size": 1, "sha256": "0" * 64,
                                                                    "url": "https://x.test/m"}]})
    assert sorted(p.name for p in dest.iterdir()) == ["notes.txt"]  # nosec B101


def test_the_venv_removal_refuses_a_folder_outside_the_runtime(tmp_path, monkeypatch):
    ctx, _ = ctx_for(tmp_path)
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    monkeypatch.setattr(Layout, "venv_dir", property(lambda self: outside))
    with pytest.raises(act.ActionError, match="refusing to delete"):
        act.act_remove_venv(ctx, {})
    assert outside.exists()  # nosec B101


def test_runtime_task_output_is_read_from_its_last_json_line(tmp_path):
    rec = Recorder({"runtime_tasks": (0, 'log noise\n{"result": "PASS", "detail": "ok", "seconds": 1.5}\n', [])})
    ctx, _ = ctx_for(tmp_path, rec)
    ctx.layout.venv_python.parent.mkdir(parents=True)
    ctx.layout.venv_python.write_bytes(b"")
    assert act.run_runtime_task(ctx, "core.import", []) == {"result": "PASS", "detail": "ok", "seconds": 1.5}  # nosec B101
    # -s, not -I: -I ignores PYTHONPATH, and the app's source is found through it.
    assert rec.calls[0][1:4] == ["-s", "-m", "Agent_Guru.genesis.runtime_tasks"]  # nosec B101
    assert rec.envs[0]["PYTHONPATH"] == str(ctx.layout.app_root)  # nosec B101


def test_a_program_that_cannot_start_is_named_in_the_error(tmp_path):
    with pytest.raises(act.ActionError, match="could not start .*no-such-python.exe"):
        act._run([str(tmp_path / "no-such-python.exe"), "-V"])


def _pinned(data, urls):
    import hashlib

    return {"id": "x", "dest": "runtime:models", "files": [
        {"name": "m.bin", "size": len(data), "sha256": hashlib.sha256(data).hexdigest(), "url": urls[0], "mirrors": urls[1:]}]}


def test_a_blocked_source_falls_through_to_the_mirror(tmp_path):
    asked = []

    def download(url, dest, pin, **k):
        asked.append(url)
        if "blocked" in url:
            raise act.vf.DownloadError("blocked.test: m.bin: SSLCertVerificationError")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"weights")

    ctx, events = ctx_for(tmp_path, download=download)
    act.act_download_files(ctx, _pinned(b"weights", ["https://blocked.test/m", "https://mirror.test/m"]))
    assert asked == ["https://blocked.test/m", "https://mirror.test/m"]  # nosec B101
    assert (ctx.layout.runtime_root / "models" / "m.bin").read_bytes() == b"weights"  # nosec B101
    assert any("trying the next source" in d.get("line", "") for k, d in events)  # nosec B101


def test_every_source_failing_names_them_all(tmp_path):
    def download(url, dest, pin, **k):
        raise act.vf.DownloadError(url + " is down")

    ctx, _ = ctx_for(tmp_path, download=download)
    with pytest.raises(act.ActionError, match="a.test.*b.test"):
        act.act_download_files(ctx, _pinned(b"x", ["https://a.test/m", "https://b.test/m"]))


def test_wrong_bytes_are_not_retried_on_another_source(tmp_path):
    asked = []

    def download(url, dest, pin, **k):
        asked.append(url)
        raise act.vf.VerificationError("m.bin does not match its pinned sha256 hash")

    ctx, _ = ctx_for(tmp_path, download=download)
    with pytest.raises(act.ActionError, match="pinned sha256"):
        act.act_download_files(ctx, _pinned(b"x", ["https://a.test/m", "https://b.test/m"]))
    assert asked == ["https://a.test/m"]  # nosec B101


def test_the_lock_is_used_without_cpu_builds_on_macos(tmp_path):
    # PyTorch's CPU index has no macOS builds, so "torch==2.14.1+cpu" cannot resolve there.
    rec = Recorder()
    ctx, _ = ctx_for(tmp_path, rec, platform="darwin")
    ctx.layout.lock_file.write_text("torch==2.14.1+cpu\nscipy==1.18.1\n", encoding="utf-8")
    act.act_pip_tier(ctx, {"id": "voice", "packages": ["torch"], "extra_index": ["https://download.pytorch.org/whl/cpu"]})
    args = rec.calls[0]
    assert Path(args[args.index("-c") + 1]).read_text(encoding="utf-8").split() == ["torch==2.14.1", "scipy==1.18.1"]  # nosec B101
    assert "--extra-index-url" not in args  # nosec B101


def test_windows_only_packages_install_only_on_windows(tmp_path):
    for platform, want in (("windows", ["scipy", "pywin32"]), ("linux", ["scipy"]), ("darwin", ["scipy"])):
        rec = Recorder()
        ctx, _ = ctx_for(tmp_path, rec, platform=platform)
        act.act_pip_tier(ctx, {"id": "core", "packages": ["scipy"], "platform_packages": {"windows": ["pywin32"]}})
        args = rec.calls[0]
        assert Path(args[args.index("-r") + 1]).read_text(encoding="utf-8").split() == want  # nosec B101


def _pbs(path: Path, members: dict[str, bytes]) -> dict:
    import hashlib
    import io
    import tarfile

    with tarfile.open(path, "w:gz") as tf:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o755
            tf.addfile(info, io.BytesIO(data))
    data = path.read_bytes()
    return {"name": path.name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest(), "url": "https://x.test/p"}


def test_the_standalone_python_is_unpacked_on_linux(tmp_path):
    entry = _pbs(tmp_path / "cpython.tar.gz", {"python/bin/python3": b"#!", "python/lib/os.py": b"x"})
    ctx, _ = ctx_for(tmp_path, platform="linux", arch="x86_64")
    cached = ctx.layout.cache_dir / "files" / entry["sha256"][:16] / entry["name"]
    cached.parent.mkdir(parents=True)
    cached.write_bytes((tmp_path / "cpython.tar.gz").read_bytes())
    out = act.act_runtime_python(ctx, {"id": "python-runtime", "files_by_platform": {"linux-x86_64": [entry]}})
    assert (ctx.layout.private_python_dir / "bin" / "python3").is_file()  # nosec B101
    assert out.detail["python"].endswith("python3")  # nosec B101


def test_a_python_archive_with_an_escaping_member_is_refused(tmp_path):
    entry = _pbs(tmp_path / "cpython.tar.gz", {"python/bin/python3": b"#!", "../../evil.txt": b"x"})
    ctx, _ = ctx_for(tmp_path, platform="linux", arch="x86_64")
    cached = ctx.layout.cache_dir / "files" / entry["sha256"][:16] / entry["name"]
    cached.parent.mkdir(parents=True)
    cached.write_bytes((tmp_path / "cpython.tar.gz").read_bytes())
    import tarfile

    with pytest.raises(tarfile.FilterError):
        act.act_runtime_python(ctx, {"id": "python-runtime", "files_by_platform": {"linux-x86_64": [entry]}})
    assert not list(tmp_path.rglob("evil.txt"))  # nosec B101


def test_no_python_pinned_for_this_chip_says_so(tmp_path):
    ctx, _ = ctx_for(tmp_path, platform="linux", arch="riscv64")
    with pytest.raises(act.ActionError, match="no private Python is pinned"):
        act.act_runtime_python(ctx, {"id": "python-runtime", "files_by_platform": {"linux-x86_64": []}})


def _ollama(entry):
    return {"id": "ollama", "files_by_platform": {"windows": [entry], "linux-x86_64": [entry], "darwin-arm64": [entry]}}


def _cached(ctx, entry, source):
    cached = ctx.layout.cache_dir / "files" / entry["sha256"][:16] / entry["name"]
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(source.read_bytes())
    return cached


def test_a_running_ollama_is_left_alone(tmp_path, monkeypatch):
    downloads = []
    monkeypatch.setattr(act, "ollama_version", lambda host: "0.40.13")
    ctx, _ = ctx_for(tmp_path, download=lambda *a, **k: downloads.append(a))
    out = act.act_ollama_install(ctx, _ollama({"name": "x", "size": 1, "sha256": "0" * 64, "url": "https://x.test/o"}))
    assert out.reused and downloads == []  # nosec B101


def test_windows_runs_the_pinned_installer_silently_then_waits_for_it(tmp_path, monkeypatch):
    answers = iter(["", "", "", "0.40.13", "0.40.13"])
    monkeypatch.setattr(act, "ollama_version", lambda host: next(answers))
    source = tmp_path / "OllamaSetup.exe"
    source.write_bytes(b"MZ")
    import hashlib

    entry = {"name": source.name, "size": 2, "sha256": hashlib.sha256(b"MZ").hexdigest(), "url": "https://x.test/o"}
    rec, spawned = Recorder(), []
    ctx, _ = ctx_for(tmp_path, rec, platform="windows", spawn=spawned.append, sleep=lambda s: None, which=lambda n: None)
    cached = _cached(ctx, entry, source)
    out = act.act_ollama_install(ctx, _ollama(entry))
    assert rec.calls == [[str(cached), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-"]]  # nosec B101
    assert spawned and spawned[0][-1] == "serve" and out.detail == {"version": "0.40.13"}  # nosec B101


def test_linux_unpacks_zstd_with_tar_and_needs_no_root(tmp_path, monkeypatch):
    answers = iter(["", "", "0.40.13", "0.40.13"])
    monkeypatch.setattr(act, "ollama_version", lambda host: next(answers))
    source = tmp_path / "ollama.tar.zst"
    source.write_bytes(b"z")
    import hashlib

    entry = {"name": source.name, "size": 1, "sha256": hashlib.sha256(b"z").hexdigest(), "url": "https://x.test/o"}
    rec, spawned = Recorder(), []
    ctx, _ = ctx_for(tmp_path, rec, platform="linux", arch="x86_64", spawn=spawned.append, sleep=lambda s: None,
                     which=lambda n: "/usr/bin/zstd" if n == "zstd" else None)
    cached = _cached(ctx, entry, source)
    act.act_ollama_install(ctx, _ollama(entry))
    assert rec.calls == [["tar", "--zstd", "-xf", str(cached), "-C", str(ctx.layout.runtime_root / "ollama")]]  # nosec B101
    assert "sudo" not in " ".join(rec.calls[0]) and spawned[0][1:] == ["serve"]  # nosec B101


def test_a_system_without_zstd_unpacks_with_the_private_environment(tmp_path):
    rec = Recorder()
    ctx, _ = ctx_for(tmp_path, rec, platform="linux", which=lambda n: None)
    act._unpack_zst(ctx, tmp_path / "o.tar.zst", tmp_path / "out")
    assert rec.calls[0][1:7] == ["-I", "-m", "pip", "install", "--no-input", "zstandard"]  # nosec B101
    assert "-c" in rec.calls[0] and str(ctx.layout.lock_file) in rec.calls[0]  # nosec B101  the lock's version
    assert rec.calls[1][-2:] == [str(tmp_path / "o.tar.zst"), str(tmp_path / "out")]  # nosec B101


def test_a_broken_tar_falls_back_to_the_private_environment(tmp_path):
    rec = Recorder({"--zstd": (2, "tar: unrecognized option", [])})
    ctx, events = ctx_for(tmp_path, rec, platform="linux", which=lambda n: "/usr/bin/zstd")
    act._unpack_zst(ctx, tmp_path / "o.tar.zst", tmp_path / "out")
    assert len(rec.calls) == 3 and any("tar --zstd failed" in d.get("line", "") for k, d in events)  # nosec B101


def test_ollama_that_never_answers_is_a_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(act, "ollama_version", lambda host: "")
    source = tmp_path / "ollama.tgz"
    entry = _pbs(source, {"ollama": b"#!"})
    ctx, _ = ctx_for(tmp_path, platform="darwin", arch="arm64", spawn=lambda a: None, sleep=lambda s: None,
                     which=lambda n: None)
    _cached(ctx, entry, source)
    with pytest.raises(act.ActionError, match="did not start answering"):
        act.act_ollama_install(ctx, _ollama(entry))


def test_an_unpinned_chip_gets_no_ollama(tmp_path, monkeypatch):
    monkeypatch.setattr(act, "ollama_version", lambda host: "")
    ctx, _ = ctx_for(tmp_path, platform="linux", arch="aarch64", which=lambda n: None)
    with pytest.raises(act.ActionError, match="no Ollama build is pinned"):
        act.act_ollama_install(ctx, _ollama({"name": "x", "size": 1, "sha256": "0" * 64, "url": "https://x.test/o"}))


def test_the_application_is_copied_out_of_the_bundle_once(tmp_path):
    bundle = tmp_path / "bundle" / "app"
    (bundle / "Agent_Guru").mkdir(parents=True)
    (bundle / "main.py").write_text("x", encoding="utf-8")
    ctx, _ = ctx_for(tmp_path)
    ctx.layout = Layout(tmp_path / "AG", tmp_path / "AG" / "app", bundled_app=bundle)
    assert not act.act_app_files(ctx, {}).reused  # nosec B101
    assert (tmp_path / "AG" / "app" / "main.py").read_text(encoding="utf-8") == "x"  # nosec B101
    assert act.act_app_files(ctx, {}).reused  # nosec B101  the same build: nothing to copy
    (bundle / "main.py").write_text("newer", encoding="utf-8")
    assert not act.act_app_files(ctx, {}).reused  # nosec B101  a new version replaces it
    assert (tmp_path / "AG" / "app" / "main.py").read_text(encoding="utf-8") == "newer"  # nosec B101


def test_nothing_is_copied_where_nothing_is_bundled(tmp_path):
    ctx, _ = ctx_for(tmp_path)
    assert act.act_app_files(ctx, {}).reused  # nosec B101


def test_an_installed_but_stopped_ollama_is_started_not_reinstalled(tmp_path, monkeypatch):
    answers = iter(["", "", "0.40.13", "0.40.13"])
    monkeypatch.setattr(act, "ollama_version", lambda host: next(answers))
    downloads, spawned = [], []
    ctx, _ = ctx_for(tmp_path, platform="windows", which=lambda n: "C:/Ollama/ollama.exe", spawn=spawned.append,
                     sleep=lambda s: None, download=lambda *a, **k: downloads.append(a))
    out = act.act_ollama_install(ctx, _ollama({"name": "x", "size": 1, "sha256": "0" * 64, "url": "https://x.test/o"}))
    assert out.reused and spawned == [["C:/Ollama/ollama.exe", "serve"]] and downloads == []  # nosec B101


def test_a_changed_bundle_makes_the_app_stale(tmp_path):
    bundle = tmp_path / "bundle" / "app"
    bundle.mkdir(parents=True)
    (bundle / "main.py").write_text("one", encoding="utf-8")
    ctx, _ = ctx_for(tmp_path)
    ctx.layout = Layout(tmp_path / "AG", tmp_path / "AG" / "app", bundled_app=bundle)
    component = {"install": "app.files"}
    assert act.is_stale(ctx, component)  # nosec B101
    act.act_app_files(ctx, component)
    assert not act.is_stale(ctx, component)  # nosec B101
    (bundle / "main.py").write_text("second", encoding="utf-8")
    assert act.is_stale(ctx, component)  # nosec B101


def test_a_changed_package_list_or_lock_makes_a_tier_stale(tmp_path):
    ctx, _ = ctx_for(tmp_path, Recorder())
    tier = {"id": "core", "install": "pip.tier", "packages": ["scipy"]}
    assert act.is_stale(ctx, tier)  # nosec B101  never installed by this version
    act.act_pip_tier(ctx, tier)
    assert not act.is_stale(ctx, tier)  # nosec B101
    assert act.is_stale(ctx, {**tier, "packages": ["scipy", "keyring"]})  # nosec B101
    ctx.layout.lock_file.write_text("scipy==2\n", encoding="utf-8")
    assert act.is_stale(ctx, tier)  # nosec B101


def test_only_the_app_and_package_tiers_can_be_stale(tmp_path):
    ctx, _ = ctx_for(tmp_path)
    assert not act.is_stale(ctx, {"install": "files.download"})  # nosec B101
