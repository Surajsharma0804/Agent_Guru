"""
Example: Multi-Turn Conversation with Context

Demonstrates maintaining conversation context across multiple turns.
"""

import asyncio
import numpy as np
from Agent_Guru.speech.engine import SpeechEngine
from Agent_Guru.speech.models import PersonalityType, EmotionType


async def main():
    engine = SpeechEngine()
    engine.initialize()

    audio = np.random.randn(16000).astype(np.float32) * 0.1

    print("=== Multi-Turn Conversation ===\n")

    for turn in range(3):
        print(f"Turn {turn + 1}:")
        result = await engine.process_voice_input(audio, personality=PersonalityType.GURU)
        print(f"  User: {result.transcription.text or '(audio input)'}")
        print(f"  Emotion: {result.emotion.primary_emotion.value}")
        print(f"  Context ID: {result.context_id}")
        print(f"  Processing time: {result.processing_time_ms:.1f}ms")

        response = engine.synthesize_response(
            f"Understood. This is turn {turn + 1} of our conversation.",
            PersonalityType.GURU,
            EmotionType.NEUTRAL,
        )
        print(f"  Response audio: {response.shape[0]} samples")
        print()

    engine.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
