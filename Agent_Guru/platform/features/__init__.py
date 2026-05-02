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
from Agent_Guru.platform.features.web_search import search_web, needs_web_search
from Agent_Guru.platform.features.reminders import ReminderManager, parse_reminder_from_transcript
from Agent_Guru.platform.features.dictation import (
    is_dictation_command, extract_dictation_text,
    is_clipboard_command, get_clipboard_text, set_clipboard_text, get_clipboard_action,
)
from Agent_Guru.platform.features.user_memory import get_user_memory, extract_user_fact
from Agent_Guru.platform.features.screen_reader import read_screen_text, is_screen_read_command
from Agent_Guru.platform.features.briefing import get_morning_briefing, is_briefing_command
from Agent_Guru.platform.features.system_status import get_system_status, is_system_status_command

__all__ = [
    "search_web", "needs_web_search",
    "ReminderManager", "parse_reminder_from_transcript",
    "is_dictation_command", "extract_dictation_text",
    "is_clipboard_command", "get_clipboard_text", "set_clipboard_text", "get_clipboard_action",
    "get_user_memory", "extract_user_fact",
    "read_screen_text", "is_screen_read_command",
    "get_morning_briefing", "is_briefing_command",
    "get_system_status", "is_system_status_command",
]
