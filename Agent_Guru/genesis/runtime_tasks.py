"""Checks and fetches that need the installed application, run inside the managed runtime.

The launcher has only the standard library, so it cannot load a model or
synthesise speech itself. It starts the private environment's Python with
`-m Agent_Guru.genesis.runtime_tasks <task> [args]` (actions.run_runtime_task)
and reads the one JSON line the task prints last:

    {"result": "PASS" | "WARNING" | "FAILED" | "NOT INSTALLED" | "NOT CONFIGURED" | "NOT APPLICABLE",
     "detail": "...", ...measurements}

A task that cannot run (a package missing) says NOT INSTALLED, never PASS.
Nothing here writes to the person's memory, settings or reminders: the
checks that store something isolate the profile into a temporary folder first.
Only the task ids in TASKS can be run; the arguments are a model name, a
Whisper size or nothing, and each task checks its own.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess  # nosec B404 - nvidia-smi with a fixed argument list
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

ASSETS = Path(__file__).resolve().parent / "assets"
#: Kokoro-synthesised "Hello Guru." (Guru voice), 1.2 s, 16 kHz mono PCM16.
STT_CLIP = ASSETS / "hello_guru.wav"
STT_EXPECTED = "hello"


def _result(result: str, detail: str, **extra: Any) -> dict[str, Any]:
    return {"result": result, "detail": detail, **extra}


def _missing(exc: ImportError) -> dict[str, Any]:
    return _result("NOT INSTALLED", f"{exc.name or exc} is not installed in the private environment")


def core_import(args: list[str]) -> dict[str, Any]:
    """The assistant's own modules import and the orchestrator can be built."""
    start = time.perf_counter()
    try:
        import Agent_Guru.integration.orchestrator  # noqa: F401
        import Agent_Guru.memory.memory_manager  # noqa: F401
    except ImportError as exc:
        return _missing(exc)
    return _result("PASS", "the orchestrator and memory modules import", seconds=round(time.perf_counter() - start, 2))


def _isolated() -> Path:
    from Agent_Guru.utils.profile_isolation import isolate_profile

    return isolate_profile(tempfile.mkdtemp(prefix="genesis_check_"), link_model_caches=False)


def db_readwrite(args: list[str]) -> dict[str, Any]:
    """aiosqlite writes a row and a new connection reads it back, in a temporary file."""
    import asyncio

    try:
        import aiosqlite
    except ImportError as exc:
        return _missing(exc)
    folder = Path(tempfile.mkdtemp(prefix="genesis_db_"))

    async def check() -> str:
        async with aiosqlite.connect(folder / "check.db") as db:
            await db.execute("CREATE TABLE t (v TEXT)")
            await db.execute("INSERT INTO t VALUES ('written')")
            await db.commit()
        async with aiosqlite.connect(folder / "check.db") as db, db.execute("SELECT v FROM t") as cur:
            row = await cur.fetchone()
            return row[0] if row else ""

    try:
        value = asyncio.run(check())
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    return _result("PASS" if value == "written" else "FAILED", f"read back {value!r}")


def memory_persist(args: list[str]) -> dict[str, Any]:
    """MemoryManager stores a turn, and a second manager on the same database recalls it."""
    import asyncio

    root = _isolated()
    try:
        from Agent_Guru.memory.memory_manager import MemoryManager
    except ImportError as exc:
        return _missing(exc)

    async def check() -> list[dict[str, Any]]:
        first = MemoryManager()
        await first.initialize()
        await first.store_interaction("GURU", "my favourite colour is teal", "Noted: teal.")
        if hasattr(first, "close"):
            await _maybe_await(first.close())
        second = MemoryManager()
        await second.initialize()
        return await second.recall("GURU", limit=5)

    try:
        recalled = asyncio.run(check())
    finally:
        shutil.rmtree(root, ignore_errors=True)
    found = any("teal" in json.dumps(r) for r in recalled)
    return _result("PASS" if found else "FAILED",
                   "a new manager recalled the stored turn" if found else f"recalled {len(recalled)} turns, none stored")


async def _maybe_await(value: Any) -> None:
    if hasattr(value, "__await__"):
        await value


def embed_sentence(args: list[str]) -> dict[str, Any]:
    try:
        from Agent_Guru.reasoning.memory.embedding import EmbeddingGenerator
    except ImportError as exc:
        return _missing(exc)
    start = time.perf_counter()
    try:
        gen = EmbeddingGenerator()
        vector = gen.generate("Agent Guru remembers what you tell it.")
    except (ImportError, RuntimeError) as exc:
        return _result("FAILED", f"{type(exc).__name__}: {exc}")
    norm = sum(x * x for x in vector) ** 0.5
    route = type(gen.model).__name__
    ok = len(vector) == 384 and abs(norm - 1.0) < 1e-3
    return _result("PASS" if ok else "FAILED", f"{len(vector)} numbers, length {norm:.4f}, route {route}",
                   seconds=round(time.perf_counter() - start, 2), route=route)


def _pstate() -> str:
    smi = shutil.which("nvidia-smi")
    if not smi:
        return "no NVIDIA GPU"
    done = subprocess.run([smi, "--query-gpu=pstate,clocks_throttle_reasons.active", "--format=csv,noheader"],  # nosec B603
                          capture_output=True, text=True, timeout=10, check=False)
    return done.stdout.strip() or f"nvidia-smi exit {done.returncode}"


def llm_reply(args: list[str]) -> dict[str, Any]:
    """A short reply from the chosen model, with tokens per second, first-token time and the GPU share."""
    model = args[0] if args else ""
    if not re.fullmatch(r"[a-z0-9][a-z0-9._\-/]*(:[a-z0-9._\-]+)?", model):
        return _result("NOT CONFIGURED", f"no valid model name given ({model!r})")
    try:
        import ollama
    except ImportError as exc:
        return _missing(exc)
    client = ollama.Client()
    start = time.perf_counter()
    first = None
    text = ""
    final: Any = None
    try:
        for part in client.chat(model=model, messages=[{"role": "user", "content": "Reply with one word: ready"}],
                                stream=True, think=False, options={"num_predict": 24}):
            piece = part.message.content or ""
            if piece and first is None:
                first = time.perf_counter() - start
            text += piece
            final = part
    except Exception as exc:  # the client raises its own and httpx's errors
        return _result("FAILED", f"{model}: {type(exc).__name__}: {exc}")
    eval_count = getattr(final, "eval_count", 0) or 0
    eval_ns = getattr(final, "eval_duration", 0) or 0
    tps = round(eval_count / (eval_ns / 1e9), 1) if eval_ns else None
    share = None
    try:
        for m in client.ps().models:
            if m.model == model or m.name == model:
                share = round(100 * (m.size_vram or 0) / m.size, 1) if m.size else None
    except Exception:  # noqa: BLE001 - the share is reported unknown, not guessed
        share = None
    if not text.strip():
        return _result("FAILED", f"{model} returned an empty reply")
    return _result("PASS", f"{model} replied {text.strip()[:40]!r}", model=model, tokens_per_second=tps,
                   first_token_seconds=round(first, 2) if first else None, gpu_share_percent=share,
                   gpu_pstate=_pstate(), measured_at=time.strftime("%Y-%m-%d %H:%M:%S"))


def kokoro_fetch(args: list[str]) -> dict[str, Any]:
    """The voice files, through the voice's own loader and pins, into the voice's own folder."""
    try:
        from Agent_Guru.speech.tts import tts_engine
    except ImportError as exc:
        return _missing(exc)
    try:
        tts_engine.verify_kokoro_files()
        return _result("PASS", "the pinned voice files were already in place", reused=True)
    except tts_engine.TTSError:
        pass
    for url, path in ((tts_engine._MODEL_URL, tts_engine._MODEL_PATH), (tts_engine._VOICES_URL, tts_engine._VOICES_PATH)):
        tts_engine._download(url, path)
    tts_engine.verify_kokoro_files()
    return _result("PASS", "downloaded and verified")


def whisper_fetch(args: list[str]) -> dict[str, Any]:
    """Every Whisper size the assistant loads: tiny for the wake check, base for speech."""
    sizes = args or ["tiny", "base"]
    bad = [s for s in sizes if s not in ("tiny", "base", "small")]
    if bad:
        return _result("FAILED", f"unknown Whisper size {bad[0]!r}")
    try:
        from faster_whisper.utils import download_model
    except ImportError as exc:
        return _missing(exc)
    for size in sizes:
        download_model(size)
    return _result("PASS", "Whisper " + " and ".join(sizes) + " are in place")


def tts_synthesize(args: list[str]) -> dict[str, Any]:
    try:
        from Agent_Guru.speech.tts.tts_engine import KokoroTTSEngine, TTSError
    except ImportError as exc:
        return _missing(exc)
    start = time.perf_counter()
    try:
        audio, rate = KokoroTTSEngine().synthesize_to_array("Agent Guru is ready.", "guru")
    except (TTSError, ImportError, OSError) as exc:
        return _result("FAILED", f"{type(exc).__name__}: {exc}")
    samples = len(audio)
    seconds = samples / rate if rate else 0
    # Audio data was produced; whether it sounds right needs a person to hear it.
    return _result("PASS" if samples and 0.3 < seconds < 10 else "FAILED",
                   f"{samples} samples at {rate} Hz ({seconds:.2f} s of audio)", needs_listening=True,
                   seconds=round(time.perf_counter() - start, 2))


def voice_import(args: list[str]) -> dict[str, Any]:
    """Every library of the voice stack loads, native parts included.

    voice-packages was checked with core.import, which passes with no voice
    package installed, so a broken install could be marked verified.
    """
    return _imports(["faster_whisper", "ctranslate2", "kokoro_onnx", "silero_vad", "sounddevice", "soundfile", "librosa"],
                    "Whisper, Kokoro, silero VAD, sounddevice and librosa load")


def stt_transcribe(args: list[str]) -> dict[str, Any]:
    size = args[0] if args else "base"
    try:
        import wave

        import numpy as np

        from Agent_Guru.speech.stt.whisper_stt import WhisperModel, WhisperTranscriber
    except ImportError as exc:
        return _missing(exc)
    if WhisperModel is None:
        return _result("NOT INSTALLED", "faster-whisper could not be loaded")
    with wave.open(str(STT_CLIP)) as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32) / 32768
    start = time.perf_counter()
    text = WhisperTranscriber(device="cpu", model_size=size).transcribe(audio, 16000, language="en").text
    heard = STT_EXPECTED in text.lower()
    return _result("PASS" if heard else "FAILED", f"heard {text.strip()!r} in the bundled clip",
                   seconds=round(time.perf_counter() - start, 2))


def wake_load(args: list[str]) -> dict[str, Any]:
    try:
        from Agent_Guru.speech.audio.wake_word import WakeWordDetector
    except ImportError as exc:
        return _missing(exc)
    detector = WakeWordDetector()
    backend, reason = detector._backend, detector._backend_reason
    if backend == "mfcc":
        return _result("WARNING", f"fallback detector: {reason}", backend=backend)
    return _result("PASS", f"{backend}: {reason}", backend=backend)


def vault_check(args: list[str]) -> dict[str, Any]:
    """The credential store encrypts and reads back a throwaway value, in a temporary profile.

    Cloud keys go through this store (DPAPI for the account on Windows). The
    value checked is random and never printed; only whether it came back.
    """
    import secrets as _secrets

    root = _isolated()
    try:
        from Agent_Guru.security import secret_store
    except ImportError as exc:
        return _missing(exc)
    probe = _secrets.token_hex(16)
    try:
        secret_store.save("genesis-check", probe.encode())
        back = secret_store.load("genesis-check")
        on_disk = secret_store.path_for("genesis-check").read_bytes()
    finally:
        shutil.rmtree(root, ignore_errors=True)
    if back is None or back.decode() != probe:
        return _result("FAILED", "the value did not come back from the credential store")
    if probe.encode() in on_disk:
        return _result("FAILED", "the credential store wrote the value in plain text")
    return _result("PASS", "a value was encrypted, stored and read back; the file did not contain it in plain text")


def _imports(names: list[str], what: str) -> dict[str, Any]:
    import importlib

    for name in names:
        try:
            importlib.import_module(name)
        except ImportError as exc:
            return _missing(exc)
        except OSError as exc:  # sounddevice on Linux, without the PortAudio system library
            return _result("NOT CONFIGURED", f"{name} needs a system library: {exc}")
    return _result("PASS", what)


def vision_check(args: list[str]) -> dict[str, Any]:
    return _imports(["cv2", "PIL.Image"], "OpenCV and Pillow load")


def browser_check(args: list[str]) -> dict[str, Any]:
    found = _imports(["playwright.async_api"], "Playwright loads")
    if found["result"] != "PASS":
        return found
    candidates = [Path(p) for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                                    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                                    r"C:\Program Files\Google\Chrome\Application\chrome.exe")]
    browser = next((p for p in candidates if p.is_file()), None) or shutil.which("msedge") or shutil.which("chrome")
    if not browser:
        return _result("NOT CONFIGURED", "Playwright loads, but no installed Edge or Chrome was found")
    return _result("PASS", f"Playwright loads; it will drive {Path(str(browser)).name}")


def coding_check(args: list[str]) -> dict[str, Any]:
    found = _imports(["git"], "GitPython loads")
    if found["result"] != "PASS":
        return found
    if not shutil.which("git"):
        return _result("NOT CONFIGURED", "GitPython loads, but the git program is not installed")
    return _result("PASS", "GitPython loads and git is installed")


def research_reach(args: list[str]) -> dict[str, Any]:
    """The search sources web_search.py uses answer an HTTPS request."""
    import urllib.request

    hosts = {"en.wikipedia.org": "https://en.wikipedia.org/w/api.php?action=query&format=json&meta=siteinfo",
             "api.duckduckgo.com": "https://api.duckduckgo.com/?q=agent&format=json&no_html=1"}
    answered, failed = [], []
    for host, url in hosts.items():
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Agent_Guru"}),  # noqa: S310
                                        timeout=10) as response:  # nosec B310 - two fixed https URLs
                (answered if response.status == 200 else failed).append(host)
        except OSError as exc:
            failed.append(f"{host} ({type(exc).__name__})")
    if not answered:
        return _result("FAILED", "no search source answered: " + ", ".join(failed))
    return _result("PASS" if not failed else "WARNING", "answered: " + ", ".join(answered)
                   + (f"; did not: {', '.join(failed)}" if failed else ""))


TASKS: dict[str, Callable[[list[str]], dict[str, Any]]] = {
    "core.import": core_import, "db.readwrite": db_readwrite, "memory.persist": memory_persist,
    "embed.sentence": embed_sentence, "llm.reply": llm_reply, "kokoro.fetch": kokoro_fetch,
    "whisper.fetch": whisper_fetch, "tts.synthesize": tts_synthesize, "stt.transcribe": stt_transcribe,
    "wake.load": wake_load, "vision.check": vision_check, "browser.check": browser_check,
    "coding.check": coding_check, "research.reach": research_reach, "vault.check": vault_check,
    "voice.import": voice_import,
}


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in TASKS:
        print(json.dumps(_result("FAILED", f"unknown task {argv[:1]}")))
        return 2
    try:
        out = TASKS[argv[0]](argv[1:])
    except Exception as exc:  # noqa: BLE001 - every outcome is reported as one JSON line
        out = _result("FAILED", f"{type(exc).__name__}: {exc}")
    print(json.dumps(out, ensure_ascii=False, default=str))
    return 0 if out["result"] in ("PASS", "WARNING", "NOT APPLICABLE") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
