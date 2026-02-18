# CUDA Setup Guide for Agent Guru Training

## GPU Requirements

**Minimum Requirements:**
- NVIDIA GPU with 4GB+ VRAM (RTX 2050, GTX 1650, or better)
- CUDA 11.8 or CUDA 12.1
- Windows 10/11, Linux, or macOS (with NVIDIA GPU)

**Recommended:**
- NVIDIA GPU with 8GB+ VRAM (RTX 3060, RTX 4060, or better)
- CUDA 12.1
- 16GB+ System RAM

## Current Setup Status

✅ **GPU Detected**: NVIDIA GeForce RTX 2050 (4GB VRAM)
✅ **CUDA Version**: 11.8
✅ **PyTorch**: Installed with CUDA 11.8 support
✅ **Status**: Ready for training

## Installation Steps

### 1. Check NVIDIA Driver

```bash
nvidia-smi
```

You should see your GPU listed with driver version and CUDA version.

### 2. Install PyTorch with CUDA Support

**For CUDA 11.8 (Current Setup):**
```bash
pip uninstall torch torchvision torchaudio
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

**For CUDA 12.1:**
```bash
pip uninstall torch torchvision torchaudio
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### 3. Verify CUDA Installation

```bash
python -c "import torch; print('CUDA Available:', torch.cuda.is_available()); print('CUDA Version:', torch.version.cuda); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"
```

Expected output:
```
CUDA Available: True
CUDA Version: 11.8
GPU: NVIDIA GeForce RTX 2050
```

### 4. Install Training Dependencies

```bash
pip install -r Agent_Guru/reasoning/requirements-training.txt
```

## Training Configuration for 4GB VRAM

The training scripts are optimized for 4GB VRAM:

**Intent Classifier (DeBERTa-v3-large):**
- Batch size: 2
- Gradient accumulation: 16 steps (effective batch 32)
- Mixed precision: Enabled (FP16)
- Max sequence length: 256

**NER Model (GLiNER):**
- Batch size: 4
- Gradient accumulation: 8 steps (effective batch 32)
- Mixed precision: Enabled (FP16)
- Max sequence length: 384

## Performance Optimization

### 1. Enable Mixed Precision Training

Already enabled in training scripts. Provides:
- 2x faster training
- 50% less memory usage
- Same accuracy

### 2. Gradient Accumulation

Simulates larger batch sizes without memory overhead:
- Small batch size (2-4) fits in VRAM
- Accumulate gradients over multiple steps
- Update weights after N steps

### 3. Memory Management

```python
# Clear CUDA cache between training runs
import torch
torch.cuda.empty_cache()
```

### 4. Monitor GPU Usage

```bash
# Watch GPU usage in real-time
nvidia-smi -l 1
```

## Troubleshooting

### Issue: CUDA Out of Memory

**Solution 1: Reduce batch size**
```python
config.batch_size = 1  # Reduce from 2 to 1
```

**Solution 2: Reduce sequence length**
```python
config.max_length = 128  # Reduce from 256 to 128
```

**Solution 3: Clear cache**
```python
import torch
torch.cuda.empty_cache()
```

### Issue: CUDA Not Available

**Check PyTorch installation:**
```bash
python -c "import torch; print(torch.__version__)"
```

Should show `+cu118` or `+cu121` suffix.

**Reinstall PyTorch with CUDA:**
```bash
pip uninstall torch torchvision torchaudio
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### Issue: Slow Training

**Enable mixed precision:**
```python
config.mixed_precision = True  # Should be enabled by default
```

**Check GPU utilization:**
```bash
nvidia-smi
```

GPU utilization should be >80% during training.

### Issue: Driver Version Mismatch

If you see warnings about CUDA version mismatch:

1. Check driver CUDA version: `nvidia-smi`
2. Install matching PyTorch version
3. Driver CUDA >= PyTorch CUDA required

## Training Commands

### Train Both Models
```bash
python Agent_Guru/reasoning/train_all.py
```

### Train Intent Classifier Only
```bash
python Agent_Guru/reasoning/train_intent_classifier.py
```

### Train NER Model Only
```bash
python Agent_Guru/reasoning/train_ner_model.py
```

### Evaluate Models
```bash
python Agent_Guru/reasoning/evaluate_models.py
```

## Expected Training Times (4GB VRAM)

**Intent Classifier (DeBERTa-v3-large):**
- Training: 8-12 hours
- Epochs: 10
- Target accuracy: >99%

**NER Model (GLiNER):**
- Training: 2-4 hours
- Epochs: 10
- Target F1: >90%

**Total Time:** ~10-16 hours for both models

## Performance Targets

**Intent Classification:**
- Training accuracy: >99%
- Validation accuracy: >97%
- Test accuracy: >95%
- Inference latency: <50ms with GPU

**NER (Entity Extraction):**
- Training F1: >95%
- Validation F1: >92%
- Test F1: >90%
- Inference latency: <100ms with GPU

## Monitoring Training

### TensorBoard

```bash
tensorboard --logdir Agent_Guru/reasoning/logs
```

Open browser: http://localhost:6006

### Watch Training Progress

Training scripts print:
- Current epoch
- Training loss
- Validation accuracy
- Learning rate
- ETA

### Check Model Checkpoints

Models saved to:
- `Agent_Guru/reasoning/models/intent_classifier/`
- `Agent_Guru/reasoning/models/ner_model/`

## Post-Training

### 1. Evaluate Models

```bash
python Agent_Guru/reasoning/evaluate_models.py
```

### 2. Check Results

Results saved to:
- `Agent_Guru/reasoning/models/intent_classifier/test_results.json`
- `Agent_Guru/reasoning/models/ner_model/test_results.json`

### 3. Deploy Models

Models ready for inference:
- `Agent_Guru/reasoning/models/intent_classifier/final_model/`
- `Agent_Guru/reasoning/models/ner_model/final_model/`

## Additional Resources

**CUDA Toolkit:**
- https://developer.nvidia.com/cuda-toolkit

**PyTorch Installation:**
- https://pytorch.org/get-started/locally/

**NVIDIA Driver:**
- https://www.nvidia.com/download/index.aspx

**Troubleshooting:**
- https://pytorch.org/docs/stable/notes/cuda.html

## Support

If you encounter issues:
1. Check `nvidia-smi` output
2. Verify PyTorch CUDA version
3. Check GPU memory usage
4. Review error messages
5. Consult PyTorch documentation

---

**Status**: Ready for training! 🚀
**GPU**: NVIDIA GeForce RTX 2050 (4GB VRAM)
**CUDA**: 11.8
**PyTorch**: Installed with CUDA support
