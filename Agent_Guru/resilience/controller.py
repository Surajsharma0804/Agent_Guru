"""Degradation controller for offline-first resilience."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from enum import Enum

logger = logging.getLogger(__name__)

try:
    import httpx

    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False

try:
    import psutil

    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False

NETWORK_CHECK_TIMEOUT_S = 2.0
NETWORK_CHECK_URL = "https://1.1.1.1"
RESOURCE_POLL_S = 5.0
RAM_THRESHOLD_MB = 512
CPU_THRESHOLD_PCT = 90.0
LLM_TIMEOUT_S = 3.0
# Consecutive healthy polls required before recovering a degradation mode.
# monitor_resources() is called once per RESOURCE_POLL_S, so this is roughly
# RECOVERY_STABLE_POLLS * RESOURCE_POLL_S seconds of sustained good health.
RECOVERY_STABLE_POLLS = 3


class DegradationMode(Enum):
    FULL = "full"
    DEGRADED = "degraded"
    MINIMAL = "minimal"
    SAFE = "safe"  # Emergency mode: only rule-based responses, no external calls


class DegradationController:
    """Controls degradation modes based on network and resource state."""

    #: Default failover chain. Cloud providers ("openai", "gemini") were
    #: removed: Agent_Guru is offline-first and the cloud adapters they would
    #: have needed no longer exist in Agent_Guru/llm/providers, so each one
    #: could only ever burn a full LLM_TIMEOUT_S (3 s) before the chain moved
    #: on - up to 6 wasted seconds on the path to the rule-based answer that
    #: was always going to be the result.
    DEFAULT_PROVIDERS = ("ollama", "rule_based")

    def __init__(
        self,
        providers: list[str] | None = None,
        provider_callables: dict[str, Callable[[str], Awaitable[str]]] | None = None,
    ) -> None:
        """Initialize the controller.

        Args:
            providers: Failover chain to try, in order. Defaults to
                DEFAULT_PROVIDERS.
            provider_callables: Real async ``(prompt) -> text`` callables per
                provider name. _call_provider()'s docstring already told
                callers to "inject real provider callables via the
                constructor" - but the constructor took no arguments at all,
                so there was no way to do it and the stub below was the only
                code path that ever ran.

        """
        self._mode = DegradationMode.FULL
        self._online = True
        self._llm_providers: list[str] = list(providers or self.DEFAULT_PROVIDERS)
        self._provider_callables: dict[str, Callable[[str], Awaitable[str]]] = dict(
            provider_callables or {},
        )
        # Tracks consecutive healthy polls for recovery hysteresis (see
        # monitor_resources()).
        self._consecutive_healthy_polls = 0

    async def detect_network_state(self) -> bool:
        """Detect network connectivity with 2s timeout."""
        if not _HTTPX_AVAILABLE:
            return True  # Assume online if httpx not available
        try:
            async with httpx.AsyncClient(timeout=NETWORK_CHECK_TIMEOUT_S) as client:
                resp = await client.head(NETWORK_CHECK_URL)
                self._online = resp.status_code < 500

        except Exception as e:
            logger.debug("Network check failed: %s", e)
            self._online = False
        return self._online

    def switch_mode(self, mode: DegradationMode) -> None:
        """Transition to a new degradation mode."""
        logger.info("Switching degradation mode: %s -> %s", self._mode.value, mode.value)
        self._mode = mode

    def get_mode(self) -> DegradationMode:
        return self._mode

    def monitor_resources(self) -> dict[str, float]:
        """Check system resources and adjust mode.

        Degrades mode immediately when resources are low (never worth
        delaying a safety response), and recovers back to FULL only once
        resources have been healthy for RECOVERY_STABLE_POLLS consecutive
        polls.

        BUG FIX: this used to recover the mode (SAFE->DEGRADED->FULL) on a
        single healthy poll, despite its own docstring claiming recovery
        happens "for sustained periods" -- the sustained check was never
        implemented. With RAM/CPU sitting right at RAM_THRESHOLD_MB /
        CPU_THRESHOLD_PCT, ordinary sampling noise could flip resources_ok
        every ~5s poll, thrashing the mode (and whatever behavior keys off
        it, e.g. which LLM providers are attempted) back and forth. Requiring
        several consecutive healthy polls before recovering removes that
        flapping while keeping degradation itself instant.
        """
        if not _PSUTIL_AVAILABLE:
            return {"ram_mb": 0.0, "cpu_pct": 0.0}
        ram_mb = psutil.virtual_memory().available / (1024 * 1024)
        cpu_pct = psutil.cpu_percent(interval=0.1)

        resources_ok = ram_mb >= RAM_THRESHOLD_MB and cpu_pct <= CPU_THRESHOLD_PCT
        resources_critical = ram_mb < RAM_THRESHOLD_MB / 2 or cpu_pct > 95.0

        if resources_critical:
            self._consecutive_healthy_polls = 0
            if self._mode != DegradationMode.SAFE:
                self.switch_mode(DegradationMode.SAFE)
        elif not resources_ok:
            self._consecutive_healthy_polls = 0
            if self._mode == DegradationMode.FULL:
                self.switch_mode(DegradationMode.DEGRADED)
        else:
            # Resources are healthy this poll - only recover once that has
            # held for RECOVERY_STABLE_POLLS consecutive polls, and require
            # a fresh streak of stability before each further recovery step.
            self._consecutive_healthy_polls += 1
            if self._consecutive_healthy_polls >= RECOVERY_STABLE_POLLS:
                if self._mode == DegradationMode.SAFE:
                    self.switch_mode(DegradationMode.DEGRADED)
                    self._consecutive_healthy_polls = 0
                elif self._mode == DegradationMode.DEGRADED:
                    self.switch_mode(DegradationMode.FULL)
                    self._consecutive_healthy_polls = 0

        return {"ram_mb": ram_mb, "cpu_pct": cpu_pct}

    async def llm_with_failover(
        self,
        prompt: str,
        providers: list[str] | None = None,
    ) -> str:
        """Try LLM providers in failover chain with 3s timeout each."""
        chain = providers or self._llm_providers
        for provider in chain:
            try:
                return await asyncio.wait_for(
                    self._call_provider(provider, prompt),
                    timeout=LLM_TIMEOUT_S,
                )
            except Exception:
                # `except (TimeoutError, Exception)` before: TimeoutError is
                # already an Exception, so the tuple was redundant. The log
                # also did not say WHICH provider failed, which is the one
                # thing worth knowing when a failover chain degrades.
                # asyncio.CancelledError derives from BaseException and still
                # propagates, so cancelling a request does not silently fall
                # through the whole chain.
                logger.exception("LLM provider %r failed; trying next in chain", provider)
        return self._rule_based_response(prompt)

    async def _call_provider(self, provider: str, prompt: str) -> str:
        """Call an LLM provider.

        Real providers are supplied through ``provider_callables`` on the
        constructor (or by overriding this method).

        This used to end with::

            return f"[{provider}] Response to: {prompt[:50]}"

        - a stub that FABRICATED an answer. Any caller wiring this controller
        in would have shipped "[ollama] Response to: what is the weather" to
        the user as though it were a model response, and llm_with_failover()
        would have reported success. A stub that returns plausible-looking
        text is worse than no stub: it cannot be detected downstream. It now
        raises instead, so an unconfigured provider fails over to the
        rule-based answer - which is honest about being offline - rather than
        inventing content.

        Raises:
            NotImplementedError: If no callable is configured for *provider*.

        """
        if provider == "rule_based":
            return self._rule_based_response(prompt)
        if self._mode == DegradationMode.SAFE:
            # Emergency mode: no external calls at all, whatever is configured.
            return self._rule_based_response(prompt)

        handler = self._provider_callables.get(provider)
        if handler is None:
            msg = (
                f"No LLM callable configured for provider {provider!r}. Pass "
                f"provider_callables={{{provider!r}: <async fn>}} to "
                f"DegradationController, or override _call_provider()."
            )
            raise NotImplementedError(msg)
        return await handler(prompt)

    def _rule_based_response(self, prompt: str) -> str:
        return f"[offline] I'm operating in offline mode. Query: {prompt[:50]}"
