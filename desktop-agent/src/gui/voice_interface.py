"""
GURU Voice Interface - Natural Speech Interaction

Handles voice input/output for natural human-like conversation.

Features:
- Continuous voice recognition
- Natural language understanding
- Text-to-speech with emotion
- Wake word detection ("Hey GURU")
- Context-aware responses
- Multi-turn conversations
"""

import threading
import queue
import time
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from enum import Enum

try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False
    print("speech_recognition not available. Install with: pip install SpeechRecognition")

from gui.tts_service import get_tts_service, TTSPriority


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
    Natural voice interaction interface for GURU.
    
    Provides continuous voice recognition, natural language processing,
    and text-to-speech for human-like conversation.
    """
    
    def __init__(self, wake_word: str = "hey guru"):
        """
        Initialize voice interface.
        
        Args:
            wake_word: Wake word to activate voice commands
        """
        self.wake_word = wake_word.lower()
        self.is_running = False
        self.current_state = VoiceState.IDLE
        
        # Callbacks
        self.on_command_callback: Optional[Callable[[VoiceCommand], None]] = None
        self.on_state_change_callback: Optional[Callable[[VoiceState], None]] = None
        self.on_audio_level_callback: Optional[Callable[[float], None]] = None
        
        # Speech recognition
        if SPEECH_RECOGNITION_AVAILABLE:
            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()
            
            # Configure recognizer for better performance
            self.recognizer.energy_threshold = 4000  # Adjust based on ambient noise
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.dynamic_energy_adjustment_damping = 0.15
            self.recognizer.dynamic_energy_ratio = 1.5
            self.recognizer.pause_threshold = 2.0  # Wait 2 seconds of silence before considering speech complete
            self.recognizer.phrase_threshold = 0.3  # Minimum seconds of speaking audio before considering phrase
            self.recognizer.non_speaking_duration = 0.8  # Seconds of non-speaking audio to keep on both sides
            
            # Adjust for ambient noise
            with self.microphone as source:
                print("Calibrating microphone for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=2)
                print(f"Microphone calibrated (energy threshold: {self.recognizer.energy_threshold})")
        else:
            self.recognizer = None
            self.microphone = None
        
        # Text-to-speech service
        self.tts_service = get_tts_service()
        self.tts_available = self.tts_service.available
        
        # Threading
        self.listen_thread: Optional[threading.Thread] = None
        self.command_queue = queue.Queue()
        
        print(f"Voice Interface initialized (SR: {SPEECH_RECOGNITION_AVAILABLE}, TTS: {self.tts_available})")
    
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
        """Start continuous voice recognition"""
        if not SPEECH_RECOGNITION_AVAILABLE:
            print("ERROR: Speech recognition not available")
            return
        
        if self.is_running:
            print("Voice interface already running")
            return
        
        self.is_running = True
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listen_thread.start()
        print("Voice interface started - listening for wake word...")
    
    def stop_listening(self):
        """Stop voice recognition"""
        self.is_running = False
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
        """Main listening loop"""
        wake_word_mode = True
        conversation_turns = 0  # Track conversation turns
        max_conversation_turns = 5  # Allow 5 exchanges before requiring wake word again
        
        while self.is_running:
            try:
                with self.microphone as source:
                    if wake_word_mode:
                        self._set_state(VoiceState.IDLE)
                        print(f"Listening for wake word: '{self.wake_word}'...")
                    else:
                        self._set_state(VoiceState.LISTENING)
                        if conversation_turns == 0:
                            print("✓ Ready to listen - speak your command now...")
                        else:
                            print(f"Listening for your response... (turn {conversation_turns}/{max_conversation_turns})")
                    
                    # Listen for audio with longer timeout and phrase limit
                    audio = self.recognizer.listen(
                        source, 
                        timeout=10,  # Wait up to 10 seconds for speech to start
                        phrase_time_limit=15  # Allow up to 15 seconds of continuous speech
                    )
                    
                    # Update audio level (simulated from energy)
                    if self.on_audio_level_callback:
                        energy = self.recognizer.energy_threshold
                        level = min(1.0, energy / 4000.0)
                        self.on_audio_level_callback(level)
                
                # Process audio
                self._set_state(VoiceState.PROCESSING)
                
                try:
                    # Recognize speech
                    text = self.recognizer.recognize_google(audio, language="en-US")
                    text_lower = text.lower()
                    
                    print(f"Recognized: {text}")
                    
                    if wake_word_mode:
                        # Check for wake word (more flexible matching)
                        wake_word_variants = [
                            "hey guru",
                            "hello guru",
                            "hi guru",
                            "guru",
                            "hey google",  # Common misrecognition
                            "ok guru",
                            "guru where are you",
                            "guru tum kaha ho",
                            "guru kahan ho"
                        ]
                        
                        wake_detected = any(variant in text_lower for variant in wake_word_variants)
                        
                        if wake_detected:
                            print(f"✓ Wake word detected! (matched: {text})")
                            
                            # Special response for "where are you"
                            if "where are you" in text_lower or "kaha ho" in text_lower or "kahan ho" in text_lower:
                                responses = [
                                    "Mai to apke pass he tha! I am always with you.",
                                    "I am always here with you!",
                                    "Mai yahan hun, apke saath!"
                                ]
                                import random
                                response = random.choice(responses)
                                self.speak(response)
                                
                                # Wait for speech to complete
                                time.sleep(len(response.split()) * 0.3)  # Rough estimate
                            else:
                                self.speak("Yes? How can I help you?")
                                # Wait for speech to complete
                                time.sleep(2)
                            
                            wake_word_mode = False
                            conversation_turns = 0
                            print("✓ Entering conversation mode - I'm listening...")
                            
                            # Extract command after wake word if present
                            wake_word_index = text_lower.find(next((w for w in wake_word_variants if w in text_lower), ""))
                            command_text = text[wake_word_index + len(self.wake_word):].strip() if wake_word_index >= 0 else ""
                            
                            if command_text and len(command_text) > 3:
                                # Process command immediately
                                command = VoiceCommand(
                                    text=command_text,
                                    confidence=0.9,
                                    timestamp=time.time(),
                                    wake_word_detected=True
                                )
                                
                                if self.on_command_callback:
                                    self.on_command_callback(command)
                                
                                conversation_turns += 1
                    else:
                        # In conversation mode - process command
                        command = VoiceCommand(
                            text=text,
                            confidence=0.9,
                            timestamp=time.time(),
                            wake_word_detected=False
                        )
                        
                        if self.on_command_callback:
                            self.on_command_callback(command)
                        
                        conversation_turns += 1
                        
                        # CONTINUOUS CONVERSATION MODE - Never return to wake word mode
                        # User can say "goodbye" or "bye" to exit
                        if any(word in text.lower() for word in ["goodbye", "bye", "exit", "quit", "alvida"]):
                            print(f"✓ Conversation ended. Say 'Hey GURU' to start again.")
                            wake_word_mode = True
                            conversation_turns = 0
                        else:
                            # Stay in conversation mode indefinitely
                            print(f"✓ Waiting for your next command... (turn {conversation_turns})")
                            time.sleep(2)  # Brief pause for GURU to respond
                
                except sr.UnknownValueError:
                    # Speech not understood
                    if not wake_word_mode:
                        print("Could not understand audio")
                        self.speak("I didn't catch that. Could you repeat?")
                        time.sleep(2)
                        # Don't exit conversation mode on misunderstanding
                
                except sr.RequestError as e:
                    print(f"Recognition service error: {e}")
                    self._set_state(VoiceState.ERROR)
                    time.sleep(2)
            
            except sr.WaitTimeoutError:
                # Timeout - continue listening
                # NEVER exit conversation mode on timeout - stay listening
                if not wake_word_mode:
                    print("✓ Still listening...")
                continue
            
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


def create_voice_interface(wake_word: str = "hey guru") -> VoiceInterface:
    """
    Factory function to create voice interface.
    
    Args:
        wake_word: Wake word to activate voice commands
    
    Returns:
        VoiceInterface instance
    """
    return VoiceInterface(wake_word)


# Export
__all__ = ['VoiceInterface', 'VoiceCommand', 'VoiceState', 'create_voice_interface']
