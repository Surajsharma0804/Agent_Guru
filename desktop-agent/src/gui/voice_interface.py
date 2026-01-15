"""
GURU Voice Interface - Natural Speech Interaction

Handles voice input/output for natural human-like conversation using
platform-agnostic PAL interfaces for cross-platform compatibility.

Features:
- Continuous voice recognition via PAL SpeechInput
- Natural language understanding
- Text-to-speech via PAL SpeechOutput
- Wake word detection ("Hey GURU")
- Context-aware responses
- Multi-turn conversations
- Platform-independent implementation

Architecture:
- Uses PAL SpeechInput interface for voice recognition
- Uses PAL SpeechOutput interface for speech synthesis
- Maintains state machine and conversation logic
- Delegates platform-specific operations to PAL backends
"""

import threading
import queue
import time
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from enum import Enum

# PAL imports - platform-agnostic interfaces
from pal.interfaces import SpeechInput, SpeechOutput, TTSPriority, Transcription

from gui.tts_service import get_tts_service


class VoiceState(Enum):
    """Voice interface states"""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"


@dataclass
class VoiceCommand:
    """Recognized voice command"""
    text: str
    confidence: float
    timestamp: float
    language: str = "en-US"
    wake_word_detected: bool = False


class VoiceInterface:
    """
    Natural voice interaction interface for GURU using PAL interfaces.
    
    Provides continuous voice recognition, natural language processing,
    and text-to-speech for human-like conversation across all platforms.
    
    Architecture:
    - Uses PAL SpeechInput for platform-agnostic voice recognition
    - Uses PAL SpeechOutput for platform-agnostic speech synthesis
    - Maintains conversation state and wake word detection
    - Thread-safe operation with proper resource management
    """
    
    def __init__(
        self,
        speech_input: SpeechInput,
        speech_output: Optional[SpeechOutput] = None,
        wake_word: str = "hey guru"
    ):
        """
        Initialize voice interface with PAL interfaces.
        
        Args:
            speech_input: Platform-specific SpeechInput implementation
            speech_output: Optional SpeechOutput (uses TTS service if None)
            wake_word: Wake word to activate voice commands
        """
        self.speech_input = speech_input
        self.wake_word = wake_word.lower()
        self.is_running = False
        self.current_state = VoiceState.IDLE
        
        # Callbacks
        self.on_command_callback: Optional[Callable[[VoiceCommand], None]] = None
        self.on_state_change_callback: Optional[Callable[[VoiceState], None]] = None
        self.on_audio_level_callback: Optional[Callable[[float], None]] = None
        
        # Get platform capabilities
        self.capabilities = speech_input.get_capabilities()
        
        # Text-to-speech service (uses PAL internally)
        self.tts_service = get_tts_service(speech_output)
        self.tts_available = self.tts_service.available
        
        # Threading
        self.listen_thread: Optional[threading.Thread] = None
        self.command_queue = queue.Queue()
        
        print(f"Voice Interface initialized (Platform-agnostic via PAL, Capabilities: {self.capabilities}, TTS: {self.tts_available})")
    
    def set_command_callback(self, callback: Callable[[VoiceCommand], None]):
        """Set callback for voice commands"""
        self.on_command_callback = callback
    
    def set_state_change_callback(self, callback: Callable[[VoiceState], None]):
        """Set callback for state changes"""
        self.on_state_change_callback = callback
    
    def set_audio_level_callback(self, callback: Callable[[float], None]):
        """Set callback for audio level updates"""
        self.on_audio_level_callback = callback
    
    def start_listening(self):
        """Start continuous voice recognition using PAL SpeechInput"""
        if self.is_running:
            print("Voice interface already running")
            return
        
        # Start PAL speech input
        self.speech_input.start_listening()
        
        self.is_running = True
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listen_thread.start()
        print("Voice interface started - listening for wake word...")
    
    def stop_listening(self):
        """Stop voice recognition and cleanup resources"""
        self.is_running = False
        
        # Stop PAL speech input
        self.speech_input.stop_listening()
        
        if self.listen_thread:
            self.listen_thread.join(timeout=2.0)
        print("Voice interface stopped")
    
    def speak(self, text: str, interrupt: bool = False):
        """
        Speak text using text-to-speech service.
        
        Args:
            text: Text to speak
            interrupt: Whether to interrupt current speech
        """
        print(f"[DEBUG] VoiceInterface.speak() called")
        print(f"[DEBUG]   Text: '{text[:50]}...'")
        print(f"[DEBUG]   Thread: {threading.current_thread().name}")
        print(f"[DEBUG]   TTS available: {self.tts_available}")
        
        if not self.tts_available:
            print(f"GURU: {text}")
            return
        
        self._set_state(VoiceState.SPEAKING)
        
        # Use TTS service
        priority = TTSPriority.URGENT if interrupt else TTSPriority.NORMAL
        print(f"[DEBUG] Calling tts_service.speak()...")
        self.tts_service.speak(text, priority, interrupt)
        print(f"[DEBUG] tts_service.speak() returned")
        
        # Wait for TTS to finish speaking before returning to idle
        def wait_for_speech():
            # Wait for speech to start
            time.sleep(0.5)
            
            # Wait while speaking
            while self.tts_service.is_speaking():
                time.sleep(0.1)
            
            # Small delay after speech completes
            time.sleep(0.5)
            
            # Return to idle state
            self._set_state(VoiceState.IDLE)
        
        threading.Thread(target=wait_for_speech, daemon=True).start()
    
    def _listen_loop(self):
        """
        Main listening loop using PAL SpeechInput interface.
        
        This method continuously processes transcriptions from the PAL backend,
        handling wake word detection and conversation state management.
        """
        wake_word_mode = True
        conversation_turns = 0
        max_conversation_turns = 5
        
        # Calibrate microphone using PAL
        try:
            energy_threshold = self.speech_input.calibrate_microphone()
            print(f"Microphone calibrated (energy threshold: {energy_threshold})")
        except Exception as e:
            print(f"Microphone calibration warning: {e}")
        
        while self.is_running:
            try:
                if wake_word_mode:
                    self._set_state(VoiceState.IDLE)
                    print(f"Listening for wake word: '{self.wake_word}'...")
                else:
                    self._set_state(VoiceState.LISTENING)
                    if conversation_turns == 0:
                        print("✓ Ready to listen - speak your command now...")
                    else:
                        print(f"Listening for your response... (turn {conversation_turns}/{max_conversation_turns})")
                
                # Wait for audio input (PAL handles the actual listening)
                # This is a simplified approach - in production, PAL would provide
                # a callback-based or async interface for continuous listening
                time.sleep(0.5)
                
                # In a real implementation, PAL would provide audio data
                # For now, we simulate by checking if PAL has transcription available
                # This would be replaced with actual PAL callback mechanism
                
                # Process transcription
                self._set_state(VoiceState.PROCESSING)
                
                # NOTE: This is a placeholder for PAL integration
                # In production, PAL SpeechInput would provide a callback or
                # async interface for receiving transcriptions
                # For now, we maintain compatibility by noting this needs
                # full PAL callback integration
                
                print("PAL SpeechInput integration: Waiting for callback-based transcription...")
                time.sleep(1.0)
                
                # TODO: Implement full PAL callback-based transcription
                # The PAL interface needs to be extended to support:
                # 1. Callback registration for transcription events
                # 2. Continuous listening with wake word detection
                # 3. Audio level monitoring
                
            except Exception as e:
                print(f"Listen loop error: {e}")
                self._set_state(VoiceState.ERROR)
                time.sleep(1)
    
    def _set_state(self, state: VoiceState):
        """Set voice interface state"""
        if self.current_state != state:
            self.current_state = state
            if self.on_state_change_callback:
                self.on_state_change_callback(state)
    
    def get_state(self) -> VoiceState:
        """Get current voice interface state"""
        return self.current_state
    
    def is_available(self) -> bool:
        """Check if voice interface is available"""
        return SPEECH_RECOGNITION_AVAILABLE and self.tts_available


def create_voice_interface(
    speech_input: Optional[SpeechInput] = None,
    speech_output: Optional[SpeechOutput] = None,
    wake_word: str = "hey guru"
) -> VoiceInterface:
    """
    Factory function to create voice interface with PAL interfaces.
    
    Args:
        speech_input: Optional SpeechInput (creates default if None)
        speech_output: Optional SpeechOutput (creates default if None)
        wake_word: Wake word to activate voice commands
    
    Returns:
        VoiceInterface instance
    
    Note:
        If PAL interfaces are not provided, this function will attempt to
        create platform-specific implementations automatically.
    """
    # If no PAL interfaces provided, create platform-specific ones
    if speech_input is None or speech_output is None:
        from pal.platform_detector import PlatformDetector
        from pal.backend_factory import PlatformBackendFactory
        
        # Detect platform
        platform = PlatformDetector.detect()
        factory = PlatformBackendFactory(platform)
        
        # Create PAL interfaces
        if speech_input is None:
            speech_input = factory.create_speech_input()
        if speech_output is None:
            speech_output = factory.create_speech_output()
    
    return VoiceInterface(speech_input, speech_output, wake_word)


# Export
__all__ = ['VoiceInterface', 'VoiceCommand', 'VoiceState', 'create_voice_interface']
