#!/usr/bin/env python3
"""
GURU AI Assistant - Production Launcher
Voice-activated AI assistant with local TTS and LLM integration

THREAD SAFETY ARCHITECTURE:
- Voice interface runs in background daemon thread
- Voice callbacks execute in background thread context
- Qt widgets MUST only be accessed from main thread
- Solution: ThreadSafeBridge with Qt signals/slots (QueuedConnection)
- All cross-thread communication goes through the bridge
- TTS service is thread-safe (internal queue + dedicated thread)

SIGNAL FLOW:
Background Thread → Bridge Signal → Qt Event Loop → Main Thread → Widget Update

FIRST-RUN DETECTION:
- Checks for user configuration file
- If not found, launches setup wizard
- Setup wizard creates user profile and preferences
- After setup, launches main application
"""

import sys
from pathlib import Path

# Setup Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

print("=" * 70)
print("GURU AI ASSISTANT")
print("=" * 70)

# Check for first-time setup and run wizard if needed
try:
    from config.first_run_detector import run_setup_wizard_if_needed
    
    print("[INFO] Checking first-time setup status...")
    setup_completed = run_setup_wizard_if_needed()
    
    if setup_completed:
        print("[INFO] Setup wizard completed successfully")
        # Reload configuration after setup
        from config.user_config import get_config_manager
        config_manager = get_config_manager()
        profile = config_manager.get_profile()
        
        print(f"\n[WELCOME] Hello, {profile.display_name}!")
        print("=" * 70 + "\n")
    else:
        # Check if user has existing profile
        print("[INFO] Setup wizard not needed or cancelled")
        from config.user_config import get_config_manager
        config_manager = get_config_manager()
        
        if not config_manager.is_first_time_setup():
            profile = config_manager.get_profile()
            print(f"\n[WELCOME BACK] {profile.display_name}")
            print("=" * 70 + "\n")
        else:
            # Setup was cancelled or failed
            print("\n[ERROR] Setup required but not completed. Exiting...")
            sys.exit(1)

except Exception as e:
    print(f"[ERROR] Configuration check failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("=" * 70)
print("INITIALIZING GURU COMPONENTS")
print("=" * 70)

# Import Qt
try:
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication
    print("[OK] PyQt6")
except ImportError as e:
    print(f"[ERROR] PyQt6 required: pip install PyQt6")
    sys.exit(1)

# Import TTS
try:
    from gui.tts_service import TTSPriority, get_tts_service
    tts = get_tts_service()
    print("[OK] TTS Service")
except Exception as e:
    print(f"[ERROR] TTS: {e}")
    sys.exit(1)

# Import Voice Interface
try:
    from gui.voice_interface import VoiceCommand, create_voice_interface
    voice = create_voice_interface(wake_word="hey guru")
    print("[OK] Voice Interface")
except Exception as e:
    print(f"[ERROR] Voice: {e}")
    sys.exit(1)

# Import Conversation Manager
try:
    from gui.conversation_manager import create_conversation_manager
    conversation = create_conversation_manager()
    print("[OK] Conversation Manager")
except Exception as e:
    print(f"[ERROR] Conversation: {e}")
    sys.exit(1)

# Import Avatar
try:
    from gui.avatar_window import AvatarState, create_guru_window
    print("[OK] Avatar Window")
except Exception as e:
    print(f"[ERROR] Avatar: {e}")
    sys.exit(1)

# Import Thread-Safe Bridge
try:
    from gui.thread_safe_bridge import get_thread_safe_bridge
    bridge = get_thread_safe_bridge()
    print("[OK] Thread-Safe Bridge")
except Exception as e:
    print(f"[ERROR] Bridge: {e}")
    sys.exit(1)

print("\n" + "=" * 70)
print("Starting GURU...")
print("=" * 70 + "\n")

# Create Qt application
app = QApplication(sys.argv)
app.setApplicationName("GURU")

# Create avatar
avatar = create_guru_window()
if not avatar:
    print("[ERROR] Failed to create avatar")
    sys.exit(1)

# Connect bridge to avatar and voice
bridge.connect_avatar(avatar)
bridge.connect_voice(voice)
print("[OK] Bridge connected to components")

# Voice command handler
# CRITICAL: This runs in voice interface background thread
# All Qt operations go through bridge signals (thread-safe)
def on_voice_command(cmd: VoiceCommand):
    print(f"\n[USER] {cmd.text}")
    
    # Set avatar to thinking state (via bridge signal)
    bridge.set_avatar_state.emit(AvatarState.THINKING)
    
    # Process input (safe in background thread - no Qt operations)
    response, intent, emotion = conversation.process_input(cmd.text)
    
    print(f"[GURU] {response}")
    
    # Set avatar to speaking state (via bridge signal)
    bridge.set_avatar_state.emit(AvatarState.SPEAKING)
    
    # Speak response (via bridge signal for consistency, though TTS is thread-safe)
    bridge.speak_text.emit(response, False)
    
    # Schedule return to idle state after speech completes
    # Estimate speech duration: ~50ms per character
    speech_duration_ms = len(response) * 50
    
    # Use QTimer in main thread by scheduling through bridge
    def schedule_idle():
        import time
        time.sleep(speech_duration_ms / 1000.0)
        bridge.set_avatar_state.emit(AvatarState.IDLE)
    
    import threading
    threading.Thread(target=schedule_idle, daemon=True).start()

voice.set_command_callback(on_voice_command)

# Start
avatar.show()
voice.start_listening()

greeting = "Hello! I'm GURU. Say 'Hey GURU' to talk to me!"
tts.speak(greeting, priority=TTSPriority.NORMAL)
print(f"\n[GURU] {greeting}\n")

print("=" * 70)
print("GURU IS ACTIVE - Say 'Hey GURU' to start")
print("=" * 70 + "\n")

# Run
try:
    sys.exit(app.exec())
except KeyboardInterrupt:
    print("\nShutting down...")
    voice.stop_listening()
    tts.stop()
    sys.exit(0)
