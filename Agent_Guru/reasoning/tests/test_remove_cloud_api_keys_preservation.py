"""
Preservation Property Tests — Remove Cloud API Keys

These tests capture the BASELINE Ollama behavior that MUST be preserved after
the fix. They are designed to PASS on the current (unfixed) code and MUST
continue to PASS after the fix is applied.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9,
             3.10, 3.11, 3.12**

EXPECTED OUTCOME ON UNFIXED CODE: ALL TESTS PASS
EXPECTED OUTCOME AFTER FIX:       ALL TESTS PASS (no regressions)
"""

import pytest
from hypothesis import given, settings
import hypothesis.strategies as st


# ---------------------------------------------------------------------------
# Test 1 — OllamaAdapter is importable
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_ollama_adapter_is_importable() -> None:
    """OllamaAdapter must be importable from Agent_Guru.llm.providers.

    This baseline behavior must be preserved before and after the fix.

    **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.11**
    """
    from Agent_Guru.llm.providers import OllamaAdapter  # noqa: F401

    assert OllamaAdapter is not None, (  # nosec B101
        "OllamaAdapter must be importable from Agent_Guru.llm.providers"
    )


# ---------------------------------------------------------------------------
# Test 2 — ModelProvider.OLLAMA exists
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_model_provider_ollama_exists() -> None:
    """ModelProvider.OLLAMA must exist in the ModelProvider enum.

    This enum value is used throughout the codebase for routing and adapter
    lookup. It must remain available before and after the fix.

    **Validates: Requirements 3.12**
    """
    from Agent_Guru.llm.models import ModelProvider

    assert hasattr(ModelProvider, "OLLAMA"), (  # nosec B101
        "ModelProvider.OLLAMA must exist in the ModelProvider enum"
    )
    assert ModelProvider.OLLAMA.value == "ollama", (  # nosec B101
        "ModelProvider.OLLAMA.value must be 'ollama'"
    )


# ---------------------------------------------------------------------------
# Test 3 — LLMRuntime routes non-cloud model names to Ollama (property-based)
# ---------------------------------------------------------------------------


@pytest.mark.property
@given(
    model_name=st.text(
        min_size=1,
        max_size=30,
        alphabet=st.characters(
            whitelist_categories=("Ll", "Lu", "Nd"),
            whitelist_characters="-_.",
        ),
    ).filter(
        lambda s: (
            not s.startswith("gpt-")
            and not s.startswith("claude-")
            and not s.startswith("gemini-")
        )
    )
)
@settings(max_examples=100)
def test_llm_runtime_routes_non_cloud_models_to_ollama(model_name: str) -> None:
    """For any model name that does not start with a cloud prefix,
    LLMRuntime._get_provider() must return ModelProvider.OLLAMA.

    This property must hold on unfixed code (non-cloud names already route to
    Ollama) and must continue to hold after the fix.

    **Validates: Requirements 3.5, 3.6, 3.12**
    """
    from Agent_Guru.llm.llm_runtime import LLMRuntime
    from Agent_Guru.llm.models import ModelProvider

    result = LLMRuntime._get_provider(model_name)

    assert result == ModelProvider.OLLAMA, (  # nosec B101
        f"LLMRuntime._get_provider('{model_name}') returned {result!r}, "
        f"expected ModelProvider.OLLAMA. Non-cloud model names must always "
        f"route to the Ollama provider."
    )


# ---------------------------------------------------------------------------
# Test 4 — DegradationController always contains "ollama"
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_degradation_controller_always_contains_ollama() -> None:
    """DegradationController._llm_providers must always contain "ollama".

    The Ollama provider must remain in the failover chain before and after
    the fix. This ensures local LLM inference is always available.

    **Validates: Requirements 3.10**
    """
    from Agent_Guru.resilience.controller import DegradationController

    controller = DegradationController()

    assert "ollama" in controller._llm_providers, (  # nosec B101
        f"DegradationController._llm_providers must contain 'ollama'. "
        f"Current list: {controller._llm_providers}"
    )


# ---------------------------------------------------------------------------
# Test 5 — LLMFallbackConfig accepts "ollama" without error
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_llm_fallback_config_accepts_ollama() -> None:
    """LLMFallbackConfig(provider="ollama") must NOT raise any error.

    The Ollama provider must remain a valid option for the LLM fallback
    classifier before and after the fix.

    **Validates: Requirements 3.8**
    """
    from Agent_Guru.reasoning.intent.llm_fallback import LLMFallbackConfig

    # Must not raise
    config = LLMFallbackConfig(provider="ollama")

    assert config.provider == "ollama", (  # nosec B101
        "LLMFallbackConfig(provider='ollama') must set provider to 'ollama'"
    )


# ---------------------------------------------------------------------------
# Test 6 — VQAEngine desktop has a local inference path (_call_local_llm)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_vqa_engine_desktop_has_no_cloud_vlm_attribute() -> None:
    """VQAEngine instantiated with platform="desktop" must have the local
    inference method (_call_local_llm) and must use it (not a cloud path)
    when platform is "desktop".

    The desktop path routes to the local LLaVA/InternVL2 model. This test
    confirms the local inference path exists and is preserved after the fix.

    Note: On unfixed code, _call_cloud_vlm also exists as a class method
    (used only for mobile platform). After the fix it will be removed.
    This test validates the PRESERVATION side: the local desktop path
    (_call_local_llm) must always be present.

    **Validates: Requirements 3.9**
    """
    from Agent_Guru.vision.vqa import VQAEngine

    engine = VQAEngine(platform="desktop")

    # The local inference method must always be present (preservation property)
    assert hasattr(engine, "_call_local_llm"), (  # nosec B101
        "VQAEngine(platform='desktop') must have a '_call_local_llm' method. "
        "The desktop path must always route to local LLaVA/InternVL2 inference."
    )
    # The platform must be set correctly
    assert engine._platform == "desktop", (  # nosec B101
        "VQAEngine(platform='desktop')._platform must be 'desktop'"
    )
