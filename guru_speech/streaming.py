"""
Streaming Audio Processing Module

Provides real-time streaming transcription and processing.
"""

import numpy as np
from typing import Optional, Callable, Iterator
from dataclasses import dataclass
from queue import Queue
import threading

from .models import TranscriptionResult
from .exceptions import GuruSpeechError


class StreamingError(GuruSpeechError):
    """Errors related to streaming audio processing."""
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message, "Streaming", original_error)


@dataclass
class StreamingConfig:
    """Configuration for streaming transcription."""
    
    chunk_duration_ms: int = 1000
    """Duration of each audio chunk in milliseconds"""
    
    sample_rate: int = 16000
    """Audio sample rate in Hz"""
    
    buffer_size: int = 5
    """Number of chunks to buffer"""
    
    enable_vad: bool = True
    """Enable voice activity detection"""
    
    silence_threshold: float = 0.01
    """Energy threshold for silence detection"""


class StreamingTranscriber:
    """
    Real-time streaming transcription.
    
    Processes audio in chunks and provides continuous transcription.
    """
    
    def __init__(
        self,
        engine,
        config: Optional[StreamingConfig] = None,
        callback: Optional[Callable[[TranscriptionResult], None]] = None
    ):
        """
        Initialize streaming transcriber.
        
        Args:
            engine: GuruSpeechEngine instance
            config: Streaming configuration
            callback: Optional callback for transcription results
        """
        self.engine = engine
        self.config = config or StreamingConfig()
        self.callback = callback
        
        self.audio_queue: Queue = Queue(maxsize=self.config.buffer_size)
        self.is_streaming = False
        self.stream_thread: Optional[threading.Thread] = None
        
        # Audio buffer for accumulating chunks
        self.audio_buffer = []
        self.buffer_duration = 0.0
    
    def start(self) -> None:
        """Start streaming transcription."""
        if self.is_streaming:
            raise StreamingError("Streaming already active")
        
        self.is_streaming = True
        self.audio_buffer = []
        self.buffer_duration = 0.0
        
        # Start processing thread
        self.stream_thread = threading.Thread(target=self._process_stream)
        self.stream_thread.daemon = True
        self.stream_thread.start()
    
    def stop(self) -> None:
        """Stop streaming transcription."""
        self.is_streaming = False
        
        if self.stream_thread:
            self.stream_thread.join(timeout=2.0)
            self.stream_thread = None
    
    def feed_audio(self, audio_chunk: np.ndarray) -> None:
        """
        Feed audio chunk to the stream.
        
        Args:
            audio_chunk: Audio samples to process
        """
        if not self.is_streaming:
            raise StreamingError("Streaming not active")
        
        try:
            self.audio_queue.put(audio_chunk, timeout=1.0)
        except:
            raise StreamingError("Audio queue full")
    
    def _process_stream(self) -> None:
        """Process audio stream (runs in separate thread)."""
        while self.is_streaming:
            try:
                # Get audio chunk from queue
                audio_chunk = self.audio_queue.get(timeout=0.1)
                
                # Add to buffer
                self.audio_buffer.append(audio_chunk)
                chunk_duration = len(audio_chunk) / self.config.sample_rate
                self.buffer_duration += chunk_duration
                
                # Process when we have enough audio
                min_duration = 2.0  # Minimum 2 seconds for transcription
                
                if self.buffer_duration >= min_duration:
                    # Concatenate buffer
                    audio = np.concatenate(self.audio_buffer)
                    
                    # Check if contains speech (if VAD enabled)
                    if self.config.enable_vad:
                        energy = np.sqrt(np.mean(audio ** 2))
                        if energy < self.config.silence_threshold:
                            # Silence, skip transcription
                            self.audio_buffer = []
                            self.buffer_duration = 0.0
                            continue
                    
                    # Transcribe
                    try:
                        result = self.engine.transcriber.transcribe(
                            audio,
                            self.config.sample_rate
                        )
                        
                        # Call callback if provided
                        if self.callback and result.text.strip():
                            self.callback(result)
                    except Exception as e:
                        print(f"Transcription error: {e}")
                    
                    # Clear buffer
                    self.audio_buffer = []
                    self.buffer_duration = 0.0
            
            except:
                # Timeout or other error, continue
                continue
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


class AudioStreamIterator:
    """
    Iterator for streaming audio from microphone.
    
    Yields audio chunks continuously.
    """
    
    def __init__(
        self,
        chunk_duration_ms: int = 1000,
        sample_rate: int = 16000,
        channels: int = 1
    ):
        """
        Initialize audio stream iterator.
        
        Args:
            chunk_duration_ms: Duration of each chunk in milliseconds
            sample_rate: Sample rate in Hz
            channels: Number of audio channels
        """
        self.chunk_duration_ms = chunk_duration_ms
        self.sample_rate = sample_rate
        self.channels = channels
        
        self.chunk_size = int(sample_rate * chunk_duration_ms / 1000)
        self.stream = None
        self.is_active = False
    
    def start(self) -> None:
        """Start audio capture."""
        import sounddevice as sd
        
        self.audio_queue = Queue()
        
        def audio_callback(indata, frames, time, status):
            if status:
                print(f"Audio callback status: {status}")
            self.audio_queue.put(indata.copy())
        
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            callback=audio_callback,
            blocksize=self.chunk_size
        )
        
        self.stream.start()
        self.is_active = True
    
    def stop(self) -> None:
        """Stop audio capture."""
        self.is_active = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
    
    def __iter__(self) -> Iterator[np.ndarray]:
        """Iterate over audio chunks."""
        if not self.is_active:
            self.start()
        
        while self.is_active:
            try:
                audio_chunk = self.audio_queue.get(timeout=1.0)
                
                # Convert to mono if needed
                if audio_chunk.ndim > 1:
                    audio_chunk = np.mean(audio_chunk, axis=1)
                
                yield audio_chunk.astype(np.float32)
            except:
                continue
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


def stream_transcribe(
    engine,
    duration: Optional[float] = None,
    callback: Optional[Callable[[TranscriptionResult], None]] = None
) -> None:
    """
    Convenience function for streaming transcription.
    
    Args:
        engine: GuruSpeechEngine instance
        duration: Optional duration in seconds (None for continuous)
        callback: Callback for transcription results
    """
    config = StreamingConfig()
    
    with StreamingTranscriber(engine, config, callback) as transcriber:
        with AudioStreamIterator(
            chunk_duration_ms=config.chunk_duration_ms,
            sample_rate=config.sample_rate
        ) as audio_stream:
            
            import time
            start_time = time.time()
            
            for audio_chunk in audio_stream:
                transcriber.feed_audio(audio_chunk)
                
                # Check duration
                if duration and (time.time() - start_time) >= duration:
                    break
