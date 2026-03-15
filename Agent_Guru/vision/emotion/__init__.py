"""Emotion recognition module."""

from Agent_Guru.vision.emotion.recognizer import (
    EMOTION_LABELS,
    EmotionRecognizer,
    EmotionResult,
)

__all__ = ["EmotionRecognizer", "EmotionResult", "EMOTION_LABELS"]
