"""
Windows Speech Output Implementation.

Implements SpeechOutput interface using Windows SAPI for text-to-speech
synthesis on Windows 10/11.

Validates: Requirements 36.3, 36.7
"""

import threading
import queue
from typing import Dict
import win32com.client

from ...interfaces import SpeechOutput, TTSPriority


class WindowsSpeechOutput(SpeechOutput):
    """
    Windows implementation of SpeechOutput.
    
    Uses:
        - Windows SAPI (win32com.client.Dispatch("SAPI.SpVoice"))
        - Priority queue for speech ordering
        - Volume bypass to avoid 1% lock
    
    Capabilities:
        - Full speech synthesis
        - Priority queue support
        - Volume control
        - Rate control
    """
    
    def __init__(self):
        """Initialize Windows speech output."""
        self.platform = "windows"
        
        # Initialize SAPI voice
        self.voice = win32com.client.Dispatch("SAPI.SpVoice")
        
        # Set default properties
        self.voice.Volume = 100  # Maximum volume (bypasses Volume Mixer)
        self.voice.Rate = 0      # Normal speed
        
        # Priority queues (one for each priority level)
        self.queues = {
            TTSPriority.CRITICAL: queue.Queue(),
            TTSPriority.HIGH: queue.Queue(),
            TTSPriority.NORMAL: queue.Queue(),
            TTSPriority.LOW: queue.Queue(),
        }
        
        # Control flags
        self._speaking = False
        self._stop_requested = False
        
        # Start TTS thread
        self._tts_thread = threading.Thread(target=self._tts_worker, daemon=True)
        self._tts_thread.start()
    
    def speak(self, text: str, priority: TTSPriority = TTSPriority.NORMAL,
             interrupt: bool = False) -> None:
        """
        Queue text for speech synthesis.
        
        Algorithm:
            1. If interrupt flag set, clear all queues and stop current speech
            2. Add text to appropriate priority queue
            3. TTS worker thread will process queues in priority order
        
        Args:
            text: Text to speak
            priority: Priority level for queue ordering
            interrupt: If True, interrupt current speech
        """
        if interrupt:
            # Clear all queues
            for q in self.queues.values():
                while not q.empty():
                    try:
                        q.get_nowait()
                    except queue.Empty:
                        break
            
            # Stop current speech
            self.stop()
        
        # Add to appropriate queue
        self.queues[priority].put(text)
    
    def stop(self) -> None:
        """
        Stop current speech and clear queue.
        
        Uses SAPI's Skip method to stop immediately.
        """
        try:
            # Skip to end of current utterance (stops immediately)
            self.voice.Skip("Sentence", 999999)
            self._speaking = False
        except Exception as e:
            print(f"Error stopping speech: {e}")
    
    def is_speaking(self) -> bool:
        """
        Check if currently speaking.
        
        Returns:
            True if speech is active, False otherwise
        """
        return self._speaking
    
    def set_volume(self, volume: int) -> None:
        """
        Set volume (0-100).
        
        Windows SAPI volume bypasses Volume Mixer to avoid 1% lock issue.
        
        Args:
            volume: Volume level (0=silent, 100=maximum)
        """
        try:
            # Clamp volume to valid range
            volume = max(0, min(100, volume))
            self.voice.Volume = volume
        except Exception as e:
            print(f"Error setting volume: {e}")
    
    def set_rate(self, rate: int) -> None:
        """
        Set speech rate (-10 to 10).
        
        Args:
            rate: Speech rate (-10=slowest, 0=normal, 10=fastest)
        """
        try:
            # Clamp rate to valid range
            rate = max(-10, min(10, rate))
            self.voice.Rate = rate
        except Exception as e:
            print(f"Error setting rate: {e}")
    
    def get_capabilities(self) -> Dict[str, bool]:
        """Return Windows speech output capabilities."""
        return {
            'has_priority_queue': True,
            'can_interrupt': True,
            'can_control_volume': True,
            'can_control_rate': True,
        }
    
    # ========================================================================
    # Private Methods
    # ========================================================================
    
    def _tts_worker(self):
        """
        TTS worker thread that processes priority queues.
        
        Algorithm:
            1. Check queues in priority order (CRITICAL → HIGH → NORMAL → LOW)
            2. If item found, synthesize speech
            3. Wait for synthesis to complete
            4. Repeat
        """
        while not self._stop_requested:
            text = None
            
            # Check queues in priority order
            for priority in [TTSPriority.CRITICAL, TTSPriority.HIGH, 
                           TTSPriority.NORMAL, TTSPriority.LOW]:
                try:
                    text = self.queues[priority].get(timeout=0.1)
                    break
                except queue.Empty:
                    continue
            
            if text:
                try:
                    self._speaking = True
                    # Speak synchronously (blocks until complete)
                    self.voice.Speak(text, 0)  # 0 = synchronous
                    self._speaking = False
                except Exception as e:
                    print(f"Error in TTS synthesis: {e}")
                    self._speaking = False
    
    def __del__(self):
        """Cleanup on destruction."""
        self._stop_requested = True
        if hasattr(self, '_tts_thread'):
            self._tts_thread.join(timeout=1.0)
