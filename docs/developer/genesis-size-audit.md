# GENESIS size audit

Measured 2026-11-04 on the development laptop (Windows 11, CPython 3.13.15,
RTX 2050 4 GB). This audit decides how the install is split into tiers. Every
number below was measured on this machine unless a row says otherwise; nothing
is estimated.

How the numbers were taken:

- Installed size of a package: every file its `RECORD` lists, `stat()`ed, in
  the development venv (`.venv`, 263 distributions, 4,499.8 MB).
- Download size of a tier: `pip install --dry-run --report` for the tier's own
  requirements with `requirements-lock.txt` as constraints (`-c`), then each
  chosen wheel's size from PyPI's JSON API (or the PyTorch index's
  `Content-Length`). Windows, CPython 3.13, x86-64.
- Disk size of a tier: the tier installed into a fresh venv made from the
  system Python 3.13.15, every file under the venv counted. Layered tiers were
  installed on top of a fresh core, and the difference is the tier's own cost.
- Which feature imports a package: a typed turn run with the profile isolated
  and a fake model, a start of `main.py` with no microphone, and an import
  hook that records the first Agent Guru frame importing each package.

## The current build

There was no installer to measure. No `dist/` folder existed, PyInstaller and
Inno Setup were not installed, and the output folder of `AgentGuru_setup.iss`
(`C:\AgentGuru_Build`) did not exist. The old `AgentGuru.spec` bundled the whole
`Agent_Guru` package and everything `main.py`'s import graph reached, compressed
with UPX and installed per machine with an admin prompt. Its size is unknown:
it was replaced without being built.

## Top 15 installed packages in the development venv

| # | Package | Installed MB | Imported by (file:line) | Needed by a user at runtime? |
|--:|:--|--:|:--|:--|
| 1 | nvidia-cudnn-cu12 9.27.0.42 | 1,149.2 | DLLs found by `speech/stt/whisper_stt.py` for GPU Whisper | Optional, NVIDIA only (voice GPU add-on). Not in the lock. |
| 2 | nvidia-cublas-cu12 12.9.2.10 | 772.2 | same | Optional, NVIDIA only. Not in the lock. |
| 3 | torch 2.14.0 (CPU build) | 531.7 | `reasoning/memory/embedding.py:28` (module scope, until 70773ccb); `speech/audio/command_capture.py:116` through silero-vad; 16 more guarded uses | Voice only (silero VAD). Memory no longer needs it (ONNX route). Training uses it. |
| 4 | nvidia-cuda-nvrtc-cu12 12.9.86 | 187.1 | dependency of nvidia-cudnn-cu12 | Optional, NVIDIA only. |
| 5 | scipy 1.18.1 | 134.3 | `speech/biometric/voice_features.py:11` (module scope, reached from `speech/engine.py:34` on every start); `self_improvement/degradation_detector.py:30` | Yes: `main.py` cannot start without it. Core. |
| 6 | llvmlite 0.50.0 | 122.4 | through numba, through librosa (`speech/audio/wake_word.py:62`) | Voice. |
| 7 | opencv-python 4.13.0.92 | 114.1 | `vision/face_features.py:35`, reached from `security/__init__.py:3` on a typed turn | Vision; guarded, so core runs without it. |
| 8 | playwright 1.64.0 | 112.7 | `integration/browser_tools.py:280`, `platform/browser_manager.py:528` (in functions) | Browser tier. |
| 9 | transformers 5.17.0 | 103.7 | through sentence-transformers; `reasoning/intent/neural_classifier.py:46` | Not with the ONNX route; training scripts. |
| 10 | spacy 3.8.16 | 96.9 | `reasoning/intent/ner_extractor.py:43` (guarded) | No: test extra only, though a development start loads it. |
| 11 | kubernetes 36.0.3 | 77.9 | nothing | No: left in the development venv by chromadb, not in the lock. |
| 12 | chromadb 1.5.9 | 70.1 | nothing (removed from the project) | No: development venv only. |
| 13 | av 18.1.0 | 70.0 | through faster-whisper | Voice. |
| 14 | sympy 1.14.0 | 69.0 | through torch | Voice (torch). |
| 15 | ctranslate2 4.8.2 | 63.5 | `speech/stt/whisper_stt.py:43`, `integration/gpu_pool.py:53` | Voice. |

24 distributions in the development venv are not in the lock, 2,265.1 MB in
all; most of it is the GPU add-on, the rest leftovers such as chromadb and
kubernetes (153.3 MB). Packages used only by tests or training (pytest, mypy,
ruff, spacy, pytorch-lightning, tensorboard, torchvision, onnx, onnxscript and
their dependencies) are 291.0 MB of the development venv. None of them enters a
user install, because every tier installs only its own requirement list.

## What the running assistant actually loads

| Run | Distributions loaded | Their installed MB |
|:--|--:|--:|
| Typed turn, no memory | 25 | 338.0 |
| Typed turn, memory on (sentence-transformers route) | 64 | 1,232.3 |
| Typed turn, memory on (ONNX route), in a venv holding only the core | 19 | (venv 203.8) |
| Full voice start, development venv, 22 s in | 140 | 3,812.1 (including the GPU add-on) |

A typed turn loads opencv through `security/__init__.py:3` ->
`security/biometric_auth.py:22` -> `vision/__init__.py:40` ->
`vision/face_features.py:35`, and scipy and GitPython through
`integration/orchestrator.py:2715` -> `self_improvement/__init__.py`. All
three imports are guarded, so the core runs without them.

## Measured tiers (Windows, CPython 3.13, against the lock)

Each optional tier was installed on top of a copy of the real core venv, and
its download was resolved as core plus tier minus core, so shared packages
count once. MB here are 10^6 bytes.

| Tier | Packages | Download MB | Disk MB | Notes |
|:--|--:|--:|--:|:--|
| Core as the code stood (sentence-transformers memory) | 68 | 272.6 | 1,203.9 | torch, transformers, scikit-learn, pandas |
| Core with ONNX memory (adopted) | 47 | 88.7 | 326.6 + 11.6 venv | the venv in which `main.py` starts and a typed turn with memory runs |
| Voice, CPU | +60 | 272.0 | +1,053.8 | torch CPU 124.0 MB download (silero VAD), llvmlite, av, ctranslate2 |
| Voice GPU add-on (NVIDIA) | +3 | 1,372.6 | about +2,108 (development venv; UNVERIFIED in a fresh one) | cuBLAS and cuDNN for CTranslate2 |
| Vision | +2 | 48.5 | +132.6 | opencv-python, pillow; the 3,350 MB vision model is separate |
| Research | 0 | 0 | 0 | aiohttp is already in the core |
| Browser | +3 | 39.0 | +113.9 | uses the installed Edge or Chrome; no browser download |
| Coding tools | +3 | 0.3 | +2.1 | GitPython |

Every tier is on by default. The owner's rule is a small download and a
complete install, with no limit on installed size; a person can still turn an
optional tier off on the plan screen or with `--no-tiers`.

The installer itself: the launcher built with PyInstaller is 29.0 MB and the
application source without tests 11.8 MB. Together, as one solid LZMA2 stream
at the Inno Setup script's settings, they are 11.9 MB, against the 80 MB
budget. Inno Setup was not installed on this machine, so the real installer
was not compiled; its size, with Inno's stub of about 2 MB, is UNVERIFIED.

Python itself, when no compatible Python (3.11 to 3.13) is installed: the
NuGet `python` package 3.13.15, 14,391,248 bytes, SHA-256
`05357887df50d3153efc681bdf432c321d3e2f9ce5788f99f4515b27e8fda0ac`, 40 MB
extracted, with `venv` and a bundled pip 26.2.1. Creating a venv from it was
not run here (running a downloaded interpreter was refused on this machine),
so that step is UNVERIFIED.

The application source tracked in git (`Agent_Guru`, `main.py`, `assets`) is
17.0 MB, 6.3 MB of it tests.

Models are never bundled and are listed for the plan only:

| Model | Bytes on disk | Source | Check |
|:--|--:|:--|:--|
| all-MiniLM-L6-v2 ONNX export (memory) | 90,405,214 + tokenizer 466,247 | Hugging Face, revision 1110a243 | SHA-256 pinned |
| Kokoro voice (model + voices) | 325,532,387 + 28,214,398 | GitHub release, pins in `speech/tts/tts_engine.py` | SHA-256 pinned |
| Whisper tiny / base (faster-whisper) | 75 MB / 142 MB in the HF cache | Hugging Face through huggingface_hub | huggingface_hub's own checks |
| The LLM | the user's choice; gemma4 is 9.6 GB | Ollama pull API | Ollama verifies its layers |

## Decisions this audit makes

1. Memory search uses the ONNX export when it is installed (70773ccb). The
   proof: on 38 fixed texts the lowest cosine similarity between the torch
   and ONNX vectors was 1.000000, 8 of 8 retrieval queries picked the same
   memory, the 171 memory and retrieval tests pass unchanged with the ONNX
   route active, and the core drops from 272.6 to 88.7 MB to download and
   from 1,203.9 to 338.3 MB on disk. The int8 export was rejected (lowest
   cosine 0.973).
2. scipy stays in the core: `main.py` imports it on every start through the
   speech engine. Making that import lazy would save 134.3 MB on disk but
   touches speaker verification; it is listed below as an option, not done.
3. Torch is the CPU build on every machine. It runs only silero VAD, which
   the development venv already runs on the CPU build. No torch variant.
4. The only hardware variant is the voice GPU add-on (cuBLAS, cuDNN, NVRTC),
   offered when an NVIDIA GPU is found. Their pins were missing from the lock
   and were added to it. onnxruntime stays the CPU build: Kokoro would use
   CUDA from onnxruntime-gpu, but no measurement shows it is worth about
   200 MB more, so that variant is not offered.
5. A tier is installed from its own requirement list with the lock as
   constraints, never with `pip install -r requirements-lock.txt`: the lock
   pins opencv-python and opencv-contrib-python together, two distributions
   that install the same `cv2` module and must never share a venv.
6. Found while measuring and fixed: `speech/stt/whisper_stt.py` could not be
   imported without faster-whisper, so `main.py` crashed five times and gave
   up in any install without the voice packages (f5a998d1).

## Savings not taken

| Saving | Size | Why not now |
|:--|--:|:--|
| Lazy scipy import in `speech/biometric/voice_features.py` | 134.3 MB disk, 36.6 MB download from the core | changes speaker verification start-up; needs its own proof |
| Silero VAD on onnxruntime instead of torch | most of torch's 124.0 MB download and the 600 MB with sympy and networkx from voice | the silero-vad package requires torch even for its ONNX model |
| Deleting `tests/` folders inside installed wheels | 47.0 MB in the core, 115.1 MB in voice | edits installed packages behind pip's back (`RECORD` no longer matches), and a repair would put them back |
| Debug symbols in wheels | 0 MB | none found (no `.pdb` files) |
| The int8 embedding export | 67 MB | changes the vectors (lowest cosine 0.973) |
