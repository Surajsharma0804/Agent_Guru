"""
Advanced Features Example

Demonstrates all advanced features:
1. Performance metrics
2. Voice biometric authentication
3. Streaming transcription
4. Complete voice assistant pipeline
"""

import numpy as np
import time
from guru_speech import (
    GuruSpeechEngine,
    WakeWordDetector,
    VoiceActivityDetector,
    TextToSpeech,
    VoiceBiometricAuthenticator,
    StreamingTranscriber,
    StreamingConfig,
    get_monitor,
    TTSConfig
)


def demo_performance_metrics():
    """Demonstrate performance monitoring."""
    print("\n" + "=" * 60)
    print("DEMO 1: Performance Metrics")
    print("=" * 60)
    
    # Get global monitor
    monitor = get_monitor()
    
    # Initialize engine
    engine = GuruSpeechEngine()
    
    # Simulate some operations
    print("\nPerforming operations...")
    
    # Transcription
    start = monitor.start_operation("transcription")
    time.sleep(0.1)  # Simulate work
    monitor.end_operation("transcription", start, success=True)
    
    # Record transcription metrics
    monitor.record_transcription(
        duration_sec=2.5,
        processing_time_ms=120.0,
        language="en",
        word_count=15
    )
    
    # Wake word detection
    start = monitor.start_operation("wake_word")
    time.sleep(0.05)
    monitor.end_operation("wake_word", start, success=True)
    
    monitor.record_wake_word_detection(
        wake_word="guru",
        latency_ms=45.0,
        is_false_positive=False
    )
    
    # TTS synthesis
    start = monitor.start_operation("tts")
    time.sleep(0.08)
    monitor.end_operation("tts", start, success=True)
    
    monitor.record_tts_synthesis(
        text_length=50,
        synthesis_time_ms=80.0
    )
    
    # Print metrics summary
    monitor.print_summary()


def demo_biometric_authentication():
    """Demonstrate voice biometric authentication."""
    print("\n" + "=" * 60)
    print("DEMO 2: Voice Biometric Authentication")
    print("=" * 60)
    
    # Initialize authenticator
    authenticator = VoiceBiometricAuthenticator(
        threshold=0.75,
        embedding_size=256
    )
    
    print("\n1. Enrolling users...")
    
    # Simulate enrollment for two users
    # In production, these would be real voice samples
    user1_audio = np.random.randn(16000).astype(np.float32) * 0.1
    user2_audio = np.random.randn(16000).astype(np.float32) * 0.2
    
    authenticator.enroll("user_alice", user1_audio, sample_rate=16000)
    authenticator.enroll("user_bob", user2_audio, sample_rate=16000)
    
    print(f"✅ Enrolled users: {authenticator.list_users()}")
    
    print("\n2. Authenticating (identification)...")
    
    # Try to identify a speaker
    test_audio = np.random.randn(16000).astype(np.float32) * 0.1
    result = authenticator.authenticate(test_audio, sample_rate=16000)
    
    print(f"   Authenticated: {result.authenticated}")
    print(f"   User ID: {result.user_id}")
    print(f"   Confidence: {result.confidence:.2f}")
    print(f"   Similarity: {result.similarity_score:.2f}")
    
    print("\n3. Authenticating (verification)...")
    
    # Verify against specific user
    result = authenticator.authenticate(
        test_audio,
        sample_rate=16000,
        user_id="user_alice"
    )
    
    print(f"   Verified as user_alice: {result.authenticated}")
    print(f"   Confidence: {result.confidence:.2f}")
    
    print("\n4. Profile management...")
    
    # Get profile info
    profile = authenticator.get_profile("user_alice")
    if profile:
        print(f"   User: {profile.user_id}")
        print(f"   Enrollment count: {profile.enrollment_count}")
        print(f"   Created: {profile.created_at}")
    
    # Save profiles
    authenticator.save_profiles("voice_profiles.pkl")
    print("✅ Profiles saved to voice_profiles.pkl")


def demo_streaming_transcription():
    """Demonstrate streaming transcription."""
    print("\n" + "=" * 60)
    print("DEMO 3: Streaming Transcription")
    print("=" * 60)
    
    # Initialize engine
    engine = GuruSpeechEngine()
    
    # Callback for transcription results
    def on_transcription(result):
        print(f"📝 Transcribed: '{result.text}' (confidence: {result.confidence:.2f})")
    
    # Configure streaming
    config = StreamingConfig(
        chunk_duration_ms=1000,
        sample_rate=16000,
        buffer_size=5,
        enable_vad=True
    )
    
    print("\nStarting streaming transcription...")
    print("(Simulating audio stream with synthetic data)")
    
    # Create streaming transcriber
    transcriber = StreamingTranscriber(
        engine=engine,
        config=config,
        callback=on_transcription
    )
    
    transcriber.start()
    
    # Simulate feeding audio chunks
    for i in range(5):
        # Generate synthetic audio chunk (1 second)
        audio_chunk = np.random.randn(16000).astype(np.float32) * 0.1
        
        try:
            transcriber.feed_audio(audio_chunk)
            print(f"   Fed chunk {i+1}/5")
            time.sleep(0.5)
        except Exception as e:
            print(f"   Error: {e}")
    
    # Stop streaming
    transcriber.stop()
    print("✅ Streaming stopped")


def demo_complete_voice_assistant():
    """Demonstrate complete voice assistant pipeline."""
    print("\n" + "=" * 60)
    print("DEMO 4: Complete Voice Assistant Pipeline")
    print("=" * 60)
    
    print("\nInitializing all components...")
    
    # 1. Wake word detector
    wake_detector = WakeWordDetector(
        wake_words=["guru", "maya"],
        sensitivity=0.7
    )
    print("✅ Wake word detector ready")
    
    # 2. VAD
    vad = VoiceActivityDetector(sample_rate=16000)
    print("✅ VAD ready")
    
    # 3. Speech engine
    engine = GuruSpeechEngine(enable_noise_reduction=True)
    print("✅ Speech engine ready")
    
    # 4. TTS
    tts = TextToSpeech(TTSConfig(speaking_rate=1.0))
    print("✅ TTS ready")
    
    # 5. Biometric authenticator
    authenticator = VoiceBiometricAuthenticator()
    print("✅ Biometric authenticator ready")
    
    print("\n" + "-" * 60)
    print("Simulating voice assistant interaction...")
    print("-" * 60)
    
    # Simulate the pipeline
    print("\n[1] Listening for wake word...")
    wake_audio = np.random.randn(16000).astype(np.float32) * 0.1
    wake_event = wake_detector.process_audio(wake_audio)
    
    if wake_event:
        print(f"    ✅ Wake word detected: '{wake_event.wake_word}'")
    else:
        print("    ⚠️  No wake word (using synthetic audio)")
        print("    Simulating wake word detection...")
    
    print("\n[2] Checking for speech with VAD...")
    speech_audio = np.random.randn(48000).astype(np.float32) * 0.1
    vad_result = vad.is_speech(speech_audio)
    print(f"    Speech detected: {vad_result.is_speech}")
    print(f"    Confidence: {vad_result.confidence:.2f}")
    
    if vad_result.is_speech:
        print("\n[3] Authenticating speaker...")
        # In production, use real voice sample
        auth_result = authenticator.authenticate(speech_audio[:16000])
        print(f"    Authenticated: {auth_result.authenticated}")
        if auth_result.user_id:
            print(f"    User: {auth_result.user_id}")
        
        print("\n[4] Transcribing speech...")
        print("    (Skipping actual transcription with synthetic audio)")
        print("    Simulated transcription: 'what time is it'")
        
        print("\n[5] Interpreting command...")
        from guru_speech.models import TranscriptionResult
        transcription = TranscriptionResult(
            text="what time is it",
            language="en",
            confidence=0.95,
            segments=[],
            duration=2.0
        )
        
        command = engine.interpret_command(transcription)
        print(f"    Is command: {command.is_command}")
        print(f"    Action: {command.action_id}")
        print(f"    Raw text: '{command.raw_text}'")
        
        print("\n[6] Generating response...")
        response_text = "The current time is 3:45 PM"
        print(f"    Response: '{response_text}'")
        
        print("\n[7] Synthesizing speech...")
        response_audio = tts.synthesize(response_text)
        print(f"    Audio generated: {len(response_audio)} samples")
        print(f"    Duration: {len(response_audio) / 22050:.2f}s")
        
        print("\n✅ Pipeline complete!")
    else:
        print("    No speech detected, waiting...")
    
    # Show final metrics
    print("\n" + "-" * 60)
    print("Performance Summary:")
    print("-" * 60)
    monitor = get_monitor()
    metrics = monitor.get_all_metrics()
    
    print(f"System uptime: {metrics['system']['uptime_seconds']:.1f}s")
    print(f"Memory usage: {metrics['system']['memory_usage_mb']:.1f}MB")
    
    if metrics['components']:
        print("\nComponent calls:")
        for name, m in metrics['components'].items():
            print(f"  {name}: {m['total_calls']} calls, avg {m['avg_time_ms']:.2f}ms")


def main():
    """Run all demos."""
    print("╔════════════════════════════════════════════════════════════╗")
    print("║     GURU SPEECH ENGINE - Advanced Features Demo           ║")
    print("╚════════════════════════════════════════════════════════════╝")
    
    try:
        # Demo 1: Performance metrics
        demo_performance_metrics()
        
        # Demo 2: Biometric authentication
        demo_biometric_authentication()
        
        # Demo 3: Streaming transcription
        demo_streaming_transcription()
        
        # Demo 4: Complete pipeline
        demo_complete_voice_assistant()
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    print("\nAll advanced features demonstrated:")
    print("  ✅ Performance metrics and monitoring")
    print("  ✅ Voice biometric authentication")
    print("  ✅ Streaming transcription")
    print("  ✅ Complete voice assistant pipeline")
    print("\nFor production use:")
    print("  - Install optional dependencies for best quality")
    print("  - Use real audio samples for biometric enrollment")
    print("  - Integrate with real-time audio capture")
    print("  - Add custom command patterns")
    print("  - Connect to your LLM backend")
    print()


if __name__ == "__main__":
    main()
