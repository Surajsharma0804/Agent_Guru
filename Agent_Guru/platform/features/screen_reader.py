"""Screen reading for Agent Guru — 'what's on my screen?'

This is one of the flagship features of Gemini Live and Siri iOS 26.
The user can ask 'what's on my screen?' or 'summarize what I'm looking at'
and the assistant reads the screen content and answers.

We use two approaches:
1. Windows UIA (UI Automation) — reads text from UI elements directly.
   Fast, accurate, no OCR needed. Works on most Windows apps.
2. Screenshot + pytesseract OCR — fallback for apps that don't expose
   text via UIA (games, PDFs, images).

The extracted text is injected into the LLM prompt so the assistant
can answer questions about it.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def read_screen_text(max_chars: int = 2000) -> Optional[str]:
    """Extract visible text from the current screen.

    Tries Windows UI Automation first (fast, accurate), then falls back
    to screenshot + OCR (slower but works on anything).

    Args:
        max_chars: Maximum characters to return (keeps LLM prompt manageable).

    Returns:
        Extracted text, or None if extraction failed.
    """
    # Try Windows UI Automation first — reads text from focused window
    text = _read_via_uia(max_chars)
    if text:
        return text

    # Fallback: screenshot + OCR
    text = _read_via_ocr(max_chars)
    return text


def _read_via_uia(max_chars: int) -> Optional[str]:
    """Read text from the focused window using Windows UI Automation."""
    try:
        import pyautogui
        import subprocess

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
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True, text=True, timeout=5
        )
        text = result.stdout.strip()
        if text and len(text) > 20:
            logger.debug("UIA screen read: %d chars", len(text))
            return text[:max_chars]
    except Exception as exc:
        logger.debug("UIA screen read failed: %s", exc)
    return None


def _read_via_ocr(max_chars: int) -> Optional[str]:
    """Take a screenshot and extract text via OCR."""
    try:
        import pyautogui
        import io

        # Take screenshot
        screenshot = pyautogui.screenshot()

        # Try pytesseract first (best quality)
        try:
            import pytesseract  # type: ignore[import]
            text = pytesseract.image_to_string(screenshot, lang="eng")
            text = text.strip()
            if text and len(text) > 10:
                logger.debug("Tesseract OCR: %d chars", len(text))
                return text[:max_chars]
        except ImportError:
            pass

        # Try easyocr as fallback
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
            pass

        # Try Windows built-in OCR via WinRT
        try:
            import asyncio
            import winrt.windows.media.ocr as ocr  # type: ignore[import]
            import winrt.windows.graphics.imaging as imaging  # type: ignore[import]
            import winrt.windows.storage.streams as streams  # type: ignore[import]

            buf = io.BytesIO()
            screenshot.save(buf, format="PNG")
            buf.seek(0)
            # WinRT OCR is async — run in a new event loop
            text = asyncio.run(_winrt_ocr(buf.read()))
            if text:
                return text[:max_chars]
        except Exception:
            pass

    except Exception as exc:
        logger.debug("OCR screen read failed: %s", exc)

    return None


async def _winrt_ocr(image_bytes: bytes) -> str:
    """Use Windows Runtime OCR engine (built into Windows 10/11)."""
    try:
        import winrt.windows.media.ocr as ocr  # type: ignore[import]
        import winrt.windows.graphics.imaging as imaging  # type: ignore[import]
        import winrt.windows.storage.streams as streams  # type: ignore[import]

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


def is_screen_read_command(transcript: str) -> bool:
    """Return True if the user is asking about screen content."""
    import re
    return bool(re.search(
        r"\b(what.?s on my screen|what is on my screen|"
        r"read my screen|what do you see|"
        r"what.?s on the screen|what is on the screen|"
        r"summarize my screen|what.?s open|what is open|"
        r"what am i looking at|describe my screen|read this|"
        r"what does this say|translate this|explain this)\b",
        transcript, re.I,
    ))
