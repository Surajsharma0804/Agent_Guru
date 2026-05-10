"""Example: Emotion-Aware Responses.

Demonstrates detecting user emotion and adapting the response accordingly.
"""

import asyncio

import numpy as np

from Agent_Guru.speech.engine import SpeechEngine
from Agent_Guru.speech.models import EmotionType, PersonalityType

EMOTION_RESPONSES = {
    EmotionType.HAPPY: ("Great to hear you're in a good mood!", EmotionType.HAPPY),
    EmotionType.SAD: ("I'm here for you. How can I help?", EmotionType.NEUTRAL),
    EmotionType.ANGRY: ("Let me help resolve that for you.", EmotionType.NEUTRAL),
    EmotionType.NEUTRAL: ("How can I assist you today?", EmotionType.NEUTRAL),
    EmotionType.SURPRISED: ("That's quite something! Tell me more.", EmotionType.HAPPY),
    EmotionType.FEARFUL: ("Don't worry, I've got you covered.", EmotionType.NEUTRAL),
    EmotionType.DISGUSTED: ("I understand. Let me find a better option.", EmotionType.NEUTRAL),
}


async def main() -> None:
    engine = SpeechEngine()
    engine.initialize()

    audio = np.random.randn(16000).astype(np.float32) * 0.1

    result = await engine.process_voice_input(audio, personality=PersonalityType.MAYA)
    detected_emotion = result.emotion.primary_emotion

    response_text, response_emotion = EMOTION_RESPONSES.get(
        detected_emotion,
        ("How can I help?", EmotionType.NEUTRAL),
    )
    engine.synthesize_response(
        response_text,
        PersonalityType.MAYA,
        response_emotion,
    )

    engine.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
