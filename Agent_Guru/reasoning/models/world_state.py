"""World State data models for context-aware reasoning.

Performance: O(1) state queries, <20ms latency
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class DeviceStatus(BaseModel):
    """Device status information."""

    battery_level: float = Field(ge=0.0, le=100.0, description="Battery percentage")
    charging: bool = Field(default=False)
    network_type: str = Field(default="wifi", description="wifi, cellular, offline")
    screen_state: str = Field(default="on", description="on, off, locked")
    do_not_disturb: bool = Field(default=False)

    @field_validator("network_type")
    @classmethod
    def validate_network_type(cls, v: str) -> str:
        valid = ["wifi", "cellular", "ethernet", "offline"]
        if v not in valid:
            msg = f"network_type must be one of {valid}"
            raise ValueError(msg)
        return v


class SystemResources(BaseModel):
    """System resource usage."""

    cpu_usage: float = Field(ge=0.0, le=100.0, description="CPU usage percentage")
    memory_usage: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Memory usage percentage",
    )
    disk_space_available: int = Field(default=0, ge=0, description="Available disk space in MB")


class AppState(BaseModel):
    """Application state."""

    app_id: str
    is_active: bool = Field(default=False)
    last_used: datetime
    usage_duration: float = Field(ge=0.0, description="Total usage in seconds")
    state_data: dict[str, Any] = Field(default_factory=dict)


class CalendarEvent(BaseModel):
    """Calendar event."""

    event_id: str
    title: str
    start_time: datetime
    end_time: datetime
    location: str | None = None
    attendees: list[str] = Field(default_factory=list)
    is_recurring: bool = Field(default=False)

    @field_validator("end_time")
    @classmethod
    def validate_end_time(cls, v: datetime, info) -> datetime:  # noqa: ANN001
        if "start_time" in info.data and v < info.data["start_time"]:
            msg = "end_time must be after start_time"
            raise ValueError(msg)
        return v


class Contact(BaseModel):
    """Contact information."""

    contact_id: str
    name: str
    phone_numbers: list[str] = Field(default_factory=list)
    email_addresses: list[str] = Field(default_factory=list)
    relationship: str | None = None
    last_contacted: datetime | None = None


class LocationState(BaseModel):
    """Location context."""

    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    accuracy: float = Field(ge=0.0, description="Accuracy in meters")
    place_name: str | None = None
    place_type: str | None = None  # home, work, restaurant, etc.
    arrival_time: datetime | None = None


class Activity(BaseModel):
    """User activity."""

    activity_id: str
    activity_type: str  # call, message, app_open, task_complete, etc.
    timestamp: datetime
    details: dict[str, Any] = Field(default_factory=dict)


class WorldState(BaseModel):
    """Complete world state for context-aware reasoning.

    Time Complexity: O(1) for all queries
    Space Complexity: O(n) where n is number of tracked items
    """

    # Device and system
    device_status: DeviceStatus = Field(default_factory=lambda: DeviceStatus(battery_level=100.0))
    system_resources: SystemResources = Field(
        default_factory=lambda: SystemResources(
            cpu_usage=0.0,
            memory_usage=0.0,
            disk_space_available=0,
        ),
    )

    # Applications
    active_apps: list[str] = Field(default_factory=list)
    app_states: dict[str, AppState] = Field(default_factory=dict)

    # Calendar and contacts
    calendar_events: list[CalendarEvent] = Field(default_factory=list)
    contacts: dict[str, Contact] = Field(default_factory=dict)

    # Location and activity
    location_context: LocationState | None = None
    activity_context: str | None = None  # working, commuting, relaxing, etc.

    # Tasks
    active_tasks: list[str] = Field(default_factory=list)
    recent_activities: list[Activity] = Field(default_factory=list, max_length=100)

    # Metadata
    last_updated: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    def get_active_app_count(self) -> int:
        """Get number of active apps."""
        return len(self.active_apps)

    def is_battery_low(self, threshold: float = 20.0) -> bool:
        """Check if battery is below threshold."""
        return self.device_status.battery_level < threshold

    def get_upcoming_events(self, hours: int = 24) -> list[CalendarEvent]:
        """Get events in next N hours."""
        now = datetime.now(tz=UTC)
        from datetime import timedelta

        cutoff = now + timedelta(hours=hours)

        return [event for event in self.calendar_events if now <= event.start_time <= cutoff]

    def get_contact_by_name(self, name: str) -> Contact | None:
        """Find contact by name (case-insensitive)."""
        name_lower = name.lower()
        for contact in self.contacts.values():
            if contact.name.lower() == name_lower:
                return contact
        return None
