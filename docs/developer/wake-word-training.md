# Training the Hey Guru and Hey Maya wake words

Three pairs of "Hey Guru" and "Hey Maya" models have been trained on this laptop (2026-10-30, and
twice on 2026-10-31; results at the end of this page). None is installed: measured through the
assistant's own detector on audio no model was trained with, all three wake more often on music than
openWakeWord's aim, and none has been measured on new recordings in the owner's room. openWakeWord ships models for alexa, hey jarvis, hey mycroft,
hey rhasspy, weather and timers only (under CC BY-NC-SA 4.0, non-commercial). Until a model is
installed the assistant uses the MFCC fallback, which wakes on loud sound; a turn it starts goes
ahead only when what was heard names Guru or Maya (see "The name check"). The startup log says which
detector runs (`WakeWordDetector initialised - backend=mfcc: ...`).

## What already exists

| Piece | Where | State |
|:--|:--|:--|
| Training pipeline: synthetic positives (Parler TTS, 21 Indian English and 2 Hindi voices, plus Piper and LibriTTS-R), negatives (ACAV100M features, Svarah's Indian English speakers, near-miss phrases), room impulses, AudioSet and FMA background, openWakeWord training, ONNX export checks, its own benchmark | `wakeword_training/runner/` (not in git), copied into the data folder's `code/` | dry run and kill test proven on the laptop |
| Offline data folder (30.89 GiB, 640 files, hashed) | `E:\agent_guru_wakeword_data` | complete; AudioSet shard 00 added 2026-10-31 |
| A100 runbook (SLURM) | `wakeword_training/runner/RUNBOOK.md` | not yet run on the A100 |
| One command for all of it | `scripts/train_wake_words.py` | this page |
| Measurement through the assistant's own detector | `scripts/wake_word_eval.py` | harness checked, see below |
| Which background clips training may use and which are only scored | `scripts/wake_audio_pools.json`, written by `scripts/split_wake_pools.py` | a test fails if a clip is in both |
| Background audio for false accepts | `scripts/build_wake_background.py` | 56.2 min of sounds, 100 min of music, from the scoring pool |
| In-room held-out takes through the assistant's detector | `scripts/room_wake_eval.py` | waiting for recordings |
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

### A second held-out set: distance and TV

The first held-out set (the 16 takes of 2026-10-01 held back from training) stays fixed so every
model is compared on it. It was recorded close to the microphone in one sitting. The second covers
three distances, each quiet and with the TV on, 25 takes of each phrase per condition. Use the
microphone and the seat the assistant normally hears you from.

1. Find the microphone's device number:
   `.venv\Scripts\python wakeword_training\scripts\record_wake.py --list-devices`
2. Quiet room, TV off, nobody talking. Record at three distances, adding `--device <n>` if the
   default is not that microphone:
   - within arm's length: `.venv\Scripts\python wakeword_training\scripts\record_wake.py --speaker room_near_quiet --takes 25`
   - 2 metres away: `... --speaker room_2m_quiet --takes 25`
   - across the room, as far as you would ever call it from: `... --speaker room_far_quiet --takes 25`
3. TV on, playing speech (news or a talk show) at the volume you watch at. Repeat the three distances
   with `room_near_tv`, `room_2m_tv` and `room_far_tv`.
4. Optional, for false wakes in your own room: with the TV on and people talking as on an ordinary
   evening, and nobody saying Guru or Maya, record 10 minutes, up to three times:

   ```
   mkdir wakeword_training\recordings\room_sound
   .venv\Scripts\python -c "import sounddevice as sd, soundfile as sf; a = sd.rec(600 * 16000, samplerate=16000, channels=1, dtype='float32'); sd.wait(); sf.write(r'wakeword_training\recordings\room_sound\score_1.wav', a, 16000)"
   ```

   (`score_2.wav` and `score_3.wav` for the others). These are scored only; training does not read them.
5. The 20-command batch for the name check: `... --speaker suraj_cmds --commands`. Then
   `.venv\Scripts\python scripts\name_check_eval.py wakeword_training\recordings\suraj_cmds`. Every
   take it lists as dropped is a command that would have gone unanswered; the aim is under 1 in 20.
6. Measure any model folder on all of it:
   `wakeword_training\venv-oww\Scripts\python scripts\room_wake_eval.py --models <folder with hey_guru.onnx and hey_maya.onnx>`.
   A condition that was not recorded is listed as "not recorded", not as a result.

All seven speaker folders are listed in `wakeword_training\recordings\bench_only.txt`, so
`pack_recordings.py` sends them to the benchmark only and training never hears them. Keep that list
when you add a held-out speaker.

## 2. Background audio for false accepts

```
wakeword_training\venv-313\Scripts\python scripts\build_wake_background.py wakeword_training\bench
```

This writes `bg_noise.npy` and `bg_music.npy` from the clips in the scoring pool of
`scripts/wake_audio_pools.json`: AudioSet balanced shard 01 (341 clips with no speech, singing, TV or
radio label, 56.2 min) and the first 200 tracks of FMA file 00001 (100 min), both under
`inputs\score_pool` in the data folder. Training reads only the training pool and stops on any clip
that is not in it. The 16.1 minutes of speech in `wakeword_training\bench\wake_neg.npy` is the third
set; training never reads it. These are real recordings mixed by script, not your room (see step 4
of the second held-out set).

Until 2026-10-31 these sets were built from AudioSet shard 09 and the first 200 tracks of FMA file
00000, which training also mixed under its examples: all 325 sound clips and 120 of the 200 music
tracks had been heard in training. Figures on those sets (the first and second models below) are not
comparable with figures on the scoring pool.

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

## The name check

While the fallback decides wakes, a turn it starts goes ahead only if the turn's own transcript names
Guru or Maya (`speech/audio/wake_word.py`, `wake_name`). The check switches itself off when a trained
model is installed and chosen at startup. Measured over the whole background fixtures, every kept
false wake transcribed by the assistant's speech recognition: false turns per hour fell from 42.7 to
1.1 on everyday sounds, 24.0 to 0.6 on music and 130.1 to 0.0 on speech. Real commands: the owner's
16 held-back takes each followed by a command all pass, but said alone 3 of 16 are dropped; synthetic
sets not used to build the rule lose 10 of 80 unseen voices, 0 of 48 Hindi and 12 of 40 bare names.
Measure it on your own commands with `scripts/name_check_eval.py` before relying on it.

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

## Second models (2026-10-31, laptop, not installed)

Retrained from the same Parler clips (2 hours 1 minute, 00:37 to 02:38) with: "Hey Guru ji" and "Hey Maya ji" among
the generated positives; "hey siri", "hey alexa", "hey google", "hey mario", "ok google",
"hey gurukul" and "hey mayank" among the near-miss negatives; and a new negative set of 7,539
two-second windows from AudioSet shard 00 (everyday sounds), shard 09's speech, TV and radio clips,
and FMA tracks 200 onwards, none of which are in the false-wake scoring sets. The training
augmentation (unchanged from the first run) mixes AudioSet shard 09 and the first 120 FMA tracks under
clips as background, and those overlap the scoring sets.

Through the assistant's WakeWordDetector, same held-out sets as the first models:

| Set | First models | Second models | Aim |
|:--|:--|:--|:--|
| 53.4 min of AudioSet sounds | 6.7 per hour | 3.4 per hour | under 0.5 |
| 100 min of FMA music | 2.4 per hour | 1.2 per hour | under 0.5 |
| 16.1 min of speech | 0 | 3.7 per hour (1 wake) | under 0.5 |
| The owner's 16 held-back takes | 13/16 | 13/16 (19% missed) | under 5% |
| 18 synthetic "Hey Guru/Maya ji" clips | 10/18 | 14/18 | |
| 12 synthetic plain clips, same voices | 12/12 | 12/12 | |

The pipeline's own benchmark chose a threshold of 0.65 (the first run 0.35): the owner's takes 16/16,
unseen synthetic voices 56/80 (first run 62/80), 0 false wakes per hour on Svarah, 3 of 21 of the
owner's recorded negatives woke it ("Hey Google" once, "Hey Mario" twice; first run 4 of 21).

Still missing for an install: false wakes are 2 to 7 times the aim, and 3 of 16 of the owner's takes
are missed through the assistant's detector though the pipeline benchmark wakes on all 16 (its
threshold differs and it scores every 80 ms frame, where the assistant decides per 1.5 s chunk).
Next: record the second held-out set above, check whether the detector's threshold (0.5 from the
default sensitivity) or its chunking is what misses the 3 takes, and add real everyday sound from the
room to the negatives.

## Why the assistant's detector missed takes the benchmark caught (2026-10-31)

The 3 takes missed by the assistant's detector were all lost to its cooldown. For 3 s after a wake
the detector returned before openWakeWord saw any audio. Two takes began inside a cooldown and were
never scored; one began just after it and was scored spliced onto audio from before the gap (0.005
through the detector, 0.974 for the same samples fed without a gap). Where both paths scored the same
audio the scores agreed within 0.03, so the threshold, resampling and scaling were not the cause.
The detector now feeds the model through the cooldown and only holds back the wake. Both earlier
model pairs then wake on 16 of 16 takes, false wakes are unchanged, and CPU per 1.5 s chunk while
listening stays at 79 ms (a chunk in cooldown now costs 78 ms instead of 0).

## Rescored on the scoring pool (2026-10-31)

Through the assistant's detector, after the cooldown fix:

| Set | First models | Second models | Third models | Aim |
|:--|:--|:--|:--|:--|
| 56.2 min of unheard sounds | 5 wakes, 5.3 per hour | 0 | 0 | under 0.5 |
| 100 min of unheard music | 4 wakes, 2.4 per hour | 2 wakes, 1.2 per hour | 2 wakes, 1.2 per hour | under 0.5 |
| 16.1 min of speech | 0 | 1 wake, 3.7 per hour | 0 | under 0.5 |
| The owner's 16 held-back takes | 16/16 | 16/16 | 16/16 | under 5% missed |
| 48 synthetic Hindi takes | | | 44/48 | |

On the old, overlapping sets the first and second models had shown 6.7 and 3.4 false wakes an hour on
sounds: training on those clips had not made the old figures look better. The counts are small; 0
wakes in 56 minutes is consistent with anything up to about 3 an hour.

## Third models (2026-10-31, laptop, not installed)

Retrained from the second run's Parler clips and features with the split pools: the extra negatives
are now all of AudioSet shards 00 and 09 and all 493 tracks of FMA file 00000 (12,014 two-second
windows, was 7,539), since none of them is scored any more. The run took 1 hour 31 minutes (training
69, the benchmark 14). The
pipeline's benchmark chose a threshold of 0.45: the owner's takes 16/16, unseen synthetic voices 55/80
(second run 56/80), Hindi 45/48, 0.29 false wakes per hour on Svarah, 3 of 21 of the owner's recorded
negatives woke it ("Hey Google" once, "Hey Mario" twice).

Not installed: 2 false wakes in 100 minutes of music is 1.2 an hour, over the 0.5 aim, and the in-room
held-out set has not been recorded. No room sound was recorded, so none is among the negatives.
