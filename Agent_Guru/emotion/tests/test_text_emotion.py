"""Emotion read from what the user said: ordinary questions stay neutral, real feelings are still found.

The keywords used to be matched as plain substrings, so "ugh" fired inside
"roughly" and "rage" inside "average": "And roughly how many people live
there?" was answered as if the user were frustrated, and with the real model
5 of 5 answers to it repeated the frustration guidance instead of giving the
number. The emotion also sits in the system prompt, so each misread changed
the prompt and cost Ollama its reuse of the previous turn.

A text is taken as emotional the way the voice pipeline takes it
(IntegrationOrchestrator._detect_emotion): not neutral, confidence over 0.4.
"""

from __future__ import annotations

import pytest

from Agent_Guru.emotion.detector import EmotionDetector


def _emotion(text: str) -> str:
    state = EmotionDetector().detect(text=text)
    return state.emotion if state.confidence > 0.4 and state.emotion != "neutral" else "neutral"


@pytest.mark.parametrize(
    "text",
    [
        "And roughly how many people live there?",
        "How many people live there?",
        "What time does the store open?",
        "What is the capital of France?",
        "How far is Delhi from Mumbai?",
        "What does this error mean?",
        # A keyword inside a longer word: each of these was given an emotion.
        "Is there enough storage on my laptop?",
        "Can you walk me through the setup?",
        "Even though it rained, we went out.",
        "My daughter wants to learn the guitar.",
        "I bought a new phone today.",
        "Tell me a joke that makes me laugh.",
        "What is the average temperature in Delhi in May?",
        "Where is the nearest garage?",
        "What does the insurance coverage include?",
        "My grandfather retired last year.",
    ],
)
def test_an_ordinary_sentence_is_neutral(text):
    assert _emotion(text) == "neutral"  # nosec B101


@pytest.mark.parametrize(
    ("text", "emotion"),
    [
        ("I'm so frustrated, nothing works today!", "frustrated"),
        ("Ugh, this keeps failing on me.", "frustrated"),
        ("Why won't this stupid thing work, it's useless.", "frustrated"),
        ("I'm so angry right now.", "angry"),
        ("I am furious with my landlord.", "angry"),
        ("He was enraged when he heard.", "angry"),
        ("I feel sad and I want to cry.", "sad"),
        ("That news was really upsetting.", "sad"),
        ("I'm so excited for the trip!", "excited"),
        ("Omg, I can't wait!", "excited"),
        ("I'm so happy today!", "happy"),
        ("I'm really anxious about my exam tomorrow.", "fearful"),
        ("I'm scared and freaking out.", "fearful"),
        ("I'm exhausted after work.", "tired"),
        ("I don't understand this at all.", "confused"),
        ("I nailed my interview!", "proud"),
    ],
)
def test_a_felt_emotion_is_still_found(text, emotion):
    assert _emotion(text) == emotion  # nosec B101
