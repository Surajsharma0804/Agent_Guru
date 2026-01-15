"""
Text-to-Speech Service

Production-grade TTS service with proper threading, queue management,
and error recovery. Handles concurrent speech requests safely.

Uses platform-agnostic PAL SpeechOutput interface for cross-platform compatibility.
"""

import threading
import queue
import time
from typing import Optional
from dataclasses import dataclass

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

# PAL imports - platform-agnostic interfaces
from pal.interfaces import SpeechOutput, TTSPriority


@dataclass
class SpeechRequest:
    """Speech request with priority"""
    text: str
    priority: TTSPriority
    interrupt: bool
    timestamp: float


class TTSService:
    """
    Production-grade text-to-speech service using PAL SpeechOutput interface.
    
    Features:
    - Platform-agnostic speech synthesis via PAL
    - Dedicated TTS thread with event loop
    - Priority-based speech queue
    - Interrupt support
    - Automatic error recovery
    - Thread-safe operations
    - Resource cleanup
    
    Architecture:
    - Uses PAL SpeechOutput interface for platform independence
    - Maintains queue management and threading logic
    - Delegates actual speech synthesis to platform-specific backend
    """
    
    def __init__(self, speech_output: SpeechOutput):
        """
        Initialize TTS service with PAL interface.
        
        Args:
            speech_output: Platform-specific SpeechOutput implementation
        """
        self.speech_output = speech_output
        self.available = True  # PAL backends handle availability internally
        self.running = False
        self.speaking = False
        
        # Speech queue with priority
        self.speech_queue: queue.PriorityQueue = queue.PriorityQueue()
        
        # TTS thread
        self.tts_thread: Optional[threading.Thread] = None
        
        # Synchronization
        self.stop_event = threading.Event()
        self.interrupt_event = threading.Event()
        
        # Get platform capabilities
        self.capabilities = speech_output.get_capabilities()
        
        safe_print(f"TTS Service initialized (Platform-agnostic via PAL, Capabilities: {self.capabilities})")
    
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
        """Main TTS thread loop using PAL SpeechOutput interface"""
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
                
                # Speak using PAL interface
                self.speaking = True
                safe_print(f"🔊 Speaking: {request.text}")
                
                try:
                    # Use PAL SpeechOutput interface
                    self.speech_output.speak(
                        text=request.text,
                        priority=request.priority,
                        interrupt=request.interrupt
                    )
                    
                    # Wait for speech to complete
                    while self.speech_output.is_speaking():
                        if self.interrupt_event.is_set():
                            self.speech_output.stop()
                            break
                        time.sleep(0.1)
                
                except Exception as e:
                    safe_print(f"TTS error during speech: {e}")
                
                self.speaking = False
            
            except Exception as e:
                safe_print(f"TTS loop error: {e}")
                time.sleep(0.1)
        
        # Cleanup
        try:
            self.speech_output.stop()
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


def get_tts_service(speech_output: Optional[SpeechOutput] = None) -> TTSService:
    """
    Get global TTS service instance.
    
    Args:
        speech_output: Optional SpeechOutput implementation (creates default if None)
    
    Returns:
        TTSService instance
    
    Note:
        If SpeechOutput interface is provided, a new instance is created.
        If SpeechOutput interface is not provided, returns singleton instance.
    """
    global _tts_service
    
    # If explicit PAL interface provided, create new instance (for testing/DI)
    if speech_output is not None:
        return TTSService(speech_output)
    
    # Otherwise use singleton pattern
    if _tts_service is None:
        from pal.platform_detector import PlatformDetector
        from pal.backend_factory import PlatformBackendFactory
        
        # Detect platform
        platform = PlatformDetector.detect()
        factory = PlatformBackendFactory(platform)
        
        # Create PAL interface
        speech_output = factory.create_speech_output()
        
        _tts_service = TTSService(speech_output)
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
    # Test TTS service with PAL
    from pal.platform_detector import PlatformDetector
    from pal.backend_factory import PlatformBackendFactory
    
    # Create platform-specific backend
    platform = PlatformDetector.detect()
    factory = PlatformBackendFactory(platform)
    speech_output = factory.create_speech_output()
    
    # Create and test service
    service = TTSService(speech_output)
    service.start()
    
    service.speak("Hello! I am GURU, your personal assistant.", TTSPriority.NORMAL)
    time.sleep(3)
    
    service.speak("This is a test of the text to speech service.", TTSPriority.NORMAL)
    time.sleep(3)
    
    service.speak("Urgent message!", TTSPriority.URGENT, interrupt=True)
    time.sleep(2)
    
    service.stop()
    safe_print("Test complete")
