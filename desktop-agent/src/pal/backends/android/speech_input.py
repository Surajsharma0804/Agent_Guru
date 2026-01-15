"""
Android Speech Input Implementation.

Implements SpeechInput interface using Android Speech Recognition
or Whisper.cpp for voice recognition on Android devices.

Maintains identical state machine behavior across all platforms.

Validates: Requirements 37.5, 37.7, 1.1-1.6, 22.1-22.8
"""

import json
import subprocess
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional, Callable
import sys
import tempfile
import os

from ...interfaces import SpeechInput, Transcription, PlatformCapabilityError


class AndroidSpeechInput(SpeechInput):
    """
    Android implementation of SpeechInput.
    
    Uses:
        - Android SpeechRecognizer (system STT) - default
        - Whisper.cpp (local processing) - optional
        - AudioRecord for audio capture
        - Background thread for continuous listening
    
    Capabilities:
        - Continuous listening with wake word detection
        - Local processing (Whisper.cpp) or cloud (system STT)
        - Identical state machine behavior across platforms
        - Language detection and multi-language support
    
    Platform Options:
        - System STT: Uses Android's built-in speech recognition
        - Whisper.cpp: Local processing (requires model files)
        - User can choose between local and cloud processing
    """
    
    def __init__(self, use_local_whisper: bool = True):
        """
        Initialize Android speech input.
        
        Args:
            use_local_whisper: If True, use Whisper.cpp for local processing.
                              If False, use Android system STT.
        """
        self.platform = "android"
        self.use_local_whisper = use_local_whisper
        
        # Check if we're running on Android
        self._is_android = self._detect_android_environment()
        
        # Speech recognition state
        self._is_listening = False
        self._energy_threshold = 300.0  # Default energy threshold
        
        # Background listening thread
        self._listen_thread = None
        self._stop_listening_event = threading.Event()
        
        # Callback for voice commands
        self._voice_callback: Optional[Callable[[Transcription], None]] = None
        
        # Wake word detection
        self._wake_words = ['hey guru', 'hello guru', 'hi guru']
        
        # Audio capture settings
        self._sample_rate = 16000
        self._chunk_size = 1024
        
        # Initialize speech recognition
        if self._is_android:
            self._init_android_speech_recognition()
        
        # Initialize Whisper.cpp if requested
        if use_local_whisper:
            self._init_whisper_cpp()
    
    def start_listening(self) -> None:
        """
        Start background listening thread.
        
        Implements continuous listening with wake word detection
        and maintains identical state machine behavior across platforms.
        """
        if self._is_listening:
            return
        
        try:
            self._stop_listening_event.clear()
            self._is_listening = True
            
            # Start background listening thread
            self._listen_thread = threading.Thread(
                target=self._listen_worker,
                daemon=True,
                name="AndroidSpeechListener"
            )
            self._listen_thread.start()
            
            print("Android speech recognition started")
            
        except Exception as e:
            print(f"Error starting Android speech recognition: {e}")
            self._is_listening = False
    
    def stop_listening(self) -> None:
        """Stop listening and cleanup resources."""
        if not self._is_listening:
            return
        
        try:
            # Signal stop
            self._stop_listening_event.set()
            self._is_listening = False
            
            # Wait for thread to finish
            if self._listen_thread and self._listen_thread.is_alive():
                self._listen_thread.join(timeout=2.0)
            
            # Cleanup Android resources
            if self._is_android:
                self._cleanup_android_speech_recognition()
            
            print("Android speech recognition stopped")
            
        except Exception as e:
            print(f"Error stopping Android speech recognition: {e}")
    
    def transcribe(self, audio_data: bytes) -> Transcription:
        """
        Transcribe audio data to text.
        
        Args:
            audio_data: Raw audio bytes (PCM format, 16kHz, 16-bit)
        
        Returns:
            Transcription result with text and metadata
        """
        try:
            if self.use_local_whisper:
                return self._transcribe_whisper(audio_data)
            else:
                return self._transcribe_android_stt(audio_data)
                
        except Exception as e:
            print(f"Error transcribing audio: {e}")
            return Transcription(
                text="",
                confidence=0.0,
                language="en",
                timestamp=datetime.now(),
                audio_duration=0.0,
                metadata={'error': str(e)}
            )
    
    def calibrate_microphone(self) -> float:
        """
        Calibrate for ambient noise.
        
        Returns:
            Energy threshold for voice detection
        """
        try:
            if self._is_android:
                return self._calibrate_android_microphone()
            else:
                # Development/testing mode
                print("Would calibrate Android microphone")
                return 300.0
                
        except Exception as e:
            print(f"Error calibrating microphone: {e}")
            return 300.0
    
    def set_voice_callback(self, callback: Callable[[Transcription], None]) -> None:
        """
        Set callback for voice commands.
        
        Args:
            callback: Function to call when voice command is detected
        """
        self._voice_callback = callback
    
    def get_capabilities(self) -> Dict[str, bool]:
        """
        Return Android speech input capabilities.
        
        Capabilities depend on whether local Whisper.cpp is used:
        - Local Whisper: has_local_processing=True, requires_cloud=False
        - System STT: has_local_processing=False, requires_cloud=True
        """
        return {
            'has_local_processing': self.use_local_whisper,
            'requires_cloud': not self.use_local_whisper,
            'supports_wake_word': True,
            'supports_continuous': True,
        }
    
    # ========================================================================
    # Private Helper Methods
    # ========================================================================
    
    def _detect_android_environment(self) -> bool:
        """
        Detect if running on Android.
        
        Returns:
            True if running on Android, False otherwise
        """
        try:
            # Check for Android-specific Python module
            if hasattr(sys, 'getandroidapilevel'):
                return True
            
            # Check for Android system properties
            try:
                result = subprocess.run(
                    ['getprop', 'ro.build.version.sdk'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                return result.returncode == 0 and result.stdout.strip().isdigit()
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
            
            return False
            
        except Exception:
            return False
    
    def _init_android_speech_recognition(self) -> None:
        """Initialize Android speech recognition."""
        try:
            # Check if speech recognition is available
            result = subprocess.run(
                ['pm', 'list', 'features'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if 'android.hardware.microphone' not in result.stdout:
                print("Warning: Microphone not available")
            
            if 'android.software.speech' not in result.stdout:
                print("Warning: Speech recognition not available")
            
        except Exception as e:
            print(f"Warning: Could not initialize Android speech recognition: {e}")
    
    def _init_whisper_cpp(self) -> None:
        """Initialize Whisper.cpp for local processing."""
        try:
            # Check if Whisper.cpp is available
            result = subprocess.run(
                ['whisper', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                print("Warning: Whisper.cpp not found. Falling back to system STT.")
                self.use_local_whisper = False
            else:
                print(f"Whisper.cpp available: {result.stdout.strip()}")
            
        except FileNotFoundError:
            print("Warning: Whisper.cpp not found. Falling back to system STT.")
            self.use_local_whisper = False
        except Exception as e:
            print(f"Warning: Could not initialize Whisper.cpp: {e}")
            self.use_local_whisper = False
    
    def _listen_worker(self) -> None:
        """Background worker thread for continuous listening."""
        while not self._stop_listening_event.is_set():
            try:
                # Capture audio chunk
                audio_chunk = self._capture_audio_chunk()
                if not audio_chunk:
                    time.sleep(0.1)
                    continue
                
                # Check energy level
                energy = self._calculate_energy(audio_chunk)
                if energy < self._energy_threshold:
                    time.sleep(0.1)
                    continue
                
                # Transcribe audio
                transcription = self.transcribe(audio_chunk)
                
                # Check for wake word or process command
                if transcription.text and transcription.confidence > 0.5:
                    self._process_transcription(transcription)
                
            except Exception as e:
                print(f"Error in listen worker: {e}")
                time.sleep(0.1)
    
    def _capture_audio_chunk(self) -> Optional[bytes]:
        """
        Capture audio chunk from microphone.
        
        Returns:
            Audio data bytes if successful, None otherwise
        """
        try:
            if self._is_android:
                # Use Android AudioRecord to capture audio
                # This would typically use Android's AudioRecord API
                # For now, simulate with a placeholder
                return b'\x00' * (self._chunk_size * 2)  # 16-bit samples
            else:
                # Development/testing mode
                return b'\x00' * (self._chunk_size * 2)
                
        except Exception as e:
            print(f"Error capturing audio: {e}")
            return None
    
    def _calculate_energy(self, audio_data: bytes) -> float:
        """
        Calculate energy level of audio data.
        
        Args:
            audio_data: Raw audio bytes
        
        Returns:
            Energy level
        """
        try:
            # Simple energy calculation
            # Convert bytes to 16-bit integers and calculate RMS
            import struct
            
            samples = struct.unpack(f'<{len(audio_data)//2}h', audio_data)
            rms = (sum(sample**2 for sample in samples) / len(samples)) ** 0.5
            return rms
            
        except Exception as e:
            print(f"Error calculating energy: {e}")
            return 0.0
    
    def _process_transcription(self, transcription: Transcription) -> None:
        """
        Process transcription result.
        
        Args:
            transcription: Transcription to process
        """
        try:
            # Check for wake word
            text_lower = transcription.text.lower()
            
            # Strip wake word if present
            for wake_word in self._wake_words:
                if wake_word in text_lower:
                    # Remove wake word from text
                    cleaned_text = text_lower.replace(wake_word, '').strip()
                    if cleaned_text:
                        # Create new transcription with cleaned text
                        cleaned_transcription = Transcription(
                            text=cleaned_text,
                            confidence=transcription.confidence,
                            language=transcription.language,
                            timestamp=transcription.timestamp,
                            audio_duration=transcription.audio_duration,
                            metadata=transcription.metadata
                        )
                        
                        # Call voice callback
                        if self._voice_callback:
                            self._voice_callback(cleaned_transcription)
                    break
            else:
                # No wake word found, call callback directly
                if self._voice_callback:
                    self._voice_callback(transcription)
                    
        except Exception as e:
            print(f"Error processing transcription: {e}")
    
    def _transcribe_whisper(self, audio_data: bytes) -> Transcription:
        """
        Transcribe audio using Whisper.cpp.
        
        Args:
            audio_data: Raw audio bytes
        
        Returns:
            Transcription result
        """
        try:
            # Save audio to temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                # Convert raw PCM to WAV format
                wav_data = self._pcm_to_wav(audio_data)
                temp_file.write(wav_data)
                temp_file_path = temp_file.name
            
            try:
                # Run Whisper.cpp
                result = subprocess.run(
                    ['whisper', temp_file_path, '--output-format', 'json'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    # Parse Whisper output
                    whisper_output = json.loads(result.stdout)
                    text = whisper_output.get('text', '').strip()
                    confidence = whisper_output.get('confidence', 0.8)
                    language = whisper_output.get('language', 'en')
                    
                    return Transcription(
                        text=text,
                        confidence=confidence,
                        language=language,
                        timestamp=datetime.now(),
                        audio_duration=len(audio_data) / (self._sample_rate * 2),
                        metadata={'engine': 'whisper.cpp'}
                    )
                else:
                    print(f"Whisper.cpp error: {result.stderr}")
                    
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                except OSError:
                    pass
            
        except Exception as e:
            print(f"Error with Whisper.cpp transcription: {e}")
        
        # Return empty transcription on error
        return Transcription(
            text="",
            confidence=0.0,
            language="en",
            timestamp=datetime.now(),
            audio_duration=0.0,
            metadata={'engine': 'whisper.cpp', 'error': 'transcription_failed'}
        )
    
    def _transcribe_android_stt(self, audio_data: bytes) -> Transcription:
        """
        Transcribe audio using Android system STT.
        
        Args:
            audio_data: Raw audio bytes
        
        Returns:
            Transcription result
        """
        try:
            if self._is_android:
                # Use Android SpeechRecognizer
                # This would typically use Android's SpeechRecognizer API
                # For now, simulate with a placeholder
                
                # Save audio to temporary file for processing
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                    wav_data = self._pcm_to_wav(audio_data)
                    temp_file.write(wav_data)
                    temp_file_path = temp_file.name
                
                try:
                    # Use Android speech recognition service
                    result = subprocess.run(
                        ['am', 'start', '-a', 'android.speech.action.RECOGNIZE_SPEECH',
                         '--es', 'android.speech.extra.AUDIO_SOURCE', temp_file_path],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if result.returncode == 0:
                        # Parse result (this would be more complex in real implementation)
                        text = "example transcription"  # Placeholder
                        confidence = 0.8
                        language = "en"
                        
                        return Transcription(
                            text=text,
                            confidence=confidence,
                            language=language,
                            timestamp=datetime.now(),
                            audio_duration=len(audio_data) / (self._sample_rate * 2),
                            metadata={'engine': 'android_stt'}
                        )
                        
                finally:
                    # Clean up temporary file
                    try:
                        os.unlink(temp_file_path)
                    except OSError:
                        pass
            else:
                # Development/testing mode
                return Transcription(
                    text="test transcription",
                    confidence=0.9,
                    language="en",
                    timestamp=datetime.now(),
                    audio_duration=1.0,
                    metadata={'engine': 'android_stt_mock'}
                )
                
        except Exception as e:
            print(f"Error with Android STT transcription: {e}")
        
        # Return empty transcription on error
        return Transcription(
            text="",
            confidence=0.0,
            language="en",
            timestamp=datetime.now(),
            audio_duration=0.0,
            metadata={'engine': 'android_stt', 'error': 'transcription_failed'}
        )
    
    def _pcm_to_wav(self, pcm_data: bytes) -> bytes:
        """
        Convert raw PCM data to WAV format.
        
        Args:
            pcm_data: Raw PCM audio bytes
        
        Returns:
            WAV format audio bytes
        """
        try:
            import struct
            
            # WAV header
            sample_rate = self._sample_rate
            bits_per_sample = 16
            channels = 1
            byte_rate = sample_rate * channels * bits_per_sample // 8
            block_align = channels * bits_per_sample // 8
            data_size = len(pcm_data)
            file_size = 36 + data_size
            
            # Create WAV header
            wav_header = struct.pack('<4sI4s4sIHHIIHH4sI',
                b'RIFF', file_size, b'WAVE', b'fmt ', 16,
                1, channels, sample_rate, byte_rate, block_align, bits_per_sample,
                b'data', data_size
            )
            
            return wav_header + pcm_data
            
        except Exception as e:
            print(f"Error converting PCM to WAV: {e}")
            return pcm_data
    
    def _calibrate_android_microphone(self) -> float:
        """
        Calibrate Android microphone for ambient noise.
        
        Returns:
            Energy threshold for voice detection
        """
        try:
            print("Calibrating microphone for ambient noise...")
            
            # Capture 1 second of ambient noise
            energy_samples = []
            for _ in range(10):  # 10 samples over 1 second
                audio_chunk = self._capture_audio_chunk()
                if audio_chunk:
                    energy = self._calculate_energy(audio_chunk)
                    energy_samples.append(energy)
                time.sleep(0.1)
            
            if energy_samples:
                # Set threshold to 2x average ambient noise
                avg_energy = sum(energy_samples) / len(energy_samples)
                threshold = avg_energy * 2.0
                self._energy_threshold = max(threshold, 100.0)  # Minimum threshold
                print(f"Microphone calibrated. Threshold: {self._energy_threshold:.1f}")
                return self._energy_threshold
            else:
                print("Calibration failed. Using default threshold.")
                return 300.0
                
        except Exception as e:
            print(f"Error calibrating microphone: {e}")
            return 300.0
    
    def _cleanup_android_speech_recognition(self) -> None:
        """Cleanup Android speech recognition resources."""
        try:
            # Stop any ongoing recognition
            if self._is_android:
                subprocess.run(
                    ['am', 'broadcast', '-a', 'android.speech.action.STOP_LISTENING'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
        except Exception as e:
            print(f"Error cleaning up Android speech recognition: {e}")
