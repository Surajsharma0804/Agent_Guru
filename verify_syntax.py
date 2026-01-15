#!/usr/bin/env python3
"""
Verify Python syntax for all files that coverage couldn't parse.
"""

import ast
import sys
from pathlib import Path

files_to_check = [
    "desktop-agent/src/ai/ollama_engine.py",
    "desktop-agent/src/config/configuration_manager.py",
    "desktop-agent/src/config/first_run_detector.py",
    "desktop-agent/src/config/user_config.py",
    "desktop-agent/src/gui/conversation_manager.py",
    "desktop-agent/src/gui/setup_wizard.py",
    "desktop-agent/src/gui/tts_service.py",
    "desktop-agent/src/gui/voice_interface.py",
    "desktop-agent/src/pal/backends/android/application_controller.py",
    "desktop-agent/src/pal/backends/android/biometric_authenticator.py",
    "desktop-agent/src/pal/backends/android/input_automation.py",
    "desktop-agent/src/pal/backends/android/security_enforcer.py",
    "desktop-agent/src/pal/backends/android/speech_input.py",
    "desktop-agent/src/pal/backends/android/speech_output.py",
    "desktop-agent/src/pal/backends/macos/application_controller.py",
    "desktop-agent/src/pal/backends/macos/speech_input.py",
    "desktop-agent/src/pal/backends/windows/application_controller.py",
    "desktop-agent/src/pal/backends/windows/speech_output.py",
]

errors_found = []

for filepath in files_to_check:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Try to parse the file
        ast.parse(content, filename=filepath)
        print(f"✓ {filepath}")
        
    except SyntaxError as e:
        errors_found.append((filepath, e))
        print(f"✗ {filepath}")
        print(f"  Line {e.lineno}: {e.msg}")
        print(f"  {e.text}")
        print()
    except Exception as e:
        errors_found.append((filepath, e))
        print(f"✗ {filepath}")
        print(f"  Error: {e}")
        print()

print()
print("=" * 80)
if errors_found:
    print(f"FOUND {len(errors_found)} FILES WITH SYNTAX ERRORS")
    print("=" * 80)
    for filepath, error in errors_found:
        print(f"\n{filepath}:")
        print(f"  {error}")
    sys.exit(1)
else:
    print("ALL FILES HAVE VALID SYNTAX")
    print("=" * 80)
    sys.exit(0)
