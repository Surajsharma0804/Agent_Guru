"""
Speech transcription module using faster-whisper.

This module contains:
- WhisperTranscriber class for speech-to-text transcription
"""

from typing import Optional
import numpy as np
from faster_whisper import WhisperModel
import soundfile as sf

from .models import TranscriptionResult, TranscriptionSegment
from .exceptions import ModelLoadError, TranscriptionError


class WhisperTranscriber:
    """
    Wraps faster-whisper for optimized speech-to-text transcription.
    """
    
    def __init__(
        self,
        model_size: str = "small",
        model_path: Optional[str] = None,
        compute_type: str = "int8",
        beam_size: int = 5,
        device: str = "cpu"
    ):
        """
        Initialize Whisper transcriber.
        
        Args:
            model_size: Whisper model size ("tiny", "base", "small", "medium", "large")
            model_path: Path to custom model (overrides model_size)
            compute_type: Compute type for inference
            beam_size: Beam size for decoding
            device: Device to run on ("cpu", "cuda")
        """
        self.model_size = model_size
        self.model_path = model_path
        self.compute_type = compute_type
        self.beam_size = beam_size
        self.device = device
        self.model = None
        
        try:
            # Load model from custom path or use default model size
            if model_path:
                self.model = WhisperModel(
                    model_path,
                    device=device,
                    compute_type=compute_type
                )
            else:
                self.model = WhisperModel(
                    model_size,
                    device=device,
                    compute_type=compute_type
                )
        except Exception as e:
            raise ModelLoadError(
                f"Failed to load Whisper model (size={model_size}, compute_type={compute_type})",
                original_error=e
            )
    
    def transcribe(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
        language: Optional[str] = None
    ) -> TranscriptionResult:
        """
        Transcribe audio to text.
        
        Args:
            audio_data: Audio as numpy array
            sample_rate: Sample rate in Hz
            language: Force language (None for auto-detect)
            
        Returns:
            TranscriptionResult with text, language, confidence
        """
        try:
            # Ensure audio is float32 and 1D
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
            
            if len(audio_data.shape) > 1:
                # Convert to mono if stereo
                audio_data = audio_data.mean(axis=1)
            
            # Calculate duration
            duration = len(audio_data) / sample_rate
            
            # Transcribe with faster-whisper
            segments_iter, info = self.model.transcribe(
                audio_data,
                beam_size=self.beam_size,
                language=language
            )
            
            # Collect segments
            segments = []
            full_text = []
            total_confidence = 0.0
            segment_count = 0
            
            for segment in segments_iter:
                segments.append(TranscriptionSegment(
                    text=segment.text,
                    start=segment.start,
                    end=segment.end,
                    confidence=segment.avg_logprob if hasattr(segment, 'avg_logprob') else 0.0
                ))
                full_text.append(segment.text)
                total_confidence += segment.avg_logprob if hasattr(segment, 'avg_logprob') else 0.0
                segment_count += 1
            
            # Calculate average confidence
            avg_confidence = total_confidence / segment_count if segment_count > 0 else 0.0
            # Convert log probability to confidence score (0.0 to 1.0)
            # avg_logprob is typically negative, so we use exp to convert
            confidence = np.exp(avg_confidence) if avg_confidence < 0 else avg_confidence
            confidence = max(0.0, min(1.0, confidence))
            
            # Get detected language
            detected_language = info.language if hasattr(info, 'language') else (language or "unknown")
            
            return TranscriptionResult(
                text=" ".join(full_text).strip(),
                language=detected_language,
                confidence=confidence,
                segments=segments,
                duration=duration
            )
            
        except Exception as e:
            raise TranscriptionError(
                f"Failed to transcribe audio (sample_rate={sample_rate}, duration={len(audio_data)/sample_rate:.2f}s)",
                original_error=e
            )
    
    def transcribe_file(
        self,
        file_path: str,
        language: Optional[str] = None
    ) -> TranscriptionResult:
        """
        Transcribe audio file.
        
        Args:
            file_path: Path to audio file
            language: Force language (None for auto-detect)
            
        Returns:
            TranscriptionResult with text, language, confidence
        """
        try:
            # Load audio file
            audio_data, sample_rate = sf.read(file_path, dtype='float32')
            
            # Transcribe using the array method
            return self.transcribe(audio_data, sample_rate, language)
            
        except Exception as e:
            raise TranscriptionError(
                f"Failed to transcribe file: {file_path}",
                original_error=e
            )
