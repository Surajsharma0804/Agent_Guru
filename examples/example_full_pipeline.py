"""
Complete Voice Pipeline Example

Demonstrates the full voice processing pipeline:
1. Wake word detection
2. Voice Activity Detection (VAD)
3. Speech-to-Text transcription
4. Command interpretation
5. Text-to-Speech synthesis

This example shows how to integrate all components for a complete
voice-driven AI assistant.
"""

import numpy as np
import sounddevice as sd
from guru_speech import (
    GuruSpeechEngine,
    WakeWordDetector,
    VoiceActivityDetector,
    TextToSpeech,
    TTSConfig,
    WakeWordEvent
)


def main():
    print("=" * 60)
    print("GURU SPEECH ENGINE - Full Pipeline Demo")
    print("=" * 60)
    print()
    
    # Initialize components
    print("🔧 Initializing components...")
    
    # 1. Wake Word Detector
    wake_detector = WakeWordDetector(
        wake_words=["guru", "maya"],
        sensitivity=0.7,
        sample_rate=16000
    )
    print("✅ Wake word detector initialized")
    
    # 2. Voice Activity Detector
    vad = VoiceActivityDetector(
        sample_rate=16000,
        aggressiveness=2
    )
    print("✅ VAD initialized")
    
    # 3. Speech Engine
    engine = GuruSpeechEngine(
        enable_noise_reduction=True,
        compute_type="int8",
        beam_size=5
    )
    print("✅ Speech engine initialized")
    
    # 4. Text-to-Speech
    tts_config = TTSConfig(
        speaking_rate=1.0,
        pitch=0.0,
        sample_rate=22050
    )
    tts = TextToSpeech(config=tts_config)
    print("✅ TTS initialized")
    
    print()
    print("=" * 60)
    print("DEMO SCENARIOS")
    print("=" * 60)
    print()
    
    # Scenario 1: Wake Word Detection
    print("📍 Scenario 1: Wake Word Detection")
    print("-" * 60)
    
    # Simulate audio with wake word (in production, this comes from microphone)
    print("Simulating wake word audio...")
    wake_audio = np.random.randn(16000).astype(np.float32) * 0.1  # 1 second of audio
    
    wake_event = wake_detector.process_audio(wake_audio)
    if wake_event:
        print(f"✅ Wake word detected: '{wake_event.wake_word}'")
        print(f"   Confidence: {wake_event.confidence:.2f}")
        print(f"   Timestamp: {wake_event.timestamp}")
    else:
        print("⚠️  No wake word detected (expected with random audio)")
    
    print()
    
    # Scenario 2: Voice Activity Detection
    print("📍 Scenario 2: Voice Activity Detection")
    print("-" * 60)
    
    # Test with silence
    silence = np.zeros(16000, dtype=np.float32)
    vad_result = vad.is_speech(silence)
    print(f"Silence detection:")
    print(f"   Is speech: {vad_result.is_speech}")
    print(f"   Confidence: {vad_result.confidence:.2f}")
    print(f"   Energy: {vad_result.energy:.4f}")
    
    # Test with noise
    noise = np.random.randn(16000).astype(np.float32) * 0.1
    vad_result = vad.is_speech(noise)
    print(f"\nNoise detection:")
    print(f"   Is speech: {vad_result.is_speech}")
    print(f"   Confidence: {vad_result.confidence:.2f}")
    print(f"   Energy: {vad_result.energy:.4f}")
    
    print()
    
    # Scenario 3: Speech Transcription with File
    print("📍 Scenario 3: Speech Transcription")
    print("-" * 60)
    
    # Check if test audio exists
    import os
    test_file = "test_audio/test_sine.wav"
    
    if os.path.exists(test_file):
        print(f"Transcribing: {test_file}")
        result = engine.transcribe_file(test_file)
        print(f"✅ Transcription complete:")
        print(f"   Text: '{result.text}'")
        print(f"   Language: {result.language}")
        print(f"   Confidence: {result.confidence:.2f}")
        print(f"   Duration: {result.duration:.2f}s")
    else:
        print(f"⚠️  Test file not found: {test_file}")
        print("   Skipping transcription demo")
    
    print()
    
    # Scenario 4: Command Interpretation
    print("📍 Scenario 4: Command Interpretation")
    print("-" * 60)
    
    # Simulate transcription result
    from guru_speech.models import TranscriptionResult
    
    transcription = TranscriptionResult(
        text="open youtube",
        language="en",
        confidence=0.95,
        segments=[],
        duration=1.5
    )
    
    command_result = engine.interpret_command(transcription)
    print(f"Input: '{transcription.text}'")
    print(f"✅ Command interpretation:")
    print(f"   Is command: {command_result.is_command}")
    print(f"   Action ID: {command_result.action_id}")
    print(f"   Parameters: {command_result.parameters}")
    print(f"   Confidence: {command_result.confidence:.2f}")
    
    print()
    
    # Scenario 5: Text-to-Speech Synthesis
    print("📍 Scenario 5: Text-to-Speech Synthesis")
    print("-" * 60)
    
    text_to_speak = "Hello! I am Guru, your voice assistant."
    print(f"Synthesizing: '{text_to_speak}'")
    
    speech_audio = tts.synthesize(text_to_speak)
    print(f"✅ Synthesis complete:")
    print(f"   Audio length: {len(speech_audio)} samples")
    print(f"   Duration: {len(speech_audio) / tts_config.sample_rate:.2f}s")
    print(f"   Sample rate: {tts_config.sample_rate} Hz")
    
    # Optionally play the audio
    play_audio = input("\n🔊 Play synthesized audio? (y/n): ").strip().lower()
    if play_audio == 'y':
        print("Playing audio...")
        sd.play(speech_audio, tts_config.sample_rate)
        sd.wait()
        print("✅ Playback complete")
    
    print()
    
    # Scenario 6: Complete Pipeline
    print("📍 Scenario 6: Complete Voice Pipeline")
    print("-" * 60)
    print("This demonstrates the full pipeline:")
    print("  1. Wake word detection")
    print("  2. VAD filtering")
    print("  3. Speech transcription")
    print("  4. Command interpretation")
    print("  5. TTS response")
    print()
    
    # Simulate the pipeline
    print("Step 1: Waiting for wake word...")
    print("   (In production, continuously monitor microphone)")
    print("   Wake word: 'guru' detected!")
    
    print("\nStep 2: Recording user speech...")
    print("   VAD: Speech detected, recording...")
    print("   VAD: Silence detected, stopping recording")
    
    print("\nStep 3: Transcribing speech...")
    print("   Transcription: 'what time is it'")
    
    print("\nStep 4: Interpreting command...")
    print("   Command: TIME_QUERY")
    print("   Action: Get current time")
    
    print("\nStep 5: Generating response...")
    response_text = "The current time is 3:45 PM"
    print(f"   Response: '{response_text}'")
    
    print("\nStep 6: Synthesizing speech...")
    response_audio = tts.synthesize(response_text)
    print(f"   Audio generated: {len(response_audio)} samples")
    
    print("\n✅ Pipeline complete!")
    
    print()
    print("=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    print()
    print("Key Features Demonstrated:")
    print("  ✅ Wake word detection (Porcupine or fallback)")
    print("  ✅ Voice Activity Detection (Silero/WebRTC/fallback)")
    print("  ✅ Noise reduction (noisereduce)")
    print("  ✅ Speech transcription (Whisper)")
    print("  ✅ Command interpretation (pattern matching)")
    print("  ✅ Text-to-Speech (Coqui/pyttsx3/fallback)")
    print()
    print("For production use:")
    print("  - Install optional dependencies: pvporcupine, torch, TTS")
    print("  - Integrate with real-time audio capture")
    print("  - Add custom command patterns")
    print("  - Train custom wake word models")
    print()


if __name__ == "__main__":
    main()
