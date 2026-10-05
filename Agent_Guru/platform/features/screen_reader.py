"""Screen reading for Agent Guru - 'what's on my screen?'.

This is one of the flagship features of Gemini Live and Siri iOS 26.
The user can ask 'what's on my screen?' or 'summarize what I'm looking at'
and the assistant reads the screen content and answers.

We use two approaches:
1. Windows UIA (UI Automation) - reads text from UI elements directly.
   Fast, accurate, no OCR needed. Works on most Windows apps.
2. Screenshot + pytesseract OCR - fallback for apps that don't expose
   text via UIA (games, PDFs, images).

The extracted text is injected into the LLM prompt so the assistant
can answer questions about it.

answer_screen_question() answers about what the screen shows, not only its
text: it captures the screen through the platform controller and asks the
local vision model (vision.vqa.VQAEngine), with the UI Automation text as
grounding. Before it, "describe my screen" and "what am I looking at" were
classified as screen_read, which skips the LLM, and nothing handled them,
so the assistant replied "Done."; questions about colours, layout or images
could not be answered at all from extracted text.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import tempfile
import threading
from typing import Any

logger = logging.getLogger(__name__)


def read_screen_text(max_chars: int = 2000) -> str | None:
    """Extract visible text from the current screen.

    Tries Windows UI Automation first (fast, accurate), then falls back
    to screenshot + OCR (slower but works on anything).

    Args:
        max_chars: Maximum characters to return (keeps LLM prompt manageable).

    Returns:
        Extracted text, or None if extraction failed.

    """
    # Try Windows UI Automation first - reads text from focused window
    text = _read_via_uia(max_chars)
    if text:
        return text

    return _read_via_ocr(max_chars)


def _read_via_uia(max_chars: int) -> str | None:
    """Read text from the focused window using Windows UI Automation."""
    try:
        import subprocess  # nosec B404

        # Use PowerShell to get the focused window title and text via UIA
        # This is the same approach Windows Narrator uses
        ps_script = """
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::RootElement
$focused = [System.Windows.Automation.AutomationElement]::FocusedElement
if ($focused -eq $null) { exit }
$condition = [System.Windows.Automation.Condition]::TrueCondition
$elements = $focused.FindAll([System.Windows.Automation.TreeScope]::Subtree, $condition)
$texts = @()
foreach ($el in $elements) {
    try {
        $name = $el.GetCurrentPropertyValue([System.Windows.Automation.AutomationElement]::NameProperty)
        if ($name -and $name.Length -gt 0) { $texts += $name }
    } catch {}
}
$texts | Select-Object -First 100 | Out-String
"""
        result = subprocess.run(  # nosec B603 B607  # noqa: S603
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        text = result.stdout.strip()
        if text and len(text) > 20:
            logger.debug("UIA screen read: %d chars", len(text))
            return text[:max_chars]
    except Exception as exc:
        logger.debug("UIA screen read failed: %s", exc)
    return None


def _read_via_ocr(max_chars: int) -> str | None:
    """Take a screenshot and extract text via OCR.

    Tries in order:
    1. Windows built-in OCR (WinRT) - no install needed, works on Win10/11
    2. pytesseract - needs Tesseract installed, auto-detects path
    3. easyocr - GPU-accelerated, no install needed beyond pip
    """
    try:
        import io

        import pyautogui

        screenshot = pyautogui.screenshot()

        # 1. Windows built-in OCR (WinRT) - best option, no extra install
        try:
            import asyncio as _asyncio

            buf = io.BytesIO()
            screenshot.save(buf, format="PNG")
            text = _asyncio.run(_winrt_ocr(buf.getvalue()))
            if text and len(text) > 10:
                logger.debug("WinRT OCR: %d chars", len(text))
                return text[:max_chars]
        except Exception:
            logger.exception("Operation failed")
        # 2. pytesseract - auto-detect Tesseract path on Windows
        try:
            # Auto-detect Tesseract on Windows (common install locations)
            import os

            import pytesseract  # type: ignore[import]

            tesseract_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                os.path.join(
                    os.environ.get("LOCALAPPDATA", ""),
                    "Programs",
                    "Tesseract-OCR",
                    "tesseract.exe",
                ),
                os.path.join(os.environ.get("PROGRAMFILES", ""), "Tesseract-OCR", "tesseract.exe"),
            ]
            for tp in tesseract_paths:
                if os.path.exists(tp):
                    pytesseract.pytesseract.tesseract_cmd = tp
                    break

            text = pytesseract.image_to_string(screenshot, lang="eng")
            text = text.strip()
            if text and len(text) > 10:
                logger.debug("Tesseract OCR: %d chars", len(text))
                return text[:max_chars]
        except ImportError as exc:
            logger.exception("Operation failed")
            logger.debug("Tesseract OCR failed: %s", exc)
        # 3. easyocr - works without any system install
        try:
            import easyocr  # type: ignore[import]
            import numpy as np

            reader = easyocr.Reader(["en"], gpu=False, verbose=False)
            img_array = np.array(screenshot)
            results = reader.readtext(img_array, detail=0)
            text = " ".join(results).strip()
            if text:
                logger.debug("EasyOCR: %d chars", len(text))
                return text[:max_chars]
        except ImportError:
            logger.exception("Operation failed")
    except Exception as exc:
        logger.debug("OCR screen read failed: %s", exc)
    return None


async def _winrt_ocr(image_bytes: bytes) -> str:
    """Use Windows Runtime OCR engine (built into Windows 10/11)."""
    try:
        from winrt.windows.graphics import imaging  # type: ignore[import]
        from winrt.windows.media import ocr  # type: ignore[import]
        from winrt.windows.storage import streams  # type: ignore[import]

        engine = ocr.OcrEngine.try_create_from_user_profile_languages()
        if engine is None:
            return ""

        # Convert bytes to IRandomAccessStream
        stream = streams.InMemoryRandomAccessStream()
        writer = streams.DataWriter(stream)
        writer.write_bytes(list(image_bytes))
        await writer.store_async()
        stream.seek(0)

        decoder = await imaging.BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
        result = await engine.recognize_async(bitmap)
        return result.text or ""
    except Exception:
        return ""


#: Questions about what is on the screen. The intent recognizer's screen_read
#: rule uses this same pattern, so the two cannot drift apart: before, "read
#: the text on my screen" became a send-message intent and "what is on my
#: screen" a general question the LLM answered without seeing anything.
SCREEN_QUESTION_PATTERN = re.compile(
    r"\b(what.?s on (my|the) screen|what is on (my|the) screen|read my screen|"
    r"what do you see|summarize my screen|what.?s open|what is open|"
    r"what am i looking at|describe (my|the) screen|read this|"
    r"what does this say|translate this|explain this|"
    r"read (the |all the )?(text|words) on (my|the) screen|what does (my|the) screen say)\b"
    r"|\b(what|which|who|how many|is there|are there|tell me|read|describe|summarize)\b"
    r"[^.?!]{0,60}\b(on|in) (my|the) (screen|display|monitor)\b",
    re.IGNORECASE,
)


def is_screen_read_command(transcript: str) -> bool:
    """Return True if the user is asking about screen content."""
    return bool(SCREEN_QUESTION_PATTERN.search(transcript or ""))


_engine: Any = None
_engine_lock = threading.Lock()


def _vqa_engine() -> Any:
    """The process-wide VQAEngine: one HTTP client, reused for every question."""
    global _engine
    with _engine_lock:
        if _engine is None:
            from Agent_Guru.vision.vqa import VQAEngine

            _engine = VQAEngine(platform="desktop")
        return _engine


def _capture_screen(controller: Any) -> Any:
    """Screenshot through the platform controller, as an RGB array.

    The image is written to a private temporary file (the controller saves to
    a path) and deleted as soon as it is read: a screenshot may hold anything
    the user has open.
    """
    import numpy as np
    from PIL import Image

    take = getattr(controller, "take_screenshot", None)
    if take is None:
        msg = "no screen capture is available on this platform"
        raise RuntimeError(msg)
    fd, path = tempfile.mkstemp(prefix="guru_screen_", suffix=".png")
    os.close(fd)
    try:
        outcome = take(save_path=path)
        if getattr(outcome, "success", True) is False:
            msg = f"screen capture failed: {getattr(outcome, 'message', '')}"
            raise RuntimeError(msg)
        with Image.open(path) as img:
            return np.array(img.convert("RGB"))
    finally:
        try:
            os.remove(path)
        except OSError:
            logger.warning("Could not delete the temporary screenshot %s", path)


def _spoken_failure(error: str) -> str:
    if "timed out" in error:
        return "I couldn't look at your screen: the vision model took too long."
    if "Connection" in error:
        return "I couldn't look at your screen: the local vision model isn't running."
    return "I couldn't look at your screen just now."


async def answer_screen_question(
    question: str,
    controller: Any,
    *,
    engine: Any = None,
    read_text: Any = None,
) -> str:
    """Answer a spoken question about the screen; return the sentence to speak.

    Args:
        question: What the user asked.
        controller: Platform controller with take_screenshot(save_path=...).
        engine: VQAEngine to use; the shared one if None.
        read_text: Callable returning the screen's text or None; UI
            Automation if None (Windows only, None elsewhere).

    Failures are said as failures ("the local vision model isn't running"),
    never as "I cannot determine that from the image", which means the model
    looked and could not tell.
    """
    try:
        image = await asyncio.to_thread(_capture_screen, controller)
    except Exception as exc:
        logger.warning("Screen question: capture failed: %s", exc)
        return "I couldn't capture your screen."
    reader = read_text or _read_via_uia
    try:
        screen_text = await asyncio.to_thread(reader, 1500)
    except Exception:
        logger.debug("Screen question: reading screen text failed", exc_info=True)
        screen_text = None
    result = await (engine or _vqa_engine()).answer(image, question, context_text=screen_text)
    if result.error:
        logger.warning("Screen question not answered: %s", result.error)
        return _spoken_failure(result.error)
    return result.answer
