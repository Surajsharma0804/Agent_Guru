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
        self.answers = answers or {}

    def __call__(self, args, cwd=None, env=None, on_line=None, should_stop=None, timeout=0):
        self.calls.append(list(args))
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
                                "pip.tier", "pip.uninstall_tier", "files.download", "files.remove", "ollama.present",
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
    assert rec.calls[0][1:4] == ["-I", "-m", "Agent_Guru.genesis.runtime_tasks"]  # nosec B101
