"""Core Reasoning Engine for Agent_Guru.

Provides multi-step chain-of-thought reasoning, intent disambiguation,
knowledge retrieval, and goal decomposition.

Quick start::

    from Agent_Guru.reasoning import ReasoningEngine

    engine = ReasoningEngine()
    result = engine.analyze("What is the weather?", memory_context=None)

Note: ReasoningEngine requires ``structlog`` and ``opentelemetry-api`` to be
installed. Install with: ``pip install structlog opentelemetry-api``
"""

__version__ = "0.1.0"


def __getattr__(name: str):  # noqa: ANN201
    """Lazy-load ReasoningEngine to avoid crashing on missing optional deps."""
    if name == "ReasoningEngine":
        try:
            from Agent_Guru.reasoning.engine import ReasoningEngine  # noqa: PLC0415
            globals()["ReasoningEngine"] = ReasoningEngine
            return ReasoningEngine
        except ImportError as exc:
            raise ImportError(
                f"ReasoningEngine requires optional dependencies: {exc}. "
                "Install with: pip install structlog opentelemetry-api"
            ) from exc
    raise AttributeError(f"module 'Agent_Guru.reasoning' has no attribute {name!r}")


__all__ = ["ReasoningEngine"]
