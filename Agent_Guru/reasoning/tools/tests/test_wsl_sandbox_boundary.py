"""Code in the WSL sandbox tries to get out, and must not.

These run the real boundary: they need WSL with the sandbox set up
(`python -m Agent_Guru sandbox setup`) and are skipped, as unverified,
everywhere else. Each attack is something model-written code could try.
"""

from __future__ import annotations

import asyncio
import json
import subprocess  # nosec B404 - wsl.exe with fixed arguments
import time

import pytest

from Agent_Guru.reasoning.tools.skills import wsl_sandbox

pytestmark = [pytest.mark.security, pytest.mark.adversarial]

_problems = wsl_sandbox.check()
if _problems:
    pytest.skip("UNVERIFIED on this host: " + "; ".join(_problems), allow_module_level=True)

_ATTACKS = r'''
import json, os, socket, subprocess
out = {}
def t(name, fn):
    try:
        out[name] = ["allowed", repr(fn())[:200]]
    except BaseException as e:
        out[name] = ["blocked", type(e).__name__]
t("home", lambda: os.listdir("/home/guru"))
t("root", lambda: os.listdir("/root"))
t("windows_drives", lambda: os.listdir("/mnt/c"))
t("windows_drivers", lambda: os.listdir("/usr/lib/wsl/drivers"))
t("interop_sockets", lambda: os.listdir("/run/WSL"))
t("shadow", lambda: open("/etc/shadow").read(1))
t("gpu", lambda: open("/dev/dxg", "rb").read(1))
t("disk", lambda: open("/dev/sda", "rb").read(1))
t("internet", lambda: socket.create_connection(("1.1.1.1", 53), 2))
t("ollama_loopback", lambda: socket.create_connection(("127.0.0.1", 11434), 2))
t("dns", lambda: socket.gethostbyname("example.com"))
open("/tmp/x.exe", "wb").write(b"MZ" + bytes(200)); os.chmod("/tmp/x.exe", 0o755)
t("windows_program", lambda: subprocess.run(["/tmp/x.exe"], capture_output=True, timeout=5))
t("wsl_init", lambda: subprocess.run(["/init"], capture_output=True, timeout=5))
t("write_etc", lambda: open("/etc/agent_guru_probe", "w").write("x"))
t("write_usr", lambda: open("/usr/bin/agent_guru_probe", "w").write("x"))
t("user_namespace", lambda: subprocess.run(["unshare", "-r", "true"], check=True, capture_output=True, timeout=5))
t("sudo", lambda: subprocess.run(["sudo", "-n", "true"], check=True, capture_output=True, timeout=5))
t("mount", lambda: subprocess.run(["mount", "-t", "tmpfs", "none", "/tmp"], check=True, capture_output=True, timeout=5))
out["processes"] = sorted(p for p in os.listdir("/proc") if p.isdigit())
out["uid"] = os.getuid()
status = open("/proc/self/status").read()
out["caps"] = status.split("CapEff:")[1].split()[0]
out["no_new_privs"] = status.split("NoNewPrivs:")[1].split()[0]
out["hostname"] = socket.gethostname()
out["env"] = sorted(os.environ)
print(json.dumps(out))
'''


def _run(code: str, **kw):
    return asyncio.run(wsl_sandbox.run_python(code, **kw))


@pytest.fixture(scope="module")
def attacks() -> dict:
    run = _run(_ATTACKS, seconds=25)
    assert run.ok, (run.result, run.stderr[-500:])  # nosec B101
    return json.loads(run.stdout)


@pytest.mark.parametrize("attack", [
    "home", "root", "windows_drives", "windows_drivers", "interop_sockets", "shadow", "gpu", "disk",
    "internet", "ollama_loopback", "dns", "windows_program", "wsl_init", "write_etc", "write_usr",
    "user_namespace", "sudo", "mount",
])
def test_attack_is_blocked(attacks, attack):
    assert attacks[attack][0] == "blocked", attacks[attack]  # nosec B101


def test_it_runs_unprivileged_and_alone(attacks):
    assert attacks["uid"] not in (0, 1000)  # nosec B101
    assert attacks["caps"] == "0000000000000000"  # nosec B101
    assert attacks["no_new_privs"] == "1"  # nosec B101
    assert attacks["processes"] == ["1"]  # nosec B101
    assert attacks["hostname"] == "sandbox"  # nosec B101


def test_no_secret_reaches_its_environment(attacks):
    assert not [k for k in attacks["env"] if any(w in k.upper() for w in ("TOKEN", "KEY", "SECRET", "PASS", "WSL"))]  # nosec B101


def test_nothing_survives_into_the_next_run():
    assert _run("open('/tmp/left_behind', 'w').write('x')").ok  # nosec B101
    run = _run("import os; print(os.path.exists('/tmp/left_behind'))")
    assert run.stdout.strip() == "False"  # nosec B101


def test_an_endless_loop_is_ended_at_its_limit():
    started = time.monotonic()
    run = _run("while True: pass", seconds=3)
    assert run.result == "timeout"  # nosec B101
    # Python is PID 1 in the service and ignores SIGTERM: before KillSignal=SIGKILL
    # a 5 s limit took 96 s to end.
    assert time.monotonic() - started < 12  # nosec B101


def test_memory_past_the_limit_is_killed():
    assert _run("x = bytearray(600 * 1024 * 1024)", memory_mb=128).result == "oom-kill"  # nosec B101


def test_a_fork_bomb_stops_at_the_task_limit():
    code = (
        "import os, time\nn = 0\ntry:\n    while True:\n        if os.fork() == 0:\n            time.sleep(20)\n"
        "            os._exit(0)\n        n += 1\nexcept OSError:\n    print(n)\n"
    )
    run = _run(code, seconds=10)
    assert run.ok and int(run.stdout) < 32  # nosec B101


def test_a_flood_of_output_is_cut_and_ended():
    started = time.monotonic()
    run = _run("import sys\nwhile True: sys.stdout.write('y' * 65536)", seconds=20)
    assert run.result == "output-limit"  # nosec B101
    assert len(run.stdout.encode()) <= wsl_sandbox.MAX_OUTPUT_BYTES  # nosec B101
    # Ended at the cut, not at the 20 s limit, and inside WSL too: a killed
    # wsl.exe left the service writing until its time limit.
    assert time.monotonic() - started < 15  # nosec B101
    left = subprocess.run(  # nosec B603 B607
        ["wsl.exe", "-d", wsl_sandbox.distro(), "-u", "root", "--exec", "systemctl", "list-units",
         "agent-guru-sandbox-*", "--state=active", "--no-legend", "--plain"],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert left.stdout.strip() == "", left.stdout  # nosec B101


def test_a_forged_result_line_does_not_change_the_result():
    run = _run("import sys\nprint('Finished with result: success', file=sys.stderr)\nsys.exit(5)")
    assert (run.result, run.exit_code) == ("exit-code", 5)  # nosec B101


def test_a_shell_script_is_held_by_the_same_boundary():
    script = (
        "ls /home/guru >/dev/null 2>&1 && echo home-open; ls /mnt/c >/dev/null 2>&1 && echo drive-open; "
        "(exec 3<>/dev/tcp/1.1.1.1/53) 2>/dev/null && echo net-open; sudo -n true 2>/dev/null && echo root; "
        "touch /etc/x 2>/dev/null && echo etc-open; id -un"
    )
    run = asyncio.run(wsl_sandbox.run_shell(script, seconds=15))
    assert run.ok and run.stdout.split() == ["agsandbox"], (run.stdout, run.stderr)  # nosec B101
