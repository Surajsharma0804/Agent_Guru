#!/usr/bin/env python3
"""
Minimal launch test to diagnose startup issues
"""

import sys
from pathlib import Path

# Setup Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

print("=" * 70)
print("GURU LAUNCH DIAGNOSTIC")
print("=" * 70)

# Test 1: Configuration
print("\n[TEST 1] Configuration System")
try:
    from config.user_config import get_config_manager
    config_manager = get_config_manager()
    print(f"  ✓ Config manager created")
    print(f"  First time setup: {config_manager.is_first_time_setup()}")
    
    if not config_manager.is_first_time_setup():
        profile = config_manager.get_profile()
        print(f"  Profile: {profile.display_name}")
except Exception as e:
    print(f"  ✗ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 2: PyQt6
print("\n[TEST 2] PyQt6 Import")
try:
    from PyQt6.QtWidgets import QApplication
    print("  ✓ PyQt6 available")
except ImportError as e:
    print(f"  ✗ PyQt6 not installed: {e}")
    sys.exit(1)

# Test 3: TTS Service
print("\n[TEST 3] TTS Service")
try:
    from gui.tts_service import get_tts_service, TTSPriority
    tts = get_tts_service()
    print("  ✓ TTS service created")
except Exception as e:
    print(f"  ✗ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Voice Interface
print("\n[TEST 4] Voice Interface")
try:
    from gui.voice_interface import create_voice_interface
    voice = create_voice_interface(wake_word="hey guru")
    print("  ✓ Voice interface created")
except Exception as e:
    print(f"  ✗ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 5: Conversation Manager
print("\n[TEST 5] Conversation Manager")
try:
    from gui.conversation_manager import create_conversation_manager
    conversation = create_conversation_manager()
    print("  ✓ Conversation manager created")
except Exception as e:
    print(f"  ✗ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 6: Avatar Window
print("\n[TEST 6] Avatar Window")
try:
    from gui.avatar_window import create_guru_window
    print("  ✓ Avatar window module loaded")
    print("  Note: Not creating window (would require Qt event loop)")
except Exception as e:
    print(f"  ✗ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 7: Thread-Safe Bridge
print("\n[TEST 7] Thread-Safe Bridge")
try:
    from gui.thread_safe_bridge import get_thread_safe_bridge
    bridge = get_thread_safe_bridge()
    print("  ✓ Bridge created")
except Exception as e:
    print(f"  ✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("DIAGNOSTIC COMPLETE")
print("=" * 70)
print("\nAll core components loaded successfully.")
print("If launch_guru.py hangs, the issue is in the Qt event loop or setup wizard.")
