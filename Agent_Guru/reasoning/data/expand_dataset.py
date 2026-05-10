"""Expand Dataset to 3x Size for MAXIMUM Accuracy.

This script generates additional high-quality training examples
to reach 200+ examples per intent for 98%+ accuracy.

Author: Agent Guru Team
Date: 2026
"""

import secrets
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


def expand_dataset() -> None:
    """Expand dataset to 3x size with high-quality examples - OVERWRITES original file."""
    # Load existing data
    data_dir = Path("Agent_Guru/reasoning/data")
    train_file = data_dir / "train_annotated.yaml"

    with open(train_file) as f:  # noqa: PTH123
        train_data = yaml.safe_load(f)

    # Track all utterances to prevent duplication
    seen_utterances = set()
    for item in train_data:
        seen_utterances.add(item["utterance"].lower().strip())

    # Group by intent
    intent_groups: dict[str, list[dict[str, Any]]] = {}
    for item in train_data:
        intent = item["intent"]
        if intent not in intent_groups:
            intent_groups[intent] = []
        intent_groups[intent].append(item)

    # Expand each intent
    expanded_data = list(train_data)  # Start with original

    for intent, examples in intent_groups.items():
        current_count = len(examples)
        target_count = current_count * 3  # 3x expansion

        # Get templates for this intent
        templates = EXPANSION_TEMPLATES.get(intent, [])

        attempts = 0
        max_attempts = (target_count - current_count) * 10  # Try 10x to avoid infinite loop
        added = 0

        while added < (target_count - current_count) and attempts < max_attempts:
            attempts += 1

            if not templates:
                # Use paraphrasing for intents without templates
                base_example = secrets.choice(examples)
                utterance = base_example["utterance"]

                # Simple paraphrasing
                paraphrased = paraphrase_utterance(utterance)

                # Check for duplication
                if paraphrased.lower().strip() not in seen_utterances:
                    seen_utterances.add(paraphrased.lower().strip())
                    expanded_data.append(
                        {
                            "utterance": paraphrased,
                            "intent": intent,
                            "entities": base_example["entities"],
                        },
                    )
                    added += 1
            else:
                # Use templates
                template = secrets.choice(templates)

                # Fill template with entities from random example
                base_example = secrets.choice(examples)
                utterance = fill_template(template, base_example)

                # Check for duplication
                if utterance.lower().strip() not in seen_utterances:
                    seen_utterances.add(utterance.lower().strip())
                    expanded_data.append(
                        {
                            "utterance": utterance,
                            "intent": intent,
                            "entities": base_example["entities"],
                        },
                    )
                    added += 1

    # OVERWRITE original file - NO DUPLICATES
    with open(train_file, "w", encoding="utf-8") as f:  # noqa: PTH123
        yaml.dump(expanded_data, f, default_flow_style=False, allow_unicode=True)

    # Update stats
    intent_counts: dict[str, int] = {}
    for item in expanded_data:
        intent = item["intent"]
        intent_counts[intent] = intent_counts.get(intent, 0) + 1

    for _intent, _count in sorted(intent_counts.items()):
        pass


def paraphrase_utterance(utterance: str) -> str:
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

    result = utterance
    for original, replacements in substitutions.items():
        if original in utterance.lower():
            replacement = secrets.choice(replacements)
            result = result.replace(original, replacement)
            break

    return result


def fill_template(template: str, example: dict) -> str:
    """Fill template with entities from example."""
    utterance = template

    # Extract entities
    for entity in example.get("entities", []):
        # Handle both 'entity' and 'type' keys
        entity_type = entity.get("entity") or entity.get("type", "")
        entity_value = entity.get("value", "")

        if not entity_type or not entity_value:
            continue

        # Replace placeholder
        placeholder = f"{{{entity_type}}}"
        if placeholder in utterance:
            utterance = utterance.replace(placeholder, entity_value)

    return utterance


if __name__ == "__main__":
    expand_dataset()
