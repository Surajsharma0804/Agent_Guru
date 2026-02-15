"""
Performance Metrics Module

Tracks and reports performance metrics for all voice processing components.
"""

import time
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
import threading


@dataclass
class ComponentMetrics:
    """Metrics for a single component."""
    
    total_calls: int = 0
    total_time_ms: float = 0.0
    min_time_ms: float = float('inf')
    max_time_ms: float = 0.0
    avg_time_ms: float = 0.0
    errors: int = 0
    last_call_time: Optional[datetime] = None


@dataclass
class WakeWordMetrics:
    """Wake word detection metrics."""
    
    total_detections: int = 0
    false_positives: int = 0
    avg_detection_latency_ms: float = 0.0
    cpu_utilization: float = 0.0
    detections_by_word: Dict[str, int] = field(default_factory=dict)


@dataclass
class TranscriptionMetrics:
    """Speech transcription metrics."""
    
    total_transcriptions: int = 0
    avg_processing_time_ms: float = 0.0
    avg_accuracy: float = 0.0
    words_per_minute: float = 0.0
    total_audio_duration_sec: float = 0.0
    languages_detected: Dict[str, int] = field(default_factory=dict)


@dataclass
class TTSMetrics:
    """Text-to-Speech metrics."""
    
    total_syntheses: int = 0
    avg_synthesis_time_ms: float = 0.0
    avg_quality_score: float = 0.0
    chars_per_second: float = 0.0
    total_characters: int = 0


@dataclass
class SystemMetrics:
    """System-wide metrics."""
    
    memory_usage_mb: float = 0.0
    peak_memory_usage_mb: float = 0.0
    avg_cpu_utilization: float = 0.0
    uptime_seconds: float = 0.0
    start_time: datetime = field(default_factory=datetime.now)


class PerformanceMonitor:
    """
    Performance monitoring and metrics collection.
    
    Tracks performance metrics for all voice processing components.
    Thread-safe for concurrent access.
    """
    
    def __init__(self):
        """Initialize performance monitor."""
        self.lock = threading.Lock()
        
        # Component metrics
        self.components: Dict[str, ComponentMetrics] = {}
        
        # Specialized metrics
        self.wake_word = WakeWordMetrics()
        self.transcription = TranscriptionMetrics()
        self.tts = TTSMetrics()
        self.system = SystemMetrics()
        
        # Start time
        self.start_time = time.time()
    
    def start_operation(self, component: str) -> float:
        """
        Start timing an operation.
        
        Args:
            component: Component name
            
        Returns:
            Start timestamp
        """
        return time.time()
    
    def end_operation(
        self,
        component: str,
        start_time: float,
        success: bool = True
    ) -> float:
        """
        End timing an operation and record metrics.
        
        Args:
            component: Component name
            start_time: Start timestamp from start_operation()
            success: Whether operation succeeded
            
        Returns:
            Duration in milliseconds
        """
        duration_ms = (time.time() - start_time) * 1000.0
        
        with self.lock:
            if component not in self.components:
                self.components[component] = ComponentMetrics()
            
            metrics = self.components[component]
            metrics.total_calls += 1
            metrics.total_time_ms += duration_ms
            metrics.min_time_ms = min(metrics.min_time_ms, duration_ms)
            metrics.max_time_ms = max(metrics.max_time_ms, duration_ms)
            metrics.avg_time_ms = metrics.total_time_ms / metrics.total_calls
            metrics.last_call_time = datetime.now()
            
            if not success:
                metrics.errors += 1
        
        return duration_ms
    
    def record_wake_word_detection(
        self,
        wake_word: str,
        latency_ms: float,
        is_false_positive: bool = False
    ) -> None:
        """Record wake word detection event."""
        with self.lock:
            self.wake_word.total_detections += 1
            
            if is_false_positive:
                self.wake_word.false_positives += 1
            
            # Update average latency
            total = self.wake_word.total_detections
            current_avg = self.wake_word.avg_detection_latency_ms
            self.wake_word.avg_detection_latency_ms = (
                (current_avg * (total - 1) + latency_ms) / total
            )
            
            # Track by word
            if wake_word not in self.wake_word.detections_by_word:
                self.wake_word.detections_by_word[wake_word] = 0
            self.wake_word.detections_by_word[wake_word] += 1
    
    def record_transcription(
        self,
        duration_sec: float,
        processing_time_ms: float,
        language: str,
        word_count: int
    ) -> None:
        """Record transcription event."""
        with self.lock:
            self.transcription.total_transcriptions += 1
            self.transcription.total_audio_duration_sec += duration_sec
            
            # Update average processing time
            total = self.transcription.total_transcriptions
            current_avg = self.transcription.avg_processing_time_ms
            self.transcription.avg_processing_time_ms = (
                (current_avg * (total - 1) + processing_time_ms) / total
            )
            
            # Calculate words per minute
            if duration_sec > 0:
                wpm = (word_count / duration_sec) * 60.0
                current_wpm = self.transcription.words_per_minute
                self.transcription.words_per_minute = (
                    (current_wpm * (total - 1) + wpm) / total
                )
            
            # Track languages
            if language not in self.transcription.languages_detected:
                self.transcription.languages_detected[language] = 0
            self.transcription.languages_detected[language] += 1
    
    def record_tts_synthesis(
        self,
        text_length: int,
        synthesis_time_ms: float
    ) -> None:
        """Record TTS synthesis event."""
        with self.lock:
            self.tts.total_syntheses += 1
            self.tts.total_characters += text_length
            
            # Update average synthesis time
            total = self.tts.total_syntheses
            current_avg = self.tts.avg_synthesis_time_ms
            self.tts.avg_synthesis_time_ms = (
                (current_avg * (total - 1) + synthesis_time_ms) / total
            )
            
            # Calculate chars per second
            if synthesis_time_ms > 0:
                cps = (text_length / synthesis_time_ms) * 1000.0
                current_cps = self.tts.chars_per_second
                self.tts.chars_per_second = (
                    (current_cps * (total - 1) + cps) / total
                )
    
    def update_system_metrics(
        self,
        memory_mb: float,
        cpu_percent: float
    ) -> None:
        """Update system-wide metrics."""
        with self.lock:
            self.system.memory_usage_mb = memory_mb
            self.system.peak_memory_usage_mb = max(
                self.system.peak_memory_usage_mb,
                memory_mb
            )
            
            # Update average CPU
            uptime = time.time() - self.start_time
            self.system.uptime_seconds = uptime
            
            # Simple moving average for CPU
            alpha = 0.1  # Smoothing factor
            self.system.avg_cpu_utilization = (
                alpha * cpu_percent +
                (1 - alpha) * self.system.avg_cpu_utilization
            )
    
    def get_component_metrics(self, component: str) -> Optional[ComponentMetrics]:
        """Get metrics for a specific component."""
        with self.lock:
            return self.components.get(component)
    
    def get_all_metrics(self) -> Dict:
        """Get all metrics as a dictionary."""
        with self.lock:
            return {
                "components": {
                    name: {
                        "total_calls": m.total_calls,
                        "avg_time_ms": m.avg_time_ms,
                        "min_time_ms": m.min_time_ms if m.min_time_ms != float('inf') else 0,
                        "max_time_ms": m.max_time_ms,
                        "errors": m.errors,
                        "last_call": m.last_call_time.isoformat() if m.last_call_time else None
                    }
                    for name, m in self.components.items()
                },
                "wake_word": {
                    "total_detections": self.wake_word.total_detections,
                    "false_positives": self.wake_word.false_positives,
                    "avg_latency_ms": self.wake_word.avg_detection_latency_ms,
                    "detections_by_word": self.wake_word.detections_by_word
                },
                "transcription": {
                    "total_transcriptions": self.transcription.total_transcriptions,
                    "avg_processing_time_ms": self.transcription.avg_processing_time_ms,
                    "words_per_minute": self.transcription.words_per_minute,
                    "total_audio_duration_sec": self.transcription.total_audio_duration_sec,
                    "languages_detected": self.transcription.languages_detected
                },
                "tts": {
                    "total_syntheses": self.tts.total_syntheses,
                    "avg_synthesis_time_ms": self.tts.avg_synthesis_time_ms,
                    "chars_per_second": self.tts.chars_per_second,
                    "total_characters": self.tts.total_characters
                },
                "system": {
                    "memory_usage_mb": self.system.memory_usage_mb,
                    "peak_memory_usage_mb": self.system.peak_memory_usage_mb,
                    "avg_cpu_utilization": self.system.avg_cpu_utilization,
                    "uptime_seconds": self.system.uptime_seconds
                }
            }
    
    def print_summary(self) -> None:
        """Print a summary of all metrics."""
        metrics = self.get_all_metrics()
        
        print("\n" + "=" * 60)
        print("GURU SPEECH ENGINE - Performance Metrics")
        print("=" * 60)
        
        print("\nComponent Performance:")
        print("-" * 60)
        for name, m in metrics["components"].items():
            print(f"{name}:")
            print(f"  Calls: {m['total_calls']}")
            print(f"  Avg Time: {m['avg_time_ms']:.2f}ms")
            print(f"  Min/Max: {m['min_time_ms']:.2f}ms / {m['max_time_ms']:.2f}ms")
            print(f"  Errors: {m['errors']}")
        
        print("\nWake Word Detection:")
        print("-" * 60)
        ww = metrics["wake_word"]
        print(f"  Total Detections: {ww['total_detections']}")
        print(f"  False Positives: {ww['false_positives']}")
        print(f"  Avg Latency: {ww['avg_latency_ms']:.2f}ms")
        if ww['detections_by_word']:
            print(f"  By Word: {ww['detections_by_word']}")
        
        print("\nTranscription:")
        print("-" * 60)
        tr = metrics["transcription"]
        print(f"  Total Transcriptions: {tr['total_transcriptions']}")
        print(f"  Avg Processing Time: {tr['avg_processing_time_ms']:.2f}ms")
        print(f"  Words Per Minute: {tr['words_per_minute']:.1f}")
        print(f"  Total Audio Duration: {tr['total_audio_duration_sec']:.1f}s")
        if tr['languages_detected']:
            print(f"  Languages: {tr['languages_detected']}")
        
        print("\nText-to-Speech:")
        print("-" * 60)
        tts = metrics["tts"]
        print(f"  Total Syntheses: {tts['total_syntheses']}")
        print(f"  Avg Synthesis Time: {tts['avg_synthesis_time_ms']:.2f}ms")
        print(f"  Chars Per Second: {tts['chars_per_second']:.1f}")
        print(f"  Total Characters: {tts['total_characters']}")
        
        print("\nSystem:")
        print("-" * 60)
        sys = metrics["system"]
        print(f"  Memory Usage: {sys['memory_usage_mb']:.1f}MB")
        print(f"  Peak Memory: {sys['peak_memory_usage_mb']:.1f}MB")
        print(f"  Avg CPU: {sys['avg_cpu_utilization']:.1f}%")
        print(f"  Uptime: {sys['uptime_seconds']:.1f}s")
        
        print("\n" + "=" * 60)
    
    def reset(self) -> None:
        """Reset all metrics."""
        with self.lock:
            self.components.clear()
            self.wake_word = WakeWordMetrics()
            self.transcription = TranscriptionMetrics()
            self.tts = TTSMetrics()
            self.system = SystemMetrics()
            self.start_time = time.time()


# Global performance monitor instance
_global_monitor: Optional[PerformanceMonitor] = None


def get_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor()
    return _global_monitor


def reset_monitor() -> None:
    """Reset the global performance monitor."""
    global _global_monitor
    if _global_monitor is not None:
        _global_monitor.reset()
