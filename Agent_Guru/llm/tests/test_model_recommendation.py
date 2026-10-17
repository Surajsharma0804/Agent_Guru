"""The first-start model recommendation picks a model that can call tools and fits this GPU."""

from __future__ import annotations

from Agent_Guru.llm.model_catalog import ModelEntry, recommend

_CHAT = ["completion", "tools"]


def _model(name, size, fit, caps=_CHAT):
    return ModelEntry(name=name, size_mb=size, capabilities=list(caps), gpu_fit=fit, needs_mb=size * 1.2 + 500)


def test_the_largest_model_that_fits_and_calls_tools_wins():
    best, why = recommend([_model("small:2b", 1500, "fits"), _model("mid:4b", 2600, "fits"),
                           _model("big:9b", 9600, "partial")])
    assert best.name == "mid:4b" and "fits" in why  # nosec B101


def test_models_that_cannot_call_tools_are_never_chosen():
    best, _ = recommend([_model("embed", 300, "fits", ["embedding"]), _model("vision:4b", 2500, "fits", ["completion", "vision"]),
                         _model("chat:2b", 1500, "fits")])
    assert best.name == "chat:2b"  # nosec B101
    none, why = recommend([_model("embed", 300, "fits", ["embedding"])])
    assert none is None and "ollama pull" in why  # nosec B101


def test_when_nothing_fits_the_least_spilling_model_is_chosen():
    best, why = recommend([_model("big:9b", 9600, "partial"), _model("mid:4b", 5000, "cpu")])
    assert best.name == "mid:4b" and "spills the least" in why  # nosec B101


def test_without_a_gpu_the_smallest_runs_on_the_cpu():
    best, why = recommend([_model("a", 5000, ""), _model("b", 1500, "")])
    assert best.name == "b" and "CPU" in why  # nosec B101
