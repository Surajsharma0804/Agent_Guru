"""Settings from a file, for the environment variables the assistant already reads.

Every part of Agent Guru reads its settings from environment variables
(OLLAMA_MODEL, AGENT_GURU_LLM_TIMEOUT, ...), which an owner can only set in a
terminal or the system dialog, and which are gone the next time the app is
started some other way. settings.toml in the data folder holds them instead:

    OLLAMA_MODEL = "gemma4"
    AGENT_GURU_LLM_TIMEOUT = 45
    AGENT_GURU_TRACES = false

apply_settings_file() runs once at start, before anything reads them. It is
not a second configuration system: the file only fills in variables, so every
module keeps reading its setting where it always has, and a variable set in
the environment still wins over the file.

Only the settings listed in KNOWN_SETTINGS are taken, each checked for its
kind; anything else is reported and left out. Secrets (API keys, tokens,
passwords, connection strings) are never taken from this file, which is plain
text: they stay in the environment or .env.
"""

from __future__ import annotations

import logging
import os
import re
import tomllib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

#: Setting name -> kind. seconds: a number above 0; count: a whole number
#: above 0; flag: true/false; text: a short string; path: a file or folder.
KNOWN_SETTINGS: dict[str, str] = {
    "OLLAMA_HOST": "text",
    "OLLAMA_MODEL": "text",
    "OLLAMA_NUM_GPU": "count",
    "OLLAMA_TIMEOUT_SECONDS": "seconds",
    "OLLAMA_CONNECT_TIMEOUT_SECONDS": "seconds",
    "OLLAMA_START_TIMEOUT_SECONDS": "seconds",
    "LLM_MAX_RETRIES": "count",
    "LLM_SLOW_THRESHOLD_MS": "seconds",
    "AGENT_GURU_NUM_CTX": "count",
    "AGENT_GURU_NUM_GPU": "count",
    "AGENT_GURU_SPOKEN_REPLY_TOKENS": "count",
    "AGENT_GURU_STT_TIMEOUT": "seconds",
    "AGENT_GURU_TTS_TIMEOUT": "seconds",
    "AGENT_GURU_LLM_TIMEOUT": "seconds",
    "AGENT_GURU_INTENT_TIMEOUT": "seconds",
    "AGENT_GURU_INTENT_TIMEOUT_SECONDS": "seconds",
    "AGENT_GURU_POLICY_TIMEOUT": "seconds",
    "AGENT_GURU_MEMORY_TIMEOUT": "seconds",
    "AGENT_GURU_MEMORY_WRITE_TIMEOUT": "seconds",
    "AGENT_GURU_TRACE_WRITE_TIMEOUT": "seconds",
    "AGENT_GURU_PLAN_TIMEOUT_SECONDS": "seconds",
    "AGENT_GURU_STARTUP_TIMEOUT": "seconds",
    "AGENT_GURU_MESSAGE_DRAFT_TTL": "seconds",
    "AGENT_GURU_MAX_RESTARTS": "count",
    "AGENT_GURU_TRACES": "flag",
    "AGENT_GURU_LEARN_FACTS": "flag",
    "AGENT_GURU_RESEARCH": "flag",
    "AGENT_GURU_API": "flag",
    "AGENT_GURU_API_PORT": "count",
    "AGENT_GURU_TELEGRAM_INBOUND": "flag",
    "TELEGRAM_ALLOWED_CHATS": "text",
    "IMAP_HOST": "text",
    "IMAP_PORT": "count",
    "IMAP_USER": "text",
    "SMTP_HOST": "text",
    "SMTP_PORT": "count",
    "SMTP_USER": "text",
    "SMTP_FROM": "text",
    "CALENDAR_ICS": "path",
    "FILES_ROOTS": "text",
    "NEWS_FEEDS": "text",
    "OBSIDIAN_VAULT": "path",
    "AGENT_GURU_ROUTER": "text",
    "AGENT_GURU_ENGINE_URL": "text",
    "AGENT_GURU_ENGINE_REASONING": "text",
    "AGENT_GURU_ALLOW_CLOUD": "flag",
    "AGENT_GURU_CLOUD_MODEL": "text",
    "AGENT_GURU_FALLBACK_MODEL": "text",
    "AGENT_GURU_NO_DOWNLOAD": "flag",
    "AGENT_GURU_INJECTION_CLASSIFIER": "flag",
    "AGENT_GURU_INJECTION_MODEL_DIR": "path",
    "AGENT_GURU_INJECTION_TIMEOUT_S": "seconds",
    "AGENT_GURU_CODE_SANDBOX": "flag",
    "AGENT_GURU_SANDBOX_DISTRO": "text",
    "AGENT_GURU_BROWSER_TOOLS": "flag",
    "AGENT_GURU_BROWSER_VISIBLE": "flag",
    "AGENT_GURU_CLOUD_TTS": "text",
    "AGENT_GURU_CLOUD_STT": "text",
    "AGENT_GURU_OPENAI_TTS_MODEL": "text",
    "AGENT_GURU_OPENAI_STT_MODEL": "text",
    "CARTESIA_VOICE_GURU": "text",
    "CARTESIA_VOICE_MAYA": "text",
    "CARTESIA_MODEL": "text",
    "DEEPGRAM_MODEL": "text",
    "AGENT_GURU_IMAGES_DIR": "path",
    "AGENT_GURU_IMAGE_MODEL": "text",
    "AGENT_GURU_BROWSER_CHANNEL": "text",
    "AGENT_GURU_LOG_DIR": "path",
    "AGENT_GURU_VQA_MODEL": "text",
    "AGENT_GURU_VQA_OPENAI_MODEL": "text",
    "AGENT_GURU_VQA_GEMINI_MODEL": "text",
    "AGENT_GURU_OPENAI_MODEL": "text",
    "AGENT_GURU_DEEPSEEK_MODEL": "text",
    "KOKORO_MODEL_PATH": "path",
    "KOKORO_VOICES_PATH": "path",
}

#: Tables in the file that are not environment variables, each read by the
#: part of the assistant it configures: [mcp] by integration/mcp_tools.py.
SECTIONS = frozenset({"mcp"})

_SECRET = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|DSN|URI|CREDENTIAL", re.IGNORECASE)
_MAX_TEXT = 300


@dataclass
class SettingsReport:
    """What a settings file did: applied, already set in the environment, or refused (with why)."""

    path: str
    applied: dict[str, str] = field(default_factory=dict)
    overridden: list[str] = field(default_factory=list)
    refused: dict[str, str] = field(default_factory=dict)
    error: str | None = None


def _as_env_value(name: str, value: object) -> str:
    """The value as the variable's text, or ValueError saying why it does not fit."""
    kind = KNOWN_SETTINGS[name]
    if kind == "flag":
        if not isinstance(value, bool):
            msg = "must be true or false"
            raise ValueError(msg)
        return "1" if value else "0"
    if kind in {"seconds", "count"}:
        if isinstance(value, bool) or not isinstance(value, int | float):
            msg = "must be a number"
            raise ValueError(msg)
        if value <= 0:
            msg = "must be above 0"
            raise ValueError(msg)
        if kind == "count" and value != int(value):
            msg = "must be a whole number"
            raise ValueError(msg)
        return str(int(value)) if kind == "count" else str(value)
    if not isinstance(value, str) or not value.strip():
        msg = "must be non-empty text"
        raise ValueError(msg)
    if len(value) > _MAX_TEXT or any(ord(c) < 32 for c in value):
        msg = f"must be one line of at most {_MAX_TEXT} characters"
        raise ValueError(msg)
    return value.strip()


def apply_settings_file(path: Path, environ: dict[str, str] | None = None) -> SettingsReport:
    """Fill in environment variables from *path*; never raises, never overrides the environment.

    Args:
        path: The settings file (TOML). A missing file is not an error.
        environ: The environment to fill; os.environ by default.

    """
    env = os.environ if environ is None else environ
    report = SettingsReport(path=str(path))
    if not path.exists():
        return report
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        report.error = f"{type(exc).__name__}: {exc}"
        logger.warning("Settings file %s not used: %s", path, report.error)
        return report
    for name, value in data.items():
        if name in SECTIONS:
            continue
        if _SECRET.search(name):
            report.refused[name] = "secrets are not read from this file; set it in the environment or .env"
        elif name not in KNOWN_SETTINGS:
            report.refused[name] = "not a setting Agent Guru reads"
        else:
            try:
                text = _as_env_value(name, value)
            except ValueError as exc:
                report.refused[name] = str(exc)
                continue
            if name in env:
                report.overridden.append(name)
            else:
                env[name] = text
                report.applied[name] = text
    for name, why in report.refused.items():
        logger.warning("Setting %s in %s ignored: %s", name, path, why)
    if report.applied:
        logger.info("Settings from %s: %s", path, ", ".join(f"{k}={v}" for k, v in report.applied.items()))
    return report


def read_settings_section(path: Path, name: str) -> dict[str, object]:
    """The [*name*] table of the settings file, or {} when there is no file or no such table.

    Raises ValueError with the reason when the file cannot be read, so the
    caller can tell the owner rather than run with half a configuration.
    """
    if not path.exists():
        return {}
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        msg = f"{path} cannot be read: {type(exc).__name__}: {exc}"
        raise ValueError(msg) from exc
    section = data.get(name, {})
    if not isinstance(section, dict):
        msg = f"{path}: {name} must be a table ([{name}])"
        raise ValueError(msg)
    return section
