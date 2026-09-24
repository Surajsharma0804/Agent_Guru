# Biometric Integration Guide

## Architecture Overview

The consolidated biometric architecture has a single rule: **only `BiometricAuthenticator` makes authentication decisions**.

```
┌──────────────────────────────────────────────────────────────┐
│  Agent_Guru.vision                                           │
│  FaceFeatureExtractor                                        │
│    detect_faces()          → List[FaceDetection]             │
│    extract_face_embedding() → FaceFeatures (embedding only)  │
│    detect_liveness()       → (bool, float)                   │
│                                                              │
│  ✅ Face detection & embedding extraction ONLY               │
│  ❌ NO authentication decisions                              │
└──────────────────────┬───────────────────────────────────────┘
                       │ FaceFeatures (512-dim embedding)
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  Agent_Guru.security                                         │
│  BiometricAuthenticator  ◄── SINGLE AUTH AUTHORITY           │
│    enroll_face()                                             │
│    authenticate_face()                                       │
│    enroll_voice()                                            │
│    authenticate_voice()                                      │
│    authenticate_multi_factor()                               │
│                                                              │
│  ✅ Template storage, comparison, liveness enforcement       │
│  ✅ Confidence scoring and fusion                            │
│  ✅ All authentication decisions                             │
└──────────────────────▲───────────────────────────────────────┘
                       │ VoiceFeatures (feature vector)
┌──────────────────────┴───────────────────────────────────────┐
│  Agent_Guru.speech                                           │
│  SpeechEngine                                                │
│    extract_voice_features() → VoiceFeatures                  │
│                                                              │
│  ✅ Voice feature extraction ONLY                            │
│  ❌ NO authentication decisions                              │
└──────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Face Authentication

```python
from Agent_Guru.security.biometric_auth import BiometricAuthenticator

auth = BiometricAuthenticator(
    face_threshold=0.75,    # cosine similarity threshold
    liveness_threshold=0.5, # anti-spoofing threshold
)

# Enroll
with open("user_photo.jpg", "rb") as f:
    auth.enroll_face("alice", f.read())

# Authenticate
with open("live_capture.jpg", "rb") as f:
    result = auth.authenticate_face("alice", f.read())

if result.authenticated:
    print(f"Welcome, Alice! (confidence={result.confidence:.2f})")
else:
    print(f"Access denied: {result.failure_reason}")
```

### Voice Authentication

```python
import numpy as np
from Agent_Guru.security.biometric_auth import BiometricAuthenticator

auth = BiometricAuthenticator(voice_threshold=0.85)

# Enroll - audio_data is a float32 numpy array (16 kHz mono)
auth.enroll_voice("alice", enrollment_audio)

# Authenticate
result = auth.authenticate_voice("alice", live_audio)

if result.authenticated:
    print(f"Voice verified (confidence={result.confidence:.2f})")
else:
    print(f"Rejected: {result.failure_reason}")
```

### Multi-Modal Authentication

```python
result = auth.authenticate_multi_factor(
    profile_id="alice",
    face_image=face_bytes,   # optional
    voice_audio=audio_array, # optional - at least one required
)

# Fused confidence: face × 0.6 + voice × 0.4
# Any liveness failure causes immediate rejection
print(result.authenticated, result.confidence, result.modality)  # "multi"
```

---

## API Reference

### `BiometricAuthenticator`

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(face_extractor=None, voice_authenticator=None, face_threshold=0.75, voice_threshold=0.85, liveness_threshold=0.5)` | All args optional; defaults create internal extractors |
| `enroll_face` | `(profile_id: str, image_data: bytes) → None` | Stores 512-dim embedding; raises `ValueError` if liveness fails |
| `authenticate_face` | `(profile_id: str, image_data: bytes) → AuthenticationResult` | Extracts embedding, checks liveness, compares to template |
| `enroll_voice` | `(profile_id: str, audio_data: np.ndarray) → None` | Extracts voice features and stores template |
| `authenticate_voice` | `(profile_id: str, audio_data: np.ndarray) → AuthenticationResult` | Extracts features, checks liveness, compares to template |
| `authenticate_multi_factor` | `(profile_id: str, face_image=None, voice_audio=None) → AuthenticationResult` | Weighted fusion; raises `ValueError` if no modality provided |

### `AuthenticationResult` fields

| Field | Type | Description |
|-------|------|-------------|
| `authenticated` | `bool` | `True` if identity verified |
| `confidence` | `float` | Similarity/fusion score in `[0.0, 1.0]` |
| `modality` | `str` | `"face"`, `"voice"`, or `"multi"` |
| `user_id` | `str` | The claimed profile ID |
| `failure_reason` | `Optional[str]` | Human-readable reason when `authenticated=False` |

### `FaceFeatures` fields

| Field | Type | Description |
|-------|------|-------------|
| `embedding` | `np.ndarray` shape `(512,)` | L2-normalised face embedding |
| `quality_score` | `float` | Overall image quality in `[0.0, 1.0]` |
| `is_live` | `bool` | `True` if liveness check passed |
| `liveness_score` | `float` | Anti-spoofing confidence in `[0.0, 1.0]` |
| `bounding_box` | `BoundingBox` | Face location in source image |
| `quality` | `FaceQuality` | Detailed quality metrics (sharpness, brightness, pose) |

### `VoiceFeatures` fields

| Field | Type | Description |
|-------|------|-------------|
| `feature_vector` | `np.ndarray` | MFCC/pitch/spectral feature vector |
| `sample_rate` | `int` | Audio sample rate in Hz |
| `duration` | `float` | Audio duration in seconds |
| `quality_score` | `float` | Audio quality estimate in `[0.0, 1.0]` |
| `liveness_score` | `float` | Anti-spoofing confidence in `[0.0, 1.0]` |
| `is_live` | `bool` | `True` when `liveness_score >= 0.55` |

---

## Migration Guide

### What Changed

| Before | After |
|--------|-------|
| `vision/` had face authentication + template matching | `vision/` has face detection and embedding extraction only |
| `speech/` had `BiometricAuthenticator` class | `speech/` has voice feature extraction only |
| Auth decisions scattered across modules | All auth decisions in `security/BiometricAuthenticator` |

### Updating Existing Code

**Old pattern (vision-based auth):**
```python
# ❌ Old - authentication in vision module
from Agent_Guru.vision.recognition import FaceRecognizer
recognizer = FaceRecognizer()
is_match = recognizer.verify_identity(profile_id, image_data)
```

**New pattern:**
```python
# ✅ New - feature extraction in vision, auth in security
from Agent_Guru.security.biometric_auth import BiometricAuthenticator
auth = BiometricAuthenticator()
result = auth.authenticate_face(profile_id, image_data)
is_match = result.authenticated
```

**Old pattern (speech-based auth):**
```python
# ❌ Old - authentication in speech module
from Agent_Guru.speech.biometric import SpeechBiometricAuth
speech_auth = SpeechBiometricAuth()
verified = speech_auth.verify_speaker(profile_id, audio)
```

**New pattern:**
```python
# ✅ New - feature extraction in speech, auth in security
from Agent_Guru.security.biometric_auth import BiometricAuthenticator
auth = BiometricAuthenticator()
result = auth.authenticate_voice(profile_id, audio)
verified = result.authenticated
```

### Deprecation Notes

- Any authentication methods previously on `vision/` or `speech/` modules are removed.
- `FaceFeatureExtractor` and `SpeechEngine.extract_voice_features()` are the supported feature extraction APIs - they return data only, never authentication decisions.
- Template storage is now exclusively managed by `BiometricAuthenticator._face_templates` and `VoiceAuthenticator._profiles`.

---

## Security Notes

### Liveness Detection

Both modalities enforce liveness before any template comparison:

- **Face**: Texture-based Laplacian variance heuristic (configurable via `liveness_threshold`, default `0.5`). InsightFace's built-in anti-spoofing is used when available.
- **Voice**: `VoiceFeatures.is_live` is set by the speech engine (`liveness_score >= 0.55`). `VoiceAuthenticator.authenticate()` rejects non-live audio immediately, before any similarity computation.

In multi-modal mode, a liveness failure in **any** modality causes immediate rejection of the entire attempt - the other modality is not evaluated.

### Anti-Spoofing

| Attack | Mitigation |
|--------|-----------|
| Printed photo | Laplacian variance detects flat textures |
| Screen replay | Low liveness score from texture analysis |
| Voice replay | `is_live=False` from speech engine |
| Synthesised voice | Liveness score below threshold |

### Template Storage

Templates are held in memory (`dict`) by default. For production deployments:

- Encrypt templates at rest with AES-256-GCM before persisting.
- Use the OS keychain (via `keyring`) for encryption key storage.
- Never log or expose raw embeddings or feature vectors.
- Securely zero memory when templates are deleted.

### Thresholds

| Parameter | Default | Notes |
|-----------|---------|-------|
| `face_threshold` | `0.75` | Cosine similarity; raise for stricter security |
| `voice_threshold` | `0.85` | Cosine similarity; voice is held to a higher bar by default |
| `liveness_threshold` | `0.5` | Face liveness; raise in high-security environments |
| Voice liveness | `0.55` | Hardcoded in `VoiceFeatures.is_live`; set in speech engine |
