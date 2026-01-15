"""
LLM Configuration Manager

Production-grade configuration management for LLM system with:
- Secure API key storage
- Configuration validation
- Migration support
- Environment variable integration
- Encrypted storage
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet


@dataclass
class LLMConfigPaths:
    """Standard configuration file paths."""
    
    # User-level configuration
    user_config_dir: Path = Path.home() / ".guru"
    user_llm_config: Path = user_config_dir / "llm_config.json"
    user_encryption_key: Path = user_config_dir / "llm_encryption.key"
    
    # Workspace-level configuration
    workspace_config_dir: Optional[Path] = None
    workspace_llm_config: Optional[Path] = None
    
    def __post_init__(self):
        """Ensure directories exist."""
        self.user_config_dir.mkdir(parents=True, exist_ok=True)
        
        if self.workspace_config_dir:
            self.workspace_config_dir.mkdir(parents=True, exist_ok=True)


class LLMConfigManager:
    """
    Production-grade LLM configuration manager.
    
    Features:
    - Secure API key storage with encryption
    - Environment variable integration
    - Configuration validation
    - Migration support
    - Workspace overrides
    """
    
    def __init__(self, workspace_dir: Optional[Path] = None):
        """
        Initialize configuration manager.
        
        Args:
            workspace_dir: Optional workspace directory for workspace-specific config
        """
        self.logger = logging.getLogger("llm.config_manager")
        
        # Setup paths
        self.paths = LLMConfigPaths()
        if workspace_dir:
            self.paths.workspace_config_dir = workspace_dir / ".guru"
            self.paths.workspace_llm_config = self.paths.workspace_config_dir / "llm_config.json"
        
        # Initialize encryption
        self._init_encryption()
        
        # Load configuration
        self.config: Optional[Dict[str, Any]] = None
    
    def _init_encryption(self):
        """Initialize encryption for sensitive data."""
        if self.paths.user_encryption_key.exists():
            with open(self.paths.user_encryption_key, 'rb') as f:
                self.encryption_key = f.read()
        else:
            # Generate new key
            self.encryption_key = Fernet.generate_key()
            with open(self.paths.user_encryption_key, 'wb') as f:
                f.write(self.encryption_key)
            
            # Secure file permissions (best effort)
            try:
                os.chmod(self.paths.user_encryption_key, 0o600)
            except:
                pass
        
        self.cipher = Fernet(self.encryption_key)
    
    def load_configuration(self) -> Dict[str, Any]:
        """
        Load LLM configuration with workspace override support.
        
        Priority:
        1. Workspace configuration (if exists)
        2. User configuration (if exists)
        3. Default configuration
        
        Returns:
            Dict containing merged configuration
        """
        # Start with default configuration
        config = self._get_default_configuration()
        
        # Load user configuration
        if self.paths.user_llm_config.exists():
            try:
                user_config = self._load_config_file(self.paths.user_llm_config)
                config = self._merge_configurations(config, user_config)
                self.logger.info("Loaded user LLM configuration")
            except Exception as e:
                self.logger.error(f"Failed to load user configuration: {e}")
        
        # Load workspace configuration (overrides user)
        if self.paths.workspace_llm_config and self.paths.workspace_llm_config.exists():
            try:
                workspace_config = self._load_config_file(self.paths.workspace_llm_config)
                config = self._merge_configurations(config, workspace_config)
                self.logger.info("Loaded workspace LLM configuration")
            except Exception as e:
                self.logger.error(f"Failed to load workspace configuration: {e}")
        
        # Load API keys from environment variables
        config = self._load_api_keys_from_env(config)
        
        # Validate configuration
        if not self._validate_configuration(config):
            self.logger.warning("Configuration validation failed, using defaults")
            config = self._get_default_configuration()
        
        self.config = config
        return config
    
    def save_configuration(
        self,
        config: Dict[str, Any],
        workspace_level: bool = False
    ) -> bool:
        """
        Save configuration to file.
        
        Args:
            config: Configuration to save
            workspace_level: If True, save to workspace config, else user config
        
        Returns:
            bool: True if save successful
        """
        try:
            # Encrypt sensitive data
            config_to_save = self._encrypt_sensitive_data(config.copy())
            
            # Determine target file
            if workspace_level and self.paths.workspace_llm_config:
                target_file = self.paths.workspace_llm_config
            else:
                target_file = self.paths.user_llm_config
            
            # Save to file
            with open(target_file, 'w') as f:
                json.dump(config_to_save, f, indent=2)
            
            self.logger.info(f"Configuration saved to {target_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
            return False
    
    def get_api_key(self, provider: str) -> Optional[str]:
        """
        Get API key for provider.
        
        Priority:
        1. Environment variable
        2. Configuration file (encrypted)
        3. None
        
        Args:
            provider: Provider name (openai, gemini)
        
        Returns:
            API key or None
        """
        # Check environment variable first
        env_var_name = f"{provider.upper()}_API_KEY"
        api_key = os.getenv(env_var_name)
        if api_key:
            return api_key
        
        # Check configuration
        if self.config:
            provider_config = self.config.get('providers', {}).get(provider, {})
            encrypted_key = provider_config.get('api_key')
            if encrypted_key:
                try:
                    # Decrypt if encrypted
                    if encrypted_key.startswith('encrypted:'):
                        encrypted_data = encrypted_key[10:]  # Remove 'encrypted:' prefix
                        decrypted = self.cipher.decrypt(encrypted_data.encode())
                        return decrypted.decode()
                    else:
                        # Plain text (for backward compatibility)
                        return encrypted_key
                except Exception as e:
                    self.logger.error(f"Failed to decrypt API key for {provider}: {e}")
        
        return None
    
    def set_api_key(
        self,
        provider: str,
        api_key: str,
        workspace_level: bool = False
    ) -> bool:
        """
        Set API key for provider.
        
        Args:
            provider: Provider name (openai, gemini)
            api_key: API key to set
            workspace_level: If True, save to workspace config
        
        Returns:
            bool: True if set successful
        """
        try:
            if not self.config:
                self.config = self._get_default_configuration()
            
            # Encrypt API key
            encrypted_key = self.cipher.encrypt(api_key.encode()).decode()
            
            # Update configuration
            if 'providers' not in self.config:
                self.config['providers'] = {}
            if provider not in self.config['providers']:
                self.config['providers'][provider] = {}
            
            self.config['providers'][provider]['api_key'] = f"encrypted:{encrypted_key}"
            
            # Save configuration
            return self.save_configuration(self.config, workspace_level)
            
        except Exception as e:
            self.logger.error(f"Failed to set API key for {provider}: {e}")
            return False
    
    def _load_config_file(self, config_file: Path) -> Dict[str, Any]:
        """Load configuration from file."""
        with open(config_file, 'r') as f:
            return json.load(f)
    
    def _merge_configurations(
        self,
        base: Dict[str, Any],
        override: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge two configurations with override taking precedence."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configurations(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _load_api_keys_from_env(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Load API keys from environment variables."""
        providers = config.get('providers', {})
        
        for provider_name in ['openai', 'gemini']:
            env_var_name = f"{provider_name.upper()}_API_KEY"
            api_key = os.getenv(env_var_name)
            
            if api_key:
                if provider_name not in providers:
                    providers[provider_name] = {}
                # Don't override if already set in config
                if not providers[provider_name].get('api_key'):
                    providers[provider_name]['api_key'] = api_key
        
        config['providers'] = providers
        return config
    
    def _encrypt_sensitive_data(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt sensitive data in configuration."""
        providers = config.get('providers', {})
        
        for provider_name, provider_config in providers.items():
            api_key = provider_config.get('api_key')
            if api_key and not api_key.startswith('encrypted:'):
                # Encrypt API key
                encrypted_key = self.cipher.encrypt(api_key.encode()).decode()
                provider_config['api_key'] = f"encrypted:{encrypted_key}"
        
        return config
    
    def _validate_configuration(self, config: Dict[str, Any]) -> bool:
        """Validate configuration structure."""
        try:
            # Check required top-level keys
            required_keys = ['mode', 'default_provider', 'providers', 'tasks']
            for key in required_keys:
                if key not in config:
                    self.logger.error(f"Missing required configuration key: {key}")
                    return False
            
            # Validate mode
            valid_modes = ['local', 'api', 'hybrid']
            if config['mode'] not in valid_modes:
                self.logger.error(f"Invalid mode: {config['mode']}")
                return False
            
            # Validate providers
            if not isinstance(config['providers'], dict):
                self.logger.error("Providers must be a dictionary")
                return False
            
            # Validate tasks
            if not isinstance(config['tasks'], dict):
                self.logger.error("Tasks must be a dictionary")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration validation error: {e}")
            return False
    
    def _get_default_configuration(self) -> Dict[str, Any]:
        """Get default LLM configuration."""
        return {
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
                    "timeout_seconds": 120,
                    "max_retries": 2
                },
                
                "deep_reasoning": {
                    "provider": "disabled",
                    "model": "",
                    "enabled": False,
                    "fallback_provider": None,
                    "fallback_model": None,
                    "timeout_seconds": 60,
                    "max_retries": 1
                }
            }
        }


# Global config manager instance
_config_manager: Optional[LLMConfigManager] = None


def get_llm_config_manager(workspace_dir: Optional[Path] = None) -> LLMConfigManager:
    """Get global LLM configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = LLMConfigManager(workspace_dir=workspace_dir)
    return _config_manager
