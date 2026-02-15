"""
Voice Activity Detection (VAD) Module

Detects speech presence in audio to improve transcription efficiency
and reduce processing of silence.
"""

import numpy as np
from typing import Optional, Tuple
from dataclasses import dataclass

from .exceptions import GuruSpeechError


class VADError(GuruSpeechError):
    """Errors related to voice activity detection."""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message, "VAD", original_error)


@dataclass
class VADResult:
    """Result from voice activity detection."""
    
    is_speech: bool
    """Whether speech was detected"""
    
    confidence: float
    """Confidence score (0.0 to 1.0)"""
    
    speech_probability: float
    """Probability that the audio contains speech"""
    
    energy: float
    """Audio energy level"""


class VoiceActivityDetector:
    """
    Voice Activity Detection using WebRTC VAD or Silero VAD.
    
    Detects speech presence in audio to filter out silence and noise.
    """
    
    def __init__(
        self,
        sample_rate: int = 16000,
        frame_duration_ms: int = 30,
        aggressiveness: int = 2
    ):
        """
        Initialize VAD.
        
        Args:
            sample_rate: Audio sample rate (8000, 16000, 32000, or 48000 Hz)
            frame_duration_ms: Frame duration (10, 20, or 30 ms)
            aggressiveness: VAD aggressiveness (0-3, higher = more aggressive)
        """
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.aggressiveness = aggressiveness
        
        self.vad = None
        self.use_webrtc = False
        self.use_silero = False
        
        # Try to initialize Silero VAD (more accurate)
        try:
            import torch
            torch.set_num_threads(1)
            model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=False
            )
            self.vad = model
            self.use_silero = True
            print("✅ Silero VAD initialized")
        except Exception as e:
            print(f"⚠️  Silero VAD not available: {e}")
            
            # Fallback to WebRTC VAD
            try:
                import webrtcvad
                self.vad = webrtcvad.Vad(aggressiveness)
                self.use_webrtc = True
                print("✅ WebRTC VAD initialized")
            except ImportError:
                print("⚠️  WebRTC VAD not available, using energy-based detection")
        
        # Energy-based fallback parameters
        self.energy_threshold = 0.01
        self.zero_crossing_threshold = 0.1
    
    def is_speech(self, audio_data: np.ndarray) -> VADResult:
        """
        Detect if audio contains speech.
        
        Args:
            audio_data: Audio samples as numpy array (float32, normalized to [-1, 1])
            
        Returns:
            VADResult with detection information
        """
        if self.use_silero:
            return self._detect_with_silero(audio_data)
        elif self.use_webrtc:
            return self._detect_with_webrtc(audio_data)
        else:
            return self._detect_with_energy(audio_data)
    
    def _detect_with_silero(self, audio_data: np.ndarray) -> VADResult:
        """Detect speech using Silero VAD."""
        try:
            import torch
            
            # Ensure audio is float32
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
            
            # Silero VAD requires specific chunk sizes: 512 samples for 16kHz
            required_size = 512 if self.sample_rate == 16000 else 256
            
            # If audio is too short or wrong size, pad or truncate
            if len(audio_data) < required_size:
                audio_data = np.pad(audio_data, (0, required_size - len(audio_data)))
            elif len(audio_data) > required_size:
                # Process in chunks and average
                num_chunks = len(audio_data) // required_size
                probs = []
                for i in range(num_chunks):
                    chunk = audio_data[i*required_size:(i+1)*required_size]
                    audio_tensor = torch.from_numpy(chunk)
                    prob = self.vad(audio_tensor, self.sample_rate).item()
                    probs.append(prob)
                speech_prob = np.mean(probs)
            else:
                # Perfect size
                audio_tensor = torch.from_numpy(audio_data)
                speech_prob = self.vad(audio_tensor, self.sample_rate).item()
            
            # Threshold at 0.5
            is_speech = speech_prob > 0.5
            
            # Calculate energy for additional info
            energy = float(np.sqrt(np.mean(audio_data ** 2)))
            
            return VADResult(
                is_speech=is_speech,
                confidence=speech_prob if is_speech else (1.0 - speech_prob),
                speech_probability=speech_prob,
                energy=energy
            )
        except Exception as e:
            raise VADError(f"Silero VAD processing failed: {e}", e)
    
    def _detect_with_webrtc(self, audio_data: np.ndarray) -> VADResult:
        """Detect speech using WebRTC VAD."""
        try:
            # Convert to int16 for WebRTC VAD
            audio_int16 = (audio_data * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()
            
            # WebRTC VAD requires specific frame sizes
            frame_size = int(self.sample_rate * self.frame_duration_ms / 1000)
            
            # Process frame
            if len(audio_int16) >= frame_size:
                is_speech = self.vad.is_speech(
                    audio_bytes[:frame_size * 2],  # 2 bytes per sample
                    self.sample_rate
                )
            else:
                is_speech = False
            
            # Calculate energy
            energy = float(np.sqrt(np.mean(audio_data ** 2)))
            
            return VADResult(
                is_speech=is_speech,
                confidence=0.8 if is_speech else 0.8,  # WebRTC doesn't provide confidence
                speech_probability=1.0 if is_speech else 0.0,
                energy=energy
            )
        except Exception as e:
            raise VADError(f"WebRTC VAD processing failed: {e}", e)
    
    def _detect_with_energy(self, audio_data: np.ndarray) -> VADResult:
        """
        Fallback energy-based speech detection.
        
        Uses RMS energy and zero-crossing rate as simple speech indicators.
        """
        # Calculate RMS energy
        energy = float(np.sqrt(np.mean(audio_data ** 2)))
        
        # Calculate zero-crossing rate
        zero_crossings = np.sum(np.abs(np.diff(np.sign(audio_data)))) / (2 * len(audio_data))
        
        # Simple heuristic: speech has moderate energy and zero-crossing rate
        is_speech = (
            energy > self.energy_threshold and
            zero_crossings > self.zero_crossing_threshold
        )
        
        # Estimate confidence based on how far above thresholds
        confidence = min(
            energy / (self.energy_threshold * 2),
            zero_crossings / (self.zero_crossing_threshold * 2)
        )
        confidence = max(0.0, min(1.0, confidence))
        
        return VADResult(
            is_speech=is_speech,
            confidence=confidence,
            speech_probability=confidence,
            energy=energy
        )
    
    def filter_silence(
        self,
        audio_data: np.ndarray,
        chunk_duration_ms: int = 30
    ) -> Tuple[np.ndarray, float]:
        """
        Remove silence from audio.
        
        Args:
            audio_data: Audio samples
            chunk_duration_ms: Duration of each chunk to analyze
            
        Returns:
            Tuple of (filtered_audio, speech_ratio)
        """
        chunk_size = int(self.sample_rate * chunk_duration_ms / 1000)
        
        speech_chunks = []
        total_chunks = 0
        speech_chunk_count = 0
        
        # Process audio in chunks
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i + chunk_size]
            
            if len(chunk) < chunk_size:
                # Pad last chunk
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
            
            total_chunks += 1
            
            # Check if chunk contains speech
            result = self.is_speech(chunk)
            
            if result.is_speech:
                speech_chunks.append(audio_data[i:i + chunk_size])
                speech_chunk_count += 1
        
        # Concatenate speech chunks
        if speech_chunks:
            filtered_audio = np.concatenate(speech_chunks)
            speech_ratio = speech_chunk_count / total_chunks
        else:
            filtered_audio = np.array([], dtype=audio_data.dtype)
            speech_ratio = 0.0
        
        return filtered_audio, speech_ratio
