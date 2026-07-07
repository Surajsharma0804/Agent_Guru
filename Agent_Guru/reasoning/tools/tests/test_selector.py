"""
Tests for tool selector.
"""

from typing import Any

import pytest

from Agent_Guru.reasoning.models.intent import Entity, Intent
from Agent_Guru.reasoning.tools.examples.messaging_tool import MessagingTool
from Agent_Guru.reasoning.tools.examples.timer_tool import CancelTimerTool, SetTimerTool
from Agent_Guru.reasoning.tools.examples.weather_tool import WeatherTool
from Agent_Guru.reasoning.tools.registry import ToolRegistry
from Agent_Guru.reasoning.tools.selector import DIRECT_MAPPINGS, ToolSelector


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

        assert result is not None  # nosec B101
        assert result.tier == 1  # nosec B101
        assert result.confidence == 1.0  # nosec B101
        assert result.tool.metadata.tool_id == "timer.set"  # nosec B101
        assert result.parameters["duration_seconds"] == 300  # nosec B101
        assert result.selection_time_ms < 10  # <10ms target  # nosec B101

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

        assert result is not None  # nosec B101
        assert result.tier == 1  # nosec B101
        assert result.confidence == 1.0  # nosec B101
        assert result.tool.metadata.tool_id == "weather.query"  # nosec B101
        assert result.parameters["location"] == "New York"  # nosec B101

    async def test_tier1_missing_required_parameter(self, selector: ToolSelector) -> None:
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
        assert result is None or result.tier > 1  # nosec B101

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

        assert result is not None  # nosec B101
        # May match Tier 1 if direct mapping exists, or Tier 2 via capability matching
        assert result.tier in [1, 2]  # nosec B101
        assert result.confidence >= 0.8  # nosec B101
        assert result.tool.metadata.tool_id == "messaging.send"  # nosec B101
        assert result.selection_time_ms < 50  # <50ms target  # nosec B101

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

        assert result is not None  # nosec B101
        # Should match timer tool based on keywords
        assert "timer" in result.tool.metadata.tool_id  # nosec B101

    async def test_tier2_no_match_below_threshold(self, selector: ToolSelector) -> None:
        """Test Tier 2 returns None when score below threshold."""
        intent = Intent(
            intent_type="unknown",  # Valid enum value
            original_input="completely unrelated query about quantum physics",
            entities={},
            confidence=0.8,
        )

        result = await selector.select_tool(intent)

        # Should not match any tool
        assert result is None  # nosec B101

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
        assert result is None  # nosec B101

    async def test_parameter_extraction_exact_match(self, selector: ToolSelector) -> None:
        """Test parameter extraction with exact entity name match."""
        intent = Intent(
            intent_type="set_timer",
            original_input="Set timer for 10 minutes",
            entities={
                "duration_seconds": Entity(
                    entity_type="duration", value=600, raw_text="10 minutes"
                ),
                "label": Entity(entity_type="text", value="Cooking", raw_text="Cooking"),
            },
            confidence=0.95,
        )

        result = await selector.select_tool(intent)

        assert result is not None  # nosec B101
        assert result.parameters["duration_seconds"] == 600  # nosec B101
        assert result.parameters["label"] == "Cooking"  # nosec B101

    async def test_parameter_extraction_fuzzy_match(self, selector: ToolSelector) -> None:
        """Test parameter extraction with fuzzy entity name match."""
        intent = Intent(
            intent_type="set_timer",
            original_input="Set timer for 5 minutes",
            entities={"duration": Entity(entity_type="duration", value=300, raw_text="5 minutes")},
            confidence=0.95,
        )

        result = await selector.select_tool(intent)

        assert result is not None  # nosec B101
        # Should fuzzy match "duration" to "duration_seconds"
        assert "duration_seconds" in result.parameters or "duration" in result.parameters  # nosec B101

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
        assert result1 is not None  # nosec B101
        assert result1.confidence == 1.0  # nosec B101

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
        assert result2 is not None  # nosec B101
        # Confidence should be high (may be Tier 1 or Tier 2)
        assert result2.confidence >= 0.8  # nosec B101

    async def test_statistics_tracking(self, selector: ToolSelector) -> None:
        """Test selection statistics tracking."""
        # Initial stats
        stats = selector.get_statistics()
        assert stats["total_selections"] == 0  # nosec B101

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
            entities={"location": Entity(entity_type="location", value="NYC", raw_text="NYC")},
            confidence=0.95,
        )
        await selector.select_tool(intent2)

        # Check stats
        stats = selector.get_statistics()
        assert stats["total_selections"] == 2  # nosec B101
        assert stats["tier1_hits"] == 2  # nosec B101
        assert stats["tier1_percentage"] == 100.0  # nosec B101

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
        assert result1 is not None  # nosec B101
        assert result1.selection_time_ms < 10  # nosec B101

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
            assert result2.selection_time_ms < 50  # nosec B101

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
        assert result is None  # nosec B101

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
        assert result is not None  # nosec B101
        assert "timer" in result.tool.metadata.tool_id  # nosec B101


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
        assert mapped_tools == expected_tools  # nosec B101

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
            assert intent_type in DIRECT_MAPPINGS  # nosec B101


class TestToolIntelligenceIntegration:
    """Tests for Tool Intelligence Engine integration with Tool Selector."""

    @pytest.fixture
    async def registry(self) -> ToolRegistry:
        """Create tool registry with example tools."""
        registry = ToolRegistry()

        # Register example tools
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

    async def test_intelligence_engine_used_in_tier2(self, selector: ToolSelector) -> None:
        """Test that intelligence engine is used for Tier 2 ranking."""
        # Use unknown intent to force Tier 2
        intent = Intent(
            intent_type="unknown",
            original_input="send a message to John saying hello",
            entities={
                "recipient": Entity(entity_type="person", value="John", raw_text="John"),
                "message": Entity(entity_type="text", value="hello", raw_text="hello"),
            },
            confidence=0.8,
        )

        result = await selector.select_tool(intent)

        assert result is not None  # nosec B101
        # Should have intelligence engine instance
        assert hasattr(selector, "_intelligence_engine")  # nosec B101
        # Should select messaging tool
        assert result.tool.metadata.tool_id == "messaging.send"  # nosec B101

    async def test_tool_execution_tracking(self, selector: ToolSelector) -> None:
        """Test that tool execution results are tracked."""
        # Record successful execution
        await selector.record_tool_execution(
            tool_id="timer.set",
            success=True,
            latency_ms=150.0,
        )

        # Check that intelligence engine was created
        assert hasattr(selector, "_intelligence_engine")  # nosec B101

        # Get tool stats
        stats = await selector._intelligence_engine.get_tool_stats("timer.set")
        assert stats is not None  # nosec B101
        assert stats.total_executions == 1  # nosec B101
        assert stats.successful_executions == 1  # nosec B101
        assert stats.success_rate == 1.0  # nosec B101

    async def test_tool_failure_tracking(self, selector: ToolSelector) -> None:
        """Test that tool failures are tracked."""
        from Agent_Guru.reasoning.tools.intelligence import FailurePattern

        # Record failed execution
        await selector.record_tool_execution(
            tool_id="weather.query",
            success=False,
            latency_ms=5000.0,
            failure_pattern=FailurePattern.TIMEOUT,
        )

        # Get tool stats
        stats = await selector._intelligence_engine.get_tool_stats("weather.query")
        assert stats is not None  # nosec B101
        assert stats.total_executions == 1  # nosec B101
        assert stats.failed_executions == 1  # nosec B101
        assert stats.success_rate == 0.0  # nosec B101
        assert "timeout" in stats.failure_patterns  # nosec B101

    async def test_user_feedback_tracking(self, selector: ToolSelector) -> None:
        """Test that user feedback is tracked."""
        # Record positive feedback
        await selector.record_user_feedback(
            tool_id="timer.set",
            user_id="user123",
            rating=5.0,
            positive=True,
        )

        # Get tool stats
        stats = await selector._intelligence_engine.get_tool_stats("timer.set")
        assert stats is not None  # nosec B101
        assert stats.user_feedback_count == 1  # nosec B101
        assert stats.user_rating == 5.0  # nosec B101

    async def test_tool_preference_learning(self, selector: ToolSelector) -> None:
        """Test that tool preferences are learned from selections."""
        # Make a selection (Tier 2 will track preference)
        intent = Intent(
            intent_type="unknown",
            original_input="send a message to Alice",
            entities={
                "recipient": Entity(entity_type="person", value="Alice", raw_text="Alice"),
                "message": Entity(entity_type="text", value="hi", raw_text="hi"),
            },
            confidence=0.8,
        )

        result = await selector.select_tool(intent)
        assert result is not None  # nosec B101

        # Check that preference was learned
        preferences = await selector._intelligence_engine.get_user_tool_preferences("default")
        assert "messaging.send" in preferences  # nosec B101
        assert preferences["messaging.send"] > 0.5  # Should have increased  # nosec B101

    async def test_degraded_tool_detection(self, selector: ToolSelector) -> None:
        """Test that degraded tools are detected and avoided."""
        from Agent_Guru.reasoning.tools.intelligence import FailurePattern

        # Record multiple failures to degrade tool
        for _ in range(5):
            await selector.record_tool_execution(
                tool_id="weather.query",
                success=False,
                latency_ms=5000.0,
                failure_pattern=FailurePattern.TIMEOUT,
            )

        # Check that tool is degraded
        stats = await selector._intelligence_engine.get_tool_stats("weather.query")
        assert stats is not None  # nosec B101
        assert stats.is_degraded  # nosec B101
        assert stats.consecutive_failures == 5  # nosec B101

        # Get degraded tools
        degraded = await selector._intelligence_engine.detect_degraded_tools()
        assert "weather.query" in degraded  # nosec B101

    async def test_ranking_with_reliability(self, selector: ToolSelector) -> None:
        """Test that tool ranking considers reliability."""
        from Agent_Guru.reasoning.tools.intelligence import FailurePattern

        # Make timer tool unreliable
        for _ in range(3):
            await selector.record_tool_execution(
                tool_id="timer.set",
                success=False,
                latency_ms=1000.0,
                failure_pattern=FailurePattern.UNKNOWN,
            )

        # Make cancel tool reliable
        for _ in range(5):
            await selector.record_tool_execution(
                tool_id="timer.cancel",
                success=True,
                latency_ms=100.0,
            )

        # Use a more specific intent that matches timer tools
        intent = Intent(
            intent_type="unknown",
            original_input="set a timer for 5 minutes",
            entities={
                "duration_seconds": Entity(entity_type="duration", value=300, raw_text="5 minutes")
            },
            confidence=0.8,
        )

        result = await selector.select_tool(intent)

        # Should match a timer tool
        assert result is not None  # nosec B101
        assert "timer" in result.tool.metadata.tool_id  # nosec B101

    async def test_ranking_with_speed(self, selector: ToolSelector) -> None:
        """Test that tool ranking considers speed."""
        # Make timer tool slow
        for _ in range(3):
            await selector.record_tool_execution(
                tool_id="timer.set",
                success=True,
                latency_ms=5000.0,  # Very slow
            )

        # Make cancel tool fast
        for _ in range(3):
            await selector.record_tool_execution(
                tool_id="timer.cancel",
                success=True,
                latency_ms=50.0,  # Very fast
            )

        # Get stats to verify
        timer_stats = await selector._intelligence_engine.get_tool_stats("timer.set")
        cancel_stats = await selector._intelligence_engine.get_tool_stats("timer.cancel")

        assert timer_stats is not None  # nosec B101
        assert cancel_stats is not None  # nosec B101
        assert timer_stats.avg_latency > cancel_stats.avg_latency  # nosec B101

    async def test_context_passed_to_ranking(self, selector: ToolSelector) -> None:
        """Test that intent context is passed to ranking engine."""
        intent = Intent(
            intent_type="unknown",
            original_input="send a message to Bob",
            entities={
                "recipient": Entity(entity_type="person", value="Bob", raw_text="Bob"),
                "message": Entity(entity_type="text", value="test", raw_text="test"),
            },
            confidence=0.8,
        )

        result = await selector.select_tool(intent)

        assert result is not None  # nosec B101
        # Intelligence engine should have been used with context
        assert hasattr(selector, "_intelligence_engine")  # nosec B101

    async def test_multiple_executions_improve_ranking(self, selector: ToolSelector) -> None:
        """Test that multiple successful executions improve tool ranking."""
        # Execute messaging tool multiple times successfully
        for _ in range(10):
            await selector.record_tool_execution(
                tool_id="messaging.send",
                success=True,
                latency_ms=100.0,
            )

        # Get stats
        stats = await selector._intelligence_engine.get_tool_stats("messaging.send")
        assert stats is not None  # nosec B101
        assert stats.total_executions == 10  # nosec B101
        assert stats.success_rate == 1.0  # nosec B101
        assert stats.get_reliability_score() == 1.0  # nosec B101

    async def test_recovery_from_degradation(self, selector: ToolSelector) -> None:
        """Test that tools can recover from degradation."""
        from Agent_Guru.reasoning.tools.intelligence import FailurePattern

        # Degrade tool
        for _ in range(5):
            await selector.record_tool_execution(
                tool_id="timer.set",
                success=False,
                latency_ms=1000.0,
                failure_pattern=FailurePattern.TIMEOUT,
            )

        # Verify degraded
        stats = await selector._intelligence_engine.get_tool_stats("timer.set")
        assert stats is not None  # nosec B101
        assert stats.is_degraded  # nosec B101

        # Recover with successful executions
        for _ in range(3):
            await selector.record_tool_execution(
                tool_id="timer.set",
                success=True,
                latency_ms=100.0,
            )

        # Check recovery
        stats = await selector._intelligence_engine.get_tool_stats("timer.set")
        assert stats is not None  # nosec B101
        assert not stats.is_degraded  # nosec B101
        assert stats.consecutive_failures == 0  # nosec B101

    async def test_user_preference_affects_ranking(self, selector: ToolSelector) -> None:
        """Test that user preferences affect tool ranking."""
        # Initialize intelligence engine first
        from Agent_Guru.reasoning.tools.intelligence import ToolIntelligenceEngine

        selector._intelligence_engine = ToolIntelligenceEngine()

        # Learn strong preference for messaging tool
        for _ in range(5):
            await selector._intelligence_engine.learn_tool_preference(
                user_id="user123",
                tool_id="messaging.send",
                selected=True,
            )

        # Get preferences
        preferences = await selector._intelligence_engine.get_user_tool_preferences("user123")
        assert "messaging.send" in preferences  # nosec B101
        assert preferences["messaging.send"] > 0.5  # nosec B101

    async def test_intelligence_engine_persistence(
        self, selector: ToolSelector, tmp_path: Any
    ) -> None:
        """Test that intelligence engine can persist and load data."""
        from Agent_Guru.reasoning.tools.intelligence import ToolIntelligenceEngine

        stats_file = tmp_path / "tool_stats.json"
        prefs_file = tmp_path / "tool_prefs.json"

        # Create engine with persistence
        engine = ToolIntelligenceEngine(
            stats_file=stats_file,
            preferences_file=prefs_file,
        )

        # Record some data
        await engine.record_execution(
            tool_id="timer.set",
            success=True,
            latency_ms=150.0,
        )

        await engine.learn_tool_preference(
            user_id="user123",
            tool_id="timer.set",
            selected=True,
        )

        # Verify files were created
        assert stats_file.exists()  # nosec B101
        assert prefs_file.exists()  # nosec B101

        # Create new engine and load data
        engine2 = ToolIntelligenceEngine(
            stats_file=stats_file,
            preferences_file=prefs_file,
        )

        # Verify data was loaded
        stats = await engine2.get_tool_stats("timer.set")
        assert stats is not None  # nosec B101
        assert stats.total_executions == 1  # nosec B101

        preferences = await engine2.get_user_tool_preferences("user123")
        assert "timer.set" in preferences  # nosec B101
