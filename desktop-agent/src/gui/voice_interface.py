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
    COMMAND_MODE = "command_mode"  # Normal command processing
    DICTATION_MODE = "dictation_mode"  # Exact text typing without interpretation


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
        self.wake_word_variations = [
            "hey guru",
            "hello guru",
            "hi guru",
            "hey guro",  # Common mispronunciation
            "hello guro",
            "hi guro"
        ]
        self.is_running = False
        self.current_state = VoiceState.IDLE
        self.is_active = False  # Track if wake word has been detected
        self.dictation_mode = False  # Track if in dictation mode
        self.silence_start_time: Optional[float] = None  # Track silence for dictation exit
        
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
    
    def strip_wake_word(self, text: str) -> str:
        """
        Strip wake word from transcribed text.
        
        CRITICAL: Once the Voice_Interface is in ACTIVE state, the wake word
        must be removed from all transcribed text to prevent downstream
        interference with Intent_Pre_Filter, Command_Executor, and LLM_Adapter.
        
        Args:
            text: Transcribed text that may contain wake word
        
        Returns:
            Text with wake word removed and whitespace normalized
        
        Requirements: 30.1, 30.2, 30.3, 30.4, 30.5, 30.6
        """
        if not text:
            return text
        
        # Convert to lowercase for case-insensitive matching
        text_lower = text.lower().strip()
        
        # Try to strip each wake word variation
        for wake_word_variant in self.wake_word_variations:
            # Check if text starts with wake word
            if text_lower.startswith(wake_word_variant):
                # Remove wake word from original text (preserving case of remaining text)
                # Find the position after the wake word in the original text
                wake_word_len = len(wake_word_variant)
                stripped = text[wake_word_len:].strip()
                
                # Log the stripping for debugging
                if stripped != text:
                    print(f"[Wake Word Strip] '{text}' -> '{stripped}'")
                
                return stripped
            
            # Check if wake word appears anywhere in the text (mid-sentence)
            # This handles cases like "open notepad hey guru"
            if wake_word_variant in text_lower:
                # Find position in original text
                pos = text_lower.find(wake_word_variant)
                # Remove wake word and normalize whitespace
                before = text[:pos].strip()
                after = text[pos + len(wake_word_variant):].strip()
                
                # Combine before and after with single space
                if before and after:
                    stripped = f"{before} {after}"
                else:
                    stripped = before or after
                
                # Log the stripping for debugging
                if stripped != text:
                    print(f"[Wake Word Strip] '{text}' -> '{stripped}'")
                
                return stripped
        
        # No wake word found, return original text
        return text
    
    def enter_dictation_mode(self):
        """
        Enter DICTATION_MODE state.
        
        In dictation mode:
        - Intent_Pre_Filter is bypassed
        - LLM_Adapter is bypassed
        - TTS_Service is muted
        - Text is typed exactly as spoken
        
        Requirements: 29.1, 29.2, 29.3, 29.4, 29.5
        """
        self.dictation_mode = True
        self._set_state(VoiceState.DICTATION_MODE)
        self.silence_start_time = None
        print("[Dictation Mode] ENTERED - typing exact text without interpretation")
    
    def exit_dictation_mode(self):
        """
        Exit DICTATION_MODE and return to COMMAND_MODE.
        
        Requirements: 29.6, 29.7
        """
        self.dictation_mode = False
        self._set_state(VoiceState.COMMAND_MODE)
        self.silence_start_time = None
        print("[Dictation Mode] EXITED - returning to command mode")
    
    def is_dictation_mode(self) -> bool:
        """Check if currently in dictation mode"""
        return self.dictation_mode
    
    def check_dictation_exit_conditions(self, text: str, has_speech: bool) -> bool:
        """
        Check if dictation mode should be exited.
        
        Exit conditions:
        1. 2 seconds of silence detected
        2. User says "done" or "stop writing"
        
        Args:
            text: Current transcribed text (if any)
            has_speech: Whether speech is currently detected
        
        Returns:
            True if should exit dictation mode, False otherwise
        
        Requirements: 29.6, 29.7
        """
        if not self.dictation_mode:
            return False
        
        # Check for exit commands
        if text:
            text_lower = text.lower().strip()
            exit_commands = ["done", "stop writing", "stop typing", "finish"]
            if any(cmd in text_lower for cmd in exit_commands):
                print(f"[Dictation Mode] Exit command detected: '{text}'")
                return True
        
        # Check for silence timeout (2 seconds)
        current_time = time.time()
        if not has_speech:
            if self.silence_start_time is None:
                self.silence_start_time = current_time
            elif current_time - self.silence_start_time >= 2.0:
                print("[Dictation Mode] 2 seconds of silence detected")
                return True
        else:
            # Reset silence timer when speech is detected
            self.silence_start_time = None
        
        return False
    
    def should_enter_dictation_mode(self, text: str) -> bool:
        """
        Check if command should trigger dictation mode entry.
        
        Dictation mode is triggered by commands containing:
        - "write"
        - "type"
        - "dictate"
        
        Args:
            text: Command text to check
        
        Returns:
            True if should enter dictation mode, False otherwise
        
        Requirements: 29.2
        """
        if not text:
            return False
        
        text_lower = text.lower().strip()
        dictation_triggers = ["write", "type", "dictate"]
        
        return any(trigger in text_lower for trigger in dictation_triggers)
    
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
        handling wake word detection, wake word stripping, and conversation
        state management including dictation mode.
        
        Requirements: 22, 29, 30
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
                # Determine current mode
                if wake_word_mode:
                    self._set_state(VoiceState.IDLE)
                    print(f"Listening for wake word: '{self.wake_word}'...")
                elif self.dictation_mode:
                    self._set_state(VoiceState.DICTATION_MODE)
                    print("Dictation mode active - speak text to type...")
                else:
                    self._set_state(VoiceState.COMMAND_MODE)
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
                
                # Simulated transcription for demonstration
                # In production, this would come from PAL callback
                transcribed_text = ""  # Would come from PAL
                has_speech = False  # Would come from PAL audio detection
                
                # CRITICAL: Strip wake word if in active state
                if self.is_active and transcribed_text:
                    transcribed_text = self.strip_wake_word(transcribed_text)
                
                # Check for wake word detection
                if wake_word_mode and transcribed_text:
                    text_lower = transcribed_text.lower()
                    wake_word_detected = any(
                        wake_word in text_lower 
                        for wake_word in self.wake_word_variations
                    )
                    
                    if wake_word_detected:
                        print(f"✓ Wake word detected!")
                        self.is_active = True
                        wake_word_mode = False
                        # Strip wake word from the transcription
                        transcribed_text = self.strip_wake_word(transcribed_text)
                        self._set_state(VoiceState.COMMAND_MODE)
                
                # Check for dictation mode entry
                if self.is_active and not self.dictation_mode and transcribed_text:
                    if self.should_enter_dictation_mode(transcribed_text):
                        self.enter_dictation_mode()
                
                # Check for dictation mode exit
                if self.dictation_mode:
                    if self.check_dictation_exit_conditions(transcribed_text, has_speech):
                        self.exit_dictation_mode()
                        # Speak confirmation
                        if self.tts_available:
                            self.speak("Done", interrupt=False)
                
                # Check for deactivation commands
                if self.is_active and transcribed_text:
                    text_lower = transcribed_text.lower()
                    deactivation_commands = ["stop", "sleep", "exit", "that's all"]
                    if any(cmd in text_lower for cmd in deactivation_commands):
                        print("Deactivation command detected")
                        self.is_active = False
                        wake_word_mode = True
                        conversation_turns = 0
                        if self.dictation_mode:
                            self.exit_dictation_mode()
                
                # Process command if we have transcribed text
                if transcribed_text and self.on_command_callback:
                    command = VoiceCommand(
                        text=transcribed_text,
                        confidence=0.9,  # Would come from PAL
                        timestamp=time.time(),
                        language="en-US",
                        wake_word_detected=False  # Already stripped
                    )
                    self.on_command_callback(command)
                
                print("PAL SpeechInput integration: Waiting for callback-based transcription...")
                time.sleep(1.0)
                
                # TODO: Implement full PAL callback-based transcription
                # The PAL interface needs to be extended to support:
                # 1. Callback registration for transcription events
                # 2. Continuous listening with wake word detection
                # 3. Audio level monitoring
                # 4. Silence detection for dictation mode
                
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
