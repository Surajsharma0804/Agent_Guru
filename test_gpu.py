#!/usr/bin/env python3
"""
GPU Setup Verification Script for Agent Guru
Tests PyTorch CUDA, ONNX Runtime GPU, and provides system information
"""

import sys

def test_pytorch_gpu():
    """Test PyTorch CUDA availability and functionality"""
    print("=" * 60)
    print("PyTorch GPU Test")
    print("=" * 60)
    
    try:
        import torch
        
        print(f"PyTorch version: {torch.__version__}")
        print(f"CUDA available: {torch.cuda.is_available()}")
        
        if torch.cuda.is_available():
            print(f"CUDA version: {torch.version.cuda}")
            print(f"cuDNN version: {torch.backends.cudnn.version()}")
            print(f"GPU count: {torch.cuda.device_count()}")
            
            for i in range(torch.cuda.device_count()):
                print(f"\nGPU {i}:")
                print(f"  Name: {torch.cuda.get_device_name(i)}")
                print(f"  Compute Capability: {torch.cuda.get_device_capability(i)}")
                
                # Get memory info
                total_memory = torch.cuda.get_device_properties(i).total_memory / 1024**3
                print(f"  Total Memory: {total_memory:.2f} GB")
                
                # Test tensor operations
                print(f"\n  Testing tensor operations on GPU {i}...")
                torch.cuda.set_device(i)
                
                # Small test
                x = torch.randn(1000, 1000, device=f'cuda:{i}')
                y = torch.randn(1000, 1000, device=f'cuda:{i}')
                z = torch.matmul(x, y)
                
                print(f"  ✓ Matrix multiplication successful")
                
                # Memory usage
                allocated = torch.cuda.memory_allocated(i) / 1024**2
                cached = torch.cuda.memory_reserved(i) / 1024**2
                print(f"  Memory allocated: {allocated:.2f} MB")
                print(f"  Memory cached: {cached:.2f} MB")
                
                # Clear cache
                torch.cuda.empty_cache()
            
            print("\n✅ PyTorch GPU: WORKING")
            return True
        else:
            print("\n⚠️  PyTorch GPU: NOT AVAILABLE")
            print("   CUDA is not available. Using CPU mode.")
            return False
            
    except ImportError:
        print("❌ PyTorch not installed")
        print("   Install with: pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118")
        return False
    except Exception as e:
        print(f"❌ Error testing PyTorch GPU: {e}")
        return False


def test_onnx_runtime_gpu():
    """Test ONNX Runtime GPU support"""
    print("\n" + "=" * 60)
    print("ONNX Runtime GPU Test")
    print("=" * 60)
    
    try:
        import onnxruntime as ort
        
        print(f"ONNX Runtime version: {ort.__version__}")
        
        providers = ort.get_available_providers()
        print(f"Available providers: {providers}")
        
        if 'CUDAExecutionProvider' in providers:
            print("\n✅ ONNX Runtime GPU: WORKING")
            
            # Get CUDA provider options
            cuda_provider_options = ort.get_provider_options('CUDAExecutionProvider')
            print(f"CUDA provider options: {cuda_provider_options}")
            
            return True
        else:
            print("\n⚠️  ONNX Runtime GPU: NOT AVAILABLE")
            print("   Install with: pip install onnxruntime-gpu")
            return False
            
    except ImportError:
        print("❌ ONNX Runtime not installed")
        print("   Install with: pip install onnxruntime-gpu")
        return False
    except Exception as e:
        print(f"❌ Error testing ONNX Runtime GPU: {e}")
        return False


def test_nvidia_smi():
    """Test nvidia-smi availability"""
    print("\n" + "=" * 60)
    print("NVIDIA Driver Test")
    print("=" * 60)
    
    try:
        import subprocess
        
        result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
        
        if result.returncode == 0:
            print(result.stdout)
            print("✅ NVIDIA Driver: WORKING")
            return True
        else:
            print("❌ nvidia-smi failed")
            return False
            
    except FileNotFoundError:
        print("❌ nvidia-smi not found")
        print("   Install NVIDIA drivers from: https://www.nvidia.com/Download/index.aspx")
        return False
    except Exception as e:
        print(f"❌ Error running nvidia-smi: {e}")
        return False


def get_system_info():
    """Get system information"""
    print("\n" + "=" * 60)
    print("System Information")
    print("=" * 60)
    
    import platform
    
    print(f"OS: {platform.system()} {platform.release()}")
    print(f"Architecture: {platform.machine()}")
    print(f"Python version: {sys.version}")
    print(f"Python executable: {sys.executable}")


def main():
    """Main test function"""
    print("\n" + "=" * 60)
    print("Agent Guru - GPU Setup Verification")
    print("=" * 60)
    
    get_system_info()
    
    # Run tests
    nvidia_ok = test_nvidia_smi()
    pytorch_ok = test_pytorch_gpu()
    onnx_ok = test_onnx_runtime_gpu()
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    print(f"NVIDIA Driver:     {'✅ OK' if nvidia_ok else '❌ FAILED'}")
    print(f"PyTorch GPU:       {'✅ OK' if pytorch_ok else '❌ FAILED'}")
    print(f"ONNX Runtime GPU:  {'✅ OK' if onnx_ok else '❌ FAILED'}")
    
    if nvidia_ok and pytorch_ok and onnx_ok:
        print("\n🎉 All GPU tests passed! You're ready to use GPU acceleration.")
        print("\nNext steps:")
        print("  1. Start training with GPU: python examples/train_model.py")
        print("  2. Monitor GPU usage: nvidia-smi")
        print("  3. Check GPU_SETUP.md for optimization tips")
        return 0
    else:
        print("\n⚠️  Some GPU tests failed. See GPU_SETUP.md for troubleshooting.")
        print("\nYou can still use Agent Guru in CPU mode, but it will be slower.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
