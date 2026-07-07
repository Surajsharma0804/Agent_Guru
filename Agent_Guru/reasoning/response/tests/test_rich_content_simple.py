"""
Simplified tests for Rich Content Generator

These tests use mock objects to avoid Pydantic validation issues.
Coverage Target: >80%
"""

from unittest.mock import Mock

import pytest

from Agent_Guru.reasoning.models.result import ExecutionResult
from Agent_Guru.reasoning.response.rich_content_generator import (
    ClientCapability,
    ContentType,
    RichContentGenerator,
)


class TestRichContentGeneratorSimple:
    """Simplified unit tests for RichContentGenerator."""

    @pytest.fixture
    def generator(self) -> RichContentGenerator:
        """Create rich content generator."""
        return RichContentGenerator()

    @pytest.fixture
    def timer_result(self) -> ExecutionResult:
        """Create timer execution result."""
        return ExecutionResult(
            success=True,
            result_data={"timer_id": "timer_123", "duration": 300},
            execution_time=0.05,
            action_id="action_123",
            tool_id="set_timer",
        )

    @pytest.fixture
    def timer_intent(self) -> Mock:
        """Create mock timer intent."""
        intent = Mock()
        intent.intent_type = "set_timer"
        intent.entities = {"duration": "5 minutes"}
        intent.get_entity = lambda key, default=None: intent.entities.get(key, default)
        return intent

    @pytest.fixture
    def weather_result(self) -> ExecutionResult:
        """Create weather execution result."""
        return ExecutionResult(
            success=True,
            result_data={
                "temperature": 72,
                "condition": "Sunny",
                "icon_url": "https://example.com/sunny.png",
            },
            execution_time=0.15,
            action_id="action_456",
            tool_id="query_weather",
        )

    @pytest.fixture
    def weather_intent(self) -> Mock:
        """Create mock weather intent."""
        intent = Mock()
        intent.intent_type = "query_weather"
        intent.entities = {"location": "San Francisco"}
        intent.get_entity = lambda key, default=None: intent.entities.get(key, default)
        return intent

    def test_initialization(self, generator: RichContentGenerator):
        """Test generator initialization."""
        assert generator is not None  # nosec B101
        assert isinstance(generator.INTENT_CONTENT_MAP, dict)  # nosec B101
        assert len(generator.INTENT_CONTENT_MAP) > 0  # nosec B101

    def test_generate_with_no_capabilities(
        self, generator: RichContentGenerator, timer_result: ExecutionResult, timer_intent: Mock
    ):
        """Test generation with text-only client."""
        capabilities = {ClientCapability.TEXT_ONLY}
        content = generator.generate(timer_result, timer_intent, capabilities)

        # Should return None for text-only clients
        assert content is None  # nosec B101

    def test_generate_with_card_capability(
        self, generator: RichContentGenerator, timer_result: ExecutionResult, timer_intent: Mock
    ):
        """Test generation with card capability."""
        capabilities = {ClientCapability.CARDS, ClientCapability.BUTTONS}
        content = generator.generate(timer_result, timer_intent, capabilities)

        assert content is not None  # nosec B101
        assert content["type"] == "card"  # nosec B101
        assert "title" in content  # nosec B101
        assert "body" in content  # nosec B101
        assert "buttons" in content  # nosec B101
        assert len(content["buttons"]) > 0  # nosec B101

    def test_generate_timer_card(
        self, generator: RichContentGenerator, timer_result: ExecutionResult, timer_intent: Mock
    ):
        """Test timer card generation."""
        capabilities = {ClientCapability.CARDS, ClientCapability.BUTTONS}
        content = generator.generate(timer_result, timer_intent, capabilities)

        assert content["type"] == "card"  # nosec B101
        assert content["title"] == "Timer Set"  # nosec B101
        assert "5 minutes" in content["body"]  # nosec B101
        assert content["icon"] == "⏱️"  # nosec B101
        assert len(content["buttons"]) == 2  # nosec B101

    def test_generate_weather_card(
        self, generator: RichContentGenerator, weather_result: ExecutionResult, weather_intent: Mock
    ):
        """Test weather card generation."""
        capabilities = {ClientCapability.CARDS, ClientCapability.IMAGES, ClientCapability.BUTTONS}
        content = generator.generate(weather_result, weather_intent, capabilities)

        assert content["type"] == "card"  # nosec B101
        assert "Weather in San Francisco" in content["title"]  # nosec B101
        assert "72°F" in content["body"]  # nosec B101
        assert "Sunny" in content["body"]  # nosec B101
        assert content["image"] == "https://example.com/sunny.png"  # nosec B101
        assert len(content["buttons"]) == 2  # nosec B101

    def test_generate_with_all_capabilities(
        self, generator: RichContentGenerator, timer_result: ExecutionResult, timer_intent: Mock
    ):
        """Test generation with all capabilities."""
        capabilities = set(ClientCapability)
        content = generator.generate(timer_result, timer_intent, capabilities)

        assert content is not None  # nosec B101
        assert content["type"] == "card"  # nosec B101

    def test_generate_with_none_capabilities(
        self, generator: RichContentGenerator, timer_result: ExecutionResult, timer_intent: Mock
    ):
        """Test generation with None capabilities (defaults to all)."""
        content = generator.generate(timer_result, timer_intent, None)

        assert content is not None  # nosec B101
        assert content["type"] == "card"  # nosec B101

    def test_supports_rich_content(self, generator: RichContentGenerator):
        """Test rich content support detection."""
        # Text-only should not support rich content
        assert not generator._supports_rich_content({ClientCapability.TEXT_ONLY})  # nosec B101

        # Cards should support rich content
        assert generator._supports_rich_content({ClientCapability.CARDS})  # nosec B101

        # Mixed capabilities should support rich content
        assert generator._supports_rich_content(  # nosec B101
            {ClientCapability.TEXT_ONLY, ClientCapability.IMAGES}
        )

    def test_get_content_type(self, generator: RichContentGenerator):
        """Test content type mapping."""
        assert generator._get_content_type("set_timer") == ContentType.CARD  # nosec B101
        assert generator._get_content_type("search_web") == ContentType.LIST  # nosec B101
        assert generator._get_content_type("play_music") == ContentType.MEDIA_PLAYER  # nosec B101
        assert generator._get_content_type("unknown_intent") is None  # nosec B101

    def test_supports_content_type(self, generator: RichContentGenerator):
        """Test content type support detection."""
        # Card requires CARDS capability
        assert generator._supports_content_type(ContentType.CARD, {ClientCapability.CARDS})  # nosec B101
        assert not generator._supports_content_type(ContentType.CARD, {ClientCapability.TEXT_ONLY})  # nosec B101

        # List requires LISTS capability
        assert generator._supports_content_type(ContentType.LIST, {ClientCapability.LISTS})  # nosec B101

        # Media player requires MEDIA capability
        assert generator._supports_content_type(ContentType.MEDIA_PLAYER, {ClientCapability.MEDIA})  # nosec B101

    def test_generate_list_content(self, generator: RichContentGenerator):
        """Test list content generation."""
        result = ExecutionResult(
            success=True,
            result_data={
                "title": "Search Results",
                "items": [
                    {"title": "Item 1", "subtitle": "Description 1"},
                    {"title": "Item 2", "subtitle": "Description 2"},
                    {"title": "Item 3", "subtitle": "Description 3"},
                ],
            },
            execution_time=0.1,
            action_id="action_789",
            tool_id="search_web",
        )
        intent = Mock()
        intent.intent_type = "search_web"
        intent.entities = {"query": "test"}
        intent.get_entity = lambda key, default=None: intent.entities.get(key, default)

        capabilities = {ClientCapability.LISTS}
        content = generator.generate(result, intent, capabilities)

        assert content["type"] == "list"  # nosec B101
        assert content["title"] == "Search Results"  # nosec B101
        assert len(content["items"]) == 3  # nosec B101
        assert content["items"][0]["title"] == "Item 1"  # nosec B101

    def test_generate_send_message_card(self, generator: RichContentGenerator):
        """Test send message card generation."""
        result = ExecutionResult(
            success=True,
            result_data={},
            execution_time=0.04,
            action_id="action_1515",
            tool_id="send_message",
        )
        intent = Mock()
        intent.intent_type = "send_message"
        intent.entities = {"recipient": "John"}
        intent.get_entity = lambda key, default=None: intent.entities.get(key, default)

        capabilities = {ClientCapability.CARDS, ClientCapability.BUTTONS}
        content = generator.generate(result, intent, capabilities)

        assert content["type"] == "card"  # nosec B101
        assert content["title"] == "Message Sent"  # nosec B101
        assert "John" in content["body"]  # nosec B101
        assert content["icon"] == "✉️"  # nosec B101
        assert len(content["buttons"]) == 2  # nosec B101

    def test_generate_default_card(self, generator: RichContentGenerator):
        """Test default card generation for unmapped intents."""
        result = ExecutionResult(
            success=True,
            result_data={"key": "value"},
            execution_time=0.05,
            action_id="action_808",
            tool_id="generic_tool",
        )
        intent = Mock()
        intent.intent_type = "unknown"  # Use unknown intent to trigger default card
        intent.entities = {}
        intent.get_entity = lambda key, default=None: default

        # Manually call _generate_card to test default behavior
        content = generator._generate_card(result, intent)

        assert content["type"] == "card"  # nosec B101
        assert content["title"] == "Action Complete"  # nosec B101
        assert "0.05s" in content["footer"]  # nosec B101

    def test_generate_list_with_string_items(self, generator: RichContentGenerator):
        """Test list generation with string items."""
        result = ExecutionResult(
            success=True,
            result_data={
                "title": "Items",
                "items": ["Item 1", "Item 2", "Item 3"],
            },
            execution_time=0.08,
            action_id="action_909",
            tool_id="list_items",
        )
        intent = Mock()
        intent.intent_type = "search_web"  # Use valid list intent
        intent.entities = {}
        intent.get_entity = lambda key, default=None: default

        capabilities = {ClientCapability.LISTS}
        content = generator.generate(result, intent, capabilities)

        assert content["type"] == "list"  # nosec B101
        assert len(content["items"]) == 3  # nosec B101
        assert content["items"][0]["title"] == "Item 1"  # nosec B101
        assert content["items"][0]["subtitle"] == ""  # nosec B101

    def test_generate_list_with_limit(self, generator: RichContentGenerator):
        """Test list generation respects item limit."""
        # Create 15 items (should be limited to 10)
        items = [{"title": f"Item {i}", "subtitle": f"Desc {i}"} for i in range(15)]
        result = ExecutionResult(
            success=True,
            result_data={"title": "Many Items", "items": items},
            execution_time=0.1,
            action_id="action_1010",
            tool_id="search_web",
        )
        intent = Mock()
        intent.intent_type = "search_web"
        intent.entities = {"query": "test"}
        intent.get_entity = lambda key, default=None: intent.entities.get(key, default)

        capabilities = {ClientCapability.LISTS}
        content = generator.generate(result, intent, capabilities)

        assert content["type"] == "list"  # nosec B101
        assert len(content["items"]) == 10  # Limited to 10  # nosec B101
        assert content["footer"] == "15 items"  # nosec B101


class TestClientCapability:
    """Test ClientCapability enum."""

    def test_capability_values(self):
        """Test capability enum values."""
        assert ClientCapability.TEXT_ONLY.value == "text_only"  # nosec B101
        assert ClientCapability.CARDS.value == "cards"  # nosec B101
        assert ClientCapability.IMAGES.value == "images"  # nosec B101
        assert ClientCapability.BUTTONS.value == "buttons"  # nosec B101

    def test_capability_membership(self):
        """Test capability set membership."""
        capabilities = {ClientCapability.CARDS, ClientCapability.BUTTONS}
        assert ClientCapability.CARDS in capabilities  # nosec B101
        assert ClientCapability.TEXT_ONLY not in capabilities  # nosec B101


class TestContentType:
    """Test ContentType enum."""

    def test_content_type_values(self):
        """Test content type enum values."""
        assert ContentType.CARD.value == "card"  # nosec B101
        assert ContentType.LIST.value == "list"  # nosec B101
        assert ContentType.CAROUSEL.value == "carousel"  # nosec B101
        assert ContentType.IMAGE.value == "image"  # nosec B101

    def test_content_type_membership(self):
        """Test content type comparison."""
        assert ContentType.CARD == ContentType.CARD  # nosec B101
        assert ContentType.CARD != ContentType.LIST  # nosec B101
