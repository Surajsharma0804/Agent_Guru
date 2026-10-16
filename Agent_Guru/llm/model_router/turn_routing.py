"""The model router, fed with this machine's real models and used for each answer.

ModelRouter (router.py) analysed tasks, scored models and learned from
outcomes, but nothing registered a real model with it and nothing asked
it anything: every answer went to OLLAMA_MODEL. This connects it:

* the registry is filled from the model catalog (what Ollama actually
  has, with its capabilities), plus AGENT_GURU_CLOUD_MODEL when the owner
  allowed the cloud and set that provider's key;
* each answer asks select_model() for the transcript;
* each finished turn reports back (success, seconds), and at start the
  recent turn records are replayed into the learning engine, so routing
  learns from this owner's turns rather than from defaults.

Two rules sit on top, from measurement on this 4 GB laptop:

* A local model that is not loaded is chosen only for a hard question:
  swapping models cost 17 to 19 s, more than any answer gains. "Hard" is
  the analyser's high complexity.
* The cloud model is used only for hard questions and only when allowed
  (AGENT_GURU_ALLOW_CLOUD); the owner's words then leave the machine.

Off unless AGENT_GURU_ROUTER = "auto": with it off every answer uses
OLLAMA_MODEL exactly as before.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

_LOADED_TTL_S = 5.0


def enabled() -> bool:
    return os.environ.get("AGENT_GURU_ROUTER", "").strip().lower() == "auto"


class TurnRouter:
    """One per assistant; build() once, then choose() per answer and record() per turn."""

    def __init__(self) -> None:
        self._router: Any = None
        self._local: set[str] = set()
        self._cloud: str = ""
        self._sizes: dict[str, float] = {}
        self._loaded: tuple[float, set[str]] = (0.0, set())

    def build(self, trace_store: Any = None) -> bool:
        """Register the installed models (and the allowed cloud model); False when there is nothing to route."""
        from Agent_Guru.llm.model_catalog import installed
        from Agent_Guru.llm.model_router.models import ModelCapability, ModelMetadata, Provider
        from Agent_Guru.llm.model_router.router import ModelRouter

        try:
            entries = installed(timeout=5.0)
        except OSError as exc:
            logger.warning("Model routing off: %s", exc)
            return False
        router = ModelRouter(prefer_local=True)
        caps = {"tools": ModelCapability.FUNCTION_CALLING, "vision": ModelCapability.VISION}
        for e in entries:
            capabilities = {ModelCapability.CONVERSATION, ModelCapability.REASONING, ModelCapability.CREATIVE_WRITING}
            capabilities |= {caps[c] for c in e.capabilities if c in caps}
            if e.context_length >= 32_000:
                capabilities.add(ModelCapability.LONG_CONTEXT)
            router.register_model(ModelMetadata(
                model_id=e.name, name=e.name, provider=Provider.OLLAMA, capabilities=capabilities,
                max_tokens=max(1, e.context_length or 4096),
                # A first guess the outcomes replace: bigger models answer slower here.
                average_latency_ms=max(500.0, e.size_mb * 0.6),
                metadata={"size_mb": e.size_mb, "gpu_fit": e.gpu_fit},
            ))
            self._local.add(e.name)
            self._sizes[e.name] = e.size_mb
        cloud = os.environ.get("AGENT_GURU_CLOUD_MODEL", "").strip()
        if cloud:
            from Agent_Guru.llm.providers.openai_compatible import endpoint_for

            if endpoint_for(cloud) is not None:
                provider = (Provider.ANTHROPIC if cloud.startswith("claude-")
                            else Provider.GOOGLE if cloud.startswith("gemini-") else Provider.OPENAI)
                router.register_model(ModelMetadata(
                    model_id=cloud, name=cloud, provider=provider, average_latency_ms=1500.0,
                    capabilities={ModelCapability.CONVERSATION, ModelCapability.REASONING,
                                  ModelCapability.FUNCTION_CALLING, ModelCapability.LONG_CONTEXT},
                ))
                self._cloud = cloud
        self._router = router
        if trace_store is not None:
            self._replay(trace_store)
        return bool(self._local)

    def _replay(self, trace_store: Any, limit: int = 300) -> None:
        try:
            turns = trace_store.recent(limit=limit)
        except Exception:
            return
        replayed = 0
        for turn in turns:
            if turn.model and turn.heard and turn.outcome in ("success", "failure"):
                self.record(turn.model, turn.heard, turn.outcome == "success", turn.seconds * 1000)
                replayed += 1
        logger.info("Model routing: %d models, %d past turns learned from", len(self._local) + bool(self._cloud), replayed)

    async def _loaded_models(self) -> set[str]:
        stamp, names = self._loaded
        if time.monotonic() - stamp < _LOADED_TTL_S:
            return names
        try:
            import httpx

            from Agent_Guru.llm.model_catalog import _host

            async with httpx.AsyncClient(timeout=0.5) as client:
                body = (await client.get(f"{_host()}/api/ps")).json()
            names = {m.get("name") or m.get("model") for m in body.get("models") or []}
        except Exception:
            names = set()
        self._loaded = (time.monotonic(), names)
        return names

    async def choose(self, transcript: str, default: str) -> tuple[str, str]:
        """(model, why) for an answer to *transcript*; (default, "") when routing is off or has no better choice.

        The router's own select_model() scored on cost and latency alone and
        sent a hard comparison question to gemma3:4b, the smaller vision
        model, so the tier is decided here and the router supplies the
        analysis and the outcomes it has learned:

        * high complexity: the allowed cloud model, else the largest local model;
        * low complexity: of the models already loaded, the one with the best
          recorded success per second for this task type (smallest when there
          are fewer than 3 outcomes), so a quick question never waits for a swap;
        * otherwise the configured model.
        """
        if self._router is None or not transcript.strip():
            return default, ""
        from Agent_Guru.llm.model_router.models import TaskSpecification

        try:
            analysis = self._router._analyzer.analyze(TaskSpecification(content=transcript[:2000]))
        except Exception as exc:
            logger.debug("Routing fell back to %s: %s", default, exc)
            return default, ""
        kind = analysis.task_type
        if analysis.complexity == "high":
            if self._cloud:
                return self._cloud, f"cloud for a {kind.value} question of high complexity"
            strongest = max(self._local, key=lambda m: self._sizes.get(m, 0.0), default=default)
            return (strongest, f"largest local model for a {kind.value} question") if strongest != default else (default, "")
        if analysis.complexity == "low":
            loaded = [m for m in self._local if m in await self._loaded_models()]
            if not loaded:
                return default, ""

            def score(model: str) -> float:
                metrics = self._router._monitor.get_metrics(model, kind)
                if metrics.sample_size >= 3:
                    return metrics.success_rate / (1.0 + metrics.average_latency_ms / 1000.0)
                return 1.0 / (1.0 + self._sizes.get(model, 0.0) / 1000.0)

            best = max(loaded, key=score)
            return (best, f"loaded model best at quick {kind.value} turns") if best != default else (default, "")
        return default, ""

    def record(self, model: str, transcript: str, success: bool, latency_ms: float) -> None:
        if self._router is None or not model or not transcript.strip():
            return
        from Agent_Guru.llm.model_router.models import TaskSpecification

        try:
            task_type = self._router._analyzer.analyze(TaskSpecification(content=transcript[:2000])).task_type
            self._router.record_outcome(model_id=model, task_type=task_type, success=success, latency_ms=latency_ms)
        except Exception:
            logger.debug("Could not record a routing outcome", exc_info=True)
