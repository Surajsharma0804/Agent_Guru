"""
Module: Agent_Guru.platform.permissions.time_checker
Purpose: Enhanced time-based permission validation with timezone support

This module implements comprehensive time-based access control:
- Time window validation (start-end hours)
- Day of week checking
- Hour range checking with cross-midnight support
- Timezone handling (local, UTC, custom)
- Multiple time window support (OR logic)

Performance Characteristics:
    - Time Complexity: O(1) for time validation
    - Space Complexity: O(1) per time restriction
    - Timezone conversion: <1ms

Author: Agent Guru Team
Date: 2026-02-26
Version: 1.0.0
"""

from datetime import datetime, time, timezone, timedelta
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class DayOfWeek(Enum):
    """Day of week enumeration."""
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6
    
    @classmethod
    def from_string(cls, day_str: str) -> "DayOfWeek":
        """
        Convert day name string to DayOfWeek enum.
        
        Args:
            day_str: Day name (case-insensitive)
            
        Returns:
            DayOfWeek enum value
            
        Raises:
            ValueError: If day name is invalid
        """
        day_map = {
            "monday": cls.MONDAY,
            "tuesday": cls.TUESDAY,
            "wednesday": cls.WEDNESDAY,
            "thursday": cls.THURSDAY,
            "friday": cls.FRIDAY,
            "saturday": cls.SATURDAY,
            "sunday": cls.SUNDAY,
            "mon": cls.MONDAY,
            "tue": cls.TUESDAY,
            "wed": cls.WEDNESDAY,
            "thu": cls.THURSDAY,
            "fri": cls.FRIDAY,
            "sat": cls.SATURDAY,
            "sun": cls.SUNDAY,
        }
        
        normalized = day_str.lower().strip()
        if normalized not in day_map:
            raise ValueError(
                f"Invalid day name: {day_str}. "
                f"Valid values: {list(day_map.keys())}"
            )
        
        return day_map[normalized]


@dataclass
class TimeWindow:
    """
    Time window with start and end times.
    
    Supports:
    - Same-day windows: 09:00-17:00
    - Cross-midnight windows: 22:00-02:00
    - Full-day windows: 00:00-23:59
    """
    start_time: time
    end_time: time
    
    def contains(self, check_time: time) -> bool:
        """
        Check if time falls within window.
        
        Time Complexity: O(1)
        
        Args:
            check_time: Time to check
            
        Returns:
            True if time is within window
        """
        # Handle cross-midnight windows (e.g., 22:00-02:00)
        if self.start_time > self.end_time:
            # Time is after start OR before end
            return check_time >= self.start_time or check_time <= self.end_time
        else:
            # Normal same-day window
            return self.start_time <= check_time <= self.end_time
    
    @classmethod
    def from_string(cls, time_range: str) -> "TimeWindow":
        """
        Parse time range string into TimeWindow.
        
        Supported formats:
        - "09:00-17:00" (HH:MM-HH:MM)
        - "9:00-17:00" (H:MM-HH:MM)
        - "09:00:00-17:00:00" (HH:MM:SS-HH:MM:SS)
        
        Args:
            time_range: Time range string
            
        Returns:
            TimeWindow instance
            
        Raises:
            ValueError: If format is invalid
        """
        try:
            start_str, end_str = time_range.split("-")
            start_str = start_str.strip()
            end_str = end_str.strip()
            
            # Pad single-digit hours with leading zero for fromisoformat
            if ':' in start_str:
                parts = start_str.split(':')
                if len(parts[0]) == 1:
                    start_str = '0' + start_str
            
            if ':' in end_str:
                parts = end_str.split(':')
                if len(parts[0]) == 1:
                    end_str = '0' + end_str
            
            start_time = time.fromisoformat(start_str)
            end_time = time.fromisoformat(end_str)
            return cls(start_time=start_time, end_time=end_time)
        except Exception as e:
            raise ValueError(
                f"Invalid time range format: {time_range}. "
                f"Expected format: HH:MM-HH:MM. Error: {e}"
            )
    
    def __str__(self) -> str:
        """String representation."""
        return f"{self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}"


@dataclass
class TimeRestriction:
    """
    Time-based access restriction with timezone support.
    
    Features:
    - Multiple day-of-week support
    - Multiple time windows (OR logic)
    - Timezone-aware validation
    - Cross-midnight window support
    
    Example:
        >>> # Business hours restriction
        >>> restriction = TimeRestriction(
        ...     days=[DayOfWeek.MONDAY, DayOfWeek.TUESDAY],
        ...     time_windows=[TimeWindow.from_string("09:00-17:00")],
        ...     timezone_name="America/New_York"
        ... )
        >>> allowed = restriction.is_allowed(datetime.now())
    """
    days: List[DayOfWeek]
    time_windows: List[TimeWindow]
    timezone_name: Optional[str] = None  # None = local timezone
    
    def is_allowed(self, dt: Optional[datetime] = None) -> bool:
        """
        Check if datetime is within allowed time restrictions.
        
        Time Complexity: O(d + w) where d=days, w=windows
        Space Complexity: O(1)
        
        Args:
            dt: Datetime to check (None = current time)
            
        Returns:
            True if time is allowed, False otherwise
        """
        if dt is None:
            dt = datetime.now()
        
        # Convert to target timezone if specified
        if self.timezone_name:
            try:
                target_tz = self._get_timezone(self.timezone_name)
                dt = dt.astimezone(target_tz)
            except Exception as e:
                logger.warning(
                    f"Failed to convert to timezone {self.timezone_name}: {e}. "
                    f"Using local timezone."
                )
        
        # Check day of week
        current_day = DayOfWeek(dt.weekday())
        if current_day not in self.days:
            logger.debug(
                f"Time restriction: Day not allowed. "
                f"Current: {current_day.name}, Allowed: {[d.name for d in self.days]}"
            )
            return False
        
        # Check time windows (OR logic - any window matches)
        current_time = dt.time()
        for window in self.time_windows:
            if window.contains(current_time):
                logger.debug(
                    f"Time restriction: Allowed. "
                    f"Day: {current_day.name}, Time: {current_time.strftime('%H:%M')}, "
                    f"Window: {window}"
                )
                return True
        
        logger.debug(
            f"Time restriction: Time not in any window. "
            f"Current: {current_time.strftime('%H:%M')}, "
            f"Windows: {[str(w) for w in self.time_windows]}"
        )
        return False
    
    @staticmethod
    def _get_timezone(tz_name: str) -> timezone:
        """
        Get timezone object from name.
        
        Args:
            tz_name: Timezone name (e.g., "America/New_York", "UTC", "UTC+05:30")
            
        Returns:
            Timezone object
            
        Raises:
            ValueError: If timezone name is invalid
        """
        # Handle UTC special case
        if tz_name.upper() == "UTC":
            return timezone.utc
        
        # Handle UTC offset format (e.g., "UTC+05:30", "UTC-08:00")
        if tz_name.upper().startswith("UTC"):
            offset_str = tz_name[3:]  # Remove "UTC" prefix
            if not offset_str:
                return timezone.utc
            
            # Parse offset
            sign = 1 if offset_str[0] == '+' else -1
            offset_str = offset_str[1:]  # Remove sign
            
            if ':' in offset_str:
                hours, minutes = map(int, offset_str.split(':'))
            else:
                hours = int(offset_str)
                minutes = 0
            
            offset = timedelta(hours=sign * hours, minutes=sign * minutes)
            return timezone(offset, name=tz_name)
        
        # For named timezones, try to use zoneinfo (Python 3.9+)
        try:
            from zoneinfo import ZoneInfo
            return ZoneInfo(tz_name)
        except ImportError:
            # Fallback for Python < 3.9
            logger.warning(
                f"zoneinfo not available. Using UTC offset for {tz_name}. "
                f"Install tzdata package for full timezone support."
            )
            return timezone.utc
        except Exception as e:
            raise ValueError(f"Invalid timezone name: {tz_name}. Error: {e}")
    
    @classmethod
    def from_dict(cls, config: dict) -> "TimeRestriction":
        """
        Create TimeRestriction from configuration dictionary.
        
        Args:
            config: Configuration dict with keys:
                - days: List of day names (e.g., ["monday", "tuesday"])
                - hours: Time range string or list of ranges
                - timezone: Optional timezone name
                
        Returns:
            TimeRestriction instance
            
        Raises:
            ValueError: If configuration is invalid
        """
        # Parse days
        days = [DayOfWeek.from_string(day) for day in config["days"]]
        
        # Parse time windows
        hours = config["hours"]
        if isinstance(hours, str):
            # Single time range
            time_windows = [TimeWindow.from_string(hours)]
        elif isinstance(hours, list):
            # Multiple time ranges
            time_windows = [TimeWindow.from_string(h) for h in hours]
        else:
            raise ValueError(
                f"Invalid hours format: {hours}. "
                f"Expected string or list of strings."
            )
        
        # Get timezone (optional)
        timezone_name = config.get("timezone")
        
        return cls(
            days=days,
            time_windows=time_windows,
            timezone_name=timezone_name
        )


class TimeChecker:
    """
    Time-based permission checker with multiple restriction support.
    
    Features:
    - Multiple time restrictions (OR logic)
    - Timezone-aware validation
    - Efficient time checking (O(1) per restriction)
    
    Example:
        >>> checker = TimeChecker([
        ...     TimeRestriction.from_dict({
        ...         "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
        ...         "hours": "09:00-17:00",
        ...         "timezone": "America/New_York"
        ...     }),
        ...     TimeRestriction.from_dict({
        ...         "days": ["saturday", "sunday"],
        ...         "hours": "10:00-14:00",
        ...         "timezone": "America/New_York"
        ...     })
        ... ])
        >>> allowed = checker.is_allowed()
    """
    
    def __init__(self, restrictions: List[TimeRestriction]):
        """
        Initialize time checker.
        
        Args:
            restrictions: List of time restrictions (OR logic)
        """
        self.restrictions = restrictions
        
        if not restrictions:
            logger.warning("TimeChecker initialized with no restrictions (always allowed)")
    
    def is_allowed(self, dt: Optional[datetime] = None) -> bool:
        """
        Check if datetime is allowed by any restriction.
        
        Time Complexity: O(n * (d + w)) where n=restrictions, d=days, w=windows
        Space Complexity: O(1)
        
        Args:
            dt: Datetime to check (None = current time)
            
        Returns:
            True if allowed by any restriction, False otherwise
        """
        # No restrictions = always allowed
        if not self.restrictions:
            return True
        
        # Check each restriction (OR logic)
        for restriction in self.restrictions:
            if restriction.is_allowed(dt):
                return True
        
        return False
    
    @classmethod
    def from_config_list(cls, config_list: List[dict]) -> "TimeChecker":
        """
        Create TimeChecker from list of configuration dictionaries.
        
        Args:
            config_list: List of time restriction configs
            
        Returns:
            TimeChecker instance
        """
        restrictions = [
            TimeRestriction.from_dict(config)
            for config in config_list
        ]
        return cls(restrictions)


# Convenience functions for common time restrictions

def business_hours(timezone_name: str = "UTC") -> TimeRestriction:
    """
    Create business hours restriction (Mon-Fri, 9am-5pm).
    
    Args:
        timezone_name: Timezone name
        
    Returns:
        TimeRestriction for business hours
    """
    return TimeRestriction(
        days=[
            DayOfWeek.MONDAY,
            DayOfWeek.TUESDAY,
            DayOfWeek.WEDNESDAY,
            DayOfWeek.THURSDAY,
            DayOfWeek.FRIDAY
        ],
        time_windows=[TimeWindow.from_string("09:00-17:00")],
        timezone_name=timezone_name
    )


def weekends(timezone_name: str = "UTC") -> TimeRestriction:
    """
    Create weekend restriction (Sat-Sun, all day).
    
    Args:
        timezone_name: Timezone name
        
    Returns:
        TimeRestriction for weekends
    """
    return TimeRestriction(
        days=[DayOfWeek.SATURDAY, DayOfWeek.SUNDAY],
        time_windows=[TimeWindow.from_string("00:00-23:59")],
        timezone_name=timezone_name
    )


def night_hours(timezone_name: str = "UTC") -> TimeRestriction:
    """
    Create night hours restriction (every day, 10pm-6am).
    
    Args:
        timezone_name: Timezone name
        
    Returns:
        TimeRestriction for night hours
    """
    return TimeRestriction(
        days=list(DayOfWeek),  # All days
        time_windows=[TimeWindow.from_string("22:00-06:00")],
        timezone_name=timezone_name
    )
