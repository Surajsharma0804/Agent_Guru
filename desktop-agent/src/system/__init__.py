"""System integration module"""

from .autostart import AutoStartManager, configure_autostart, is_autostart_enabled

__all__ = ['AutoStartManager', 'configure_autostart', 'is_autostart_enabled']
