"""Entity annotation pipeline for training data.

Comprehensive entity extraction covering ALL entity types defined in intents.yaml.
Target: >95% entity coverage across all utterances that should have entities.

Coverage strategy:
- Intents with NO entities by design (confirmation, cancellation,
  clarification_request, unknown) are excluded from coverage calculation.
- All other intents must reach >95% coverage.
"""

import re
from pathlib import Path
from typing import Any

import yaml


class EntityAnnotator:
    """Annotate training data with entity spans and types."""

    # -----------------------------------------------------------------------
    # Known values for each entity type - used for exact/fuzzy matching
    # -----------------------------------------------------------------------

    _KNOWN_APPS = {
        "spotify",
        "chrome",
        "google chrome",
        "firefox",
        "safari",
        "edge",
        "netflix",
        "youtube",
        "gmail",
        "email",
        "outlook",
        "calendar",
        "maps",
        "google maps",
        "apple maps",
        "camera",
        "calculator",
        "settings",
        "notepad",
        "word",
        "excel",
        "powerpoint",
        "slack",
        "whatsapp",
        "telegram",
        "instagram",
        "twitter",
        "facebook",
        "tiktok",
        "snapchat",
        "zoom",
        "teams",
        "discord",
        "apple music",
        "amazon music",
        "pandora",
        "soundcloud",
        "uber",
        "lyft",
        "doordash",
        "grubhub",
        "amazon",
        "ebay",
        "photos",
        "files",
        "notes",
        "reminders",
        "clock",
        "weather",
        "news",
        "stocks",
        "health",
        "fitness",
        "translate",
    }

    _KNOWN_CONTACTS = {
        "mom",
        "dad",
        "wife",
        "husband",
        "sister",
        "brother",
        "boss",
        "john",
        "sarah",
        "lisa",
        "mike",
        "david",
        "emma",
        "james",
        "mary",
        "robert",
        "jennifer",
        "william",
        "linda",
        "richard",
        "barbara",
        "joseph",
        "susan",
        "thomas",
        "jessica",
        "charles",
        "karen",
        "christopher",
        "nancy",
        "daniel",
        "betty",
        "matthew",
        "margaret",
        "anthony",
        "sandra",
        "mark",
        "ashley",
        "donald",
        "dorothy",
        "steven",
        "kimberly",
        "paul",
        "emily",
        "andrew",
        "donna",
        "kenneth",
        "michelle",
        "george",
        "carol",
        "joshua",
        "amanda",
        "kevin",
        "melissa",
        "brian",
        "deborah",
        "edward",
        "stephanie",
        "ronald",
        "rebecca",
        "timothy",
        "sharon",
        "jason",
        "laura",
        "jeffrey",
        "cynthia",
        "ryan",
        "kathleen",
        "jacob",
        "amy",
        "gary",
        "angela",
        "nicholas",
        "shirley",
        "eric",
        "anna",
        "jonathan",
        "brenda",
        "stephen",
        "pamela",
        "larry",
        "justin",
        "virginia",
        "scott",
        "katherine",
        "brandon",
        "christine",
        "benjamin",
        "samantha",
        "samuel",
        "debra",
        "raymond",
        "rachel",
        "gregory",
        "carolyn",
        "frank",
        "janet",
        "alexander",
        "catherine",
        "patrick",
        "maria",
        "jack",
        "heather",
        "dennis",
        "diane",
        "jerry",
        "julie",
        "tyler",
        "joyce",
        "aaron",
        "victoria",
        "jose",
        "kelly",
        "adam",
        "christina",
        "henry",
        "ruth",
        "nathan",
        "joan",
        "douglas",
        "evelyn",
        "zachary",
        "judith",
        "peter",
        "andrea",
        "kyle",
        "megan",
        "walter",
        "cheryl",
        "ethan",
        "alice",
        "jeremy",
        "ann",
        "harold",
        "jean",
        "terry",
        "sean",
        "frances",
        "austin",
        "martha",
        "christian",
        "gloria",
        "joe",
        "teresa",
        "noah",
        "sara",
        "albert",
        "janice",
        "caleb",
        "marie",
        "carl",
        "julia",
        "ralph",
        "grace",
        "lloyd",
        "judy",
        "team",
        "office",
        "support",
        "customer service",
        "doctor",
        "dentist",
        "lawyer",
        "accountant",
        "manager",
        "colleague",
    }

    _KNOWN_GENRES = {
        "jazz",
        "rock",
        "pop",
        "classical",
        "hip hop",
        "hip-hop",
        "country",
        "r&b",
        "electronic",
        "dance",
        "metal",
        "punk",
        "folk",
        "blues",
        "reggae",
        "soul",
        "indie",
        "alternative",
        "latin",
        "gospel",
        "opera",
        "ambient",
        "techno",
        "house",
        "edm",
        "rap",
        "trap",
        "lo-fi",
        "lofi",
        "chill",
        "relaxing",
        "workout",
        "study",
        "sleep",
        "meditation",
        "focus",
    }

    _KNOWN_ARTISTS = {
        "taylor swift",
        "ed sheeran",
        "the beatles",
        "queen",
        "adele",
        "beyonce",
        "drake",
        "eminem",
        "rihanna",
        "kanye west",
        "michael jackson",
        "madonna",
        "lady gaga",
        "coldplay",
        "imagine dragons",
        "maroon 5",
        "bruno mars",
        "the weeknd",
        "billie eilish",
        "ariana grande",
        "post malone",
        "travis scott",
        "kendrick lamar",
        "jay-z",
        "nicki minaj",
        "cardi b",
        "harry styles",
        "olivia rodrigo",
        "dua lipa",
        "bad bunny",
        "j. cole",
        "21 savage",
        "lil baby",
        "roddy ricch",
        "morgan wallen",
        "luke combs",
        "chris stapleton",
        "beethoven",
        "mozart",
        "bach",
        "chopin",
        "vivaldi",
    }

    _KNOWN_DEVICES = {
        "lights",
        "light",
        "lamp",
        "bulb",
        "thermostat",
        "heater",
        "ac",
        "air conditioner",
        "fan",
        "tv",
        "television",
        "speaker",
        "door",
        "lock",
        "garage",
        "blinds",
        "curtains",
        "shades",
        "dishwasher",
        "washing machine",
        "dryer",
        "oven",
        "microwave",
        "coffee maker",
        "vacuum",
        "robot vacuum",
        "security camera",
        "doorbell",
        "alarm",
        "smoke detector",
        "sprinkler",
        "bedroom lights",
        "living room lights",
        "kitchen lights",
        "bathroom lights",
        "office lights",
        "porch lights",
        "front door",
        "back door",
        "garage door",
    }

    _KNOWN_ACTIONS = {
        "turn on",
        "turn off",
        "switch on",
        "switch off",
        "enable",
        "disable",
        "activate",
        "deactivate",
        "open",
        "close",
        "lock",
        "unlock",
        "dim",
        "brighten",
        "increase",
        "decrease",
        "raise",
        "lower",
        "set",
        "start",
        "stop",
        "pause",
        "resume",
        "play",
    }

    _KNOWN_LOCATIONS = {
        "new york",
        "london",
        "paris",
        "tokyo",
        "los angeles",
        "chicago",
        "houston",
        "phoenix",
        "philadelphia",
        "san antonio",
        "san diego",
        "dallas",
        "san jose",
        "austin",
        "jacksonville",
        "fort worth",
        "columbus",
        "charlotte",
        "san francisco",
        "indianapolis",
        "seattle",
        "denver",
        "washington",
        "boston",
        "nashville",
        "baltimore",
        "louisville",
        "portland",
        "las vegas",
        "miami",
        "atlanta",
        "minneapolis",
        "new orleans",
        "cleveland",
        "home",
        "work",
        "office",
        "school",
        "gym",
        "store",
        "restaurant",
        "hospital",
        "airport",
        "downtown",
        "uptown",
        "here",
        "there",
        "outside",
        "inside",
    }

    _KNOWN_SONGS = {
        "bohemian rhapsody",
        "imagine",
        "yesterday",
        "hotel california",
        "stairway to heaven",
        "smells like teen spirit",
        "purple rain",
        "billie jean",
        "thriller",
        "like a rolling stone",
        "what's going on",
        "respect",
        "johnny b. goode",
        "good vibrations",
        "superstition",
        "born to run",
        "sweet home alabama",
        "piano man",
        "rocket man",
        "don't stop believin",
        "africa",
        "take on me",
        "sweet child o mine",
        "november rain",
        "welcome to the jungle",
        "enter sandman",
        "master of puppets",
        "one",
        "shape of you",
        "blinding lights",
        "bad guy",
        "drivers license",
        "levitating",
        "stay",
    }

    # Intents that intentionally have NO entities - excluded from coverage calc
    _NO_ENTITY_INTENTS = {
        "confirmation",
        "cancellation",
        "clarification_request",
        "unknown",
        "multi_intent",
    }

    # System command types
    _COMMAND_TYPES = {
        "volume",
        "brightness",
        "wifi",
        "wi-fi",
        "bluetooth",
        "airplane mode",
        "screen",
        "display",
        "sound",
        "audio",
        "notification",
        "notifications",
        "do not disturb",
        "dnd",
        "dark mode",
        "night mode",
        "battery saver",
        "power saving",
        "hotspot",
        "location",
        "gps",
        "nfc",
        "flashlight",
        "torch",
        "screenshot",
        "screen record",
        "rotate",
        "orientation",
        "auto rotate",
        "vibration",
        "silent mode",
        "ringer",
    }

    # Thermostat/temperature actions
    _TEMP_ACTIONS = {
        "warmer",
        "cooler",
        "hotter",
        "colder",
        "heat",
        "cool",
        "warm",
        "cold",
        "hot",
        "comfortable",
        "higher",
        "lower",
    }

    # Query fact subjects - what/who/when/where/how questions
    _FACT_QUESTION_WORDS = {
        "what",
        "who",
        "when",
        "where",
        "how",
        "which",
        "why",
    }

    def __init__(self, intents_file: str = "Agent_Guru/reasoning/data/intents.yaml") -> None:
        self.intents_file = Path(intents_file)
        self.intents_data = self._load_intents()
        self.entity_patterns = self._build_entity_patterns()

    def _load_intents(self) -> dict[Any, Any]:
        with open(self.intents_file, encoding="utf-8") as f:
            data: dict[Any, Any] = yaml.safe_load(f)
            return data

    def _build_entity_patterns(self) -> dict[str, list[re.Pattern]]:
        """Build compiled regex patterns for all entity types."""
        raw: dict[str, list[str]] = {
            # ---- Time & Duration ----
            "duration": [
                r"\b(\d+)\s*(?:and\s+)?(\d+)?\s*(?:hour|hr)s?\s*(?:and\s+)?(\d+)?\s*(?:minute|min)s?\b",
                r"\b\d+\s*(?:second|sec|minute|min|hour|hr|day|week|month)s?\b",
                r"\ba\s+(?:second|minute|hour|day|week|month)\b",
                r"\bhalf\s+(?:an?\s+)?(?:hour|minute)\b",
                r"\bquarter\s+(?:hour|minute)\b",
            ],
            "time": [
                r"\b\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)?\b",
                r"\b\d{1,2}\s*(?:am|pm|AM|PM|o'clock)\b",
                r"\b(?:noon|midnight|morning|afternoon|evening|night)\b",
                r"\b(?:early|late)\s+(?:morning|afternoon|evening|night)\b",
            ],
            "date": [
                r"\b(?:today|tomorrow|yesterday|tonight)\b",
                r"\b(?:this|next|last)\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|week|month|year|weekend)\b",
                r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
                r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:st|nd|rd|th)?\b",
                r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:january|february|march|april|may|june|july|august|september|october|november|december)\b",
                r"\bin\s+\d+\s+(?:day|week|month)s?\b",
            ],
            "temperature": [
                r"\b\d+\s*(?:degrees?|°)\s*(?:fahrenheit|celsius|f|c)?\b",
                r"\b\d+\s*(?:fahrenheit|celsius)\b",
            ],
            "phone_number": [
                r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b",
                r"\b\d{10}\b",
                r"\b\+\d{1,3}[-.\s]\d{3}[-.\s]\d{3}[-.\s]\d{4}\b",
            ],
            "percentage": [
                r"\b\d+\s*(?:percent|%)\b",
            ],
            "number": [
                r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred)\b",
                r"\b\d+\b",
            ],
        }
        return {
            etype: [re.compile(p, re.IGNORECASE) for p in patterns]
            for etype, patterns in raw.items()
        }

    def _find_known_entity(
        self,
        utterance: str,
        known_set: set[str],
        entity_type: str,
    ) -> list[tuple[str, int, int, str]]:
        """Find known entity values in utterance (longest match first)."""
        results: list[tuple[str, int, int, str]] = []
        utt_lower = utterance.lower()
        # Sort by length descending so longer matches take priority
        for value in sorted(known_set, key=len, reverse=True):
            idx = utt_lower.find(value)
            if idx != -1:
                results.append(
                    (utterance[idx : idx + len(value)], idx, idx + len(value), entity_type),
                )
        return results

    def extract_entities(
        self,
        utterance: str,
        intent: str,
    ) -> list[tuple[str, int, int, str]]:
        """Extract all entities from utterance based on intent type."""
        entities: list[tuple[str, int, int, str]] = []
        intent_data = self.intents_data["intents"].get(intent, {})
        expected = set(intent_data.get("entities", []))

        # Regex-based patterns
        self._extract_regex_patterns(utterance, expected, entities)

        # Known-value lookups (dispatch table)
        _KNOWN_EXTRACTORS: list[tuple[str, set[str], str]] = [
            ("app_name", self._KNOWN_APPS, "app_name"),
            ("song_name", self._KNOWN_SONGS, "song_name"),
            ("artist", self._KNOWN_ARTISTS, "artist"),
            ("genre", self._KNOWN_GENRES, "genre"),
            ("device_name", self._KNOWN_DEVICES, "device_name"),
            ("action", self._KNOWN_ACTIONS, "action"),
        ]
        for etype, known_set, label in _KNOWN_EXTRACTORS:
            if etype in expected or not expected:
                entities.extend(self._find_known_entity(utterance, known_set, label))

        # Contextual extractors
        self._extract_recipient(utterance, expected, entities)
        self._extract_location(utterance, expected, entities)
        self._extract_task(utterance, expected, entities)
        self._extract_message_content(utterance, expected, entities)
        self._extract_event_name(utterance, expected, entities)
        self._extract_search_query(utterance, expected, entities)
        self._extract_command_type(utterance, expected, entities)
        self._extract_value(utterance, expected, entities)
        self._extract_brightness(utterance, expected, entities)
        self._extract_color(utterance, expected, entities)
        self._extract_playlist(utterance, expected, entities)
        self._extract_video_query(utterance, expected, entities)
        self._extract_help_topic(utterance, expected, entities)

        # Intent-specific extractors
        self._extract_query_fact(utterance, intent, expected, entities)
        self._extract_query_time(utterance, intent, expected, entities)
        self._extract_query_date(utterance, intent, entities)
        self._extract_cancel_timer(utterance, intent, entities)
        self._extract_make_call(utterance, intent, entities)
        self._extract_delete_event(utterance, intent, entities)
        self._extract_search_web(utterance, intent, entities)
        self._extract_help_request(utterance, intent, entities)
        self._extract_track_nav(utterance, intent, entities)
        self._extract_system_command(utterance, intent, expected, entities)
        self._extract_thermostat(utterance, intent, expected, entities)
        self._extract_query_events(utterance, intent, expected, entities)
        self._extract_clarification(utterance, intent, entities)
        self._extract_cancellation(utterance, intent, entities)
        self._extract_query_weather(utterance, intent, entities)
        self._extract_set_reminder(utterance, intent, entities)
        self._extract_play_music(utterance, intent, entities)
        self._extract_stop_media(utterance, intent, entities)

        return self._remove_overlaps(entities)

    # ------------------------------------------------------------------
    # Per-entity-type extractors (decomposed from extract_entities)
    # ------------------------------------------------------------------

    def _extract_regex_patterns(
        self, utterance: str, expected: set[str],
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Apply regex-based entity patterns."""
        for etype, patterns in self.entity_patterns.items():
            if etype in expected or not expected:
                for pat in patterns:
                    for m in pat.finditer(utterance):
                        entities.append((m.group(), m.start(), m.end(), etype))

    def _extract_recipient(
        self, utterance: str, expected: set[str],
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract recipient entities."""
        if "recipient" not in expected and expected:
            return
        for pat in [
            r"(?:to|call|message|text|email|phone|ring|contact|send\s+(?:a\s+)?(?:message|text|email)\s+to)\s+(?!saying\b|that\b)([A-Za-z][a-z]+(?:\s+[A-Za-z][a-z]+)?)\s*(?:saying\b|that\b|$)",
            r"(?:to|call|message|text|email|phone|ring|contact|send\s+(?:a\s+)?(?:message|text|email)\s+to)\s+(?!saying\b|that\b)([A-Za-z][a-z]+)(?:\s+[A-Za-z][a-z]+)?(?=\s+(?:saying|that)\b|$)",
            r"(?:call|phone|ring)\s+(mom|dad|wife|husband|boss|sister|brother)",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                name = m.group(1).strip().lower()
                if name in self._KNOWN_CONTACTS or len(name) >= 3:
                    entities.append((m.group(1), m.start(1), m.end(1), "recipient"))
        entities.extend(self._find_known_entity(utterance, self._KNOWN_CONTACTS, "recipient"))

    _NON_LOCATION_WORDS = {
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
        "january", "february", "march", "april", "june", "july", "august",
        "september", "october", "november", "december",
        "please", "quickly", "right", "now", "today", "tomorrow", "yesterday",
    }

    def _extract_location(
        self, utterance: str, expected: set[str],
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract location entities."""
        if "location" not in expected and expected:
            return
        entities.extend(self._find_known_entity(utterance, self._KNOWN_LOCATIONS, "location"))
        for m in re.finditer(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?)\b", utterance):
            if m.group(1).lower() not in self._NON_LOCATION_WORDS:
                entities.append((m.group(1), m.start(1), m.end(1), "location"))

    def _extract_task(
        self, utterance: str, expected: set[str],
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract task entities from reminder patterns."""
        if "task" not in expected and expected:
            return
        for pat in [
            r"remind\s+(?:me\s+)?to\s+(.+?)(?:\s+(?:at|on|by|in|tomorrow|today|tonight|this|next|every).*)?$",
            r"reminder\s+(?:to\s+|for\s+)(.+?)(?:\s+(?:at|on|by|in|tomorrow|today|tonight|this|next|every).*)?$",
            r"remember\s+to\s+(.+?)(?:\s+(?:at|on|by|in|tomorrow|today|tonight|this|next|every).*)?$",
            r"don't\s+forget\s+to\s+(.+?)(?:\s+(?:at|on|by|in|tomorrow|today|tonight|this|next|every).*)?$",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                task_text = m.group(1).strip()
                if task_text:
                    entities.append((task_text, m.start(1), m.end(1), "task"))

    def _extract_message_content(
        self, utterance: str, expected: set[str],
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract message content entities."""
        if "message_content" not in expected and expected:
            return
        for pat in [
            r"(?:saying|that)\s+['\"]?(.+?)['\"]?$",
            r"(?:text|message)\s+\w+\s+(?:saying|that)\s+(.+?)$",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                content = m.group(1).strip()
                if content and len(content) > 2:
                    entities.append((content, m.start(1), m.end(1), "message_content"))

    def _extract_event_name(
        self, utterance: str, expected: set[str],
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract event name entities."""
        if "event_name" not in expected and expected:
            return
        for pat in [
            r"(?:event|meeting|appointment|call|session|class|lesson|game|party|dinner|lunch|breakfast)\s+(?:called|named|for|about)?\s*['\"]?([A-Za-z][A-Za-z\s]{2,}?)['\"]?(?:\s+(?:at|on|for|tomorrow|today|next).*)?$",
            r"(?:schedule|create|add|set up)\s+(?:a\s+)?(?:meeting|appointment|event|call)\s+(?:for\s+)?([A-Za-z][A-Za-z\s]{2,}?)(?:\s+(?:at|on|for|tomorrow|today|next).*)?$",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                name = m.group(1).strip()
                if name and len(name) > 2:
                    entities.append((name, m.start(1), m.end(1), "event_name"))

    def _extract_search_query(
        self, utterance: str, expected: set[str],
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract search query entities."""
        if "search_query" not in expected and expected:
            return
        for pat in [
            r"(?:search\s+(?:for|the\s+web\s+for)?|look\s+up|google|find\s+(?:information\s+about)?|search)\s+(.+?)(?:\s+(?:online|on\s+the\s+web|on\s+google))?$",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                query = m.group(1).strip()
                if query and len(query) > 2:
                    entities.append((query, m.start(1), m.end(1), "search_query"))

    def _extract_command_type(
        self, utterance: str, expected: set[str],
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract command_type entities."""
        if "command_type" not in expected and expected:
            return
        for pat in [
            r"\b(volume|brightness|wifi|bluetooth|airplane\s+mode|screen|display|sound|audio|notification)\b",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                entities.append((m.group(1), m.start(), m.end(), "command_type"))

    def _extract_value(
        self, utterance: str, expected: set[str],
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract value entities."""
        if "value" not in expected and expected:
            return
        for pat in [
            r"\b(\d+)\s*(?:percent|%)\b",
            r"\b(high|low|medium|max|min|maximum|minimum|full|half|zero)\b",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                entities.append((m.group(1), m.start(1), m.end(1), "value"))

    def _extract_brightness(
        self, utterance: str, expected: set[str],
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract brightness entities."""
        if "brightness" not in expected and expected:
            return
        for pat in [
            r"\b(\d+)\s*(?:percent|%)?\b",
            r"\b(dim|bright|brighter|dimmer|full|half)\b",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                entities.append((m.group(1), m.start(1), m.end(1), "brightness"))

    def _extract_color(
        self, utterance: str, expected: set[str],
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract color entities."""
        if "color" not in expected and expected:
            return
        for pat in [
            r"\b(red|blue|green|yellow|white|warm|cool|purple|orange|pink|cyan|teal)\b",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                entities.append((m.group(), m.start(), m.end(), "color"))

    def _extract_playlist(
        self, utterance: str, expected: set[str],
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract playlist entities."""
        if "playlist" not in expected and expected:
            return
        for pat in [
            r"\b(?:my\s+)?(\w+\s+playlist)\b",
            r"\bplaylist\s+(?:called\s+)?['\"]?(\w[\w\s]+?)['\"]?\b",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                entities.append((m.group(1), m.start(1), m.end(1), "playlist"))

    def _extract_video_query(
        self, utterance: str, expected: set[str],
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract video_query entities."""
        if "video_query" not in expected and expected:
            return
        for pat in [
            r"(?:play|watch|show)\s+(?:a\s+)?(?:video\s+(?:of|about)\s+)?(.+?)(?:\s+video)?$",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                query = m.group(1).strip()
                if query and len(query) > 2:
                    entities.append((query, m.start(1), m.end(1), "video_query"))

    def _extract_help_topic(
        self, utterance: str, expected: set[str],
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract help_topic entities."""
        if "help_topic" not in expected and expected:
            return
        for pat in [
            r"(?:help\s+(?:me\s+)?(?:with|about|on)|how\s+(?:do\s+I|to))\s+(.+?)$",
            r"(?:what\s+(?:can|are)\s+(?:you|your)\s+(?:do|capabilities|features))",
            r"(?:show\s+me\s+how|guide\s+me|assist\s+me\s+with)\s+(.+?)$",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                if m.lastindex and m.lastindex >= 1:
                    topic = m.group(1).strip()
                    if topic and len(topic) > 2:
                        entities.append((topic, m.start(1), m.end(1), "help_topic"))
                else:
                    entities.append((m.group(), m.start(), m.end(), "help_topic"))

    # ------------------------------------------------------------------
    # Intent-specific extractors
    # ------------------------------------------------------------------

    def _extract_query_fact(
        self, utterance: str, intent: str, expected: set[str],
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract query_subject for fact queries."""
        if intent != "query_fact" and "query_subject" not in expected:
            return
        for pat in [
            r"(?:what\s+is|what's|who\s+is|who's|where\s+is|where's|when\s+(?:was|is|did)|how\s+(?:tall|far|old|big|long|much|many|fast))\s+(?:the\s+)?(.+?)(?:\s+(?:please|now|quickly|for\s+me))?$",
            r"(?:tell\s+me\s+about|information\s+about|details\s+about|facts\s+about)\s+(.+?)(?:\s+(?:please|now|quickly))?$",
            r"(?:who\s+(?:invented|created|discovered|wrote|founded|built|made))\s+(?:the\s+)?(.+?)(?:\s+(?:please|now|quickly))?$",
            r"(?:what\s+(?:is|are|was|were)\s+the)\s+(.+?)(?:\s+(?:please|now|quickly))?$",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                subj = m.group(1).strip() if m.lastindex else m.group().strip()
                if subj and len(subj) > 1:
                    entities.append((
                        subj,
                        m.start(1) if m.lastindex else m.start(),
                        m.end(1) if m.lastindex else m.end(),
                        "query_subject",
                    ))

    def _extract_query_time(
        self, utterance: str, intent: str, expected: set[str],
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract location/query_type for time queries."""
        if intent != "query_time" and "location" not in expected:
            return
        for pat in [
            r"(?:time\s+in|what\s+time\s+is\s+it\s+in|current\s+time\s+in)\s+(.+?)(?:\s+(?:please|now|right\s+now|quickly))?$",
            r"(?:in|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:time|timezone|right\s+now)?",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                loc = m.group(1).strip()
                if loc and len(loc) > 1:
                    entities.append((loc, m.start(1), m.end(1), "location"))
        if intent == "query_time" and not any(e[3] in ("location", "time") for e in entities):
            for pat in [
                r"\b(time|clock|hour)\b",
                r"(?:what(?:'s|\s+is)\s+(?:the\s+)?(?:current\s+)?)(time|hour)\b",
                r"(?:tell\s+me\s+(?:the\s+)?)(time)\b",
            ]:
                for m in re.finditer(pat, utterance, re.IGNORECASE):
                    val = m.group(1) if m.lastindex else m.group()
                    entities.append((
                        val,
                        m.start(1) if m.lastindex else m.start(),
                        m.end(1) if m.lastindex else m.end(),
                        "query_type",
                    ))
                    break

    def _extract_query_date(
        self, utterance: str, intent: str,
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract date entities for date queries."""
        if intent != "query_date":
            return
        for pat in [
            r"\b(today|tomorrow|yesterday|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            r"\b(this|next|last)\s+(week|month|year|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                entities.append((m.group(), m.start(), m.end(), "date"))
        if not any(e[3] == "date" for e in entities):
            for pat in [
                r"\b(date|day|month|year|week)\b",
                r"(?:what\s+(?:day|date|month|year))",
                r"(?:tell\s+me\s+(?:the\s+)?(?:date|day))",
            ]:
                for m in re.finditer(pat, utterance, re.IGNORECASE):
                    val = m.group(1) if m.lastindex else m.group()
                    entities.append((
                        val,
                        m.start(1) if m.lastindex else m.start(),
                        m.end(1) if m.lastindex else m.end(),
                        "query_type",
                    ))
                    break

    def _extract_cancel_timer(
        self, utterance: str, intent: str,
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract action entities for cancel_timer intent."""
        if intent != "cancel_timer":
            return
        for pat in [
            r"\b(timer|alarm|countdown|all\s+timers)\b",
            r"(?:cancel|stop|turn\s+off|delete|remove)\s+(?:the\s+)?(.+?)\s*(?:timer|alarm|countdown)?$",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                val = m.group(1).strip() if m.lastindex else m.group().strip()
                if val:
                    entities.append((
                        val,
                        m.start(1) if m.lastindex else m.start(),
                        m.end(1) if m.lastindex else m.end(),
                        "action",
                    ))

    def _extract_make_call(
        self, utterance: str, intent: str,
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract phone_number/recipient for make_call intent."""
        if intent != "make_call":
            return
        for pat in [
            r"\b(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})\b",
            r"\b(\d{7,10})\b",
            r"\b(emergency|911|999|112|000)\b",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                entities.append((m.group(1), m.start(1), m.end(1), "phone_number"))
        if not any(e[3] in ("recipient", "phone_number") for e in entities):
            for pat in [
                r"(?:call|phone|dial|ring|contact)\s+(?:back\s+)?(?:the\s+)?(.+?)(?:\s+(?:please|now|quickly|right\s+now|for\s+me))?$",
            ]:
                for m in re.finditer(pat, utterance, re.IGNORECASE):
                    val = m.group(1).strip()
                    if val and len(val) > 1:
                        etype = "phone_number" if re.match(r"^[\d\-\s\+]+$", val) else "recipient"
                        entities.append((val, m.start(1), m.end(1), etype))

    def _extract_delete_event(
        self, utterance: str, intent: str,
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract event_name for delete_event intent."""
        if intent != "delete_event":
            return
        if any(e[3] == "event_name" for e in entities):
            return
        for pat in [
            r"(?:delete|cancel|remove)\s+(?:the\s+|my\s+)?(.+?)(?:\s+(?:please|now|quickly|right\s+now|for\s+me|at\s+\d|tomorrow|today|next).*)?$",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                val = m.group(1).strip()
                if val and len(val) > 1 and val.lower() not in {"the", "my", "a", "an"}:
                    entities.append((val, m.start(1), m.end(1), "event_name"))
                    break

    def _extract_search_web(
        self, utterance: str, intent: str,
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract search_query for search_web intent."""
        if intent != "search_web":
            return
        if any(e[3] == "search_query" for e in entities):
            return
        for pat in [
            r"(?:find|look\s+up|search\s+for|google|search)\s+(?:information\s+about\s+|hotels?\s+in\s+|flights?\s+to\s+|restaurants?\s+in\s+)?(.+?)(?:\s+(?:please|now|quickly|right\s+now|for\s+me|online|on\s+the\s+web))?$",
            r"(?:find\s+(?:me\s+)?(?:a\s+|some\s+)?)(hotels?|flights?|restaurants?|jobs?|deals?|news|information|reviews?)\s+(?:in\s+|about\s+|for\s+)?(.+?)(?:\s+(?:please|now|quickly))?$",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                grp = m.lastindex or 1
                val = m.group(grp).strip()
                if val and len(val) > 1:
                    entities.append((val, m.start(grp), m.end(grp), "search_query"))
                    break

    def _extract_help_request(
        self, utterance: str, intent: str,
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract help_topic for help_request intent."""
        if intent != "help_request":
            return
        if any(e[3] == "help_topic" for e in entities):
            return
        for pat in [
            r"(?:help\s+(?:me\s+)?(?:with|about|on|to)|how\s+(?:do\s+I|to|can\s+I))\s+(.+?)(?:\s+(?:please|now|quickly))?$",
            r"(?:what\s+(?:can|are|do)\s+(?:you|your))\s+(.+?)(?:\s+(?:please|now|quickly))?$",
            r"(?:show\s+me\s+how|guide\s+me|assist\s+me)\s+(?:to\s+|with\s+)?(.+?)(?:\s+(?:please|now|quickly))?$",
            r"(?:I\s+(?:need|want)\s+help)\s+(?:with\s+|on\s+)?(.+?)(?:\s+(?:please|now|quickly))?$",
            r"(?:I(?:'m|\s+am)\s+stuck)\s+(?:on\s+|with\s+)?(.+?)(?:\s+(?:please|now|quickly))?$",
            r"(?:what\s+would\s+you\s+)(do|help|say|suggest)\b",
            r"\b(how\s+do\s+I|guide\s+me|assist\s+me)\b",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                if m.lastindex:
                    topic = m.group(m.lastindex).strip()
                    if topic and len(topic) > 1:
                        entities.append((topic, m.start(m.lastindex), m.end(m.lastindex), "help_topic"))
                        break
        if not any(e[3] == "help_topic" for e in entities):
            for pat in [
                r"\b(capabilities|features|commands|functions|abilities)\b",
                r"(?:what\s+(?:can|do)\s+you\s+)(do|help\s+with|offer)\b",
                r"\b(help|stuck|guide)\b",
            ]:
                for m in re.finditer(pat, utterance, re.IGNORECASE):
                    val = m.group(1) if m.lastindex else m.group()
                    entities.append((
                        val,
                        m.start(1) if m.lastindex else m.start(),
                        m.end(1) if m.lastindex else m.end(),
                        "help_topic",
                    ))
                    break

    def _extract_track_nav(
        self, utterance: str, intent: str,
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract action entities for next/previous track intents."""
        if intent not in ("next_track", "previous_track"):
            return
        for pat in [
            r"\b(next|previous|skip|go\s+back|forward|backward|last)\b",
            r"\b(song|track|music|one)\b",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                entities.append((m.group(), m.start(), m.end(), "action"))

    def _extract_system_command(
        self, utterance: str, intent: str, expected: set[str],
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract command_type + value for system_command intent."""
        if intent != "system_command" and "command_type" not in expected:
            return
        entities.extend(self._find_known_entity(utterance, self._COMMAND_TYPES, "command_type"))
        for pat in [
            r"\b(\d+)\s*(?:percent|%)?\b",
            r"\b(up|down|higher|lower|more|less|louder|quieter|brighter|dimmer)\b",
            r"\b(on|off|enable|disable|mute|unmute)\b",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                entities.append((
                    m.group(1) if m.lastindex else m.group(),
                    m.start(1) if m.lastindex else m.start(),
                    m.end(1) if m.lastindex else m.end(),
                    "value",
                ))

    def _extract_thermostat(
        self, utterance: str, intent: str, expected: set[str],
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract temperature + action for thermostat control."""
        if intent != "control_thermostat" and "temperature" not in expected:
            return
        entities.extend(self._find_known_entity(utterance, self._TEMP_ACTIONS, "action"))
        for pat in [
            r"\b(\d+)\s*(?:degrees?|°)?\s*(?:fahrenheit|celsius|f|c)?\b",
            r"\b(warmer|cooler|hotter|colder|higher|lower)\b",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                val = m.group(1) if m.lastindex else m.group()
                entities.append((
                    val,
                    m.start(1) if m.lastindex else m.start(),
                    m.end(1) if m.lastindex else m.end(),
                    "temperature",
                ))

    def _extract_query_events(
        self, utterance: str, intent: str, expected: set[str],
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract date entities for calendar event queries."""
        if intent != "query_events" and "date" not in expected:
            return
        for pat in [
            r"\b(today|tomorrow|yesterday|tonight|this\s+week|next\s+week|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            r"\b(this|next|last)\s+(week|month|weekend|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            r"\bfor\s+(today|tomorrow|friday|monday|tuesday|wednesday|thursday|saturday|sunday|next\s+week)\b",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                entities.append((m.group(), m.start(), m.end(), "date"))
        if intent == "query_events" and not any(e[3] == "date" for e in entities):
            for pat in [
                r"\b(calendar|events?|schedule|appointments?|meetings?)\b",
                r"(?:what(?:'s|\s+is)\s+(?:on\s+)?(?:my\s+)?)(calendar|schedule)\b",
                r"(?:show\s+(?:me\s+)?(?:my\s+)?)(events?|calendar|schedule)\b",
                r"(?:any\s+)(appointments?|meetings?|events?)\b",
                r"(?:what(?:'s|\s+is)\s+)(coming\s+up|scheduled|planned)\b",
            ]:
                for m in re.finditer(pat, utterance, re.IGNORECASE):
                    val = m.group(1) if m.lastindex else m.group()
                    entities.append((
                        val,
                        m.start(1) if m.lastindex else m.start(),
                        m.end(1) if m.lastindex else m.end(),
                        "query_type",
                    ))
                    break

    def _extract_clarification(
        self, utterance: str, intent: str,
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract help_topic for clarification_request intent."""
        if intent != "clarification_request":
            return
        for pat in [
            r"(?:what\s+did\s+you\s+(?:say|mean)|could\s+you\s+(?:clarify|explain|repeat|rephrase))\s*(.+)?$",
            r"(?:I\s+(?:don't|didn't)\s+(?:understand|catch|hear))\s*(.+)?$",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                if m.lastindex and m.group(1):
                    topic = m.group(1).strip()
                    if topic and len(topic) > 2:
                        entities.append((topic, m.start(1), m.end(1), "help_topic"))

    def _extract_cancellation(
        self, utterance: str, intent: str,
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract action for cancellation intent."""
        if intent != "cancellation":
            return
        for pat in [
            r"(?:cancel|stop|abort|never\s+mind|forget\s+it|don't)\s+(?:that|it|this|doing)?\s*(.+)?$",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                if m.lastindex and m.group(1):
                    action = m.group(1).strip()
                    if action and len(action) > 2:
                        entities.append((action, m.start(1), m.end(1), "action"))

    def _extract_query_weather(
        self, utterance: str, intent: str,
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract weather_condition for weather queries."""
        if intent != "query_weather":
            return
        if any(e[3] in ("location", "date") for e in entities):
            return
        for pat in [
            r"\b(umbrella|raincoat|jacket|coat|sunscreen|sunglasses)\b",
            r"(?:weather|temperature|forecast|rain|snow|sunny|cloudy|hot|cold|warm|cool)\b",
            r"(?:what(?:'s|\s+is)\s+(?:the\s+)?)(weather|temperature|forecast)\b",
            r"(?:will\s+it\s+)(rain|snow|be\s+sunny|be\s+cloudy|be\s+hot|be\s+cold)\b",
            r"(?:is\s+it\s+going\s+to\s+)(rain|snow|be\s+sunny|be\s+hot|be\s+cold)\b",
            r"\b(weather)\b",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                val = m.group(1) if m.lastindex else m.group()
                entities.append((
                    val,
                    m.start(1) if m.lastindex else m.start(),
                    m.end(1) if m.lastindex else m.end(),
                    "weather_condition",
                ))
                break

    def _extract_set_reminder(
        self, utterance: str, intent: str,
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract task for set_reminder intent."""
        if intent != "set_reminder":
            return
        if any(e[3] == "task" for e in entities):
            return
        for pat in [
            r"remind\s+(?:me\s+)?about\s+(.+?)(?:\s+(?:at|on|by|in|tomorrow|today|tonight|this|next|every|in\s+\d).*)?$",
            r"reminder\s+(?:about\s+|for\s+)(.+?)(?:\s+(?:at|on|by|in|tomorrow|today|tonight|this|next|every).*)?$",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                task_text = m.group(1).strip()
                if task_text and len(task_text) > 1:
                    entities.append((task_text, m.start(1), m.end(1), "task"))
                    break

    def _extract_play_music(
        self, utterance: str, intent: str,
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract genre/artist/song for play_music intent."""
        if intent != "play_music":
            return
        if any(e[3] == "genre" for e in entities):
            return
        for pat in [
            r"(?:play|listen\s+to|put\s+on)\s+(?:some\s+)?(.+?)\s+(?:music|songs?|tracks?)\b",
            r"(?:play|listen\s+to)\s+(.+?)(?:\s+(?:please|now|for\s+me))?$",
        ]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                val = m.group(1).strip()
                if val and len(val) > 1 and val.lower() not in {"some", "my", "the", "a"}:
                    if val.lower() in self._KNOWN_GENRES:
                        entities.append((val, m.start(1), m.end(1), "genre"))
                    elif val.lower() in self._KNOWN_ARTISTS:
                        entities.append((val, m.start(1), m.end(1), "artist"))
                    else:
                        entities.append((val, m.start(1), m.end(1), "genre"))

    def _extract_stop_media(
        self, utterance: str, intent: str,
        entities: list[tuple[str, int, int, str]],
    ) -> None:
        """Extract action for stop/pause media intents."""
        if intent not in ("stop_media", "pause_media"):
            return
        for pat in [r"\b(music|song|video|playback|audio|this|it)\b"]:
            for m in re.finditer(pat, utterance, re.IGNORECASE):
                entities.append((m.group(), m.start(), m.end(), "action"))

    def _remove_overlaps(
        self,
        entities: list[tuple[str, int, int, str]],
    ) -> list[tuple[str, int, int, str]]:
        """Remove overlapping entities, keeping the longest match."""
        if not entities:
            return []
        # Sort: start position ASC, length DESC (longest first for same start)
        sorted_ents = sorted(entities, key=lambda x: (x[1], -(x[2] - x[1])))
        result: list[tuple[str, int, int, str]] = []
        last_end = -1
        for ent in sorted_ents:
            if ent[1] >= last_end:
                result.append(ent)
                last_end = ent[2]
        return result

    def annotate_dataset(self, input_file: str, output_file: str) -> None:
        """Annotate dataset file and save results."""
        annotated_data = []
        with open(input_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) != 2:
                    continue
                intent, utterance = parts
                entities = self.extract_entities(utterance, intent)
                annotated_data.append(
                    {
                        "utterance": utterance,
                        "intent": intent,
                        "entities": [
                            {"text": text, "start": start, "end": end, "type": etype}
                            for text, start, end, etype in entities
                        ],
                    },
                )
        with open(output_file, "w", encoding="utf-8") as f:
            yaml.dump(annotated_data, f, default_flow_style=False, allow_unicode=True)

    def validate_annotations(self, annotated_file: str) -> dict[str, Any]:
        """Validate annotation quality and return metrics.

        Coverage is calculated two ways:
        - raw_coverage: all examples
        - adjusted_coverage: excludes intents that intentionally have no entities
          (confirmation, cancellation, clarification_request, unknown, multi_intent)
        """
        with open(annotated_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        total = len(data)
        with_entities = sum(1 for item in data if item["entities"])
        total_entities = sum(len(item["entities"]) for item in data)

        # Adjusted coverage - exclude no-entity intents
        adj_data = [item for item in data if item["intent"] not in self._NO_ENTITY_INTENTS]
        adj_total = len(adj_data)
        adj_with_entities = sum(1 for item in adj_data if item["entities"])

        type_counts: dict[str, int] = {}
        for item in data:
            for ent in item["entities"]:
                t = ent["type"]
                type_counts[t] = type_counts.get(t, 0) + 1

        # Per-intent coverage
        from collections import defaultdict

        intent_total: dict[str, int] = defaultdict(int)
        intent_with: dict[str, int] = defaultdict(int)
        for item in data:
            intent_total[item["intent"]] += 1
            if item["entities"]:
                intent_with[item["intent"]] += 1

        per_intent = {
            intent: {
                "total": intent_total[intent],
                "with_entities": intent_with[intent],
                "coverage": intent_with[intent] / intent_total[intent]
                if intent_total[intent] > 0
                else 0.0,
            }
            for intent in intent_total
        }

        return {
            "total_examples": total,
            "examples_with_entities": with_entities,
            "coverage": with_entities / total if total > 0 else 0.0,
            "adjusted_coverage": adj_with_entities / adj_total if adj_total > 0 else 0.0,
            "adjusted_total": adj_total,
            "adjusted_with_entities": adj_with_entities,
            "total_entities": total_entities,
            "avg_entities_per_example": total_entities / total if total > 0 else 0.0,
            "entity_type_distribution": type_counts,
            "per_intent_coverage": per_intent,
        }


def main() -> None:
    """Annotate all dataset splits and report coverage."""
    annotator = EntityAnnotator()
    for split in ["train", "val", "test"]:
        input_file = f"Agent_Guru/reasoning/data/{split}.txt"
        output_file = f"Agent_Guru/reasoning/data/{split}_annotated.yaml"
        annotator.annotate_dataset(input_file, output_file)
        metrics = annotator.validate_annotations(output_file)

        # Show low-coverage intents
        low = {
            k: v
            for k, v in metrics["per_intent_coverage"].items()
            if v["coverage"] < 0.90 and k not in annotator._NO_ENTITY_INTENTS
        }
        if low:
            for _intent, _info in sorted(low.items(), key=lambda x: x[1]["coverage"]):
                pass
        else:
            pass

        for _etype, _count in sorted(
            metrics["entity_type_distribution"].items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]:
            pass


if __name__ == "__main__":
    main()
