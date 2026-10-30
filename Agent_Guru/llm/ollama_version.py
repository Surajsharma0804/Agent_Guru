"""Which Ollama version the assistant was measured on, and a startup note when another is installed.

The Ollama desktop app updates itself when it starts (0.40.3 to 0.40.13 during one session here),
and the README's speeds and tool results belong to the version they were measured on. Nothing said
which version was running, so a change in speed or tool behaviour after an update had no visible
cause. The check never blocks startup: an Ollama that does not answer is reported and the start goes on.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

#: The version the README's "Choosing a model" figures were measured on.
TESTED_OLLAMA_VERSION = "0.40.13"
#: Seconds to wait for /api/version. Ollama answers in milliseconds when it is up.
TIMEOUT_S = 3.0


def check_ollama_version(host: str = "http://127.0.0.1:11434", *, client: Any = None) -> str | None:
    """Log the installed Ollama version against the tested one, once; return it, or None if unknown.

    127.0.0.1, not localhost: on Windows each new connection to localhost tried IPv6 first and cost
    about 2 s, measured.
    """
    import httpx

    url = host.rstrip("/").replace("://localhost", "://127.0.0.1") + "/api/version"
    own = client is None
    client = client or httpx.Client(timeout=TIMEOUT_S)
    try:
        found = str(client.get(url, timeout=TIMEOUT_S).json().get("version") or "")
    except (httpx.HTTPError, ValueError, AttributeError) as exc:
        logger.info("Ollama version not checked: %s did not answer (%s)", url, type(exc).__name__)
        return None
    finally:
        if own:
            client.close()
    if not found:
        logger.info("Ollama version not checked: %s gave no version", url)
        return None
    if found == TESTED_OLLAMA_VERSION:
        logger.info("Ollama %s, the version the README's measurements were made on", found)
    else:
        logger.warning(
            "Ollama %s is installed; the README's speeds and tool results were measured on %s. "
            "If replies are slower or tools behave differently, this update is a likely cause.",
            found, TESTED_OLLAMA_VERSION,
        )
    return found
