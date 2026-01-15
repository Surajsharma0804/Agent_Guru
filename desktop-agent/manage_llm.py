#!/usr/bin/env python3
"""
LLM System Management CLI

Production-grade command-line tool for managing the GURU LLM system.

Features:
- View system status
- Switch providers
- Configure API keys
- Test providers
- View audit logs
- Manage configuration
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.llm.config_manager import get_llm_config_manager
from src.llm.integration import get_llm_integration
from src.llm.model_router import ProviderType, RouterConfiguration, TaskType, get_model_router


class LLMManager:
    """LLM system management interface."""
    
    def __init__(self):
        self.config_manager = get_llm_config_manager()
    
    async def status(self):
        """Display system status."""
        print("=" * 70)
        print("GURU LLM System Status")
        print("=" * 70)
        
        # Load configuration
        config = self.config_manager.load_configuration()
        
        print(f"\nMode: {config['mode']}")
        print(f"Default Provider: {config['default_provider']}")
        print(f"Fallback Enabled: {config['enable_fallback']}")
        print(f"Audit Logging: {config['enable_audit_logging']}")
        
        # Provider status
        print("\n" + "-" * 70)
        print("Providers:")
        print("-" * 70)
        
        for provider_name, provider_config in config['providers'].items():
            status_icon = "✓" if provider_config['enabled'] else "✗"
            print(f"\n{status_icon} {provider_name.upper()}")
            print(f"  Enabled: {provider_config['enabled']}")
            print(f"  Models: {', '.join(provider_config.get('models', []))}")
            print(f"  Default Model: {provider_config.get('default_model', 'N/A')}")
            
            if provider_name in ['openai', 'gemini']:
                api_key = self.config_manager.get_api_key(provider_name)
                if api_key:
                    print(f"  API Key: {'*' * 20} (configured)")
                else:
                    print(f"  API Key: Not configured")
        
        # Task routing
        print("\n" + "-" * 70)
        print("Task Routing:")
        print("-" * 70)
        
        for task_name, task_config in config['tasks'].items():
            status_icon = "✓" if task_config['enabled'] else "✗"
            print(f"\n{status_icon} {task_name}")
            print(f"  Provider: {task_config['provider']}")
            print(f"  Model: {task_config['model']}")
            print(f"  Enabled: {task_config['enabled']}")
            
            if task_config.get('fallback_provider'):
                print(f"  Fallback: {task_config['fallback_provider']}/{task_config['fallback_model']}")
        
        print("\n" + "=" * 70)
    
    async def test_provider(self, provider_name: str):
        """Test a specific provider."""
        print(f"\nTesting {provider_name} provider...")
        
        try:
            # Initialize router
            config = self.config_manager.load_configuration()
            router = get_model_router()
            
            # Load config into router
            router.config = RouterConfiguration.from_dict(config)
            
            # Initialize
            if not await router.initialize():
                print(f"✗ Failed to initialize router")
                return
            
            # Check if provider is available
            provider_type = ProviderType(provider_name)
            if provider_type not in router.providers:
                print(f"✗ Provider {provider_name} not available")
                print(f"  Available providers: {[p.value for p in router.providers.keys()]}")
                return
            
            # Test with simple prompt
            print(f"✓ Provider {provider_name} is available")
            print(f"  Testing with simple prompt...")
            
            result = await router.route_task(
                task_type=TaskType.CONVERSATION,
                prompt="Hello, how are you?",
                preferred_provider=provider_type
            )
            
            if result['success']:
                print(f"✓ Test successful!")
                print(f"  Response: {result['result'][:100]}...")
                print(f"  Duration: {result['metadata'].get('duration_ms', 'N/A')}ms")
            else:
                print(f"✗ Test failed: {result.get('error')}")
        
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
    
    async def switch_provider(
        self,
        task: str,
        provider: str,
        model: str
    ):
        """Switch provider for a task."""
        print(f"\nSwitching {task} to {provider}/{model}...")
        
        try:
            # Load configuration
            config = self.config_manager.load_configuration()
            
            # Validate task
            if task not in config['tasks']:
                print(f"✗ Invalid task: {task}")
                print(f"  Valid tasks: {', '.join(config['tasks'].keys())}")
                return
            
            # Validate provider
            if provider not in config['providers']:
                print(f"✗ Invalid provider: {provider}")
                print(f"  Valid providers: {', '.join(config['providers'].keys())}")
                return
            
            # Update configuration
            config['tasks'][task]['provider'] = provider
            config['tasks'][task]['model'] = model
            
            # Save configuration
            if self.config_manager.save_configuration(config):
                print(f"✓ Successfully switched {task} to {provider}/{model}")
                print(f"  Configuration saved")
            else:
                print(f"✗ Failed to save configuration")
        
        except Exception as e:
            print(f"✗ Switch failed: {e}")
    
    async def set_api_key(self, provider: str, api_key: str):
        """Set API key for provider."""
        print(f"\nSetting API key for {provider}...")
        
        try:
            if self.config_manager.set_api_key(provider, api_key):
                print(f"✓ API key set successfully for {provider}")
                print(f"  Key is encrypted and stored securely")
            else:
                print(f"✗ Failed to set API key")
        
        except Exception as e:
            print(f"✗ Failed to set API key: {e}")
    
    async def enable_provider(self, provider: str):
        """Enable a provider."""
        print(f"\nEnabling {provider} provider...")
        
        try:
            config = self.config_manager.load_configuration()
            
            if provider not in config['providers']:
                print(f"✗ Invalid provider: {provider}")
                return
            
            config['providers'][provider]['enabled'] = True
            
            if self.config_manager.save_configuration(config):
                print(f"✓ Provider {provider} enabled")
            else:
                print(f"✗ Failed to save configuration")
        
        except Exception as e:
            print(f"✗ Failed to enable provider: {e}")
    
    async def disable_provider(self, provider: str):
        """Disable a provider."""
        print(f"\nDisabling {provider} provider...")
        
        try:
            config = self.config_manager.load_configuration()
            
            if provider not in config['providers']:
                print(f"✗ Invalid provider: {provider}")
                return
            
            config['providers'][provider]['enabled'] = False
            
            if self.config_manager.save_configuration(config):
                print(f"✓ Provider {provider} disabled")
            else:
                print(f"✗ Failed to save configuration")
        
        except Exception as e:
            print(f"✗ Failed to disable provider: {e}")
    
    async def local_only_mode(self):
        """Switch to local-only mode."""
        print("\nSwitching to local-only mode...")
        
        try:
            config = self.config_manager.load_configuration()
            
            # Set mode to local
            config['mode'] = 'local'
            config['default_provider'] = 'ollama'
            
            # Disable API providers
            for provider in ['openai', 'gemini']:
                if provider in config['providers']:
                    config['providers'][provider]['enabled'] = False
            
            # Switch all tasks to ollama
            for task_name, task_config in config['tasks'].items():
                if task_config['provider'] in ['openai', 'gemini']:
                    task_config['provider'] = 'ollama'
                    # Use default model
                    if task_name == 'intent_extraction':
                        task_config['model'] = 'qwen2.5:7b-instruct'
                    elif task_name == 'intent_structuring':
                        task_config['model'] = 'mistral:7b-instruct'
                    elif task_name == 'conversation':
                        task_config['model'] = 'qwen2.5:7b-instruct'
            
            if self.config_manager.save_configuration(config):
                print("✓ Switched to local-only mode")
                print("  All API providers disabled")
                print("  All tasks using local models")
            else:
                print("✗ Failed to save configuration")
        
        except Exception as e:
            print(f"✗ Failed to switch to local-only mode: {e}")
    
    async def export_config(self, output_file: str):
        """Export configuration to file."""
        print(f"\nExporting configuration to {output_file}...")
        
        try:
            config = self.config_manager.load_configuration()
            
            # Remove encrypted API keys for export
            for provider_config in config.get('providers', {}).values():
                if 'api_key' in provider_config:
                    provider_config['api_key'] = None
            
            with open(output_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            print(f"✓ Configuration exported to {output_file}")
            print(f"  Note: API keys are not included in export")
        
        except Exception as e:
            print(f"✗ Export failed: {e}")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="GURU LLM System Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # View system status
  python manage_llm.py status
  
  # Test a provider
  python manage_llm.py test ollama
  python manage_llm.py test openai
  
  # Switch provider for a task
  python manage_llm.py switch intent_extraction openai gpt-3.5-turbo
  
  # Set API key
  python manage_llm.py set-key openai sk-your-key-here
  
  # Enable/disable provider
  python manage_llm.py enable openai
  python manage_llm.py disable gemini
  
  # Switch to local-only mode
  python manage_llm.py local-only
  
  # Export configuration
  python manage_llm.py export my_config.json
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Status command
    subparsers.add_parser('status', help='Display system status')
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Test a provider')
    test_parser.add_argument('provider', choices=['ollama', 'openai', 'gemini'])
    
    # Switch command
    switch_parser = subparsers.add_parser('switch', help='Switch provider for a task')
    switch_parser.add_argument('task', help='Task name')
    switch_parser.add_argument('provider', help='Provider name')
    switch_parser.add_argument('model', help='Model name')
    
    # Set API key command
    key_parser = subparsers.add_parser('set-key', help='Set API key for provider')
    key_parser.add_argument('provider', choices=['openai', 'gemini'])
    key_parser.add_argument('api_key', help='API key')
    
    # Enable provider command
    enable_parser = subparsers.add_parser('enable', help='Enable a provider')
    enable_parser.add_argument('provider', help='Provider name')
    
    # Disable provider command
    disable_parser = subparsers.add_parser('disable', help='Disable a provider')
    disable_parser.add_argument('provider', help='Provider name')
    
    # Local-only mode command
    subparsers.add_parser('local-only', help='Switch to local-only mode')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export configuration')
    export_parser.add_argument('output_file', help='Output file path')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = LLMManager()
    
    if args.command == 'status':
        await manager.status()
    elif args.command == 'test':
        await manager.test_provider(args.provider)
    elif args.command == 'switch':
        await manager.switch_provider(args.task, args.provider, args.model)
    elif args.command == 'set-key':
        await manager.set_api_key(args.provider, args.api_key)
    elif args.command == 'enable':
        await manager.enable_provider(args.provider)
    elif args.command == 'disable':
        await manager.disable_provider(args.provider)
    elif args.command == 'local-only':
        await manager.local_only_mode()
    elif args.command == 'export':
        await manager.export_config(args.output_file)


if __name__ == "__main__":
    asyncio.run(main())
