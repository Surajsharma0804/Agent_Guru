# GURU Diagnostics - Quick Start Guide

## What is it?

The GURU diagnostic tool tests all critical system components to ensure everything is working correctly.

## How to run it?

### Windows (Easiest)

Double-click: **`RUN_DIAGNOSTICS.bat`**

### Command Line

```bash
python run_diagnostics.py
```

## What does it test?

✓ Platform detection (Windows/macOS/Android/iOS)  
✓ PAL backend interfaces (6 interfaces)  
✓ Configuration files  
✓ Text-to-Speech (TTS)  
✓ Voice recognition  
✓ Biometric authentication  
✓ LLM connectivity  
✓ Component health  
✓ Audit logging  

## How long does it take?

**5-15 seconds** for all tests

## What do the results mean?

- **✓ PASS**: Component is working correctly
- **✗ FAIL**: Component has critical issues
- **⚠ WARN**: Component has warnings or limitations
- **○ SKIP**: Test was skipped

## Common Issues

### "LLM Connectivity Failed"

**Fix**: Start Ollama service
```bash
ollama serve
```

### "Biometric Authentication Not Available"

**Fix**: Configure Windows Hello in system settings

### "TTS Synthesis Failed"

**Fix**: Check audio output device is connected and enabled

### "Configuration Files Missing"

**Fix**: Run setup wizard
```bash
python launch_guru.py
```

## Need more help?

See full documentation: **`docs/DIAGNOSTIC_TOOL.md`**

## Exit Codes

- **0** = All tests passed ✓
- **1** = Some tests failed ✗
- **130** = Interrupted by user (Ctrl+C)

---

**Quick Tip**: Run diagnostics after:
- Fresh installation
- System updates
- Configuration changes
- Troubleshooting issues
