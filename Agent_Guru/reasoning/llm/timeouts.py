"""Timing policy for local LLM inference.

AGENT_GURU is offline-first: the normal deployment is a local Ollama model
running on whatever machine the user owns. That machine frequently has no
usable GPU and a modest CPU, and on such hardware a small model answering a
planning prompt routinely takes tens of seconds - loading the model off disk
on the first call takes longer still.

Every LLM timeout in this codebase was originally a bare literal sized for a
fast machine: 5 s for plan generation, 1 s for intent fallback, 15 s for a
generate call, 10 s to find a server that may still be loading a model. On
CPU-only hardware those budgets do not expire because something is wrong -
they expire because the machine is slow, and the user sees a timeout error
instead of an answer. A local-first assistant that cannot wait for its own
local model is not usable on the hardware it was built for.

The defaults here are therefore sized for CPU-only inference on modest
hardware, and every one of them is overridable by environment variable so a
fast machine can tighten them and a very slow one can loosen them further:

===========================================  ==========================
Environment variable                         Governs
===========================================  ==========================
``OLLAMA_CONNECT_TIMEOUT_SECONDS``           TCP connect to the server
``OLLAMA_TIMEOUT_SECONDS``                   One generate call
``OLLAMA_START_TIMEOUT_SECONDS``             Waiting for the server
``AGENT_GURU_PLAN_TIMEOUT_SECONDS``          One plan-generation attempt
``AGENT_GURU_INTENT_TIMEOUT_SECONDS``        One intent-fallback call
===========================================  ==========================

``OLLAMA_TIMEOUT_SECONDS`` already existed - the reasoning test conftest sets
it to 2 with the comment "so any accidental real call fails in 2s, not 300s" -
but nothing in the production code ever read it, so that hardening did
nothing. Reading it here makes the test suite's intent real.

Connect timeout is deliberately NOT generous. Failing to open a TCP socket to
a local port is not slow on any hardware; it means nothing is listening, and
that should be reported in seconds rather than waited out.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

#: Opening a local TCP socket does not get slower on a weak machine - either
#: something is listening or nothing is. Fail fast and say so.
DEFAULT_CONNECT_TIMEOUT_S = 5.0

#: One generate call. A 4B model on a CPU emits single-digit tokens per
#: second, so a few hundred tokens of plan JSON is comfortably a minute.
DEFAULT_GENERATE_TIMEOUT_S = 180.0

#: Waiting for the Ollama server to answer. The first request after a cold
#: start also pays for reading the model weights off disk.
DEFAULT_START_TIMEOUT_S = 120.0

#: One plan-generation attempt. Generation plus JSON parsing; the caller
#: retries, so the total budget is a multiple of this.
DEFAULT_PLAN_TIMEOUT_S = 180.0

#: One intent-classification fallback call. Shorter than a plan because the
#: prompt and the expected answer are both small, but still far above the
#: 1 s that was hard-coded - no local model classifies intent in a second on
#: a CPU.
DEFAULT_INTENT_TIMEOUT_S = 60.0


def _env_float(name: str, default: float) -> float:
    """Read a positive float from the environment, falling back on default.

    A malformed or non-positive value is reported and ignored rather than
    raised: a typo in an environment variable should not stop the assistant
    from starting, and silently accepting ``0`` would turn every LLM call into
    an instant timeout - the hardest kind of misconfiguration to diagnose.
    """
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        logger.warning(
            "%s=%r is not a number; using the default of %.1fs", name, raw, default
        )
        return default
    if value <= 0:
        logger.warning(
            "%s=%r must be positive; using the default of %.1fs", name, raw, default
        )
        return default
    return value


def connect_timeout() -> float:
    """Seconds to wait for a TCP connection to the local LLM server."""
    return _env_float("OLLAMA_CONNECT_TIMEOUT_SECONDS", DEFAULT_CONNECT_TIMEOUT_S)


def generate_timeout() -> float:
    """Seconds to wait for one completed generate call."""
    return _env_float("OLLAMA_TIMEOUT_SECONDS", DEFAULT_GENERATE_TIMEOUT_S)


def start_timeout() -> float:
    """Seconds to wait for the LLM server to become available."""
    return _env_float("OLLAMA_START_TIMEOUT_SECONDS", DEFAULT_START_TIMEOUT_S)


def plan_timeout() -> float:
    """Seconds to wait for one plan-generation attempt."""
    return _env_float("AGENT_GURU_PLAN_TIMEOUT_SECONDS", DEFAULT_PLAN_TIMEOUT_S)


def intent_timeout() -> float:
    """Seconds to wait for one intent-classification fallback call."""
    return _env_float("AGENT_GURU_INTENT_TIMEOUT_SECONDS", DEFAULT_INTENT_TIMEOUT_S)
