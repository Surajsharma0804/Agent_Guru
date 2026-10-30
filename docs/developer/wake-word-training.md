# Training the Hey Guru and Hey Maya wake words

A first pair of "Hey Guru" and "Hey Maya" models was trained on this laptop on 2026-10-30 (results
at the end of this page). They are not installed: measured through the assistant's own detector they
miss openWakeWord's aims, and they have not been measured on new recordings in the owner's room. openWakeWord ships models for alexa, hey jarvis,
hey mycroft, hey rhasspy, weather and timers only (under CC BY-NC-SA 4.0, non-commercial). Until a
model is installed the assistant uses the MFCC fallback, which wakes on loud sound and on talk in
the room; its startup log says so (`WakeWordDetector initialised - backend=mfcc: ...`).

## What already exists

| Piece | Where | State |
|:--|:--|:--|
| Training pipeline: synthetic positives (Parler TTS, 21 Indian English and 2 Hindi voices, plus Piper and LibriTTS-R), negatives (ACAV100M features, Svarah's Indian English speakers, near-miss phrases), room impulses, AudioSet and FMA background, openWakeWord training, ONNX export checks, its own benchmark | `wakeword_training/runner/` (not in git), copied into the data folder's `code/` | dry run and kill test proven on the laptop |
| Offline data folder (30.25 GiB, 638 files, hashed) | `E:\agent_guru_wakeword_data` | complete |
| A100 runbook (SLURM) | `wakeword_training/runner/RUNBOOK.md` | not yet run on the A100 |
| One command for all of it | `scripts/train_wake_words.py` | this page |
| Measurement through the assistant's own detector | `scripts/wake_word_eval.py` | harness checked, see below |
| Background audio for false accepts | `scripts/build_wake_background.py` | 53.4 min of sounds, 100 min of music |
| Recording takes | `wakeword_training/scripts/record_wake.py` | 24 tests pass |

The model files go in `%LOCALAPPDATA%\agent_guru\wake_models` as `hey_guru.onnx` and
`hey_maya.onnx`. The detector loads them at startup and logs which it found.

## Installing openWakeWord

It is not a dependency of the project, on purpose. On Linux it requires `tflite-runtime`, which has
no Python 3.13 wheel (3.11 has one), so adding it would break installs and CI there.

- Windows: `.venv\Scripts\python -m pip install openwakeword==0.6.0`. Its other dependencies
  (onnxruntime, scipy, scikit-learn, requests, tqdm) are already in the environment.
- Linux: `pip install --no-deps openwakeword==0.6.0`. The assistant runs the ONNX models only.

Its two feature models (`melspectrogram.onnx`, `embedding_model.onnx`) must be in openWakeWord's
`resources/models` folder; the data folder has them under `inputs/models/openwakeword`.

## 1. Record a held-out set in your room

Training never sees these takes, so they are the only measurement of the models on your voice in
your room. Record after the data folder was packed (2026-10-02), under a speaker name of its own:

```
.venv\Scripts\python wakeword_training\scripts\record_wake.py --list-devices
.venv\Scripts\python wakeword_training\scripts\record_wake.py --speaker suraj_room --takes 25
.venv\Scripts\python wakeword_training\scripts\record_wake.py --speaker suraj_room --contains
```

- Sit where you usually sit, with the microphone the assistant uses, the room as it usually is.
- The first command records 25 takes each of "Hey Guru" and "Hey Maya" in eight styles (normal,
  faster, slower, across the room, soft, louder, busy, as a question). Takes that are too quiet or
  clipped are refused and asked again; a stopped session resumes where it left off.
- The second records sentences that hold a wake phrase without being a wake ("Hey Guru ji", "I told
  her hey Maya is late"). They are measured, not trained on: see "Near misses" below.
- Do not pack these into the data folder. They land in `wakeword_training\recordings\suraj_room\`.

## 2. Background audio for false accepts

```
wakeword_training\venv-313\Scripts\python scripts\build_wake_background.py wakeword_training\bench
```

This writes `bg_noise.npy` and `bg_music.npy` from the data folder's AudioSet and FMA files. The
16.1 minutes of speech in `wakeword_training\bench\wake_neg.npy` is the third set. These are real
recordings mixed by script, not your room; for your room, record 15 minutes of an ordinary evening
(TV on, people talking) without saying the wake word, and add it the same way.

## 3. Train

On the laptop (RTX 2050: 4 hours 2 minutes for both models on 2026-10-30, of which Parler TTS took
105 minutes, training 89 and the benchmark 32) or any CUDA machine:

```
.venv\Scripts\python scripts\train_wake_words.py --data E:\agent_guru_wakeword_data ^
    --work E:\agent_guru_wakeword_work ^
    --heldout wakeword_training\recordings\suraj_room\hey_guru wakeword_training\recordings\suraj_room\hey_maya ^
    --contains wakeword_training\recordings\suraj_room\contains ^
    --background wakeword_training\bench\bg_noise.npy wakeword_training\bench\bg_music.npy wakeword_training\bench\wake_neg.npy
```

Ollama must not hold the GPU while it trains (`ollama stop gemma4:latest`). Run the same command
again after a crash or Ctrl+C; finished stages are skipped. Add `--scale 0.01` for a 12-minute dry
run that checks the pipeline (its models detect nothing; that is expected). On the A100, follow
`wakeword_training/runner/RUNBOOK.md`, then run this command with the trained `work` folder copied
back to skip straight to the measurement.

## 4. Read the measurement

`E:\agent_guru_wakeword_work\out\REPORT.md` is the pipeline's benchmark; `app_eval.json` beside it
is the assistant's detector on your held-out takes:

| In app_eval.json | Meaning | Aim (openWakeWord's own) |
|:--|:--|:--|
| `background.*.per_hour` | false accepts per hour of wake-free audio | under 0.5 |
| `positives.*.false_reject_rate` | share of your takes that did not wake it | under 5% |
| `positives.*.wrong_name` | Guru heard as Maya or the reverse | 0 |
| `positives.*.latency_s_median` | end of the phrase to the wake, in the 1.5 s chunks the assistant uses; speech recognition comes after | under 1.5 s |
| `contains.*.woke` | sentences holding a phrase that woke it | see below |

Only then install: add `--install` to the same command. It refuses unless held-out takes were
measured. Restart the assistant; its log must say `backend=openwakeword: models for hey guru, hey
maya in ...`.

## Near misses

"Hey Guru ji" and "hey Maya" said inside a sentence contain the wake phrase itself. A detector that
listens for the phrase fires before "ji" is said, so these cannot be trained as negatives: doing so
teaches the model to reject the phrase and raises false rejects. They are measured with
`--contains` instead. The harness check below woke on 4 of 4 such sentences, as expected. Whether
"Hey Guru ji" should simply count as a wake is the owner's decision.

## Harness check (not a result)

`scripts/wake_word_eval.py` was run on 2026-10-30 with openWakeWord's stock `hey_jarvis` model
renamed to `hey_jarvis.onnx` as a stand-in, through the assistant's WakeWordDetector:

| Set | Result |
|:--|:--|
| 53.4 min of AudioSet sounds, 100 min of FMA music, 16.1 min of speech | 0 false accepts |
| 18 TTS takes of "hey jarvis" (2 voices, 3 speeds, 3 phrasings) | 18 woke, right name, latency median 0.0 s, max 0.64 s |
| 4 sentences containing "hey jarvis" | 4 woke |
| Compute | 84 ms per 1.5 s chunk (median), 147 ms (p95) |

These numbers say the harness works. They say nothing about Guru or Maya.

## First trained models (2026-10-30, laptop, not installed)

The pipeline's own benchmark (`E:\agent_guru_wakeword_work\out\REPORT.md`), at its operating
threshold of 0.35:

| Set | Result |
|:--|:--|
| The owner's 16 takes held back from training (same session as the training takes) | 16/16 |
| TTS: 28 dev clips, 80 held-out clips of unseen voices, 48 Hindi clips | 27/28, 62/80 (78%), 47/48 |
| Bare names "Guru", "Maya" (not what these models are for) | 3/40 |
| 16.1 min of speech; Svarah's 34 held-out speakers (3.4 h) | 0 false wakes per hour on both |
| The owner's recorded negatives | 4 of 21 woke it ("Hey Google" twice, "Hey Mario" twice); 1 of 9 with the name ("My guru told me something") |

Through the assistant's WakeWordDetector (`scripts/wake_word_eval.py`, threshold 0.5 from the
default sensitivity, 1.5 s chunks):

| Set | Result | Aim |
|:--|:--|:--|
| 53.4 min of AudioSet sounds | 6 false accepts, 6.7 per hour | under 0.5 |
| 100 min of FMA music | 4 false accepts, 2.4 per hour | under 0.5 |
| 16.1 min of speech | 0 | under 0.5 |
| The owner's 16 held-back takes | 13 woke with the right name, 3 missed (19%); latency median 0.36 s, max 1.27 s | under 5% |
| Compute, both models | 173 ms per 1.5 s chunk (median) | |

Next: record the in-room held-out set (step 1), add the four negatives that woke it and everyday
sounds to the training negatives, and retrain; a retrain that reuses these clips costs only the
training step (about 65 minutes here).
