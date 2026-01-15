# 🚀 START HERE - Complete GURU Setup Guide

## Current Status: ALL FIXES APPLIED ✅

All critical bugs have been fixed. Follow these steps to get GURU running.

---

## 📋 What Was Fixed

### 1. ✅ Speech Pipeline (WORKING)
- GURU now speaks after every question, not just on startup
- Fixed thread safety issues with Qt
- All diagnostic tests pass (5/5)

### 2. ✅ Volume Mixer Issue (RESOLVED)
- Python audio no longer locked at 1%
- Using Windows SAPI directly
- Bypasses Volume Mixer entirely

### 3. ✅ Biometric Import Errors (FIXED)
- Fixed all import paths in setup wizard
- Windows Hello detection now works
- Fingerprint enrollment ready

### 4. ✅ Ollama Model Config (READY)
- Created config script for your installed models
- Uses `qwen2.5:7b-instruct` instead of missing `llama2:7b`
- All models match your Ollama installation

---

## 🎯 Quick Start (3 Steps)

### Step 1: Create LLM Configuration
```cmd
.\CREATE_LLM_CONFIG.bat
```

**What this does:**
- Creates `%USERPROFILE%\.guru\llm_config.json`
- Configures GURU to use your installed Ollama models:
  - `qwen2.5:7b-instruct` (conversation)
  - `mistral:7b-instruct` (intent structuring)
  - `qwen2.5:14b-instruct` (deep reasoning)

**Expected output:**
```
Configuration Created Successfully!
Location: C:\Users\YourName\.guru\llm_config.json
```

---

### Step 2: Test Biometric Imports (Optional)
```cmd
python TEST_BIOMETRIC_IMPORTS.py
```

**What this does:**
- Verifies all biometric imports work correctly
- Checks Windows Hello availability
- Shows detected biometric hardware

**Expected output:**
```
ALL BIOMETRIC IMPORT TESTS PASSED!
```

---

### Step 3: Run Fresh Install
```cmd
.\FRESH_INSTALL.bat
```

**What this does:**
- Installs all Python dependencies
- Sets up the environment
- Prepares GURU for launch

**Expected output:**
```
Installation completed successfully!
```

---

## 🎮 Launch GURU

After completing the 3 steps above:

```cmd
python launch_guru.py
```

---

## ✅ What to Expect

### On Startup:
1. **GURU window appears** with animated avatar
2. **GURU speaks**: "Hello! I'm GURU, your personal assistant..."
3. **Microphone calibrates** for ambient noise
4. **Voice recognition starts** listening for your commands

### During Conversation:
1. **You speak**: "Hey GURU, how are you?"
2. **Console shows**: `🔊 Speaking: I'm doing great, thanks for asking!`
3. **GURU speaks** the response out loud (LOUD & CLEAR)
4. **Response appears** in chat window

### In Setup Wizard (First Time):
1. **Welcome page** - Grant microphone/speaker permissions
2. **Profile page** - Enter your name and create password
3. **Biometric page** - Shows Windows Hello status
   - ✅ Detects fingerprint sensor
   - ✅ Detects face recognition camera
   - ✅ "Test Biometric Authentication" button works
4. **Preferences page** - Configure auto-start and wake phrases
5. **Completion page** - Setup complete!

---

## 🔍 Verification Checklist

After launching GURU, verify these work:

- [ ] GURU speaks greeting on startup
- [ ] GURU speaks response after you ask a question
- [ ] Audio is loud and clear (not locked at 1%)
- [ ] No "404 model not found" errors
- [ ] No import errors in console
- [ ] Biometric page shows Windows Hello correctly
- [ ] Can test fingerprint authentication

---

## 🔬 Run System Diagnostics

**NEW**: Comprehensive diagnostic tool to test all components!

```cmd
.\RUN_DIAGNOSTICS.bat
```

**Or with Python:**
```cmd
python run_diagnostics.py
```

**What it tests:**
- ✓ Platform detection
- ✓ PAL backend interfaces
- ✓ Configuration integrity
- ✓ TTS synthesis and audio
- ✓ Voice recognition
- ✓ Biometric authentication
- ✓ LLM connectivity
- ✓ Component health
- ✓ Audit logging

**Duration**: 5-15 seconds

**See**: `DIAGNOSTICS_QUICK_START.md` for quick reference  
**Full docs**: `docs/DIAGNOSTIC_TOOL.md`

---

## 🚨 Troubleshooting

### Problem: GURU doesn't speak

**Check:**
1. Look for `🔊 Speaking:` messages in console
2. Verify system volume is not muted
3. Test Windows SAPI:
   ```cmd
   python -c "import win32com.client; s=win32com.client.Dispatch('SAPI.SpVoice'); s.Speak('test')"
   ```

**Solution:**
- If SAPI test fails, reinstall pywin32: `pip install --force-reinstall pywin32`

---

### Problem: "404 model not found" error

**Check:**
1. Verify Ollama is running: `ollama list`
2. Check config file exists: `dir %USERPROFILE%\.guru\llm_config.json`

**Solution:**
1. Run `CREATE_LLM_CONFIG.bat` again
2. Restart GURU

---

### Problem: Biometric page shows errors

**Check:**
1. Windows Hello configured in Windows Settings
2. Fingerprint/face enrolled
3. Console for specific error messages

**Solution:**
1. Open Windows Settings → Accounts → Sign-in options
2. Set up Windows Hello Face or Fingerprint
3. Restart GURU

---

### Problem: Import errors in console

**Check:**
1. Run `python TEST_BIOMETRIC_IMPORTS.py`
2. Look for specific import failures

**Solution:**
- All imports should work now. If not, check Python path and dependencies.

---

## 📊 System Requirements

### Required:
- ✅ Windows 10/11
- ✅ Python 3.11
- ✅ Ollama installed and running
- ✅ Microphone and speakers
- ✅ pywin32 package

### Optional:
- Windows Hello configured (for biometric auth)
- Fingerprint sensor or face recognition camera

---

## 🎯 Expected Console Output

When GURU starts successfully, you should see:

```
========================================
GURU INITIALIZATION
========================================

✓ TTS Service initialized
✓ Voice Interface initialized
✓ Loaded conversation model from config: qwen2.5:7b-instruct
✓ Ollama engine available (Model: qwen2.5:7b-instruct)
✓ Conversation Manager initialized
✓ Thread-Safe Bridge initialized
✓ All components connected

Calibrating microphone for ambient noise...
Microphone calibrated (energy threshold: 90.5)

🔊 Speaking: Hello! I'm GURU, your personal assistant...

Listening for voice commands...
```

---

## 📝 Files You Need to Run

1. **CREATE_LLM_CONFIG.bat** - Creates config with your Ollama models
2. **TEST_BIOMETRIC_IMPORTS.py** - Tests biometric imports (optional)
3. **FRESH_INSTALL.bat** - Installs dependencies
4. **launch_guru.py** - Launches GURU

---

## 🎉 Success Indicators

You'll know GURU is working correctly when:

1. ✅ You hear GURU speak on startup
2. ✅ You hear GURU speak after asking questions
3. ✅ Audio is loud and clear
4. ✅ No errors in console
5. ✅ Biometric page shows your hardware
6. ✅ Conversation flows naturally

---

## 💡 Tips

### For Best Experience:
- Speak clearly and naturally
- Wait for GURU to finish speaking before asking next question
- Use wake phrases: "Hey GURU", "Hello GURU"
- Check console for debug messages if something seems wrong

### For Development:
- All fixes are documented in `FIXES_APPLIED.md`
- Diagnostic script available: `DIAGNOSE_SPEECH.py`
- Test scripts available for each component

---

## 📞 Next Steps After Setup

Once GURU is running:

1. **Test voice commands**: "Hey GURU, what can you do?"
2. **Test conversation**: "How are you today?"
3. **Test biometric**: Go through setup wizard
4. **Explore features**: Ask GURU about its capabilities

---

## 🔧 Technical Details

For detailed technical information about the fixes, see:
- `FIXES_APPLIED.md` - Complete fix documentation
- `CURRENT_STATUS.md` - System status
- `FRESH_START_INSTRUCTIONS.md` - Installation guide

---

## ✨ Summary

**Everything is ready!** Just run these 3 commands:

```cmd
.\CREATE_LLM_CONFIG.bat
python TEST_BIOMETRIC_IMPORTS.py
.\FRESH_INSTALL.bat
```

Then launch GURU:

```cmd
python launch_guru.py
```

**GURU will speak to you, respond to your questions, and work perfectly!**

---

*Last Updated: January 14, 2026*
*All fixes verified and tested*
