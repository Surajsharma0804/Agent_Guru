"""What a voice turn sends the model, so Ollama can reuse the previous turn's work.

Ollama reuses a previous request's prompt processing only up to where the new
request first differs from it, and only near the end of what it processed.
Every turn used to differ early: the system prompt ended with "This is turn
N", and the last message carried 5 recalled memories, among them the
session's own earlier turns. Measured with gemma4 on Ollama, 2.0 to 2.5 s
went to prompt processing before the first word of each answer.

These run whole turns through run_pipeline with the real MemoryManager. Its
embeddings are a small keyword vector, so memories about the same thing are
similar and others are not, without loading a model.
"""

from __future__ import annotations

import math
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from Agent_Guru.integration.orchestrator import IntegrationOrchestrator, WakeWordEvent
from Agent_Guru.memory import memory_manager
from Agent_Guru.memory.memory_manager import MemoryManager
from Agent_Guru.platform.features import user_memory as user_memory_module

TOPICS = [
    "sister", "wedding", "gift", "married", "peanut", "allergic", "snack", "hike", "blood", "pressure",
    "doctor", "japan", "capital", "tokyo", "guitar", "chords", "space", "planet", "cricket", "team",
]


def _embed(text: str) -> list[float]:
    words = set(re.findall(r"[a-z]+", text.lower()))
    v = [1.0 if t in words else 0.0 for t in TOPICS] + [0.05]
    norm = math.sqrt(sum(x * x for x in v))
    return [x / norm for x in v]


class _LLM:
    def __init__(self, answers: dict[str, str]) -> None:
        self.answers, self.requests = answers, []

    async def complete(self, request):
        self.requests.append(request)
        said = request.messages[-1].content
        reply = next((a for q, a in self.answers.items() if said.endswith(q)), "Okay.")
        return SimpleNamespace(content=reply, finish_reason="stop")


class _Allow:
    def evaluate(self, intent):
        return True


@pytest.fixture
def session(tmp_path, monkeypatch):
    async def embed(text: str) -> list[float]:
        return _embed(text)

    monkeypatch.setattr(memory_manager, "_embed_text_async", embed)
    monkeypatch.setattr(
        user_memory_module, "_user_memory", user_memory_module.UserMemory(path=tmp_path / "user_memory.json"),
    )
    memory = MemoryManager(platform_override="test-platform")
    llm = _LLM({
        "What is the capital of Japan?": "Tokyo is the capital of Japan.",
        "What should I gift my sister for her wedding?": "A photo album of the two of you.",
        "Tell me a fun fact about space.": "A day on Venus is longer than its year.",
    })
    orch = IntegrationOrchestrator(
        speech_engine=None, vision_engine=None, llm_runtime=llm, platform_controller=object(),
        agent_orchestrator=None, memory=memory, reasoning=None, security=None, policy=_Allow(),
        avatar=None, deployment=None, gpu_pool=None,
    )
    orch._stage_tts = AsyncMock(return_value=None)
    orch._play_filler = AsyncMock(return_value=None)
    orch._fetch_web_context = AsyncMock(return_value="")

    async def turn(transcript: str):
        orch._stage_stt = AsyncMock(return_value=(transcript, "en"))
        result = await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru"))
        return result, llm.requests[-1].messages

    return SimpleNamespace(orch=orch, memory=memory, llm=llm, turn=turn)


async def test_recall_is_told_which_turns_the_conversation_holds(session):
    calls = []
    real = session.memory.search

    async def search(query, **kw):
        calls.append(kw.get("known"))
        return await real(query, **kw)

    session.memory.search = search
    await session.turn("What is the capital of Japan?")
    await session.turn("Tell me a fun fact about space.")
    assert calls == [[], [("What is the capital of Japan?", "Tokyo is the capital of Japan.")]]  # nosec B101


async def test_this_sessions_turns_are_not_recalled_beside_the_history(session):
    await session.turn("What is the capital of Japan?")
    result, messages = await session.turn("What is the capital of Japan?")
    # Before: the first turn came back from memory and was put in front of
    # the question, although the history already held it.
    assert not result.memory_context  # nosec B101
    assert messages[-1].content.endswith("What is the capital of Japan?")  # nosec B101
    assert "[Context:" not in messages[-1].content  # nosec B101
    assert [m.content for m in messages[1:3]] == [  # nosec B101
        "What is the capital of Japan?", "Tokyo is the capital of Japan.",
    ]


async def test_a_relevant_older_memory_still_reaches_the_model(session):
    await session.memory.store_interaction(
        "GURU", "My sister Priya is getting married in December.", "Congrats to Priya!",
    )
    result, messages = await session.turn("What should I gift my sister for her wedding?")
    assert [m["user_message"] for m in result.memory_context] == [  # nosec B101
        "My sister Priya is getting married in December.",
    ]
    assert "Priya is getting married in December" in messages[-1].content  # nosec B101


async def test_an_unrelated_private_memory_is_not_sent_with_another_question(session):
    await session.memory.store_interaction(
        "GURU", "My doctor says my blood pressure is too high.", "Let's keep an eye on that.",
    )
    result, messages = await session.turn("Tell me a fun fact about space.")
    # Before: the nearest 5 were sent whatever they were about.
    assert not result.memory_context  # nosec B101
    assert all("blood pressure" not in m.content for m in messages)  # nosec B101


async def test_turns_left_out_of_the_prompt_stay_stored(session):
    await session.turn("What is the capital of Japan?")
    await session.turn("What is the capital of Japan?")
    assert session.memory.interaction_count() == 2  # nosec B101
    later = await session.memory.search("What is the capital of Japan?")
    assert {r["user_message"] for r in later} == {"What is the capital of Japan?"}  # nosec B101


async def test_the_system_prompt_is_the_same_on_every_turn(session):
    systems = []
    for said in ("What is the capital of Japan?", "What should I gift my sister for her wedding?",
                 "Tell me a fun fact about space.", "What is the capital of Japan?"):
        _, messages = await session.turn(said)
        systems.append(messages[0].content)
    # Before: it ended with "This is turn N", different on every turn.
    assert len(set(systems)) == 1  # nosec B101
    assert "This is turn" not in systems[0]  # nosec B101


async def test_emotion_guidance_stays_in_the_system_prompt(session):
    # Beside the user's words it was followed literally: a question misread
    # as frustrated was answered with the guidance's own example sentence
    # and not answered at all, in 5 of 5 tries with the real model.
    await session.turn("What is the capital of Japan?")
    _, messages = await session.turn("I am so frustrated, nothing works today!")
    assert "EMOTION DETECTED: 'frustrated'" in messages[0].content  # nosec B101
    assert "EMOTION DETECTED" not in messages[-1].content  # nosec B101


async def test_turn_details_reach_the_model_beside_the_users_words(session):
    _, first = await session.turn("What is the capital of Japan?")
    _, second = await session.turn("I am so frustrated, nothing works today!")
    assert "SESSION START" in first[-1].content  # nosec B101
    note, said = second[-1].content.rsplit("\n", 1)
    assert said == "I am so frustrated, nothing works today!"  # nosec B101
    assert "CONVERSATION STATE: This is turn 2." in note  # nosec B101
    assert "This is turn" not in second[0].content  # nosec B101


async def test_each_request_starts_with_the_previous_one(session):
    # What lets Ollama reuse the previous turn: the new request repeats it
    # up to the previous question, so only the end is processed anew.
    previous, previous_said = None, ""
    for said in ("What is the capital of Japan?", "What should I gift my sister for her wedding?",
                 "Tell me a fun fact about space.", "What is the capital of Japan?"):
        _, messages = await session.turn(said)
        sent = [(m.role, m.content) for m in messages]
        if previous is not None:
            assert sent[: len(previous) - 1] == previous[:-1]  # nosec B101
            assert sent[len(previous) - 1][1] == previous_said  # nosec B101
        previous, previous_said = sent, said


async def test_a_turn_with_no_memory_and_no_history_still_works(session):
    result, messages = await session.turn("Tell me a fun fact about space.")
    assert result.llm_response == "A day on Venus is longer than its year."  # nosec B101
    assert [m.role for m in messages] == ["system", "user"]  # nosec B101


async def test_a_factual_follow_up_keeps_the_system_prompt(session):
    # "roughly" was read as frustrated ("ugh" inside it), which put
    # frustration guidance in the system prompt for this turn alone and
    # cost the reuse of the previous turn's processing.
    _, first = await session.turn("What is the capital of Japan?")
    _, second = await session.turn("And roughly how many people live there?")
    assert second[0].content == first[0].content  # nosec B101
    assert "EMOTION DETECTED" not in second[0].content  # nosec B101


async def test_a_first_question_is_answered_before_any_small_talk(session):
    # The first-turn note told the model to greet and ask what's up whatever
    # the user said. With gemma4 a first question's answer began 128
    # characters into the reply (median of 10), after a sentence of small
    # talk; with this wording, 42.
    _, first = await session.turn("What is the capital of Japan?")
    note = first[-1].content.rsplit("\n", 1)[0]
    assert "Ask how they're doing" not in note  # nosec B101
    assert "start your reply with the answer" in note  # nosec B101
    assert "If the user is greeting you" in note  # nosec B101  a greeting still gets one back
