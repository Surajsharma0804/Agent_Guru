"""
Text-to-Speech Service

Production-grade TTS service with proper threading, queue management,
and error recovery. Handles concurrent speech requests safely.

Uses platform-agnostic PAL SpeechOutput interface for cross-platform compatibility.

Integrates with Response Ownership Coordinator to enforce speech contract:
- During action execution: Only brief action phrases allowed
- During conversation: Full conversational speech allowed
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

# Response ownership imports
from communication.response_ownership import (
    get_response_ownership_coordinator,
    ResponseOwner
)

# Speech contract imports
from communication.speech_contract import (
    get_speech_contract_validator,
    SpeechContext,
    ValidationResult
)


@dataclass(order=True)
class SpeechRequest:
    """
    Speech request with priority.
    
    Uses @dataclass(order=True) to enable comparison for priority queue.
    Comparison is based on field order: priority first, then timestamp.
    """
    # Priority value (negated for correct ordering in min-heap)
    priority_value: int
    # Timestamp for FIFO ordering within same priority
    timestamp: float
    # Text to speak (not used in comparison)
    text: str = ""
    # Original priority enum (not used in comparison)
    priority: TTSPriority = TTSPriority.NORMAL
    # Interrupt flag (not used in comparison)
    interrupt: bool = False


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
        
        # Get response ownership coordinator
        self.ownership_coordinator = get_response_ownership_coordinator()
        
        # Get speech contract validator
        self.speech_validator = get_speech_contract_validator()
        
        # Approved action phrases for speech contract enforcement (DEPRECATED - use validator)
        self.approved_action_phrases = {
            "opening", "opened", "done", "typed", "sent", "failed",
            "searching", "closing", "closed", "starting", "started",
            "stopping", "stopped", "creating", "created", "deleting",
            "deleted", "saving", "saved", "loading", "loaded"
        }
        
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
        
        Enforces speech contract based on response ownership:
        - If Command_Executor owns response: Only action phrases allowed
        - If Conversation_Manager owns response: Full speech allowed
        - If no owner: Full speech allowed
        
        Uses SpeechContractValidator for comprehensive validation.
        
        Algorithm:
            1. Validate text against speech contract
            2. If interrupt flag set, clear queue and stop current speech
            3. Create SpeechRequest with proper ordering fields
            4. Add to priority queue (min-heap with negated priority)
        
        Args:
            text: Text to speak
            priority: Speech priority
            interrupt: Whether to interrupt current speech
        
        Validates: Requirements 28.3, 32.1, 32.2, 32.4, 32.5, 32.6, 32.7
        """
        if not text or not text.strip():
            return
        
        text = text.strip()
        
        # Check response ownership and enforce speech contract
        current_owner = self.ownership_coordinator.get_current_owner()
        
        # Determine speech context based on ownership
        if current_owner == ResponseOwner.COMMAND_EXECUTOR:
            speech_context = SpeechContext.ACTION_EXECUTION
        elif current_owner == ResponseOwner.ERROR_HANDLER:
            speech_context = SpeechContext.ERROR
        else:
            speech_context = SpeechContext.CONVERSATION
        
        # Validate speech against contract
        validation_result = self.speech_validator.validate(text, speech_context)
        
        if not validation_result.is_valid:
            # Speech contract violation - reject
            safe_print(
                f"TTS rejected: '{text[:50]}...' - {validation_result.reason}"
            )
            
            # If there's a suggested alternative, use it
            if validation_result.suggested_alternative:
                safe_print(f"TTS using alternative: '{validation_result.suggested_alternative}'")
                text = validation_result.suggested_alternative
            else:
                # No alternative - suppress speech
                return
        
        # Additional enforcement for action execution context
        if current_owner == ResponseOwner.COMMAND_EXECUTOR:
            # Enforce brevity: ≤ 5 words for action phrases
            word_count = self.speech_validator.get_word_count(text)
            if word_count > 5:
                safe_print(
                    f"TTS truncated: '{text}' exceeds 5 words ({word_count} words)"
                )
                # Truncate to 5 words
                text = self.speech_validator.truncate_to_word_limit(text, 5)
        
        # If interrupt requested, clear queue and stop current speech BEFORE adding new item
        if interrupt:
            self.interrupt_event.set()
            # Clear queue of lower priority items
            self._clear_lower_priority(priority)
        
        # Create request with proper ordering fields
        # Priority queue is a min-heap, so use priority value directly
        # CRITICAL=0 (processed first, highest priority)
        # HIGH=1
        # NORMAL=2
        # LOW=3 (processed last, lowest priority)
        priority_value = priority.value  # Use value directly (no negation)
        timestamp = time.time()
        
        request = SpeechRequest(
            priority_value=priority_value,
            timestamp=timestamp,
            text=text,
            priority=priority,
            interrupt=interrupt
        )
        
        # Add to queue
        self.speech_queue.put(request)
        
        safe_print(f"TTS queued: '{text[:50]}...' (Priority: {priority.name})")
    
    def _clear_lower_priority(self, min_priority: TTSPriority):
        """
        Clear queue items with lower priority than min_priority.
        
        Algorithm:
            1. Create new empty queue
            2. Drain old queue
            3. Keep only items with priority >= min_priority
            4. Replace old queue with new queue
        
        Args:
            min_priority: Minimum priority to keep (items with lower priority are discarded)
        """
        new_queue = queue.PriorityQueue()
        
        while not self.speech_queue.empty():
            try:
                request = self.speech_queue.get_nowait()
                
                # Keep items with equal or higher priority
                # Remember: priority_value is negated, so more negative = higher priority
                # CRITICAL=0 → priority_value=0
                # HIGH=1 → priority_value=-1
                # NORMAL=2 → priority_value=-2
                # LOW=3 → priority_value=-3
                if request.priority.value <= min_priority.value:
                    new_queue.put(request)
            except queue.Empty:
                break
        
        self.speech_queue = new_queue
    
    def _tts_loop(self):
        """
        Main TTS thread loop using PAL SpeechOutput interface.
        
        Algorithm:
            1. Wait for speech request from priority queue (with timeout)
            2. Clear interrupt flag
            3. Synthesize speech using PAL interface
            4. Wait for speech to complete (checking for interrupts)
            5. Repeat until stop requested
        """
        # Main loop
        while self.running and not self.stop_event.is_set():
            try:
                # Get next speech request (with timeout)
                try:
                    request = self.speech_queue.get(timeout=0.5)
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
