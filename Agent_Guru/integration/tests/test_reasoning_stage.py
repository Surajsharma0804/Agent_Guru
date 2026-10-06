"""A spoken turn must not wait on, or quote, the ReasoningEngine.

Every turn used to run ReasoningEngine.process() as "stage 3" under a 2 s
timeout. For a question, process() classifies the intent with the LLM and
then writes a complete answer of its own, which took 4 to 5 s with gemma3:4b
on a laptop GPU, so the stage was cancelled at 2.0 s and its work thrown
away: every question waited 2 s for nothing before the real answer was
requested. For a rule-matched command process() finished at once, and its
whole result object, a canned answer included, was pasted into the user
message as "[Reasoning: ReasoningResult(...)]". Nothing else read the
stage's output.
"""

from __future__ import annotations

import asyncio
import time

CANNED = "ReasoningResult(response='an answer the voice path never asked for')"


class _SlowReasoning:
    """Stands in for ReasoningEngine on a question: takes longer than the old 2 s cap."""

    def __init__(self) -> None:
        self.calls = 0

    async def process(self, raw_input):
        self.calls += 1
        await asyncio.sleep(5)
        return CANNED


class _InstantReasoning:
    """Stands in for ReasoningEngine on a rule-matched command: returns at once."""

    def __init__(self) -> None:
        self.calls = 0

    async def process(self, raw_input):
        self.calls += 1
        return CANNED


async def test_a_question_does_not_wait_for_the_reasoning_engine(run_turn):
    reasoning = _SlowReasoning()
    # The first turn in a process pays one-off lazy imports (speaker
    # verification pulls in scipy.signal, about 2 s). Warm them first so the
    # timing below measures only what this test is about.
    await run_turn("hello")

    start = time.perf_counter()
    turn = await run_turn("who is the Prime Minister of India", reasoning=reasoning)
    elapsed = time.perf_counter() - start

    assert reasoning.calls == 0
    assert elapsed < 1.0
    assert turn.llm.requests, "the question must still be answered"


async def test_the_answer_prompt_carries_no_reasoning_dump(run_turn):
    reasoning = _InstantReasoning()

    turn = await run_turn("tell me a joke about cats", reasoning=reasoning)

    sent = "\n".join(m.content for r in turn.llm.requests for m in r.messages)
    assert turn.llm.requests
    assert "[Reasoning:" not in sent
    assert "an answer the voice path never asked for" not in sent
