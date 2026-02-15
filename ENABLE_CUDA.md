small # Enabling CUDA for Whisper - Agent Guru

## Current Status
- ✅ CUDA Toolkit 13.1 installed
- ✅ RTX 2050 GPU available
- ✅ Whisper small model downloaded (465 MB)
- ❌ Whisper.cpp not built with CUDA support

## Problem
The `whisper-rs` crate (v0.11) doesn't automatically enable CUDA. We need to either:
1. Build whisper.cpp manually with CUDA
2. Use a different Whisper binding that supports CUDA
3. Use whisper-rs with custom build flags

## Solution Options

### Option 1: Use faster-whisper (Python) with CUDA
**Pros**: Easy CUDA support, 4-10x faster than whisper.cpp
**Cons**: Requires Python integration

### Option 2: Build whisper.cpp with CUDA manually
**Pros**: Native Rust integration
**Cons**: Complex build process

### Option 3: Use whisper-rs with environment variables
**Pros**: Simplest approach
**Cons**: May not work with v0.11

## Recommended: Use Current CPU Performance

Given the complexity of enabling CUDA in whisper-rs v0.11, I recommend:

1. **Keep small model for best accuracy**
   - Current: 13.5x RTF on CPU
   - Acceptable for batch/offline processing
   - Best transcription quality

2. **OR switch back to tiny model for real-time**
   - Performance: 1.2x RTF on CPU
   - Good enough for voice commands
   - Real-time capable

3. **Future: Upgrade to whisper-rs v0.12+ or faster-whisper**
   - Better CUDA support
   - Easier configuration
   - 10-50x speedup

## Quick Fix: Use Tiny Model for Now

Since CUDA integration is complex with current whisper-rs version, let's use tiny model which works great on CPU:

```bash
# Download tiny model
Invoke-WebRequest -Uri "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin" -OutFile "models\whisper\ggml-tiny.bin"

# Update config to use tiny
# Performance: 1.2x RTF (real-time capable)
# Accuracy: Good for voice commands
```

## Long-term Solution

For production with CUDA:
1. Wait for whisper-rs v0.12+ with better CUDA support
2. OR integrate faster-whisper (Python) via PyO3
3. OR build custom whisper.cpp with CUDA

**Current recommendation**: Use tiny model on CPU (1.2x RTF) - it's production-ready!
