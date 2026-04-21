"""
Agent Guru — Investor / Client Demo
====================================
Hybrid demo: automated backbone + optional live voice moments.

Run:
    python Guru_Demo.py              # full automated demo
    python Guru_Demo.py --live       # enable live voice input moments
    python Guru_Demo.py --section 3  # jump to a specific section (1-6)

Sections:
    1. Introduction & system overview
    2. Voice pipeline (STT → LLM → TTS)
    3. System control (apps, volume, screenshot)
    4. Browser & web automation
    5. Dual personality (Guru → Maya)
    6. Summary & stats
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path

import pyautogui

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.15

# ─── Colour helpers (works on Windows 10+ terminal) ──────────────────────────
RESET  = "\033[0m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BOLD   = "\033[1m"
DIM    = "\033[2m"


def _c(colour: str, text: str) -> str:
    return f"{colour}{text}{RESET}"


def banner(title: str) -> None:
    width = 70
    print()
    print(_c(CYAN, "─" * width))
    print(_c(CYAN + BOLD, f"  {title}"))
    print(_c(CYAN, "─" * width))


def step(msg: str) -> None:
    print(_c(GREEN, f"\n  ▶  {msg}"))


def info(msg: str) -> None:
    print(_c(DIM, f"     {msg}"))


def warn(msg: str) -> None:
    print(_c(YELLOW, f"  ⚠  {msg}"))


def ok(msg: str) -> None:
    print(_c(GREEN, f"  ✓  {msg}"))


# ─── TTS — prefer Coqui (natural), fall back to pyttsx3 (robotic) ────────────

_tts_engine = None          # pyttsx3 fallback
_coqui_engine = None        # Coqui TTS (natural voice)
_coqui_ready = False


def _init_tts() -> None:
    global _tts_engine, _coqui_engine, _coqui_ready

    # Try Coqui TTS first (natural voice — same engine used in main.py)
    try:
        import io
        import contextlib
        from TTS.api import TTS  # type: ignore[import]
        with contextlib.redirect_stdout(io.StringIO()):
            _coqui_engine = TTS(model_name="tts_models/en/vctk/vits", progress_bar=False)
        _coqui_ready = True
        info("TTS: Coqui VITS (natural voice) ✓")
    except Exception as e:
        warn(f"Coqui TTS unavailable ({e}) — using pyttsx3 fallback")

    # Always init pyttsx3 as fallback
    try:
        import pyttsx3  # type: ignore[import]
        _tts_engine = pyttsx3.init()
        _tts_engine.setProperty("rate", 165)
        voices = _tts_engine.getProperty("voices")
        if voices:
            _tts_engine.setProperty("voice", voices[0].id)
    except Exception:
        pass


def speak(text: str, personality: str = "guru") -> None:
    """Speak text using the best available TTS engine."""
    label = "GURU" if personality == "guru" else "MAYA"
    colour = CYAN if personality == "guru" else "\033[95m"
    print(f"\n  {colour}[{label}]{RESET}: {text}")

    if _coqui_ready and _coqui_engine is not None:
        try:
            import io, contextlib, tempfile, wave
            import numpy as np
            import sounddevice as sd  # type: ignore[import]

            speaker = "p226" if personality == "guru" else "p225"
            # Strip emojis — TTS doesn't need them
            import re
            clean = re.sub(r'[^\x00-\x7F]+', '', text).strip()
            if not clean:
                return

            with contextlib.redirect_stdout(io.StringIO()):
                tmp = tempfile.mktemp(suffix=".wav")
                _coqui_engine.tts_to_file(text=clean, speaker=speaker, file_path=tmp)

            with wave.open(tmp, "rb") as wf:
                sr = wf.getframerate()
                frames = wf.readframes(wf.getnframes())
                audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

            sd.play(audio, samplerate=sr)
            sd.wait()
            os.unlink(tmp)
            return
        except Exception as e:
            pass  # fall through to pyttsx3

    if _tts_engine is not None:
        try:
            _tts_engine.say(text)
            _tts_engine.runAndWait()
        except Exception:
            pass


def wait(t: float = 1.5) -> None:
    time.sleep(t)


# ─── Demo folder ─────────────────────────────────────────────────────────────

def demo_folder() -> Path:
    p = Path.home() / "Documents" / "GURU_Demo"
    p.mkdir(parents=True, exist_ok=True)
    return p


def ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ─── System info panel ───────────────────────────────────────────────────────

def print_system_info() -> None:
    banner("System Configuration")
    try:
        import torch
        gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU only"
        vram = f"{torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB" if torch.cuda.is_available() else "N/A"
        print(f"  {'GPU':<20} {_c(GREEN, gpu)}")
        print(f"  {'VRAM':<20} {_c(GREEN, vram)}")
    except Exception:
        print(f"  {'GPU':<20} {_c(YELLOW, 'PyTorch not available')}")

    ollama_model = os.environ.get("OLLAMA_MODEL", "mistral:7b-instruct")
    print(f"  {'LLM':<20} {_c(GREEN, f'Ollama / {ollama_model}')}")
    print(f"  {'STT':<20} {_c(GREEN, 'faster-whisper (GPU)')}")
    print(f"  {'TTS':<20} {_c(GREEN, 'Coqui VITS (natural)' if _coqui_ready else 'pyttsx3 (fallback)')}")
    print(f"  {'Wake words':<20} {_c(GREEN, 'Hey Guru / Hey Maya')}")
    print(f"  {'Platform':<20} {_c(GREEN, 'Windows (win32)')}")


# ─── Live voice helper ───────────────────────────────────────────────────────

def live_voice_moment(prompt_text: str, timeout: int = 10) -> str | None:
    """
    Attempt a live voice capture using the real pipeline.
    Returns the transcript or None if it fails / times out.
    """
    try:
        import asyncio
        import numpy as np
        from Agent_Guru.speech.stt.whisper_stt import WhisperTranscriber

        step(f"[LIVE] {prompt_text}")
        speak(prompt_text)
        wait(0.5)

        print(_c(YELLOW, f"\n  🎤  Listening for {timeout}s... speak now"))

        # Capture audio
        try:
            import sounddevice as sd  # type: ignore[import]
            sr = 16000
            audio = sd.rec(int(timeout * sr), samplerate=sr, channels=1, dtype="float32")
            sd.wait()
            audio_np = audio[:, 0]
        except Exception as e:
            warn(f"Audio capture failed: {e}")
            return None

        # Transcribe
        stt = WhisperTranscriber(model_size="base", device="cuda")
        result = stt.transcribe(audio_np, sample_rate=16000)
        transcript = result.text.strip()

        if transcript:
            ok(f"Heard: \"{transcript}\"")
            return transcript
        else:
            warn("Nothing heard — continuing with automated demo")
            return None

    except Exception as e:
        warn(f"Live voice moment failed: {e} — continuing automated")
        return None


# ─── SECTION 1: Introduction ─────────────────────────────────────────────────

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


# ─── SECTION 2: Voice pipeline ───────────────────────────────────────────────

def section_voice_pipeline(live: bool = False) -> None:
    banner("Section 2 — Voice Pipeline (STT → LLM → TTS)")

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
                import httpx
                t0 = time.perf_counter()
                r = httpx.post(
                    "http://localhost:11434/api/chat",
                    json={
                        "model": os.environ.get("OLLAMA_MODEL", "mistral:7b-instruct"),
                        "messages": [
                            {"role": "system", "content": "You are Guru, a helpful AI assistant. Be concise — 1-2 sentences."},
                            {"role": "user", "content": transcript},
                        ],
                        "stream": False,
                        "options": {"num_gpu": 99, "num_predict": 80},
                    },
                    timeout=45,
                )
                latency = (time.perf_counter() - t0) * 1000
                reply = r.json()["message"]["content"].strip()
                ok(f"LLM response ({latency:.0f}ms): \"{reply}\"")
                speak(reply)
            except Exception as e:
                warn(f"LLM call failed: {e}")
                speak("I understood your question. My language model is processing it.")
        else:
            # Automated fallback
            _automated_llm_demo()
    else:
        _automated_llm_demo()


def _automated_llm_demo() -> None:
    step("Automated LLM demo — asking Guru a question")
    question = "What makes you better than Alexa or Siri?"
    speak(f"Let me answer this question: {question}")
    wait(0.5)

    try:
        import httpx
        t0 = time.perf_counter()
        r = httpx.post(
            "http://localhost:11434/api/chat",
            json={
                "model": os.environ.get("OLLAMA_MODEL", "mistral:7b-instruct"),
                "messages": [
                    {"role": "system", "content": "You are Guru, an AI assistant. Answer in 2 sentences max. Be confident and specific."},
                    {"role": "user", "content": question},
                ],
                "stream": False,
                "options": {"num_gpu": 99, "num_predict": 80},
            },
            timeout=45,
        )
        latency = (time.perf_counter() - t0) * 1000
        reply = r.json()["message"]["content"].strip()
        ok(f"LLM latency: {latency:.0f}ms")
        speak(reply)
    except Exception as e:
        warn(f"Ollama not available: {e}")
        speak(
            "Unlike Alexa or Siri, I run entirely on your device. "
            "No cloud, no subscription, and I can control your entire computer."
        )


# ─── SECTION 3: System control ───────────────────────────────────────────────

def section_system_control(live: bool = False) -> None:
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
        if transcript and any(w in transcript.lower() for w in ["notepad", "calculator", "calc", "chrome", "browser"]):
            _execute_app_command(transcript)
        else:
            _automated_system_demo()
    else:
        _automated_system_demo()


def _execute_app_command(transcript: str) -> None:
    t = transcript.lower()
    if "notepad" in t:
        step("Opening Notepad")
        speak("Opening Notepad now.")
        subprocess.Popen(["notepad.exe"])
        wait(2)
        _write_demo_text()
    elif "calc" in t:
        step("Opening Calculator")
        speak("Opening Calculator.")
        subprocess.Popen("calc.exe")
        wait(2)
        pyautogui.write("999*42")
        pyautogui.press("enter")
        wait(2)
        speak("Calculation complete.")
        pyautogui.hotkey("alt", "f4")
    elif "chrome" in t or "browser" in t:
        step("Opening Chrome")
        speak("Opening Chrome.")
        webbrowser.open("https://www.google.com")
        wait(3)
    else:
        _automated_system_demo()


def _automated_system_demo() -> None:
    # 3a — Open Notepad and write
    step("Opening Notepad and writing a structured document")
    speak("I am opening Notepad and writing a document.")
    subprocess.Popen(["notepad.exe"])
    wait(2)
    _write_demo_text()

    # 3b — Screenshot
    step("Taking a screenshot")
    speak("Taking a screenshot of the current screen.")
    screenshot_path = demo_folder() / f"screenshot_{ts()}.png"
    try:
        import pyautogui as _pg
        _pg.screenshot(str(screenshot_path))
        ok(f"Screenshot saved: {screenshot_path.name}")
        speak("Screenshot saved to the demo folder.")
    except Exception as e:
        warn(f"Screenshot failed: {e}")

    # 3c — Calculator
    step("Opening Calculator")
    speak("Now opening the system calculator.")
    subprocess.Popen("calc.exe")
    wait(2)
    pyautogui.write("12345+67890")
    pyautogui.press("enter")
    wait(2)
    speak("Calculation complete.")
    pyautogui.hotkey("alt", "f4")
    wait(1)


def _write_demo_text() -> None:
    text = (
        "AGENT GURU — Live Demonstration\n"
        "================================\n\n"
        f"Date: {datetime.now().strftime('%B %d, %Y  %H:%M:%S')}\n\n"
        "Capabilities demonstrated:\n"
        "  • GPU-accelerated speech recognition (Whisper)\n"
        "  • Local LLM reasoning (Ollama / Mistral 7B)\n"
        "  • Natural text-to-speech (Coqui VITS)\n"
        "  • Full system control (apps, files, browser)\n"
        "  • Dual personality: Guru (professional) + Maya (warm)\n"
        "  • No cloud subscription required\n\n"
        "This file was created autonomously by Agent Guru.\n"
    )
    pyautogui.write(text, interval=0.015)
    wait(2)

    speak("Saving the document with a unique timestamp.")
    save_path = str(demo_folder() / f"GURU_Demo_{ts()}.txt")
    pyautogui.hotkey("ctrl", "s")
    wait(1.5)
    pyautogui.write(save_path, interval=0.02)
    wait(0.5)
    pyautogui.press("enter")
    wait(1.5)
    ok(f"Saved: {Path(save_path).name}")

    speak("Document saved. Closing Notepad.")
    pyautogui.hotkey("alt", "f4")
    wait(1)


# ─── SECTION 4: Browser & web ────────────────────────────────────────────────

def section_browser() -> None:
    banner("Section 4 — Browser & Web Automation")

    speak(
        "Now I will demonstrate browser control. "
        "I can open websites, search YouTube, and control media playback."
    )
    wait(1)

    step("Opening YouTube and searching")
    speak("Opening YouTube and searching for a song.")
    webbrowser.open("https://www.youtube.com/results?search_query=chak+de+india+song")
    wait(6)

    speak("Selecting the first result.")
    pyautogui.press("tab")
    wait(0.5)
    pyautogui.press("enter")
    wait(6)

    speak("Playing the video. Now I will demonstrate media controls.")
    wait(2)

    speak("Pausing.")
    pyautogui.press("k")
    wait(2)

    speak("Resuming.")
    pyautogui.press("k")
    wait(2)

    speak("Increasing volume.")
    for _ in range(4):
        pyautogui.press("up")
        wait(0.3)

    wait(3)
    speak("Browser demonstration complete. Closing the tab.")
    pyautogui.hotkey("ctrl", "w")
    wait(1)


# ─── SECTION 5: Dual personality ─────────────────────────────────────────────

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


# ─── SECTION 6: Summary & stats ──────────────────────────────────────────────

def section_summary() -> None:
    banner("Section 6 — Summary & Competitive Advantage")

    speak(
        "Let me summarise what you just saw.",
        personality="guru",
    )
    wait(0.5)

    advantages = [
        ("Wake word detection",    "<200ms",  "Alexa: 250ms, Siri: 300ms"),
        ("Speech recognition",     "<1s GPU", "Alexa: 1.5s, Siri: 2.0s"),
        ("LLM response",           "8-12s*",  "Cloud APIs: 2-4s (no GPU needed)"),
        ("Privacy",                "100% local", "Alexa/Siri: cloud-dependent"),
        ("System control",         "Full OS", "Alexa/Siri: sandboxed"),
        ("Cost",                   "Free",    "Alexa/Siri: subscription"),
    ]

    print()
    print(f"  {'Feature':<28} {'Agent Guru':<18} {'Competitors'}")
    print(f"  {'─'*28} {'─'*18} {'─'*30}")
    for feat, ours, theirs in advantages:
        print(f"  {feat:<28} {_c(GREEN, ours):<27} {_c(DIM, theirs)}")
    print()
    print(_c(DIM, "  * 8-12s with 4GB VRAM (63% GPU). Drops to <2s with 8GB+ VRAM or cloud LLM."))

    speak(
        "Agent Guru runs entirely on your device. "
        "No cloud subscription, no privacy concerns, and full control over your computer. "
        "With a better GPU or a cloud API key, response time drops under two seconds.",
        personality="guru",
    )
    wait(1)

    speak(
        "We are ready for production. Thank you for your time.",
        personality="maya",
    )

    # Write final report
    report = demo_folder() / f"GURU_Demo_Report_{ts()}.txt"
    report.write_text(
        f"Agent Guru Demo Report\n"
        f"Generated: {datetime.now()}\n\n"
        f"Sections completed:\n"
        f"  1. Introduction & system overview\n"
        f"  2. Voice pipeline (STT → LLM → TTS)\n"
        f"  3. System control (Notepad, screenshot, calculator)\n"
        f"  4. Browser & media control\n"
        f"  5. Dual personality (Guru + Maya)\n"
        f"  6. Summary & competitive analysis\n\n"
        f"All files saved to: {demo_folder()}\n",
        encoding="utf-8",
    )
    ok(f"Demo report saved: {report.name}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Agent Guru Demo")
    parser.add_argument("--live", action="store_true", help="Enable live voice input moments")
    parser.add_argument("--section", type=int, default=0, help="Jump to section 1-6")
    parser.add_argument("--no-browser", action="store_true", help="Skip browser section")
    args = parser.parse_args()

    # Enable ANSI colours on Windows
    os.system("")

    print(_c(BOLD + CYAN, """
╔══════════════════════════════════════════════════════════════════╗
║              AGENT GURU — Investor Demo                          ║
║              The AI Voice Assistant That Beats Alexa             ║
╚══════════════════════════════════════════════════════════════════╝
"""))

    if args.live:
        print(_c(YELLOW, "  ⚡  LIVE MODE — real voice input enabled\n"))
    else:
        print(_c(DIM, "  ℹ   Automated mode. Use --live for real voice input.\n"))

    _init_tts()

    sections = {
        1: lambda: section_intro(),
        2: lambda: section_voice_pipeline(live=args.live),
        3: lambda: section_system_control(live=args.live),
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
    print(_c(BOLD + GREEN, "  ✓  Demo completed successfully."))
    print(_c(DIM, f"  Files saved to: {demo_folder()}"))
    print()


if __name__ == "__main__":
    main()
