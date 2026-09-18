"""Command parser for voice command recognition and interpretation.

Supports:
- Intent extraction
- Entity recognition (dates, numbers, names)
- Command chaining
- Multi-language patterns
- Custom command registration
- System control commands
"""

import re
from dataclasses import dataclass, field
from typing import Any

from Agent_Guru.speech.models import CommandResult

# Leading politeness/wake filler that precedes a real command in natural
# speech. Stripped before matching so "please turn off the wifi" scores the
# same as "turn off the wifi".
# Connector that MAY separate two chained commands ("open chrome and type hi").
# Deliberately does NOT consume the whitespace that FOLLOWS the connector:
# in "open THEN and type A" the bogus "THEN" boundary would otherwise eat
# the space before the real "and", hiding the genuine boundary from the
# non-overlapping scan.
_CHAIN_SPLIT_RE = re.compile(r"\s+(?:and|then)\b", re.IGNORECASE)

# A genuine new command segment never itself opens with a connector -- the
# connector is the separator. Used to reject false chain boundaries.
_LEADING_CONNECTOR_RE = re.compile(r"^(?:and|then|also|next)\b", re.IGNORECASE)

_POLITE_PREFIX_RE = re.compile(
    # Leading connector: chained utterances are split into parts that still
    # carry their conjunction ("... and type a"), which an anchored match
    # would otherwise reject.
    r"^(?:(?:and|then|also|next)\s+)?"
    r"(?:(?:hey|hi|ok|okay|yo)\s+(?:guru|maya)\b[\s,]*)?"
    r"(?:(?:please|pls)\s+)?"
    r"(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?)?"
    r"(?:(?:i\s+(?:want|need)\s+you\s+to|i'd\s+like\s+you\s+to)\s+)?"
    r"(?:(?:please|pls)\s+)?",
    re.IGNORECASE,
)


@dataclass
class CommandPattern:
    """Command pattern definition."""

    patterns: list[str]
    action_id: str
    description: str
    parameters: list[str] = field(default_factory=list)
    requires_confirmation: bool = False
    language: str = "en"


class CommandParser:
    """Parse and interpret voice commands.

    Features:
    - Intent extraction from transcribed text
    - Entity recognition (dates, numbers, names, percentages)
    - Command chaining support
    - Multi-language pattern matching
    - Custom command registration
    - Confidence scoring
    - Context-aware disambiguation

    Default Commands:
    - System control: open, close, minimize, maximize
    - Text operations: type, send, read
    - File operations: create, delete, move, search
    - Settings: volume, brightness, wifi
    - Mouse/keyboard: click, scroll, press
    """

    def __init__(self) -> None:
        """Initialize command parser with default command registry."""
        # BUG FIX (Round 17): see register_command()'s note on why this is
        # keyed by (action_id, language) rather than action_id alone.
        self._commands: dict[tuple[str, str], CommandPattern] = {}
        self._register_default_commands()

    def register_command(
        self,
        patterns: list[str],
        action_id: str,
        description: str = "",
        parameters: list[str] | None = None,
        requires_confirmation: bool = False,
        language: str = "en",
    ) -> None:
        """Register a new command pattern.

        Args:
            patterns: List of text patterns that trigger this command
            action_id: Action identifier for execution
            description: Human-readable description
            parameters: List of parameter names to extract
            requires_confirmation: Whether command needs user confirmation
            language: Language code for language-specific matching

        BUG FIX (Round 17): this class advertises "Multi-language pattern
        matching" and accepts a `language` parameter specifically so the
        same logical action (e.g. "OPEN_APP", executed by the same
        downstream handler regardless of language) can have a different
        pattern set per language. But commands used to be stored in
        `self._commands` keyed by `action_id` alone -- so registering
        "OPEN_APP" for Hindi after it was already registered for English
        would silently OVERWRITE the English patterns entirely rather than
        adding a second, coexisting entry. The bug was latent (nothing in
        this codebase yet registers the same action_id under two
        languages), but it would have silently broken the very feature
        the docstring promises the moment anyone did. Fixed by keying
        storage on (action_id, language), so the same action_id can have
        one pattern set per language, all coexisting.

        """
        command = CommandPattern(
            patterns=patterns,
            action_id=action_id,
            description=description,
            parameters=parameters or [],
            requires_confirmation=requires_confirmation,
            language=language,
        )
        self._commands[(action_id, language)] = command

    def interpret(
        self,
        text: str,
        language: str = "en",
        context: dict[str, Any] | None = None,
        *,
        _allow_chain: bool = True,
    ) -> CommandResult:
        """Interpret text as a command.

        Args:
            text: Transcribed text to interpret
            language: Language code for language-specific matching
            context: Optional conversation context for disambiguation

        Returns:
            CommandResult with action_id, parameters, and confidence

        """
        original_text = text.strip()
        text = original_text.lower()

        if not text:
            return CommandResult(
                is_command=False,
                action_id=None,
                parameters={},
                confidence=0.0,
                raw_text=text,
            )

        # Check for command chaining. BUG FIX: the mere PRESENCE of " and "/
        # " then " used to trigger a split, truncating ordinary sentences.
        # Now a chain requires a connector that genuinely starts a second
        # command (see _chain_parts). _allow_chain stops sub-commands, which
        # may still contain a connector inside an argument, from recursing.
        if _allow_chain and len(self._chain_parts(original_text, language)) > 1:
            # Pass original_text (not the lowercased `text`) through so
            # chained sub-commands can still benefit from the name-
            # extraction casing fix above -- see _parse_chained_command().
            return self._parse_chained_command(original_text, language, context)

        # Try to match against registered commands
        best_match = None
        best_confidence = 0.0
        best_parameters = {}

        for (action_id, cmd_language), command in self._commands.items():
            if cmd_language != language:
                continue

            for pattern in command.patterns:
                confidence, parameters = self._match_pattern(text, pattern, command.parameters)

                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = action_id
                    best_parameters = parameters

        # If no match found, try entity extraction for generic commands
        if best_match is None:
            # BUG FIX (Round 17): this used to pass the already-lowercased
            # `text` to _extract_entities(), whose name-extraction regex
            # (`r"\b[A-Z][a-z]+..."`) matches only CAPITALIZED words. Since
            # `text` is lowercased above (line "text = original_text.lower()")
            # BEFORE this call, the names entity could never match anything,
            # ever -- a silently, permanently dead piece of functionality.
            # Fixed by extracting entities from `original_text`, which
            # preserves the original casing needed for name detection while
            # every other entity type here (numbers/percentages/dates) is
            # unaffected by case.
            # BUG FIX: this used to return is_command=True/"GENERIC_COMMAND"
            # whenever ANY entity was found. _extract_entities() matches bare
            # numbers, weekdays, "today/tomorrow/yesterday" and capitalised
            # names, so plain conversation became an executable command:
            #   "how are you doing today"      -> GENERIC_COMMAND (0.50)
            #   "I am meeting Sarah tomorrow"  -> GENERIC_COMMAND
            # An entity on its own carries no instruction. The entities are
            # still returned for callers that want them (context, memory),
            # but the utterance is no longer flagged for execution.
            entities = self._extract_entities(original_text)
            return CommandResult(
                is_command=False,
                action_id=None,
                parameters=entities,
                confidence=0.0,
                raw_text=text,
            )

        return CommandResult(
            is_command=True,
            action_id=best_match,
            parameters=best_parameters,
            confidence=best_confidence,
            raw_text=text,
        )

    def get_registered_commands(self) -> list[dict[str, Any]]:
        """Get list of all registered commands.

        Returns:
            List of command definitions

        """
        return [
            {
                "action_id": action_id,
                "patterns": cmd.patterns,
                "description": cmd.description,
                "parameters": cmd.parameters,
                "requires_confirmation": cmd.requires_confirmation,
                "language": cmd.language,
            }
            for (action_id, _language), cmd in self._commands.items()
        ]

    def _register_default_commands(self) -> None:
        """Register default system control commands."""
        # System control commands
        self.register_command(
            patterns=[
                r"open (?P<app_name>[\w\s]+)",
                r"launch (?P<app_name>[\w\s]+)",
                r"start (?P<app_name>[\w\s]+)",
            ],
            action_id="OPEN_APP",
            description="Open an application",
            parameters=["app_name"],
        )

        self.register_command(
            patterns=[
                r"close (?P<app_name>[\w\s]+)",
                r"quit (?P<app_name>[\w\s]+)",
                r"exit (?P<app_name>[\w\s]+)",
            ],
            action_id="CLOSE_APP",
            description="Close an application",
            parameters=["app_name"],
        )

        self.register_command(
            patterns=[r"minimize (?P<app_name>[\w\s]+)?", r"minimize window"],
            action_id="MINIMIZE_WINDOW",
            description="Minimize window",
            parameters=["app_name"],
        )

        self.register_command(
            patterns=[r"maximize (?P<app_name>[\w\s]+)?", r"maximize window"],
            action_id="MAXIMIZE_WINDOW",
            description="Maximize window",
            parameters=["app_name"],
        )

        # Text operations
        self.register_command(
            # NOTE: "write ..." and "enter ..." are intentionally kept here --
            # test_type_text_command documents them as TYPE_TEXT. They remain
            # ambiguous with composition ("write a poem about the sea" still
            # routes to typing rather than being composed) and with ordinary
            # speech ("enter the room"). Anchoring now confines that to
            # utterances that OPEN with the verb, which removes the
            # mid-sentence misfires; narrowing the verbs themselves is a
            # product decision, deliberately left to the owner.
            patterns=[
                r"type out (?P<text>.+)",
                r"type (?P<text>.+)",
                r"write (?P<text>.+)",
                r"enter (?P<text>.+)",
            ],
            action_id="TYPE_TEXT",
            description="Type text",
            parameters=["text"],
        )

        self.register_command(
            patterns=[
                r"send message (?P<message>.+) to (?P<recipient>[\w\s]+)",
                r"message (?P<recipient>[\w\s]+) (?P<message>.+)",
            ],
            action_id="SEND_MESSAGE",
            description="Send a message",
            parameters=["message", "recipient"],
        )

        self.register_command(
            patterns=[
                r"read (?P<item>email|message|notification)s?",
                r"check (?P<item>email|message|notification)s?",
            ],
            action_id="READ_ITEM",
            description="Read emails/messages",
            parameters=["item"],
        )

        # File operations
        self.register_command(
            patterns=[r"create file (?P<filename>[\w\s\.]+)", r"new file (?P<filename>[\w\s\.]+)"],
            action_id="CREATE_FILE",
            description="Create a new file",
            parameters=["filename"],
        )

        self.register_command(
            patterns=[
                r"delete file (?P<filename>[\w\s\.]+)",
                r"remove file (?P<filename>[\w\s\.]+)",
            ],
            action_id="DELETE_FILE",
            description="Delete a file",
            parameters=["filename"],
            requires_confirmation=True,
        )

        self.register_command(
            patterns=[
                r"move (?P<source>[\w\s\.]+) to (?P<destination>[\w\s\.]+)",
                r"rename (?P<source>[\w\s\.]+) to (?P<destination>[\w\s\.]+)",
            ],
            action_id="MOVE_FILE",
            description="Move or rename a file",
            parameters=["source", "destination"],
        )

        self.register_command(
            patterns=[
                r"search for (?P<query>.+) in (?P<location>[\w\s]+)",
                r"find (?P<query>.+) in (?P<location>[\w\s]+)",
                r"search for (?P<query>.+)",
                r"find (?P<query>.+)",
            ],
            action_id="SEARCH_FILES",
            description="Search for files",
            parameters=["query", "location"],
        )

        # Settings commands
        self.register_command(
            patterns=[
                r"set volume to (?P<level>\d+) percent",
                r"volume (?P<level>\d+) percent",
                # BUG FIX: "set volume to 50" matched none of these ("to"
                # without "percent"), so it fell through to the generic
                # entity blob and never actually set the volume.
                r"set volume to (?P<level>\d+)",
                r"set volume (?P<level>\d+)",
            ],
            action_id="SET_VOLUME",
            description="Set system volume",
            parameters=["level"],
        )

        self.register_command(
            patterns=[r"increase volume", r"volume up", r"louder"],
            action_id="VOLUME_UP",
            description="Increase volume",
        )

        self.register_command(
            patterns=[r"decrease volume", r"volume down", r"quieter"],
            action_id="VOLUME_DOWN",
            description="Decrease volume",
        )

        self.register_command(
            patterns=[r"mute", r"silence"],
            action_id="MUTE",
            description="Mute audio",
        )

        self.register_command(
            patterns=[
                r"set brightness to (?P<level>\d+) percent",
                r"brightness (?P<level>\d+) percent",
                # Same as volume: people omit "percent".
                r"set brightness to (?P<level>\d+)",
                r"set brightness (?P<level>\d+)",
            ],
            action_id="SET_BRIGHTNESS",
            description="Set screen brightness",
            parameters=["level"],
        )

        self.register_command(
            patterns=[
                # People say "the wifi"/"wi-fi"; the article used to break the
                # match entirely, so "turn off the wifi" was not a command.
                r"turn (?P<state>on|off) (?:the )?wi-?fi",
                r"turn (?:the )?wi-?fi (?P<state>on|off)",
                r"(?P<state>enable|disable) (?:the )?wi-?fi",
                r"wi-?fi (?P<state>on|off)",
            ],
            action_id="TOGGLE_WIFI",
            description="Toggle WiFi",
            parameters=["state"],
        )

        self.register_command(
            patterns=[
                r"turn (?P<state>on|off) (?:the )?bluetooth",
                r"turn (?:the )?bluetooth (?P<state>on|off)",
                r"(?P<state>enable|disable) (?:the )?bluetooth",
                r"bluetooth (?P<state>on|off)",
            ],
            action_id="TOGGLE_BLUETOOTH",
            description="Toggle Bluetooth",
            parameters=["state"],
        )

        # Mouse/keyboard commands
        self.register_command(
            patterns=[r"click", r"left click"],
            action_id="CLICK",
            description="Perform mouse click",
        )

        self.register_command(
            patterns=[r"right click"],
            action_id="RIGHT_CLICK",
            description="Perform right click",
        )

        self.register_command(
            patterns=[r"double click"],
            action_id="DOUBLE_CLICK",
            description="Perform double click",
        )

        self.register_command(
            patterns=[
                r"scroll (?P<direction>up|down)",
                r"scroll (?P<direction>up|down) (?P<amount>\d+)",
            ],
            action_id="SCROLL",
            description="Scroll page",
            parameters=["direction", "amount"],
        )

        self.register_command(
            patterns=[r"press (?P<key>[\w\s]+)", r"hit (?P<key>[\w\s]+)"],
            action_id="PRESS_KEY",
            description="Press keyboard key",
            parameters=["key"],
        )

    def _match_pattern(
        self,
        text: str,
        pattern: str,
        param_names: list[str],
    ) -> tuple[float, dict[str, Any]]:
        """Match text against a pattern and extract parameters.

        Args:
            text: Text to match
            pattern: Regex pattern
            param_names: Parameter names to extract

        Returns:
            Tuple of (confidence, parameters)

        """
        try:
            # BUG FIX: this used re.search(), matching a command pattern
            # ANYWHERE inside the utterance. Because patterns like
            # r"start (?P<app_name>[\w\s]+)" and r"open (...)" are single
            # common verbs, ordinary conversation was executed as desktop
            # automation. Measured against the real parser:
            #   "I want to start eating healthier"        -> OPEN_APP  0.69
            #   "let me open up about something"          -> OPEN_APP  0.77
            #   "I need to close this chapter of my life" -> CLOSE_APP 0.74
            #   "can you write a poem about the sea"      -> TYPE_TEXT 0.76
            # Someone confiding in their companion must not launch an app.
            #
            # A command is an instruction the utterance OPENS with, so the
            # match is now anchored, after stripping leading politeness/wake
            # filler so natural phrasing still works.
            stripped = _POLITE_PREFIX_RE.sub("", text, count=1).strip()
            if not stripped:
                return 0.0, {}

            match = re.match(pattern, stripped, re.IGNORECASE)
            if not match:
                return 0.0, {}

            # Extract parameters
            parameters: dict[str, Any] = {}
            # A command declares ONE parameter list but several patterns, and
            # not every pattern captures every parameter (e.g. SET_VOLUME's
            # "volume up" captures no level, while "set volume to 40" does).
            # match.group(name) raises IndexError for the absent ones, so this
            # loop used to drive normal control flow through an exception.
            # groupdict() answers both cases -- group absent from this pattern,
            # and group present but unmatched -- as None, which is exactly the
            # distinction the code wants, with no exception and one dict build
            # instead of one lookup per name.
            groups = match.groupdict()
            for param_name in param_names:
                value = groups.get(param_name)
                if value:
                    # Try to parse as number
                    try:
                        parameters[param_name] = int(value)
                    except ValueError:
                        parameters[param_name] = str(value).strip()

            # Calculate confidence based on match quality
            matched_length = len(match.group(0))
            text_length = len(stripped)
            confidence = matched_length / text_length

            # Boost confidence if exact match
            if matched_length == text_length:
                confidence = 1.0

            # Ensure confidence is in [0, 1]
            confidence = max(0.0, min(1.0, confidence))

            return confidence, parameters

        except re.error:
            return 0.0, {}

    def _extract_entities(self, text: str) -> dict[str, Any]:
        """Extract entities from text (dates, numbers, names).

        Args:
            text: Text to extract entities from

        Returns:
            Dictionary of extracted entities

        """
        entities = {}

        # Extract numbers
        numbers = re.findall(r"\b\d+\b", text)
        if numbers:
            entities["numbers"] = [int(n) for n in numbers]

        # Extract percentages
        percentages = re.findall(r"(\d+)\s*percent", text, re.IGNORECASE)
        if percentages:
            entities["percentages"] = [int(p) for p in percentages]

        # Extract dates (simple patterns)
        date_patterns = [
            r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",  # MM/DD/YYYY
            r"\b\d{4}-\d{2}-\d{2}\b",  # YYYY-MM-DD
            r"\b(today|tomorrow|yesterday)\b",
            r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        ]

        dates = []
        for pattern in date_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            dates.extend(matches)

        if dates:
            entities["dates"] = dates

        # Extract potential names (capitalized words)
        #
        # BUG FIX: transcribed speech is conventionally sentence-cased --
        # Whisper (and STT engines generally) capitalize the first word of
        # every utterance regardless of what part of speech it actually
        # is. A naive "any capitalized word" regex therefore misidentifies
        # the first word of nearly every utterance as a person's name:
        # "Remind me to call John" produced names=["Remind", "John"], with
        # "Remind" a false positive purely from sentence position, not
        # from being an actual proper noun. Since GENERIC_COMMAND's
        # extracted entities are handed to whatever routes voice commands
        # (e.g. Agent_Guru.speech.engine._process_command ->
        # agent_orchestration.route_command), a consumer trying to figure
        # out "who does this command refer to" from parameters["names"]
        # would have gotten that answer corrupted on nearly every
        # utterance.
        #
        # Fix: a capitalized word (or run of consecutive capitalized
        # words) that starts at position 0 of the text has its *leading*
        # word dropped, unless that leading word is the entire utterance
        # (e.g. the user just said "John" -- kept as-is) -- whatever
        # capitalized word(s) remain after dropping it, if any, are kept
        # as the name candidate. This handles both shapes the original
        # bug produced:
        #   - "Remind me to call John" -> the sentence-initial match is
        #     just "Remind" on its own; dropping its only word leaves
        #     nothing, so it's excluded entirely. "John" (not
        #     sentence-initial) is kept. Result: ["John"].
        #   - "Call Sarah now" -> greedy matching merges the adjacent
        #     capitalized words into one run, "Call Sarah"; dropping the
        #     leading word "Call" leaves "Sarah", which is kept. Result:
        #     ["Sarah"].
        # This is a heuristic trade-off, not a full NER solution: an
        # utterance that genuinely *opens* with a multi-word proper name
        # (e.g. "John Smith called") will have its first word dropped
        # the same way ("Smith" only, not "John Smith"), since nothing
        # short of real language understanding can tell "capitalized verb
        # + capitalized name" apart from "capitalized name + capitalized
        # name" using position and casing alone. That trade-off is
        # deliberately accepted: this is a voice *command* parser, where
        # an utterance opening with "<verb> <name>" (the case this fixes)
        # is the overwhelmingly common shape, not "<name> <name> <verb>"
        # (the rare case this doesn't perfectly handle).
        names = []
        for match in re.finditer(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text):
            candidate = match.group(0)
            if match.start() == 0 and candidate != text.strip():
                remainder = candidate.split(" ", 1)
                candidate = remainder[1] if len(remainder) > 1 else None
                if not candidate:
                    continue
            names.append(candidate)
        if names:
            entities["names"] = names

        return entities

    def _starts_command(self, text: str, language: str) -> bool:
        """True if `text` BEGINS a recognised command.

        Used to decide whether a connector is really a chain boundary or
        just a word inside an argument.
        """
        candidate = text.strip()
        if not candidate or _LEADING_CONNECTOR_RE.match(candidate):
            return False
        candidate = candidate.lower()
        for (_action_id, cmd_language), command in self._commands.items():
            if cmd_language != language:
                continue
            for pattern in command.patterns:
                confidence, _params = self._match_pattern(
                    candidate, pattern, command.parameters,
                )
                if confidence > 0.0:
                    return True
        return False

    def _chain_parts(self, text: str, language: str) -> list[str]:
        """Split only at connectors that actually start a new command.

        BUG FIX: every utterance containing " and "/" then " used to be
        split unconditionally, so a connector inside an argument silently
        truncated what the user said:
          "search for cats and dogs in downloads" -> searched only "cats"
          "type I love coffee and tea"            -> typed "i love coffee"
          "send message see you then to john"     -> failed entirely
        A connector is now a boundary only when what follows begins a
        recognised command, so "open chrome and type hi" still chains.
        """
        parts: list[str] = []
        last = 0
        for match in _CHAIN_SPLIT_RE.finditer(text):
            if self._starts_command(text[match.end():], language):
                parts.append(text[last:match.start()])
                last = match.end()
        parts.append(text[last:])
        return [p for p in (part.strip() for part in parts) if p]

    def _parse_chained_command(
        self,
        text: str,
        language: str,
        context: dict[str, Any] | None,
    ) -> CommandResult:
        """Parse chained commands (e.g., "open browser and search for weather").

        Args:
            text: Text containing chained commands
            language: Language code
            context: Conversation context

        Returns:
            CommandResult with chained commands

        BUG FIX (Round 17): this used to split on the literal, lowercase
        substrings " and "/" then " via str.split(), which meant `text`
        had to already be lowercased for the split to reliably match (the
        only caller, interpret(), does lowercase before checking whether
        to chain at all). That, in turn, meant every sub-command's
        original casing was already lost before reaching here, so the
        name-extraction fix in interpret() couldn't help chained
        sub-commands recover it. Fixed by splitting with a case-insensitive
        regex instead, so callers can pass ORIGINAL-case text through and
        each sub-command keeps its original casing (interpret() now does
        exactly this).

        """
        # Split by "and" or "then" (case-insensitive; preserves casing of
        # the parts themselves, unlike a lowercase-only literal split).
        parts = self._chain_parts(text, language)

        # Parse each part
        sub_commands = []
        total_confidence = 0.0

        for part in parts:
            part = part.strip()
            if not part:
                continue

            result = self.interpret(part, language, context, _allow_chain=False)
            if result.is_command:
                sub_commands.append(
                    {
                        "action_id": result.action_id,
                        "parameters": result.parameters,
                        "confidence": result.confidence,
                    },
                )
                total_confidence += result.confidence

        if not sub_commands:
            return CommandResult(
                is_command=False,
                action_id=None,
                parameters={},
                confidence=0.0,
                raw_text=text,
            )

        # Average confidence
        avg_confidence = total_confidence / len(sub_commands)

        return CommandResult(
            is_command=True,
            action_id="CHAINED_COMMAND",
            parameters={"sub_commands": sub_commands},
            confidence=avg_confidence,
            raw_text=text,
        )
