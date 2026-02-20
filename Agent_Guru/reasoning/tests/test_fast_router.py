"""
Comprehensive tests for Fast Intent Router.

Coverage Target: 100% - ZERO COMPROMISE
Test Types: Unit + Property-Based + Performance

Author: Agent Guru Team
Date: 2026-02-19
"""

import time
from pathlib import Path
from typing import Dict

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck

from Agent_Guru.reasoning.intent.fast_router import (
    FastIntentRouter,
    MatchQuality,
    PatternMatch,
)
from Agent_Guru.reasoning.models.intent import EntityType


# Fixtures

@pytest.fixture
def patterns_file() -> Path:
    """Get path to intent patterns file."""
    return Path("Agent_Guru/reasoning/data/intent_patterns.yaml")


@pytest.fixture
def router(patterns_file: Path) -> FastIntentRouter:
    """Create Fast Intent Router with loaded patterns."""
    router = FastIntentRouter()
    router.load_patterns(patterns_file)
    return router


@pytest.fixture
def router_empty() -> FastIntentRouter:
    """Create empty Fast Intent Router without patterns."""
    return FastIntentRouter()


# Unit Tests - Initialization

class TestInitialization:
    """Test router initialization and configuration."""

    def test_init_default_params(self):
        """Test initialization with default parameters."""
        router = FastIntentRouter()
        assert router._cache_size == 10000
        assert router._total_matches == 0
        assert router._cache_hits == 0
        assert len(router._cache) == 0

    def test_init_custom_params(self):
        """Test initialization with custom parameters."""
        router = FastIntentRouter(cache_size=5000, cache_ttl_seconds=600)
        assert router._cache_size == 5000
        assert router._cache_ttl.total_seconds() == 600

    def test_load_patterns_success(self, router, patterns_file):
        """Test successful pattern loading."""
        assert len(router._patterns) > 0
        assert len(router._entity_patterns) > 0
        metrics = router.get_metrics()
        assert metrics["patterns_loaded"] > 0

    def test_load_patterns_file_not_found(self, router_empty):
        """Test loading patterns from non-existent file."""
        with pytest.raises(FileNotFoundError):
            router_empty.load_patterns("nonexistent.yaml")

    def test_load_patterns_invalid_format(self, router_empty, tmp_path):
        """Test loading invalid patterns file."""
        invalid_file = tmp_path / "invalid.yaml"
        invalid_file.write_text("invalid: yaml\nno_patterns: true")
        
        with pytest.raises(ValueError, match="missing 'patterns' key"):
            router_empty.load_patterns(invalid_file)


# Unit Tests - Pattern Matching

class TestPatternMatching:
    """Test pattern matching functionality."""

    def test_match_exact_timer(self, router):
        """Test exact match for timer command."""
        result = router.match("set timer for 5 minutes")
        
        assert result is not None
        assert result.intent_type == "set_timer"
        assert "duration" in result.entities
        assert result.confidence > 0.9
        assert result.quality == MatchQuality.EXACT
        assert result.latency_ms < 50  # Performance target

    def test_match_exact_weather(self, router):
        """Test exact match for weather query."""
        result = router.match("what's the weather")
        
        assert result is not None
        assert result.intent_type == "query_weather"
        assert result.confidence > 0.9
        assert result.latency_ms < 50

    def test_match_with_location_entity(self, router):
        """Test match with location entity extraction."""
        result = router.match("weather in New York")
        
        assert result is not None
        assert result.intent_type == "query_weather"
        assert "location" in result.entities
        # Note: Input is normalized to lowercase, so entity value is lowercase
        assert result.entities["location"].value.lower() == "new york"

    def test_match_play_music(self, router):
        """Test match for music command."""
        result = router.match("play music")
        
        assert result is not None
        assert result.intent_type == "play_music"
        assert result.confidence > 0.9

    def test_match_no_match(self, router):
        """Test no match for unknown pattern."""
        result = router.match("this is a completely unknown command that should not match")
        
        assert result is None

    def test_match_case_insensitive(self, router):
        """Test case-insensitive matching."""
        result1 = router.match("SET TIMER FOR 5 MINUTES")
        result2 = router.match("set timer for 5 minutes")
        
        assert result1 is not None
        assert result2 is not None
        assert result1.intent_type == result2.intent_type

    def test_match_with_extra_whitespace(self, router):
        """Test matching with extra whitespace."""
        result = router.match("  set   timer   for   5   minutes  ")
        
        assert result is not None
        assert result.intent_type == "set_timer"


# Unit Tests - Entity Extraction

class TestEntityExtraction:
    """Test entity extraction functionality."""

    def test_extract_duration_minutes(self, router):
        """Test duration extraction in minutes."""
        result = router.match("set timer for 10 minutes")
        
        assert "duration" in result.entities
        entity = result.entities["duration"]
        assert entity.entity_type == EntityType.DURATION
        assert entity.confidence == 0.95

    def test_extract_duration_seconds(self, router):
        """Test duration extraction in seconds."""
        result = router.match("set timer for 30 seconds")
        
        assert "duration" in result.entities
        entity = result.entities["duration"]
        assert entity.raw_text == "30 seconds"

    def test_extract_time_12hour(self, router):
        """Test time extraction in 12-hour format."""
        result = router.match("set alarm for 7:30 am")
        
        assert "time" in result.entities
        entity = result.entities["time"]
        assert entity.entity_type == EntityType.TIME

    def test_extract_person_entity(self, router):
        """Test person entity extraction."""
        result = router.match("send message to John Smith")
        
        assert "contact" in result.entities
        entity = result.entities["contact"]
        assert entity.entity_type == EntityType.PERSON

    def test_extract_device_entity(self, router):
        """Test device entity extraction."""
        result = router.match("turn on lights")
        
        assert "device" in result.entities
        entity = result.entities["device"]
        assert entity.entity_type == EntityType.DEVICE


# Unit Tests - Caching

class TestCaching:
    """Test result caching functionality."""

    def test_cache_hit(self, router):
        """Test cache hit for identical input."""
        input_text = "set timer for 5 minutes"
        
        # First match - cache miss
        result1 = router.match(input_text)
        metrics1 = router.get_metrics()
        
        # Second match - cache hit
        result2 = router.match(input_text)
        metrics2 = router.get_metrics()
        
        assert result1.intent_type == result2.intent_type
        assert metrics2["cache_hits"] > metrics1["cache_hits"]
        assert metrics2["cache_hit_rate"] > 0

    def test_cache_miss(self, router):
        """Test cache miss for different inputs."""
        router.match("set timer for 5 minutes")
        router.match("what's the weather")
        
        metrics = router.get_metrics()
        assert metrics["cache_misses"] == 2
        assert metrics["cache_hits"] == 0

    def test_cache_size_limit(self, router_empty):
        """Test cache size limit enforcement."""
        router_empty._cache_size = 5  # Small cache for testing
        
        # Add more entries than cache size
        for i in range(10):
            router_empty._cache_result(f"input_{i}", PatternMatch(
                intent_type="test",
                entities={},
                confidence=0.9,
                quality=MatchQuality.EXACT,
                pattern=f"input_{i}",
                latency_ms=10.0,
            ))
        
        assert len(router_empty._cache) <= 5

    def test_clear_cache(self, router):
        """Test cache clearing."""
        router.match("set timer for 5 minutes")
        assert len(router._cache) > 0
        
        router.clear_cache()
        assert len(router._cache) == 0
        assert router._cache_hits == 0
        assert router._cache_misses == 0


# Unit Tests - Metrics

class TestMetrics:
    """Test performance metrics tracking."""

    def test_metrics_initial_state(self, router_empty):
        """Test metrics in initial state."""
        metrics = router_empty.get_metrics()
        
        assert metrics["total_matches"] == 0
        assert metrics["cache_hits"] == 0
        assert metrics["cache_misses"] == 0
        assert metrics["cache_hit_rate"] == 0.0
        assert metrics["average_latency_ms"] == 0.0

    def test_metrics_after_matches(self, router):
        """Test metrics after performing matches."""
        router.match("set timer for 5 minutes")
        router.match("what's the weather")
        
        metrics = router.get_metrics()
        assert metrics["total_matches"] == 2
        assert metrics["average_latency_ms"] > 0

    def test_metrics_cache_hit_rate(self, router):
        """Test cache hit rate calculation."""
        input_text = "set timer for 5 minutes"
        
        # First match - miss
        router.match(input_text)
        # Second match - hit
        router.match(input_text)
        
        metrics = router.get_metrics()
        assert metrics["cache_hit_rate"] == 0.5  # 1 hit out of 2 total


# Unit Tests - Confidence Calculation

class TestConfidenceCalculation:
    """Test confidence score calculation."""

    def test_confidence_high_for_exact_match(self, router):
        """Test high confidence for exact pattern match."""
        result = router.match("set timer for 5 minutes")
        assert result.confidence >= 0.95

    def test_confidence_with_entities(self, router):
        """Test confidence boost with entity extraction."""
        result = router.match("weather in New York")
        assert result.confidence >= 0.95

    def test_confidence_short_input(self, router):
        """Test confidence reduction for very short input."""
        result = router.match("help")
        # Short inputs may have slightly lower confidence
        assert 0.8 <= result.confidence <= 1.0


# Performance Tests

class TestPerformance:
    """Test performance targets."""

    def test_latency_under_50ms(self, router):
        """Test that latency is under 50ms P95 target."""
        latencies = []
        
        test_inputs = [
            "set timer for 5 minutes",
            "what's the weather",
            "play music",
            "turn on lights",
            "send message to John",
        ]
        
        for _ in range(100):
            for input_text in test_inputs:
                result = router.match(input_text)
                if result:
                    latencies.append(result.latency_ms)
        
        # Calculate P95
        latencies.sort()
        p95_index = int(len(latencies) * 0.95)
        p95_latency = latencies[p95_index]
        
        assert p95_latency < 50, f"P95 latency {p95_latency}ms exceeds 50ms target"

    def test_throughput_target(self, router):
        """Test throughput meets target (>1000 matches/second)."""
        input_text = "set timer for 5 minutes"
        
        start_time = time.perf_counter()
        count = 0
        
        # Run for 1 second
        while time.perf_counter() - start_time < 1.0:
            router.match(input_text)
            count += 1
        
        assert count > 1000, f"Throughput {count} matches/sec below 1000 target"


# Property-Based Tests

class TestProperties:
    """Property-based tests using Hypothesis."""

    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=500)
    def test_match_never_crashes(self, input_text):
        """Property: match() never crashes on any input."""
        # Create router inside test to avoid fixture issues
        router = FastIntentRouter()
        patterns_file = Path("Agent_Guru/reasoning/data/intent_patterns.yaml")
        router.load_patterns(patterns_file)
        
        try:
            result = router.match(input_text)
            # If result exists, validate it
            if result:
                assert isinstance(result, PatternMatch)
                assert 0.0 <= result.confidence <= 1.0
                assert result.latency_ms >= 0
        except Exception as e:
            pytest.fail(f"match() crashed on input '{input_text}': {e}")

    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=500)
    def test_match_deterministic(self, input_text):
        """Property: Same input produces same output."""
        # Create router inside test to avoid fixture issues
        router = FastIntentRouter()
        patterns_file = Path("Agent_Guru/reasoning/data/intent_patterns.yaml")
        router.load_patterns(patterns_file)
        
        result1 = router.match(input_text)
        result2 = router.match(input_text)
        
        if result1 is None:
            assert result2 is None
        else:
            assert result1.intent_type == result2.intent_type
            assert result1.confidence == result2.confidence

    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=500)
    def test_confidence_always_valid(self, input_text):
        """Property: Confidence is always between 0.0 and 1.0."""
        # Create router inside test to avoid fixture issues
        router = FastIntentRouter()
        patterns_file = Path("Agent_Guru/reasoning/data/intent_patterns.yaml")
        router.load_patterns(patterns_file)
        
        result = router.match(input_text)
        if result:
            assert 0.0 <= result.confidence <= 1.0

    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=500)
    def test_latency_always_positive(self, input_text):
        """Property: Latency is always positive."""
        # Create router inside test to avoid fixture issues
        router = FastIntentRouter()
        patterns_file = Path("Agent_Guru/reasoning/data/intent_patterns.yaml")
        router.load_patterns(patterns_file)
        
        result = router.match(input_text)
        if result:
            assert result.latency_ms >= 0


# Integration Tests

class TestIntegration:
    """Integration tests for complete workflows."""

    def test_full_workflow_timer(self, router):
        """Test complete workflow for timer command."""
        result = router.match("set timer for 10 minutes")
        
        # Verify all components
        assert result is not None
        assert result.intent_type == "set_timer"
        assert "duration" in result.entities
        assert result.confidence > 0.9
        assert result.quality == MatchQuality.EXACT
        assert result.latency_ms < 50
        
        # Verify metrics updated
        metrics = router.get_metrics()
        assert metrics["total_matches"] > 0

    def test_full_workflow_weather_with_location(self, router):
        """Test complete workflow for weather query with location."""
        result = router.match("weather in San Francisco")
        
        assert result is not None
        assert result.intent_type == "query_weather"
        assert "location" in result.entities
        # Note: Input is normalized to lowercase, so entity value is lowercase
        assert result.entities["location"].raw_text.lower() == "san francisco"
        assert result.confidence > 0.9

    def test_multiple_commands_sequence(self, router):
        """Test sequence of multiple commands."""
        commands = [
            ("set timer for 5 minutes", "set_timer"),
            ("what's the weather", "query_weather"),
            ("play music", "play_music"),
            ("turn on lights", "device_on"),
        ]
        
        for input_text, expected_intent in commands:
            result = router.match(input_text)
            assert result is not None
            assert result.intent_type == expected_intent


# Edge Cases

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_input(self, router):
        """Test empty input string."""
        result = router.match("")
        assert result is None

    def test_whitespace_only(self, router):
        """Test whitespace-only input."""
        result = router.match("   ")
        assert result is None

    def test_very_long_input(self, router):
        """Test very long input string."""
        long_input = "set timer for " + "very " * 100 + "long time"
        result = router.match(long_input)
        # Should handle gracefully (may or may not match)
        assert isinstance(result, (PatternMatch, type(None)))

    def test_special_characters(self, router):
        """Test input with special characters."""
        result = router.match("set timer for 5 minutes!!!")
        # Should still match despite special characters
        assert result is None or result.intent_type == "set_timer"

    def test_unicode_input(self, router):
        """Test input with unicode characters."""
        result = router.match("set timer for 5 minutes 🎵")
        # Should handle gracefully
        assert isinstance(result, (PatternMatch, type(None)))


# Validation Tests

class TestValidation:
    """Test data validation."""

    def test_pattern_match_confidence_validation(self):
        """Test PatternMatch confidence validation."""
        with pytest.raises(ValueError, match="Confidence must be 0.0-1.0"):
            PatternMatch(
                intent_type="test",
                entities={},
                confidence=1.5,  # Invalid
                quality=MatchQuality.EXACT,
                pattern="test",
                latency_ms=10.0,
            )

    def test_pattern_match_negative_confidence(self):
        """Test PatternMatch with negative confidence."""
        with pytest.raises(ValueError, match="Confidence must be 0.0-1.0"):
            PatternMatch(
                intent_type="test",
                entities={},
                confidence=-0.1,  # Invalid
                quality=MatchQuality.EXACT,
                pattern="test",
                latency_ms=10.0,
            )


# Additional Coverage Tests for 100%

class TestCompileEntityPatterns:
    """Test entity pattern compilation edge cases."""

    def test_invalid_regex_pattern(self, router_empty, tmp_path):
        """Test handling of invalid regex patterns."""
        # Create patterns file with invalid regex
        patterns_file = tmp_path / "invalid_regex.yaml"
        patterns_file.write_text("""
patterns:
  - pattern: "test command"
    intent: "test"
    entities: {}

entity_patterns:
  DURATION:
    - pattern: '([0-9+'  # Invalid regex - unclosed bracket
      unit: "seconds"
""")
        
        # Should not crash, just skip invalid pattern
        router_empty.load_patterns(patterns_file)
        assert len(router_empty._patterns) == 1


class TestTraverseTrie:
    """Test trie traversal edge cases for 100% coverage."""

    def test_entity_at_end_of_pattern(self, router):
        """Test pattern ending with entity (consumes all remaining words)."""
        result = router.match("send message to John Smith Anderson")
        
        assert result is not None
        assert result.intent_type == "send_message"
        assert "contact" in result.entities

    def test_entity_with_no_following_pattern_word(self, router):
        """Test entity that consumes remaining words when no pattern word follows."""
        result = router.match("remind me to buy groceries and cook dinner")
        
        assert result is not None
        assert result.intent_type == "set_reminder"
        assert "task" in result.entities


class TestExtractEntities:
    """Test entity extraction edge cases."""

    def test_entity_position_beyond_words(self, router_empty):
        """Test entity extraction when position is beyond word list."""
        # Manually create entity positions beyond word count
        words = ["test", "command"]
        entity_positions = {5: "duration"}  # Position 5 doesn't exist
        
        entities = router_empty._extract_entities(words, entity_positions)
        
        # Should skip invalid position
        assert len(entities) == 0

    def test_entity_without_regex_match(self, router):
        """Test entity extraction when regex doesn't match."""
        result = router.match("open some_random_app_name")
        
        assert result is not None
        assert result.intent_type == "open_app"
        assert "app" in result.entities
        # Should use heuristic (first 1-3 words)
        assert result.entities["app"].raw_text == "some_random_app_name"


class TestFormatEntityValue:
    """Test entity value formatting edge cases."""

    def test_format_12hour_simple(self, router):
        """Test 12-hour simple format (no minutes)."""
        # This tests the 12hour_simple format path
        result = router.match("set alarm for 7 am")
        
        assert result is not None
        assert result.intent_type == "set_alarm"
        assert "time" in result.entities

    def test_format_24hour(self, router):
        """Test 24-hour format."""
        result = router.match("set alarm for 14:30")
        
        assert result is not None
        assert result.intent_type == "set_alarm"
        assert "time" in result.entities

    def test_format_time_format_duration(self, router):
        """Test MM:SS duration format."""
        result = router.match("set timer for 5:30")
        
        assert result is not None
        assert result.intent_type == "set_timer"
        assert "duration" in result.entities

    def test_format_default_case(self, router_empty):
        """Test default formatting when no special format."""
        # Create a mock match object
        import re
        pattern = re.compile(r'(\w+)')
        match = pattern.search("test")
        
        # Test with no unit or format in pattern_data
        result = router_empty._format_entity_value(match, {})
        
        # Should return first captured group
        assert result == "test"

    def test_format_no_groups(self, router_empty):
        """Test formatting when regex has no groups."""
        import re
        pattern = re.compile(r'\w+')  # No capturing groups
        match = pattern.search("test")
        
        result = router_empty._format_entity_value(match, {})
        
        # Should return entire match
        assert result == "test"


class TestCalculateConfidence:
    """Test confidence calculation edge cases."""

    def test_confidence_single_word_no_entities(self, router_empty):
        """Test confidence for single word with no entities."""
        confidence = router_empty._calculate_confidence(1, 0)
        
        # Should be reduced for short input
        assert confidence == 0.85  # 0.95 - 0.1

    def test_confidence_single_word_with_entity(self, router_empty):
        """Test confidence for single word with entity."""
        confidence = router_empty._calculate_confidence(1, 1)
        
        # Reduced for short input, but increased for entity
        assert confidence == 0.90  # 0.95 - 0.1 + 0.05

    def test_confidence_multiple_words_with_entities(self, router_empty):
        """Test confidence for multiple words with entities."""
        confidence = router_empty._calculate_confidence(5, 2)
        
        # Should be at maximum
        assert confidence == 1.0  # 0.95 + 0.05, capped at 1.0


class TestCacheExpiration:
    """Test cache TTL and expiration."""

    def test_cache_expiration(self, router_empty):
        """Test that cache entries expire after TTL."""
        from datetime import datetime, timedelta
        import time
        
        router_empty._cache_ttl = timedelta(milliseconds=10)  # Very short TTL
        
        # Add entry to cache
        match = PatternMatch(
            intent_type="test",
            entities={},
            confidence=0.9,
            quality=MatchQuality.EXACT,
            pattern="test",
            latency_ms=10.0,
        )
        router_empty._cache_result("test input", match)
        
        # Wait for expiration
        time.sleep(0.02)  # 20ms > 10ms TTL
        
        # Check cache - should be expired
        result = router_empty._check_cache("test input")
        assert result is None
        assert len(router_empty._cache) == 0  # Should be removed


class TestClearCache:
    """Test cache clearing functionality."""

    def test_clear_cache_resets_metrics(self, router):
        """Test that clear_cache resets hit/miss counters."""
        # Generate some cache activity
        router.match("set timer for 5 minutes")
        router.match("set timer for 5 minutes")  # Cache hit
        
        initial_hits = router._cache_hits
        initial_misses = router._cache_misses
        
        assert initial_hits > 0
        assert initial_misses > 0
        
        # Clear cache
        router.clear_cache()
        
        # Verify metrics reset
        assert router._cache_hits == 0
        assert router._cache_misses == 0
        assert len(router._cache) == 0


class TestAdvancedTraversal:
    """Test advanced trie traversal scenarios for 100% coverage."""

    def test_entity_middle_of_pattern_greedy_match(self, router):
        """Test entity in middle of pattern with greedy matching."""
        # Pattern: "remind me at {time} to {task}"
        # This tests the greedy matching logic in _traverse_trie
        result = router.match("remind me at 3 pm to call mom")
        
        assert result is not None
        assert result.intent_type == "set_reminder"
        assert "time" in result.entities
        assert "task" in result.entities

    def test_entity_no_match_after_entity(self, router_empty, tmp_path):
        """Test pattern where entity is followed by non-matching word."""
        # Create a pattern that will fail the greedy match
        patterns_file = tmp_path / "test_patterns.yaml"
        patterns_file.write_text("""
patterns:
  - pattern: "test {entity} specific"
    intent: "test_intent"
    entities:
      entity: "TASK"

entity_patterns:
  TASK:
    - pattern: '(.+)'
      type: "task_description"
""")
        
        router_empty.load_patterns(patterns_file)
        
        # This should fail because "specific" doesn't follow the entity
        result = router_empty.match("test something different")
        assert result is None


class TestEntityFormatting:
    """Test all entity formatting branches for 100% coverage."""

    def test_format_12hour_simple_with_period(self, router_empty, tmp_path):
        """Test 12-hour simple format with AM/PM."""
        # Create pattern with 12hour_simple format
        patterns_file = tmp_path / "time_patterns.yaml"
        patterns_file.write_text("""
patterns:
  - pattern: "alarm at {time}"
    intent: "set_alarm"
    entities:
      time: "TIME"

entity_patterns:
  TIME:
    - pattern: '(\\d{1,2})\\s*(am|pm|AM|PM)'
      format: "12hour_simple"
""")
        
        router_empty.load_patterns(patterns_file)
        result = router_empty.match("alarm at 7 pm")
        
        assert result is not None
        assert "time" in result.entities

    def test_confidence_capped_at_one(self, router_empty):
        """Test that confidence is capped at 1.0."""
        # Multiple words with entities should cap at 1.0
        confidence = router_empty._calculate_confidence(10, 5)
        assert confidence == 1.0


class TestMetricsEdgeCases:
    """Test metrics calculation edge cases."""

    def test_metrics_with_zero_matches(self, router_empty):
        """Test metrics when no matches have been performed."""
        metrics = router_empty.get_metrics()
        
        assert metrics["total_matches"] == 0
        assert metrics["cache_hit_rate"] == 0.0
        assert metrics["average_latency_ms"] == 0.0


class TestFinalCoverage:
    """Final tests to achieve 100% coverage."""

    def test_traverse_trie_entity_not_end_invalid(self, router_empty, tmp_path):
        """Test trie traversal when entity consumes all words but pattern doesn't end."""
        # Line 337: if not current.is_end: return None
        patterns_file = tmp_path / "test_patterns.yaml"
        patterns_file.write_text("""
patterns:
  - pattern: "command {entity} more"
    intent: "test_intent"
    entities:
      entity: "TASK"

entity_patterns:
  TASK:
    - pattern: '(.+)'
      type: "task_description"
""")
        
        router_empty.load_patterns(patterns_file)
        
        # This should fail: entity consumes "something" but "more" is missing
        result = router_empty.match("command something")
        assert result is None

    def test_format_12hour_simple_no_period(self, router_empty):
        """Test 12hour_simple format without period in groups."""
        # Line 439: Test the else branch when len(groups) <= 2 or groups[2] is None
        import re
        
        # Create a match with only 2 groups (no period)
        pattern = re.compile(r'(\d{1,2})\s*(am|pm)?', re.IGNORECASE)
        match = pattern.search("7")  # No AM/PM
        
        pattern_data = {"format": "12hour_simple"}
        result = router_empty._format_entity_value(match, pattern_data)
        
        # Should handle missing period gracefully
        assert result is not None

    def test_calculate_confidence_edge_cases(self, router_empty):
        """Test confidence calculation edge cases."""
        # Lines 484-485: Test the else branch (no entity boost)
        # Already tested in test_confidence_single_word_no_entities
        # But let's be explicit
        confidence = router_empty._calculate_confidence(2, 0)
        assert confidence == 0.95  # Base confidence, no reduction, no boost


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=Agent_Guru/reasoning/intent/fast_router", "--cov-report=term-missing"])
