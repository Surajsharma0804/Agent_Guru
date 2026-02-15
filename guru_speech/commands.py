"""
Command interpretation module for mapping transcriptions to agent actions.

This module contains:
- CommandInterpreter class for pattern matching and command detection
- Default command registry with multi-language support
"""

import re
from typing import List, Dict, Any, Optional
from difflib import SequenceMatcher

from .models import CommandResult, CommandPattern
from .exceptions import CommandInterpretationError


class CommandInterpreter:
    """
    Interprets transcribed text as commands for the Guru Agent.
    Uses pattern matching and fuzzy matching for command detection.
    """
    
    def __init__(self):
        """Initialize command interpreter with default command registry."""
        self._commands: List[CommandPattern] = []
        self._register_default_commands()
    
    def register_command(
        self,
        patterns: List[str],
        action_id: str,
        description: str = "",
        languages: Optional[List[str]] = None,
        parameter_extractors: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Register a new command pattern.
        
        Args:
            patterns: List of text patterns that trigger this command
            action_id: Action identifier for Guru Agent
            description: Human-readable description
            languages: Supported languages (defaults to ["en"])
            parameter_extractors: Functions to extract parameters from matched text
        """
        try:
            if not patterns:
                raise ValueError("patterns list cannot be empty")
            if not action_id:
                raise ValueError("action_id cannot be empty")
            
            command = CommandPattern(
                patterns=patterns,
                action_id=action_id,
                description=description,
                languages=languages or ["en"],
                parameter_extractors=parameter_extractors or {}
            )
            self._commands.append(command)
        except Exception as e:
            raise CommandInterpretationError(
                f"Failed to register command: {action_id}",
                original_error=e
            )
    
    def interpret(
        self,
        text: str,
        language: str = "en"
    ) -> CommandResult:
        """
        Interpret text as a command.
        
        Args:
            text: Transcribed text
            language: Language code for language-specific matching
            
        Returns:
            CommandResult with action_id and parameters
        """
        try:
            text_lower = text.lower().strip()
            
            # Try exact and fuzzy matching for each registered command
            for command in self._commands:
                # Check if language is supported
                if language not in command.languages:
                    continue
                
                # Try each pattern for this command
                for pattern in command.patterns:
                    pattern_lower = pattern.lower().strip()
                    
                    # Check for exact match
                    if self._matches_pattern(text_lower, pattern_lower):
                        parameters = self._extract_parameters(
                            text,
                            pattern,
                            command.parameter_extractors
                        )
                        
                        return CommandResult(
                            action_id=command.action_id,
                            parameters=parameters,
                            raw_text=text,
                            confidence=1.0,
                            language=language,
                            is_command=True
                        )
                    
                    # Try fuzzy matching (similarity threshold: 0.8)
                    similarity = self._calculate_similarity(text_lower, pattern_lower)
                    if similarity >= 0.8:
                        parameters = self._extract_parameters(
                            text,
                            pattern,
                            command.parameter_extractors
                        )
                        
                        return CommandResult(
                            action_id=command.action_id,
                            parameters=parameters,
                            raw_text=text,
                            confidence=similarity,
                            language=language,
                            is_command=True
                        )
            
            # No command matched - return raw text
            return CommandResult(
                action_id=None,
                parameters={},
                raw_text=text,
                confidence=0.0,
                language=language,
                is_command=False
            )
            
        except Exception as e:
            if isinstance(e, CommandInterpretationError):
                raise
            raise CommandInterpretationError(
                f"Failed to interpret text: {text}",
                original_error=e
            )
    
    def get_registered_commands(self) -> List[Dict[str, Any]]:
        """
        Get list of all registered commands.
        
        Returns:
            List of command definitions as dictionaries
        """
        return [
            {
                "action_id": cmd.action_id,
                "patterns": cmd.patterns,
                "description": cmd.description,
                "languages": cmd.languages,
                "has_parameters": bool(cmd.parameter_extractors)
            }
            for cmd in self._commands
        ]
    
    def _matches_pattern(self, text: str, pattern: str) -> bool:
        """
        Check if text matches pattern (supports wildcards).
        
        Args:
            text: Input text (lowercase)
            pattern: Pattern to match (lowercase, may contain *)
            
        Returns:
            True if text matches pattern
        """
        # Convert pattern with * to regex
        if "*" in pattern:
            regex_pattern = pattern.replace("*", ".*")
            return bool(re.match(f"^{regex_pattern}$", text))
        else:
            return text == pattern
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two strings using SequenceMatcher.
        
        Args:
            text1: First string
            text2: Second string
            
        Returns:
            Similarity score (0.0 to 1.0)
        """
        return SequenceMatcher(None, text1, text2).ratio()
    
    def _extract_parameters(
        self,
        text: str,
        pattern: str,
        extractors: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract parameters from text using pattern and extractors.
        
        Args:
            text: Input text
            pattern: Pattern that matched
            extractors: Parameter extraction functions
            
        Returns:
            Dictionary of extracted parameters
        """
        parameters = {}
        
        # If pattern has *, extract the wildcard content
        if "*" in pattern:
            # Find what the * matched
            pattern_parts = pattern.split("*")
            if len(pattern_parts) == 2:
                prefix, suffix = pattern_parts
                text_lower = text.lower()
                
                # Extract the part that matched *
                if prefix and suffix:
                    if text_lower.startswith(prefix.lower()) and text_lower.endswith(suffix.lower()):
                        start = len(prefix)
                        end = len(text) - len(suffix)
                        wildcard_match = text[start:end].strip()
                        parameters["query"] = wildcard_match
                elif prefix:
                    if text_lower.startswith(prefix.lower()):
                        wildcard_match = text[len(prefix):].strip()
                        parameters["query"] = wildcard_match
                elif suffix:
                    if text_lower.endswith(suffix.lower()):
                        wildcard_match = text[:-len(suffix)].strip()
                        parameters["query"] = wildcard_match
        
        # Apply custom extractors
        for param_name, extractor in extractors.items():
            try:
                parameters[param_name] = extractor(text)
            except Exception:
                # If extraction fails, skip this parameter
                pass
        
        return parameters
    
    def _register_default_commands(self) -> None:
        """Register default command patterns."""
        # OPEN_YOUTUBE command - English, Hindi, Punjabi
        self.register_command(
            patterns=["open youtube", "youtube kholo", "youtube ਖੋਲ੍ਹੋ"],
            action_id="OPEN_YOUTUBE",
            description="Open YouTube",
            languages=["en", "hi", "pa"]
        )
        
        # SEARCH command with parameter extraction - English, Hindi, Punjabi
        self.register_command(
            patterns=["search for *", "* dhundo", "* ਲੱਭੋ"],
            action_id="SEARCH",
            description="Search for something",
            languages=["en", "hi", "pa"]
        )
        
        # PLAY_MUSIC command - English, Hindi, Punjabi
        self.register_command(
            patterns=["play music", "music chalao", "music ਚਲਾਓ"],
            action_id="PLAY_MUSIC",
            description="Play music",
            languages=["en", "hi", "pa"]
        )
