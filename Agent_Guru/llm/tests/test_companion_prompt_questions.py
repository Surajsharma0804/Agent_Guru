"""The companion prompts do not teach the model to end every reply with a question.

Both prompts said "FOLLOW-UPS - this is CRITICAL: ALWAYS end with something
that keeps the conversation going", and most of their examples ended in a
question ("Oh that's easy - Paris! Have you been there?"). gemma4 copies
examples closely: in the round 12 soak 17 of 17 chatty replies ended by
asking the owner something. On 20 fixed prompts per persona, two runs each
with an empty profile, the 17 that need nothing more ended in a question 55
times in 68 with the old prompts and 16 in 68 with the new ones.

The model's output cannot be tested here without a model, so this pins what
taught the habit: every quoted example in the built prompt that ends in a
question must be one of a short list, each with a reason to be a question.
A new example that teaches a filler question fails this test and has to be
argued for.
"""

from __future__ import annotations

import re

import pytest

from Agent_Guru.llm.companion_prompts import build_companion_prompt

# Questions the prompts may still quote, by why they are questions.
_ALLOWED = {
    # A reaction, not a question to answer.
    "Oh damn, really?", "Wait, seriously?", "No way, really?",
    # Quoted as things never to say.
    "How may I assist you?", "What else is going on?", "Is there anything else?", "How's your day?",
    "What else is on your mind?", "How's everything going?",
    "wild, right?", "pretty cool, huh?", "so cool, right?", "isn't it wild?",
    "wanna plan a trip there?", "wanna test me on more?", "wanna chat about something fun?",
    # The owner only greeted: asking what they want is the task.
    "Hey! Good to hear from you. What's up?",
    # Needed to finish the task.
    "which genre do you like?", "who's it to?", "what kind of books do you love?", "who's it for?",
    # Comfort, where asking what happened is the help.
    "Ugh, that sucks. What happened?", "Oh that's tough yaar. Kya hua exactly?", "kya hua?",
    "You've been going hard. Rest a bit, yeah?",
    # A greeting in another language.
    "Hey, alles klar?",
}


def _quoted_questions(prompt: str) -> set[str]:
    return set(re.findall(r'"([^"]*\?)"', prompt))


@pytest.mark.parametrize("personality", ["guru", "maya"])
@pytest.mark.parametrize("code_mixing", ["hinglish", ""])
def test_only_justified_questions_are_quoted_as_examples(personality, code_mixing):
    prompt = build_companion_prompt(
        personality=personality, user_facts="", current_date="November 03, 2026", emotion_hint="neutral",
        nickname="", code_mixing=code_mixing, user_country="", knowledge_cutoff="",
    )
    taught = _quoted_questions(prompt) - _ALLOWED
    assert not taught, f"{personality} prompt teaches these questions: {sorted(taught)}"  # nosec B101


@pytest.mark.parametrize("personality", ["guru", "maya"])
def test_the_prompt_says_to_ask_only_when_the_task_needs_it(personality):
    prompt = build_companion_prompt(
        personality=personality, user_facts="", current_date="November 03, 2026", emotion_hint="neutral",
        nickname="", code_mixing="hinglish", user_country="", knowledge_cutoff="",
    )
    assert "ALWAYS end with" not in prompt and "ALWAYS keep the conversation alive" not in prompt  # nosec B101
    assert "Ask a question only when you can't do what they asked without the answer" in prompt  # nosec B101
