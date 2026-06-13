"""Platform feature modules for Agent Guru.

These are the high-level features that make the assistant useful day-to-day:
- web_search: Real-time web search for current events
- reminders: Voice-set timers and reminders
- dictation: Type anywhere by speaking, clipboard operations
- user_memory: Persistent memory of user facts across sessions
- screen_reader: Read and understand what's on the screen (like Gemini Live)
- briefing: Morning briefing with weather, news, date/time
- system_status: CPU, RAM, battery, disk status queries
"""

from Agent_Guru.platform.features.briefing import get_morning_briefing, is_briefing_command
from Agent_Guru.platform.features.dictation import (
    extract_dictation_text,
    get_clipboard_action,
    get_clipboard_text,
    is_clipboard_command,
    is_dictation_command,
    set_clipboard_text,
)
from Agent_Guru.platform.features.reminders import ReminderManager, parse_reminder_from_transcript
from Agent_Guru.platform.features.screen_reader import is_screen_read_command, read_screen_text
from Agent_Guru.platform.features.system_status import get_system_status, is_system_status_command
from Agent_Guru.platform.features.user_memory import extract_user_fact, get_user_memory
from Agent_Guru.platform.features.web_search import needs_web_search, search_web

__all__ = [
    "ReminderManager",
    "extract_dictation_text",
    "extract_user_fact",
    "get_clipboard_action",
    "get_clipboard_text",
    "get_morning_briefing",
    "get_system_status",
    "get_user_memory",
    "is_briefing_command",
    "is_clipboard_command",
    "is_dictation_command",
    "is_screen_read_command",
    "is_system_status_command",
    "needs_web_search",
    "parse_reminder_from_transcript",
    "read_screen_text",
    "search_web",
    "set_clipboard_text",
]
