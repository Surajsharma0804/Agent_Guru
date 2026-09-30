"""Generation options for every call this codebase makes to Ollama.

AGENT_GURU talks to one local Ollama server through four separate clients:
the voice answer (``llm/providers/ollama_adapter.py``), the reasoning
provider (``reasoning/llm/providers/ollama_provider.py``), the intent LLM
fallback (``reasoning/intent/llm_fallback.py``) and ``OllamaServer``
(``reasoning/llm/ollama_server.py``). Each one built its own ``options``
dict, and they disagreed:

===========================  =========  =======  ==========
Client                       num_ctx    num_gpu  num_thread
===========================  =========  =======  ==========
voice answer (adapter)       1024       99       8
reasoning provider           (unset)    99       (unset)
intent LLM fallback          (unset)    (unset)  (unset)
OllamaServer                 (unset)    (unset)  (unset)
===========================  =========  =======  ==========

That cost the user tens of seconds per spoken question, measured on an RTX
2050 (4 GB) with gemma3:4b:

* An unset ``num_ctx`` means "whatever the server was started with". That is
  not a stable default: the Ollama desktop app's context-length setting
  exports ``OLLAMA_CONTEXT_LENGTH`` to the server, and on the development
  machine it was 131072. The intent fallback therefore loaded the model with a
  128K context, 61% of it on the CPU, at 7.6 tokens/s.
* Ollama reloads the model whenever a request's context size or GPU layer
  count differs from the loaded one. Every voice turn made two requests with
  different options (the fallback, then the answer), so every turn loaded the
  model twice, 8-18 s each time.
* ``num_gpu`` turned out to matter as much as ``num_ctx``. Left unset,
  Ollama's own placement kept 54% of gemma3:4b on the CPU at every context
  size from 2048 to 8192 (about 8 tokens/s). With ``num_gpu=99`` the whole
  model fit on the GPU at 4096 (3727 MiB) and ran at 33 tokens/s.

One spoken "what is the capital of France" took 45.6 s. The answer itself
needed about 3 s. The rest was spent waiting on the fallback's 128K-context
call and reloading the model.

So every client takes its options from here. The values are sized by
measurement (see ``DEFAULT_NUM_CTX``), and each one can be overridden from
the environment as an escape hatch for advanced users. An ordinary user never
needs to set anything:

======================================  ==========================================
Environment variable                    Governs
======================================  ==========================================
``AGENT_GURU_NUM_CTX``                  Context window sent with every request
``AGENT_GURU_NUM_GPU``                  Model layers Ollama is asked to put on GPU
``AGENT_GURU_SPOKEN_REPLY_TOKENS``      Longest reply the voice pipeline generates
``OLLAMA_MODEL``                        Model every client asks for
======================================  ==========================================

``OLLAMA_CONTEXT_LENGTH`` is deliberately NOT read. It configures the
server, it is exactly the setting that silently made this 131072, and
honouring it would bring the bug back on every machine where it is set high.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

#: Model asked for when ``OLLAMA_MODEL`` is not set.
#:
#: This name used to be written out in ten modules, each with its own reading
#: of ``OLLAMA_MODEL``: most stripped it, the intent engine did not, so a blank
#: value sent the model name "" from one client and the default from the
#: others. Changing the model meant finding every copy, and a missed copy kept
#: asking Ollama for a model that was no longer pulled.
DEFAULT_OLLAMA_MODEL = "gemma3:4b"

#: The top-level ``think`` field of every chat and generate request.
#:
#: Thinking models (gemma4, qwen3, deepseek-r1) reason before they answer when
#: the request does not say otherwise, and the reasoning counts against
#: ``num_predict``. Measured with gemma4:latest on a 4 GB RTX 2050: with the
#: voice pipeline's 100-token reply cap, every token went to reasoning and the
#: spoken answer came back empty, "What is the capital of France?" took 21 s
#: and Guru said nothing; the intent classifier spent 5.4 s and returned an
#: empty string instead of JSON. With ``think`` false the same requests took
#: 1.2 s and 0.7 s and answered correctly. Nothing in this codebase reads the
#: reasoning, and a spoken answer cannot wait for it. Ollama accepts false for
#: models that cannot think, so it is sent to every model.
OLLAMA_THINK = False


def ollama_model() -> str:
    """Model name every Ollama client sends: ``OLLAMA_MODEL`` if set, else the default."""
    return os.environ.get("OLLAMA_MODEL", "").strip() or DEFAULT_OLLAMA_MODEL

#: Context window sent with every Ollama request.
#:
#: Sized to the largest prompt the voice pipeline builds, not to the GPU.
#: Measured with gemma3:4b's own tokenizer (Ollama's prompt_eval_count):
#:
#: * turn 1, no history: 1619 tokens. The system prompt alone is about 1600,
#:   so the old 1024 could never have held one. Ollama silently raises
#:   anything below 2048 to 2048, which is the only reason it worked.
#: * 12 typical exchanges plus a web snippet: 2352 tokens.
#: * the orchestrator's history budget (2900 estimated tokens) actually
#:   binding, plus a web snippet: 4257 tokens.
#:
#: At 4096 that worst case came back with prompt_eval_count 4039: Ollama had
#: dropped 218 tokens of conversation with no error. 6144 holds the 4257-token
#: worst case plus a full spoken reply with room to spare.
#:
#: Why this is a fixed value and not detected from VRAM: gemma3's KV cache is
#: small at these sizes (3685 MiB total at 2048, 3769 MiB at 6144, 3811 MiB at
#: 8192, all fully on a 4 GB GPU), so context size is not what decides whether
#: the model fits. A 24 GB card given 8192 would run exactly the same prompts,
#: because the pipeline never builds one larger than about 4.3K tokens. A
#: card too small for the weights is not rescued by a smaller window either.
DEFAULT_NUM_CTX = 6144

#: Ollama raises any smaller request to this (measured on 0.32.5: num_ctx=1024
#: loads with context 2048), so asking for less only misreports what runs.
MIN_NUM_CTX = 2048

#: Ask Ollama to put every layer on the GPU. Ollama caps this at what the model
#: has. Without it, Ollama's own placement left 54% of gemma3:4b on the CPU
#: of a 4 GB card that holds all of it: 5.9 s instead of 2.6 s for the same
#: answer.
DEFAULT_NUM_GPU = 99

#: Longest reply, in tokens, the voice pipeline asks the model for.
#:
#: This was 400, which in practice meant no limit. Measured with the real
#: system prompt on gemma3:4b, "tell me about the history of India" ran 228
#: tokens, 163 words, about 65 s of speech, and 14-27 s of generation on a
#: 4 GB laptop GPU. Every token is paid for twice, once in generation and again
#: in speech, and the user can do nothing until both are over.
#:
#: 100 tokens is about 70 words, roughly 28 s of speech at a normal speaking
#: rate. That leaves room for the 2-4 sentences the companion prompt asks for
#: while bounding generation at about 3 s on a cool GPU and about 12 s on a
#: throttled or CPU-only one. Short factual answers never reach it: "what is the
#: capital of France" is 43 tokens. The orchestrator trims a capped reply back
#: to its last full sentence, so the cap never ends speech mid-word.
DEFAULT_SPOKEN_REPLY_TOKENS = 100


def _env_int(name: str, default: int, minimum: int) -> int:
    """Read an integer from the environment, falling back on default.

    Same contract as ``timeouts._env_float``: a typo must not stop the
    assistant from starting, so a malformed or out-of-range value is logged
    and ignored rather than raised.
    """
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("%s=%r is not an integer; using the default of %d", name, raw, default)
        return default
    if value < minimum:
        logger.warning(
            "%s=%r is below the minimum of %d; using the default of %d",
            name, raw, minimum, default,
        )
        return default
    return value


def context_window() -> int:
    """Context window (tokens) sent with every Ollama request."""
    return _env_int("AGENT_GURU_NUM_CTX", DEFAULT_NUM_CTX, MIN_NUM_CTX)


def gpu_layers() -> int:
    """Model layers Ollama is asked to offload to the GPU. 0 means CPU only."""
    return _env_int("AGENT_GURU_NUM_GPU", DEFAULT_NUM_GPU, 0)


def spoken_reply_tokens() -> int:
    """Longest reply, in tokens, the voice pipeline asks the model for."""
    return _env_int("AGENT_GURU_SPOKEN_REPLY_TOKENS", DEFAULT_SPOKEN_REPLY_TOKENS, 1)


def ollama_options(
    *,
    num_predict: int | None,
    temperature: float | None = None,
    top_p: float | None = None,
    stop: list[str] | None = None,
) -> dict[str, Any]:
    """Build the ``options`` object for one Ollama generate or chat request.

    The load-affecting options (``num_ctx``, ``num_gpu``) come from this
    module and nowhere else. If two clients sent different values, Ollama
    would reload the model between their requests. Sampling options stay
    per call because they really do differ: the intent classifier wants
    temperature 0, a conversation does not. ``num_predict=None`` leaves the
    reply length to Ollama.
    """
    options: dict[str, Any] = {
        "num_ctx": context_window(),
        "num_gpu": gpu_layers(),
    }
    if num_predict is not None:
        options["num_predict"] = num_predict
    if temperature is not None:
        options["temperature"] = temperature
    if top_p is not None:
        options["top_p"] = top_p
    if stop:
        options["stop"] = stop
    return options


def context_fits(prompt_tokens: int | None, num_predict: int | None, *, source: str) -> bool:
    """Report, loudly, a request that did not fit the context window.

    Ollama never errors on an oversized prompt. It drops the start of the
    conversation and answers anyway. The measured case: a 4257-token prompt
    at num_ctx 4096 came back with prompt_eval_count 4039, and the reply
    looked normal. The assistant then answers from a conversation it can no
    longer see, and nothing tells anyone why.

    ``prompt_tokens`` is Ollama's ``prompt_eval_count`` for the request. If it
    plus the reply budget exceeds the window, either the prompt was already
    cut or the reply had no room. Logged at WARNING with the numbers needed
    to fix it. Returns False in that case so callers can record it.
    """
    if not prompt_tokens:
        return True
    num_ctx = context_window()
    needed = prompt_tokens + (num_predict or 0)
    if needed <= num_ctx:
        return True
    logger.warning(
        "%s: prompt of %d tokens plus a %d-token reply budget does not fit the "
        "%d-token context window. Ollama drops the start of the prompt without "
        "an error, so this answer may ignore part of the conversation. Shorten "
        "the prompt or raise AGENT_GURU_NUM_CTX.",
        source, prompt_tokens, num_predict or 0, num_ctx,
    )
    return False
