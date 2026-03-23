"""
Configuration loading for the LLM Runtime.

Loads RuntimeConfig from environment variables or YAML/JSON files,
with validation and sensible defaults.

Author: Agent Guru Team
Date: 2026-03-18
Version: 1.0.0
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from Agent_Guru.llm.models import (
    AnthropicConfig,
    GoogleConfig,
    OllamaConfig,
    OpenAIConfig,
    RuntimeConfig,
)

logger = logging.getLogger(__name__)


def load_config_from_env() -> RuntimeConfig:
    """
    Load RuntimeConfig from environment variables.

    Environment variables:
        OPENAI_API_KEY: OpenAI API key
        ANTHROPIC_API_KEY: Anthropic API key
        GOOGLE_API_KEY: Google API key
        OLLAMA_HOST: Ollama host URL (default: http://localhost:11434)
        LLM_MAX_RETRIES: Max retry attempts (default: 3)
        LLM_SLOW_THRESHOLD_MS: Slow response threshold in ms (default: 5000)
        GITHUB_REPO_URL: GitHub repository API URL (optional)
        GITHUB_BRANCH: GitHub branch (default: main)
        GITHUB_AUTH_TOKEN: GitHub authentication token (optional)

    Returns:
        RuntimeConfig populated from environment.
    """
    return RuntimeConfig(
        openai_config=OpenAIConfig(
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            organization=os.environ.get("OPENAI_ORG_ID"),
        ),
        anthropic_config=AnthropicConfig(
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        ),
        google_config=GoogleConfig(
            api_key=os.environ.get("GOOGLE_API_KEY", ""),
        ),
        ollama_config=OllamaConfig(
            host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
        ),
        max_retries=int(os.environ.get("LLM_MAX_RETRIES", "3")),
        slow_threshold_ms=float(os.environ.get("LLM_SLOW_THRESHOLD_MS", "5000")),
        github_repo_url=os.environ.get("GITHUB_REPO_URL"),
        github_branch=os.environ.get("GITHUB_BRANCH", "main"),
        github_auth_token=os.environ.get("GITHUB_AUTH_TOKEN"),
    )


def load_config_from_file(path: str) -> RuntimeConfig:
    """
    Load RuntimeConfig from a YAML or JSON file.

    Args:
        path: Path to configuration file (.yaml, .yml, or .json).

    Returns:
        RuntimeConfig populated from file.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If the file format is unsupported.
    """
    config_path = Path(path)

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    suffix = config_path.suffix.lower()

    if suffix in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore[import]

            with open(config_path) as f:
                data: dict[str, Any] = yaml.safe_load(f) or {}
        except ImportError as e:
            raise ImportError("PyYAML is required for YAML config files: pip install pyyaml") from e
    elif suffix == ".json":
        with open(config_path) as f:
            data = json.load(f)
    else:
        raise ValueError(f"Unsupported config file format: {suffix}. Use .yaml or .json")

    return _dict_to_config(data)


def _dict_to_config(data: dict[str, Any]) -> RuntimeConfig:
    """Convert a raw dictionary to RuntimeConfig."""
    openai_data = data.get("openai", {})
    anthropic_data = data.get("anthropic", {})
    google_data = data.get("google", {})
    ollama_data = data.get("ollama", {})
    github_data = data.get("github", {})

    return RuntimeConfig(
        openai_config=OpenAIConfig(
            api_key=openai_data.get("api_key", ""),
            organization=openai_data.get("organization"),
            timeout_s=float(openai_data.get("timeout_s", 60.0)),
        ),
        anthropic_config=AnthropicConfig(
            api_key=anthropic_data.get("api_key", ""),
            timeout_s=float(anthropic_data.get("timeout_s", 60.0)),
        ),
        google_config=GoogleConfig(
            api_key=google_data.get("api_key", ""),
            timeout_s=float(google_data.get("timeout_s", 60.0)),
        ),
        ollama_config=OllamaConfig(
            host=ollama_data.get("host", "http://localhost:11434"),
            timeout_s=float(ollama_data.get("timeout_s", 120.0)),
        ),
        max_retries=int(data.get("max_retries", 3)),
        slow_threshold_ms=float(data.get("slow_threshold_ms", 5000.0)),
        compression_threshold=float(data.get("compression_threshold", 0.8)),
        max_history_messages=int(data.get("max_history_messages", 100)),
        github_repo_url=github_data.get("repo_url"),
        github_branch=github_data.get("branch", "main"),
        github_auth_token=github_data.get("auth_token"),
    )
