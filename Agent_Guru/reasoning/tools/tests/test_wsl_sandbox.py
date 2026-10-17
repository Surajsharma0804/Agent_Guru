"""How a sandbox run is started and how its end is read, without starting WSL."""

from __future__ import annotations

import asyncio

from Agent_Guru.reasoning.tools.skills import wsl_sandbox
from Agent_Guru.reasoning.tools.skills.wsl_sandbox import parse_result, run_command

_TRAILER = (
    "          Finished with result: {result}\n"
    "Main processes terminated with: code={code}, status={status}\n"
    "               Service runtime: 84ms\n"
)


def test_the_run_starts_with_no_shell_as_the_sandbox_user():
    argv = run_command(10, 256, "wsl.exe")
    assert argv[:7] == ["wsl.exe", "-d", wsl_sandbox.distro(), "-u", "root", "--exec", "systemd-run"]  # nosec B101
    assert argv[-4:] == ["/usr/bin/python3", "-I", "-u", "-"]  # nosec B101
    props = {argv[i + 1] for i, a in enumerate(argv) if a == "-p"}
    for needed in ("User=agsandbox", "PrivateNetwork=yes", "RestrictAddressFamilies=AF_UNIX", "NoNewPrivileges=yes",
                   "CapabilityBoundingSet=", "RestrictNamespaces=yes", "ProtectSystem=strict", "ProtectHome=tmpfs",
                   "PrivatePIDs=yes", "PrivateDevices=yes", "MemoryMax=256M", "MemorySwapMax=0", "TasksMax=32",
                   "RuntimeMaxSec=10", "KillSignal=SIGKILL"):
        assert needed in props, needed  # nosec B101
    assert any(p.startswith("InaccessiblePaths=/init ") for p in props)  # nosec B101
    assert not any(a in {"sh", "bash", "/bin/sh", "/bin/bash", "-c"} for a in argv)  # nosec B101


def test_the_distribution_can_be_chosen(monkeypatch):
    monkeypatch.setenv(wsl_sandbox.DISTRO_ENV, "Debian")
    assert run_command(5, 64, "wsl.exe")[2] == "Debian"  # nosec B101


def test_results_are_read_from_systemds_summary():
    ok = "Running as unit: run-p1.service; invocation ID: x\n" + _TRAILER.format(
        result="success", code="exited", status="0/SUCCESS")
    assert parse_result(ok) == ("success", 0, "")  # nosec B101
    failed = "Running as unit: run-p2.service\nTraceback: boom\n" + _TRAILER.format(
        result="exit-code", code="exited", status="3/NOTIMPLEMENTED")
    assert parse_result(failed) == ("exit-code", 3, "Traceback: boom")  # nosec B101
    killed = _TRAILER.format(result="timeout", code="killed", status="9/KILL")
    assert parse_result(killed)[:2] == ("timeout", None)  # nosec B101


def test_a_summary_printed_by_the_program_is_not_believed():
    """systemd prints its summary after the program ends, so the last one is systemd's."""
    forged = _TRAILER.format(result="success", code="exited", status="0/SUCCESS")
    real = _TRAILER.format(result="oom-kill", code="killed", status="9/KILL")
    result, code, own = parse_result("Running as unit: run-p3.service\n" + forged + real)
    assert (result, code) == ("oom-kill", None)  # nosec B101
    assert "Finished with result: success" in own  # nosec B101


def test_no_summary_means_systemd_run_itself_failed():
    assert parse_result("Failed to start transient service unit: Unit agsandbox not found")[0] == "unknown"  # nosec B101


def test_too_long_code_is_refused_before_anything_starts(monkeypatch):
    monkeypatch.setattr(wsl_sandbox.shutil, "which", lambda _name: (_ for _ in ()).throw(AssertionError("started")))
    run = asyncio.run(wsl_sandbox.run_python("x" * (wsl_sandbox.MAX_CODE_CHARS + 1)))
    assert run.result == "unavailable" and not run.ok  # nosec B101


def test_no_wsl_means_unavailable_not_an_error(monkeypatch):
    monkeypatch.setattr(wsl_sandbox.shutil, "which", lambda _name: None)
    assert asyncio.run(wsl_sandbox.run_python("print(1)")).result == "unavailable"  # nosec B101
    monkeypatch.setattr(wsl_sandbox, "_checked_ok", False)
    assert wsl_sandbox.check() == ["WSL is not installed"]  # nosec B101
