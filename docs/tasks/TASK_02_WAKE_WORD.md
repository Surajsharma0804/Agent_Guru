TASK:
Wake Word Engine

REQUIRES REPOS:
- openWakeWord

CLONE PATH:
f:\MY PROJECTS\Guru-Agent\quarantine\voice\openWakeWord\

INTELLIGENCE TO EXTRACT:
- MFCC feature extraction pipeline
- Streaming audio ring buffer logic
- Neural confidence thresholding
- False-positive suppression model
- Wake phrase training workflow

REWRITE TARGETS:
- /guru/voice/wake/audio_features.rs
- /guru/voice/wake/neural_gate.rs
- /guru/voice/wake/training_pipeline.rs

FORMAL MODELS:
- /guru/formal/TASK_02_WAKE_WORD.tla

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
