# GPU Setup Guide for Agent Guru

This guide will help you set up GPU acceleration for faster training and inference in Agent Guru.

## Benefits of GPU Acceleration

- **10-50x faster** speech recognition (Whisper with CUDA)
- **5-10x faster** face recognition training
- **3-5x faster** LLM inference (if using local models)
- **Real-time processing** for voice and vision

## Prerequisites

### Hardware Requirements
- NVIDIA GPU with CUDA Compute Capability 3.5 or higher
- Minimum 4GB VRAM (8GB+ recommended)
- Supported GPUs:
  - RTX 30/40 series (recommended)
  - GTX 16 series
  - RTX 20 series
  - Tesla/Quadro series

### Check Your GPU

**Windows:**
```cmd
nvidia-smi
```

**Linux/macOS:**
```bash
nvidia-smi
```

If this command works, you have an NVIDIA GPU installed.

## Installation Steps

### Step 1: Install NVIDIA Drivers

**Windows:**
1. Download from: https://www.nvidia.com/Download/index.aspx
2. Install the latest Game Ready or Studio Driver
3. Restart your computer

**Linux:**
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install nvidia-driver-535

# Arch Linux
sudo pacman -S nvidia nvidia-utils

# Verify installation
nvidia-smi
```

### Step 2: Install CUDA Toolkit

**Windows:**
1. Download CUDA 11.8 or 12.1 from: https://developer.nvidia.com/cuda-downloads
2. Run the installer
3. Add to PATH (installer usually does this automatically)

**Linux:**
```bash
# Ubuntu/Debian (CUDA 11.8)
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-ubuntu2204.pin
sudo mv cuda-ubuntu2204.pin /etc/apt/preferences.d/cuda-repository-pin-600
wget https://developer.download.nvidia.com/compute/cuda/11.8.0/local_installers/cuda-repo-ubuntu2204-11-8-local_11.8.0-520.61.05-1_amd64.deb
sudo dpkg -i cuda-repo-ubuntu2204-11-8-local_11.8.0-520.61.05-1_amd64.deb
sudo cp /var/cuda-repo-ubuntu2204-11-8-local/cuda-*-keyring.gpg /usr/share/keyrings/
sudo apt-get update
sudo apt-get -y install cuda

# Add to PATH
echo 'export PATH=/usr/local/cuda/bin:$PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc
```

**Verify CUDA:**
```bash
nvcc --version
```

### Step 3: Install cuDNN (Optional but Recommended)

1. Register at: https://developer.nvidia.com/cudnn
2. Download cuDNN for your CUDA version
3. Extract and copy files:

**Windows:**
```cmd
# Copy files to CUDA installation directory
# Usually: C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8\
```

**Linux:**
```bash
tar -xzvf cudnn-linux-x86_64-8.x.x.x_cudaX.Y-archive.tar.xz
sudo cp cudnn-*-archive/include/cudnn*.h /usr/local/cuda/include
sudo cp -P cudnn-*-archive/lib/libcudnn* /usr/local/cuda/lib64
sudo chmod a+r /usr/local/cuda/include/cudnn*.h /usr/local/cuda/lib64/libcudnn*
```

### Step 4: Install Python GPU Dependencies

**Activate your virtual environment first:**
```bash
# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

**Install PyTorch with CUDA:**
```bash
# CUDA 11.8
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# CUDA 12.1
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

**Install ONNX Runtime GPU:**
```bash
pip install onnxruntime-gpu
```

**Verify PyTorch GPU:**
```python
import torch
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"CUDA version: {torch.version.cuda}")
print(f"GPU: {torch.cuda.get_device_name(0)}")
print(f"GPU count: {torch.cuda.device_count()}")
```

### Step 5: Build Rust with CUDA Support (Whisper)

**Enable whisper feature in Cargo.toml:**
```toml
[dependencies]
whisper-rs = { version = "0.11", features = ["cuda"] }
```

**Build with CUDA:**
```bash
# Set CUDA path (if not in PATH)
# Windows
set CUDA_PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8

# Linux/macOS
export CUDA_PATH=/usr/local/cuda

# Build
cargo build --release --features whisper
```

## Verification

### Test Python GPU

Create `test_gpu.py`:
```python
import torch
import onnxruntime as ort

print("=== PyTorch GPU Test ===")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"CUDA version: {torch.version.cuda}")
    
    # Test tensor operation
    x = torch.randn(1000, 1000).cuda()
    y = torch.randn(1000, 1000).cuda()
    z = torch.matmul(x, y)
    print("✓ GPU tensor operations working")

print("\n=== ONNX Runtime GPU Test ===")
providers = ort.get_available_providers()
print(f"Available providers: {providers}")
if 'CUDAExecutionProvider' in providers:
    print("✓ ONNX Runtime GPU support enabled")
else:
    print("✗ ONNX Runtime GPU support not available")
```

Run:
```bash
python test_gpu.py
```

### Test Rust GPU (Whisper)

```bash
cargo test --release --features whisper
```

## Performance Benchmarks

### Expected Speedups with GPU

| Component | CPU (i7) | GPU (RTX 3060) | Speedup |
|-----------|----------|----------------|---------|
| Whisper STT | 2.5s | 0.15s | 16x |
| Face Recognition | 150ms | 25ms | 6x |
| Face Training | 4 hours | 45 min | 5.3x |
| LLM Inference | 8s | 1.2s | 6.7x |

## Troubleshooting

### Issue: "CUDA out of memory"

**Solution:**
```python
# Reduce batch size in training
# Clear GPU cache
import torch
torch.cuda.empty_cache()
```

### Issue: "CUDA driver version is insufficient"

**Solution:** Update NVIDIA drivers to latest version

### Issue: "Could not load dynamic library 'cudart64_110.dll'"

**Solution:** 
- Reinstall CUDA Toolkit
- Add CUDA bin directory to PATH
- Restart terminal/IDE

### Issue: "No CUDA GPUs are available"

**Solution:**
```bash
# Check if GPU is detected
nvidia-smi

# Check PyTorch CUDA
python -c "import torch; print(torch.cuda.is_available())"

# Reinstall PyTorch with correct CUDA version
pip uninstall torch torchvision torchaudio
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### Issue: Rust build fails with CUDA

**Solution:**
```bash
# Make sure CUDA_PATH is set
echo $CUDA_PATH  # Linux/macOS
echo %CUDA_PATH%  # Windows

# Try building without CUDA first
cargo build --release

# Then add whisper feature
cargo build --release --features whisper
```

## CPU-Only Alternative

If you don't have a GPU or encounter issues:

**Python:**
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install onnxruntime  # CPU version
```

**Rust:**
```bash
cargo build --release  # Without whisper feature
```

## Monitoring GPU Usage

**During training/inference:**
```bash
# Watch GPU usage in real-time
watch -n 1 nvidia-smi

# Or use
nvidia-smi dmon
```

**In Python:**
```python
import torch

# Check memory usage
print(f"Allocated: {torch.cuda.memory_allocated(0) / 1024**3:.2f} GB")
print(f"Cached: {torch.cuda.memory_reserved(0) / 1024**3:.2f} GB")
```

## Optimization Tips

1. **Use mixed precision training** (FP16) for 2x speedup:
```python
from torch.cuda.amp import autocast, GradScaler

scaler = GradScaler()
with autocast():
    output = model(input)
```

2. **Enable TensorFloat-32** on Ampere GPUs (RTX 30/40):
```python
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True
```

3. **Use DataLoader with pin_memory**:
```python
DataLoader(dataset, batch_size=32, pin_memory=True, num_workers=4)
```

4. **Clear cache between runs**:
```python
torch.cuda.empty_cache()
```

## Next Steps

After GPU setup:
1. Run `python test_gpu.py` to verify installation
2. Start training with GPU acceleration
3. Monitor GPU usage with `nvidia-smi`
4. Adjust batch sizes based on VRAM

## Support

For GPU-related issues:
- Check NVIDIA forums: https://forums.developer.nvidia.com/
- PyTorch forums: https://discuss.pytorch.org/
- CUDA documentation: https://docs.nvidia.com/cuda/

---

Last Updated: February 16, 2026
