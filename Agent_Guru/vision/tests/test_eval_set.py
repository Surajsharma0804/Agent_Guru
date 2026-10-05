"""The vision evaluation set stays usable: every image loads and every scorer judges answers as intended.

The set runs against a real model outside the suite, so nothing else would
notice a renamed screenshot or a scorer that accepts wrong answers.
"""

from __future__ import annotations

import pytest

from Agent_Guru.vision.eval_set import IMAGES, QUESTIONS


def test_every_question_has_an_image_that_loads():
    for q in QUESTIONS:
        image = IMAGES[q.image]()
        assert image.ndim == 3 and image.shape[2] == 3 and min(image.shape[:2]) >= 200  # nosec B101


def test_drawn_images_are_identical_every_time():
    for name in ("shapes", "triangles", "sign"):
        assert (IMAGES[name]() == IMAGES[name]()).all()  # nosec B101


@pytest.mark.parametrize(("question", "right", "wrong"), [
    ("Is the blue square to the left or to the right of the red circle?", "To the right.", "To the left."),
    ("How many triangles are in the image?", "There are three triangles.", "Two."),
    ("How many views does the main video have?", "104M views", "10M views"),
    ("Is the user signed in?", "No, a Sign in button is shown.", "Yes."),
    ("What time is shown in the taskbar?", "8:21 PM", "10:29:18"),
    ("Which file is highlighted in the file explorer?", "Guru_Demo.py", "README.md"),
    ("Which application is shown?", "Visual Studio Code", "Agent Guru"),
])
def test_scorer_accepts_right_and_rejects_wrong(question, right, wrong):
    q = next(q for q in QUESTIONS if q.question == question)
    assert q.is_correct(right)  # nosec B101
    assert not q.is_correct(wrong)  # nosec B101


def test_wrong_answers_measured_on_gemma3_score_as_wrong():
    # The answers gemma3:4b actually gave on 2026-10-05 for the six misses.
    measured = {
        "Is the blue square to the left or to the right of the red circle?": "To the left.",
        "What colour is the 'Check it out' button?": "Red.",
        "Is the user signed in?": "I cannot determine that from the image",
        "Which application is shown?": "Agent Guru",
        "What time is shown in the taskbar?": "10:29:18",
        "Which file is highlighted in the file explorer?": "README.md",
    }
    for q in QUESTIONS:
        if q.question in measured:
            assert not q.is_correct(measured[q.question]), q.question  # nosec B101
