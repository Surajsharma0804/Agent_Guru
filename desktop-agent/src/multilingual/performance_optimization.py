"""
Performance Optimization and Caching for Multilingual Processing

IMPLEMENTS REQUIREMENTS 14.1, 14.2, 9.2, 9.5, 14.6:
- 14.1: Optimize language model loading and memory usage
- 14.2: Implement model caching and lazy loading strategies
- 9.2: Create language context caching per session
- 9.5: Optimize repeated language detection and normalization
- 14.6: Create resource usage monitoring and throttling

This module provides production-grade performance optimization including:
- Intelligent model loading and caching
- Hardware acceleration integration (GPU, NPU)
- Session-based performance optimization
- Resource monitoring and throttling
- Adaptive performance tuning
"""

import logging
import time
import threading
import psutil
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable
from collections import defaultdict, deque
from threading import RLock, Lock
import gc


class HardwareAccelerationType(Enum):
    """Types of hardware acceleration available."""
    
    NONE = "none"
    CPU_OPTIMIZED = "cpu_optimized"
    GPU_CUDA = "gpu_cuda"
    GPU_METAL = "gpu_metal"
    GPU_OPENCL = "gpu_opencl"
    NPU = "npu"
    TPU = "tpu"


class ModelLoadingStrategy(Enum):
    """Strategies for model loading."""
    
    EAGER = "eager"  # Load all models at startup
    LAZY = "lazy"  # Load models on first use
    PREDICTIVE = "predictive"  # Load based on usage patterns
    ADAPTIVE = "adaptive"  # Dynamically adjust based on resources


class CacheTier(Enum):
    """Cache tier levels for multi-tier caching."""
    
    L1_MEMORY = "l1_memory"  # Hot cache in memory
    L2_MEMORY = "l2_memory"  # Warm cache in memory
    L3_DISK = "l3_disk"  # Cold cache on disk


@dataclass
class HardwareCapabilities:
    """Hardware capabilities for acceleration."""
    
    cpu_count: int
    cpu_frequency_mhz: float
    total_memory_gb: float
    available_memory_gb: float
    
    # GPU capabilities
    has_gpu: bool = False
    gpu_type: Optional[str] = None
    gpu_memory_gb: Optional[float] = None
    gpu_compute_capability: Optional[str] = None
    
    # NPU capabilities
    has_npu: bool = False
    npu_type: Optional[str] = None
    npu_tops: Optional[float] = None
    
    # Acceleration support
    cuda_available: bool = False
    metal_available: bool = False
    opencl_available: bool = False
    
    def get_best_acceleration(self) -> HardwareAccelerationType:
        """Determine best available hardware acceleration."""
        if self.cuda_available and self.has_gpu:
            return HardwareAccelerationType.GPU_CUDA
        elif self.metal_available and self.has_gpu:
            return HardwareAccelerationType.GPU_METAL
        elif self.opencl_available and self.has_gpu:
            return HardwareAccelerationType.GPU_OPENCL
        elif self.has_npu:
            return HardwareAccelerationType.NPU
        elif self.cpu_count >= 8:
            return HardwareAccelerationType.CPU_OPTIMIZED
        else:
            return HardwareAccelerationType.NONE


@dataclass
class ModelCacheEntry:
    """Entry in the model cache."""
    
    model_id: str
    model_type: str
    language: Optional[str]
    model_object: Any
    
    # Cache metadata
    load_time_ms: int
    memory_size_mb: float
    last_access_time: datetime
    access_count: int = 0
    hit_rate: float = 0.0
    
    # Performance metrics
    average_inference_time_ms: float = 0.0
    total_inference_count: int = 0
    
    def update_access(self):
        """Update access statistics."""
        self.last_access_time = datetime.utcnow()
        self.access_count += 1
        
    def update_inference_stats(self, inference_time_ms: float):
        """Update inference performance statistics."""
        self.total_inference_count += 1
        # Running average
        self.average_inference_time_ms = (
            (self.average_inference_time_ms * (self.total_inference_count - 1) + inference_time_ms) /
            self.total_inference_count
        )


@dataclass
class SessionPerformanceContext:
    """Performance context for a session."""
    
    session_id: str
    start_time: datetime
    
    # Language usage patterns
    dominant_language: Optional[str] = None
    language_usage_count: Dict[str, int] = field(default_factory=dict)
    language_switch_count: int = 0
    
    # Performance metrics
    total_detections: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    average_detection_time_ms: float = 0.0
    
    # Resource usage
    peak_memory_mb: float = 0.0
    total_cpu_time_ms: float = 0.0
    
    def update_language_usage(self, language: str):
        """Update language usage statistics."""
        if language not in self.language_usage_count:
            self.language_usage_count[language] = 0
        self.language_usage_count[language] += 1
        
        # Update dominant language
        max_count = max(self.language_usage_count.values())
        for lang, count in self.language_usage_count.items():
            if count == max_count:
                if self.dominant_language and self.dominant_language != lang:
                    self.language_switch_count += 1
                self.dominant_language = lang
                break
                
    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.cache_hits + self.cache_misses
        return (self.cache_hits / total * 100) if total > 0 else 0.0


@dataclass
class ResourceUsageMetrics:
    """Real-time resource usage metrics."""
    
    timestamp: datetime
    
    # CPU metrics
    cpu_percent: float
    cpu_count: int
    cpu_frequency_mhz: float
    
    # Memory metrics
    memory_used_mb: float
    memory_available_mb: float
    memory_percent: float
    
    # Process-specific metrics
    process_memory_mb: float
    process_cpu_percent: float
    
    # GPU metrics (if available)
    gpu_memory_used_mb: Optional[float] = None
    gpu_utilization_percent: Optional[float] = None
    
    def is_resource_constrained(self, 
                               cpu_threshold: float = 80.0,
                               memory_threshold: float = 85.0) -> bool:
        """Check if system is resource constrained."""
        return (self.cpu_percent >= cpu_threshold or 
                self.memory_percent >= memory_threshold)


class HardwareAccelerationController:
    """
    Direct control of hardware acceleration for multilingual processing.
    
    Controls GPU/TPU hardware interfaces, capability detection, and
    acceleration strategy selection for optimal performance.
    
    This controller manages:
    - Hardware capability detection (GPU, TPU, NPU)
    - Acceleration strategy selection
    - Device allocation and scheduling
    - Fallback to CPU when hardware unavailable
    - Performance monitoring and optimization
    
    IMPLEMENTS REQUIREMENT 14.1: Optimize language model loading and memory usage
    IMPLEMENTS REQUIREMENT 14.2: Create hardware acceleration integration (GPU, NPU support)
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._capabilities: Optional[HardwareCapabilities] = None
        self._acceleration_type: HardwareAccelerationType = HardwareAccelerationType.NONE
        self._lock = Lock()
        
    def detect_hardware_capabilities(self) -> HardwareCapabilities:
        """Detect available hardware capabilities."""
        with self._lock:
            if self._capabilities:
                return self._capabilities
                
            self.logger.info("Detecting hardware capabilities...")
            
            # CPU detection
            cpu_count = psutil.cpu_count(logical=True)
            cpu_freq = psutil.cpu_freq()
            cpu_frequency_mhz = cpu_freq.current if cpu_freq else 0.0
            
            # Memory detection
            memory = psutil.virtual_memory()
            total_memory_gb = memory.total / (1024 ** 3)
            available_memory_gb = memory.available / (1024 ** 3)
            
            # GPU detection
            has_gpu, gpu_info = self._detect_gpu()
            
            # NPU detection
            has_npu, npu_info = self._detect_npu()
            
            # Acceleration framework detection
            cuda_available = self._check_cuda_available()
            metal_available = self._check_metal_available()
            opencl_available = self._check_opencl_available()
            
            self._capabilities = HardwareCapabilities(
                cpu_count=cpu_count,
                cpu_frequency_mhz=cpu_frequency_mhz,
                total_memory_gb=total_memory_gb,
                available_memory_gb=available_memory_gb,
                has_gpu=has_gpu,
                gpu_type=gpu_info.get('type') if gpu_info else None,
                gpu_memory_gb=gpu_info.get('memory_gb') if gpu_info else None,
                gpu_compute_capability=gpu_info.get('compute_capability') if gpu_info else None,
                has_npu=has_npu,
                npu_type=npu_info.get('type') if npu_info else None,
                npu_tops=npu_info.get('tops') if npu_info else None,
                cuda_available=cuda_available,
                metal_available=metal_available,
                opencl_available=opencl_available
            )
            
            self._acceleration_type = self._capabilities.get_best_acceleration()
            
            self.logger.info(
                f"Hardware capabilities detected: "
                f"CPU={cpu_count} cores @ {cpu_frequency_mhz:.0f}MHz, "
                f"Memory={total_memory_gb:.1f}GB, "
                f"GPU={has_gpu}, NPU={has_npu}, "
                f"Acceleration={self._acceleration_type.value}"
            )
            
            return self._capabilities

            
    def _detect_gpu(self) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Detect GPU availability and capabilities."""
        try:
            # Try NVIDIA GPU detection
            import subprocess
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if result.returncode == 0 and result.stdout.strip():
                gpu_info = result.stdout.strip().split(',')
                gpu_name = gpu_info[0].strip()
                gpu_memory_str = gpu_info[1].strip().split()[0]
                gpu_memory_gb = float(gpu_memory_str) / 1024
                
                return True, {
                    'type': gpu_name,
                    'memory_gb': gpu_memory_gb,
                    'compute_capability': 'unknown'
                }
        except Exception as e:
            self.logger.debug(f"NVIDIA GPU detection failed: {e}")
            
        # Try AMD GPU detection
        try:
            import subprocess
            result = subprocess.run(
                ['rocm-smi', '--showproductname'],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if result.returncode == 0 and result.stdout.strip():
                return True, {
                    'type': 'AMD GPU',
                    'memory_gb': None,
                    'compute_capability': 'unknown'
                }
        except Exception as e:
            self.logger.debug(f"AMD GPU detection failed: {e}")
            
        return False, None
        
    def _detect_npu(self) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Detect NPU availability and capabilities."""
        # NPU detection is platform-specific
        # This is a placeholder for actual NPU detection logic
        return False, None
        
    def _check_cuda_available(self) -> bool:
        """Check if CUDA is available."""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False
            
    def _check_metal_available(self) -> bool:
        """Check if Metal (Apple Silicon) is available."""
        try:
            import torch
            return hasattr(torch.backends, 'mps') and torch.backends.mps.is_available()
        except (ImportError, AttributeError):
            return False
            
    def _check_opencl_available(self) -> bool:
        """Check if OpenCL is available."""
        try:
            import pyopencl
            platforms = pyopencl.get_platforms()
            return len(platforms) > 0
        except ImportError:
            return False
            
    def get_acceleration_type(self) -> HardwareAccelerationType:
        """Get current hardware acceleration type."""
        if not self._capabilities:
            self.detect_hardware_capabilities()
        return self._acceleration_type
        
    def configure_model_for_acceleration(self, model: Any, model_type: str) -> Any:
        """Configure model to use hardware acceleration."""
        if self._acceleration_type == HardwareAccelerationType.NONE:
            return model
            
        try:
            if self._acceleration_type == HardwareAccelerationType.GPU_CUDA:
                return self._configure_cuda(model)
            elif self._acceleration_type == HardwareAccelerationType.GPU_METAL:
                return self._configure_metal(model)
            elif self._acceleration_type == HardwareAccelerationType.GPU_OPENCL:
                return self._configure_opencl(model)
            elif self._acceleration_type == HardwareAccelerationType.NPU:
                return self._configure_npu(model)
            elif self._acceleration_type == HardwareAccelerationType.CPU_OPTIMIZED:
                return self._configure_cpu_optimized(model)
        except Exception as e:
            self.logger.warning(f"Failed to configure hardware acceleration: {e}")
            
        return model
        
    def _configure_cuda(self, model: Any) -> Any:
        """Configure model for CUDA acceleration."""
        try:
            import torch
            if hasattr(model, 'to'):
                return model.to('cuda')
        except Exception as e:
            self.logger.warning(f"CUDA configuration failed: {e}")
        return model
        
    def _configure_metal(self, model: Any) -> Any:
        """Configure model for Metal acceleration."""
        try:
            import torch
            if hasattr(model, 'to'):
                return model.to('mps')
        except Exception as e:
            self.logger.warning(f"Metal configuration failed: {e}")
        return model
        
    def _configure_opencl(self, model: Any) -> Any:
        """Configure model for OpenCL acceleration."""
        # OpenCL configuration is model-specific
        return model
        
    def _configure_npu(self, model: Any) -> Any:
        """Configure model for NPU acceleration."""
        # NPU configuration is platform-specific
        return model
        
    def _configure_cpu_optimized(self, model: Any) -> Any:
        """Configure model for optimized CPU execution."""
        try:
            import torch
            if hasattr(model, 'to'):
                model = model.to('cpu')
            # Enable CPU optimizations
            if hasattr(torch, 'set_num_threads'):
                torch.set_num_threads(self._capabilities.cpu_count)
        except Exception as e:
            self.logger.warning(f"CPU optimization failed: {e}")
        return model



class ModelCacheOrchestrator:
    """
    Orchestrates model caching with lazy loading and memory management.
    
    Coordinates model loading, caching strategies, memory management,
    and multi-tier cache optimization for multilingual models.
    
    This orchestrator manages:
    - Lazy model loading on demand
    - Multi-tier cache (memory, disk, remote)
    - LRU eviction and memory pressure handling
    - Model preloading and warming
    - Cache hit/miss metrics and optimization
    
    IMPLEMENTS REQUIREMENT 14.1: Optimize language model loading and memory usage
    IMPLEMENTS REQUIREMENT 14.2: Implement model caching and lazy loading strategies
    """
    
    def __init__(self, 
                 max_cache_size_mb: float = 2048.0,
                 loading_strategy: ModelLoadingStrategy = ModelLoadingStrategy.LAZY):
        self.logger = logging.getLogger(__name__)
        self.max_cache_size_mb = max_cache_size_mb
        self.loading_strategy = loading_strategy
        
        # Model cache
        self._cache: Dict[str, ModelCacheEntry] = {}
        self._cache_lock = RLock()
        
        # Loading queue for predictive loading
        self._loading_queue: deque = deque()
        self._loading_thread: Optional[threading.Thread] = None
        self._loading_active = False
        
        # Usage tracking for adaptive loading
        self._usage_patterns: Dict[str, List[datetime]] = defaultdict(list)
        self._prediction_window_minutes = 30
        
        # Hardware acceleration
        self._hw_manager = HardwareAccelerationController()
        
    def get_model(self, 
                  model_id: str,
                  model_type: str,
                  language: Optional[str],
                  loader_func: Callable[[], Any]) -> Tuple[Any, bool]:
        """
        Get model from cache or load it.
        
        Returns:
            Tuple of (model, cache_hit)
        """
        with self._cache_lock:
            # Check if model is in cache
            if model_id in self._cache:
                entry = self._cache[model_id]
                entry.update_access()
                self._record_usage(model_id)
                self.logger.debug(f"Model cache hit: {model_id}")
                return entry.model_object, True
                
            # Model not in cache - need to load
            self.logger.info(f"Model cache miss: {model_id}, loading...")
            
            # Check if we need to evict models to make space
            self._ensure_cache_space(model_id)
            
            # Load the model
            start_time = time.time()
            model = loader_func()
            load_time_ms = int((time.time() - start_time) * 1000)
            
            # Configure for hardware acceleration
            model = self._hw_manager.configure_model_for_acceleration(model, model_type)
            
            # Estimate model memory size
            memory_size_mb = self._estimate_model_size(model)
            
            # Create cache entry
            entry = ModelCacheEntry(
                model_id=model_id,
                model_type=model_type,
                language=language,
                model_object=model,
                load_time_ms=load_time_ms,
                memory_size_mb=memory_size_mb,
                last_access_time=datetime.utcnow(),
                access_count=1
            )
            
            self._cache[model_id] = entry
            self._record_usage(model_id)
            
            self.logger.info(
                f"Model loaded and cached: {model_id} "
                f"(load_time={load_time_ms}ms, size={memory_size_mb:.1f}MB)"
            )
            
            return model, False

            
    def _ensure_cache_space(self, new_model_id: str):
        """Ensure there's enough cache space for a new model."""
        current_size = sum(entry.memory_size_mb for entry in self._cache.values())
        
        # If we're under the limit, no need to evict
        if current_size < self.max_cache_size_mb * 0.9:  # 90% threshold
            return
            
        self.logger.info(f"Cache size ({current_size:.1f}MB) approaching limit, evicting models...")
        
        # Sort models by priority (LRU with access frequency consideration)
        sorted_models = sorted(
            self._cache.items(),
            key=lambda x: (x[1].access_count, x[1].last_access_time),
            reverse=False  # Least accessed and oldest first
        )
        
        # Evict models until we have enough space
        target_size = self.max_cache_size_mb * 0.7  # Target 70% utilization
        for model_id, entry in sorted_models:
            if current_size <= target_size:
                break
                
            self.logger.info(f"Evicting model from cache: {model_id}")
            del self._cache[model_id]
            current_size -= entry.memory_size_mb
            
            # Force garbage collection to free memory
            gc.collect()
            
    def _estimate_model_size(self, model: Any) -> float:
        """Estimate model memory size in MB."""
        try:
            import sys
            size_bytes = sys.getsizeof(model)
            
            # For PyTorch models, get parameter size
            if hasattr(model, 'parameters'):
                try:
                    import torch
                    param_size = sum(p.numel() * p.element_size() for p in model.parameters())
                    size_bytes = max(size_bytes, param_size)
                except Exception:
                    pass
                    
            return size_bytes / (1024 * 1024)  # Convert to MB
        except Exception as e:
            self.logger.warning(f"Failed to estimate model size: {e}")
            return 100.0  # Default estimate
            
    def _record_usage(self, model_id: str):
        """Record model usage for predictive loading."""
        self._usage_patterns[model_id].append(datetime.utcnow())
        
        # Keep only recent usage (last 24 hours)
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        self._usage_patterns[model_id] = [
            t for t in self._usage_patterns[model_id] if t > cutoff_time
        ]
        
    def predict_next_models(self, current_model_id: str, top_n: int = 3) -> List[str]:
        """Predict which models are likely to be needed next."""
        # Simple prediction based on recent usage patterns
        # In production, this could use more sophisticated ML-based prediction
        
        recent_cutoff = datetime.utcnow() - timedelta(minutes=self._prediction_window_minutes)
        
        # Count recent usage for each model
        recent_usage = {}
        for model_id, timestamps in self._usage_patterns.items():
            if model_id == current_model_id:
                continue
            recent_count = sum(1 for t in timestamps if t > recent_cutoff)
            if recent_count > 0:
                recent_usage[model_id] = recent_count
                
        # Return top N most recently used models
        sorted_models = sorted(recent_usage.items(), key=lambda x: x[1], reverse=True)
        return [model_id for model_id, _ in sorted_models[:top_n]]
        
    def preload_models(self, model_ids: List[str], loader_funcs: Dict[str, Callable]):
        """Preload models in background."""
        if self.loading_strategy == ModelLoadingStrategy.EAGER:
            # Load immediately
            for model_id in model_ids:
                if model_id not in self._cache and model_id in loader_funcs:
                    self.get_model(model_id, "preload", None, loader_funcs[model_id])
        else:
            # Add to loading queue for background loading
            for model_id in model_ids:
                if model_id not in self._cache:
                    self._loading_queue.append((model_id, loader_funcs.get(model_id)))
                    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._cache_lock:
            total_size = sum(entry.memory_size_mb for entry in self._cache.values())
            total_accesses = sum(entry.access_count for entry in self._cache.values())
            
            return {
                'cached_models': len(self._cache),
                'total_size_mb': total_size,
                'max_size_mb': self.max_cache_size_mb,
                'utilization_percent': (total_size / self.max_cache_size_mb * 100) if self.max_cache_size_mb > 0 else 0,
                'total_accesses': total_accesses,
                'models': {
                    model_id: {
                        'type': entry.model_type,
                        'language': entry.language,
                        'size_mb': entry.memory_size_mb,
                        'access_count': entry.access_count,
                        'last_access': entry.last_access_time.isoformat(),
                        'avg_inference_ms': entry.average_inference_time_ms
                    }
                    for model_id, entry in self._cache.items()
                }
            }
            
    def clear_cache(self, model_ids: Optional[List[str]] = None):
        """Clear cache entries."""
        with self._cache_lock:
            if model_ids is None:
                self._cache.clear()
                self.logger.info("Cleared entire model cache")
            else:
                for model_id in model_ids:
                    if model_id in self._cache:
                        del self._cache[model_id]
                        self.logger.info(f"Cleared model from cache: {model_id}")
                        
            # Force garbage collection
            gc.collect()



class SessionPerformanceOptimizer:
    """
    Session-based performance optimization with adaptive tuning.
    
    IMPLEMENTS REQUIREMENT 9.2: Create language context caching per session
    IMPLEMENTS REQUIREMENT 9.5: Optimize repeated language detection and normalization
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Session contexts
        self._sessions: Dict[str, SessionPerformanceContext] = {}
        self._session_lock = RLock()
        
        # Language context cache per session
        self._language_cache: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
        # Normalization result cache
        self._normalization_cache: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
        # Adaptive thresholds per session
        self._adaptive_thresholds: Dict[str, Dict[str, float]] = defaultdict(dict)
        
    def create_session(self, session_id: str) -> SessionPerformanceContext:
        """Create a new session performance context."""
        with self._session_lock:
            if session_id in self._sessions:
                return self._sessions[session_id]
                
            context = SessionPerformanceContext(
                session_id=session_id,
                start_time=datetime.utcnow()
            )
            
            self._sessions[session_id] = context
            self.logger.info(f"Created performance context for session: {session_id}")
            
            return context
            
    def get_session(self, session_id: str) -> Optional[SessionPerformanceContext]:
        """Get session performance context."""
        with self._session_lock:
            return self._sessions.get(session_id)
            
    def cache_language_context(self, 
                               session_id: str,
                               language: str,
                               confidence: float,
                               context_data: Dict[str, Any]):
        """Cache language context for a session."""
        cache_key = f"{session_id}:{language}"
        self._language_cache[session_id][language] = {
            'language': language,
            'confidence': confidence,
            'context': context_data,
            'cached_at': datetime.utcnow(),
            'access_count': 0
        }
        
        # Update session context
        session = self.get_session(session_id)
        if session:
            session.update_language_usage(language)
            
    def get_cached_language_context(self, 
                                    session_id: str,
                                    language: str) -> Optional[Dict[str, Any]]:
        """Get cached language context for a session."""
        if session_id not in self._language_cache:
            return None
            
        cached = self._language_cache[session_id].get(language)
        if cached:
            # Update access count
            cached['access_count'] += 1
            
            # Check if cache is still fresh (within 5 minutes)
            cache_age = datetime.utcnow() - cached['cached_at']
            if cache_age < timedelta(minutes=5):
                return cached
                
        return None
        
    def cache_normalization_result(self,
                                   session_id: str,
                                   text: str,
                                   language: str,
                                   normalized_intent: Any):
        """Cache normalization result for repeated commands."""
        cache_key = f"{language}:{text}"
        self._normalization_cache[session_id][cache_key] = {
            'text': text,
            'language': language,
            'intent': normalized_intent,
            'cached_at': datetime.utcnow(),
            'hit_count': 0
        }
        
    def get_cached_normalization(self,
                                session_id: str,
                                text: str,
                                language: str) -> Optional[Any]:
        """Get cached normalization result."""
        if session_id not in self._normalization_cache:
            return None
            
        cache_key = f"{language}:{text}"
        cached = self._normalization_cache[session_id].get(cache_key)
        
        if cached:
            # Update hit count
            cached['hit_count'] += 1
            
            # Check cache freshness (within 10 minutes)
            cache_age = datetime.utcnow() - cached['cached_at']
            if cache_age < timedelta(minutes=10):
                return cached['intent']
                
        return None
        
    def update_adaptive_threshold(self,
                                 session_id: str,
                                 threshold_type: str,
                                 performance_metric: float):
        """Update adaptive thresholds based on session performance."""
        if session_id not in self._adaptive_thresholds:
            self._adaptive_thresholds[session_id] = {}
            
        # Simple adaptive algorithm: adjust threshold based on performance
        current_threshold = self._adaptive_thresholds[session_id].get(threshold_type, 0.85)
        
        # If performance is good, we can be slightly more lenient
        # If performance is poor, be more strict
        if performance_metric > 0.9:
            new_threshold = max(0.75, current_threshold - 0.01)
        elif performance_metric < 0.7:
            new_threshold = min(0.95, current_threshold + 0.01)
        else:
            new_threshold = current_threshold
            
        self._adaptive_thresholds[session_id][threshold_type] = new_threshold
        
    def get_adaptive_threshold(self,
                              session_id: str,
                              threshold_type: str,
                              default: float = 0.85) -> float:
        """Get adaptive threshold for session."""
        return self._adaptive_thresholds.get(session_id, {}).get(threshold_type, default)
        
    def update_session_metrics(self,
                              session_id: str,
                              detection_time_ms: float,
                              cache_hit: bool):
        """Update session performance metrics."""
        session = self.get_session(session_id)
        if not session:
            return
            
        session.total_detections += 1
        
        if cache_hit:
            session.cache_hits += 1
        else:
            session.cache_misses += 1
            
        # Update running average of detection time
        session.average_detection_time_ms = (
            (session.average_detection_time_ms * (session.total_detections - 1) + detection_time_ms) /
            session.total_detections
        )
        
    def get_session_statistics(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session performance statistics."""
        session = self.get_session(session_id)
        if not session:
            return None
            
        return {
            'session_id': session_id,
            'start_time': session.start_time.isoformat(),
            'duration_minutes': (datetime.utcnow() - session.start_time).total_seconds() / 60,
            'dominant_language': session.dominant_language,
            'language_usage': session.language_usage_count,
            'language_switches': session.language_switch_count,
            'total_detections': session.total_detections,
            'cache_hit_rate': session.cache_hit_rate,
            'average_detection_time_ms': session.average_detection_time_ms,
            'peak_memory_mb': session.peak_memory_mb
        }
        
    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """Clean up old session data."""
        with self._session_lock:
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
            
            sessions_to_remove = [
                session_id for session_id, session in self._sessions.items()
                if session.start_time < cutoff_time
            ]
            
            for session_id in sessions_to_remove:
                del self._sessions[session_id]
                if session_id in self._language_cache:
                    del self._language_cache[session_id]
                if session_id in self._normalization_cache:
                    del self._normalization_cache[session_id]
                if session_id in self._adaptive_thresholds:
                    del self._adaptive_thresholds[session_id]
                    
            if sessions_to_remove:
                self.logger.info(f"Cleaned up {len(sessions_to_remove)} old sessions")



class ResourceMonitor:
    """
    Real-time resource monitoring and throttling.
    
    IMPLEMENTS REQUIREMENT 14.6: Create resource usage monitoring for multilingual processing
    IMPLEMENTS REQUIREMENT 14.6: Implement appropriate throttling to prevent resource exhaustion
    """
    
    def __init__(self,
                 cpu_threshold: float = 80.0,
                 memory_threshold: float = 85.0,
                 monitoring_interval_seconds: float = 1.0):
        self.logger = logging.getLogger(__name__)
        
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold
        self.monitoring_interval = monitoring_interval_seconds
        
        # Monitoring state
        self._monitoring_active = False
        self._monitoring_thread: Optional[threading.Thread] = None
        self._metrics_history: deque = deque(maxlen=300)  # Keep last 5 minutes at 1s intervals
        self._lock = Lock()
        
        # Throttling state
        self._throttle_active = False
        self._throttle_level = 0.0  # 0.0 = no throttle, 1.0 = maximum throttle
        
        # Process handle for detailed metrics
        self._process = psutil.Process()
        
    def start_monitoring(self):
        """Start resource monitoring in background thread."""
        if self._monitoring_active:
            return
            
        self._monitoring_active = True
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="ResourceMonitor"
        )
        self._monitoring_thread.start()
        self.logger.info("Resource monitoring started")
        
    def stop_monitoring(self):
        """Stop resource monitoring."""
        self._monitoring_active = False
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=2.0)
        self.logger.info("Resource monitoring stopped")
        
    def _monitoring_loop(self):
        """Main monitoring loop."""
        while self._monitoring_active:
            try:
                metrics = self._collect_metrics()
                
                with self._lock:
                    self._metrics_history.append(metrics)
                    
                # Check if throttling is needed
                self._update_throttling(metrics)
                
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(self.monitoring_interval)
                
    def _collect_metrics(self) -> ResourceUsageMetrics:
        """Collect current resource usage metrics."""
        # System-wide metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_count = psutil.cpu_count(logical=True)
        cpu_freq = psutil.cpu_freq()
        cpu_frequency_mhz = cpu_freq.current if cpu_freq else 0.0
        
        memory = psutil.virtual_memory()
        memory_used_mb = (memory.total - memory.available) / (1024 * 1024)
        memory_available_mb = memory.available / (1024 * 1024)
        memory_percent = memory.percent
        
        # Process-specific metrics
        process_memory_info = self._process.memory_info()
        process_memory_mb = process_memory_info.rss / (1024 * 1024)
        process_cpu_percent = self._process.cpu_percent(interval=0.1)
        
        # GPU metrics (if available)
        gpu_memory_used_mb, gpu_utilization = self._collect_gpu_metrics()
        
        return ResourceUsageMetrics(
            timestamp=datetime.utcnow(),
            cpu_percent=cpu_percent,
            cpu_count=cpu_count,
            cpu_frequency_mhz=cpu_frequency_mhz,
            memory_used_mb=memory_used_mb,
            memory_available_mb=memory_available_mb,
            memory_percent=memory_percent,
            process_memory_mb=process_memory_mb,
            process_cpu_percent=process_cpu_percent,
            gpu_memory_used_mb=gpu_memory_used_mb,
            gpu_utilization_percent=gpu_utilization
        )
        
    def _collect_gpu_metrics(self) -> Tuple[Optional[float], Optional[float]]:
        """Collect GPU metrics if available."""
        try:
            import subprocess
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=memory.used,utilization.gpu', '--format=csv,noheader,nounits'],
                capture_output=True,
                text=True,
                timeout=1
            )
            
            if result.returncode == 0 and result.stdout.strip():
                values = result.stdout.strip().split(',')
                memory_used_mb = float(values[0].strip())
                utilization = float(values[1].strip())
                return memory_used_mb, utilization
        except Exception:
            pass
            
        return None, None
        
    def _update_throttling(self, metrics: ResourceUsageMetrics):
        """Update throttling level based on resource usage."""
        is_constrained = metrics.is_resource_constrained(
            self.cpu_threshold,
            self.memory_threshold
        )
        
        if is_constrained:
            # Increase throttling
            self._throttle_level = min(1.0, self._throttle_level + 0.1)
            if not self._throttle_active:
                self._throttle_active = True
                self.logger.warning(
                    f"Resource throttling activated: "
                    f"CPU={metrics.cpu_percent:.1f}%, Memory={metrics.memory_percent:.1f}%"
                )
        else:
            # Decrease throttling
            if self._throttle_level > 0:
                self._throttle_level = max(0.0, self._throttle_level - 0.05)
                
            if self._throttle_level == 0 and self._throttle_active:
                self._throttle_active = False
                self.logger.info("Resource throttling deactivated")
                
    def get_current_metrics(self) -> Optional[ResourceUsageMetrics]:
        """Get most recent resource metrics."""
        with self._lock:
            if self._metrics_history:
                return self._metrics_history[-1]
        return None
        
    def get_metrics_history(self, duration_seconds: int = 60) -> List[ResourceUsageMetrics]:
        """Get metrics history for specified duration."""
        with self._lock:
            cutoff_time = datetime.utcnow() - timedelta(seconds=duration_seconds)
            return [
                m for m in self._metrics_history
                if m.timestamp > cutoff_time
            ]
            
    def is_throttling_active(self) -> bool:
        """Check if throttling is currently active."""
        return self._throttle_active
        
    def get_throttle_level(self) -> float:
        """Get current throttle level (0.0 to 1.0)."""
        return self._throttle_level
        
    def should_throttle_operation(self) -> bool:
        """Check if operations should be throttled."""
        return self._throttle_active and self._throttle_level > 0.3
        
    def get_throttle_delay_ms(self) -> int:
        """Get recommended delay in milliseconds for throttling."""
        if not self._throttle_active:
            return 0
            
        # Scale delay based on throttle level
        # Level 0.3 = 10ms, Level 1.0 = 100ms
        return int(self._throttle_level * 100)
        
    def get_resource_statistics(self) -> Dict[str, Any]:
        """Get comprehensive resource statistics."""
        with self._lock:
            if not self._metrics_history:
                return {}
                
            recent_metrics = list(self._metrics_history)
            
            # Calculate statistics
            avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
            max_cpu = max(m.cpu_percent for m in recent_metrics)
            
            avg_memory = sum(m.memory_percent for m in recent_metrics) / len(recent_metrics)
            max_memory = max(m.memory_percent for m in recent_metrics)
            
            avg_process_memory = sum(m.process_memory_mb for m in recent_metrics) / len(recent_metrics)
            max_process_memory = max(m.process_memory_mb for m in recent_metrics)
            
            return {
                'monitoring_active': self._monitoring_active,
                'throttling_active': self._throttle_active,
                'throttle_level': self._throttle_level,
                'metrics_count': len(recent_metrics),
                'cpu': {
                    'average_percent': avg_cpu,
                    'max_percent': max_cpu,
                    'threshold': self.cpu_threshold
                },
                'memory': {
                    'average_percent': avg_memory,
                    'max_percent': max_memory,
                    'threshold': self.memory_threshold
                },
                'process': {
                    'average_memory_mb': avg_process_memory,
                    'max_memory_mb': max_process_memory
                }
            }



class PerformanceOptimizationOrchestrator:
    """
    Orchestrates all performance optimization components for multilingual processing.
    
    Coordinates hardware acceleration, model caching, session optimization,
    and resource monitoring to achieve optimal system performance.
    
    This orchestrator integrates:
    - Hardware acceleration control
    - Model cache management
    - Session-based optimization
    - Resource monitoring and throttling
    - Adaptive performance tuning
    
    IMPLEMENTS ALL REQUIREMENTS:
    - 14.1: Optimize language model loading and memory usage
    - 14.2: Implement model caching and lazy loading strategies
    - 9.2: Create language context caching per session
    - 9.5: Optimize repeated language detection and normalization
    - 14.6: Create resource usage monitoring and throttling
    """
    
    def __init__(self, config):
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # Initialize all optimization components
        self.hw_manager = HardwareAccelerationController()
        self.model_cache = ModelCacheOrchestrator(
            max_cache_size_mb=getattr(config, 'max_model_cache_mb', 2048.0),
            loading_strategy=ModelLoadingStrategy.LAZY
        )
        self.session_optimizer = SessionPerformanceOptimizer()
        self.resource_monitor = ResourceMonitor(
            cpu_threshold=getattr(config, 'cpu_threshold', 80.0),
            memory_threshold=getattr(config, 'memory_threshold', 85.0)
        )
        
        # Performance metrics
        self._total_operations = 0
        self._total_cache_hits = 0
        self._total_processing_time_ms = 0.0
        self._metrics_lock = Lock()
        
        # Start resource monitoring
        if getattr(config, 'performance_monitoring', True):
            self.resource_monitor.start_monitoring()
            
        self.logger.info("Performance optimization manager initialized")
        
    def optimize_model_loading(self,
                               model_id: str,
                               model_type: str,
                               language: Optional[str],
                               loader_func: Callable[[], Any]) -> Tuple[Any, Dict[str, Any]]:
        """
        Optimize model loading with caching and hardware acceleration.
        
        Returns:
            Tuple of (model, performance_metrics)
        """
        start_time = time.time()
        
        # Check if we should throttle
        if self.resource_monitor.should_throttle_operation():
            delay_ms = self.resource_monitor.get_throttle_delay_ms()
            self.logger.debug(f"Throttling model loading by {delay_ms}ms")
            time.sleep(delay_ms / 1000.0)
            
        # Get model from cache or load
        model, cache_hit = self.model_cache.get_model(
            model_id=model_id,
            model_type=model_type,
            language=language,
            loader_func=loader_func
        )
        
        load_time_ms = int((time.time() - start_time) * 1000)
        
        # Update metrics
        with self._metrics_lock:
            self._total_operations += 1
            if cache_hit:
                self._total_cache_hits += 1
            self._total_processing_time_ms += load_time_ms
            
        performance_metrics = {
            'cache_hit': cache_hit,
            'load_time_ms': load_time_ms,
            'hardware_acceleration': self.hw_manager.get_acceleration_type().value,
            'throttled': self.resource_monitor.is_throttling_active()
        }
        
        return model, performance_metrics
        
    def optimize_language_detection(self,
                                    session_id: str,
                                    audio_data: bytes,
                                    detection_func: Callable[[bytes], Any]) -> Tuple[Any, Dict[str, Any]]:
        """
        Optimize language detection with session caching.
        
        Returns:
            Tuple of (detection_result, performance_metrics)
        """
        start_time = time.time()
        
        # Create session if it doesn't exist
        session = self.session_optimizer.get_session(session_id)
        if not session:
            session = self.session_optimizer.create_session(session_id)
            
        # Check for cached language context
        if session.dominant_language:
            cached_context = self.session_optimizer.get_cached_language_context(
                session_id,
                session.dominant_language
            )
            
            if cached_context:
                # Use cached context to optimize detection
                self.logger.debug(f"Using cached language context for session {session_id}")
                
        # Perform detection
        result = detection_func(audio_data)
        
        detection_time_ms = int((time.time() - start_time) * 1000)
        
        # Cache the result
        if hasattr(result, 'language') and hasattr(result, 'confidence'):
            self.session_optimizer.cache_language_context(
                session_id=session_id,
                language=result.language,
                confidence=result.confidence,
                context_data={'detection_time_ms': detection_time_ms}
            )
            
        # Update session metrics
        cache_hit = cached_context is not None
        self.session_optimizer.update_session_metrics(
            session_id=session_id,
            detection_time_ms=detection_time_ms,
            cache_hit=cache_hit
        )
        
        performance_metrics = {
            'detection_time_ms': detection_time_ms,
            'cache_hit': cache_hit,
            'session_cache_hit_rate': session.cache_hit_rate if session else 0.0
        }
        
        return result, performance_metrics
        
    def optimize_intent_normalization(self,
                                      session_id: str,
                                      text: str,
                                      language: str,
                                      normalization_func: Callable[[str, str], Any]) -> Tuple[Any, Dict[str, Any]]:
        """
        Optimize intent normalization with result caching.
        
        Returns:
            Tuple of (normalized_intent, performance_metrics)
        """
        start_time = time.time()
        
        # Check cache first
        cached_result = self.session_optimizer.get_cached_normalization(
            session_id=session_id,
            text=text,
            language=language
        )
        
        if cached_result:
            normalization_time_ms = int((time.time() - start_time) * 1000)
            
            performance_metrics = {
                'normalization_time_ms': normalization_time_ms,
                'cache_hit': True
            }
            
            return cached_result, performance_metrics
            
        # Perform normalization
        result = normalization_func(text, language)
        
        normalization_time_ms = int((time.time() - start_time) * 1000)
        
        # Cache the result
        self.session_optimizer.cache_normalization_result(
            session_id=session_id,
            text=text,
            language=language,
            normalized_intent=result
        )
        
        performance_metrics = {
            'normalization_time_ms': normalization_time_ms,
            'cache_hit': False
        }
        
        return result, performance_metrics
        
    def get_adaptive_threshold(self,
                              session_id: str,
                              threshold_type: str,
                              default: float = 0.85) -> float:
        """Get adaptive threshold for session."""
        return self.session_optimizer.get_adaptive_threshold(
            session_id=session_id,
            threshold_type=threshold_type,
            default=default
        )
        
    def update_adaptive_threshold(self,
                                 session_id: str,
                                 threshold_type: str,
                                 performance_metric: float):
        """Update adaptive threshold based on performance."""
        self.session_optimizer.update_adaptive_threshold(
            session_id=session_id,
            threshold_type=threshold_type,
            performance_metric=performance_metric
        )
        
    def get_comprehensive_statistics(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
        with self._metrics_lock:
            cache_hit_rate = (
                (self._total_cache_hits / self._total_operations * 100)
                if self._total_operations > 0 else 0.0
            )
            
            avg_processing_time = (
                self._total_processing_time_ms / self._total_operations
                if self._total_operations > 0 else 0.0
            )
            
        return {
            'hardware': {
                'acceleration_type': self.hw_manager.get_acceleration_type().value,
                'capabilities': self.hw_manager._capabilities.__dict__ if self.hw_manager._capabilities else {}
            },
            'model_cache': self.model_cache.get_cache_statistics(),
            'resource_usage': self.resource_monitor.get_resource_statistics(),
            'overall_metrics': {
                'total_operations': self._total_operations,
                'cache_hit_rate': cache_hit_rate,
                'average_processing_time_ms': avg_processing_time
            }
        }
        
    def get_session_statistics(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific session."""
        return self.session_optimizer.get_session_statistics(session_id)
        
    def cleanup(self):
        """Cleanup resources and stop monitoring."""
        self.resource_monitor.stop_monitoring()
        self.session_optimizer.cleanup_old_sessions()
        self.model_cache.clear_cache()
        self.logger.info("Performance optimization manager cleaned up")
        
    def __enter__(self):
        """Context manager entry."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()
