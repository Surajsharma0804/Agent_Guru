#!/usr/bin/env python3
"""
GuruVision Installation Verification Script

This script checks that all dependencies are installed correctly,
verifies GPU availability, and tests basic functionality.

Usage:
    python verify_installation.py
"""

import sys
import importlib
import subprocess
from typing import List, Tuple, Dict
import warnings

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Print a formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(70)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ {text}{Colors.RESET}")


def check_python_version() -> bool:
    """Check if Python version is compatible"""
    print_header("Python Version Check")
    
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    
    print_info(f"Python version: {version_str}")
    
    if version.major == 3 and 8 <= version.minor <= 11:
        print_success(f"Python {version_str} is supported (3.8-3.11)")
        return True
    else:
        print_error(f"Python {version_str} is not in the supported range (3.8-3.11)")
        print_warning("GuruVision is tested on Python 3.8-3.11. Recommended: Python 3.10")
        return False


def check_dependencies() -> Tuple[bool, List[str]]:
    """Check if all required dependencies are installed"""
    print_header("Dependency Check")
    
    required_packages = {
        'torch': 'PyTorch',
        'torchvision': 'TorchVision',
        'onnx': 'ONNX',
        'onnxruntime': 'ONNX Runtime',
        'cv2': 'OpenCV (opencv-python)',
        'insightface': 'InsightFace',
        'numpy': 'NumPy',
        'sklearn': 'scikit-learn',
        'PIL': 'Pillow',
        'hypothesis': 'Hypothesis (for testing)',
    }
    
    all_installed = True
    missing_packages = []
    
    for package, name in required_packages.items():
        try:
            mod = importlib.import_module(package)
            version = getattr(mod, '__version__', 'unknown')
            print_success(f"{name}: {version}")
        except ImportError:
            print_error(f"{name}: NOT INSTALLED")
            all_installed = False
            missing_packages.append(package if package != 'cv2' else 'opencv-python')
    
    if not all_installed:
        print_warning("\nMissing packages detected. Install with:")
        print_info(f"pip install {' '.join(missing_packages)}")
    
    return all_installed, missing_packages


def check_gpu_availability() -> Dict[str, any]:
    """Check GPU availability and CUDA support"""
    print_header("GPU Availability Check")
    
    gpu_info = {
        'cuda_available': False,
        'gpu_count': 0,
        'gpu_names': [],
        'onnxruntime_gpu': False
    }
    
    try:
        import torch
        
        gpu_info['cuda_available'] = torch.cuda.is_available()
        
        if gpu_info['cuda_available']:
            gpu_info['gpu_count'] = torch.cuda.device_count()
            gpu_info['gpu_names'] = [torch.cuda.get_device_name(i) for i in range(gpu_info['gpu_count'])]
            
            print_success(f"CUDA is available")
            print_info(f"CUDA version: {torch.version.cuda}")
            print_info(f"Number of GPUs: {gpu_info['gpu_count']}")
            
            for i, name in enumerate(gpu_info['gpu_names']):
                print_info(f"GPU {i}: {name}")
                
                # Check GPU memory
                props = torch.cuda.get_device_properties(i)
                total_memory = props.total_memory / (1024**3)  # Convert to GB
                print_info(f"  Memory: {total_memory:.2f} GB")
        else:
            print_warning("CUDA is not available")
            print_info("GuruVision will run on CPU (slower performance)")
    
    except ImportError:
        print_error("PyTorch not installed - cannot check GPU")
        return gpu_info
    
    # Check ONNX Runtime GPU support
    try:
        import onnxruntime as ort
        
        providers = ort.get_available_providers()
        print_info(f"\nONNX Runtime providers: {', '.join(providers)}")
        
        if 'CUDAExecutionProvider' in providers:
            gpu_info['onnxruntime_gpu'] = True
            print_success("ONNX Runtime GPU support is available")
        else:
            print_warning("ONNX Runtime GPU support not available")
            print_info("Install with: pip install onnxruntime-gpu")
    
    except ImportError:
        print_error("ONNX Runtime not installed")
    
    return gpu_info


def test_basic_functionality() -> bool:
    """Test basic GuruVision functionality"""
    print_header("Basic Functionality Test")
    
    all_tests_passed = True
    
    # Test 1: Import GuruVision modules
    print_info("Test 1: Importing GuruVision modules...")
    try:
        from guru_vision.config import GuruVisionConfig
        from guru_vision.database.face_db import FaceDatabase
        from guru_vision.utils.logging import setup_logging
        print_success("GuruVision modules imported successfully")
    except ImportError as e:
        print_error(f"Failed to import GuruVision modules: {e}")
        all_tests_passed = False
        return all_tests_passed
    
    # Test 2: Create configuration
    print_info("Test 2: Creating configuration...")
    try:
        config = GuruVisionConfig()
        print_success(f"Configuration created with threshold: {config.recognition_threshold}")
    except Exception as e:
        print_error(f"Failed to create configuration: {e}")
        all_tests_passed = False
    
    # Test 3: Initialize database
    print_info("Test 3: Initializing face database...")
    try:
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_db.json")
            db = FaceDatabase(db_path)
            print_success("Face database initialized successfully")
    except Exception as e:
        print_error(f"Failed to initialize database: {e}")
        all_tests_passed = False
    
    # Test 4: Test numpy operations
    print_info("Test 4: Testing numpy operations...")
    try:
        import numpy as np
        
        # Create a dummy embedding
        embedding = np.random.randn(512).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)
        
        # Test cosine similarity
        similarity = np.dot(embedding, embedding)
        
        if 0.99 <= similarity <= 1.01:
            print_success(f"Numpy operations working (self-similarity: {similarity:.4f})")
        else:
            print_error(f"Unexpected similarity value: {similarity}")
            all_tests_passed = False
    except Exception as e:
        print_error(f"Numpy operations failed: {e}")
        all_tests_passed = False
    
    # Test 5: Test OpenCV
    print_info("Test 5: Testing OpenCV...")
    try:
        import cv2
        import numpy as np
        
        # Create a dummy image
        img = np.zeros((112, 112, 3), dtype=np.uint8)
        
        # Test basic operations
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (56, 56))
        
        print_success(f"OpenCV operations working (version: {cv2.__version__})")
    except Exception as e:
        print_error(f"OpenCV operations failed: {e}")
        all_tests_passed = False
    
    # Test 6: Test PyTorch
    print_info("Test 6: Testing PyTorch...")
    try:
        import torch
        
        # Create a dummy tensor
        tensor = torch.randn(1, 3, 112, 112)
        
        # Test basic operations
        output = torch.nn.functional.relu(tensor)
        
        print_success(f"PyTorch operations working (version: {torch.__version__})")
    except Exception as e:
        print_error(f"PyTorch operations failed: {e}")
        all_tests_passed = False
    
    return all_tests_passed


def check_directory_structure() -> bool:
    """Check if required directories exist"""
    print_header("Directory Structure Check")
    
    import os
    
    required_dirs = [
        'guru_vision',
        'guru_vision/detection',
        'guru_vision/alignment',
        'guru_vision/recognition',
        'guru_vision/liveness',
        'guru_vision/emotion',
        'guru_vision/tracking',
        'guru_vision/database',
        'guru_vision/training',
        'guru_vision/utils',
    ]
    
    all_exist = True
    
    for dir_path in required_dirs:
        if os.path.isdir(dir_path):
            print_success(f"{dir_path}/")
        else:
            print_error(f"{dir_path}/ - NOT FOUND")
            all_exist = False
    
    if not all_exist:
        print_warning("\nSome directories are missing. Ensure you're in the project root.")
    
    return all_exist


def print_summary(results: Dict[str, bool]):
    """Print summary of all checks"""
    print_header("Verification Summary")
    
    total_checks = len(results)
    passed_checks = sum(1 for v in results.values() if v)
    
    for check_name, passed in results.items():
        if passed:
            print_success(check_name)
        else:
            print_error(check_name)
    
    print(f"\n{Colors.BOLD}Result: {passed_checks}/{total_checks} checks passed{Colors.RESET}")
    
    if passed_checks == total_checks:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ GuruVision installation is complete and ready to use!{Colors.RESET}\n")
        return True
    else:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠ Some checks failed. Please review the errors above.{Colors.RESET}\n")
        return False


def main():
    """Main verification function"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}GuruVision Installation Verification{Colors.RESET}")
    print(f"{Colors.BLUE}This script will verify your GuruVision installation{Colors.RESET}\n")
    
    results = {}
    
    # Run all checks
    results['Python Version'] = check_python_version()
    
    deps_ok, missing = check_dependencies()
    results['Dependencies'] = deps_ok
    
    gpu_info = check_gpu_availability()
    results['GPU Check'] = True  # GPU is optional, so always pass
    
    results['Directory Structure'] = check_directory_structure()
    
    results['Basic Functionality'] = test_basic_functionality()
    
    # Print summary
    all_passed = print_summary(results)
    
    # Additional recommendations
    if all_passed:
        print_info("Next steps:")
        print("  1. Review the configuration in guru_vision/config.py")
        print("  2. Prepare your training dataset")
        print("  3. Run the training pipeline: python train.py")
        print("  4. Test recognition: python examples/recognize_webcam.py")
    else:
        print_info("Troubleshooting:")
        print("  1. Install missing dependencies")
        print("  2. Ensure you're in the project root directory")
        print("  3. Check Python version compatibility")
        print("  4. Review error messages above")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
