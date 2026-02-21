"""
Tests for tool selector.
"""

import pytest
from typing import Any, Dict

from Agent_Guru.reasoning.models.intent import Intent, Entity
from Agent_Guru.reasoning.tools.selector import ToolSelector, SelectedTool, DIRECT_MAPPINGS
from Agent_Guru.reasoning.tools.registry import ToolRegistry
from Agent_Guru.reasoning.tools.examples.timer_tool import SetTimerTool, CancelTimerTool
from Agent_Guru.reasoning.tools.examples.weather_tool import WeatherTool
from Agent_Guru.reasoning.tools.examples.messaging_tool import MessagingTool


class TestToolSelector:
    """Tests for ToolSelector."""

    @pytest.fixture
    async def registry(self) -> ToolRegistry:
        """Create tool registry with example tools."""
        # Create fresh registry for each test
        registry = ToolRegistry()

        # Register example tools directly with registry
        timer_tool = SetTimerTool()
        await registry.register(timer_tool, timer_tool._tool_metadata)

        cancel_tool = CancelTimerTool()
        await registry.register(cancel_tool, cancel_tool._tool_metadata)

        weather_tool = WeatherTool()
        await registry.register(weather_tool, weather_tool._tool_metadata)

        messaging_tool = MessagingTool()
        await registry.register(messaging_tool, messaging_tool._tool_metadata)

        return registry

    @pytest.fixture
    def selector(self, registry: ToolRegistry) -> ToolSelector:
        """Create tool selector."""
        return ToolSelector(registry)

    async def test_tier1_direct_mapping_timer(self, selector: ToolSelector) -> None:
        """Test Tier 1 direct mapping for timer intent."""
        intent = Intent(
            intent_type="set_timer",
            text="Set a timer for 5 minutes",
            entities={
                "duration_seconds": Entity(
                    entity_type="duration",
                    value=300,
                    raw_text="5 minutes",
                )
            },
            confidence=0.95,
            original_input="Set a timer for 5 minutes",
        )

        result = await selector.select_tool(intent)

        assert result is not None
        assert result.tier == 1
        assert result.confidence == 1.0
        assert result.tool.metadata.tool_id == "timer.set"
        assert result.parameters["duration_seconds"] == 300
        assert result.selection_time_ms < 10  # <10ms target

    async def test_tier1_direct_mapping_weather(self, selector: ToolSelector) -> None:
        """Test Tier 1 direct mapping for weather intent."""
        intent = Intent(
            intent_type="query_weather",
            text="What's the weather in New York?",
            entities={
                "location": Entity(
                    entity_type="location",
                    value="New York",
                    raw_text="New York",
                )
            },
            confidence=0.95,
            original_input="What's the weather in New York?",
        )

        result = await selector.select_tool(intent)

        assert result is not None
        assert result.tier == 1
        assert result.confidence == 1.0
        assert result.tool.metadata.tool_id == "weather.query"
        assert result.parameters["location"] == "New York"

    async def test_tier1_missing_required_parameter(
        self, selector: ToolSelector
    ) -> None:
        """Test Tier 1 fails when required parameter missing."""
        intent = Intent(
            intent_type="set_timer",
            text="Set a timer",
            entities={},  # Missing duration_seconds
            confidence=0.95,
            original_input="Set a timer",
        )

        result = await selector.select_tool(intent)

        # Should fall through to Tier 2 or return None
        assert result is None or result.tier > 1

    async def test_tier2_capability_matching(self, selector: ToolSelector) -> None:
        """Test Tier 2 capability matching."""
        # Use "unknown" intent type to force Tier 2 matching
        intent = Intent(
            intent_type="unknown",  # Not in direct mappings
            original_input="Send a message to John saying hello",
            entities={
                "recipient": Entity(entity_type="person", value="John", raw_text="John"),
                "message": Entity(entity_type="text", value="hello", raw_text="hello"),
            },
            confidence=0.8,
        )

        result = await selector.select_tool(intent)

        assert result is not None
        # May match Tier 1 if direct mapping exists, or Tier 2 via capability matching
        assert result.tier in [1, 2]
        assert result.confidence >= 0.8
        assert result.tool.metadata.tool_id == "messaging.send"
        assert result.selection_time_ms < 50  # <50ms target

    async def test_tier2_scoring_algorithm(self, selector: ToolSelector) -> None:
        """Test Tier 2 scoring algorithm."""
        intent = Intent(
            intent_type="unknown",  # Valid enum value
            original_input="set a timer for cooking for 10 minutes",
            entities={
                "duration_seconds": Entity(entity_type="duration", value=600, raw_text="10 minutes")
            },
            confidence=0.8,
        )

        result = await selector.select_tool(intent)

        assert result is not None
        # Should match timer tool based on keywords
        assert "timer" in result.tool.metadata.tool_id

    async def test_tier2_no_match_below_threshold(
        self, selector: ToolSelector
    ) -> None:
        """Test Tier 2 returns None when score below threshold."""
        intent = Intent(
            intent_type="unknown",  # Valid enum value
            original_input="completely unrelated query about quantum physics",
            entities={},
            confidence=0.8,
        )

        result = await selector.select_tool(intent)

        # Should not match any tool
        assert result is None

    async def test_tier3_not_implemented(self, selector: ToolSelector) -> None:
        """Test Tier 3 returns None (not yet implemented)."""
        intent = Intent(
            intent_type="unknown",  # Valid enum value
            original_input="do something",
            entities={},
            confidence=0.5,
        )

        result = await selector.select_tool(intent)

        # Tier 3 not implemented yet
        assert result is None

    async def test_parameter_extraction_exact_match(
        self, selector: ToolSelector
    ) -> None:
        """Test parameter extraction with exact entity name match."""
        intent = Intent(
            intent_type="set_timer",
            original_input="Set timer for 10 minutes",
            entities={
                "duration_seconds": Entity(entity_type="duration", value=600, raw_text="10 minutes"),
                "label": Entity(entity_type="text", value="Cooking", raw_text="Cooking"),
            },
            confidence=0.95,
        )

        result = await selector.select_tool(intent)

        assert result is not None
        assert result.parameters["duration_seconds"] == 600
        assert result.parameters["label"] == "Cooking"

    async def test_parameter_extraction_fuzzy_match(
        self, selector: ToolSelector
    ) -> None:
        """Test parameter extraction with fuzzy entity name match."""
        intent = Intent(
            intent_type="set_timer",
            original_input="Set timer for 5 minutes",
            entities={
                "duration": Entity(entity_type="duration", value=300, raw_text="5 minutes")
            },
            confidence=0.95,
        )

        result = await selector.select_tool(intent)

        assert result is not None
        # Should fuzzy match "duration" to "duration_seconds"
        assert "duration_seconds" in result.parameters or "duration" in result.parameters

    async def test_confidence_scoring(self, selector: ToolSelector) -> None:
        """Test confidence scoring for different tiers."""
        # Tier 1: confidence = 1.0
        intent1 = Intent(
            intent_type="set_timer",
            original_input="Set timer",
            entities={
                "duration_seconds": Entity(entity_type="duration", value=300, raw_text="5 minutes")
            },
            confidence=0.95,
        )
        result1 = await selector.select_tool(intent1)
        assert result1 is not None
        assert result1.confidence == 1.0

        # Tier 2: confidence = match score (0.8-1.0)
        intent2 = Intent(
            intent_type="unknown",
            original_input="send a message to John saying hi",
            entities={
                "recipient": Entity(entity_type="person", value="John", raw_text="John"),
                "message": Entity(entity_type="text", value="hi", raw_text="hi"),
            },
            confidence=0.8,
        )
        result2 = await selector.select_tool(intent2)
        assert result2 is not None
        # Confidence should be high (may be Tier 1 or Tier 2)
        assert result2.confidence >= 0.8

    async def test_statistics_tracking(self, selector: ToolSelector) -> None:
        """Test selection statistics tracking."""
        # Initial stats
        stats = selector.get_statistics()
        assert stats["total_selections"] == 0

        # Make some selections
        intent1 = Intent(
            intent_type="set_timer",
            original_input="Set timer",
            entities={
                "duration_seconds": Entity(entity_type="duration", value=300, raw_text="5 minutes")
            },
            confidence=0.95,
        )
        await selector.select_tool(intent1)

        intent2 = Intent(
            intent_type="query_weather",
            original_input="Weather?",
            entities={
                "location": Entity(entity_type="location", value="NYC", raw_text="NYC")
            },
            confidence=0.95,
        )
        await selector.select_tool(intent2)

        # Check stats
        stats = selector.get_statistics()
        assert stats["total_selections"] == 2
        assert stats["tier1_hits"] == 2
        assert stats["tier1_percentage"] == 100.0

    async def test_latency_targets(self, selector: ToolSelector) -> None:
        """Test that latency targets are met."""
        # Tier 1: <10ms
        intent1 = Intent(
            intent_type="set_timer",
            original_input="Set timer",
            entities={
                "duration_seconds": Entity(entity_type="duration", value=300, raw_text="5 minutes")
            },
            confidence=0.95,
        )
        result1 = await selector.select_tool(intent1)
        assert result1 is not None
        assert result1.selection_time_ms < 10

        # Tier 2: <50ms
        intent2 = Intent(
            intent_type="unknown",
            original_input="send a message to John saying hello",
            entities={
                "recipient": Entity(entity_type="person", value="John", raw_text="John"),
                "message": Entity(entity_type="text", value="hello", raw_text="hello"),
            },
            confidence=0.8,
        )
        result2 = await selector.select_tool(intent2)
        if result2 is not None:
            # Should be fast regardless of tier
            assert result2.selection_time_ms < 50

    async def test_empty_registry(self) -> None:
        """Test selector with empty registry."""
        empty_registry = ToolRegistry()
        selector = ToolSelector(empty_registry)

        intent = Intent(
            intent_type="set_timer",
            original_input="Set timer",
            entities={
                "duration_seconds": Entity(entity_type="duration", value=300, raw_text="5 minutes")
            },
            confidence=0.95,
        )

        result = await selector.select_tool(intent)
        assert result is None

    async def test_multiple_candidates_ranking(self, selector: ToolSelector) -> None:
        """Test that best candidate is selected when multiple match."""
        intent = Intent(
            intent_type="unknown",
            original_input="set a timer for cooking for 10 minutes",
            entities={
                "duration_seconds": Entity(entity_type="duration", value=600, raw_text="10 minutes")
            },
            confidence=0.8,
        )

        result = await selector.select_tool(intent)

        # Should select timer tool (best match)
        assert result is not None
        assert "timer" in result.tool.metadata.tool_id


class TestDirectMappings:
    """Tests for direct intent→tool mappings."""

    def test_all_mappings_valid(self) -> None:
        """Test that all direct mappings are valid tool IDs."""
        expected_tools = {
            "timer.set",
            "timer.cancel",
            "weather.query",
            "messaging.send",
            "music.play",
            "calendar.create_event",
        }

        mapped_tools = set(DIRECT_MAPPINGS.values())
        assert mapped_tools == expected_tools

    def test_common_intents_mapped(self) -> None:
        """Test that common intents have direct mappings."""
        common_intents = [
            "set_timer",
            "cancel_timer",
            "query_weather",
            "send_message",
            "play_music",
            "create_calendar_event",
        ]

        for intent_type in common_intents:
            assert intent_type in DIRECT_MAPPINGS
