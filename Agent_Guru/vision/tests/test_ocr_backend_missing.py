"""Without an OCR backend, OCREngine returns no text and says so once, not on every call.

It logged an ERROR with a traceback, image array included, on every text
question, and no OCR backend is a required dependency.
"""

from __future__ import annotations

import builtins

import numpy as np
import pytest

from Agent_Guru.vision import ocr


class RecordingLogger:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def __getattr__(self, level):
        return lambda event, *args, **kwargs: self.calls.append((level, event))


@pytest.fixture
def no_backend(monkeypatch):
    real_import = builtins.__import__

    def without_ocr(name, *args, **kwargs):
        if name in ("paddleocr", "pytesseract"):
            raise ImportError(f"No module named {name!r}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_ocr)
    monkeypatch.setattr(ocr, "_missing_backend_reported", False, raising=False)
    log = RecordingLogger()
    monkeypatch.setattr(ocr, "logger", log)
    return log


async def test_missing_backend_returns_no_text(no_backend):
    result = await ocr.OCREngine().extract(np.full((120, 200, 3), 255, np.uint8))
    assert result.text == ""  # nosec B101


async def test_missing_backend_is_reported_once_as_a_warning(no_backend):
    image = np.full((120, 200, 3), 255, np.uint8)
    for _ in range(3):
        await ocr.OCREngine().extract(image)

    reports = [c for c in no_backend.calls if "OCR backend" in c[1] or "neither" in c[1]]
    assert reports == [("warning", reports[0][1])]  # nosec B101
    assert not [c for c in no_backend.calls if c[0] in ("error", "exception")]  # nosec B101
