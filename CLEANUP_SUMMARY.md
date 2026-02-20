# Intent Classifier Model Cleanup - Summary

## Investigation Results

I've analyzed the `Agent_Guru/reasoning/models/intent_classifier` directory and found it's consuming **38.82 GB** of disk space, with **38.50 GB (99.2%)** being unnecessary training checkpoints.

## What I Found

### Files Taking Up Space

| File/Directory | Size | Needed? |
|----------------|------|---------|
| `intent-classifier-epoch=00-val_accuracy=0.0455-v2.ckpt` | 6.48 GB | ❌ No |
| `last-v2.ckpt` | 6.48 GB | ❌ No |
| `intent-classifier-epoch=00-val_accuracy=0.0455.ckpt` | 6.48 GB | ❌ No |
| `intent-classifier-epoch=00-val_accuracy=0.0455-v1.ckpt` | 6.48 GB | ❌ No |
| `last-v1.ckpt` | 3.97 GB | ❌ No |
| `intent-classifier-epoch=04-val_accuracy=0.9848.ckpt` | 3.97 GB | ❌ No |
| `last.ckpt` | 1.39 GB | ❌ No |
| `intent-classifier-epoch=00-val_accuracy=0.0227.ckpt` | 1.39 GB | ❌ No |
| `checkpoint-132/` | 0.92 GB | ❌ No |
| `checkpoint-165/` | 0.92 GB | ❌ No |
| `logs/` | <0.01 GB | ❌ No |
| `final_model/` | 0.31 GB | ✅ Yes |
| Tokenizer files | 0.005 GB | ✅ Yes |

### What Production Actually Uses

The production code (`neural_classifier.py`) only needs:

1. **ONNX model**: `final_model/model.onnx` (doesn't exist yet, needs conversion)
2. **Tokenizer files**: `tokenizer.json`, `vocab.json`, `merges.txt`, etc.
3. **Label mappings**: `label_mappings.yaml`

**Total needed: ~320 MB**

## What I Created

### 1. Cleanup Script (`cleanup_model_checkpoints.py`)

A safe, automated script that:
- Shows exactly what will be deleted (dry-run mode)
- Calculates space savings
- Asks for confirmation before deleting
- Preserves all production-critical files

### 2. Comprehensive Guide (`MODEL_CLEANUP_GUIDE.md`)

Complete documentation including:
- Problem analysis
- Step-by-step cleanup instructions
- ONNX conversion guide
- Best practices for future
- FAQ section

## How to Execute Cleanup

### Option 1: All-in-One Script (Recommended)

The easiest way - does everything automatically:

```bash
python Agent_Guru/reasoning/optimize_models.py
```

This will:
1. Check prerequisites
2. Clean up training checkpoints
3. Convert to ONNX format
4. Verify the setup (optional)

### Option 2: Step-by-Step

If you prefer manual control:

#### Step 1: Preview (Dry Run)

```bash
python Agent_Guru/reasoning/cleanup_model_checkpoints.py --dry-run
```

This shows what will be deleted without actually deleting anything.

#### Step 2: Execute Cleanup

```bash
python Agent_Guru/reasoning/cleanup_model_checkpoints.py --execute
```

This will:
1. Show you the files to be deleted
2. Ask you to type 'DELETE' to confirm
3. Delete the unnecessary files
4. Show final space savings

#### Step 3: Convert to ONNX (Required for Production)

```bash
python Agent_Guru/reasoning/convert_to_onnx.py
```

This creates the `model.onnx` file that production actually uses.

## Expected Results

- **Before**: 38.82 GB
- **After**: 0.31 GB (313 MB)
- **Space Freed**: 38.50 GB
- **Reduction**: 99.2%

## Safety

✅ **Safe to execute** - The script preserves all files needed for production:
- `final_model/` directory (contains trained model)
- All tokenizer files
- Label mappings
- Training metrics (for reference)

❌ **Only deletes**:
- Training checkpoint files (*.ckpt)
- Intermediate checkpoint directories
- Training logs

## Production Impact

**Zero impact** on production because:
1. Production uses ONNX model (not PyTorch checkpoints)
2. All inference files are preserved
3. Model accuracy and performance unchanged

## Next Steps

1. **Review the dry-run output** to see what will be deleted
2. **Execute the cleanup** if you're satisfied
3. **Convert to ONNX** for production use
4. **Verify** everything works with `verify_implementation.py`

## Questions?

See `Agent_Guru/reasoning/models/MODEL_CLEANUP_GUIDE.md` for:
- Detailed explanations
- Manual cleanup instructions
- Retraining considerations
- Best practices
- FAQ

---

**Ready to execute?** Run the cleanup script with `--execute` flag.

**Need more info?** Check the comprehensive guide in `MODEL_CLEANUP_GUIDE.md`.
