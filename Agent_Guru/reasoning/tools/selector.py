"""
Tool selection engine with three-tier strategy.

This module implements intelligent tool selection using:
- Tier 1: Direct intent→tool mapping (<10ms)
- Tier 2: Capability matching with scoring (<50ms)
- Tier 3: LLM-assisted selection for ambiguous cases (<100ms)
"""

import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

from Agent_Guru.reasoning.models.intent import Intent
from Agent_Guru.reasoning.tools.base import Tool, ToolMetadata
from Agent_Guru.reasoning.tools.registry import ToolRegistry


@dataclass
class SelectedTool:
    """Result of tool selection.

    Attributes:
        tool: Selected tool instance
        parameters: Extracted parameters for tool execution
        confidence: Selection confidence (0.0-1.0)
        tier: Selection tier used (1, 2, or 3)
        selection_time_ms: Time taken for selection
    """

    tool: Tool
    parameters: Dict[str, Any]
    confidence: float
    tier: int
    selection_time_ms: int


# Tier 1: Direct intent→tool mappings for common intents
DIRECT_MAPPINGS: Dict[str, str] = {
    "set_timer": "timer.set",
    "cancel_timer": "timer.cancel",
    "query_weather": "weather.query",
    "send_message": "messaging.send",
    "play_music": "music.play",
    "create_calendar_event": "calendar.create_event",
}


class ToolSelector:
    """Three-tier tool selection engine.

    Provides intelligent tool selection with confidence scoring and fallback logic.
    """

    def __init__(self, registry: ToolRegistry) -> None:
        """Initialize tool selector.

        Args:
            registry: Tool registry instance
        """
        self.registry = registry
        self._tier1_hits = 0
        self._tier2_hits = 0
        self._tier3_hits = 0
        self._total_selections = 0

    async def select_tool(self, intent: Intent) -> Optional[SelectedTool]:
        """Select best tool for given intent using three-tier strategy.

        Args:
            intent: Intent to select tool for

        Returns:
            SelectedTool if found, None otherwise
        """
        start_time = time.perf_counter()
        self._total_selections += 1

        # Tier 1: Direct mapping (<10ms)
        result = await self._tier1_direct_mapping(intent)
        if result is not None:
            self._tier1_hits += 1
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return SelectedTool(
                tool=result[0],
                parameters=result[1],
                confidence=1.0,
                tier=1,
                selection_time_ms=elapsed_ms,
            )

        # Tier 2: Capability matching (<50ms)
        result = await self._tier2_capability_matching(intent)
        if result is not None:
            self._tier2_hits += 1
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return SelectedTool(
                tool=result[0],
                parameters=result[1],
                confidence=result[2],
                tier=2,
                selection_time_ms=elapsed_ms,
            )

        # Tier 3: LLM-assisted selection (<100ms)
        result = await self._tier3_llm_assisted(intent)
        if result is not None:
            self._tier3_hits += 1
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return SelectedTool(
                tool=result[0],
                parameters=result[1],
                confidence=result[2],
                tier=3,
                selection_time_ms=elapsed_ms,
            )

        # No suitable tool found
        return None

    async def _tier1_direct_mapping(
        self, intent: Intent
    ) -> Optional[Tuple[Tool, Dict[str, Any]]]:
        """Tier 1: Direct intent→tool mapping.

        Time Complexity: O(1) - hash table lookup
        Target Latency: <10ms

        Args:
            intent: Intent to map

        Returns:
            (tool, parameters) if mapping found, None otherwise
        """
        # Check if intent type has direct mapping
        if intent.intent_type not in DIRECT_MAPPINGS:
            return None

        tool_id = DIRECT_MAPPINGS[intent.intent_type]
        tool = self.registry.get_tool(tool_id)

        if tool is None:
            return None

        # Extract parameters from intent entities
        parameters = self._extract_parameters_from_entities(tool, intent)

        # Validate required parameters are present
        if not self._validate_required_parameters(tool, parameters):
            return None

        return (tool, parameters)

    async def _tier2_capability_matching(
        self, intent: Intent
    ) -> Optional[Tuple[Tool, Dict[str, Any], float]]:
        """Tier 2: Capability-based matching with scoring.

        Time Complexity: O(n) where n = number of tools
        Target Latency: <50ms

        Args:
            intent: Intent to match

        Returns:
            (tool, parameters, confidence) if match found, None otherwise
        """
        # Get all tools
        all_tools = self.registry.list_tools()

        if not all_tools:
            return None

        # Score each tool
        candidates: List[Tuple[ToolMetadata, float]] = []
        for metadata in all_tools:
            score = self._calculate_match_score(metadata, intent)
            if score > 0.5:  # Minimum threshold
                candidates.append((metadata, score))

        if not candidates:
            return None

        # Sort by score (descending)
        candidates.sort(key=lambda x: x[1], reverse=True)

        # Get best candidate
        best_metadata, best_score = candidates[0]
        best_tool = self.registry.get_tool(best_metadata.tool_id)

        if best_tool is None:
            return None

        # Extract parameters
        parameters = self._extract_parameters_from_entities(best_tool, intent)

        # Only accept if score is high enough
        if best_score < 0.5:  # Lower threshold from 0.8 to 0.5
            return None

        return (best_tool, parameters, best_score)

    async def _tier3_llm_assisted(
        self, intent: Intent
    ) -> Optional[Tuple[Tool, Dict[str, Any], float]]:
        """Tier 3: LLM-assisted selection for ambiguous cases.

        Time Complexity: O(1) - single LLM call
        Target Latency: <100ms

        Args:
            intent: Intent to select tool for

        Returns:
            (tool, parameters, confidence) if selection made, None otherwise
        """
        # TODO: Implement LLM-assisted selection in future task
        # For now, return None (will be implemented with LLM integration)
        return None

    def _calculate_match_score(self, metadata: ToolMetadata, intent: Intent) -> float:
        """Calculate match score between tool and intent.

        Scoring factors:
        - Capability overlap: 40%
        - Parameter coverage: 30%
        - Description similarity: 30%

        Args:
            metadata: Tool metadata
            intent: Intent to match

        Returns:
            Match score (0.0-1.0)
        """
        score = 0.0

        # Factor 1: Capability overlap (40%)
        intent_keywords = set(intent.original_input.lower().split())
        capability_keywords = set()
        for cap in metadata.capabilities:
            capability_keywords.update(cap.lower().split("_"))

        if capability_keywords:
            overlap = len(intent_keywords & capability_keywords)
            # More lenient scoring - any overlap is good
            if overlap > 0:
                capability_score = min(overlap / max(len(capability_keywords), 1), 1.0)
                score += capability_score * 0.4
            # Also check if any capability word is substring of intent words
            for cap_word in capability_keywords:
                for intent_word in intent_keywords:
                    if cap_word in intent_word or intent_word in cap_word:
                        score += 0.1  # Bonus for substring match
                        break

        # Factor 2: Parameter coverage (30%)
        available_params = set(intent.entities.keys())
        required_params = {p.name for p in metadata.parameters if p.required}

        if required_params:
            coverage = len(available_params & required_params) / len(required_params)
            score += coverage * 0.3
        else:
            # No required parameters, full score
            score += 0.3

        # Factor 3: Description similarity (30%)
        description_keywords = set(metadata.description.lower().split())
        if description_keywords:
            overlap = len(intent_keywords & description_keywords)
            if overlap > 0:
                description_score = min(overlap / max(len(description_keywords), 1), 1.0)
                score += description_score * 0.3

        return min(score, 1.0)

    def _extract_parameters_from_entities(
        self, tool: Tool, intent: Intent
    ) -> Dict[str, Any]:
        """Extract tool parameters from intent entities.

        Args:
            tool: Tool to extract parameters for
            intent: Intent containing entities

        Returns:
            Dictionary of parameter name → value (extracted from Entity.value)
        """
        parameters: Dict[str, Any] = {}
        metadata = tool.metadata

        # Map entity names to parameter names
        for param in metadata.parameters:
            # Try exact match first
            if param.name in intent.entities:
                entity = intent.entities[param.name]
                # Extract value from Entity object
                parameters[param.name] = entity.value if hasattr(entity, 'value') else entity
            # Try fuzzy match (e.g., "duration" matches "duration_seconds")
            else:
                for entity_name, entity_value in intent.entities.items():
                    if param.name.startswith(entity_name) or entity_name.startswith(
                        param.name
                    ):
                        # Extract value from Entity object
                        parameters[param.name] = entity_value.value if hasattr(entity_value, 'value') else entity_value
                        break

        return parameters

    def _validate_required_parameters(
        self, tool: Tool, parameters: Dict[str, Any]
    ) -> bool:
        """Validate that all required parameters are present.

        Args:
            tool: Tool to validate parameters for
            parameters: Extracted parameters

        Returns:
            True if all required parameters present, False otherwise
        """
        metadata = tool.metadata
        required_params = {p.name for p in metadata.parameters if p.required}
        available_params = set(parameters.keys())

        return required_params.issubset(available_params)

    def get_statistics(self) -> Dict[str, Any]:
        """Get tool selection statistics.

        Returns:
            Dictionary with selection statistics
        """
        if self._total_selections == 0:
            return {
                "total_selections": 0,
                "tier1_percentage": 0.0,
                "tier2_percentage": 0.0,
                "tier3_percentage": 0.0,
            }

        return {
            "total_selections": self._total_selections,
            "tier1_hits": self._tier1_hits,
            "tier2_hits": self._tier2_hits,
            "tier3_hits": self._tier3_hits,
            "tier1_percentage": (self._tier1_hits / self._total_selections) * 100,
            "tier2_percentage": (self._tier2_hits / self._total_selections) * 100,
            "tier3_percentage": (self._tier3_hits / self._total_selections) * 100,
        }
