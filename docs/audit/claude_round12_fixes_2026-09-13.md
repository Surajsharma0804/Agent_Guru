# AGENT_GURU — Round 12: Voice/Vision/Avatar Subsystem Audit (Backlog #34, partial)

**Date:** 2026-09-13
**Scope:** A close read of the highest-risk, hottest-path files in `Agent_Guru/speech/`, `Agent_Guru/vision/`, and `Agent_Guru/avatar/` — the three subsystems together comprise well over 100 files across `speech/{audio,stt,tts,mobile,biometric,commands,context,emotion}/`, `vision/{detection,recognition,liveness,tracking,database,alignment}/`, and `avatar/{lip_sync,rendering,personality,emotion}/`. This round did **not** attempt an exhaustive file-by-file sweep of that entire surface in one pass — it prioritized the manager/engine/facade classes that sit directly on the real-time voice and vision pipelines, since those are both the highest-traffic code paths and the ones a bug in would be most visible to a user. Stated plainly per the project mandate: this is real, verified progress on a large backlog item, not a claim that #34 is fully closed.

## Files read in full this round

`speech/stt_manager.py`, `speech/tts_manager.py`, `speech/wake_word_manager.py`, `speech/engine.py`, `vision/ocr.py`, `avatar/avatar_system.py`, and the first 200 lines of `vision/engine.py` (its `initialize()`/lifecycle section).

**Notable observation:** `tts_manager.py` and `wake_word_manager.py` already carry extensive inline `FIX`/`BUG-NNN` comments documenting concurrency races and correctness bugs that were found and fixed in *earlier* engineering work on this codebase (a shared-engine race between concurrent Guru/Maya synthesis requests, a pyttsx3 voice-switching bug, an event-loop-blocking audio capture bug, and others) — all independently verified as already fixed. This is good evidence that this particular corner of the codebase has already had real scrutiny; it is not evidence that the rest of `speech/`, `vision/`, or `avatar/` has.

## Fix — `SpeechEngine.extract_voice_features()`'s documented 10-second timeout did not actually bound how long the caller could be blocked

**File:** `speech/engine.py`

**Problem:** this method is the integration point between the speech engine and the biometric authentication system (its own docstring says "FOR SECURITY SYSTEM USE ONLY" — it feeds `BiometricAuthenticator.authenticate_voice()`). When called from a thread that already has a running asyncio event loop, it dispatches the actual feature-extraction coroutine to a one-off `ThreadPoolExecutor` and waits with `future.result(timeout=10)`, and the docstring/exception message promise the caller gets a `RuntimeError` after at most 10 seconds if extraction hangs.

That promise was false. The executor was used as `with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:` — and `ThreadPoolExecutor.__exit__` calls `shutdown(wait=True)`, which blocks until every submitted task actually finishes, independent of whether `future.result()` already gave up on it. So while `future.result(timeout=10)` itself did raise `TimeoutError` at the correct 10-second mark, that exception could not propagate out of the `with` block — and therefore out to the caller — until the runaway background task *actually completed*, however long that took. A genuinely stuck extraction (a hung model call, blocked hardware I/O) would silently block the caller for the real duration of the hang, not the documented 10 seconds — in the worst case, forever.

**Verified concretely, twice:**
1. An isolated repro of the exact pattern: `future.result(timeout=0.5)` against a 3-second background task raises `TimeoutError` at t=0.5s as expected, but control does not return to the caller until t=3.0s — the full task duration.
2. The real, edited `speech/engine.py` loaded via `importlib` (with every one of its ~20 sibling-module imports stubbed, but the actual method body under test unmodified): calling `extract_voice_features()` against a stub extractor that hangs for 30 seconds now correctly raises the documented `RuntimeError("Voice feature extraction timed out after 10s")` and returns control to the caller in ~10 seconds — not ~30. Before the fix this same test setup would have blocked for the full 30 seconds.

**Fix:** stopped using the executor as a context manager. It's now created and torn down with `pool.shutdown(wait=False)` in a `finally` block, so the caller's 10-second timeout is honored immediately; the orphaned worker thread is left to finish (or never finish) on its own without blocking anything else.

## Finding documented but not fixed — `GuruAvatarSystem.reload_config()` does not actually reload anything into the live avatar

**File:** `avatar/avatar_system.py`

`reload_config(new_config)` is documented as "Hot-reload configuration without restart," but its entire body is:
```python
def reload_config(self, new_config: AvatarConfig) -> None:
    self._config = new_config
    logger.info("Configuration reloaded")
```
`self._config` is read only inside `initialize()` (to construct `EmotionRecognizer`, `LipSyncController`, `PersonalityEngine`, `AvatarRenderer`, and `PerformanceMonitor`) and is never referenced again afterward by `process_user_emotion()`, `process_speech_audio()`, `render_frame()`, `update()`, or anything else that runs after startup. So calling `reload_config()` after `initialize()` silently changes an attribute nothing reads — every already-constructed sub-component keeps running with whatever settings it was built with at `initialize()` time, and the caller has no way to know their new config had zero effect. I did not fix this: doing it correctly means knowing which of `EmotionRecognizer`, `LipSyncController`, `PersonalityEngine`, `AvatarRenderer`, and `PerformanceMonitor` actually expose a live-update path for each config field (some may need a full re-init, e.g. a backend change on `AvatarRenderer`; others might have a cheap setter) — that requires reading all five of those modules, which is outside this round's time budget. Flagging it precisely rather than guessing at a reload strategy that might silently do the wrong thing for some subset of fields.

## What remains unaudited in this backlog item

This is the honest accounting, not a checklist to be quietly dropped:
- `speech/`: `audio/` (capture, streaming, noise_cancellation, processor — the actual DSP/audio-I/O layer), `stt/` (whisper_stt.py, language_detector.py — the real transcription backend `stt_manager.py` wraps), `tts/` (synthesis_engine.py, tts_engine.py, voice_cloner.py — the real Kokoro/Coqui backend `tts_manager.py` wraps), `mobile/`, `biometric/`, `commands/`, `context/`, `emotion/`.
- `vision/`: the rest of `engine.py` (only its first 200 of ~700+ lines were read), `detection/`, `recognition/`, `liveness/`, `tracking/`, `database/`, `alignment/`, plus the other top-level files (`face_features.py`, `gesture.py`, `handwriting.py`, `pose.py`, `scene.py`, `screen.py`, `vqa.py`, `depth.py`, `tracker.py`, `model_manager.py`, `privacy.py`, `observability.py`).
- `avatar/`: `lip_sync/`, `rendering/`, `personality/`, `emotion/`, `performance.py`, `state_manager.py`, `speech_integration.py`, `vision_integration.py`.

## Status

Backlog task #34 stays **in progress**, not completed — this round made real, verified progress on the highest-traffic code (one genuine timeout bug found, reproduced, and fixed with an executed regression test against the real code; one hot-reload no-op documented) but the subsystem is far too large to responsibly claim full closure in a single pass.
