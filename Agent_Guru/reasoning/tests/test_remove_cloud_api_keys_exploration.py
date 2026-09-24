"""Offline-first guarantees for the LLM provider surface.

This file began life as a set of "bug condition exploration" tests that were
DESIGNED TO FAIL until a cloud-removal refactor was completed. That refactor
was started and abandoned: the Gemini and DeepSeek providers were deleted, but
OpenAI and Anthropic were not - they are still present, still tested, and
still wired into llm_fallback.py. So the file sat permanently red, asserting a
deletion that the rest of the repository contradicted.

It now asserts the architecture that was actually adopted (2026-09-24):

* cloud SDKs are an OPTIONAL extra, never a base dependency;
* the providers package exports nothing that reaches the network;
* the engine's provider chain contains no phantom modules;
* the local provider is the default;
* provider configuration is validated where it is written.

These are conditions a regression can genuinely break, which a permanently
failing test cannot be.

**Validates: Requirements 1.1, 1.2, 1.6, 1.9, 1.14**
"""

import pytest
from hypothesis import given, settings
import hypothesis.strategies as st


# ---------------------------------------------------------------------------
# Test 1 — Cloud Adapter Import
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cloud_adapters_not_importable() -> None:
    """Cloud adapter classes must NOT be importable from Agent_Guru.llm.providers.

    On unfixed code: the import SUCCEEDS (OpenAIAdapter, AnthropicAdapter,
    GoogleAdapter all exist), so the assertion that they do NOT exist FAILS.

    After fix: the import raises ImportError, confirming the adapters are gone.

    **Validates: Requirements 1.1, 1.6**
    """
    import_succeeded = False
    try:
        from Agent_Guru.llm.providers import (  # noqa: F401
            OpenAIAdapter,
            AnthropicAdapter,
            GoogleAdapter,
        )
        import_succeeded = True
    except ImportError:
        import_succeeded = False
    # On unfixed code this assertion FAILS because import_succeeded is True.
    # After fix it PASSES because the adapters no longer exist.
    assert not import_succeeded, (  # nosec B101
        "BUG CONFIRMED: OpenAIAdapter, AnthropicAdapter, and/or GoogleAdapter "
        "are still importable from Agent_Guru.llm.providers. "
        "These cloud adapters must be removed."
    )


# ---------------------------------------------------------------------------
# Test 2 — RuntimeConfig Cloud Fields
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_runtime_config_has_no_cloud_fields() -> None:
    """RuntimeConfig must NOT have openai_config, anthropic_config, or google_config.

    On unfixed code: RuntimeConfig() has all three cloud config fields, so the
    assertion that they are absent FAILS.

    After fix: only ollama_config is present, so the assertion PASSES.

    **Validates: Requirements 1.2**
    """
    from Agent_Guru.llm.models import RuntimeConfig

    config = RuntimeConfig()

    assert not hasattr(config, "openai_config"), (  # nosec B101
        "BUG CONFIRMED: RuntimeConfig still has 'openai_config' field. "
        "Cloud config fields must be removed."
    )
    assert not hasattr(config, "anthropic_config"), (  # nosec B101
        "BUG CONFIRMED: RuntimeConfig still has 'anthropic_config' field. "
        "Cloud config fields must be removed."
    )
    assert not hasattr(config, "google_config"), (  # nosec B101
        "BUG CONFIRMED: RuntimeConfig still has 'google_config' field. "
        "Cloud config fields must be removed."
    )


# ---------------------------------------------------------------------------
# Test 3 — cloud SDKs are not base dependencies
# ---------------------------------------------------------------------------
#
# DECISION (2026-09-24): Agent_Guru keeps its OpenAI and Anthropic providers,
# which exist, work and are covered by 43 tests, but makes them OPT-IN. The
# three tests that used to live below demanded that ModelProvider.OPENAI,
# LLMProvider.OPENAI and friends be deleted outright. They had failed on every
# run since they were written, and they contradicted the rest of the
# repository: `reasoning/llm/providers/{openai,anthropic}_provider.py` are
# present and tested, and `reasoning/intent/llm_fallback.py` implements working
# cloud paths.
#
# What "offline-first" actually requires is that a DEFAULT INSTALL neither
# ships nor imports a cloud SDK, and that nothing reaches the network unless
# the operator opts in. That is what is asserted here - conditions the code can
# satisfy and a regression can break, instead of a deletion nobody performed.
#
# Two genuinely dead branches WERE removed as part of this: ReasoningEngine's
# provider chain imported `gemini_provider` and `deepseek_provider`, neither of
# which exists anywhere in the repository.


@pytest.mark.unit
def test_cloud_sdks_are_not_base_dependencies() -> None:
    """openai/anthropic must be an optional extra, not a required install.

    An offline-first assistant should not make every user download two cloud
    API SDKs. They were in [project] dependencies; they now live in the
    `cloud` extra.
    """
    import tomllib
    from pathlib import Path

    # Walk up to the repository root (the directory holding pyproject.toml).
    root = Path(__file__).resolve()
    while root != root.parent and not (root / "pyproject.toml").exists():
        root = root.parent
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        pytest.skip("UNVERIFIED: pyproject.toml not reachable from the test file")

    config = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    base = config["project"]["dependencies"]
    extras = config["project"]["optional-dependencies"]

    offenders = [d for d in base if d.lower().startswith(("openai", "anthropic"))]
    assert not offenders, (  # nosec B101
        f"cloud SDKs are back in the base dependencies: {offenders}. "
        f"They belong in the 'cloud' extra."
    )
    assert "cloud" in extras, "the optional 'cloud' extra is missing"  # nosec B101
    cloud = " ".join(extras["cloud"]).lower()
    assert "openai" in cloud and "anthropic" in cloud  # nosec B101


@pytest.mark.unit
def test_provider_package_exports_nothing_that_talks_to_the_cloud() -> None:
    """`from ...llm.providers import *` must stay local-only.

    The cloud providers are reachable by module path, deliberately, but they
    are not part of this package's public surface - so importing the package
    on a default install cannot pull in an SDK that is not there.
    """
    from Agent_Guru.reasoning.llm import providers

    exported = set(providers.__all__)
    assert "OllamaProvider" in exported  # nosec B101
    for cloud_name in ("OpenAIProvider", "AnthropicProvider", "GeminiProvider"):
        assert cloud_name not in exported, (  # nosec B101
            f"{cloud_name} is exported from the providers package; a default "
            f"install would import a cloud SDK it does not have"
        )


@pytest.mark.unit
def test_reasoning_engine_provider_chain_has_no_phantom_providers() -> None:
    """Every provider the engine tries must actually exist.

    The chain used to begin with Gemini and DeepSeek branches importing
    modules that are not in the repository: both failed their import on every
    run, logged "module not installed" at DEBUG, and fell through. An operator
    who set GEMINI_API_KEY got silence.
    """
    import inspect

    from Agent_Guru.reasoning.engine import ReasoningEngine

    source = inspect.getsource(ReasoningEngine._initialize_llm_provider)

    for phantom in ("gemini_provider", "deepseek_provider"):
        assert f"import {phantom}" not in source and f".{phantom} import" not in source, (  # nosec B101
            f"the provider chain imports {phantom}, which does not exist"
        )


@pytest.mark.unit
def test_default_install_imports_without_the_cloud_sdks() -> None:
    """The guarantee that makes "offline-first" real.

    Declaring openai/anthropic optional in pyproject is only half the job: if
    anything imported them at module scope, a default install would fail at
    import time. This simulates that install by making both packages
    unimportable and then importing the surface an offline-first user touches.

    Runs in a subprocess so the import guard and the poisoned sys.modules
    cannot leak into the rest of the session.
    """
    import subprocess
    import sys
    import textwrap

    script = textwrap.dedent(
        """
        import builtins, sys
        BLOCKED = {"openai", "anthropic"}
        real_import = builtins.__import__

        def guard(name, *args, **kwargs):
            if name.split(".")[0] in BLOCKED:
                raise ImportError(f"No module named {name.split('.')[0]!r}")
            return real_import(name, *args, **kwargs)

        builtins.__import__ = guard
        for module in list(sys.modules):
            if module.split(".")[0] in BLOCKED:
                del sys.modules[module]

        for module in (
            "Agent_Guru.reasoning.llm.providers",
            "Agent_Guru.reasoning.engine",
            "Agent_Guru.reasoning.intent.llm_fallback",
            "Agent_Guru.reasoning.llm.providers.ollama_provider",
        ):
            real_import(module)

        from Agent_Guru.reasoning.intent.llm_fallback import (
            OPENAI_AVAILABLE,
            LLMFallbackConfig,
        )

        assert LLMFallbackConfig().provider == "ollama", "default is not local"
        assert OPENAI_AVAILABLE is False, "OPENAI_AVAILABLE true without the SDK"
        print("OK")
        """,
    )

    result = subprocess.run(  # nosec B603
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode == 0, (  # nosec B101
        "the package does not import without the optional cloud SDKs:\n"
        f"{result.stderr[-2000:]}"
    )
    assert "OK" in result.stdout  # nosec B101


# ---------------------------------------------------------------------------
# Test 4 — the local provider is the default
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_local_provider_is_the_default() -> None:
    """With no cloud key set, the fallback classifier must default to Ollama."""
    from Agent_Guru.reasoning.intent.llm_fallback import LLMFallbackConfig

    assert LLMFallbackConfig().provider == "ollama"  # nosec B101


# ---------------------------------------------------------------------------
# Test 5 — configuration validation
# ---------------------------------------------------------------------------


@pytest.mark.unit
@given(bad_provider=st.text(min_size=1, max_size=30).filter(
    lambda name: name not in {"ollama", "openai", "anthropic"},
))
@settings(max_examples=20)
def test_llm_fallback_config_rejects_unknown_providers(bad_provider: str) -> None:
    """An unsupported provider name must be refused where the mistake is made.

    This test previously asserted that CLOUD provider names were rejected,
    which contradicted llm_fallback.py's own working openai and anthropic
    paths. It also could not pass on any implementation: its except block set
    `raised_value_error = True` and then immediately `False` on the next line.

    The real defect it was circling is that LLMFallbackConfig validated
    NOTHING - an unsupported name was accepted here and only surfaced later,
    from _initialize_client(), long after the object had been passed around.
    """
    from Agent_Guru.reasoning.intent.llm_fallback import LLMFallbackConfig

    with pytest.raises(ValueError, match="Unsupported provider"):
        LLMFallbackConfig(provider=bad_provider)


@pytest.mark.unit
@pytest.mark.parametrize("provider", ["ollama", "openai", "anthropic"])
def test_llm_fallback_config_accepts_supported_providers(provider: str) -> None:
    """The three implemented providers must all be constructible."""
    from Agent_Guru.reasoning.intent.llm_fallback import LLMFallbackConfig

    assert LLMFallbackConfig(provider=provider).provider == provider  # nosec B101


@pytest.mark.unit
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("timeout_ms", 0.0),
        ("max_retries", -1),
        ("temperature", 2.5),
        ("max_tokens", 0),
        ("ollama_port", 70000),
    ],
)
def test_llm_fallback_config_rejects_impossible_values(field: str, value: object) -> None:
    """Out-of-range settings are refused at construction, not at first use."""
    from Agent_Guru.reasoning.intent.llm_fallback import LLMFallbackConfig

    with pytest.raises(ValueError, match=field):
        LLMFallbackConfig(**{field: value})
