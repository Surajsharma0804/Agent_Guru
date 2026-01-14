"""
GURU Desktop Agent - Graphical User Interface

Humanized AI assistant with voice interaction, visual presence, and natural conversation.
"""

from .avatar_window import GURUAvatarWindow, create_guru_window
from .voice_interface import VoiceInterface, create_voice_interface
from .conversation_manager import ConversationManager, create_conversation_manager

__all__ = [
    'GURUAvatarWindow',
    'create_guru_window',
    'VoiceInterface',
    'create_voice_interface',
    'ConversationManager',
    'create_conversation_manager'
]
