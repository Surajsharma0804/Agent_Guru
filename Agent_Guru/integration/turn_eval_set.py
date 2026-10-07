"""Spoken turns with known good outcomes, for scoring the assistant end to end.

The pipeline tests run against fakes, so they cannot say whether the real
model answers well, whether it buries the answer under small talk, or how
long a turn takes. This set is for that. Run it with scripts/turn_eval.py
against a real Ollama; it is not part of the test suite.

Each case is one conversation. Its last utterance is the one scored; earlier
ones set it up, in the same session or, for long-term memory, in an earlier
one. Answers are checked with regular expressions, because a right answer can
be worded many ways.

The cases come from turns run on the real assistant while building the turn
records (2026-10-07), including the ones that went wrong: a first question
answered after a sentence of small talk, and an unknown application name taken
for a website. scripts/turn_eval.py --rated adds the turns the owner marked
right or wrong by voice.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TurnCase:
    """One conversation and what its last turn must do.

    correct / wrong: patterns the scored reply must and must not match
        (case-insensitive). None means the reply text is not judged.
    intent: pattern the recognized intent must match, for commands.
    status: the action status the turn must end with ("success", "denied",
        ...), or None when no action is expected.
    answer_first: the answer must start within ANSWER_FIRST_CHARS of the
        reply, instead of after small talk.
    earlier_session: said in a previous session, so only long-term memory
        can carry it into this one.
    """

    category: str
    said: tuple[str, ...]
    correct: str | None = None
    wrong: str | None = None
    intent: str | None = None
    status: str | None = None
    answer_first: bool = False
    earlier_session: tuple[str, ...] = ()

    def reply_ok(self, reply: str) -> bool | None:
        if self.correct is None and self.wrong is None:
            return None
        text = reply or ""
        if self.correct and not re.search(self.correct, text, re.IGNORECASE):
            return False
        return not (self.wrong and re.search(self.wrong, text, re.IGNORECASE))


#: Where the answer may start in a reply that should lead with it. A short
#: lead-in ("Oh, easy!") is fine; a sentence of greeting is not. Measured
#: before the first-turn fix: 128 characters (median), after: 42.
ANSWER_FIRST_CHARS = 60

#: A reply that opens like this greets instead of answering.
SMALL_TALK_OPENING = re.compile(
    r"^\W*(?:hey|hi|hello|yo|namaste)\b[^.!?]*[.!?]\s*(?:[^.!?]*\b(?:what'?s up|how(?:'s| is| are)|haven'?t (?:talked|chatted|heard))\b)",
    re.IGNORECASE,
)

#: Things the persona must never say (system prompt ETHICS rule).
NEEDY_PHRASES = re.compile(r"\b(?:i missed you|i was worried about you|don'?t leave me|only i understand you)\b", re.IGNORECASE)

CASES: tuple[TurnCase, ...] = (
    # First question of a session: answered, not greeted.
    TurnCase("first_question", ("what is the capital of France",), correct=r"\bparis\b", answer_first=True),
    TurnCase("first_question", ("who wrote Romeo and Juliet",), correct=r"\bshakespeare\b", answer_first=True),
    TurnCase("first_question", ("how many days are in a week",), correct=r"\b(?:seven|7)\b", answer_first=True),
    # Factual questions later in a conversation.
    TurnCase("factual", ("hi there", "what is two plus two"), correct=r"\b(?:four|4)\b", wrong=r"\b(?:five|5|three|3)\b",
             answer_first=True),
    TurnCase("factual", ("hello", "what is the boiling point of water in celsius"), correct=r"\b100\b", answer_first=True),
    TurnCase("factual", ("hey", "which planet is closest to the sun"), correct=r"\bmercury\b", answer_first=True),
    # A follow-up that only makes sense with the previous turn.
    TurnCase("follow_up", ("what is the capital of Japan", "and what is its population roughly"),
             correct=r"\b(?:million|crore|lakh)|\b\d{2}\b"),
    TurnCase("follow_up", ("tell me about the Taj Mahal", "which city is it in"), correct=r"\bagra\b"),
    # Conversation and persona.
    TurnCase("conversation", ("hi there",), correct=r"\b(?:hey|hi|hello|yo)\b"),
    TurnCase("conversation", ("tell me a joke",), intent=r"^conversation"),
    TurnCase("emotional", ("I'm feeling really stressed about my exam tomorrow",),
             correct=r"\b(?:exam|stress|breath|relax|prepare|study|okay|ok|got this|rest)\w*", wrong=NEEDY_PHRASES.pattern),
    # Remembered within the session (chat history).
    TurnCase("memory_session", ("my favourite colour is green", "what is my favourite colour"), correct=r"\bgreen\b"),
    # Remembered across sessions (long-term memory and user facts).
    TurnCase("memory_long_term", ("what is my name",), correct=r"\bravi\b", earlier_session=("my name is Ravi",)),
    TurnCase("memory_long_term", ("where do I live",), correct=r"\bpune\b", earlier_session=("I live in Pune",)),
    # Commands: the right intent, and the status the production policy gives.
    TurnCase("command", ("open notepad",), intent=r"^system_control:open_app:notepad$", status="denied"),
    TurnCase("command", ("close notepad",), intent=r"^system_control:close_app:notepad$", status="denied"),
    TurnCase("command", ("turn the volume up",), intent=r"^system_control:volume:up$", status="denied"),
    TurnCase("command", ("send a message to John saying I'll be late",),
             intent=r"^communication:send_message:John:whatsapp:I'll be late$"),
    TurnCase("command", ("remind me in 10 minutes to drink water",), intent=r"^system_control:reminder:"),
    # Feedback on the previous answer.
    TurnCase("feedback", ("what is two plus two", "that was wrong"), intent=r"^feedback:rating$", status="success",
             correct=r"marked that answer as wrong"),
    TurnCase("feedback", ("what is the capital of France", "sahi hai"), intent=r"^feedback:rating$", status="success",
             correct=r"marked that answer as right"),
    # Failure cases: what must not happen.
    TurnCase("failure", ("that was wrong",), status="failed", correct=r"no earlier answer"),
    # Found on the real assistant: an unknown application name became a
    # website to open. Scored as wrong until it is not.
    TurnCase("failure", ("open zxqvbn",), intent=r"^system_control:open_app:"),
)
