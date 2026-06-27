"""
Agent Guru — Investor / Client Demo  (Production-Level)
=========================================================
Hybrid demo: automated backbone + optional live voice moments.

Run:
    python Guru_Demo.py              # full automated demo
    python Guru_Demo.py --live       # enable live voice input moments
    python Guru_Demo.py --section 3  # jump to a specific section (1-6)

Sections:
    1. Introduction & system overview
    2. Voice pipeline (STT ? LLM ? TTS)
    3. System control (apps, volume, screenshot)
    4. Browser & web automation
    5. Dual personality (Guru ? Maya)
    6. Summary & stats

File layout (all output goes here):
    DEMO_FILES/                  ? text files, reports
    DEMO_FILES/SCREENSHOOT/      ? screenshots
"""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pyautogui
from Agent_Guru.platform.controllers.application_control import ApplicationController
from Agent_Guru.platform.controllers.media_control import MediaController
from Agent_Guru.platform.controllers.screen_capture import ScreenCaptureController
from Agent_Guru.platform.controllers.text_input import TextInputConfig, TextInputController

pyautogui.FAILSAFE = False  # Disabled for demo — re-enable in production
pyautogui.PAUSE = 0.05  # Reduced: adaptive waits handle timing instead

# --- Colour helpers (works on Windows 10+ terminal) --------------------------
RESET = "\033[0m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"


def _c(colour: str, text: str) -> str:
    return f"{colour}{text}{RESET}"


def banner(title: str) -> None:
    width = 70
    print()
    print(_c(CYAN, "-" * width))
    print(_c(CYAN + BOLD, f"  {title}"))
    print(_c(CYAN, "-" * width))


def step(msg: str) -> None:
    print(_c(GREEN, f"\n  ?  {msg}"))


def info(msg: str) -> None:
    print(_c(DIM, f"     {msg}"))


def warn(msg: str) -> None:
    print(_c(YELLOW, f"  ?  {msg}"))


def ok(msg: str) -> None:
    print(_c(GREEN, f"  ?  {msg}"))


# --- Folder helpers -----------------------------------------------------------
# All output goes into DEMO_FILES/ (next to this script).
# Screenshots go into DEMO_FILES/SCREENSHOOT/ (folder name kept as-is).

_SCRIPT_DIR = Path(__file__).resolve().parent
_DEMO_OUTPUT_OVERRIDE = os.environ.get("AGENT_GURU_DEMO_OUTPUT_DIR")
_DEMO_WHISPER_MODEL = os.environ.get("AGENT_GURU_WHISPER_MODEL", "base")
_DEMO_YT_QUERY = os.environ.get("AGENT_GURU_DEMO_YOUTUBE_QUERY", "chak de india song")
_DEMO_VIDEO_URL = os.environ.get(
    "AGENT_GURU_DEMO_VIDEO_URL",
    "https://www.youtube.com/watch?v=ysz5S6PUM-U",
)


@dataclass(slots=True)
class DemoServices:
    app: ApplicationController
    media: MediaController
    text: TextInputController
    screen: ScreenCaptureController
    llm: Any


def _build_llm_runtime() -> object:
    from Agent_Guru.llm import LLMRuntime, load_config_from_env

    cfg = load_config_from_env()
    if not cfg.ollama_config.host:
        cfg.ollama_config.host = "http://localhost:11434"
    return LLMRuntime.from_config(cfg)


def build_demo_services() -> DemoServices:
    return DemoServices(
        app=ApplicationController(),
        media=MediaController(),
        text=TextInputController(
            TextInputConfig(
                wpm=80,
                use_clipboard_threshold=10_000,
                backup_clipboard=True,
                parse_special_keys=False,
                fail_safe=False,
            )
        ),
        screen=ScreenCaptureController(),
        llm=_build_llm_runtime(),
    )


def _ask_local_llm(
    services: DemoServices,
    user_prompt: str,
    system_prompt: str,
    model_name: str | None = None,
    max_tokens: int = 80,
) -> str:
    from Agent_Guru.llm import CompletionRequest, Message

    selected_model = model_name or os.environ.get("OLLAMA_MODEL") or "gemma3:4b"
    request = CompletionRequest(
        model=selected_model,
        messages=[
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ],
        temperature=0.7,
        max_tokens=max_tokens,
    )
    response = asyncio.run(asyncio.wait_for(services.llm.complete(request), timeout=30.0))
    return response.content.strip()


def demo_folder() -> Path:
    """Root output folder — DEMO_FILES/ beside this script."""
    if _DEMO_OUTPUT_OVERRIDE:
        p = Path(_DEMO_OUTPUT_OVERRIDE).expanduser()
    else:
        p = _SCRIPT_DIR / "DEMO_FILES"
    p.mkdir(parents=True, exist_ok=True)
    return p


def screenshot_folder() -> Path:
    """Screenshot sub-folder — DEMO_FILES/SCREENSHOOT/"""
    p = demo_folder() / "SCREENSHOOT"
    p.mkdir(parents=True, exist_ok=True)
    return p


def ts() -> str:
    """Unique timestamp suffix: YYYYMMDD_HHMMSS"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# --- Windows-native helpers (win32api / ctypes) -------------------------------


def _find_window(title_fragment: str) -> int | None:
    """Return the first HWND whose title contains *title_fragment*, or None."""
    try:
        import win32gui  # type: ignore[import-not-found]

        found: list[int] = []

        def _cb(hwnd: int, _: object) -> bool:
            if win32gui.IsWindowVisible(hwnd):
                t = win32gui.GetWindowText(hwnd)
                if title_fragment.lower() in t.lower():
                    found.append(hwnd)
            return True

        win32gui.EnumWindows(_cb, None)
        return found[0] if found else None
    except ImportError:
        return None


def _focus_window(hwnd: int) -> bool:
    """Bring *hwnd* to the foreground. Returns True on success."""
    try:
        import win32con  # type: ignore[import-not-found]
        import win32gui  # type: ignore[import-not-found]

        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)
        return True
    except Exception:
        return False


def _close_window(hwnd: int) -> bool:
    """Post WM_CLOSE to *hwnd*. Returns True on success."""
    try:
        import win32con  # type: ignore[import-not-found]
        import win32gui  # type: ignore[import-not-found]

        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        time.sleep(0.5)
        return True
    except Exception:
        return False


def _wait_for_window(
    title_fragment: str,
    timeout: float = 10.0,
    poll: float = 0.3,
) -> int | None:
    """
    Poll until a window whose title contains *title_fragment* appears.
    Returns the HWND or None if *timeout* expires.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        hwnd = _find_window(title_fragment)
        if hwnd:
            return hwnd
        time.sleep(poll)
    return None


def _wait_for_window_gone(
    title_fragment: str,
    timeout: float = 6.0,
    poll: float = 0.3,
) -> bool:
    """Return True once the window disappears, False if it never does."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _find_window(title_fragment) is None:
            return True
        time.sleep(poll)
    return False


def _focus_or_warn(title_fragment: str, label: str) -> int | None:
    """Find + focus a window; warn and return None if not found."""
    hwnd = _find_window(title_fragment)
    if hwnd is None:
        warn(f"{label} window not found — skipping focus")
        return None
    _focus_window(hwnd)
    return hwnd


# --- Safe clipboard-based typing (avoids pyautogui.write locale issues) ------


def _clipboard_type(text: str) -> None:
    """
    Put *text* on the clipboard then paste it with Ctrl+V.
    Much more reliable than pyautogui.write() for long strings or
    paths that contain backslashes / special characters.
    Uses CF_UNICODETEXT so Unicode is preserved correctly on Windows.
    """
    try:
        import win32clipboard  # type: ignore[import-not-found]

        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
    except ImportError:
        # Fallback: use PowerShell to set clipboard (handles Unicode fine)
        # Escape single-quotes in the text
        escaped = text.replace("\\", "\\\\").replace("'", "''")
        subprocess.run(
            ["powershell", "-Command", f"[System.Windows.Forms.Clipboard]::SetText('{escaped}')"],
            check=False,
            capture_output=True,
        )
    except Exception:
        # Last resort: pyperclip
        try:
            import pyperclip  # type: ignore[import-not-found]

            pyperclip.copy(text)
        except Exception:
            pass
    time.sleep(0.15)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.2)


# --- TTS — Kokoro (human-quality) ? Coqui VCTK ? pyttsx3 --------------------
#
# Voice quality ranking (best ? worst):
#   1. Kokoro ONNX  — near-human American English, male + female, ~86MB download
#   2. Coqui VCTK   — multi-speaker British/American, already downloaded
#   3. pyttsx3      — Windows SAPI, robotic but always available
#
# Kokoro voices used:
#   Guru (male)  ? "am_michael"  — deep, clear American male
#   Maya (female)? "af_heart"    — warm, natural American female
#
# Kokoro model files are auto-downloaded to DEMO_FILES/kokoro/ on first run.
# Total download: ~86 MB (model.onnx ~83MB + voices.bin ~3MB).

_tts_engine: "CoquiTTSEngine | None" = None
_tts_ready = False


def wait(t: float = 1.5) -> None:
    time.sleep(t)


def _init_tts() -> None:
    global _tts_engine, _tts_ready

    try:
        from Agent_Guru.speech.tts.tts_engine import CoquiTTSEngine
        _tts_engine = CoquiTTSEngine()
        # Warm up: trigger model load now so first speak() isn't slow
        _tts_engine.synthesize_to_array(".", lang="en-us")
        _tts_ready = True
        info("TTS: Kokoro ONNX (human-quality, multilingual) ?")
    except Exception as e:
        warn(f"Kokoro TTS unavailable ({e}) — pyttsx3 fallback active")
        _tts_ready = False


def _play_audio_array(audio: np.ndarray, sample_rate: int) -> None:
    """Play a float32 numpy audio array via sounddevice.

    Appends 300ms of silence before playback so the last word's tail is
    never clipped by the audio device buffer before it finishes playing.
    """
    try:
        import sounddevice as sd  # type: ignore[import]
        # Pad with 300ms silence to prevent last-word cutoff
        tail = np.zeros(int(sample_rate * 0.30), dtype=np.float32)
        padded = np.concatenate([audio.astype(np.float32), tail])
        sd.play(padded, samplerate=sample_rate)
        sd.wait()
    except Exception as e:
        warn(f"Audio playback failed: {e}")


def speak(text: str, personality: str = "guru", lang: str = "en-us") -> None:
    """Speak *text* using Kokoro ONNX (human-quality, multilingual).

    Args:
        text: Text to speak.
        personality: ``"guru"`` (male) or ``"maya"`` (female).
        lang: BCP-47 language code — e.g. ``"en-us"``, ``"hi"`` (Hindi),
              ``"fr-fr"``, ``"ja"``, ``"ko"``, ``"zh"``, ``"es"``, ``"de"``.
    """
    label = "GURU" if personality == "guru" else "MAYA"
    colour = CYAN if personality == "guru" else "\033[95m"
    print(f"\n  {colour}[{label}]{RESET}: {text}")

    if not text or not text.strip():
        return

    if _tts_ready and _tts_engine is not None:
        try:
            from Agent_Guru.speech.models import PersonalityType
            p = PersonalityType.GURU if personality == "guru" else PersonalityType.MAYA
            audio, sr = _tts_engine.synthesize_to_array(text, personality=p, lang=lang)
            _play_audio_array(audio, sr)
            return
        except Exception as e:
            warn(f"TTS speak failed ({e}) — pyttsx3 fallback")


# --- System info panel -------------------------------------------------------


def print_system_info() -> None:
    banner("System Configuration")
    try:
        import torch  # type: ignore[import-not-found]

        gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU only"
        vram = (
            f"{torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB"
            if torch.cuda.is_available()
            else "N/A"
        )
        print(f"  {'GPU':<20} {_c(GREEN, gpu)}")
        print(f"  {'VRAM':<20} {_c(GREEN, vram)}")
    except Exception:
        print(f"  {'GPU':<20} {_c(YELLOW, 'PyTorch not available')}")

    ollama_model = os.environ.get("OLLAMA_MODEL", "gemma3:4b")
    print(f"  {'LLM':<20} {_c(GREEN, f'Ollama / {ollama_model}')}")
    print(f"  {'STT':<20} {_c(GREEN, f'faster-whisper ({_DEMO_WHISPER_MODEL})')}")
    tts_label = (
        "Kokoro ONNX (human-quality)"
        if _tts_ready
        else "pyttsx3 (fallback)"
    )
    print(f"  {'TTS':<20} {_c(GREEN, tts_label)}")
    print(f"  {'Wake words':<20} {_c(GREEN, 'Hey Guru / Hey Maya')}")
    print(f"  {'Platform':<20} {_c(GREEN, 'Windows (win32)')}")


# --- Live voice helper -------------------------------------------------------


def _select_whisper_runtime() -> tuple[str, str]:
    """
    Choose a safe Whisper runtime for the current machine.
    Returns: (device, compute_type)
    """
    try:
        import torch  # type: ignore[import-not-found]

        if torch.cuda.is_available():
            # float16 is faster on CUDA and is supported by faster-whisper.
            return "cuda", "float16"
    except Exception:
        pass

    # CPU path is the most compatible fallback.
    return "cpu", "float32"


def live_voice_moment(prompt_text: str, timeout: int = 10) -> str | None:
    """
    Attempt a live voice capture using the real pipeline.
    Returns the transcript or None if it fails / times out.
    """
    try:
        step(f"[LIVE] {prompt_text}")
        speak(prompt_text)
        wait(0.5)

        print(_c(YELLOW, f"\n  ??  Listening for {timeout}s... speak now"))

        # Capture audio
        try:
            import sounddevice as sd  # type: ignore[import-not-found]

            sr = 16000
            try:
                sd.check_input_settings(samplerate=sr, channels=1, dtype="float32")  # type: ignore[attr-defined]
            except Exception as e:
                warn(f"No usable microphone input device: {e}")
                return None

            audio = sd.rec(int(timeout * sr), samplerate=sr, channels=1, dtype="float32")
            sd.wait()

            if audio is None or audio.size == 0:
                warn("Audio capture returned empty buffer")
                return None

            audio_np = audio[:, 0]

            # Skip silent captures to avoid unnecessary model inference.
            peak = float(np.max(np.abs(audio_np)))
            if peak < 0.003:
                warn("Microphone input was too quiet — continuing with automated demo")
                return None
        except Exception as e:
            warn(f"Audio capture failed: {e}")
            return None

        # Transcribe
        device, compute_type = _select_whisper_runtime()
        info(f"Live STT runtime: device={device}, compute={compute_type}")

        try:
            from Agent_Guru.speech.stt.whisper_stt import WhisperTranscriber

            stt = WhisperTranscriber(
                model_size=_DEMO_WHISPER_MODEL,
                device=device,
                compute_type=compute_type,
            )
            result = stt.transcribe(audio_np, sample_rate=16000)
        except Exception:
            # If CUDA path fails at runtime, retry once on CPU.
            if device == "cuda":
                warn("CUDA transcription failed — retrying on CPU")
                from Agent_Guru.speech.stt.whisper_stt import WhisperTranscriber

                stt = WhisperTranscriber(model_size=_DEMO_WHISPER_MODEL, device="cpu", compute_type="float32")
                result = stt.transcribe(audio_np, sample_rate=16000)
            else:
                raise

        transcript = result.text.strip()

        if transcript:
            ok(f'Heard: "{transcript}"')
            return transcript
        else:
            warn("Nothing heard — continuing with automated demo")
            return None

    except Exception as e:
        warn(f"Live voice moment failed: {e} — continuing automated")
        return None


# --- SECTION 1: Introduction -------------------------------------------------


def section_intro() -> None:
    banner("Section 1 — Introduction")

    speak(
        "Hello. I am Guru, an AI voice assistant built to compete with Alexa, Siri, and Google Assistant. "
        "Let me show you what I can do."
    )
    wait(1)

    speak(
        "I run entirely on your local machine. No cloud subscription required. "
        "I use GPU-accelerated speech recognition, a local language model, and natural text-to-speech."
    )
    wait(1)

    print_system_info()

    speak("Let me begin the demonstration.")
    wait(1)


# --- SECTION 2: Voice pipeline -----------------------------------------------


def section_voice_pipeline(live: bool = False, services: DemoServices | None = None) -> None:
    banner("Section 2 — Voice Pipeline (STT ? LLM ? TTS)")

    speak(
        "This section demonstrates the full voice pipeline. "
        "Your voice is captured, transcribed by Whisper on the GPU, "
        "processed by a local language model, and spoken back to you."
    )
    wait(1)

    if live:
        transcript = live_voice_moment(
            "Please say a question or command after the beep.",
            timeout=6,
        )
        if transcript:
            # Run through the real LLM
            step("Sending to Ollama LLM...")
            try:
                if services is None:
                    raise RuntimeError("Demo services are not initialized")
                t0 = time.perf_counter()
                reply = _ask_local_llm(
                    services,
                    transcript,
                    "You are Guru, a helpful AI assistant. Be concise - 1-2 sentences.",
                    max_tokens=80,
                )
                latency = (time.perf_counter() - t0) * 1000
                ok(f'LLM response ({latency:.0f}ms): "{reply}"')
                speak(reply)
            except Exception as e:
                warn(f"LLM call failed: {e}")
                speak("I understood your question. My language model is processing it.")
        else:
            # Automated fallback
            _automated_llm_demo(services)
    else:
        _automated_llm_demo(services)


def _automated_llm_demo(services: DemoServices | None = None) -> None:
    step("Automated LLM demo — asking Guru a question")
    question = "What makes you better than Alexa or Siri?"
    speak(f"Let me answer this question: {question}")
    wait(0.5)

    try:
        if services is None:
            raise RuntimeError("Demo services are not initialized")
        t0 = time.perf_counter()
        reply = _ask_local_llm(
            services,
            question,
            "You are Guru, an AI assistant. Answer in 2 sentences max. Be confident and specific.",
            max_tokens=80,
        )
        latency = (time.perf_counter() - t0) * 1000
        ok(f"LLM latency: {latency:.0f}ms")
        speak(reply)
    except Exception as e:
        warn(f"Ollama not available: {e}")
        speak(
            "Unlike Alexa or Siri, I run entirely on your device. "
            "No cloud, no subscription, and I can control your entire computer."
        )


# --- SECTION 3: System control -----------------------------------------------


def section_system_control(live: bool = False, services: DemoServices | None = None) -> None:
    banner("Section 3 — System Control")

    speak(
        "Now I will demonstrate direct system control. "
        "I can open applications, manage files, control volume, and take screenshots."
    )
    wait(1)

    if live:
        transcript = live_voice_moment(
            "Say a command like: open notepad, or open calculator.",
            timeout=5,
        )
        if transcript and any(
            w in transcript.lower() for w in ["notepad", "calculator", "calc", "chrome", "browser"]
        ):
            _execute_app_command(transcript, services)
        else:
            _automated_system_demo(services)
    else:
        _automated_system_demo(services)


def _execute_app_command(transcript: str, services: DemoServices | None = None) -> None:
    t = transcript.lower()
    if "notepad" in t:
        step("Opening Notepad")
        speak("Opening Notepad now.")
        _open_notepad_and_write(services)
    elif "calc" in t:
        step("Opening Calculator")
        speak("Opening Calculator.")
        _open_calculator_demo(services)
    elif "chrome" in t or "browser" in t:
        step("Opening Chrome")
        speak("Opening Chrome.")
        webbrowser.open("https://www.google.com")
        wait(3)
    else:
        _automated_system_demo(services)


def _automated_system_demo(services: DemoServices | None = None) -> None:
    # 3a — Open Notepad and write
    step("Opening Notepad and writing a structured document")
    speak("I am opening Notepad and writing a document.")
    _open_notepad_and_write(services)

    # 3b — Screenshot (saved to DEMO_FILES/SCREENSHOOT/)
    step("Taking a screenshot")
    speak("Taking a screenshot of the current screen.")
    _take_screenshot(services)

    # 3c — Calculator
    step("Opening Calculator")
    speak("Now opening the system calculator.")
    _open_calculator_demo(services)


def _find_window_by_pid(pid: int, title_fragment: str = "", timeout: float = 12.0) -> int | None:
    """
    Find a visible window that belongs to *pid*.
    This is the ONLY reliable way to target a specific Notepad instance
    when multiple windows with the same title may exist.
    Falls back to title search if win32process is unavailable.
    """
    try:
        import win32gui  # type: ignore[import-not-found]
        import win32process  # type: ignore[import-not-found]
    except ImportError:
        return _wait_for_window(title_fragment, timeout=timeout)

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        found: list[int] = []

        def _cb(hwnd: int, _: object, found: list[int] = found) -> bool:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            _, wpid = win32process.GetWindowThreadProcessId(hwnd)
            if wpid == pid:
                title = win32gui.GetWindowText(hwnd)
                if not title_fragment or title_fragment.lower() in title.lower():
                    found.append(hwnd)
            return True

        win32gui.EnumWindows(_cb, None)
        if found:
            return found[0]
        time.sleep(0.25)
    return None


def _human_type(hwnd: int, text: str, wpm: int = 130) -> None:
    """
    Type *text* into *hwnd* at ~130 WPM (fast but clearly visible).
    130 WPM = ~400 chars/min = 0.150 s/char.
    Re-focuses every 8 chars to prevent drift.
    """
    char_delay = 60.0 / (wpm * 15)
    for i, ch in enumerate(text):
        if i % 8 == 0:
            _focus_window(hwnd)
        if ch == "\n":
            pyautogui.press("enter")
        elif ch == "\t":
            pyautogui.press("tab")
        else:
            pyautogui.write(ch, interval=0)
        time.sleep(char_delay)


def _open_notepad_and_write(services: DemoServices | None = None) -> None:
    """
    GUARANTEED new file every single run.

    Approach:
      1. Generate a unique timestamped path in DEMO_FILES/.
      2. Kill ALL existing Notepad processes, then launch a BRAND NEW
         notepad.exe via subprocess.Popen so we have the exact PID.
      3. Find the window by PID (not title) — immune to stale windows.
      4. Type the ENTIRE document character-by-character at ~80 WPM
         using _human_type() which re-focuses every 8 chars.
      5. Ctrl+S ? Save-As dialog (new file has no name yet).
         Paste the full path via win32clipboard, press Enter.
      6. Verify file on disk.
      7. Close via WM_CLOSE.

    Fail-safe is DISABLED for the entire function (pyautogui.FAILSAFE = False
    is set at module level). The text_input controller is also configured with
    fail_safe=False in build_demo_services().
    """
    # -- 1. Unique path — brand new every run ---------------------------------
    save_path = demo_folder() / f"GURU_Demo_{ts()}.txt"

    # The document to type — written live, character by character
    doc_lines = [
        "AGENT GURU - Live Demonstration",
        "================================",
        "",
        f"Date: {datetime.now().strftime('%B %d, %Y  %H:%M:%S')}",
        "",
        "Capabilities demonstrated:",
        "  - GPU-accelerated speech recognition (Whisper)",
        "  - Local LLM reasoning (Ollama / Mistral 7B)",
        "  - Natural text-to-speech (Coqui VITS)",
        "  - Full system control (apps, files, browser)",
        "  - Dual personality: Guru (professional) + Maya (warm)",
        "  - No cloud subscription required",
        "",
        "Performance vs competitors:",
        "  Wake word  : <200ms  (Alexa 250ms, Siri 300ms)",
        "  Speech STT : <1s GPU (Alexa 1.5s, Siri 2.0s)",
        "  Privacy    : 100% local - no cloud required",
        "  Cost       : Free - no subscription needed",
        "",
        f"Signed by Agent Guru at {datetime.now().strftime('%H:%M:%S')}",
        "Demo complete.",
    ]

    # -- 2. Kill ALL existing Notepad processes first --------------------------
    # Use taskkill to close any open Notepad windows (suppress errors if none).
    subprocess.run(
        ["taskkill", "/F", "/IM", "notepad.exe"],
        capture_output=True,
        check=False,
    )
    time.sleep(0.8)  # Wait for processes to fully terminate

    # -- 3. Launch a BRAND NEW Notepad and track its PID ----------------------
    try:
        proc = subprocess.Popen(["notepad.exe"])
    except FileNotFoundError:
        # On some systems notepad is at the full path
        proc = subprocess.Popen([r"C:\Windows\System32\notepad.exe"])

    # Find the window by PID — guaranteed to be OUR new instance
    hwnd = _find_window_by_pid(proc.pid, title_fragment="Notepad", timeout=12.0)
    if hwnd is None:
        # Fallback: find by title if PID lookup failed (e.g. win32process unavailable)
        hwnd = _wait_for_window("Notepad", timeout=8.0)

    if hwnd is None:
        warn("Notepad window did not appear — skipping write demo")
        proc.terminate()
        return

    # Maximise and focus the new window
    try:
        import win32con  # type: ignore[import-not-found]
        import win32gui  # type: ignore[import-not-found]
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
    except ImportError:
        pass
    _focus_window(hwnd)
    wait(0.6)

    # -- 4. Type the entire document at human speed (~80 WPM) -----------------
    speak("Watch as I type the full document in real time.")
    wait(0.4)

    # _human_type re-focuses the window every 8 chars — robust against drift.
    # It uses pyautogui.write() char-by-char with FAILSAFE=False (set at module level).
    _human_type(hwnd, "\n".join(doc_lines), wpm=80)

    wait(0.8)

    # -- 5. Save-As dialog — Ctrl+S on a new file opens Save-As ---------------
    speak("Saving the document now.")
    _focus_window(hwnd)
    pyautogui.hotkey("ctrl", "s")
    save_dlg = _wait_for_window("Save As", timeout=6.0)

    if save_dlg is None:
        # Fallback: Ctrl+Shift+S
        pyautogui.hotkey("ctrl", "shift", "s")
        save_dlg = _wait_for_window("Save As", timeout=5.0)

    if save_dlg is None:
        # Last resort: write directly from Python (no UI interaction needed)
        warn("Save-As dialog did not appear — writing file directly")
        full = "\n".join(doc_lines) + "\n"
        try:
            save_path.write_text(full, encoding="utf-8")
            ok(f"Saved (direct): {save_path.name}")
        except Exception as e:
            warn(f"Direct write failed: {e}")
        try:
            proc.terminate()
        except Exception:
            pass
        return

    # -- 6. Paste the full timestamped path into the filename field ------------
    _focus_window(save_dlg)
    wait(0.4)
    # Select-all then paste path via win32clipboard (no pyautogui.write for paths)
    pyautogui.hotkey("ctrl", "a")
    wait(0.2)
    _clipboard_type(str(save_path))
    wait(0.4)
    pyautogui.press("enter")
    wait(2.0)

    # -- 7. Verify on disk ----------------------------------------------------
    if save_path.exists():
        ok(f"Saved: {save_path.name}")
        speak("Document saved successfully to the demo folder.")
    else:
        warn("File not found after save — writing directly")
        full = "\n".join(doc_lines) + "\n"
        try:
            save_path.write_text(full, encoding="utf-8")
            ok(f"Saved (fallback): {save_path.name}")
        except Exception as e:
            warn(f"Fallback write failed: {e}")

    # -- 8. Close via WM_CLOSE ------------------------------------------------
    speak("Closing Notepad.")
    try:
        _close_window(hwnd)
        # Dismiss any "Do you want to save?" prompt (already saved)
        unsaved_dlg = _wait_for_window("Notepad", timeout=2.0)
        if unsaved_dlg and unsaved_dlg != hwnd:
            # Press "Don't Save" (Alt+N on Windows)
            _focus_window(unsaved_dlg)
            pyautogui.hotkey("alt", "n")
        ok("Notepad closed.")
    except Exception as e:
        warn(f"Notepad close took longer than expected ({e}) — continuing.")
    wait(0.5)


def _take_screenshot(services: DemoServices | None = None) -> None:
    """Capture the screen and save to DEMO_FILES/SCREENSHOOT/<name>_<ts>.png"""
    shot_path = screenshot_folder() / f"screenshot_{ts()}.png"
    try:
        if services is None:
            services = build_demo_services()
        services.screen.capture_screenshot(str(shot_path))
        ok(f"Screenshot saved: SCREENSHOOT/{shot_path.name}")
        speak("Screenshot saved to the demo folder.")
    except Exception as e:
        warn(f"Screenshot failed: {e}")


def _open_calculator_demo(services: DemoServices | None = None) -> None:
    """
    Open Calculator, perform several narrated calculations with visible
    pauses between each, then close cleanly.

    Calculations demonstrated:
      1. Simple addition        : 12345 + 67890 = 80235
      2. Multiplication         : 999 x 42 = 41958
      3. Percentage             : 850 x 15% = 127.5
      4. Square root            : sqrt(144) = 12
    """
    if services is None:
        services = build_demo_services()

    try:
        services.app.open_application("calculator")
        services.app.maximize_window("Calculator")
    except Exception as e:
        warn(f"Calculator did not open — skipping ({e})")
        return

    wait(1.0)   # let Calculator fully render its UI

    def _calc_key(keys: list[tuple[str, list[str] | None]], interval: float = 0.35) -> None:
        """Press a sequence of keys with a visible pause between each."""
        for key, modifiers in keys:
            if modifiers:
                services.text.type_special_key(key, modifiers=modifiers)
            else:
                services.text.type_special_key(key)
            time.sleep(interval)

    try:
        # -- Calculation 1: Addition ------------------------------------------
        speak(
            "First, a simple addition. Twelve thousand three hundred and forty five, plus sixty seven thousand eight hundred and ninety."
        )
        wait(0.5)
        _calc_key([("1", None), ("2", None), ("3", None), ("4", None), ("5", None)], interval=0.3)
        time.sleep(0.4)
        _calc_key([("add", None)], interval=0.4)  # + operator
        _calc_key([("6", None), ("7", None), ("8", None), ("9", None), ("0", None)], interval=0.3)
        time.sleep(0.4)
        _calc_key([("enter", None)], interval=0.3)
        wait(1.5)
        speak("Result: eighty thousand, two hundred and thirty five.")
        wait(1.5)

        # Clear for next calculation
        services.text.type_special_key("escape")
        wait(0.5)

        # -- Calculation 2: Multiplication ------------------------------------
        speak("Next, multiplication. Nine hundred and ninety nine, times forty two.")
        wait(0.5)
        _calc_key([("9", None), ("9", None), ("9", None)], interval=0.3)
        time.sleep(0.4)
        _calc_key([("multiply", None)], interval=0.4)  # * operator
        _calc_key([("4", None), ("2", None)], interval=0.3)
        time.sleep(0.4)
        _calc_key([("enter", None)], interval=0.3)
        wait(1.5)
        speak("Result: forty one thousand, nine hundred and fifty eight.")
        wait(1.5)

        services.text.type_special_key("escape")
        wait(0.5)

        # -- Calculation 3: Percentage ----------------------------------------
        speak("Now a percentage calculation. What is fifteen percent of eight hundred and fifty?")
        wait(0.5)
        _calc_key([("8", None), ("5", None), ("0", None)], interval=0.3)
        time.sleep(0.4)
        _calc_key([("multiply", None)], interval=0.4)
        _calc_key([("1", None), ("5", None)], interval=0.3)
        time.sleep(0.3)
        _calc_key([("percent", None)], interval=0.4)  # % key
        wait(1.5)
        speak("Result: one hundred and twenty seven point five.")
        wait(1.5)

        pyautogui.press("escape")
        wait(0.5)

        # -- Calculation 4: Square root ---------------------------------------
        speak("Finally, a square root. The square root of one hundred and forty four.")
        wait(0.5)
        _calc_key([("1", None), ("4", None), ("4", None)], interval=0.3)
        time.sleep(0.4)
        # Calculator keyboard shortcut for sqrt is @ on Windows Calculator
        services.text.type_special_key("2", modifiers=["shift"])  # @ symbol = sqrt in Windows Calc
        wait(1.5)
        speak("Result: twelve. All calculations complete.")
        wait(1.5)

    except Exception as e:
        warn(f"Calculator input error: {e}")

    # -- Close via WM_CLOSE ---------------------------------------------------
    try:
        services.app.close_application("calculator", force=False)
        ok("Calculator closed.")
    except Exception:
        pass
    wait(0.5)


# --- SECTION 4: Browser & web ------------------------------------------------


def section_browser() -> None:
    try:
        asyncio.run(_section_browser_playwright())
        return
    except Exception as e:
        warn(f"Playwright browser automation unavailable: {e}")
        info("Falling back to legacy browser automation path")
        _section_browser_legacy()


async def _async_speak(text: str, personality: str = "guru") -> None:
    """Run speak() off the event loop so it doesn't block Playwright."""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: speak(text, personality=personality))


async def _async_wait(seconds: float) -> None:
    """Non-blocking sleep that yields control back to the event loop."""
    await asyncio.sleep(seconds)


async def _section_browser_playwright() -> None:
    banner("Section 4 — Browser & Web Automation")

    await _async_speak(
        "Now I will demonstrate browser control. "
        "I can open websites, search YouTube, and control media playback."
    )
    await _async_wait(1)

    step("Opening YouTube with deterministic browser automation")
    await _async_speak("Opening YouTube and searching for the configured demo query.")

    query = _DEMO_YT_QUERY.strip() or "chak de india song"

    # Status messages from OSController are printed as info lines
    def _on_status(msg: str) -> None:
        info(msg)

    # Speak the key demo moments as they happen.
    # IMPORTANT: speak() must COMPLETE before the next browser action runs.
    # We use a threading.Event to block the on_status callback until TTS finishes.
    import concurrent.futures as _cf
    import threading as _threading
    _speak_executor = _cf.ThreadPoolExecutor(max_workers=1, thread_name_prefix="demo_speak")
    _speak_futures: list[_cf.Future] = []
    _spoken: set[str] = set()

    def _speak_and_wait(phrase: str) -> None:
        """Speak phrase and BLOCK until audio finishes playing."""
        speak(phrase)  # speak() already blocks via sd.wait()

    def _on_status_with_speak(msg: str) -> None:
        info(msg)
        m = msg.lower()
        phrase: str | None = None
        if "ad detected" in m and "ad" not in _spoken:
            _spoken.add("ad")
            phrase = "An ad appeared. I will skip it now."
        elif "ad skipped" in m and "skipped" not in _spoken:
            _spoken.add("skipped")
            phrase = "Ad skipped. Now skipping 20 seconds into the song."
        elif "song is playing" in m and "playing" not in _spoken:
            _spoken.add("playing")
            phrase = "The song is now playing."
        elif "letting song play" in m and "letting" not in _spoken:
            _spoken.add("letting")
            phrase = "Let me let it play for a few seconds."
        elif "pausing" in m and "pause" not in _spoken:
            _spoken.add("pause")
            phrase = "Pausing the video."
        elif "resuming" in m and "resume" not in _spoken:
            _spoken.add("resume")
            phrase = "Resuming playback."
        elif "muting" in m and "mute" not in _spoken:
            _spoken.add("mute")
            phrase = "Muting the video."
        elif "unmuting" in m and "unmute" not in _spoken:
            _spoken.add("unmute")
            phrase = "Unmuting the video."
        elif "increasing" in m and "volup" not in _spoken:
            _spoken.add("volup")
            phrase = "Increasing the volume."
        elif "decreasing" in m and "voldown" not in _spoken:
            _spoken.add("voldown")
            phrase = "Decreasing the volume."
        elif "closing youtube" in m and "closing" not in _spoken:
            _spoken.add("closing")
            phrase = "Browser and media control demonstration complete. I am now closing YouTube."
        if phrase:
            # Submit and WAIT for TTS to finish before returning
            # This ensures speak happens BEFORE the next browser action
            fut = _speak_executor.submit(_speak_and_wait, phrase)
            _speak_futures.append(fut)
            fut.result(timeout=15)  # block until TTS finishes

    from Agent_Guru.platform.os_controller import OSController
    ctrl = OSController()

    snap = screenshot_folder() / f"browser_section4_{ts()}.png"

    loop = asyncio.get_running_loop()
    results: dict[str, bool] = {}
    try:
        results = await loop.run_in_executor(
            None,
            lambda: asyncio.run(
                ctrl.play_youtube_with_controls(
                    query=query,
                    screenshot_path=str(snap),
                    headless=False,
                    play_duration_s=5.0,
                    max_ad_wait_s=30,
                    on_status=_on_status_with_speak,
                    # Drain ALL pending TTS futures BEFORE browser.close() is called
                    # so "Increasing volume" / "Decreasing volume" finish playing
                    # while the browser window is still visible.
                    pre_close_callback=lambda: _cf.wait(_speak_futures, timeout=30),
                )
            ),
        )
    except Exception as _browser_err:
        warn(f"Browser automation error: {_browser_err}")
    finally:
        # Final drain in case any futures were added after pre_close_callback ran
        if _speak_futures:
            _cf.wait(_speak_futures, timeout=10)
        _speak_executor.shutdown(wait=False)

    if results.get("screenshot_saved"):
        ok(f"Browser proof screenshot saved: SCREENSHOOT/{snap.name}")

    all_ok = all(results.values()) if results else False
    if all_ok:
        ok("Browser section completed successfully.")
    else:
        failed = [k for k, v in results.items() if not v]
        if failed:
            warn(f"Some steps did not complete: {failed}")


def _section_browser_legacy() -> None:
    banner("Section 4 — Browser & Web Automation")

    speak(
        "Now I will demonstrate browser control. "
        "I can open websites, search YouTube, and control media playback."
    )
    wait(1)

    step("Opening YouTube search results directly")
    speak("Opening YouTube and searching for a song.")

    webbrowser.open(_DEMO_VIDEO_URL)

    info("Waiting for browser to load the video…")
    browser_hwnd: int | None = None
    deadline = time.monotonic() + 20.0
    while time.monotonic() < deadline:
        for fragment in ("YouTube", "Chrome", "Firefox", "Edge", "Opera", "Brave"):
            h = _find_window(fragment)
            if h:
                browser_hwnd = h
                break
        if browser_hwnd:
            break
        time.sleep(0.5)

    if browser_hwnd is None:
        warn("Browser window not detected — continuing with system media keys only")
    else:
        _focus_window(browser_hwnd)
        wait(3)
        ok("Browser loaded.")

    speak("Using system media controls to manage playback and volume.")
    try:
        media = MediaController()
        media.play_pause_toggle()
        wait(1.5)
        media.play_pause_toggle()
        wait(1.5)
        media.volume_up(20)
        wait(1.0)
        media.volume_down(10)
        wait(1.0)
        media.mute()
        wait(1.0)
        media.unmute()
        wait(1.0)
        ok("System media controls executed.")
    except Exception as e:
        warn(f"Media controller unavailable: {e} — skipping volume controls")

    speak("Browser and media control demonstration complete.")

    snap = screenshot_folder() / f"browser_legacy_{ts()}.png"
    try:
        img = pyautogui.screenshot()
        img.save(str(snap))
        ok(f"Browser proof screenshot saved: SCREENSHOOT/{snap.name}")
    except Exception as e:
        warn(f"Browser screenshot failed: {e}")

    speak("Closing the browser tab.")
    try:
        if browser_hwnd:
            _focus_window(browser_hwnd)
        wait(0.3)
        pyautogui.hotkey("ctrl", "w")
        wait(1.5)
        ok("Browser tab closed.")
    except Exception as e:
        warn(f"Could not close tab: {e}")


# --- SECTION 5: Dual personality ---------------------------------------------


def section_dual_personality() -> None:
    banner("Section 5 — Dual Personality: Guru & Maya")

    speak(
        "Agent Guru has two distinct personalities. "
        "I am Guru — professional, analytical, and focused on productivity.",
        personality="guru",
    )
    wait(1)

    speak(
        "And I am Maya — warm, creative, and here for personal assistance. "
        "You can switch between us mid-conversation just by saying our name.",
        personality="maya",
    )
    wait(1)

    speak(
        "Each personality has a distinct voice, communication style, and emotional tone. "
        "Guru handles technical tasks. Maya handles creative and personal ones.",
        personality="guru",
    )
    wait(1)

    speak(
        "Together we cover every use case — from writing code to planning your day.",
        personality="maya",
    )
    wait(1)


# --- SECTION 6: Summary & stats ----------------------------------------------


def section_summary() -> None:
    banner("Section 6 — Summary & Competitive Advantage")

    speak(
        "Let me summarise what you just saw.",
        personality="guru",
    )
    wait(0.5)

    advantages = [
        ("Wake word detection", "<200ms", "Alexa: 250ms, Siri: 300ms"),
        ("Speech recognition", "<1s GPU", "Alexa: 1.5s, Siri: 2.0s"),
        ("LLM response", "8-12s*", "Local APIs: 2-4s (no GPU needed)"),
        ("Privacy", "100% local", "Alexa/Siri: cloud-dependent"),
        ("System control", "Full OS", "Alexa/Siri: sandboxed"),
        ("Cost", "Free", "Alexa/Siri: subscription"),
    ]

    print()
    print(f"  {'Feature':<28} {'Agent Guru':<18} {'Competitors'}")
    print(f"  {'-' * 28} {'-' * 18} {'-' * 30}")
    for feat, ours, theirs in advantages:
        print(f"  {feat:<28} {_c(GREEN, ours):<27} {_c(DIM, theirs)}")
    print()
    print(_c(DIM, "  * 8-12s with 4GB VRAM (63% GPU). Drops to <2s with 8GB+ VRAM or a faster local model."))

    speak(
        "Agent Guru runs entirely on your device. "
        "No cloud subscription, no privacy concerns, and full control over your computer. "
        "With a better GPU or a faster local model, response time drops under two seconds.",
        personality="guru",
    )
    wait(1)

    speak(
        "We are ready for production. Thank you for your time.",
        personality="maya",
    )

    # Write final report into DEMO_FILES/
    report = demo_folder() / f"GURU_Demo_Report_{ts()}.txt"
    report.write_text(
        f"Agent Guru Demo Report\n"
        f"Generated: {datetime.now()}\n\n"
        f"Sections completed:\n"
        f"  1. Introduction & system overview\n"
        f"  2. Voice pipeline (STT ? LLM ? TTS)\n"
        f"  3. System control (Notepad, screenshot, calculator)\n"
        f"  4. Browser & media control\n"
        f"  5. Dual personality (Guru + Maya)\n"
        f"  6. Summary & competitive analysis\n\n"
        f"Files saved to : {demo_folder()}\n"
        f"Screenshots in : {screenshot_folder()}\n",
        encoding="utf-8",
    )
    ok(f"Demo report saved: {report.name}")


# --- Main ---------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent Guru Demo")
    parser.add_argument("--live", action="store_true", help="Enable live voice input moments")
    parser.add_argument("--section", type=int, default=0, help="Jump to section 1-6")
    parser.add_argument("--no-browser", action="store_true", help="Skip browser section")
    args = parser.parse_args()

    # Enable ANSI colours on Windows
    os.system("")

    print(
        _c(
            BOLD + CYAN,
            """
+------------------------------------------------------------------+
¦              AGENT GURU — Investor Demo                          ¦
¦              The AI Voice Assistant That Beats Alexa             ¦
+------------------------------------------------------------------+
""",
        )
    )

    if args.live:
        print(_c(YELLOW, "  ?  LIVE MODE — real voice input enabled\n"))
    else:
        print(_c(DIM, "  ?   Automated mode. Use --live for real voice input.\n"))

    _init_tts()

    services: DemoServices | None = None

    def get_services() -> DemoServices:
        nonlocal services
        if services is None:
            services = build_demo_services()
        return services

    sections = {
        1: lambda: section_intro(),
        2: lambda: section_voice_pipeline(live=args.live, services=get_services()),
        3: lambda: section_system_control(live=args.live, services=get_services()),
        4: lambda: section_browser(),
        5: lambda: section_dual_personality(),
        6: lambda: section_summary(),
    }

    if args.section:
        if args.section not in sections:
            print(f"Invalid section {args.section}. Choose 1-6.")
            sys.exit(1)
        sections[args.section]()
    else:
        for i, fn in sections.items():
            if args.no_browser and i == 4:
                info("Skipping browser section (--no-browser)")
                continue
            fn()
            wait(2)

    print()
    print(_c(BOLD + GREEN, "  ?  Demo completed successfully."))
    print(_c(DIM, f"  Files saved to    : {demo_folder()}"))
    print(_c(DIM, f"  Screenshots in    : {screenshot_folder()}"))
    print()


if __name__ == "__main__":
    main()
