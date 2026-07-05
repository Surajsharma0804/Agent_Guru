"""Degradation controller for offline-first resilience."""

from __future__ import annotations

import asyncio
import logging
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


class DegradationMode(Enum):
    FULL = "full"
    DEGRADED = "degraded"
    MINIMAL = "minimal"
    SAFE = "safe"  # Emergency mode: only rule-based responses, no external calls


class DegradationController:
    """Controls degradation modes based on network and resource state."""

    def __init__(self) -> None:
        self._mode = DegradationMode.FULL
        self._online = True
        self._llm_providers: list[str] = ["ollama", "openai", "gemini", "rule_based"]

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

        Degrades mode when resources are low, and recovers back to FULL
        when resources normalise for sustained periods.
        """
        if not _PSUTIL_AVAILABLE:
            return {"ram_mb": 0.0, "cpu_pct": 0.0}
        ram_mb = psutil.virtual_memory().available / (1024 * 1024)
        cpu_pct = psutil.cpu_percent(interval=0.1)

        resources_ok = ram_mb >= RAM_THRESHOLD_MB and cpu_pct <= CPU_THRESHOLD_PCT
        resources_critical = ram_mb < RAM_THRESHOLD_MB / 2 or cpu_pct > 95.0

        if resources_critical:
            if self._mode != DegradationMode.SAFE:
                self.switch_mode(DegradationMode.SAFE)
        elif not resources_ok:
            if self._mode == DegradationMode.FULL:
                self.switch_mode(DegradationMode.DEGRADED)
        else:
            # Resources are healthy — recover toward FULL
            if self._mode == DegradationMode.SAFE:
                self.switch_mode(DegradationMode.DEGRADED)
            elif self._mode == DegradationMode.DEGRADED:
                self.switch_mode(DegradationMode.FULL)

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
            except (TimeoutError, Exception):
                logger.exception("Provider failed")
        return self._rule_based_response(prompt)

    async def _call_provider(self, provider: str, prompt: str) -> str:
        """Call an LLM provider.

        NOTE: This is a stub implementation. In production, this should
        delegate to the actual FailoverRouter or provider adapters.
        Override this method or inject real provider callables via the
        constructor to enable real LLM calls in degradation mode.
        """
        await asyncio.sleep(0)
        if provider == "rule_based":
            return self._rule_based_response(prompt)
        if self._mode == DegradationMode.SAFE:
            return self._rule_based_response(prompt)
        return f"[{provider}] Response to: {prompt[:50]}"

    def _rule_based_response(self, prompt: str) -> str:
        return f"[offline] I'm operating in offline mode. Query: {prompt[:50]}"
