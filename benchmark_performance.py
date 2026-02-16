#!/usr/bin/env python3
"""
GuruVision Performance Benchmarking Script

This script measures system performance including:
- FPS on CPU and GPU
- Memory usage
- Initialization time
- Per-frame latency

Usage:
    python benchmark_performance.py [--config CONFIG_PATH] [--duration SECONDS]
"""

import sys
import time
import argparse
import warnings
from typing import Dict, List, Tuple
import tracemalloc
import psutil
import os

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Print a formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(70)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}\n")


def print_metric(name: str, value: str, unit: str = "", status: str = "info"):
    """Print a metric with formatting"""
    color = Colors.CYAN
    if status == "success":
        color = Colors.GREEN
    elif status == "warning":
        color = Colors.YELLOW
    elif status == "error":
        color = Colors.RED
    
    print(f"{color}{name:.<40} {value:>15} {unit}{Colors.RESET}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ {text}{Colors.RESET}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")


def get_system_info() -> Dict[str, any]:
    """Get system information"""
    print_header("System Information")
    
    import platform
    
    info = {
        'platform': platform.system(),
        'platform_version': platform.version(),
        'processor': platform.processor(),
        'python_version': platform.python_version(),
        'cpu_count': psutil.cpu_count(logical=False),
        'cpu_count_logical': psutil.cpu_count(logical=True),
        'total_memory_gb': psutil.virtual_memory().total / (1024**3),
    }
    
    print_metric("Operating System", info['platform'])
    print_metric("Processor", info['processor'])
    print_metric("Physical CPU Cores", str(info['cpu_count']))
    print_metric("Logical CPU Cores", str(info['cpu_count_logical']))
    print_metric("Total RAM", f"{info['total_memory_gb']:.2f}", "GB")
    print_metric("Python Version", info['python_version'])
    
    # Check GPU
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            print_metric("GPU", gpu_name)
            print_metric("GPU Memory", f"{gpu_memory:.2f}", "GB")
            info['gpu_available'] = True
            info['gpu_name'] = gpu_name
            info['gpu_memory_gb'] = gpu_memory
        else:
            print_metric("GPU", "Not available")
            info['gpu_available'] = False
    except ImportError:
        print_warning("PyTorch not installed - cannot check GPU")
        info['gpu_available'] = False
    
    return info


def benchmark_initialization(config_path: str = None) -> Dict[str, float]:
    """Benchmark system initialization time"""
    print_header("Initialization Benchmark")
    
    results = {}
    
    # Measure import time
    print_info("Measuring import time...")
    start_time = time.time()
    
    try:
        from guru_vision.config import GuruVisionConfig
        from guru_vision.database.face_db import FaceDatabase
        from guru_vision.detection.detector import FaceDetector
        from guru_vision.alignment.aligner import FaceAligner
        from guru_vision.recognition.recognizer import FaceRecognizer
        from guru_vision.liveness.detector import LivenessDetector
        from guru_vision.emotion.recognizer import EmotionRecognizer
        from guru_vision.tracking.tracker import FaceTracker
        
        import_time = time.time() - start_time
        results['import_time'] = import_time
        print_metric("Import Time", f"{import_time:.3f}", "seconds", "success")
    except ImportError as e:
        print_warning(f"Failed to import modules: {e}")
        return results
    
    # Measure configuration loading
    print_info("Measuring configuration loading...")
    start_time = time.time()
    
    try:
        if config_path and os.path.exists(config_path):
            config = GuruVisionConfig.from_file(config_path)
        else:
            config = GuruVisionConfig()
        
        config_time = time.time() - start_time
        results['config_time'] = config_time
        print_metric("Config Load Time", f"{config_time:.3f}", "seconds", "success")
    except Exception as e:
        print_warning(f"Failed to load config: {e}")
        config = GuruVisionConfig()
        results['config_time'] = 0
    
    # Measure database initialization
    print_info("Measuring database initialization...")
    start_time = time.time()
    
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "benchmark_db.json")
            db = FaceDatabase(db_path)
        
        db_time = time.time() - start_time
        results['database_time'] = db_time
        print_metric("Database Init Time", f"{db_time:.3f}", "seconds", "success")
    except Exception as e:
        print_warning(f"Failed to initialize database: {e}")
        results['database_time'] = 0
    
    # Measure model loading (if models exist)
    print_info("Measuring model loading...")
    
    # Check if ONNX model exists
    model_path = config.onnx_model_path
    if os.path.exists(model_path):
        start_time = time.time()
        
        try:
            recognizer = FaceRecognizer(model_path, use_gpu=False)
            model_time = time.time() - start_time
            results['model_load_time'] = model_time
            print_metric("Model Load Time (CPU)", f"{model_time:.3f}", "seconds", "success")
            
            # Try GPU if available
            try:
                import torch
                if torch.cuda.is_available():
                    start_time = time.time()
                    recognizer_gpu = FaceRecognizer(model_path, use_gpu=True)
                    model_time_gpu = time.time() - start_time
                    results['model_load_time_gpu'] = model_time_gpu
                    print_metric("Model Load Time (GPU)", f"{model_time_gpu:.3f}", "seconds", "success")
            except Exception as e:
                print_warning(f"GPU model loading failed: {e}")
        except Exception as e:
            print_warning(f"Failed to load model: {e}")
            results['model_load_time'] = 0
    else:
        print_warning(f"Model not found at {model_path}")
        print_info("Run training first: python train.py")
        results['model_load_time'] = 0
    
    # Calculate total initialization time
    total_time = sum(results.values())
    results['total_init_time'] = total_time
    
    print_metric("Total Init Time", f"{total_time:.3f}", "seconds", 
                 "success" if total_time < 5.0 else "warning")
    
    # Check against requirement (< 5 seconds)
    if total_time < 5.0:
        print_success(f"Initialization time meets requirement (< 5 seconds)")
    else:
        print_warning(f"Initialization time exceeds requirement (< 5 seconds)")
    
    return results


def benchmark_memory_usage(duration: int = 10) -> Dict[str, float]:
    """Benchmark memory usage during operation"""
    print_header("Memory Usage Benchmark")
    
    results = {}
    
    # Get baseline memory
    process = psutil.Process(os.getpid())
    baseline_memory = process.memory_info().rss / (1024**2)  # MB
    
    print_metric("Baseline Memory", f"{baseline_memory:.2f}", "MB")
    
    # Start memory tracking
    tracemalloc.start()
    
    try:
        from guru_vision.config import GuruVisionConfig
        from guru_vision.database.face_db import FaceDatabase
        import numpy as np
        import tempfile
        
        # Create temporary database
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "benchmark_db.json")
            db = FaceDatabase(db_path)
            
            # Simulate adding identities
            print_info(f"Simulating identity additions for {duration} seconds...")
            
            start_time = time.time()
            identity_count = 0
            
            while time.time() - start_time < duration:
                # Create dummy embeddings
                embeddings = [np.random.randn(512).astype(np.float32) for _ in range(5)]
                embeddings = [e / np.linalg.norm(e) for e in embeddings]
                
                # Add identity
                db.add_identity(
                    name=f"person_{identity_count}",
                    embeddings=embeddings,
                    permission_level="user",
                    metadata={}
                )
                
                identity_count += 1
                
                # Check memory periodically
                if identity_count % 10 == 0:
                    current_memory = process.memory_info().rss / (1024**2)
                    print(f"  Identities: {identity_count}, Memory: {current_memory:.2f} MB", end='\r')
            
            print()  # New line after progress
            
            # Get final memory
            final_memory = process.memory_info().rss / (1024**2)
            memory_used = final_memory - baseline_memory
            
            results['baseline_memory_mb'] = baseline_memory
            results['final_memory_mb'] = final_memory
            results['memory_used_mb'] = memory_used
            results['identities_added'] = identity_count
            results['memory_per_identity_kb'] = (memory_used * 1024) / identity_count if identity_count > 0 else 0
            
            print_metric("Final Memory", f"{final_memory:.2f}", "MB")
            print_metric("Memory Used", f"{memory_used:.2f}", "MB")
            print_metric("Identities Added", str(identity_count))
            print_metric("Memory per Identity", f"{results['memory_per_identity_kb']:.2f}", "KB")
            
            # Check against requirement (< 4GB)
            if final_memory < 4096:
                print_success(f"Memory usage meets requirement (< 4GB)")
            else:
                print_warning(f"Memory usage exceeds requirement (< 4GB)")
    
    except Exception as e:
        print_warning(f"Memory benchmark failed: {e}")
    
    finally:
        # Stop memory tracking
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        results['peak_memory_mb'] = peak / (1024**2)
        print_metric("Peak Traced Memory", f"{results['peak_memory_mb']:.2f}", "MB")
    
    return results


def benchmark_fps(use_gpu: bool = False, duration: int = 10) -> Dict[str, float]:
    """Benchmark frames per second"""
    device_name = "GPU" if use_gpu else "CPU"
    print_header(f"FPS Benchmark ({device_name})")
    
    results = {}
    
    try:
        from guru_vision.detection.detector import FaceDetector
        from guru_vision.alignment.aligner import FaceAligner
        import numpy as np
        import cv2
        
        # Check if GPU is available
        if use_gpu:
            import torch
            if not torch.cuda.is_available():
                print_warning("GPU not available, skipping GPU benchmark")
                return results
        
        # Initialize components
        print_info("Initializing components...")
        detector = FaceDetector(use_gpu=use_gpu)
        aligner = FaceAligner()
        
        # Create synthetic frames
        print_info(f"Generating synthetic frames for {duration} seconds...")
        
        frame_count = 0
        total_detection_time = 0
        total_alignment_time = 0
        
        start_time = time.time()
        
        while time.time() - start_time < duration:
            # Generate random frame
            frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            
            # Add synthetic face (simple rectangle)
            cv2.rectangle(frame, (200, 150), (440, 330), (255, 255, 255), -1)
            
            # Measure detection time
            det_start = time.time()
            detections = detector.detect(frame)
            det_time = time.time() - det_start
            total_detection_time += det_time
            
            # Measure alignment time (if faces detected)
            if detections:
                align_start = time.time()
                for detection in detections:
                    try:
                        aligned = aligner.align(frame, detection)
                    except:
                        pass
                align_time = time.time() - align_start
                total_alignment_time += align_time
            
            frame_count += 1
            
            # Print progress
            if frame_count % 10 == 0:
                elapsed = time.time() - start_time
                current_fps = frame_count / elapsed
                print(f"  Frames: {frame_count}, FPS: {current_fps:.2f}", end='\r')
        
        print()  # New line after progress
        
        # Calculate metrics
        elapsed_time = time.time() - start_time
        fps = frame_count / elapsed_time
        avg_detection_time = (total_detection_time / frame_count) * 1000  # ms
        avg_alignment_time = (total_alignment_time / frame_count) * 1000 if frame_count > 0 else 0  # ms
        avg_frame_time = (elapsed_time / frame_count) * 1000  # ms
        
        results['fps'] = fps
        results['frame_count'] = frame_count
        results['elapsed_time'] = elapsed_time
        results['avg_detection_time_ms'] = avg_detection_time
        results['avg_alignment_time_ms'] = avg_alignment_time
        results['avg_frame_time_ms'] = avg_frame_time
        
        print_metric("Total Frames", str(frame_count))
        print_metric("Elapsed Time", f"{elapsed_time:.2f}", "seconds")
        print_metric("FPS", f"{fps:.2f}", "fps", 
                     "success" if (use_gpu and fps >= 30) or (not use_gpu and fps >= 10) else "warning")
        print_metric("Avg Detection Time", f"{avg_detection_time:.2f}", "ms")
        print_metric("Avg Alignment Time", f"{avg_alignment_time:.2f}", "ms")
        print_metric("Avg Frame Time", f"{avg_frame_time:.2f}", "ms")
        
        # Check against requirements
        if use_gpu:
            if fps >= 30:
                print_success(f"GPU FPS meets requirement (>= 30 fps)")
            else:
                print_warning(f"GPU FPS below requirement (>= 30 fps)")
        else:
            if fps >= 10:
                print_success(f"CPU FPS meets requirement (>= 10 fps)")
            else:
                print_warning(f"CPU FPS below requirement (>= 10 fps)")
    
    except Exception as e:
        print_warning(f"FPS benchmark failed: {e}")
        import traceback
        traceback.print_exc()
    
    return results


def print_summary(init_results: Dict, memory_results: Dict, 
                  cpu_fps_results: Dict, gpu_fps_results: Dict):
    """Print summary of all benchmarks"""
    print_header("Benchmark Summary")
    
    print(f"\n{Colors.BOLD}Initialization:{Colors.RESET}")
    if 'total_init_time' in init_results:
        total_init = init_results['total_init_time']
        status = "✓" if total_init < 5.0 else "⚠"
        print(f"  {status} Total: {total_init:.3f}s (requirement: < 5s)")
    
    print(f"\n{Colors.BOLD}Memory Usage:{Colors.RESET}")
    if 'final_memory_mb' in memory_results:
        final_mem = memory_results['final_memory_mb']
        status = "✓" if final_mem < 4096 else "⚠"
        print(f"  {status} Peak: {final_mem:.2f} MB (requirement: < 4096 MB)")
    
    print(f"\n{Colors.BOLD}Performance:{Colors.RESET}")
    if 'fps' in cpu_fps_results:
        cpu_fps = cpu_fps_results['fps']
        status = "✓" if cpu_fps >= 10 else "⚠"
        print(f"  {status} CPU FPS: {cpu_fps:.2f} (requirement: >= 10 fps)")
    
    if 'fps' in gpu_fps_results:
        gpu_fps = gpu_fps_results['fps']
        status = "✓" if gpu_fps >= 30 else "⚠"
        print(f"  {status} GPU FPS: {gpu_fps:.2f} (requirement: >= 30 fps)")
    
    print()


def main():
    """Main benchmarking function"""
    parser = argparse.ArgumentParser(description='GuruVision Performance Benchmark')
    parser.add_argument('--config', type=str, help='Path to configuration file')
    parser.add_argument('--duration', type=int, default=10, 
                        help='Duration for each benchmark in seconds (default: 10)')
    parser.add_argument('--skip-gpu', action='store_true', 
                        help='Skip GPU benchmarks')
    
    args = parser.parse_args()
    
    print(f"\n{Colors.BOLD}{Colors.BLUE}GuruVision Performance Benchmark{Colors.RESET}")
    print(f"{Colors.BLUE}This will measure system performance and resource usage{Colors.RESET}\n")
    
    # Get system info
    system_info = get_system_info()
    
    # Run benchmarks
    init_results = benchmark_initialization(args.config)
    
    memory_results = benchmark_memory_usage(args.duration)
    
    cpu_fps_results = benchmark_fps(use_gpu=False, duration=args.duration)
    
    gpu_fps_results = {}
    if not args.skip_gpu and system_info.get('gpu_available', False):
        gpu_fps_results = benchmark_fps(use_gpu=True, duration=args.duration)
    
    # Print summary
    print_summary(init_results, memory_results, cpu_fps_results, gpu_fps_results)
    
    print_info("Benchmark complete!")
    print_info("Note: Results may vary based on system load and configuration")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
