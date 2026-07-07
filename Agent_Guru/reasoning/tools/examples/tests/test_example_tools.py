"""
Tests for example tools.
"""


from Agent_Guru.reasoning.tools.examples.timer_tool import SetTimerTool, CancelTimerTool
from Agent_Guru.reasoning.tools.examples.weather_tool import WeatherTool
from Agent_Guru.reasoning.tools.examples.messaging_tool import MessagingTool
from Agent_Guru.reasoning.tools.examples.music_tool import MusicTool
from Agent_Guru.reasoning.tools.examples.calendar_tool import CalendarTool


class TestTimerTools:
    """Tests for timer tools."""

    async def test_set_timer_success(self) -> None:
        """Test setting a timer successfully."""
        tool = SetTimerTool()
        result = await tool.execute(duration_seconds=300, label="Cooking")

        assert result["success"] is True  # nosec B101
        assert result["result"]["duration_seconds"] == 300  # nosec B101
        assert result["result"]["label"] == "Cooking"  # nosec B101
        assert "timer_id" in result["result"]  # nosec B101
        assert "expiration_time" in result["result"]  # nosec B101

    async def test_set_timer_default_label(self) -> None:
        """Test setting a timer with default label."""
        tool = SetTimerTool()
        result = await tool.execute(duration_seconds=60)

        assert result["success"] is True  # nosec B101
        assert result["result"]["label"] == "Timer"  # nosec B101

    async def test_set_timer_negative_duration(self) -> None:
        """Test setting a timer with negative duration fails."""
        tool = SetTimerTool()
        result = await tool.execute(duration_seconds=-10)

        assert result["success"] is False  # nosec B101
        assert "positive" in result["error"]  # nosec B101

    async def test_set_timer_exceeds_max_duration(self) -> None:
        """Test setting a timer exceeding 24 hours fails."""
        tool = SetTimerTool()
        result = await tool.execute(duration_seconds=90000)  # > 24 hours

        assert result["success"] is False  # nosec B101
        assert "24 hours" in result["error"]  # nosec B101

    async def test_cancel_timer_success(self) -> None:
        """Test canceling a timer successfully."""
        tool = CancelTimerTool()
        result = await tool.execute(timer_id="timer_12345")

        assert result["success"] is True  # nosec B101
        assert result["result"]["timer_id"] == "timer_12345"  # nosec B101

    async def test_cancel_timer_invalid_id(self) -> None:
        """Test canceling a timer with invalid ID fails."""
        tool = CancelTimerTool()
        result = await tool.execute(timer_id="invalid_id")

        assert result["success"] is False  # nosec B101
        assert "Invalid timer ID" in result["error"]  # nosec B101


class TestWeatherTool:
    """Tests for weather tool."""

    async def test_query_weather_success(self) -> None:
        """Test querying weather successfully."""
        tool = WeatherTool()
        result = await tool.execute(location="New York")

        assert result["success"] is True  # nosec B101
        assert result["result"]["location"] == "New York"  # nosec B101
        assert "temperature" in result["result"]  # nosec B101
        assert "condition" in result["result"]  # nosec B101

    async def test_query_weather_with_fahrenheit(self) -> None:
        """Test querying weather with fahrenheit units."""
        tool = WeatherTool()
        result = await tool.execute(location="London", units="fahrenheit")

        assert result["success"] is True  # nosec B101
        assert result["result"]["units"] == "fahrenheit"  # nosec B101

    async def test_query_weather_invalid_units(self) -> None:
        """Test querying weather with invalid units fails."""
        tool = WeatherTool()
        result = await tool.execute(location="Paris", units="kelvin")

        assert result["success"] is False  # nosec B101
        assert "Invalid units" in result["error"]  # nosec B101

    async def test_query_weather_empty_location(self) -> None:
        """Test querying weather with empty location fails."""
        tool = WeatherTool()
        result = await tool.execute(location="")

        assert result["success"] is False  # nosec B101
        assert "cannot be empty" in result["error"]  # nosec B101


class TestMessagingTool:
    """Tests for messaging tool."""

    async def test_send_message_success(self) -> None:
        """Test sending a message successfully."""
        tool = MessagingTool()
        result = await tool.execute(recipient="John", message="Hello!")

        assert result["success"] is True  # nosec B101
        assert result["result"]["recipient"] == "John"  # nosec B101
        assert result["result"]["message"] == "Hello!"  # nosec B101
        assert "message_id" in result["result"]  # nosec B101

    async def test_send_message_empty_recipient(self) -> None:
        """Test sending a message with empty recipient fails."""
        tool = MessagingTool()
        result = await tool.execute(recipient="", message="Hello!")

        assert result["success"] is False  # nosec B101
        assert "Recipient cannot be empty" in result["error"]  # nosec B101

    async def test_send_message_empty_message(self) -> None:
        """Test sending an empty message fails."""
        tool = MessagingTool()
        result = await tool.execute(recipient="John", message="")

        assert result["success"] is False  # nosec B101
        assert "Message cannot be empty" in result["error"]  # nosec B101

    async def test_send_message_exceeds_max_length(self) -> None:
        """Test sending a message exceeding max length fails."""
        tool = MessagingTool()
        long_message = "x" * 1001
        result = await tool.execute(recipient="John", message=long_message)

        assert result["success"] is False  # nosec B101
        assert "exceeds maximum length" in result["error"]  # nosec B101


class TestMusicTool:
    """Tests for music tool."""

    async def test_play_music_success(self) -> None:
        """Test playing music successfully."""
        tool = MusicTool()
        result = await tool.execute(query="Bohemian Rhapsody")

        assert result["success"] is True  # nosec B101
        assert result["result"]["query"] == "Bohemian Rhapsody"  # nosec B101
        assert result["result"]["shuffle"] is False  # nosec B101
        assert "now_playing" in result["result"]  # nosec B101

    async def test_play_music_with_shuffle(self) -> None:
        """Test playing music with shuffle enabled."""
        tool = MusicTool()
        result = await tool.execute(query="Jazz playlist", shuffle=True)

        assert result["success"] is True  # nosec B101
        assert result["result"]["shuffle"] is True  # nosec B101
        assert "shuffled" in result["result"]["message"]  # nosec B101

    async def test_play_music_empty_query(self) -> None:
        """Test playing music with empty query fails."""
        tool = MusicTool()
        result = await tool.execute(query="")

        assert result["success"] is False  # nosec B101
        assert "cannot be empty" in result["error"]  # nosec B101


class TestCalendarTool:
    """Tests for calendar tool."""

    async def test_create_event_success(self) -> None:
        """Test creating a calendar event successfully."""
        tool = CalendarTool()
        result = await tool.execute(
            title="Team Meeting", start_time="2024-01-15T14:00:00Z", duration_minutes=60
        )

        assert result["success"] is True  # nosec B101
        assert result["result"]["title"] == "Team Meeting"  # nosec B101
        assert result["result"]["duration_minutes"] == 60  # nosec B101
        assert "event_id" in result["result"]  # nosec B101

    async def test_create_event_with_location(self) -> None:
        """Test creating a calendar event with location."""
        tool = CalendarTool()
        result = await tool.execute(
            title="Dentist",
            start_time="2024-01-20T10:00:00Z",
            duration_minutes=30,
            location="123 Main St",
        )

        assert result["success"] is True  # nosec B101
        assert result["result"]["location"] == "123 Main St"  # nosec B101

    async def test_create_event_default_duration(self) -> None:
        """Test creating a calendar event with default duration."""
        tool = CalendarTool()
        result = await tool.execute(title="Lunch", start_time="2024-01-15T12:00:00Z")

        assert result["success"] is True  # nosec B101
        assert result["result"]["duration_minutes"] == 60  # nosec B101

    async def test_create_event_empty_title(self) -> None:
        """Test creating an event with empty title fails."""
        tool = CalendarTool()
        result = await tool.execute(title="", start_time="2024-01-15T14:00:00Z")

        assert result["success"] is False  # nosec B101
        assert "cannot be empty" in result["error"]  # nosec B101

    async def test_create_event_negative_duration(self) -> None:
        """Test creating an event with negative duration fails."""
        tool = CalendarTool()
        result = await tool.execute(
            title="Meeting", start_time="2024-01-15T14:00:00Z", duration_minutes=-30
        )

        assert result["success"] is False  # nosec B101
        assert "must be positive" in result["error"]  # nosec B101

    async def test_create_event_exceeds_max_duration(self) -> None:
        """Test creating an event exceeding 24 hours fails."""
        tool = CalendarTool()
        result = await tool.execute(
            title="Long Event", start_time="2024-01-15T14:00:00Z", duration_minutes=1500
        )

        assert result["success"] is False  # nosec B101
        assert "24 hours" in result["error"]  # nosec B101


class TestToolMetadata:
    """Tests for tool metadata."""

    def test_timer_tool_metadata(self) -> None:
        """Test that timer tools have correct metadata."""
        set_timer = SetTimerTool()
        assert set_timer.metadata.tool_id == "timer.set"  # nosec B101
        assert set_timer.metadata.sensitivity.value == "safe"  # nosec B101
        assert "timer" in set_timer.metadata.capabilities  # nosec B101

        cancel_timer = CancelTimerTool()
        assert cancel_timer.metadata.tool_id == "timer.cancel"  # nosec B101

    def test_weather_tool_metadata(self) -> None:
        """Test that weather tool has correct metadata."""
        tool = WeatherTool()
        assert tool.metadata.tool_id == "weather.query"  # nosec B101
        assert "weather" in tool.metadata.capabilities  # nosec B101

    def test_messaging_tool_metadata(self) -> None:
        """Test that messaging tool has correct metadata."""
        tool = MessagingTool()
        assert tool.metadata.tool_id == "messaging.send"  # nosec B101
        assert tool.metadata.sensitivity.value == "sensitive"  # nosec B101
        assert "messaging" in tool.metadata.capabilities  # nosec B101

    def test_music_tool_metadata(self) -> None:
        """Test that music tool has correct metadata."""
        tool = MusicTool()
        assert tool.metadata.tool_id == "music.play"  # nosec B101
        assert "music" in tool.metadata.capabilities  # nosec B101

    def test_calendar_tool_metadata(self) -> None:
        """Test that calendar tool has correct metadata."""
        tool = CalendarTool()
        assert tool.metadata.tool_id == "calendar.create_event"  # nosec B101
        assert "calendar" in tool.metadata.capabilities  # nosec B101
