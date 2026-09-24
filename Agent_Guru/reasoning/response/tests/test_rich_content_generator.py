"""
Tests for Rich Content Generator

Coverage Target: >80%
"""

import pytest

from Agent_Guru.reasoning.models.intent import Entity, Intent
from Agent_Guru.reasoning.models.result import ExecutionResult
from Agent_Guru.reasoning.response.rich_content_generator import (


    ClientCapability,
    ContentType,
    RichContentGenerator,
)


def _entities(**values: object) -> dict[str, Entity]:
    """Build the Entity-valued mapping Intent.entities requires.

    Intent.entities is ``dict[str, Entity]`` (reasoning/models/intent.py), not
    ``dict[str, str]``. These tests still passed raw strings, so every Intent
    they built died in the pydantic constructor with "Input should be a valid
    dictionary or instance of Entity" before the code under test ran -- a
    failure that said nothing about the behaviour being tested.

    The raw text is carried through unchanged, so any assertion that looks for
    an entity's value still sees exactly the same string it saw before.
    """
    return {
        name: Entity(entity_type=name, value=value, raw_text=str(value))
        for name, value in values.items()
    }



class TestRichContentGenerator:
    """Unit tests for RichContentGenerator."""

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
    def timer_intent(self) -> Intent:
        """Create timer intent."""
        return Intent(
            intent_type="set_timer",
            original_input="test input for set_timer",
            entities=_entities(duration="5 minutes"),
            confidence=0.95,
            requires_reasoning=False,
        )

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
    def weather_intent(self) -> Intent:
        """Create weather intent."""
        return Intent(
            intent_type="query_weather",
            original_input="test input for query_weather",
            entities=_entities(location="San Francisco"),
            confidence=0.92,
            requires_reasoning=False,
        )

    def test_initialization(self, generator: RichContentGenerator):
        """Test generator initialization."""
        assert generator is not None  # nosec B101
        assert isinstance(generator.INTENT_CONTENT_MAP, dict)  # nosec B101
        assert len(generator.INTENT_CONTENT_MAP) > 0  # nosec B101

    def test_generate_with_no_capabilities(
        self, generator: RichContentGenerator, timer_result: ExecutionResult, timer_intent: Intent
    ):
        """Test generation with text-only client."""
        capabilities = {ClientCapability.TEXT_ONLY}
        content = generator.generate(timer_result, timer_intent, capabilities)

        # Should return None for text-only clients
        assert content is None  # nosec B101

    def test_generate_with_card_capability(
        self, generator: RichContentGenerator, timer_result: ExecutionResult, timer_intent: Intent
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
        self, generator: RichContentGenerator, timer_result: ExecutionResult, timer_intent: Intent
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
        self,
        generator: RichContentGenerator,
        weather_result: ExecutionResult,
        weather_intent: Intent,
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
        intent = Intent(
            intent_type="search_web",
            original_input="test input for search_web",
            entities=_entities(query="test"),
            confidence=0.9,
            requires_reasoning=False,
        )
        capabilities = {ClientCapability.LISTS}

        content = generator.generate(result, intent, capabilities)

        assert content["type"] == "list"  # nosec B101
        assert content["title"] == "Search Results"  # nosec B101
        assert len(content["items"]) == 3  # nosec B101
        assert content["items"][0]["title"] == "Item 1"  # nosec B101

    def test_generate_carousel_content(self, generator: RichContentGenerator):
        """Test carousel content generation."""
        result = ExecutionResult(
            success=True,
            result_data={
                "items": [
                    {"title": "Day 1", "body": "Sunny, 75°F", "image": "day1.png"},
                    {"title": "Day 2", "body": "Cloudy, 70°F", "image": "day2.png"},
                ],
            },
            execution_time=0.12,
            action_id="action_101",
            tool_id="weather_forecast",
        )
        intent = Intent(
            intent_type="weather_forecast",
            original_input="test input for weather_forecast",
            entities=_entities(location="Seattle"),
            confidence=0.88,
            requires_reasoning=False,
        )
        capabilities = {ClientCapability.CARDS}

        content = generator.generate(result, intent, capabilities)

        assert content["type"] == "carousel"  # nosec B101
        assert len(content["cards"]) == 2  # nosec B101
        assert content["cards"][0]["title"] == "Day 1"  # nosec B101

    def test_generate_image_content(self, generator: RichContentGenerator):
        """Test image content generation."""
        result = ExecutionResult(
            success=True,
            result_data={
                "image_url": "https://example.com/photo.jpg",
                "alt_text": "Beautiful sunset",
                "caption": "Sunset at the beach",
            },
            execution_time=0.08,
            action_id="action_202",
            tool_id="take_photo",
        )
        intent = Intent(
            intent_type="take_photo",
            original_input="test input for take_photo",
            entities={},
            confidence=0.95,
            requires_reasoning=False,
        )
        capabilities = {ClientCapability.IMAGES}

        content = generator.generate(result, intent, capabilities)

        assert content["type"] == "image"  # nosec B101
        assert content["url"] == "https://example.com/photo.jpg"  # nosec B101
        assert content["alt_text"] == "Beautiful sunset"  # nosec B101
        assert content["caption"] == "Sunset at the beach"  # nosec B101

    def test_generate_media_player_content(self, generator: RichContentGenerator):
        """Test media player content generation."""
        result = ExecutionResult(
            success=True,
            result_data={
                "media_url": "https://example.com/song.mp3",
                "media_type": "audio",
                "title": "Great Song",
                "artist": "Famous Artist",
                "album": "Best Album",
                "duration": 240,
            },
            execution_time=0.06,
            action_id="action_303",
            tool_id="play_music",
        )
        intent = Intent(
            intent_type="play_music",
            original_input="test input for play_music",
            entities=_entities(song="Great Song"),
            confidence=0.93,
            requires_reasoning=False,
        )
        capabilities = {ClientCapability.MEDIA}

        content = generator.generate(result, intent, capabilities)

        assert content["type"] == "media_player"  # nosec B101
        assert content["media_url"] == "https://example.com/song.mp3"  # nosec B101
        assert content["media_type"] == "audio"  # nosec B101
        assert content["title"] == "Great Song"  # nosec B101
        assert content["artist"] == "Famous Artist"  # nosec B101
        assert "play" in content["controls"]  # nosec B101

    def test_generate_map_content(self, generator: RichContentGenerator):
        """Test map content generation."""
        result = ExecutionResult(
            success=True,
            result_data={
                "latitude": 37.7749,
                "longitude": -122.4194,
                "zoom": 15,
                "title": "San Francisco",
                "markers": [{"lat": 37.7749, "lng": -122.4194, "label": "SF"}],
            },
            execution_time=0.11,
            action_id="action_404",
            tool_id="navigate_to",
        )
        intent = Intent(
            intent_type="navigate_to",
            original_input="test input for navigate_to",
            entities=_entities(destination="San Francisco"),
            confidence=0.91,
            requires_reasoning=False,
        )
        capabilities = {ClientCapability.MAPS}

        content = generator.generate(result, intent, capabilities)

        assert content["type"] == "map"  # nosec B101
        assert content["center"]["latitude"] == 37.7749  # nosec B101
        assert content["center"]["longitude"] == -122.4194  # nosec B101
        assert content["zoom"] == 15  # nosec B101
        assert len(content["markers"]) == 1  # nosec B101

    def test_generate_chart_content(self, generator: RichContentGenerator):
        """Test chart content generation."""
        result = ExecutionResult(
            success=True,
            result_data={
                "chart_type": "line",
                "title": "Temperature Trend",
                "data": [65, 68, 72, 70, 75],
                "labels": ["Mon", "Tue", "Wed", "Thu", "Fri"],
                "y_axis_label": "Temperature (°F)",
            },
            execution_time=0.09,
            action_id="action_505",
            tool_id="show_stats",
        )
        intent = Intent(
            intent_type="show_stats",
            original_input="test input for show_stats",
            entities=_entities(metric="temperature"),
            confidence=0.87,
            requires_reasoning=False,
        )
        capabilities = {ClientCapability.CHARTS}

        content = generator.generate(result, intent, capabilities)

        assert content["type"] == "chart"  # nosec B101
        assert content["chart_type"] == "line"  # nosec B101
        assert content["title"] == "Temperature Trend"  # nosec B101
        assert len(content["data"]) == 5  # nosec B101
        assert len(content["labels"]) == 5  # nosec B101

    def test_generate_table_content(self, generator: RichContentGenerator):
        """Test table content generation."""
        result = ExecutionResult(
            success=True,
            result_data={
                "title": "Event Schedule",
                "headers": ["Time", "Event", "Location"],
                "rows": [
                    ["9:00 AM", "Meeting", "Room A"],
                    ["2:00 PM", "Presentation", "Room B"],
                ],
            },
            execution_time=0.07,
            action_id="action_606",
            tool_id="show_calendar",
        )
        intent = Intent(
            intent_type="show_calendar",
            original_input="test input for show_calendar",
            entities={},
            confidence=0.89,
            requires_reasoning=False,
        )
        capabilities = {ClientCapability.RICH_TEXT}

        content = generator.generate(result, intent, capabilities)

        assert content["type"] == "table"  # nosec B101
        assert content["title"] == "Event Schedule"  # nosec B101
        assert len(content["headers"]) == 3  # nosec B101
        assert len(content["rows"]) == 2  # nosec B101

    def test_generate_with_unknown_intent(self, generator: RichContentGenerator):
        """Test generation with unknown intent."""
        result = ExecutionResult(
            success=True,
            result_data={"result": "success"},
            execution_time=0.05,
            action_id="action_707",
            tool_id="unknown_tool",
        )
        intent = Intent(
            intent_type="unknown",
            original_input="test input for unknown",
            entities={},
            confidence=0.5,
            requires_reasoning=False,
        )
        capabilities = {ClientCapability.CARDS}

        content = generator.generate(result, intent, capabilities)

        # Should return None for unmapped intents
        assert content is None  # nosec B101

    def test_generate_with_all_capabilities(
        self, generator: RichContentGenerator, timer_result: ExecutionResult, timer_intent: Intent
    ):
        """Test generation with all capabilities."""
        capabilities = set(ClientCapability)
        content = generator.generate(timer_result, timer_intent, capabilities)

        assert content is not None  # nosec B101
        assert content["type"] == "card"  # nosec B101

    def test_generate_with_none_capabilities(
        self, generator: RichContentGenerator, timer_result: ExecutionResult, timer_intent: Intent
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
        assert generator._get_content_type("list_timers") == ContentType.LIST  # nosec B101
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

    def test_generate_default_card(self, generator: RichContentGenerator):
        """Test default card generation for unmapped intents."""
        result = ExecutionResult(
            success=True,
            result_data={"key": "value"},
            execution_time=0.05,
            action_id="action_808",
            tool_id="generic_tool",
        )
        intent = Intent(
            intent_type="unknown",
            original_input="test input for unknown",
            entities={},
            confidence=0.8,
            requires_reasoning=False,
        )

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
        intent = Intent(
            intent_type="list_timers",
            original_input="test input for list_timers",
            entities={},
            confidence=0.9,
            requires_reasoning=False,
        )
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
        intent = Intent(
            intent_type="search_web",
            original_input="test input for search_web",
            entities=_entities(query="test"),
            confidence=0.9,
            requires_reasoning=False,
        )
        capabilities = {ClientCapability.LISTS}

        content = generator.generate(result, intent, capabilities)

        assert content["type"] == "list"  # nosec B101
        assert len(content["items"]) == 10  # Limited to 10  # nosec B101
        assert content["footer"] == "15 items"  # nosec B101

    def test_generate_gallery_with_limit(self, generator: RichContentGenerator):
        """Test gallery generation respects image limit."""
        # Create 25 images (should be limited to 20)
        images = [f"https://example.com/img{i}.jpg" for i in range(25)]
        result = ExecutionResult(
            success=True,
            result_data={"images": images},
            execution_time=0.12,
            action_id="action_1111",
            tool_id="show_photos",
        )
        intent = Intent(
            intent_type="show_photos",
            original_input="test input for show_photos",
            entities={},
            confidence=0.92,
            requires_reasoning=False,
        )
        capabilities = {ClientCapability.IMAGES}

        content = generator.generate(result, intent, capabilities)

        assert content["type"] == "gallery"  # nosec B101
        assert len(content["images"]) == 20  # Limited to 20  # nosec B101

    def test_generate_button_group_with_limit(self, generator: RichContentGenerator):
        """Test button group generation respects button limit."""
        # Create 10 buttons (should be limited to 6)
        buttons = [{"label": f"Button {i}", "action": f"action_{i}"} for i in range(10)]
        result = ExecutionResult(
            success=True,
            result_data={"buttons": buttons},
            execution_time=0.06,
            action_id="action_1212",
            tool_id="show_options",
        )
        intent = Intent(
            intent_type="show_options",
            original_input="test input for show_options",
            entities={},
            confidence=0.85,
            requires_reasoning=False,
        )

        # Manually call _generate_button_group
        content = generator._generate_button_group(result, intent)

        assert content["type"] == "button_group"  # nosec B101
        assert len(content["buttons"]) == 6  # Limited to 6  # nosec B101

    def test_generate_quick_reply_with_limit(self, generator: RichContentGenerator):
        """Test quick reply generation respects reply limit."""
        # Create 12 replies (should be limited to 8)
        replies = [{"text": f"Reply {i}", "action": f"action_{i}"} for i in range(12)]
        result = ExecutionResult(
            success=True,
            result_data={"quick_replies": replies},
            execution_time=0.05,
            action_id="action_1313",
            tool_id="show_replies",
        )
        intent = Intent(
            intent_type="show_replies",
            original_input="test input for show_replies",
            entities={},
            confidence=0.88,
            requires_reasoning=False,
        )

        # Manually call _generate_quick_reply
        content = generator._generate_quick_reply(result, intent)

        assert content["type"] == "quick_reply"  # nosec B101
        assert len(content["replies"]) == 8  # Limited to 8  # nosec B101

    def test_generate_form_content(self, generator: RichContentGenerator):
        """Test form content generation."""
        result = ExecutionResult(
            success=True,
            result_data={
                "title": "Contact Form",
                "fields": [
                    {
                        "name": "name",
                        "label": "Your Name",
                        "type": "text",
                        "required": True,
                        "placeholder": "Enter your name",
                    },
                    {
                        "name": "email",
                        "label": "Email",
                        "type": "text",
                        "required": True,
                    },
                ],
                "submit_label": "Send",
                "cancel_label": "Cancel",
            },
            execution_time=0.07,
            action_id="action_1414",
            tool_id="show_form",
        )
        intent = Intent(
            intent_type="show_form",
            original_input="test input for show_form",
            entities={},
            confidence=0.86,
            requires_reasoning=False,
        )

        # Manually call _generate_form
        content = generator._generate_form(result, intent)

        assert content["type"] == "form"  # nosec B101
        assert content["title"] == "Contact Form"  # nosec B101
        assert len(content["fields"]) == 2  # nosec B101
        assert content["fields"][0]["name"] == "name"  # nosec B101
        assert content["fields"][0]["required"] is True  # nosec B101
        assert content["submit_label"] == "Send"  # nosec B101

    def test_generate_send_message_card(self, generator: RichContentGenerator):
        """Test send message card generation."""
        result = ExecutionResult(
            success=True,
            result_data={},
            execution_time=0.04,
            action_id="action_1515",
            tool_id="send_message",
        )
        intent = Intent(
            intent_type="send_message",
            original_input="test input for send_message",
            entities=_entities(recipient="John"),
            confidence=0.94,
            requires_reasoning=False,
        )
        capabilities = {ClientCapability.CARDS, ClientCapability.BUTTONS}

        content = generator.generate(result, intent, capabilities)

        assert content["type"] == "card"  # nosec B101
        assert content["title"] == "Message Sent"  # nosec B101
        assert "John" in content["body"]  # nosec B101
        assert content["icon"] == "✉️"  # nosec B101
        assert len(content["buttons"]) == 2  # nosec B101

    def test_generate_carousel_with_limit(self, generator: RichContentGenerator):
        """Test carousel generation respects card limit."""
        # Create 10 cards (should be limited to 5)
        items = [{"title": f"Card {i}", "body": f"Body {i}"} for i in range(10)]
        result = ExecutionResult(
            success=True,
            result_data={"items": items},
            execution_time=0.11,
            action_id="action_1616",
            tool_id="weather_forecast",
        )
        intent = Intent(
            intent_type="weather_forecast",
            original_input="test input for weather_forecast",
            entities={},
            confidence=0.9,
            requires_reasoning=False,
        )
        capabilities = {ClientCapability.CARDS}

        content = generator.generate(result, intent, capabilities)

        assert content["type"] == "carousel"  # nosec B101
        assert len(content["cards"]) == 5  # Limited to 5  # nosec B101


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
