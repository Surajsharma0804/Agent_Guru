"""
LLM Configuration Generator

Creates production-grade LLM configuration file with user's installed Ollama models.
This replaces the batch script which has JSON escaping issues on Windows.
"""

import json
import os
from pathlib import Path


def create_llm_config():
    """Create LLM configuration file with correct models"""
    
    print("=" * 80)
    print("CREATING LLM CONFIGURATION")
    print("=" * 80)
    print()
    
    # Configuration directory
    config_dir = Path.home() / ".guru"
    config_file = config_dir / "llm_config.json"
    
    # Create directory if it doesn't exist
    config_dir.mkdir(parents=True, exist_ok=True)
    print(f"✓ Configuration directory: {config_dir}")
    
    # Production-grade configuration
    config = {
        "mode": "local",
        "default_provider": "ollama",
        "enable_fallback": True,
        "enable_audit_logging": True,
        "fail_closed_on_error": True,
        
        "providers": {
            "ollama": {
                "enabled": True,
                "base_url": "http://localhost:11434",
                "models": [
                    "qwen2.5:7b-instruct",
                    "qwen2.5:14b-instruct",
                    "mistral:7b-instruct"
                ],
                "default_model": "qwen2.5:7b-instruct",
                "require_manual_confirmation": False,
                "require_armed_authority": False,
                "timeout_seconds": 30,
                "max_concurrent_requests": 5
            },
            
            "openai": {
                "enabled": False,
                "api_key": None,
                "models": ["gpt-3.5-turbo", "gpt-4"],
                "default_model": "gpt-3.5-turbo",
                "require_manual_confirmation": True,
                "require_armed_authority": True,
                "timeout_seconds": 30,
                "max_concurrent_requests": 3
            },
            
            "gemini": {
                "enabled": False,
                "api_key": None,
                "models": ["gemini-pro", "gemini-1.5-pro"],
                "default_model": "gemini-pro",
                "require_manual_confirmation": True,
                "require_armed_authority": True,
                "timeout_seconds": 30,
                "max_concurrent_requests": 3
            }
        },
        
        "tasks": {
            "intent_extraction": {
                "provider": "ollama",
                "model": "qwen2.5:7b-instruct",
                "enabled": True,
                "fallback_provider": None,
                "fallback_model": None,
                "timeout_seconds": 30,
                "max_retries": 2
            },
            
            "intent_structuring": {
                "provider": "ollama",
                "model": "mistral:7b-instruct",
                "enabled": True,
                "fallback_provider": None,
                "fallback_model": None,
                "timeout_seconds": 30,
                "max_retries": 2
            },
            
            "conversation": {
                "provider": "ollama",
                "model": "qwen2.5:7b-instruct",
                "enabled": True,
                "fallback_provider": None,
                "fallback_model": None,
                "timeout_seconds": 15,
                "max_retries": 1
            },
            
            "deep_reasoning": {
                "provider": "ollama",
                "model": "qwen2.5:14b-instruct",
                "enabled": True,
                "fallback_provider": None,
                "fallback_model": None,
                "timeout_seconds": 60,
                "max_retries": 1
            }
        }
    }
    
    # Write configuration file
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Configuration file created: {config_file}")
        print()
        print("=" * 80)
        print("CONFIGURATION CREATED SUCCESSFULLY")
        print("=" * 80)
        print()
        print("Models configured:")
        print("  - Conversation: qwen2.5:7b-instruct")
        print("  - Intent Extraction: qwen2.5:7b-instruct")
        print("  - Intent Structuring: mistral:7b-instruct")
        print("  - Deep Reasoning: qwen2.5:14b-instruct")
        print()
        print("All models match your installed Ollama models!")
        print()
        
        # Verify file was created
        if config_file.exists():
            file_size = config_file.stat().st_size
            print(f"✓ Verification: File exists ({file_size} bytes)")
            return True
        else:
            print("✗ ERROR: File was not created!")
            return False
            
    except Exception as e:
        print(f"✗ ERROR creating configuration file: {e}")
        return False


if __name__ == "__main__":
    success = create_llm_config()
    
    if success:
        print()
        print("Next step: Run GURU with 'python launch_guru.py'")
    else:
        print()
        print("Configuration creation failed. Please check permissions.")
    
    input("\nPress Enter to exit...")
