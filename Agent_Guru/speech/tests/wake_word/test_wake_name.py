"""One rule says whether speech names a wake word: Guru or Maya as a word, with "ji" the one allowed suffix.

The detector picked Guru or Maya by finding the names anywhere in the text, so "gurukul" chose Guru and
"Mayank" chose Maya, and "Guru ji" counted only because the substring happened to be in it. The same
rule now serves the fallback wake's name check and the detector's choice of personality.
"""

from __future__ import annotations

import pytest

from Agent_Guru.speech.audio.wake_word import WakeWordDetector, wake_name
from Agent_Guru.speech.models import PersonalityType


@pytest.mark.parametrize(("said", "name"), [
    ("Hey Guru ji, what time is it?", "guru"),
    ("Hey Maya ji", "maya"),
    ("Guruji, open notepad", "guru"),       # Whisper often writes it joined
    ("Mayaji tell me a joke", "maya"),
    ("हे गुरु जी", "guru"),
    ("हे गुरुजी", "guru"),
    ("माया जी", "maya"),
    ("Guru ji", "guru"),
    ("Maya ji", "maya"),
    # A real word that only starts with "ji" after the name is not a suffix at all.
    ("Hey Guru, jitna ho sake jaldi", "guru"),
])
def test_ji_is_allowed_after_the_name(said, name):
    assert wake_name(said) == name


@pytest.mark.parametrize("said", [
    # "jii" is not the "ji" suffix, joined or spaced (the owner's decision).
    "guru jii",
    "maya jii",
    "Hey Guru jii, what time is it?",
    "Hey Maya, jii",
    "gurujii",
    "Hey gurukul is my school",   # a different word that starts with the name
    "hey gurujii",                # joined, but not "ji"
    "Gurugram traffic",
    "Gurugram",
    "Mayank is here",
    "Mayank",
    "Mayapur temple",
    "Mayapur",
    "the jiguru of it",
])
def test_words_that_only_start_or_contain_the_name_are_not_wakes(said):
    assert wake_name(said) is None


@pytest.mark.parametrize(("heard", "name"), [("Feguru,", "guru"), ("Yimayah", "maya"), ("Hemaia,", "maya"),
                                             ("Thaemaya, Thaemaya,", "maya")])
def test_how_whisper_wrote_the_owners_own_wake_takes(heard, name):
    # From the half of the owner's takes used for training, said without a command.
    assert wake_name(heard) == name


@pytest.mark.parametrize("word", ["samaya", "satguru", "Ramayana"])
def test_listed_greetings_do_not_let_other_words_through(word):
    # "Any few letters before the name" would have let these Hindi words count as wakes.
    assert wake_name(word) is None


def test_a_name_said_inside_a_sentence_still_passes_this_check():
    # Not fixed here, and not fixable by text: "I told her hey Maya is late" names Maya.
    # Telling it from a wake needs the trained wake word model.
    assert wake_name("I told her hey Maya is late") == "maya"


@pytest.mark.parametrize(("said", "chosen"), [
    ("Guruji what time is it", ("hey guru", PersonalityType.GURU)),
    ("Himaya, open notepad", ("hey maya", PersonalityType.MAYA)),
    ("the gurukul is near the market", None),
    ("Mayank is coming home", None),
    ("Hey Guru jii", None),
])
def test_the_detector_chooses_the_personality_by_the_same_rule(said, chosen):
    assert WakeWordDetector()._match_transcript(said) == chosen
