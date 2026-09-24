"""Tests for DegradationController.

This module had NO tests at all, which is how it came to ship a
``_call_provider`` stub that fabricated answers - returning
``"[ollama] Response to: <prompt>"`` as though it were a model response, with
``llm_with_failover()`` reporting success. The tests below pin the behaviour
that matters for an offline-first assistant: never invent content, always fall
back to an answer that says it is offline, and never spend the failover budget
on providers that cannot possibly answer.
"""

from __future__ import annotations

import asyncio

import pytest

from Agent_Guru.resilience.controller import DegradationController, DegradationMode


class TestFailoverChain:
    """The default chain and how it is traversed."""

    def test_default_chain_has_no_cloud_providers(self):
        """Agent_Guru is offline-first and has no cloud adapters.

        Listing "openai"/"gemini" here only burned one LLM_TIMEOUT_S each
        before the chain reached the rule-based answer it was always going to
        return.
        """
        controller = DegradationController()

        assert "openai" not in controller._llm_providers  # nosec B101
        assert "anthropic" not in controller._llm_providers  # nosec B101
        assert "gemini" not in controller._llm_providers  # nosec B101
        assert controller._llm_providers[-1] == "rule_based", (  # nosec B101
            "the chain must always end in a provider that cannot fail"
        )

    @pytest.mark.asyncio
    async def test_uses_the_first_working_provider(self):
        calls: list[str] = []

        async def ollama(prompt: str) -> str:
            calls.append("ollama")
            return f"ollama says: {prompt}"

        controller = DegradationController(provider_callables={"ollama": ollama})

        result = await controller.llm_with_failover("hello")

        assert result == "ollama says: hello"  # nosec B101
        assert calls == ["ollama"]  # nosec B101

    @pytest.mark.asyncio
    async def test_falls_through_to_the_next_provider_on_failure(self):
        calls: list[str] = []

        async def broken(prompt: str) -> str:
            calls.append("broken")
            msg = "provider exploded"
            raise RuntimeError(msg)

        async def working(prompt: str) -> str:
            calls.append("working")
            return "recovered"

        controller = DegradationController(
            providers=["broken", "working", "rule_based"],
            provider_callables={"broken": broken, "working": working},
        )

        assert await controller.llm_with_failover("hi") == "recovered"  # nosec B101
        assert calls == ["broken", "working"]  # nosec B101

    @pytest.mark.asyncio
    async def test_unconfigured_provider_does_not_fabricate_a_response(self):
        """The regression this module's missing tests allowed.

        With no callable configured the controller must fall through to the
        offline answer, not return invented text that looks like a model
        response.
        """
        controller = DegradationController(providers=["ollama", "rule_based"])

        result = await controller.llm_with_failover("what is the weather")

        assert "Response to:" not in result, (  # nosec B101
            "the stub that fabricated an answer is back"
        )
        assert "[ollama]" not in result  # nosec B101
        assert "offline" in result.lower()  # nosec B101

    @pytest.mark.asyncio
    async def test_unconfigured_provider_raises_from_call_provider(self):
        """Directly, the failure is explicit rather than silent."""
        controller = DegradationController()

        with pytest.raises(NotImplementedError, match="No LLM callable configured"):
            await controller._call_provider("ollama", "hello")

    @pytest.mark.asyncio
    async def test_a_slow_provider_is_abandoned(self):
        """A hung provider must not stall the whole chain."""

        async def hangs(prompt: str) -> str:
            await asyncio.sleep(30)
            return "never"

        controller = DegradationController(
            providers=["hangs", "rule_based"],
            provider_callables={"hangs": hangs},
        )

        # Patch the module constant down so the test does not really wait 3s.
        import Agent_Guru.resilience.controller as controller_module

        original = controller_module.LLM_TIMEOUT_S
        controller_module.LLM_TIMEOUT_S = 0.05
        try:
            result = await controller.llm_with_failover("hello")
        finally:
            controller_module.LLM_TIMEOUT_S = original

        assert "offline" in result.lower()  # nosec B101

    @pytest.mark.asyncio
    async def test_explicit_chain_overrides_the_default(self):
        async def only(prompt: str) -> str:
            return "explicit"

        controller = DegradationController(provider_callables={"only": only})

        result = await controller.llm_with_failover("hi", providers=["only"])
        assert result == "explicit"  # nosec B101


class TestSafeMode:
    """SAFE mode must make no external calls at all."""

    @pytest.mark.asyncio
    async def test_safe_mode_never_calls_a_provider(self):
        called = False

        async def provider(prompt: str) -> str:
            nonlocal called
            called = True
            return "should not happen"

        controller = DegradationController(provider_callables={"ollama": provider})
        controller.switch_mode(DegradationMode.SAFE)

        result = await controller.llm_with_failover("hello")

        assert called is False, "SAFE mode made an external call"  # nosec B101
        assert "offline" in result.lower()  # nosec B101


class TestModeTransitions:
    def test_starts_in_full_mode(self):
        assert DegradationController().get_mode() is DegradationMode.FULL  # nosec B101

    def test_switch_mode_is_recorded(self):
        controller = DegradationController()
        controller.switch_mode(DegradationMode.MINIMAL)
        assert controller.get_mode() is DegradationMode.MINIMAL  # nosec B101
