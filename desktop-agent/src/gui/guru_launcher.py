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

import sys
import signal
import threading
import time
from typing import Optional

# Import console utilities for cross-platform Unicode support
from utils.console import safe_print
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from PyQt6.QtWidgets import QApplication, QMessageBox
    from PyQt6.QtCore import QTimer, pyqtSignal, QObject, Qt
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    print("PyQt6 not available. Install with: pip install PyQt6")

from src.gui.avatar_window import GURUAvatarWindow, AvatarState, create_guru_window
from src.gui.voice_interface import VoiceInterface, VoiceCommand, VoiceState, create_voice_interface
from src.gui.conversation_manager import ConversationManager, Intent, Emotion, create_conversation_manager

# Backend integration
from src.authority.state import AuthorityStateMachine, AuthorityConfiguration, create_authority_state_machine
from src.audit.audit_logger import AuditLogger, AuditEvent, AuditEventType, AuditSeverity

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
        
        print("GURU Integration Bridge created")
    
    def initialize_backend(self):
        """Initialize backend security and audit systems"""
        safe_print("Initializing backend systems...")
        safe_print("DEBUG: About to create audit logger")
        
        try:
            # Initialize audit logger
            self.audit_logger = AuditLogger(
                log_directory="audit_logs",
                enable_real_time_verification=True,
                testing_mode=False
            )
            safe_print("DEBUG: Audit logger created, about to log event")
            
            self.audit_logger.log_system_event(
                "gui_launcher_start",
                {"mode": "humanized_interface"},
                AuditSeverity.INFO
            )
            safe_print("DEBUG: Event logged")
            safe_print("✓ Audit logger initialized")
            
            safe_print("DEBUG: About to create authority config")
            # Initialize authority machine
            config = AuthorityConfiguration(
                test_mode_disable_workstation_lock=False  # Production mode
            )
            safe_print("DEBUG: Config created, about to create authority machine")
            
            self.authority_machine = create_authority_state_machine(config)
            safe_print("DEBUG: Authority machine created")
            safe_print("✓ Authority machine initialized")
            
            safe_print("DEBUG: About to set is_initialized = True")
            self.is_initialized = True
            safe_print("DEBUG: is_initialized set to True")
            safe_print("Backend systems initialized successfully")
            
        except Exception as e:
            safe_print(f"ERROR initializing backend: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def initialize_gui(self):
        """Initialize GUI components"""
        safe_print("Initializing GUI components...")
        
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
            self.update_avatar_state.connect(
                self.avatar_window.set_state,
                Qt.ConnectionType.QueuedConnection
            )
            self.update_status_text.connect(
                self.avatar_window.status_label.setText,
                Qt.ConnectionType.QueuedConnection
            )
            self.update_audio_level.connect(
                self.avatar_window.update_audio_level,
                Qt.ConnectionType.QueuedConnection
            )
            
            safe_print("✓ Avatar window created")
            
            # Create voice interface
            self.voice_interface = create_voice_interface(wake_word="hey guru")
            
            # Connect voice callbacks
            self.voice_interface.set_command_callback(self.on_voice_command)
            self.voice_interface.set_state_change_callback(self.on_voice_state_change)
            self.voice_interface.set_audio_level_callback(self.on_audio_level_update)
            
            # Connect speak signal with QUEUED connection for thread safety
            # CRITICAL: Voice callbacks run in background thread, signals must be queued to main thread
            print(f"[DEBUG] Connecting speak_text signal to voice_interface.speak...")
            print(f"[DEBUG] Voice interface type: {type(self.voice_interface)}")
            print(f"[DEBUG] Voice interface has speak method: {hasattr(self.voice_interface, 'speak')}")
            
            self.speak_text.connect(
                lambda text, interrupt: self.voice_interface.speak(text, interrupt),
                Qt.ConnectionType.QueuedConnection
            )
            
            print(f"[DEBUG] speak_text signal connected successfully")
            
            safe_print("✓ Voice interface created")
            
            # Create conversation manager
            self.conversation_manager = create_conversation_manager()
            safe_print("✓ Conversation manager created")
            
            safe_print("GUI components initialized successfully")
            
        except Exception as e:
            safe_print(f"ERROR initializing GUI: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def start(self):
        """Start the humanized GURU system"""
        if not self.is_initialized:
            raise RuntimeError("Backend not initialized")
        
        print("\n" + "="*60)
        print("STARTING HUMANIZED GURU AI ASSISTANT")
        print("="*60)
        
        # Verify audio configuration
        audio_manager = get_audio_manager()
        audio_ok, audio_error = audio_manager.verify_audio_output()
        
        if not audio_ok:
            safe_print(f"⚠ Audio configuration issue: {audio_error}")
        
        # Warn about potential mute
        audio_manager.unmute_python_audio()
        
        # Show avatar window
        self.avatar_window.show()
        safe_print("✓ Avatar window displayed")
        
        # Start voice recognition
        if self.voice_interface.is_available():
            self.voice_interface.start_listening()
            safe_print("✓ Voice recognition started")
            
            # Initial greeting
            self.speak_text.emit(
                "Hello! I'm GURU, your personal AI assistant. Say 'Hey GURU' to talk to me!",
                False
            )
        else:
            safe_print("⚠ Voice recognition not available")
            self.update_status_text.emit("Voice recognition unavailable")
        
        # Update avatar state
        self.update_avatar_state.emit(AvatarState.IDLE)
        
        # Log startup
        if self.audit_logger:
            self.audit_logger.log_system_event(
                "humanized_gui_started",
                {
                    "voice_available": self.voice_interface.is_available(),
                    "authority_state": self.authority_machine.current_state.value
                },
                AuditSeverity.INFO
            )
        
        safe_print("\n✓ GURU is now active and listening!")
        safe_print("Say 'Hey GURU' to start talking")
        safe_print("="*60 + "\n")
    
    def on_voice_button_clicked(self):
        """Handle voice button click"""
        print("Voice button clicked")
        
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
        print("Settings clicked")
        self.speak_text.emit("Settings interface coming soon!", False)
    
    def on_voice_command(self, command: VoiceCommand):
        """Handle voice command from user"""
        print(f"\n{'='*60}")
        print(f"USER: {command.text}")
        print(f"{'='*60}")
        print(f"[DEBUG] on_voice_command called from thread: {threading.current_thread().name}")
        
        # Log to audit
        if self.audit_logger:
            self.audit_logger.log_system_event(
                "voice_command_received",
                {
                    "text_length": len(command.text),
                    "confidence": command.confidence,
                    "wake_word_detected": command.wake_word_detected
                },
                AuditSeverity.INFO
            )
        
        # Update avatar state
        print(f"[DEBUG] Emitting avatar state: THINKING")
        self.update_avatar_state.emit(AvatarState.THINKING)
        
        # Process through conversation manager
        print(f"[DEBUG] Processing input through conversation manager...")
        response, intent, emotion = self.conversation_manager.process_input(command.text)
        
        print(f"GURU: {response}")
        print(f"Intent: {intent.value}, Emotion: {emotion.value}")
        print(f"{'='*60}\n")
        
        # Map emotion to avatar state
        avatar_state_map = {
            Emotion.NEUTRAL: AvatarState.IDLE,
            Emotion.HAPPY: AvatarState.SPEAKING,
            Emotion.HELPFUL: AvatarState.PROCESSING,
            Emotion.CONCERNED: AvatarState.THINKING,
            Emotion.APOLOGETIC: AvatarState.THINKING,
            Emotion.EXCITED: AvatarState.SPEAKING
        }
        
        # Update avatar
        avatar_state = avatar_state_map.get(emotion, AvatarState.SPEAKING)
        print(f"[DEBUG] Emitting avatar state: {avatar_state}")
        self.update_avatar_state.emit(avatar_state)
        
        # ALWAYS speak the response vocally
        print(f"GURU (speaking): {response}")
        print(f"[DEBUG] About to emit speak_text signal...")
        print(f"[DEBUG] Voice interface available: {self.voice_interface is not None}")
        
        self.speak_text.emit(response, False)
        
        print(f"[DEBUG] speak_text signal emitted")
        
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
            print(f"GURU: {auth_response}")
            self.speak_text.emit(auth_response, True)
            
            # Update avatar to locked state
            self.update_avatar_state.emit(AvatarState.LOCKED)
            return
        
        # Command execution would go here
        # This integrates with the existing command execution pipeline
        print(f"Executing command: {command_text}")
        
        # Log command execution
        if self.audit_logger:
            self.audit_logger.log_system_event(
                "command_execution_requested",
                {"command": command_text[:100]},  # Truncate for privacy
                AuditSeverity.INFO
            )
    
    def on_voice_state_change(self, state: VoiceState):
        """Handle voice interface state changes"""
        # Map voice state to avatar state
        state_map = {
            VoiceState.IDLE: AvatarState.IDLE,
            VoiceState.LISTENING: AvatarState.LISTENING,
            VoiceState.PROCESSING: AvatarState.THINKING,
            VoiceState.SPEAKING: AvatarState.SPEAKING,
            VoiceState.ERROR: AvatarState.ERROR
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
        print("\nShutting down GURU...")
        
        # Stop voice recognition
        if self.voice_interface:
            self.voice_interface.stop_listening()
        
        # Log shutdown
        if self.audit_logger:
            self.audit_logger.log_system_event(
                "humanized_gui_shutdown",
                {"graceful": True},
                AuditSeverity.INFO
            )
        
        print("GURU shutdown complete")


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
        print("ERROR: PyQt6 is required for the GUI")
        print("Install with: pip install PyQt6")
        return 1
    
    print("\n" + "="*60)
    print("GURU HUMANIZED AI ASSISTANT")
    print("Production-Grade Personal Automation with Natural Interaction")
    print("="*60 + "\n")
    
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
            print(f"\nReceived signal {signum}")
            bridge.shutdown()
            app.quit()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Run Qt event loop
        return app.exec()
        
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        
        # Show error dialog
        if PYQT_AVAILABLE:
            QMessageBox.critical(
                None,
                "GURU Startup Error",
                f"Failed to start GURU:\n\n{str(e)}\n\nCheck console for details."
            )
        
        return 1
    
    finally:
        bridge.shutdown()


if __name__ == "__main__":
    sys.exit(main())
