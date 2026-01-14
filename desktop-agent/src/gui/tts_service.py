"""
Text-to-Speech Service

Production-grade TTS service with proper threading, queue management,
and error recovery. Handles concurrent speech requests safely.

Uses Windows SAPI directly via COM automation to bypass volume mixer issues.
"""

import sys
import threading
import queue
import time
from typing import Optional
from dataclasses import dataclass
from enum import Enum

# Import console utilities for cross-platform Unicode support
try:
    from utils.console import safe_print
except ImportError:
    def safe_print(text, **kwargs):
        try:
            print(text, **kwargs)
        except UnicodeEncodeError:
            text = str(text).replace('✓', '[OK]').replace('✗', '[X]').replace('⚠', '[!]').replace('🔊', '[SPEAK]')
            print(text, **kwargs)

# Try Windows Direct TTS first (bypasses volume mixer issues)
WINDOWS_DIRECT_TTS = False
if sys.platform == "win32":
    try:
        import win32com.client
        WINDOWS_DIRECT_TTS = True
        safe_print("[TTS] Using Windows Direct SAPI (bypasses volume mixer)")
    except ImportError:
        safe_print("[TTS] pywin32 not available, falling back to pyttsx3")

# Fallback to pyttsx3
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False


class TTSPriority(Enum):
    """Speech priority levels"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


@dataclass
class SpeechRequest:
    """Speech request with priority"""
    text: str
    priority: TTSPriority
    interrupt: bool
    timestamp: float


class TTSService:
    """
    Production-grade text-to-speech service.
    
    Features:
    - Dedicated TTS thread with event loop
    - Priority-based speech queue
    - Interrupt support
    - Automatic error recovery
    - Thread-safe operations
    - Resource cleanup
    """
    
    def __init__(self):
        """Initialize TTS service"""
        self.available = WINDOWS_DIRECT_TTS or PYTTSX3_AVAILABLE
        self.use_windows_direct = WINDOWS_DIRECT_TTS
        self.running = False
        self.speaking = False
        
        # Speech queue with priority
        self.speech_queue: queue.PriorityQueue = queue.PriorityQueue()
        
        # TTS thread
        self.tts_thread: Optional[threading.Thread] = None
        
        # Synchronization
        self.stop_event = threading.Event()
        self.interrupt_event = threading.Event()
        
        # Windows Direct TTS voice object (created in TTS thread)
        self.windows_voice = None
        
        safe_print(f"TTS Service initialized (Available: {self.available}, Method: {'Windows SAPI' if self.use_windows_direct else 'pyttsx3'})")
    
    def start(self):
        """Start TTS service"""
        if not self.available:
            safe_print("TTS not available - service will print text instead")
            return
        
        if self.running:
            return
        
        self.running = True
        self.stop_event.clear()
        
        self.tts_thread = threading.Thread(target=self._tts_loop, daemon=True)
        self.tts_thread.start()
        
        safe_print("✓ TTS Service started")
    
    def stop(self):
        """Stop TTS service"""
        if not self.running:
            return
        
        self.running = False
        self.stop_event.set()
        
        if self.tts_thread:
            self.tts_thread.join(timeout=2.0)
        
        safe_print("✓ TTS Service stopped")
    
    def speak(self, text: str, priority: TTSPriority = TTSPriority.NORMAL, interrupt: bool = False):
        """
        Queue text for speech.
        
        Args:
            text: Text to speak
            priority: Speech priority
            interrupt: Whether to interrupt current speech
        """
        if not text or not text.strip():
            return
        
        request = SpeechRequest(
            text=text.strip(),
            priority=priority,
            interrupt=interrupt,
            timestamp=time.time()
        )
        
        # If interrupt requested, signal current speech to stop
        if interrupt:
            self.interrupt_event.set()
            # Clear queue of lower priority items
            self._clear_lower_priority(priority)
        
        # Add to queue (priority queue uses tuple: (priority_value, timestamp, request))
        # Lower priority value = higher priority
        priority_value = -priority.value  # Negate so higher enum value = higher priority
        self.speech_queue.put((priority_value, request.timestamp, request))
        
        safe_print(f"TTS queued: '{text[:50]}...' (Priority: {priority.name})")
    
    def _clear_lower_priority(self, min_priority: TTSPriority):
        """Clear queue items with lower priority"""
        new_queue = queue.PriorityQueue()
        
        while not self.speech_queue.empty():
            try:
                item = self.speech_queue.get_nowait()
                priority_value, timestamp, request = item
                
                # Keep items with equal or higher priority
                if -priority_value >= min_priority.value:
                    new_queue.put(item)
            except queue.Empty:
                break
        
        self.speech_queue = new_queue
    
    def _tts_loop(self):
        """Main TTS thread loop"""
        # Initialize COM for this thread (CRITICAL for Windows SAPI)
        if self.use_windows_direct:
            try:
                import pythoncom
                pythoncom.CoInitialize()
                safe_print("✓ COM initialized for TTS thread")
            except Exception as e:
                safe_print(f"⚠ COM initialization warning: {e}")
        
        # Create TTS engine in this thread
        try:
            if self.use_windows_direct:
                # Use Windows SAPI directly
                import win32com.client
                self.windows_voice = win32com.client.Dispatch("SAPI.SpVoice")
                self.windows_voice.Volume = 100  # Maximum volume
                self.windows_voice.Rate = 0  # Normal speed
                safe_print("✓ Windows SAPI voice initialized (volume: 100)")
            else:
                # Use pyttsx3
                engine = pyttsx3.init()
                
                # Configure voice
                voices = engine.getProperty('voices')
                for voice in voices:
                    if 'female' in voice.name.lower() or 'zira' in voice.name.lower():
                        engine.setProperty('voice', voice.id)
                        break
                
                # Set volume to MAXIMUM
                engine.setProperty('volume', 1.0)
                engine.setProperty('rate', 175)
                
                safe_print("✓ pyttsx3 engine initialized")
        
        except Exception as e:
            safe_print(f"✗ Failed to initialize TTS engine: {e}")
            self.available = False
            return
        
        # Main loop
        while self.running and not self.stop_event.is_set():
            try:
                # Get next speech request (with timeout)
                try:
                    priority_value, timestamp, request = self.speech_queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                
                # Clear interrupt flag
                self.interrupt_event.clear()
                
                # Speak
                self.speaking = True
                safe_print(f"🔊 Speaking: {request.text}")
                
                try:
                    if self.use_windows_direct:
                        # Windows SAPI - asynchronous
                        self.windows_voice.Speak(request.text, 1)  # 1 = SVSFlagsAsync
                        
                        # Wait for speech to complete
                        while self.windows_voice.Status.RunningState == 2:  # 2 = SRSEIsSpeaking
                            if self.interrupt_event.is_set():
                                self.windows_voice.Speak("", 2)  # 2 = SVSFPurgeBeforeSpeak
                                break
                            time.sleep(0.1)
                    else:
                        # pyttsx3
                        interrupted = False
                        
                        def on_word(name, location, length):
                            nonlocal interrupted
                            if self.interrupt_event.is_set():
                                interrupted = True
                                engine.stop()
                        
                        engine.connect('started-word', on_word)
                        engine.say(request.text)
                        engine.runAndWait()
                
                except Exception as e:
                    safe_print(f"TTS error during speech: {e}")
                
                self.speaking = False
            
            except Exception as e:
                safe_print(f"TTS loop error: {e}")
                time.sleep(0.1)
        
        # Cleanup
        try:
            if self.use_windows_direct:
                self.windows_voice = None
                # Uninitialize COM for this thread
                try:
                    import pythoncom
                    pythoncom.CoUninitialize()
                    safe_print("✓ COM uninitialized for TTS thread")
                except:
                    pass
            else:
                engine.stop()
        except:
            pass
        
        safe_print("TTS thread exiting")
    
    def is_speaking(self) -> bool:
        """Check if currently speaking"""
        return self.speaking
    
    def clear_queue(self):
        """Clear all pending speech"""
        while not self.speech_queue.empty():
            try:
                self.speech_queue.get_nowait()
            except queue.Empty:
                break
        
        self.interrupt_event.set()
        safe_print("TTS queue cleared")


# Global TTS service instance
_tts_service: Optional[TTSService] = None


def get_tts_service() -> TTSService:
    """Get global TTS service instance"""
    global _tts_service
    if _tts_service is None:
        _tts_service = TTSService()
        _tts_service.start()
    return _tts_service


def speak(text: str, priority: TTSPriority = TTSPriority.NORMAL, interrupt: bool = False):
    """
    Convenience function to speak text.
    
    Args:
        text: Text to speak
        priority: Speech priority
        interrupt: Whether to interrupt current speech
    """
    service = get_tts_service()
    service.speak(text, priority, interrupt)


def stop_speaking():
    """Stop current speech"""
    service = get_tts_service()
    service.clear_queue()


if __name__ == "__main__":
    # Test TTS service
    service = TTSService()
    service.start()
    
    service.speak("Hello! I am GURU, your personal assistant.", TTSPriority.NORMAL)
    time.sleep(3)
    
    service.speak("This is a test of the text to speech service.", TTSPriority.NORMAL)
    time.sleep(3)
    
    service.speak("Urgent message!", TTSPriority.URGENT, interrupt=True)
    time.sleep(2)
    
    service.stop()
    safe_print("Test complete")
