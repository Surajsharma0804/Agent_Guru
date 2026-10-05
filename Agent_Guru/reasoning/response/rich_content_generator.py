"""Rich Content Generator.

Generates structured data for UI cards, images, buttons, and interactive elements.
Adapts content format based on client capabilities.

Performance Requirements:
- Time Complexity: O(1) - constant time generation
- Space Complexity: O(1) - bounded content size
- Latency: <50ms target

Design:
- Intent-based content generation
- Client capability detection
- Structured data formats (cards, lists, media)
- Interactive elements (buttons, quick replies)
- Fallback to text-only for limited clients
"""

from enum import Enum
from typing import Any

from Agent_Guru.reasoning.config.logging import get_logger
from Agent_Guru.reasoning.models.intent import Intent
from Agent_Guru.reasoning.models.result import ExecutionResult

logger = get_logger(__name__)


class ClientCapability(str, Enum):
    """Client capability types."""

    TEXT_ONLY = "text_only"  # Basic text only
    RICH_TEXT = "rich_text"  # Formatted text (bold, italic, etc.)
    CARDS = "cards"  # UI cards with title, body, footer
    IMAGES = "images"  # Image display
    BUTTONS = "buttons"  # Interactive buttons
    QUICK_REPLIES = "quick_replies"  # Quick reply chips
    LISTS = "lists"  # Structured lists
    MEDIA = "media"  # Audio/video playback
    FORMS = "forms"  # Input forms
    MAPS = "maps"  # Map display
    CHARTS = "charts"  # Data visualization


class ContentType(str, Enum):
    """Rich content types."""

    CARD = "card"  # Basic card
    LIST = "list"  # List of items
    CAROUSEL = "carousel"  # Horizontal scrolling cards
    IMAGE = "image"  # Single image
    GALLERY = "gallery"  # Image gallery
    BUTTON_GROUP = "button_group"  # Group of buttons
    QUICK_REPLY = "quick_reply"  # Quick reply chips
    MEDIA_PLAYER = "media_player"  # Audio/video player
    FORM = "form"  # Input form
    MAP = "map"  # Map view
    CHART = "chart"  # Data chart
    TABLE = "table"  # Data table


class RichContentGenerator:
    """Generates rich content for visual interfaces.

    Time Complexity: O(1) - constant time generation
    Space Complexity: O(1) - bounded content size
    Latency Target: <50ms

    Example:
        >>> generator = RichContentGenerator()
        >>> result = ExecutionResult(success=True, result_data={"timer": "5 minutes"})
        >>> intent = Intent(intent_type="set_timer", entities={"duration": "5 minutes"})
        >>> capabilities = {ClientCapability.CARDS, ClientCapability.BUTTONS}
        >>> content = generator.generate(result, intent, capabilities)
        >>> print(content["type"])
        "card"

    """

    # Intent to content type mapping
    INTENT_CONTENT_MAP: dict[str, ContentType] = {
        # Timer intents
        "set_timer": ContentType.CARD,
        "cancel_timer": ContentType.CARD,
        "list_timers": ContentType.LIST,
        # Weather intents
        "query_weather": ContentType.CARD,
        "weather_forecast": ContentType.CAROUSEL,
        # Music intents
        "play_music": ContentType.MEDIA_PLAYER,
        "search_music": ContentType.LIST,
        # Message intents
        "send_message": ContentType.CARD,
        "read_messages": ContentType.LIST,
        # Calendar intents
        "create_event": ContentType.CARD,
        "list_events": ContentType.LIST,
        "show_calendar": ContentType.TABLE,
        # Smart home intents
        "control_device": ContentType.CARD,
        "list_devices": ContentType.LIST,
        # Search intents
        "search_web": ContentType.LIST,
        "show_results": ContentType.CAROUSEL,
        # Navigation intents
        "navigate_to": ContentType.MAP,
        "show_directions": ContentType.MAP,
        # Photo intents
        "show_photos": ContentType.GALLERY,
        "take_photo": ContentType.IMAGE,
        # Data intents
        "show_stats": ContentType.CHART,
        "show_report": ContentType.TABLE,
        # Interactive intents.
        # _generate_button_group(), _generate_quick_reply() and
        # _generate_form() were all implemented and unit-tested by calling
        # them directly, but no map entry selected them -- so BUTTON_GROUP,
        # QUICK_REPLY and FORM were the three ContentTypes that generate()
        # could never produce. The map is what makes them reachable.
        "show_options": ContentType.BUTTON_GROUP,
        "show_replies": ContentType.QUICK_REPLY,
        "show_form": ContentType.FORM,
    }

    def __init__(self) -> None:
        """Initialize rich content generator."""
        logger.info("RichContentGenerator initialized")

    def generate(
        self,
        result: ExecutionResult,
        intent: Intent,
        client_capabilities: set[ClientCapability] | None = None,
    ) -> dict[str, Any] | None:
        """Generate rich content based on execution result and intent.

        Time Complexity: O(1) - constant time
        Space Complexity: O(1) - bounded content size

        Args:
            result: Execution result
            intent: User intent
            client_capabilities: Set of client capabilities (None = all capabilities)

        Returns:
            Rich content dictionary or None if not applicable

        """
        # Default to all capabilities if not specified
        if client_capabilities is None:
            client_capabilities = set(ClientCapability)

        # Check if client supports rich content
        if not self._supports_rich_content(client_capabilities):
            logger.debug(
                "Client does not support rich content",
                extra={"capabilities": [c.value for c in client_capabilities]},
            )
            return None

        # Get intent type as string
        intent_type = (
            intent.intent_type if hasattr(intent.intent_type, "value") else str(intent.intent_type)
        )
        if hasattr(intent_type, "value"):
            intent_type = intent_type.value

        # Determine content type for intent
        content_type = self._get_content_type(intent_type)
        if not content_type:
            logger.debug(
                "No rich content mapping for intent",
                extra={"intent_type": intent_type},
            )
            return None

        # Check if client supports this content type
        if not self._supports_content_type(content_type, client_capabilities):
            logger.debug(
                "Client does not support content type",
                extra={
                    "content_type": content_type.value,
                    "capabilities": [c.value for c in client_capabilities],
                },
            )
            return None

        # Generate content based on type
        content = self._generate_content(content_type, result, intent)

        logger.info(
            "Rich content generated",
            extra={
                "content_type": content_type.value,
                "intent_type": intent_type,
                "has_buttons": "buttons" in content,
                "has_image": "image" in content,
            },
        )

        return content

    def _supports_rich_content(self, capabilities: set[ClientCapability]) -> bool:
        """Check if client supports any rich content.

        Args:
            capabilities: Client capabilities

        Returns:
            True if client supports rich content

        """
        rich_capabilities = {
            ClientCapability.RICH_TEXT,
            ClientCapability.CARDS,
            ClientCapability.IMAGES,
            ClientCapability.BUTTONS,
            ClientCapability.QUICK_REPLIES,
            ClientCapability.LISTS,
            ClientCapability.MEDIA,
            ClientCapability.FORMS,
            ClientCapability.MAPS,
            ClientCapability.CHARTS,
        }
        return bool(capabilities & rich_capabilities)

    def _get_content_type(self, intent_type: str) -> ContentType | None:
        """Get content type for intent.

        Args:
            intent_type: Intent type (can be string or IntentType enum)

        Returns:
            Content type or None

        """
        # Convert enum to string if needed
        if hasattr(intent_type, "value"):
            intent_type = intent_type.value
        return self.INTENT_CONTENT_MAP.get(intent_type)

    def _supports_content_type(
        self,
        content_type: ContentType,
        capabilities: set[ClientCapability],
    ) -> bool:
        """Check if client supports content type.

        Args:
            content_type: Content type
            capabilities: Client capabilities

        Returns:
            True if supported

        """
        # Map content types to required capabilities
        requirements = {
            ContentType.CARD: {ClientCapability.CARDS},
            ContentType.LIST: {ClientCapability.LISTS},
            ContentType.CAROUSEL: {ClientCapability.CARDS},
            ContentType.IMAGE: {ClientCapability.IMAGES},
            ContentType.GALLERY: {ClientCapability.IMAGES},
            ContentType.BUTTON_GROUP: {ClientCapability.BUTTONS},
            ContentType.QUICK_REPLY: {ClientCapability.QUICK_REPLIES},
            ContentType.MEDIA_PLAYER: {ClientCapability.MEDIA},
            ContentType.FORM: {ClientCapability.FORMS},
            ContentType.MAP: {ClientCapability.MAPS},
            ContentType.CHART: {ClientCapability.CHARTS},
            ContentType.TABLE: {ClientCapability.RICH_TEXT},
        }

        required = requirements.get(content_type, set())
        return bool(required & capabilities)

    def _generate_content(
        self,
        content_type: ContentType,
        result: ExecutionResult,
        intent: Intent,
    ) -> dict[str, Any]:
        """Generate content based on type.

        Args:
            content_type: Content type
            result: Execution result
            intent: User intent

        Returns:
            Content dictionary

        """
        # Dispatch to specific generator
        generators = {
            ContentType.CARD: self._generate_card,
            ContentType.LIST: self._generate_list,
            ContentType.CAROUSEL: self._generate_carousel,
            ContentType.IMAGE: self._generate_image,
            ContentType.GALLERY: self._generate_gallery,
            ContentType.BUTTON_GROUP: self._generate_button_group,
            ContentType.QUICK_REPLY: self._generate_quick_reply,
            ContentType.MEDIA_PLAYER: self._generate_media_player,
            ContentType.FORM: self._generate_form,
            ContentType.MAP: self._generate_map,
            ContentType.CHART: self._generate_chart,
            ContentType.TABLE: self._generate_table,
        }

        generator = generators.get(content_type, self._generate_card)
        return generator(result, intent)

    def _generate_card(self, result: ExecutionResult, intent: Intent) -> dict[str, Any]:
        """Generate card content.

        Args:
            result: Execution result
            intent: User intent

        Returns:
            Card content

        """
        # Extract data from result
        data = result.result_data or {}

        # Get intent type as string
        intent_type = (
            intent.intent_type if hasattr(intent.intent_type, "value") else str(intent.intent_type)
        )

        # Generate card based on intent
        if intent_type == "set_timer":
            duration = (
                intent.get_entity("duration", "unknown")
                if hasattr(intent, "get_entity")
                else intent.entities.get("duration", "unknown")
            )
            if hasattr(duration, "value"):
                duration = duration.value
            if isinstance(duration, int) and not isinstance(duration, bool):
                # Duration entities hold whole seconds (utils.duration); shown
                # as they were, the card read "Timer for 300 is now active".
                from Agent_Guru.utils.duration import describe_duration

                duration = describe_duration(duration)
            return {
                "type": "card",
                "title": "Timer Set",
                "body": f"Timer for {duration} is now active",
                "footer": "Say 'cancel timer' to stop",
                "icon": "⏱️",
                "buttons": [
                    {"label": "Cancel Timer", "action": "cancel_timer"},
                    {"label": "Add Another", "action": "set_timer"},
                ],
            }

        if intent_type == "query_weather":
            location = (
                intent.get_entity("location", "your location")
                if hasattr(intent, "get_entity")
                else intent.entities.get("location", "your location")
            )
            if hasattr(location, "value"):
                location = location.value
            temp = data.get("temperature", "N/A")
            condition = data.get("condition", "N/A")
            return {
                "type": "card",
                "title": f"Weather in {location}",
                "body": f"{temp}°F, {condition}",
                "footer": "Updated just now",
                "image": data.get("icon_url"),
                "buttons": [
                    {"label": "7-Day Forecast", "action": "weather_forecast"},
                    {"label": "Hourly", "action": "hourly_weather"},
                ],
            }

        if intent_type == "send_message":
            recipient = (
                intent.get_entity("recipient", "contact")
                if hasattr(intent, "get_entity")
                else intent.entities.get("recipient", "contact")
            )
            if hasattr(recipient, "value"):
                recipient = recipient.value
            return {
                "type": "card",
                "title": "Message Sent",
                "body": f"Your message to {recipient} was delivered",
                "footer": "Sent just now",
                "icon": "✉️",
                "buttons": [
                    {"label": "Send Another", "action": "send_message"},
                    {"label": "View Conversation", "action": "view_messages"},
                ],
            }

        # Default card
        return {
            "type": "card",
            "title": "Action Complete" if result.success else "Action Failed",
            "body": str(data) if data else "No additional information",
            "footer": f"Completed in {result.execution_time:.2f}s",
        }

    def _generate_list(self, result: ExecutionResult, intent: Intent) -> dict[str, Any]:
        """Generate list content.

        Args:
            result: Execution result
            intent: User intent

        Returns:
            List content

        """
        data = result.result_data or {}

        # Extract items from result
        items = data.get("items", [])
        if not isinstance(items, list):
            items = [items]

        # Format items
        formatted_items = []
        for item in items[:10]:  # Limit to 10 items
            if isinstance(item, dict):
                formatted_items.append(
                    {
                        "title": item.get("title", str(item)),
                        "subtitle": item.get("subtitle", ""),
                        "icon": item.get("icon"),
                        "action": item.get("action"),
                    },
                )
            else:
                formatted_items.append(
                    {
                        "title": str(item),
                        "subtitle": "",
                    },
                )

        return {
            "type": "list",
            "title": data.get("title", "Results"),
            "items": formatted_items,
            "footer": f"{len(items)} items" if len(items) > 10 else None,
        }

    def _generate_carousel(self, result: ExecutionResult, intent: Intent) -> dict[str, Any]:
        """Generate carousel content.

        Args:
            result: Execution result
            intent: User intent

        Returns:
            Carousel content

        """
        data = result.result_data or {}
        items = data.get("items", [])

        # Generate cards for carousel
        cards = []
        for item in items[:5]:  # Limit to 5 cards
            if isinstance(item, dict):
                cards.append(
                    {
                        "title": item.get("title", ""),
                        "body": item.get("body", ""),
                        "image": item.get("image"),
                        "buttons": item.get("buttons", []),
                    },
                )

        return {
            "type": "carousel",
            "cards": cards,
        }

    def _generate_image(self, result: ExecutionResult, intent: Intent) -> dict[str, Any]:
        """Generate image content.

        Args:
            result: Execution result
            intent: User intent

        Returns:
            Image content

        """
        data = result.result_data or {}

        return {
            "type": "image",
            "url": data.get("image_url", ""),
            "alt_text": data.get("alt_text", "Image"),
            "caption": data.get("caption"),
            "thumbnail_url": data.get("thumbnail_url"),
        }

    def _generate_gallery(self, result: ExecutionResult, intent: Intent) -> dict[str, Any]:
        """Generate gallery content.

        Args:
            result: Execution result
            intent: User intent

        Returns:
            Gallery content

        """
        data = result.result_data or {}
        images = data.get("images", [])

        return {
            "type": "gallery",
            "images": [
                {
                    "url": img.get("url", "") if isinstance(img, dict) else img,
                    "thumbnail_url": img.get("thumbnail_url") if isinstance(img, dict) else None,
                    "caption": img.get("caption") if isinstance(img, dict) else None,
                }
                for img in images[:20]  # Limit to 20 images
            ],
        }

    def _generate_button_group(self, result: ExecutionResult, intent: Intent) -> dict[str, Any]:
        """Generate button group content.

        Args:
            result: Execution result
            intent: User intent

        Returns:
            Button group content

        """
        data = result.result_data or {}
        buttons = data.get("buttons", [])

        return {
            "type": "button_group",
            "buttons": [
                {
                    "label": btn.get("label", "") if isinstance(btn, dict) else str(btn),
                    "action": btn.get("action") if isinstance(btn, dict) else None,
                    "style": btn.get("style", "default") if isinstance(btn, dict) else "default",
                }
                for btn in buttons[:6]  # Limit to 6 buttons
            ],
        }

    def _generate_quick_reply(self, result: ExecutionResult, intent: Intent) -> dict[str, Any]:
        """Generate quick reply content.

        Args:
            result: Execution result
            intent: User intent

        Returns:
            Quick reply content

        """
        data = result.result_data or {}
        replies = data.get("quick_replies", [])

        return {
            "type": "quick_reply",
            "replies": [
                {
                    "text": reply.get("text", "") if isinstance(reply, dict) else str(reply),
                    "action": reply.get("action") if isinstance(reply, dict) else None,
                }
                for reply in replies[:8]  # Limit to 8 quick replies
            ],
        }

    def _generate_media_player(self, result: ExecutionResult, intent: Intent) -> dict[str, Any]:
        """Generate media player content.

        Args:
            result: Execution result
            intent: User intent

        Returns:
            Media player content

        """
        data = result.result_data or {}

        return {
            "type": "media_player",
            "media_url": data.get("media_url", ""),
            "media_type": data.get("media_type", "audio"),  # audio or video
            "title": data.get("title", ""),
            "artist": data.get("artist"),
            "album": data.get("album"),
            "thumbnail_url": data.get("thumbnail_url"),
            "duration": data.get("duration"),
            "controls": ["play", "pause", "skip", "previous"],
        }

    def _generate_form(self, result: ExecutionResult, intent: Intent) -> dict[str, Any]:
        """Generate form content.

        Args:
            result: Execution result
            intent: User intent

        Returns:
            Form content

        """
        data = result.result_data or {}
        fields = data.get("fields", [])

        return {
            "type": "form",
            "title": data.get("title", "Form"),
            "fields": [
                {
                    "name": field.get("name", ""),
                    "label": field.get("label", ""),
                    "type": field.get("type", "text"),  # text, number, date, select, etc.
                    "required": field.get("required", False),
                    "placeholder": field.get("placeholder"),
                    "options": field.get("options"),  # For select fields
                }
                for field in fields
            ],
            "submit_label": data.get("submit_label", "Submit"),
            "cancel_label": data.get("cancel_label", "Cancel"),
        }

    def _generate_map(self, result: ExecutionResult, intent: Intent) -> dict[str, Any]:
        """Generate map content.

        Args:
            result: Execution result
            intent: User intent

        Returns:
            Map content

        """
        data = result.result_data or {}

        return {
            "type": "map",
            "center": {
                "latitude": data.get("latitude", 0.0),
                "longitude": data.get("longitude", 0.0),
            },
            "zoom": data.get("zoom", 15),
            "markers": data.get("markers", []),
            "route": data.get("route"),  # Optional route polyline
            "title": data.get("title"),
        }

    def _generate_chart(self, result: ExecutionResult, intent: Intent) -> dict[str, Any]:
        """Generate chart content.

        Args:
            result: Execution result
            intent: User intent

        Returns:
            Chart content

        """
        data = result.result_data or {}

        return {
            "type": "chart",
            "chart_type": data.get("chart_type", "line"),  # line, bar, pie, etc.
            "title": data.get("title", "Chart"),
            "data": data.get("data", []),
            "labels": data.get("labels", []),
            "x_axis_label": data.get("x_axis_label"),
            "y_axis_label": data.get("y_axis_label"),
        }

    def _generate_table(self, result: ExecutionResult, intent: Intent) -> dict[str, Any]:
        """Generate table content.

        Args:
            result: Execution result
            intent: User intent

        Returns:
            Table content

        """
        data = result.result_data or {}

        return {
            "type": "table",
            "title": data.get("title", "Table"),
            "headers": data.get("headers", []),
            "rows": data.get("rows", []),
            "footer": data.get("footer"),
        }
