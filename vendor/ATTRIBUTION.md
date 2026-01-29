# Attribution Registry

## libsodium
- **URL**: https://github.com/jedisct1/libsodium
- **License**: ISC
- **Intelligence Used**:
  - Ed25519 Key Generation & Signing Logic
  - X25519 Key Exchange State Machine
  - Secure Memory Zeroization patterns
  - XChaCha20Poly1305 Construction
- **GURU Target**: `guru/security/crypto/*`
- **Verification**: Clean-Room Implementation (No code copied).

## openWakeWord
- **URL**: https://github.com/dscripka/openWakeWord
- **License**: Apache-2.0
- **Intelligence Used**:
  - MFCC feature extraction pipeline
  - Streaming audio ring buffer logic
  - Neural confidence thresholding
  - Prediction buffer (deque) architecture
  - False-positive suppression model
- **GURU Target**: `guru/voice/wake/*`
- **Verification**: Clean-Room Implementation (No code copied).
