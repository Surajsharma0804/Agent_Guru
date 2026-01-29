TASK:
Cryptographic Identity Core

REQUIRES REPOS:
- libsodium

CLONE PATH:
f:\MY PROJECTS\Guru-Agent\quarantine\crypto\libsodium\

INTELLIGENCE TO EXTRACT:
- Ed25519 key lifecycle (generate → sign → verify → rotate → revoke)
- X25519 Diffie-Hellman exchange state machine
- Secure memory zeroization patterns
- Key derivation pipeline (HKDF-style)
- Authenticated encryption envelope design

REWRITE TARGETS:
- /guru/security/crypto/identity_keys.rs
- /guru/security/crypto/key_exchange.rs
- /guru/security/crypto/secure_memory.rs
- /guru/security/crypto/envelope.rs

FORMAL MODELS:
- /guru/formal/TASK_01_CRYPTO_IDENTITY.tla

TESTS:
- Unit tests
- Property tests
- Offline tests
- Security tests
- Performance benchmarks

STOP-GATE:
- Quarantine deleted
- Tests pass
- Reproducible build verified
- Commit signed
- Runtime attestation compatible
- Policy freeze compatible
- Attribution written
