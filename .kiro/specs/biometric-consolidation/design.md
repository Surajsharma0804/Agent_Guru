# Design Document: Biometric Consolidation

## Overview

The Biometric Consolidation initiative centralizes all biometric authentication logic into guru-security-cryptography, eliminating duplicate implementations across the codebase. This design ensures a single source of truth for authentication while maintaining specialized feature extraction in component-specific modules.

**Current State (Before Consolidation)**:
- ❌ GuruVision has face authentication logic
- ❌ guru_speech has voice authentication logic
- ❌ Multiple authentication implementations
- ❌ Inconsistent authentication policies
- ❌ Difficult to maintain and test

**Target State (After Consolidation)**:
- ✅ guru-security-cryptography: ONLY authentication system
- ✅ GuruVision: Face detection and embedding extraction ONLY
- ✅ guru_speech: Voice feature extraction ONLY
- ✅ Single authentication interface
- ✅ Consistent authentication policies
- ✅ Easy to maintain and test

## Architecture

### Before Consolidation

```
┌─────────────────────────────────────────────────────────┐
│                    GuruVision                           │
│  - Face detection                                       │
│  - Embedding extraction                                 │
│  - ❌ Face authentication (DUPLICATE)                   │
│  - ❌ Template matching (DUPLICATE)                     │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                    guru_speech                          │
│  - Voice feature extraction                             │
│  - ❌ Voice authentication (DUPLICATE)                  │
│  - ❌ Speaker verification (DUPLICATE)                  │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│              guru-security-cryptography                 │
│  - ❌ Some authentication logic (INCOMPLETE)            │
└─────────────────────────────────────────────────────────┘
```

### After Consolidation

```
┌─────────────────────────────────────────────────────────┐
│                    GuruVision                           │
│  - Face detection                                       │
│  - Embedding extraction (512-dim vector)                │
│  - ✅ NO authentication logic                           │
└────────────────────┬────────────────────────────────────┘
                     │ Provides embeddings
                     ▼
┌─────────────────────────────────────────────────────────┐
│              guru-security-cryptography                 │
│           BiometricAuthenticator (CENTRAL)              │
│  - ✅ Face authentication                               │
│  - ✅ Voice authentication                              │
│  - ✅ Fingerprint authentication                        │
│  - ✅ Multi-factor fusion                               │
│  - ✅ Template storage                                  │
│  - ✅ Confidence scoring                                │
└────────────────────▲────────────────────────────────────┘
                     │ Provides features
                     │
┌────────────────────┴────────────────────────────────────┐
│                    guru_speech                          │
│  - Voice feature extraction                             │
│  - ✅ NO authentication logic                           │
└─────────────────────────────────────────────────────────┘
```

## Consolidation Strategy

### Phase 1: Identify Duplicate Code
1. Audit GuruVision for authentication logic
2. Audit guru_speech for authentication logic
3. Document all authentication methods
4. Identify feature extraction vs authentication boundaries

### Phase 2: Update GuruVision
1. Remove authentication methods from GuruVision
2. Keep only face detection and embedding extraction
3. Update integration with BiometricAuthenticator
4. Add clear interface documentation
5. Update tests to verify no authentication logic remains

### Phase 3: Update guru_speech
1. Remove authentication methods from guru_speech
2. Keep only voice feature extraction
3. Update integration with BiometricAuthenticator
4. Add clear interface documentation
5. Update tests to verify no authentication logic remains

### Phase 4: Verify Security System
1. Ensure BiometricAuthenticator handles all authentication
2. Verify integration with all feature extractors
3. Test end-to-end authentication flows
4. Update documentation

## Component Interfaces

### GuruVision Interface (After Consolidation)

```python
class GuruVisionClient:
    """Client interface for GuruVision face processing."""
    
    def detect_faces(self, image_data: bytes) -> List[FaceDetection]:
        """
        Detect faces in image.
        
        Returns list of face bounding boxes and landmarks.
        NO authentication logic.
        """
        pass
    
    def extract_face_embedding(self, image_data: bytes) -> np.ndarray:
        """
        Extract 512-dimensional face embedding.
        
        Returns embedding vector for authentication by security system.
        NO authentication logic - only feature extraction.
        """
        pass
```

### guru_speech Interface (After Consolidation)

```python
class GuruSpeechClient:
    """Client interface for guru_speech voice processing."""
    
    def extract_voice_features(self, audio_data: bytes) -> np.ndarray:
        """
        Extract voice biometric features.
        
        Returns feature vector for authentication by security system.
        NO authentication logic - only feature extraction.
        """
        pass
```

### BiometricAuthenticator Interface (Central Authentication)

```python
class BiometricAuthenticator:
    """CENTRAL biometric authentication system."""
    
    def __init__(
        self,
        guruvision_client: GuruVisionClient,
        guru_speech_client: GuruSpeechClient,
        fingerprint_reader: Optional[FingerprintReader]
    ):
        """Initialize with feature extraction clients."""
        pass
    
    def authenticate_face(
        self,
        profile_id: str,
        image_data: bytes
    ) -> BiometricResult:
        """
        Authenticate using face.
        
        1. Calls guruvision_client.extract_face_embedding()
        2. Compares with stored template
        3. Returns authentication result
        """
        pass
    
    def authenticate_voice(
        self,
        profile_id: str,
        audio_data: bytes
    ) -> BiometricResult:
        """
        Authenticate using voice.
        
        1. Calls guru_speech_client.extract_voice_features()
        2. Compares with stored template
        3. Returns authentication result
        """
        pass
    
    def authenticate_multi_factor(
        self,
        profile_id: str,
        face_image: Optional[bytes] = None,
        voice_audio: Optional[bytes] = None,
        use_fingerprint: bool = False
    ) -> FusedBiometricResult:
        """
        Authenticate using multiple factors.
        
        Fuses results from available factors.
        """
        pass
```

## Data Flow

### Face Authentication Flow (After Consolidation)

```
User provides face image
        ↓
BiometricAuthenticator.authenticate_face(profile_id, image_data)
        ↓
GuruVisionClient.extract_face_embedding(image_data)
        ↓ Returns 512-dim embedding
BiometricAuthenticator compares with stored template
        ↓
BiometricAuthenticator returns BiometricResult
        ↓
Application receives authentication decision
```

### Voice Authentication Flow (After Consolidation)

```
User provides voice sample
        ↓
BiometricAuthenticator.authenticate_voice(profile_id, audio_data)
        ↓
GuruSpeechClient.extract_voice_features(audio_data)
        ↓ Returns feature vector
BiometricAuthenticator compares with stored template
        ↓
BiometricAuthenticator returns BiometricResult
        ↓
Application receives authentication decision
```

## Benefits of Consolidation

### 1. Single Source of Truth
- All authentication logic in one place
- Consistent authentication policies
- Easier to audit and secure

### 2. Reduced Code Duplication
- No duplicate authentication implementations
- Shared template storage
- Shared confidence scoring

### 3. Easier Maintenance
- Update authentication logic in one place
- Fix bugs in one place
- Add new biometric types in one place

### 4. Better Testing
- Test authentication logic once
- Test feature extraction separately
- Clear separation of concerns

### 5. Clearer Architecture
- Feature extraction components focus on their specialty
- Security system handles all authentication
- Clean interfaces between components

## Migration Checklist

### GuruVision Migration
- [ ] Remove authentication methods
- [ ] Keep only face detection and embedding extraction
- [ ] Update integration with BiometricAuthenticator
- [ ] Update tests
- [ ] Update documentation

### guru_speech Migration
- [ ] Remove authentication methods
- [ ] Keep only voice feature extraction
- [ ] Update integration with BiometricAuthenticator
- [ ] Update tests
- [ ] Update documentation

### Security System Verification
- [ ] Verify BiometricAuthenticator handles all authentication
- [ ] Test face authentication end-to-end
- [ ] Test voice authentication end-to-end
- [ ] Test multi-factor authentication
- [ ] Update documentation

### Testing
- [ ] Unit tests for feature extraction (GuruVision, guru_speech)
- [ ] Unit tests for authentication (BiometricAuthenticator)
- [ ] Integration tests for end-to-end flows
- [ ] Verify no authentication logic in feature extraction components

## Success Criteria

✅ All authentication logic in guru-security-cryptography
✅ GuruVision only does face detection and embedding extraction
✅ guru_speech only does voice feature extraction
✅ All tests passing
✅ Documentation updated
✅ No duplicate authentication code

