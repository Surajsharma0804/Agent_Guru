"""Tests for the local-LLM timing policy.

Every LLM timeout in the codebase used to be a bare literal sized for a fast
machine - 5 s for plan generation, 1 s for intent fallback, 15 s for a
generate call, 10 s to find a server that might still be loading a model.
AGENT_GURU is offline-first, so the normal deployment is a local model on
consumer hardware that frequently has no usable GPU. On such a machine those
budgets expire because the machine is slow, not because anything is wrong,
and the user gets a timeout error instead of an answer.

These tests pin the two properties that matter: the defaults are large enough
to be usable on slow hardware, and every one of them can be overridden from
the environment without editing code.
"""

from __future__ import annotations

import pytest

from Agent_Guru.reasoning.llm import timeouts

#: (accessor, environment variable, shipped default)
POLICIES = [
    (timeouts.connect_timeout, "OLLAMA_CONNECT_TIMEOUT_SECONDS", timeouts.DEFAULT_CONNECT_TIMEOUT_S),
    (timeouts.generate_timeout, "OLLAMA_TIMEOUT_SECONDS", timeouts.DEFAULT_GENERATE_TIMEOUT_S),
    (timeouts.start_timeout, "OLLAMA_START_TIMEOUT_SECONDS", timeouts.DEFAULT_START_TIMEOUT_S),
    (timeouts.plan_timeout, "AGENT_GURU_PLAN_TIMEOUT_SECONDS", timeouts.DEFAULT_PLAN_TIMEOUT_S),
    (timeouts.intent_timeout, "AGENT_GURU_INTENT_TIMEOUT_SECONDS", timeouts.DEFAULT_INTENT_TIMEOUT_S),
]

IDS = [name for _, name, _ in POLICIES]


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test from the shipped defaults.

    The reasoning conftest sets OLLAMA_TIMEOUT_SECONDS=2 for the whole
    session, which would otherwise make the default-value tests below read
    that instead of what the module ships.
    """
    for _, env_name, _ in POLICIES:
        monkeypatch.delenv(env_name, raising=False)


class TestDefaults:
    @pytest.mark.parametrize(("accessor", "env_name", "default"), POLICIES, ids=IDS)
    def test_default_is_returned_when_unset(
        self, accessor, env_name: str, default: float
    ) -> None:
        assert accessor() == default

    @pytest.mark.parametrize(("accessor", "env_name", "default"), POLICIES, ids=IDS)
    def test_every_default_is_positive(
        self, accessor, env_name: str, default: float
    ) -> None:
        assert default > 0

    def test_inference_budgets_are_sized_for_cpu_hardware(self) -> None:
        """The whole point of the module: these must not be single-digit.

        A local model producing a multi-step plan on a CPU needs tens of
        seconds. The previous literals (5 s for a plan, 1 s for intent) were
        not merely tight, they were unreachable, so the features they guarded
        never worked on GPU-less hardware.
        """
        assert timeouts.DEFAULT_PLAN_TIMEOUT_S >= 60.0
        assert timeouts.DEFAULT_GENERATE_TIMEOUT_S >= 60.0
        assert timeouts.DEFAULT_INTENT_TIMEOUT_S >= 30.0
        assert timeouts.DEFAULT_START_TIMEOUT_S >= 60.0

    def test_connect_timeout_stays_short(self) -> None:
        """Connecting to a local socket does not get slower on weak hardware.

        Either something is listening on the port or nothing is, so this one
        must stay small - otherwise "Ollama isn't running" takes minutes to
        report instead of seconds.
        """
        assert timeouts.DEFAULT_CONNECT_TIMEOUT_S <= 10.0
        assert timeouts.DEFAULT_CONNECT_TIMEOUT_S < timeouts.DEFAULT_GENERATE_TIMEOUT_S


class TestEnvironmentOverrides:
    @pytest.mark.parametrize(("accessor", "env_name", "default"), POLICIES, ids=IDS)
    def test_override_is_honoured(
        self, accessor, env_name: str, default: float, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(env_name, "12.5")
        assert accessor() == 12.5

    @pytest.mark.parametrize(("accessor", "env_name", "default"), POLICIES, ids=IDS)
    def test_integer_string_is_accepted(
        self, accessor, env_name: str, default: float, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(env_name, "45")
        assert accessor() == 45.0

    @pytest.mark.parametrize(("accessor", "env_name", "default"), POLICIES, ids=IDS)
    def test_surrounding_whitespace_is_tolerated(
        self, accessor, env_name: str, default: float, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(env_name, "  7.5  ")
        assert accessor() == 7.5

    @pytest.mark.parametrize(("accessor", "env_name", "default"), POLICIES, ids=IDS)
    def test_empty_string_falls_back_to_default(
        self, accessor, env_name: str, default: float, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(env_name, "")
        assert accessor() == default

    def test_a_fast_machine_can_tighten_the_budget(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("AGENT_GURU_PLAN_TIMEOUT_SECONDS", "5")
        assert timeouts.plan_timeout() == 5.0

    def test_a_very_slow_machine_can_loosen_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("AGENT_GURU_PLAN_TIMEOUT_SECONDS", "600")
        assert timeouts.plan_timeout() == 600.0


class TestMalformedValues:
    """A typo must not stop the assistant from starting."""

    @pytest.mark.parametrize("bad", ["abc", "30s", "1,5", "--5", "nan-ish"])
    def test_unparseable_value_falls_back_and_warns(
        self, bad: str, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv("AGENT_GURU_PLAN_TIMEOUT_SECONDS", bad)
        with caplog.at_level("WARNING"):
            assert timeouts.plan_timeout() == timeouts.DEFAULT_PLAN_TIMEOUT_S
        assert any("is not a number" in r.message for r in caplog.records)

    @pytest.mark.parametrize("bad", ["0", "0.0", "-1", "-30.5"])
    def test_non_positive_value_falls_back_and_warns(
        self, bad: str, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Zero is the dangerous one: it turns every call into an instant
        timeout, which looks like a broken model rather than a bad setting."""
        monkeypatch.setenv("AGENT_GURU_PLAN_TIMEOUT_SECONDS", bad)
        with caplog.at_level("WARNING"):
            assert timeouts.plan_timeout() == timeouts.DEFAULT_PLAN_TIMEOUT_S
        assert any("must be positive" in r.message for r in caplog.records)

    def test_fallback_never_returns_a_non_positive_number(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for _, env_name, _ in POLICIES:
            monkeypatch.setenv(env_name, "0")
        assert all(accessor() > 0 for accessor, _, _ in POLICIES)


class TestConsumersUseThePolicy:
    """The policy is only worth having if the call sites actually read it."""

    def test_plan_generator_default_follows_the_policy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from Agent_Guru.reasoning.llm.reasoning import ReasoningPlanGenerator

        monkeypatch.setenv("AGENT_GURU_PLAN_TIMEOUT_SECONDS", "42")
        assert ReasoningPlanGenerator(llm_provider=None).timeout_seconds == 42.0

    def test_plan_generator_explicit_argument_wins(self) -> None:
        from Agent_Guru.reasoning.llm.reasoning import ReasoningPlanGenerator

        assert ReasoningPlanGenerator(llm_provider=None, timeout_seconds=9.0).timeout_seconds == 9.0

    @pytest.mark.parametrize("bad", [0, -1.0])
    def test_plan_generator_rejects_non_positive_timeout(self, bad: float) -> None:
        from Agent_Guru.reasoning.llm.reasoning import ReasoningPlanGenerator

        with pytest.raises(ValueError, match="timeout_seconds must be positive"):
            ReasoningPlanGenerator(llm_provider=None, timeout_seconds=bad)

    def test_intent_fallback_default_follows_the_policy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from Agent_Guru.reasoning.intent.llm_fallback import LLMFallbackConfig

        monkeypatch.setenv("AGENT_GURU_INTENT_TIMEOUT_SECONDS", "8")
        assert LLMFallbackConfig().timeout_ms == 8000.0

    def test_provider_config_default_follows_the_policy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from Agent_Guru.reasoning.llm.providers.base import ProviderConfig

        monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "25")
        assert ProviderConfig(api_key="x").timeout_seconds == 25.0

    def test_ollama_timeout_seconds_is_actually_read(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The reasoning conftest has always set this to 2 "so any accidental
        real call fails in 2s, not 300s" - but nothing in production read it,
        so the hardening did nothing at all."""
        monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "2")
        assert timeouts.generate_timeout() == 2.0
