"""
Command parser for voice command recognition and interpretation.

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
from typing import Dict, List, Optional, Any, Tuple

from ..models import CommandResult


@dataclass
class CommandPattern:
    """Command pattern definition."""
    patterns: List[str]
    action_id: str
    description: str
    parameters: List[str] = field(default_factory=list)
    requires_confirmation: bool = False
    language: str = "en"


class CommandParser:
    """
    Parse and interpret voice commands.
    
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
    
    def __init__(self):
        """Initialize command parser with default command registry."""
        self._commands: Dict[str, CommandPattern] = {}
        self._register_default_commands()
    
    def register_command(
        self,
        patterns: List[str],
        action_id: str,
        description: str = "",
        parameters: Optional[List[str]] = None,
        requires_confirmation: bool = False,
        language: str = "en"
    ) -> None:
        """
        Register a new command pattern.
        
        Args:
            patterns: List of text patterns that trigger this command
            action_id: Action identifier for execution
            description: Human-readable description
            parameters: List of parameter names to extract
            requires_confirmation: Whether command needs user confirmation
            language: Language code for language-specific matching
        """
        command = CommandPattern(
            patterns=patterns,
            action_id=action_id,
            description=description,
            parameters=parameters or [],
            requires_confirmation=requires_confirmation,
            language=language
        )
        self._commands[action_id] = command
    
    def interpret(
        self,
        text: str,
        language: str = "en",
        context: Optional[Dict[str, Any]] = None
    ) -> CommandResult:
        """
        Interpret text as a command.
        
        Args:
            text: Transcribed text to interpret
            language: Language code for language-specific matching
            context: Optional conversation context for disambiguation
            
        Returns:
            CommandResult with action_id, parameters, and confidence
        """
        text = text.strip().lower()
        
        if not text:
            return CommandResult(
                is_command=False,
                action_id=None,
                parameters={},
                confidence=0.0,
                raw_text=text
            )
        
        # Check for command chaining
        if " and " in text or " then " in text:
            return self._parse_chained_command(text, language, context)
        
        # Try to match against registered commands
        best_match = None
        best_confidence = 0.0
        best_parameters = {}
        
        for action_id, command in self._commands.items():
            if command.language != language:
                continue
            
            for pattern in command.patterns:
                confidence, parameters = self._match_pattern(text, pattern, command.parameters)
                
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = action_id
                    best_parameters = parameters
        
        # If no match found, try entity extraction for generic commands
        if best_match is None:
            entities = self._extract_entities(text)
            if entities:
                return CommandResult(
                    is_command=True,
                    action_id="GENERIC_COMMAND",
                    parameters=entities,
                    confidence=0.5,
                    raw_text=text
                )
            
            return CommandResult(
                is_command=False,
                action_id=None,
                parameters={},
                confidence=0.0,
                raw_text=text
            )
        
        return CommandResult(
            is_command=True,
            action_id=best_match,
            parameters=best_parameters,
            confidence=best_confidence,
            raw_text=text
        )
    
    def get_registered_commands(self) -> List[Dict[str, Any]]:
        """
        Get list of all registered commands.
        
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
                "language": cmd.language
            }
            for action_id, cmd in self._commands.items()
        ]
    
    def _register_default_commands(self) -> None:
        """Register default system control commands."""
        
        # System control commands
        self.register_command(
            patterns=[
                r"open (?P<app_name>[\w\s]+)",
                r"launch (?P<app_name>[\w\s]+)",
                r"start (?P<app_name>[\w\s]+)"
            ],
            action_id="OPEN_APP",
            description="Open an application",
            parameters=["app_name"]
        )
        
        self.register_command(
            patterns=[
                r"close (?P<app_name>[\w\s]+)",
                r"quit (?P<app_name>[\w\s]+)",
                r"exit (?P<app_name>[\w\s]+)"
            ],
            action_id="CLOSE_APP",
            description="Close an application",
            parameters=["app_name"]
        )
        
        self.register_command(
            patterns=[
                r"minimize (?P<app_name>[\w\s]+)?",
                r"minimize window"
            ],
            action_id="MINIMIZE_WINDOW",
            description="Minimize window",
            parameters=["app_name"]
        )
        
        self.register_command(
            patterns=[
                r"maximize (?P<app_name>[\w\s]+)?",
                r"maximize window"
            ],
            action_id="MAXIMIZE_WINDOW",
            description="Maximize window",
            parameters=["app_name"]
        )
        
        # Text operations
        self.register_command(
            patterns=[
                r"type (?P<text>.+)",
                r"write (?P<text>.+)",
                r"enter (?P<text>.+)"
            ],
            action_id="TYPE_TEXT",
            description="Type text",
            parameters=["text"]
        )
        
        self.register_command(
            patterns=[
                r"send message (?P<message>.+) to (?P<recipient>[\w\s]+)",
                r"message (?P<recipient>[\w\s]+) (?P<message>.+)"
            ],
            action_id="SEND_MESSAGE",
            description="Send a message",
            parameters=["message", "recipient"]
        )
        
        self.register_command(
            patterns=[
                r"read (?P<item>email|message|notification)s?",
                r"check (?P<item>email|message|notification)s?"
            ],
            action_id="READ_ITEM",
            description="Read emails/messages",
            parameters=["item"]
        )
        
        # File operations
        self.register_command(
            patterns=[
                r"create file (?P<filename>[\w\s\.]+)",
                r"new file (?P<filename>[\w\s\.]+)"
            ],
            action_id="CREATE_FILE",
            description="Create a new file",
            parameters=["filename"]
        )
        
        self.register_command(
            patterns=[
                r"delete file (?P<filename>[\w\s\.]+)",
                r"remove file (?P<filename>[\w\s\.]+)"
            ],
            action_id="DELETE_FILE",
            description="Delete a file",
            parameters=["filename"],
            requires_confirmation=True
        )
        
        self.register_command(
            patterns=[
                r"move (?P<source>[\w\s\.]+) to (?P<destination>[\w\s\.]+)",
                r"rename (?P<source>[\w\s\.]+) to (?P<destination>[\w\s\.]+)"
            ],
            action_id="MOVE_FILE",
            description="Move or rename a file",
            parameters=["source", "destination"]
        )
        
        self.register_command(
            patterns=[
                r"search for (?P<query>.+) in (?P<location>[\w\s]+)",
                r"find (?P<query>.+) in (?P<location>[\w\s]+)",
                r"search for (?P<query>.+)",
                r"find (?P<query>.+)"
            ],
            action_id="SEARCH_FILES",
            description="Search for files",
            parameters=["query", "location"]
        )
        
        # Settings commands
        self.register_command(
            patterns=[
                r"set volume to (?P<level>\d+) percent",
                r"volume (?P<level>\d+) percent",
                r"set volume (?P<level>\d+)"
            ],
            action_id="SET_VOLUME",
            description="Set system volume",
            parameters=["level"]
        )
        
        self.register_command(
            patterns=[
                r"increase volume",
                r"volume up",
                r"louder"
            ],
            action_id="VOLUME_UP",
            description="Increase volume"
        )
        
        self.register_command(
            patterns=[
                r"decrease volume",
                r"volume down",
                r"quieter"
            ],
            action_id="VOLUME_DOWN",
            description="Decrease volume"
        )
        
        self.register_command(
            patterns=[
                r"mute",
                r"silence"
            ],
            action_id="MUTE",
            description="Mute audio"
        )
        
        self.register_command(
            patterns=[
                r"set brightness to (?P<level>\d+) percent",
                r"brightness (?P<level>\d+) percent"
            ],
            action_id="SET_BRIGHTNESS",
            description="Set screen brightness",
            parameters=["level"]
        )
        
        self.register_command(
            patterns=[
                r"turn (?P<state>on|off) wifi",
                r"(?P<state>enable|disable) wifi",
                r"wifi (?P<state>on|off)"
            ],
            action_id="TOGGLE_WIFI",
            description="Toggle WiFi",
            parameters=["state"]
        )
        
        self.register_command(
            patterns=[
                r"turn (?P<state>on|off) bluetooth",
                r"(?P<state>enable|disable) bluetooth",
                r"bluetooth (?P<state>on|off)"
            ],
            action_id="TOGGLE_BLUETOOTH",
            description="Toggle Bluetooth",
            parameters=["state"]
        )
        
        # Mouse/keyboard commands
        self.register_command(
            patterns=[
                r"click",
                r"left click"
            ],
            action_id="CLICK",
            description="Perform mouse click"
        )
        
        self.register_command(
            patterns=[
                r"right click"
            ],
            action_id="RIGHT_CLICK",
            description="Perform right click"
        )
        
        self.register_command(
            patterns=[
                r"double click"
            ],
            action_id="DOUBLE_CLICK",
            description="Perform double click"
        )
        
        self.register_command(
            patterns=[
                r"scroll (?P<direction>up|down)",
                r"scroll (?P<direction>up|down) (?P<amount>\d+)"
            ],
            action_id="SCROLL",
            description="Scroll page",
            parameters=["direction", "amount"]
        )
        
        self.register_command(
            patterns=[
                r"press (?P<key>[\w\s]+)",
                r"hit (?P<key>[\w\s]+)"
            ],
            action_id="PRESS_KEY",
            description="Press keyboard key",
            parameters=["key"]
        )
    
    def _match_pattern(
        self,
        text: str,
        pattern: str,
        param_names: List[str]
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Match text against a pattern and extract parameters.
        
        Args:
            text: Text to match
            pattern: Regex pattern
            param_names: Parameter names to extract
            
        Returns:
            Tuple of (confidence, parameters)
        """
        try:
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                return 0.0, {}
            
            # Extract parameters
            parameters: Dict[str, Any] = {}
            for param_name in param_names:
                try:
                    value = match.group(param_name)
                    if value:
                        # Try to parse as number
                        try:
                            parameters[param_name] = int(value)
                        except ValueError:
                            parameters[param_name] = str(value).strip()
                except IndexError:
                    pass
            
            # Calculate confidence based on match quality
            matched_length = len(match.group(0))
            text_length = len(text)
            confidence = matched_length / text_length
            
            # Boost confidence if exact match
            if matched_length == text_length:
                confidence = 1.0
            
            # Ensure confidence is in [0, 1]
            confidence = max(0.0, min(1.0, confidence))
            
            return confidence, parameters
            
        except re.error:
            return 0.0, {}
    
    def _extract_entities(self, text: str) -> Dict[str, Any]:
        """
        Extract entities from text (dates, numbers, names).
        
        Args:
            text: Text to extract entities from
            
        Returns:
            Dictionary of extracted entities
        """
        entities = {}
        
        # Extract numbers
        numbers = re.findall(r'\b\d+\b', text)
        if numbers:
            entities["numbers"] = [int(n) for n in numbers]
        
        # Extract percentages
        percentages = re.findall(r'(\d+)\s*percent', text, re.IGNORECASE)
        if percentages:
            entities["percentages"] = [int(p) for p in percentages]
        
        # Extract dates (simple patterns)
        date_patterns = [
            r'\b\d{1,2}/\d{1,2}/\d{2,4}\b',  # MM/DD/YYYY
            r'\b\d{4}-\d{2}-\d{2}\b',  # YYYY-MM-DD
            r'\b(today|tomorrow|yesterday)\b',
            r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b'
        ]
        
        dates = []
        for pattern in date_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            dates.extend(matches)
        
        if dates:
            entities["dates"] = dates
        
        # Extract potential names (capitalized words)
        names = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        if names:
            entities["names"] = names
        
        return entities
    
    def _parse_chained_command(
        self,
        text: str,
        language: str,
        context: Optional[Dict[str, Any]]
    ) -> CommandResult:
        """
        Parse chained commands (e.g., "open browser and search for weather").
        
        Args:
            text: Text containing chained commands
            language: Language code
            context: Conversation context
            
        Returns:
            CommandResult with chained commands
        """
        # Split by "and" or "then"
        separators = [" and ", " then "]
        parts = [text]
        
        for sep in separators:
            new_parts = []
            for part in parts:
                new_parts.extend(part.split(sep))
            parts = new_parts
        
        # Parse each part
        sub_commands = []
        total_confidence = 0.0
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            result = self.interpret(part, language, context)
            if result.is_command:
                sub_commands.append({
                    "action_id": result.action_id,
                    "parameters": result.parameters,
                    "confidence": result.confidence
                })
                total_confidence += result.confidence
        
        if not sub_commands:
            return CommandResult(
                is_command=False,
                action_id=None,
                parameters={},
                confidence=0.0,
                raw_text=text
            )
        
        # Average confidence
        avg_confidence = total_confidence / len(sub_commands)
        
        return CommandResult(
            is_command=True,
            action_id="CHAINED_COMMAND",
            parameters={"sub_commands": sub_commands},
            confidence=avg_confidence,
            raw_text=text
        )
