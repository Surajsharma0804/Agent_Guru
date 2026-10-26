"""`agent-guru doctor`: check that everything the assistant needs works on this machine.

Every check exercises the real component; nothing is reported working because
it is installed or configured. Ollama is asked for its models, the model is
asked for one token, the microphone is opened and read, Kokoro speaks a test
sentence and Whisper must hear it back. Nothing is changed and nothing is
played: the speaker is only found, unless --sound asks for a test tone.

Checks run one after another through HealthCheckManager, each with its own
time limit: loading the model, Whisper and Kokoro at once would make them
compete for the same GPU and memory and report times that mean nothing.

A healthy check is "ok"; "warn" means it works but not as well as it could
(Whisper on the CPU, an owner-only file readable by others); "fail" means
the assistant cannot do that part of its job.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import re
import shutil
import sqlite3
import subprocess  # nosec B404
import sys
import tempfile
import time
import urllib.request
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from Agent_Guru.platform.error_handling.health_check import (
    ComponentHealth,
    HealthCheckManager,
    HealthStatus,
)

if TYPE_CHECKING:
    from pathlib import Path

# Words only: Whisper writes "testing one two three" as "Testing 1, 2, 3",
# which a word check reads as a miss.
_TEST_PHRASE = "the quick brown fox jumps over the lazy dog"
_TEST_WORDS_NEEDED = 7  # of 9, so punctuation or one misheard word is not a failure
_MIN_PYTHON = (3, 11)
_REQUIRED_MODULES = {
    "ollama": "talking to the model",
    "faster_whisper": "speech recognition",
    "kokoro_onnx": "speech output",
    "sounddevice": "microphone and speaker",
    "numpy": "audio",
    "psutil": "processes and resources",
    "aiosqlite": "long-term memory",
}
_WINDOWS_MODULES = {"win32gui": "window and app control", "comtypes": "WhatsApp verification"}


def _result(name: str, status: HealthStatus, message: str, **metadata: Any) -> ComponentHealth:
    return ComponentHealth(name=name, status=status, message=message, last_check=datetime.now(tz=UTC),
                           response_time_ms=0.0, metadata=metadata)


def _ok(name: str, message: str, **meta: Any) -> ComponentHealth:
    return _result(name, HealthStatus.HEALTHY, message, **meta)


def _warn(name: str, message: str, **meta: Any) -> ComponentHealth:
    return _result(name, HealthStatus.DEGRADED, message, **meta)


def _fail(name: str, message: str, **meta: Any) -> ComponentHealth:
    return _result(name, HealthStatus.UNHEALTHY, message, **meta)


def _ollama_host() -> str:
    host = os.environ.get("OLLAMA_HOST", "").strip() or "http://localhost:11434"
    return host if host.startswith(("http://", "https://")) else f"http://{host}"


def _get_json(url: str, payload: dict[str, Any] | None = None, timeout: float = 5.0) -> Any:
    if not url.startswith(("http://", "https://")):
        msg = f"not an http URL: {url}"
        raise ValueError(msg)
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
        return json.loads(response.read())


# ---------------------------------------------------------------------------
# Checks. Each one is async and returns a ComponentHealth.
# ---------------------------------------------------------------------------


async def check_python() -> ComponentHealth:
    version = ".".join(map(str, sys.version_info[:3]))
    if sys.version_info[:2] < _MIN_PYTHON:
        return _fail("python", f"Python {version} is older than {'.'.join(map(str, _MIN_PYTHON))}")
    return _ok("python", f"Python {version}", executable=sys.executable)


async def check_dependencies() -> ComponentHealth:
    wanted = dict(_REQUIRED_MODULES)
    if sys.platform == "win32":
        wanted.update(_WINDOWS_MODULES)
    missing = []
    for module, purpose in wanted.items():
        try:
            await asyncio.to_thread(importlib.import_module, module)
        except Exception as exc:
            missing.append(f"{module} ({purpose}): {type(exc).__name__}")
    if missing:
        return _fail("dependencies", "missing: " + "; ".join(missing))
    return _ok("dependencies", f"{len(wanted)} required packages import")


async def check_ollama() -> ComponentHealth:
    host = _ollama_host()
    try:
        tags = await asyncio.to_thread(_get_json, f"{host}/api/tags")
    except Exception as exc:
        return _fail("ollama", f"not reachable at {host}: {exc}. Start Ollama, or set OLLAMA_HOST.")
    names = sorted(m.get("name", "") for m in tags.get("models", []))
    return _ok("ollama", f"reachable at {host}, {len(names)} models installed", models=names)


async def check_model() -> ComponentHealth:
    """The configured model exists and produces a token; reports the load and first-token time."""
    from Agent_Guru.reasoning.llm.generation import OLLAMA_THINK, ollama_model, ollama_options

    host, model = _ollama_host(), ollama_model()
    try:
        tags = await asyncio.to_thread(_get_json, f"{host}/api/tags")
    except Exception as exc:
        return _fail("model", f"cannot ask Ollama for its models: {exc}")
    names = {m.get("name", "") for m in tags.get("models", [])}
    if model not in names and f"{model}:latest" not in names:
        return _fail("model", f"{model} is not installed. Run: ollama pull {model}", installed=sorted(names))
    started = time.perf_counter()
    # Loaded with the options the assistant itself sends. With only num_predict, Ollama loaded the
    # model at its own context (4096 here) instead of the assistant's 6144, so the load time
    # reported was not the one the user pays, and the next real request reloaded the model:
    # 5.1 s on gemma3:1b, measured.
    try:
        reply = await asyncio.to_thread(
            _get_json, f"{host}/api/generate",
            {"model": model, "prompt": "Say OK.", "stream": False, "think": OLLAMA_THINK,
             "options": ollama_options(num_predict=1)},
            120.0,
        )
    except Exception as exc:
        return _fail("model", f"{model} is installed but did not answer: {exc}")
    seconds = time.perf_counter() - started
    load_s = reply.get("load_duration", 0) / 1e9
    return _ok("model", f"{model} answers ({seconds:.1f} s for one token, {load_s:.1f} s of it loading)",
               model=model, seconds=round(seconds, 3), load_s=round(load_s, 3))


def _nvidia_smi() -> list[dict[str, Any]]:
    exe = shutil.which("nvidia-smi")
    if exe is None:
        return []
    out = subprocess.run(  # nosec B603  # noqa: S603  fixed program and arguments
        [exe, "--query-gpu=name,memory.total,memory.used,driver_version", "--format=csv,noheader,nounits"],
        capture_output=True, text=True, timeout=10, check=False,
    )
    gpus = []
    for line in out.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 4:
            gpus.append({"name": parts[0], "total_mb": int(parts[1]), "used_mb": int(parts[2]), "driver": parts[3]})
    return gpus


async def check_gpu() -> ComponentHealth:
    try:
        gpus = await asyncio.to_thread(_nvidia_smi)
    except Exception as exc:
        return _warn("gpu", f"nvidia-smi failed: {exc}; the model and speech will be slower on the CPU")
    if not gpus:
        return _warn("gpu", "no NVIDIA GPU found; the model and speech run on the CPU")
    g = gpus[0]
    free = g["total_mb"] - g["used_mb"]
    return _ok("gpu", f"{g['name']}, {g['total_mb'] / 1024:.1f} GB VRAM, {free / 1024:.1f} GB free, driver {g['driver']}",
               gpus=gpus)


async def check_cpu_and_memory() -> ComponentHealth:
    import psutil

    ram = psutil.virtual_memory()
    available_gb = ram.available / 2**30
    message = f"{psutil.cpu_count(logical=True)} CPU threads, {ram.total / 2**30:.1f} GB RAM, {available_gb:.1f} GB free"
    if available_gb < 2.0:
        return _warn("cpu_and_ram", message + "; under 2 GB free, models may page to disk")
    return _ok("cpu_and_ram", message)


async def check_microphone() -> ComponentHealth:
    """Opens the default input for half a second and checks samples arrive."""
    import numpy as np
    import sounddevice as sd

    try:
        device = sd.query_devices(kind="input")
    except Exception as exc:
        return _fail("microphone", f"no input device: {exc}")

    def record() -> Any:
        from Agent_Guru.speech.audio.portaudio_lock import portaudio_in_use

        with portaudio_in_use():
            return sd.rec(8000, samplerate=16000, channels=1, dtype="float32", blocking=True)

    try:
        audio = await asyncio.to_thread(record)
    except Exception as exc:
        return _fail("microphone", f"{device['name']} could not be opened: {exc}")
    rms = float(np.sqrt(np.mean(np.square(audio)))) if audio is not None and len(audio) else 0.0
    if rms == 0.0:
        return _warn("microphone", f"{device['name']} opened but sent pure silence (muted, or blocked by privacy settings)")
    return _ok("microphone", f"{device['name']} records (level {rms:.6f} over 0.5 s)", device=device["name"], rms=rms)


async def check_speaker(play: bool = False) -> ComponentHealth:
    import numpy as np
    import sounddevice as sd

    try:
        device = sd.query_devices(kind="output")
    except Exception as exc:
        return _fail("speaker", f"no output device: {exc}")
    if not play:
        return _ok("speaker", f"{device['name']} found (not played; use --sound to hear a test tone)", device=device["name"])
    from Agent_Guru.speech.audio.portaudio_lock import play_and_wait

    t = np.linspace(0, 0.3, int(16000 * 0.3), False)
    tone = (np.sin(2 * np.pi * 660 * t) * 0.2).astype(np.float32)
    try:
        await asyncio.to_thread(play_and_wait, tone, 16000)
    except Exception as exc:
        return _fail("speaker", f"{device['name']} could not play: {exc}")
    return _ok("speaker", f"{device['name']} played a test tone", device=device["name"])


async def check_speech() -> ComponentHealth:
    """Kokoro says a test phrase and Whisper must hear it back, through the app's own SpeechEngine."""
    import numpy as np

    from Agent_Guru.speech.engine import SpeechEngine
    from Agent_Guru.speech.models import PersonalityType
    from Agent_Guru.speech.stt.whisper_stt import cuda_failure

    engine = SpeechEngine()
    started = time.perf_counter()
    try:
        await asyncio.to_thread(engine.initialize)
    except Exception as exc:
        return _fail("speech", f"speech engine did not start: {exc}")
    load_s = time.perf_counter() - started
    started = time.perf_counter()
    try:
        audio, rate = await asyncio.to_thread(engine.synthesize_to_array, _TEST_PHRASE, PersonalityType.GURU)
    except Exception as exc:
        return _fail("speech", f"speech output (Kokoro) failed: {exc}")
    tts_s = time.perf_counter() - started
    audio = np.asarray(audio, dtype=np.float32)
    if rate != 16000:
        audio = np.interp(np.linspace(0, len(audio), int(len(audio) * 16000 / rate), endpoint=False),
                          np.arange(len(audio)), audio).astype(np.float32)
    started = time.perf_counter()
    try:
        heard = await asyncio.to_thread(engine.transcribe, audio)
    except Exception as exc:
        return _fail("speech", f"speech recognition (Whisper) failed: {exc}")
    stt_s = time.perf_counter() - started
    text = re.sub(r"[^a-z ]", "", (getattr(heard, "text", "") or "").lower()).strip()
    device = getattr(engine.stt_transcriber, "device", "unknown")
    meta = {"heard": text, "whisper_device": device, "load_s": round(load_s, 2), "tts_s": round(tts_s, 2),
            "stt_s": round(stt_s, 2)}
    heard_words = set(text.split())
    if sum(word in heard_words for word in _TEST_PHRASE.split()) < _TEST_WORDS_NEEDED:
        return _fail("speech", f"Kokoro spoke {_TEST_PHRASE!r} but Whisper heard {text!r}", **meta)
    summary = f"Kokoro spoke the test phrase in {tts_s:.1f} s and Whisper heard it in {stt_s:.1f} s on the {device.upper()}"
    if device != "cuda":
        reason = cuda_failure() or "no CUDA device was usable"
        return _warn("speech", f"{summary}; the GPU was not used: {reason}", **meta)
    return _ok("speech", summary, **meta)


def _app_data() -> Path:
    from Agent_Guru.utils.path_utils import app_data_dir

    return app_data_dir(create=False)


async def check_data_folder() -> ComponentHealth:
    folder = _app_data()
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=folder, prefix="doctor_", delete=True) as handle:
            handle.write(b"ok")
    except Exception as exc:
        return _fail("data_folder", f"{folder} is not writable: {exc}")
    return _ok("data_folder", f"{folder} is writable", path=str(folder))


def acl_principals(icacls_output: str, path: str) -> list[str]:
    r"""The accounts icacls lists for *path*, e.g. ["NT AUTHORITY\\SYSTEM", "HOST\\user"].

    The first line starts with the path itself, whose drive letter has a colon
    of its own, so each account is read up to its ":(" permission marker.
    """
    principals = []
    for line in icacls_output.splitlines():
        if ":(" not in line:
            continue
        line = line.removeprefix(path)
        principals.append(line[: line.index(":(")].strip())
    return principals


def _owner_only(path: Path) -> bool | None:
    """True if only the current user can open *path* (Windows ACL), None if that cannot be read."""
    if sys.platform != "win32":
        return (path.stat().st_mode & 0o077) == 0
    exe = shutil.which("icacls")
    user = os.environ.get("USERNAME", "").lower()
    if exe is None or not user:
        return None
    out = subprocess.run([exe, str(path)], capture_output=True, text=True, timeout=10, check=False)  # nosec B603  # noqa: S603
    principals = acl_principals(out.stdout, str(path))
    if not principals:
        return None
    return all(p.lower() == user or p.lower().endswith("\\" + user) for p in principals)


async def check_databases() -> ComponentHealth:
    """memory.db and turns.db open read-only and pass SQLite's quick_check; reports who else can read them."""
    folder = _app_data()
    found, problems, notes = {}, [], []
    for name in ("memory.db", "turns.db"):
        path = folder / name
        if not path.exists():
            notes.append(f"{name} not created yet")
            continue
        try:
            uri = f"{path.as_uri()}?mode=ro"
            conn = sqlite3.connect(uri, uri=True, timeout=5)
            try:
                verdict = conn.execute("PRAGMA quick_check").fetchone()[0]
                tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            finally:
                conn.close()
        except sqlite3.Error as exc:
            problems.append(f"{name}: {exc}")
            continue
        if verdict != "ok":
            problems.append(f"{name}: {verdict}")
        found[name] = {"tables": len(tables), "bytes": path.stat().st_size}
        private = await asyncio.to_thread(_owner_only, path)
        if private is False:
            notes.append(f"{name} can be read by other accounts on this computer")
    if problems:
        return _fail("databases", "; ".join(problems), databases=found)
    message = ", ".join(f"{n} ok ({v['bytes'] // 1024} KB)" for n, v in found.items()) or "no databases yet"
    if any("other accounts" in n for n in notes):
        return _warn("databases", message + "; " + "; ".join(notes), databases=found)
    return _ok("databases", message + ("; " + "; ".join(notes) if notes else ""), databases=found)


async def check_audit_log() -> ComponentHealth:
    """The audit log on disk is unbroken: every signature valid, every entry linked to the one before."""
    from Agent_Guru.security.audit.logger import AuditLogger, signing_key_at

    folder = _app_data()
    path, key_path = folder / "audit.db", folder / "audit_signing.key"
    if not path.exists():
        return _ok("audit_log", "no audit log yet")
    try:
        key = await asyncio.to_thread(signing_key_at, key_path)
    except Exception as exc:
        return _fail("audit_log", f"the signing key cannot be read ({type(exc).__name__}): earlier entries cannot be verified")
    log = AuditLogger(str(path), signing_key=key)
    ok, broken_at = await asyncio.to_thread(log.verify_chain)
    if not ok:
        return _fail("audit_log", f"entry {broken_at} was changed, or an entry before it was removed or moved")
    with sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True) as conn:
        count = conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0]
    return _ok("audit_log", f"{count} entries, signatures and chain intact")


async def check_settings() -> ComponentHealth:
    """What settings.toml in the data folder set, and what it was refused."""
    from Agent_Guru.utils.settings import apply_settings_file

    path = _app_data() / "settings.toml"
    if not path.exists():
        return _ok("settings", f"no settings file; built-in settings and the environment are used ({path})")
    report = apply_settings_file(path, environ=dict(os.environ))
    if report.error:
        return _fail("settings", f"{path} cannot be read: {report.error}")
    parts = [f"{len(report.applied)} applied"]
    if report.overridden:
        parts.append("overridden by the environment: " + ", ".join(report.overridden))
    if report.refused:
        parts.append("ignored: " + "; ".join(f"{k} ({why})" for k, why in report.refused.items()))
        return _warn("settings", ", ".join(parts), applied=report.applied, refused=report.refused)
    return _ok("settings", ", ".join(parts), applied=report.applied)


async def check_policy() -> ComponentHealth:
    """Which kinds of action the installed policy lets the assistant take.

    Asked through the orchestrator's own policy stage, so the answer is the one
    a voice turn would get, not a second reading of the rules.
    """
    from Agent_Guru.integration.orchestrator import IntegrationOrchestrator
    from Agent_Guru.policy import PolicyEngine
    from Agent_Guru.policy.defaults import install_default_policies

    engine = PolicyEngine()
    install_default_policies(engine)
    orch = IntegrationOrchestrator(
        speech_engine=None, vision_engine=None, llm_runtime=None, platform_controller=None,
        agent_orchestrator=None, memory=None, reasoning=None, security=None, policy=engine,
        avatar=None, deployment=None, gpu_pool=None,  # type: ignore[arg-type]
    )
    probes = {
        "send a message": "communication:send_message:Test:whatsapp:hi",
        "open an app": "system_control:open_app:notepad",
        "close an app": "system_control:close_app:notepad",
        "set a reminder": "system_control:reminder:in 5 minutes",
        "change the volume": "system_control:volume:up",
    }
    allowed, refused = [], []
    for label, intent in probes.items():
        (allowed if await orch._stage_policy(intent) else refused).append(label)
    message = f"allows: {', '.join(allowed) or 'nothing'}; refuses: {', '.join(refused) or 'nothing'}"
    return _ok("policy", message, allowed=allowed, refused=refused)


# ---------------------------------------------------------------------------


def build_manager(*, quick: bool = False, sound: bool = False) -> HealthCheckManager:
    manager = HealthCheckManager(check_timeout=10.0)
    manager.register_check("python", check_python)
    manager.register_check("dependencies", check_dependencies, timeout=60.0)
    manager.register_check("ollama", check_ollama)
    if not quick:
        manager.register_check("model", check_model, timeout=180.0)
    manager.register_check("gpu", check_gpu, timeout=15.0)
    manager.register_check("cpu_and_ram", check_cpu_and_memory)
    manager.register_check("microphone", check_microphone)
    manager.register_check("speaker", lambda: check_speaker(play=sound))
    if not quick:
        manager.register_check("speech", check_speech, timeout=240.0)
    manager.register_check("data_folder", check_data_folder)
    manager.register_check("databases", check_databases, timeout=30.0)
    manager.register_check("audit_log", check_audit_log, timeout=60.0)
    manager.register_check("settings", check_settings)
    manager.register_check("policy", check_policy)
    return manager


_MARK = {HealthStatus.HEALTHY: "ok  ", HealthStatus.DEGRADED: "warn", HealthStatus.UNHEALTHY: "FAIL"}


def run(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="agent-guru doctor", description=__doc__.splitlines()[0])
    parser.add_argument("--quick", action="store_true", help="skip the checks that load models (model, speech)")
    parser.add_argument("--sound", action="store_true", help="play a short test tone on the speaker")
    parser.add_argument("--json", action="store_true", help="print the results as JSON")
    args = parser.parse_args(argv)

    health = asyncio.run(build_manager(quick=args.quick, sound=args.sound).check_health(use_cache=False, sequential=True))
    if args.json:
        print(json.dumps(health.to_dict(), indent=2, default=str))  # noqa: T201  the command's output
    else:
        for c in health.components:
            print(f"[{_MARK.get(c.status, '?   ')}] {c.name:13s} {c.message}  ({c.response_time_ms / 1000:.1f} s)")  # noqa: T201
        print(f"\n{health.healthy_count} ok, {health.degraded_count} warnings, {health.unhealthy_count} failed")  # noqa: T201
    return 1 if health.unhealthy_count else 0
