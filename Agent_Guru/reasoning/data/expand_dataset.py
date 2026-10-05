"""Expand Dataset to 3x Size for MAXIMUM Accuracy.

This script generates additional high-quality training examples
to reach 200+ examples per intent for 98%+ accuracy.

Author: Agent Guru Team
Date: 2026
"""

import argparse
import random
import re
from pathlib import Path
from typing import Any

import yaml

# Additional utterance templates per intent
EXPANSION_TEMPLATES = {
    "set_timer": [
        "set timer for {duration}",
        "start a {duration} timer",
        "create timer {duration}",
        "timer for {duration} please",
        "I need a {duration} timer",
        "can you set a timer for {duration}",
        "set a {duration} countdown",
        "start countdown for {duration}",
        "begin timer {duration}",
        "make a timer for {duration}",
    ],
    "set_alarm": [
        "set alarm for {time}",
        "wake me up at {time}",
        "alarm at {time}",
        "create alarm {time}",
        "set an alarm for {time}",
        "I need an alarm at {time}",
        "alarm for {time} please",
        "wake me at {time}",
        "set wake up alarm {time}",
        "alarm me at {time}",
    ],
    "query_weather": [
        "what's the weather",
        "weather forecast",
        "how's the weather",
        "tell me the weather",
        "weather today",
        "what's it like outside",
        "is it raining",
        "will it rain today",
        "temperature outside",
        "weather report",
    ],
    "play_music": [
        "play music",
        "play some music",
        "start music",
        "I want to listen to music",
        "play a song",
        "put on some music",
        "music please",
        "play my playlist",
        "start playing music",
        "turn on music",
    ],
    "send_message": [
        "send message",
        "text someone",
        "send a text",
        "message someone",
        "send text message",
        "I want to send a message",
        "compose message",
        "write a message",
        "send sms",
        "text message",
    ],
    "make_call": [
        "call someone",
        "make a call",
        "phone someone",
        "dial number",
        "I want to call",
        "place a call",
        "ring someone",
        "call please",
        "make phone call",
        "start call",
    ],
    "open_app": [
        "open app",
        "launch app",
        "start app",
        "open application",
        "run app",
        "I want to open app",
        "launch application",
        "start application",
        "open program",
        "run application",
    ],
    "close_app": [
        "close app",
        "quit app",
        "exit app",
        "stop app",
        "close application",
        "shut down app",
        "kill app",
        "terminate app",
        "end app",
        "close program",
    ],
    "volume_up": [
        "volume up",
        "increase volume",
        "louder",
        "turn up volume",
        "make it louder",
        "raise volume",
        "boost volume",
        "volume higher",
        "increase sound",
        "turn it up",
    ],
    "volume_down": [
        "volume down",
        "decrease volume",
        "quieter",
        "turn down volume",
        "make it quieter",
        "lower volume",
        "reduce volume",
        "volume lower",
        "decrease sound",
        "turn it down",
    ],
    "mute": [
        "mute",
        "silence",
        "turn off sound",
        "mute audio",
        "silence audio",
        "no sound",
        "mute volume",
        "turn off volume",
        "silence please",
        "quiet",
    ],
    "unmute": [
        "unmute",
        "turn on sound",
        "unmute audio",
        "sound on",
        "enable sound",
        "restore sound",
        "unmute volume",
        "turn on volume",
        "sound please",
        "audio on",
    ],
}


DEFAULT_TRAIN_FILE = Path(__file__).resolve().parent / "train_annotated.yaml"


def expand_examples(train_data: list[dict[str, Any]], rng: random.Random) -> list[dict[str, Any]]:
    """Return train_data plus up to 2x as many new examples per intent.

    rng decides every choice, so the same data and seed give the same output.
    The draws used to come from the secrets module, which cannot be seeded:
    two runs over the same data wrote different training sets.

    A new example is kept only if every entity it carries can be located in
    its new text, with start and end recomputed for that text, and no
    template placeholder is left in it. The old version copied the base
    example's offsets onto a different sentence and filled placeholders from
    a "value" key that this data does not have (it uses "text"): one run over
    the 2,448 training examples added 20 sentences with a literal
    placeholder such as "create alarm {time}" and 848 entity spans that
    pointed at the wrong characters.
    """
    seen_utterances = {item["utterance"].lower().strip() for item in train_data}

    intent_groups: dict[str, list[dict[str, Any]]] = {}
    for item in train_data:
        intent_groups.setdefault(item["intent"], []).append(item)

    expanded_data = list(train_data)
    # Sorted, so the order of draws does not depend on the file's order of intents.
    for intent in sorted(intent_groups):
        examples = intent_groups[intent]
        wanted = len(examples) * 2  # to 3x the original count
        templates = EXPANSION_TEMPLATES.get(intent, [])
        added = 0
        for _ in range(wanted * 10):  # bounded: duplicates and misses are rejected
            if added >= wanted:
                break
            base_example = rng.choice(examples)
            if templates:
                utterance = fill_template(rng.choice(templates), base_example)
            else:
                utterance = paraphrase_utterance(base_example["utterance"], rng)
            if "{" in utterance or utterance.lower().strip() in seen_utterances:
                continue
            entities = relocate_entities(utterance, base_example.get("entities", []))
            if entities is None:
                continue
            seen_utterances.add(utterance.lower().strip())
            expanded_data.append({"utterance": utterance, "intent": intent, "entities": entities})
            added += 1
    return expanded_data


def relocate_entities(utterance: str, entities: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """Copy entities onto a new utterance with offsets found in it, or None if any is absent."""
    located = []
    for entity in entities:
        text = entity.get("text") or entity.get("value") or ""
        match = re.search(re.escape(text), utterance, flags=re.IGNORECASE) if text else None
        if match is None:
            return None
        located.append({**entity, "start": match.start(), "end": match.end(),
                        "text": utterance[match.start():match.end()]})
    return located


def expand_dataset(input_file: Path, output_file: Path, seed: int | None = None) -> int:
    """Expand input_file into output_file; return the number of examples written."""
    with open(input_file, encoding="utf-8") as f:
        train_data = yaml.safe_load(f)
    expanded = expand_examples(train_data, random.Random(seed))  # nosec B311 - not security
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(expanded, f, default_flow_style=False, allow_unicode=True)
    return len(expanded)


def paraphrase_utterance(utterance: str, rng: random.Random) -> str:
    """Simple paraphrasing using substitutions."""
    substitutions = {
        "can you": ["could you", "would you", "please"],
        "I need": ["I want", "I'd like", "give me"],
        "set a": ["create a", "make a", "start a"],
        "turn on": ["switch on", "enable", "activate"],
        "turn off": ["switch off", "disable", "deactivate"],
        "open": ["launch", "start", "run"],
        "close": ["quit", "exit", "stop"],
    }

    for original, replacements in substitutions.items():
        # Matched without regard to case; replacing only the exact-case text
        # used to leave "Can you ..." unchanged, which was then rejected as a
        # duplicate and wasted the attempt.
        pattern = re.compile(re.escape(original), re.IGNORECASE)
        if pattern.search(utterance):
            return pattern.sub(rng.choice(replacements), utterance, count=1)
    return utterance


def fill_template(template: str, example: dict) -> str:
    """Fill template placeholders with the example's entity texts."""
    utterance = template
    for entity in example.get("entities", []):
        entity_type = entity.get("entity") or entity.get("type", "")
        entity_value = entity.get("text") or entity.get("value", "")
        if entity_type and entity_value:
            utterance = utterance.replace(f"{{{entity_type}}}", entity_value)
    return utterance


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Expand the intent training set to about 3x.")
    parser.add_argument("--input", type=Path, default=DEFAULT_TRAIN_FILE)
    parser.add_argument(
        "--output", type=Path, default=None,
        help="where to write (default: overwrite --input, as this script always did)",
    )
    parser.add_argument("--seed", type=int, default=None, help="make the output reproducible")
    args = parser.parse_args(argv)
    count = expand_dataset(args.input, args.output or args.input, args.seed)
    print(f"wrote {count} examples to {args.output or args.input}")


if __name__ == "__main__":
    main()
