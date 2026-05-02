"""Platform feature modules for Agent Guru.

These are the high-level features that make the assistant useful day-to-day:
- web_search: Real-time web search for current events
- reminders: Voice-set timers and reminders
- dictation: Type anywhere by speaking, clipboard operations
- user_memory: Persistent memory of user facts across sessions
"""
from Agent_Guru.platform.features.web_search import search_web, needs_web_search
from Agent_Guru.platform.features.reminders import ReminderManager, parse_reminder_from_transcript
from Agent_Guru.platform.features.dictation import (
    is_dictation_command, extract_dictation_text,
    is_clipboard_command, get_clipboard_text, set_clipboard_text, get_clipboard_action,
)
from Agent_Guru.platform.features.user_memory import get_user_memory, extract_user_fact

__all__ = [
    "search_web", "needs_web_search",
    "ReminderManager", "parse_reminder_from_transcript",
    "is_dictation_command", "extract_dictation_text",
    "is_clipboard_command", "get_clipboard_text", "set_clipboard_text", "get_clipboard_action",
    "get_user_memory", "extract_user_fact",
]
