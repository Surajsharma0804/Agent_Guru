"""
Thread-Safe Bridge for Cross-Thread Communication

Production-grade solution for marshalling operations from background threads
to the Qt main thread using signals/slots.

ARCHITECTURE:
- Bridge QObject MUST be created in main thread
- Bridge signals automatically use QueuedConnection for cross-thread
- Background threads emit signals
- Main thread processes signals in event loop
- Type-safe, deterministic, no race conditions

CRITICAL: The bridge must be created in the main thread and moveToThread
must NOT be called. Qt automatically handles cross-thread signal delivery
when the receiver lives in the main thread.

USAGE:
    # In main thread:
    bridge = ThreadSafeBridge()
    bridge.connect_avatar(avatar)

    # From background thread:
    bridge.set_avatar_state.emit(AvatarState.THINKING)
    bridge.speak_text.emit("Hello", False)

    # Signals are automatically queued and processed in main thread
"""

import threading

from PyQt6.QtCore import QObject, Qt, pyqtSignal


class ThreadSafeBridge(QObject):
    """
    Thread-safe bridge for cross-thread communication.

    MUST be created in the main thread. All signals automatically use
    Qt.QueuedConnection when emitted from background threads.
    """

    # Avatar control signals
    set_avatar_state = pyqtSignal(object)  # AvatarState
    set_avatar_status = pyqtSignal(str)  # Status text

    # Speech control signals
    speak_text = pyqtSignal(str, bool)  # text, interrupt
    stop_speech = pyqtSignal()

    # Audio visualization signals
    update_audio_level = pyqtSignal(float)  # level (0.0-1.0)

    # System signals
    show_error = pyqtSignal(str, str)  # title, message
    show_info = pyqtSignal(str, str)  # title, message

    def __init__(self):
        super().__init__()

        # Verify we're in the main thread
        if threading.current_thread().name != "MainThread":
            raise RuntimeError(
                "ThreadSafeBridge MUST be created in the main thread. "
                f"Current thread: {threading.current_thread().name}"
            )

    def connect_avatar(self, avatar_window):
        """
        Connect bridge signals to avatar window.

        Args:
            avatar_window: GURUAvatarWindow instance
        """
        # Explicitly use QueuedConnection for thread safety
        # This ensures signals from background threads are queued to main thread
        self.set_avatar_state.connect(avatar_window.set_state, Qt.ConnectionType.QueuedConnection)

        self.set_avatar_status.connect(
            lambda text: avatar_window.status_label.setText(text), Qt.ConnectionType.QueuedConnection
        )

        self.update_audio_level.connect(avatar_window.update_audio_level, Qt.ConnectionType.QueuedConnection)

    def connect_voice(self, voice_interface):
        """
        Connect bridge signals to voice interface.

        Args:
            voice_interface: VoiceInterface instance (can be None for testing)
        """
        if voice_interface is None:
            return

        self.speak_text.connect(
            lambda text, interrupt: voice_interface.speak(text, interrupt), Qt.ConnectionType.QueuedConnection
        )

        self.stop_speech.connect(lambda: voice_interface.tts_service.clear_queue(), Qt.ConnectionType.QueuedConnection)


# Global bridge instance
_bridge = None


def get_thread_safe_bridge() -> ThreadSafeBridge:
    """
    Get global thread-safe bridge instance.

    MUST be called from main thread on first invocation.

    Returns:
        ThreadSafeBridge singleton
    """
    global _bridge
    if _bridge is None:
        _bridge = ThreadSafeBridge()
    return _bridge


__all__ = ["ThreadSafeBridge", "get_thread_safe_bridge"]
