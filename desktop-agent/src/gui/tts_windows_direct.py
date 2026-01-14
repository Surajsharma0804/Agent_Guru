"""
Windows Direct Audio TTS

Alternative TTS implementation that bypasses pyttsx3 volume issues
by using Windows SAPI directly with COM automation.
"""

import sys
import threading
import queue
import time
from typing import Optional
from dataclasses import dataclass
from enum import Enum

try:
    import win32com.client
    SAPI_AVAILABLE = True
except ImportError:
    SAPI_AVAILABLE = False
    print("win32com not available. Install with: pip install pywin32")


class WindowsDirectTTS:
    """
    Direct Windows SAPI TTS that bypasses volume mixer issues.
    
    Uses COM automation to control Windows Speech API directly,
    which respects system volume instead of per-app volume.
    """
    
    def __init__(self):
        self.available = SAPI_AVAILABLE and sys.platform == "win32"
        self.speaking = False
        
        if self.available:
            try:
                # Create SAPI voice object
                self.voice = win32com.client.Dispatch("SAPI.SpVoice")
                
                # Set volume to MAXIMUM (0-100 scale)
                self.voice.Volume = 100
                
                # Set rate (normal speed)
                self.voice.Rate = 0
                
                print(f"[WindowsDirectTTS] Initialized with volume: {self.voice.Volume}")
                
            except Exception as e:
                print(f"[WindowsDirectTTS] Failed to initialize: {e}")
                self.available = False
    
    def speak(self, text: str, wait: bool = False):
        """
        Speak text using Windows SAPI.
        
        Args:
            text: Text to speak
            wait: If True, wait for speech to complete
        """
        if not self.available:
            print(f"[WindowsDirectTTS] Not available: {text}")
            return
        
        try:
            self.speaking = True
            
            if wait:
                # Synchronous speech
                self.voice.Speak(text)
            else:
                # Asynchronous speech (non-blocking)
                self.voice.Speak(text, 1)  # 1 = SVSFlagsAsync
            
            self.speaking = False
            
        except Exception as e:
            print(f"[WindowsDirectTTS] Error speaking: {e}")
            self.speaking = False
    
    def stop(self):
        """Stop current speech"""
        if self.available:
            try:
                self.voice.Speak("", 2)  # 2 = SVSFPurgeBeforeSpeak
            except:
                pass
    
    def is_speaking(self) -> bool:
        """Check if currently speaking"""
        return self.speaking


def test_windows_direct_tts():
    """Test Windows Direct TTS"""
    tts = WindowsDirectTTS()
    
    if not tts.available:
        print("Windows Direct TTS not available")
        return
    
    print("Testing Windows Direct TTS...")
    tts.speak("Hello! This is a test of Windows Direct TTS. Can you hear me?", wait=True)
    print("Test complete")


if __name__ == "__main__":
    test_windows_direct_tts()
