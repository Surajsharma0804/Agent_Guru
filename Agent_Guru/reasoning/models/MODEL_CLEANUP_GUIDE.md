# Model Checkpoint Cleanup Guide

## Problem

The `intent_classifier` model directory is taking up **38.82 GB** of disk space, primarily due to training checkpoint files that are not needed for production inference.

## Analysis

### Current Space Usage

```
Total: 38.82 GB
├── Training checkpoints (*.ckpt): ~37 GB
├── Checkpoint directories: ~1.8 GB
├── Final model (needed): 313 MB
└── Tokenizer files (needed): ~5 MB
```

### What's Actually Needed for Production

The production code (`neural_classifier.py`) only requires:

1. **ONNX model**: `final_model/model.onnx` (needs to be converted)
2. **Tokenizer files**: `tokenizer.json`, `vocab.json`, `merges.txt`, etc.
3. **Label mappings**: `label_mappings.yaml`

Total needed: **~320 MB** (after ONNX conversion)

### What Can Be Deleted

All training artifacts that are only used during model training:

- `*.ckpt` files (8 files, ~37 GB)
- `checkpoint-*/` directories (2 dirs, ~1.8 GB)
- `logs/` directory (training logs)

**Total space to free: 38.50 GB**

## Solution

### Option 1: Automated Cleanup (Recommended)

Use the provided cleanup script:

```bash
# Step 1: Preview what will be deleted (dry run)
python Agent_Guru/reasoning/cleanup_model_checkpoints.py --dry-run

# Step 2: Execute the cleanup
python Agent_Guru/reasoning/cleanup_model_checkpoints.py --execute
```

The script will:
- Show you exactly what will be deleted
- Calculate space savings
- Ask for confirmation before deleting
- Keep all files needed for production

### Option 2: Manual Cleanup

If you prefer to delete files manually:

```bash
cd Agent_Guru/reasoning/models/intent_classifier

# Delete checkpoint files
rm *.ckpt

# Delete checkpoint directories
rm -rf checkpoint-132/
rm -rf checkpoint-165/

# Delete training logs
rm -rf logs/
```

### Option 3: Keep Everything (Not Recommended)

If you want to keep training checkpoints for future fine-tuning:
- Move them to external storage or archive
- Compress them (can reduce size by 50-70%)
- Keep only the best checkpoint (`intent-classifier-epoch=04-val_accuracy=0.9848.ckpt`)

## After Cleanup

### Convert Model to ONNX

The production code expects an ONNX model for optimal inference performance:

```bash
python Agent_Guru/reasoning/convert_to_onnx.py \
    --model-path Agent_Guru/reasoning/models/intent_classifier/final_model \
    --output-path Agent_Guru/reasoning/models/intent_classifier/final_model/model.onnx
```

This will create the `model.onnx` file (~313 MB) needed for production.

### Verify Production Setup

After cleanup and ONNX conversion, verify everything works:

```bash
python verify_implementation.py
```

This will test:
- Model loading
- Inference performance
- GPU acceleration (if available)

## Files Kept After Cleanup

```
intent_classifier/
├── final_model/
│   ├── config.json
│   ├── model.safetensors (313 MB)
│   └── model.onnx (313 MB, after conversion)
├── label_mappings.yaml
├── tokenizer.json
├── vocab.json
├── merges.txt
├── special_tokens_map.json
├── tokenizer_config.json
└── training_metrics.yaml (optional, for reference)
```

**Total size: ~630 MB** (with both PyTorch and ONNX models)

## Performance Impact

**None.** Deleting training checkpoints has zero impact on production performance because:

1. Production uses ONNX model, not PyTorch checkpoints
2. All inference-related files are preserved
3. Model accuracy and latency remain unchanged

## Retraining Considerations

If you need to retrain the model in the future:

1. Training checkpoints are **not required** for retraining
2. You can retrain from scratch using the training script
3. The training data is preserved in `Agent_Guru/reasoning/data/`
4. Training takes 8-12 hours with GPU (acceptable for occasional retraining)

## Best Practices

### For Development

- Delete checkpoints after successful training
- Keep only the best checkpoint if needed
- Use the cleanup script regularly

### For Production

- Only deploy the ONNX model and tokenizer files
- Don't include training checkpoints in production builds
- Use `.dockerignore` to exclude `*.ckpt` files

### For CI/CD

Add to `.gitignore`:

```gitignore
# Model checkpoints (too large for git)
*.ckpt
checkpoint-*/
logs/version_*/
```

Add to `.dockerignore`:

```dockerignore
# Exclude training artifacts from Docker images
*.ckpt
checkpoint-*/
logs/
```

## FAQ

**Q: Will this break anything?**
A: No. Production code only uses the ONNX model and tokenizer files, which are preserved.

**Q: Can I recover deleted checkpoints?**
A: No, deletion is permanent. Run in dry-run mode first to verify.

**Q: Should I keep the best checkpoint?**
A: Not necessary. The `final_model/` directory contains the trained model in a more efficient format.

**Q: What if I need to fine-tune the model later?**
A: You can fine-tune from the `final_model/` directory or retrain from scratch. Checkpoints are not required.

**Q: How often should I run cleanup?**
A: After each training session, or when disk space is low.

## Summary

- **Current size**: 38.82 GB
- **After cleanup**: 0.31 GB (313 MB)
- **Space saved**: 38.50 GB (99.2% reduction)
- **Production impact**: None
- **Recommended action**: Run cleanup script with `--execute`

---

**Status**: Ready to Execute ✅
**Risk Level**: Low (production files preserved) ✅
**Space Savings**: 38.50 GB ✅
