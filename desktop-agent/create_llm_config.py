"""
LLM Configuration Generator

Creates production-grade LLM configuration file with user's installed Ollama models.
Uses automatic model detection and intelligent model selection.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config.ollama_detector import auto_configure_ollama


def main():
    """Main entry point for LLM configuration generation."""
    
    print("=" * 80)
    print("OLLAMA MODEL AUTO-DETECTION AND CONFIGURATION")
    print("=" * 80)
    print()
    
    print("Detecting installed Ollama models...")
    print()
    
    # Run auto-configuration
    success, message = auto_configure_ollama()
    
    if success:
        print("✓ SUCCESS")
        print("=" * 80)
        print(message)
        print("=" * 80)
        print()
        print("Next step: Run GURU with 'python launch_guru.py'")
    else:
        print("✗ FAILED")
        print("=" * 80)
        print(message)
        print("=" * 80)
        print()
        print("Please ensure:")
        print("  1. Ollama is running (check with 'ollama list')")
        print("  2. You have installed models (use 'ollama pull <model>')")
        print()
        print("Recommended models:")
        print("  - ollama pull qwen2.5:7b-instruct")
        print("  - ollama pull mistral:7b-instruct")
        print("  - ollama pull qwen2.5:14b-instruct (optional, for deep reasoning)")
    
    print()
    input("Press Enter to exit...")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

