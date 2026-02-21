"""
WorldState Integration with Reasoning Components.

This module provides integration between WorldState and reasoning components.

Performance: <10ms context generation
"""


import structlog

from Agent_Guru.reasoning.models.world_state import WorldState

logger = structlog.get_logger(__name__)


class WorldStateContextGenerator:
    """Generate context summaries from WorldState for reasoning components.

    Time Complexity: O(1) for all operations
    Space Complexity: O(1)
    """

    def __init__(self):
        """Initialize context generator."""
        logger.info("world_state_context_generator_initialized")

    def generate_llm_context(self, state: WorldState) -> str:
        """Generate context summary for LLM prompts.

        Time Complexity: O(1)

        Args:
            state: Current world state

        Returns:
            Context summary string for LLM injection
        """
        context_parts = []

        # Device status
        battery_status = "charging" if state.device_status.charging else "not charging"
        context_parts.append(
            f"Device: {state.device_status.battery_level:.0f}% battery ({battery_status}), "
            f"{state.device_status.network_type} network"
        )

        # System resources
        if state.system_resources.cpu_usage > 80:
            context_parts.append("System: High CPU usage")
        if state.system_resources.memory_usage > 80:
            context_parts.append("System: High memory usage")

        # Active apps
        if state.active_apps:
            app_count = len(state.active_apps)
            context_parts.append(f"Active apps: {app_count}")

        # Location
        if state.location_context:
            if state.location_context.place_name:
                context_parts.append(f"Location: {state.location_context.place_name}")

        # Calendar
        upcoming = state.get_upcoming_events(hours=2)
        if upcoming:
            context_parts.append(f"Upcoming: {len(upcoming)} event(s) in next 2 hours")

        # Active tasks
        if state.active_tasks:
            context_parts.append(f"Active tasks: {len(state.active_tasks)}")

        return " | ".join(context_parts) if context_parts else "No context available"

    def check_constraints(self, state: WorldState) -> dict[str, bool]:
        """Check state constraints for task planning.

        Time Complexity: O(1)

        Args:
            state: Current world state

        Returns:
            Dictionary of constraint checks
        """
        constraints = {
            "battery_low": state.is_battery_low(threshold=20.0),
            "battery_critical": state.is_battery_low(threshold=10.0),
            "network_available": state.device_status.network_type != "offline",
            "do_not_disturb": state.device_status.do_not_disturb,
            "high_cpu": state.system_resources.cpu_usage > 80,
            "high_memory": state.system_resources.memory_usage > 80,
            "has_upcoming_events": len(state.get_upcoming_events(hours=1)) > 0,
        }

        return constraints

    def get_app_availability(self, state: WorldState, app_id: str) -> bool:
        """Check if app is available/active.

        Time Complexity: O(1)

        Args:
            state: Current world state
            app_id: App identifier to check

        Returns:
            True if app is active
        """
        return app_id in state.active_apps

    def get_calendar_conflicts(
        self,
        state: WorldState,
        proposed_start: str,
        proposed_end: str,
    ) -> list[str]:
        """Check for calendar conflicts.

        Time Complexity: O(n) where n is number of events

        Args:
            state: Current world state
            proposed_start: Proposed start time (ISO format)
            proposed_end: Proposed end time (ISO format)

        Returns:
            List of conflicting event IDs
        """
        from datetime import datetime

        try:
            start = datetime.fromisoformat(proposed_start)
            end = datetime.fromisoformat(proposed_end)
        except ValueError:
            logger.warning("invalid_datetime_format")
            return []

        conflicts = []
        for event in state.calendar_events:
            # Check for overlap
            if start < event.end_time and end > event.start_time:
                conflicts.append(event.event_id)

        return conflicts

    def should_use_brief_response(self, state: WorldState) -> bool:
        """Determine if brief responses should be used.

        Time Complexity: O(1)

        Args:
            state: Current world state

        Returns:
            True if brief responses recommended
        """
        # Use brief responses when:
        # - Battery is low
        # - Do not disturb is on
        # - High system load
        return (
            state.is_battery_low(threshold=15.0)
            or state.device_status.do_not_disturb
            or state.system_resources.cpu_usage > 90
        )

    def get_location_constraints(self, state: WorldState) -> dict[str, any]:
        """Get location-based constraints.

        Time Complexity: O(1)

        Args:
            state: Current world state

        Returns:
            Dictionary of location constraints
        """
        if not state.location_context:
            return {"has_location": False}

        return {
            "has_location": True,
            "place_name": state.location_context.place_name,
            "place_type": state.location_context.place_type,
            "is_home": state.location_context.place_type == "home",
            "is_work": state.location_context.place_type == "work",
        }

    def generate_context_summary(self, state: WorldState) -> dict[str, any]:
        """Generate comprehensive context summary.

        Time Complexity: O(1)

        Args:
            state: Current world state

        Returns:
            Dictionary with context summary
        """
        return {
            "llm_context": self.generate_llm_context(state),
            "constraints": self.check_constraints(state),
            "brief_response_mode": self.should_use_brief_response(state),
            "location": self.get_location_constraints(state),
            "active_app_count": len(state.active_apps),
            "active_task_count": len(state.active_tasks),
            "upcoming_event_count": len(state.get_upcoming_events(hours=2)),
        }
