"""
Ollama Model Auto-Detection

Production-grade Ollama model detection and configuration generation with:
- Automatic detection of installed Ollama models
- Intelligent model selection for different tasks
- Automatic llm_config.json generation
- Model capability analysis
- Timeout configuration based on model size
- Fallback model selection

DETECTION STRATEGY:
1. Query Ollama API for installed models
2. Analyze model names and sizes
3. Select appropriate models for each task:
   - Conversation: Fast, general-purpose (7B)
   - Intent Extraction: Fast, instruction-following (7B)
   - Intent Structuring: Fast, structured output (7B)
   - Deep Reasoning: Slow, high-quality (14B+)
4. Generate optimized configuration

MODEL SELECTION CRITERIA:
- Conversation: qwen2.5:7b-instruct > mistral:7b-instruct > llama2:7b
- Intent: qwen2.5:7b-instruct > mistral:7b-instruct > llama2:7b
- Structuring: mistral:7b-instruct > qwen2.5:7b-instruct > llama2:7b
- Reasoning: qwen2.5:14b-instruct > mixtral:8x7b > llama2:13b

SECURITY INVARIANTS:
- Only queries localhost Ollama instance
- No network calls to external services
- No model downloads (user must install models)
- Configuration validation before saving
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests


@dataclass
class OllamaModel:
    """Ollama model information."""

    name: str
    size: int  # Size in bytes
    modified: datetime
    digest: str
    family: str = ""  # Model family (qwen, mistral, llama, etc.)
    parameter_count: str = ""  # Parameter count (7B, 14B, etc.)

    @property
    def is_instruct(self) -> bool:
        """Check if model is instruction-tuned."""
        return "instruct" in self.name.lower()

    @property
    def is_small(self) -> bool:
        """Check if model is small (< 10B parameters)."""
        if "7b" in self.name.lower():
            return True
        if "3b" in self.name.lower():
            return True
        return False

    @property
    def is_large(self) -> bool:
        """Check if model is large (>= 13B parameters)."""
        if "13b" in self.name.lower() or "14b" in self.name.lower():
            return True
        if "70b" in self.name.lower():
            return True
        if "8x7b" in self.name.lower():  # Mixtral
            return True
        return False

    @property
    def estimated_timeout(self) -> int:
        """Estimate appropriate timeout based on model size."""
        if self.is_small:
            return 30  # 30 seconds for small models
        elif self.is_large:
            return 180  # 3 minutes for large models
        else:
            return 60  # 1 minute for medium models


class OllamaDetector:
    """
    Production-grade Ollama model detector and configuration generator.

    Features:
    - Automatic detection of installed Ollama models
    - Intelligent model selection for different tasks
    - Automatic configuration generation
    - Model capability analysis
    - Timeout optimization based on model size
    - Fallback model selection

    Example:
        detector = OllamaDetector()

        # Detect installed models
        models = detector.detect_models()

        # Generate configuration
        config = detector.generate_llm_config()

        # Save configuration
        detector.save_llm_config(config)
    """

    def __init__(self, base_url: str = "http://localhost:11434", config_dir: Optional[Path] = None):
        """
        Initialize Ollama detector.

        Args:
            base_url: Ollama API base URL
            config_dir: Configuration directory (defaults to ~/.guru)
        """
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.config_dir = config_dir or (Path.home() / ".guru")
        self.logger = logging.getLogger("config.ollama_detector")

        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def is_ollama_available(self) -> bool:
        """
        Check if Ollama service is available.

        Returns:
            bool: True if Ollama is running and accessible
        """
        try:
            response = requests.get(f"{self.api_url}/tags", timeout=2)
            return response.status_code == 200
        except Exception:
            return False

    def detect_models(self) -> List[OllamaModel]:
        """
        Detect installed Ollama models.

        Returns:
            List of OllamaModel objects

        Raises:
            RuntimeError: If Ollama is not available
        """
        if not self.is_ollama_available():
            raise RuntimeError("Ollama is not running or not accessible. " "Please start Ollama and try again.")

        try:
            response = requests.get(f"{self.api_url}/tags", timeout=5)
            response.raise_for_status()

            data = response.json()
            models_data = data.get("models", [])

            models = []
            for model_data in models_data:
                # Parse model information
                name = model_data.get("name", "")
                size = model_data.get("size", 0)
                modified_str = model_data.get("modified_at", "")
                digest = model_data.get("digest", "")

                # Parse modified timestamp
                try:
                    modified = datetime.fromisoformat(modified_str.replace("Z", "+00:00"))
                except Exception:
                    modified = datetime.now()

                # Extract model family and parameter count
                family, parameter_count = self._parse_model_name(name)

                model = OllamaModel(
                    name=name,
                    size=size,
                    modified=modified,
                    digest=digest,
                    family=family,
                    parameter_count=parameter_count,
                )

                models.append(model)

            self.logger.info(f"Detected {len(models)} Ollama models")
            return models

        except Exception as e:
            self.logger.error(f"Failed to detect Ollama models: {e}")
            raise RuntimeError(f"Failed to detect Ollama models: {e}")

    def select_models_for_tasks(self, models: List[OllamaModel]) -> Dict[str, Optional[str]]:
        """
        Select appropriate models for different tasks.

        Args:
            models: List of available models

        Returns:
            Dict mapping task names to model names
        """
        # Filter instruction-tuned models
        instruct_models = [m for m in models if m.is_instruct]

        if not instruct_models:
            self.logger.warning("No instruction-tuned models found")
            instruct_models = models  # Fallback to all models

        # Separate by size
        small_models = [m for m in instruct_models if m.is_small]
        large_models = [m for m in instruct_models if m.is_large]

        # Model preferences for each task
        conversation_preferences = [
            "qwen2.5:7b-instruct",
            "mistral:7b-instruct",
            "llama2:7b-chat",
            "llama3:8b-instruct",
        ]

        intent_preferences = ["qwen2.5:7b-instruct", "mistral:7b-instruct", "llama2:7b-chat", "llama3:8b-instruct"]

        structuring_preferences = ["mistral:7b-instruct", "qwen2.5:7b-instruct", "llama2:7b-chat", "llama3:8b-instruct"]

        reasoning_preferences = [
            "qwen2.5:14b-instruct",
            "mixtral:8x7b-instruct",
            "llama2:13b-chat",
            "qwen2.5:32b-instruct",
        ]

        # Select models
        selected = {
            "conversation": self._select_best_model(small_models, conversation_preferences),
            "intent_extraction": self._select_best_model(small_models, intent_preferences),
            "intent_structuring": self._select_best_model(small_models, structuring_preferences),
            "deep_reasoning": self._select_best_model(large_models, reasoning_preferences),
        }

        # Fallback: use any available model if specific task model not found
        if not selected["conversation"] and instruct_models:
            selected["conversation"] = instruct_models[0].name

        if not selected["intent_extraction"]:
            selected["intent_extraction"] = selected["conversation"]

        if not selected["intent_structuring"]:
            selected["intent_structuring"] = selected["conversation"]

        # Deep reasoning is optional
        if not selected["deep_reasoning"]:
            self.logger.info("No large model found for deep reasoning (optional)")

        self.logger.info(f"Selected models: {selected}")
        return selected

    def generate_llm_config(self, models: Optional[List[OllamaModel]] = None) -> Dict[str, Any]:
        """
        Generate LLM configuration with detected models.

        Args:
            models: Optional list of models (auto-detected if not provided)

        Returns:
            Dict containing LLM configuration
        """
        # Detect models if not provided
        if models is None:
            models = self.detect_models()

        # Select models for tasks
        selected_models = self.select_models_for_tasks(models)

        # Find selected model objects for timeout configuration
        model_map = {m.name: m for m in models}

        # Build configuration
        config = {
            "mode": "local",
            "default_provider": "ollama",
            "enable_fallback": True,
            "enable_audit_logging": True,
            "fail_closed_on_error": True,
            "providers": {
                "ollama": {
                    "enabled": True,
                    "base_url": self.base_url,
                    "models": [m.name for m in models],
                    "default_model": selected_models.get("conversation"),
                    "require_manual_confirmation": False,
                    "require_armed_authority": False,
                    "timeout_seconds": 30,
                    "max_concurrent_requests": 5,
                },
                "openai": {
                    "enabled": False,
                    "api_key": None,
                    "models": ["gpt-3.5-turbo", "gpt-4"],
                    "default_model": "gpt-3.5-turbo",
                    "require_manual_confirmation": True,
                    "require_armed_authority": True,
                    "timeout_seconds": 30,
                    "max_concurrent_requests": 3,
                },
                "gemini": {
                    "enabled": False,
                    "api_key": None,
                    "models": ["gemini-pro", "gemini-1.5-pro"],
                    "default_model": "gemini-pro",
                    "require_manual_confirmation": True,
                    "require_armed_authority": True,
                    "timeout_seconds": 30,
                    "max_concurrent_requests": 3,
                },
            },
            "tasks": {},
        }

        # Configure conversation task
        if selected_models.get("conversation"):
            model = model_map.get(selected_models["conversation"])
            config["tasks"]["conversation"] = {
                "provider": "ollama",
                "model": selected_models["conversation"],
                "enabled": True,
                "fallback_provider": None,
                "fallback_model": None,
                "timeout_seconds": model.estimated_timeout if model else 30,
                "max_retries": 2,
            }

        # Configure intent extraction task
        if selected_models.get("intent_extraction"):
            model = model_map.get(selected_models["intent_extraction"])
            config["tasks"]["intent_extraction"] = {
                "provider": "ollama",
                "model": selected_models["intent_extraction"],
                "enabled": True,
                "fallback_provider": None,
                "fallback_model": None,
                "timeout_seconds": model.estimated_timeout if model else 30,
                "max_retries": 2,
            }

        # Configure intent structuring task
        if selected_models.get("intent_structuring"):
            model = model_map.get(selected_models["intent_structuring"])
            config["tasks"]["intent_structuring"] = {
                "provider": "ollama",
                "model": selected_models["intent_structuring"],
                "enabled": True,
                "fallback_provider": None,
                "fallback_model": None,
                "timeout_seconds": model.estimated_timeout if model else 30,
                "max_retries": 2,
            }

        # Configure deep reasoning task (optional)
        if selected_models.get("deep_reasoning"):
            model = model_map.get(selected_models["deep_reasoning"])
            config["tasks"]["deep_reasoning"] = {
                "provider": "ollama",
                "model": selected_models["deep_reasoning"],
                "enabled": True,
                "fallback_provider": None,
                "fallback_model": None,
                "timeout_seconds": model.estimated_timeout if model else 60,
                "max_retries": 1,
            }
        else:
            # Disable deep reasoning if no large model available
            config["tasks"]["deep_reasoning"] = {
                "provider": "disabled",
                "model": "",
                "enabled": False,
                "fallback_provider": None,
                "fallback_model": None,
                "timeout_seconds": 60,
                "max_retries": 1,
            }

        return config

    def save_llm_config(self, config: Dict[str, Any], config_file: Optional[Path] = None) -> Path:
        """
        Save LLM configuration to file.

        Args:
            config: LLM configuration to save
            config_file: Optional custom config file path

        Returns:
            Path to saved configuration file
        """
        if config_file is None:
            config_file = self.config_dir / "llm_config.json"

        # Create backup if file exists
        if config_file.exists():
            backup_file = config_file.with_suffix(".json.backup")
            import shutil

            shutil.copy2(config_file, backup_file)
            self.logger.info(f"Created backup: {backup_file}")

        # Save configuration
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)

        self.logger.info(f"Saved LLM configuration to {config_file}")
        return config_file

    def auto_configure(self) -> Tuple[bool, str]:
        """
        Automatically detect models and generate configuration.

        Returns:
            Tuple of (success, message)
        """
        try:
            # Check Ollama availability
            if not self.is_ollama_available():
                return False, ("Ollama is not running or not accessible. " "Please start Ollama and try again.")

            # Detect models
            models = self.detect_models()

            if not models:
                return False, (
                    "No Ollama models found. " "Please install models using 'ollama pull <model>' and try again."
                )

            # Generate configuration
            config = self.generate_llm_config(models)

            # Validate configuration
            if not self._validate_config(config):
                return False, "Generated configuration is invalid"

            # Save configuration
            config_file = self.save_llm_config(config)

            # Build success message
            selected_models = self.select_models_for_tasks(models)
            message = f"Successfully configured {len(models)} Ollama models:\n"
            message += f"  - Conversation: {selected_models.get('conversation', 'N/A')}\n"
            message += f"  - Intent Extraction: {selected_models.get('intent_extraction', 'N/A')}\n"
            message += f"  - Intent Structuring: {selected_models.get('intent_structuring', 'N/A')}\n"
            message += f"  - Deep Reasoning: {selected_models.get('deep_reasoning', 'N/A')}\n"
            message += f"\nConfiguration saved to: {config_file}"

            return True, message

        except Exception as e:
            self.logger.error(f"Auto-configuration failed: {e}")
            return False, f"Auto-configuration failed: {e}"

    def _select_best_model(self, models: List[OllamaModel], preferences: List[str]) -> Optional[str]:
        """Select best model from list based on preferences."""
        # Try exact matches first
        for preferred in preferences:
            for model in models:
                if model.name == preferred:
                    return model.name

        # Try partial matches
        for preferred in preferences:
            for model in models:
                if preferred.split(":")[0] in model.name:
                    return model.name

        # Return first available model
        if models:
            return models[0].name

        return None

    def _parse_model_name(self, name: str) -> Tuple[str, str]:
        """
        Parse model name to extract family and parameter count.

        Args:
            name: Model name (e.g., "qwen2.5:7b-instruct")

        Returns:
            Tuple of (family, parameter_count)
        """
        # Extract family (before colon)
        if ":" in name:
            family = name.split(":")[0]
        else:
            family = name

        # Extract parameter count
        parameter_count = ""
        patterns = [
            r"(\d+b)",  # 7b, 14b, etc.
            r"(\d+x\d+b)",  # 8x7b (Mixtral)
        ]

        for pattern in patterns:
            match = re.search(pattern, name.lower())
            if match:
                parameter_count = match.group(1)
                break

        return family, parameter_count

    def _validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate generated configuration."""
        try:
            # Check required keys
            required_keys = ["mode", "default_provider", "providers", "tasks"]
            for key in required_keys:
                if key not in config:
                    self.logger.error(f"Missing required key: {key}")
                    return False

            # Check providers
            if "ollama" not in config["providers"]:
                self.logger.error("Missing ollama provider")
                return False

            # Check tasks
            required_tasks = ["conversation", "intent_extraction", "intent_structuring"]
            for task in required_tasks:
                if task not in config["tasks"]:
                    self.logger.error(f"Missing required task: {task}")
                    return False

            return True

        except Exception as e:
            self.logger.error(f"Configuration validation error: {e}")
            return False


def auto_configure_ollama(
    base_url: str = "http://localhost:11434", config_dir: Optional[Path] = None
) -> Tuple[bool, str]:
    """
    Convenience function for automatic Ollama configuration.

    Args:
        base_url: Ollama API base URL
        config_dir: Configuration directory

    Returns:
        Tuple of (success, message)
    """
    detector = OllamaDetector(base_url=base_url, config_dir=config_dir)
    return detector.auto_configure()
