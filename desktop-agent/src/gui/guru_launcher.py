"""
GURU Humanized AI Assistant - Main Launcher

Complete integration of visual presence, voice interaction, and conversational AI
for natural human-like interaction.

This is the production-grade launcher that creates a fully humanized AI assistant
with visual avatar, voice recognition, natural language understanding, and
text-to-speech capabilities.

Architecture:
- Visual avatar window (always-on-top, animated)
- Continuous voice recognition with wake word detection
- Natural language conversation management
- Integration with backend authority and security systems
- Real-time audio visualization
- Context-aware responses with personality

Security Integration:
- Authority state machine integration
- Audit logging of all interactions
- Secure command execution pipeline
- Biometric verification support

Thread Safety:
- Voice interface runs in background thread
- All Qt operations marshalled via signals with QueuedConnection
- TTS service is thread-safe (internal queue + dedicated thread)
"""

import logging
import signal
import sys
import time
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Configure logging
logger = logging.getLogger(__name__)

try:
    from PyQt6.QtCore import QObject, Qt, pyqtSignal
    from PyQt6.QtWidgets import QApplication, QMessageBox

    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False

from src.audit.audit_logger import AuditLogger, AuditSeverity

# Backend integration
from src.authority.authority_state_machine import AuthorityConfiguration, AuthorityStateMachine, create_authority_state_machine
from src.gui.avatar_window import AvatarState, GURUAvatarWindow, create_guru_window
from src.gui.conversation_manager import ConversationManager, Emotion, Intent, create_conversation_manager
from src.gui.voice_interface import VoiceCommand, VoiceInterface, VoiceState, create_voice_interface

# System integration
from src.system.audio_manager import get_audio_manager


class GURUIntegrationBridge(QObject):
    """
    Bridge between GUI components and backend systems.

    Handles:
    - Voice command processing
    - Authority state synchronization
    - Audit logging
    - State management
    - Error handling
    """

    # Signals for thread-safe GUI updates
    update_avatar_state = pyqtSignal(object)  # AvatarState
    update_status_text = pyqtSignal(str)
    speak_text = pyqtSignal(str, bool)  # text, interrupt
    update_audio_level = pyqtSignal(float)

    def __init__(self):
        super().__init__()

        # Backend components
        self.authority_machine: Optional[AuthorityStateMachine] = None
        self.audit_logger: Optional[AuditLogger] = None

        # GUI components
        self.avatar_window: Optional[GURUAvatarWindow] = None
        self.voice_interface: Optional[VoiceInterface] = None
        self.conversation_manager: Optional[ConversationManager] = None

        # State
        self.is_initialized = False

    def initialize_backend(self):
        """Initialize backend security and audit systems"""
        logger.info("Initializing backend systems...")

        try:
            # Initialize audit logger
            self.audit_logger = AuditLogger(
                log_directory="audit_logs", enable_real_time_verification=True, testing_mode=False
            )

            self.audit_logger.log_system_event(
                "gui_launcher_start", {"mode": "humanized_interface"}, AuditSeverity.INFO
            )
            logger.info("Audit logger initialized")

            # Initialize authority machine
            config = AuthorityConfiguration(test_mode_disable_workstation_lock=False)  # Production mode

            self.authority_machine = create_authority_state_machine(config)
            logger.info("Authority machine initialized")

            self.is_initialized = True
            logger.info("Backend systems initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing backend: {e}", exc_info=True)
            raise

    def initialize_gui(self):
        """Initialize GUI components"""
        logger.info("Initializing GUI components...")

        try:
            # Create avatar window
            self.avatar_window = create_guru_window()
            if not self.avatar_window:
                raise RuntimeError("Failed to create avatar window")

            # Connect avatar signals
            self.avatar_window.voice_button_clicked.connect(self.on_voice_button_clicked)
            self.avatar_window.settings_button_clicked.connect(self.on_settings_clicked)

            # Connect bridge signals to avatar with QUEUED connection for thread safety
            # CRITICAL: These signals are emitted from voice interface background thread
            self.update_avatar_state.connect(self.avatar_window.set_state, Qt.ConnectionType.QueuedConnection)
            self.update_status_text.connect(self.avatar_window.status_label.setText, Qt.ConnectionType.QueuedConnection)
            self.update_audio_level.connect(self.avatar_window.update_audio_level, Qt.ConnectionType.QueuedConnection)

            safe_print("✓ Avatar window created")

            # Create voice interface
            self.voice_interface = create_voice_interface(wake_word="hey guru")

            # Connect voice callbacks
            self.voice_interface.set_command_callback(self.on_voice_command)
            self.voice_interface.set_state_change_callback(self.on_voice_state_change)
            self.voice_interface.set_audio_level_callback(self.on_audio_level_update)

            # Connect speak signal with QUEUED connection for thread safety
            # CRITICAL: Voice callbacks run in background thread, signals must be queued to main thread

            self.speak_text.connect(
                lambda text, interrupt: self.voice_interface.speak(text, interrupt), Qt.ConnectionType.QueuedConnection
            )

            logger.info("Voice interface created")

            # Create conversation manager
            self.conversation_manager = create_conversation_manager()
            logger.info("Conversation manager created")

            logger.info("GUI components initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing GUI: {e}", exc_info=True)
            raise

    def start(self):
        """Start the humanized GURU system"""
        if not self.is_initialized:
            raise RuntimeError("Backend not initialized")

        # Verify audio configuration
        audio_manager = get_audio_manager()
        audio_ok, audio_error = audio_manager.verify_audio_output()

        if not audio_ok:
            logger.warning(f"Audio configuration issue: {audio_error}")

        # Warn about potential mute
        audio_manager.unmute_python_audio()

        # Show avatar window
        self.avatar_window.show()
        logger.info("Avatar window displayed")

        # Start voice recognition
        if self.voice_interface.is_available():
            self.voice_interface.start_listening()
            logger.info("Voice recognition started")

            # Initial greeting
            self.speak_text.emit("Hello! I'm GURU, your personal AI assistant. Say 'Hey GURU' to talk to me!", False)
        else:
            logger.warning("Voice recognition not available")
            self.update_status_text.emit("Voice recognition unavailable")

        # Update avatar state
        self.update_avatar_state.emit(AvatarState.IDLE)

        # Log startup
        if self.audit_logger:
            self.audit_logger.log_system_event(
                "humanized_gui_started",
                {
                    "voice_available": self.voice_interface.is_available(),
                    "authority_state": self.authority_machine.current_state.value,
                },
                AuditSeverity.INFO,
            )

        logger.info("GURU is now active and listening")

    def on_voice_button_clicked(self):
        """Handle voice button click"""

        if self.voice_interface.is_available():
            if self.voice_interface.is_running:
                self.voice_interface.stop_listening()
                self.update_status_text.emit("Voice recognition stopped")
            else:
                self.voice_interface.start_listening()
                self.update_status_text.emit("Listening...")
        else:
            self.update_status_text.emit("Voice recognition not available")

    def on_settings_clicked(self):
        """Handle settings button click"""
        self.speak_text.emit("Settings interface coming soon!", False)

    def on_voice_command(self, command: VoiceCommand):
        """Handle voice command from user"""

        # Log to audit
        if self.audit_logger:
            self.audit_logger.log_system_event(
                "voice_command_received",
                {
                    "text_length": len(command.text),
                    "confidence": command.confidence,
                    "wake_word_detected": command.wake_word_detected,
                },
                AuditSeverity.INFO,
            )

        # Update avatar state
        self.update_avatar_state.emit(AvatarState.THINKING)

        # Process through conversation manager
        response, intent, emotion = self.conversation_manager.process_input(command.text)

        # Map emotion to avatar state
        avatar_state_map = {
            Emotion.NEUTRAL: AvatarState.IDLE,
            Emotion.HAPPY: AvatarState.SPEAKING,
            Emotion.HELPFUL: AvatarState.PROCESSING,
            Emotion.CONCERNED: AvatarState.THINKING,
            Emotion.APOLOGETIC: AvatarState.THINKING,
            Emotion.EXCITED: AvatarState.SPEAKING,
        }

        # Update avatar
        avatar_state = avatar_state_map.get(emotion, AvatarState.SPEAKING)
        self.update_avatar_state.emit(avatar_state)

        # ALWAYS speak the response vocally

        self.speak_text.emit(response, False)

        # Wait for speech to complete before checking for command execution
        time.sleep(1)  # Give TTS time to start

        # Check if command requires execution
        if intent == Intent.COMMAND:
            self.execute_command(command.text, response)

    def execute_command(self, command_text: str, response: str):
        """Execute actual command with authority checking"""
        # Check authority state
        if not self.authority_machine.is_armed:
            auth_response = "I need your authorization to execute commands. Please authenticate first."
            self.speak_text.emit(auth_response, True)

            # Update avatar to locked state
            self.update_avatar_state.emit(AvatarState.LOCKED)
            return

        # Command execution would go here
        # This integrates with the existing command execution pipeline

        # Log command execution
        if self.audit_logger:
            self.audit_logger.log_system_event(
                "command_execution_requested",
                {"command": command_text[:100]},  # Truncate for privacy
                AuditSeverity.INFO,
            )

    def on_voice_state_change(self, state: VoiceState):
        """Handle voice interface state changes"""
        # Map voice state to avatar state
        state_map = {
            VoiceState.IDLE: AvatarState.IDLE,
            VoiceState.LISTENING: AvatarState.LISTENING,
            VoiceState.PROCESSING: AvatarState.THINKING,
            VoiceState.SPEAKING: AvatarState.SPEAKING,
            VoiceState.ERROR: AvatarState.ERROR,
        }

        avatar_state = state_map.get(state, AvatarState.IDLE)
        self.update_avatar_state.emit(avatar_state)

        # Update visualizer
        is_active = state in [VoiceState.LISTENING, VoiceState.PROCESSING]
        if self.avatar_window:
            self.avatar_window.set_visualizer_active(is_active)

    def on_audio_level_update(self, level: float):
        """Handle audio level updates"""
        self.update_audio_level.emit(level)

    def shutdown(self):
        """Graceful shutdown"""

        # Stop voice recognition
        if self.voice_interface:
            self.voice_interface.stop_listening()

        # Log shutdown
        if self.audit_logger:
            self.audit_logger.log_system_event("humanized_gui_shutdown", {"graceful": True}, AuditSeverity.INFO)


def main():
    """
    Main entry point for humanized GURU AI assistant.

    Launches complete system with:
    - Visual avatar presence
    - Voice recognition and synthesis
    - Natural conversation management
    - Backend security integration
    """

    if not PYQT_AVAILABLE:
        return 1

    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("GURU AI Assistant")
    app.setOrganizationName("GURU")

    # Create integration bridge
    bridge = GURUIntegrationBridge()

    try:
        # Initialize backend
        bridge.initialize_backend()

        # Initialize GUI
        bridge.initialize_gui()

        # Start system
        bridge.start()

        # Setup signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            bridge.shutdown()
            app.quit()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Run Qt event loop
        return app.exec()

    except Exception:
        import traceback

        traceback.print_exc()

        # Show error dialog
        if PYQT_AVAILABLE:
            QMessageBox.critical(
                None, "GURU Startup Error", f"Failed to start GURU:\n\n{str(e)}\n\nCheck console for details."
            )

        return 1

    finally:
        bridge.shutdown()


if __name__ == "__main__":
    sys.exit(main())
