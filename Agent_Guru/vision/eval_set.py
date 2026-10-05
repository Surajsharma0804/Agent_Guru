"""A fixed set of visual questions with known answers, for comparing vision models.

The VQA pipeline can work perfectly while the model answers wrongly, and the
tests cannot tell the two apart: they run against a fake server. This set is
for the other question, how often the configured model is right. Run it with
scripts/vqa_eval.py against a real Ollama; it is not part of the test suite.

Measured 2026-10-05 with gemma3:4b on Ollama 0.35.1: 10 of 16. The six
misses were the model's (spatial relation, a small button's colour, UI
state, application vs window title, small taskbar text, highlight); asking
at full resolution instead of the 896 px the engine sends did not fix any.

Images are either drawn here, so they are identical on every machine, or
the two screenshots tracked in DEMO_FILES/SCREENSHOOT. Answers are scored by
regular expressions, not exact strings, because a correct model may say
"Three." or "There are 3 triangles."
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

_REPO = Path(__file__).resolve().parents[2]
_SCREENSHOTS = _REPO / "DEMO_FILES" / "SCREENSHOOT"


@dataclass(frozen=True)
class VisualQuestion:
    category: str
    image: str
    question: str
    expected: str
    #: The answer is correct if it matches this (case-insensitive) ...
    correct: str
    #: ... and does not match this, when given ("left" for a "right" answer).
    wrong: str | None = None

    def is_correct(self, answer: str) -> bool:
        text = answer or ""
        if not re.search(self.correct, text, re.IGNORECASE):
            return False
        return not (self.wrong and re.search(self.wrong, text, re.IGNORECASE))


def _shapes() -> np.ndarray:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (640, 400), "white")
    draw = ImageDraw.Draw(img)
    draw.ellipse((60, 120, 220, 280), fill=(220, 20, 20))
    draw.rectangle((400, 120, 560, 280), fill=(20, 40, 220))
    return np.array(img)


def _triangles() -> np.ndarray:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (640, 400), "white")
    draw = ImageDraw.Draw(img)
    for x in (80, 260, 440):
        draw.polygon([(x, 300), (x + 120, 300), (x + 60, 140)], fill=(20, 160, 40))
    return np.array(img)


def _sign() -> np.ndarray:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (640, 400), (240, 240, 240))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arialbd.ttf", 110)
    except OSError:
        # Without Arial, Pillow's built-in font; it takes a size from 10.1
        # on, and on 10.0 the sign is small but still drawn.
        try:
            font = ImageFont.load_default(size=110)
        except TypeError:
            font = ImageFont.load_default()
    draw.text((120, 130), "GATE 42", fill="black", font=font)
    return np.array(img)


def _screenshot(name: str) -> Callable[[], np.ndarray]:
    def load() -> np.ndarray:
        from PIL import Image

        with Image.open(_SCREENSHOTS / name) as img:
            return np.array(img.convert("RGB"))

    return load


IMAGES: dict[str, Callable[[], np.ndarray]] = {
    "shapes": _shapes,
    "triangles": _triangles,
    "sign": _sign,
    "youtube": _screenshot("browser_section4_20260815_202312.png"),
    "vscode": _screenshot("screenshot_20260815_202116.png"),
}

QUESTIONS: tuple[VisualQuestion, ...] = (
    VisualQuestion("colour", "shapes", "What colour is the circle?", "red", r"\bred\b"),
    VisualQuestion("spatial", "shapes", "Is the blue square to the left or to the right of the red circle?",
                   "right", r"\bright\b", r"\bleft\b"),
    VisualQuestion("counting", "triangles", "How many triangles are in the image?", "3", r"\b(3|three)\b"),
    VisualQuestion("colour", "triangles", "What colour are the triangles?", "green", r"\bgreen\b"),
    VisualQuestion("text", "sign", "What does the sign say?", "GATE 42", r"gate\s*42"),
    VisualQuestion("scene", "youtube", "Which website is this?", "YouTube", r"youtube"),
    VisualQuestion("text", "youtube", "What has been typed in the search box?", "chak de india song", r"chak de india"),
    VisualQuestion("text", "youtube", "What error message is shown on the video player?",
                   "Something went wrong. Refresh or try again later.", r"something went wrong"),
    VisualQuestion("text", "youtube", "How many views does the main video have?", "104M", r"104\s*(m|million)"),
    VisualQuestion("colour", "youtube", "What colour is the 'Check it out' button?", "black", r"\bblack\b"),
    VisualQuestion("scene", "youtube", "Is the user signed in?", "no (a Sign in button is shown)",
                   r"\bno\b|not signed|sign(ed)? out|sign in button", r"\byes\b"),
    VisualQuestion("scene", "vscode", "Which application is shown?", "Visual Studio Code",
                   r"visual studio code|vs ?code"),
    VisualQuestion("text", "vscode", "What time is shown in the taskbar?", "8:21 PM", r"8:21"),
    VisualQuestion("text", "vscode", "Which file is highlighted in the file explorer?", "Guru_Demo.py", r"guru_demo"),
    VisualQuestion("text", "vscode", "What error is shown in the terminal?", "ConnectionError: Failed to connect to Ollama",
                   r"connection ?error|failed to connect"),
    VisualQuestion("spatial", "vscode", "Which panel is on the right side of the window?", "Chat / Sessions",
                   r"\bchat\b|session"),
)
