"""Where everything lives inside the portable data folder, as paths relative to its root.

prepare.py fills the folder, verify.py checks it against manifest.json, and the runner
reads from it. All three take their paths from here, so they cannot disagree, and nothing
inside the folder points outside it: copy the folder anywhere and it still works.
"""
from pathlib import PurePosixPath as P

ACAV = P("inputs/features/openwakeword_features_ACAV100M_2000_hrs_16bit.npy")
VALIDATION = P("inputs/features/validation_set_features.npy")
AUDIOSET = P("inputs/background/audioset_bal_train_09.parquet")
# A second AudioSet shard, for everyday sounds as negatives: shard 09 also feeds the false-wake scoring.
AUDIOSET_EXTRA = P("inputs/background/audioset_bal_train_00.parquet")
FMA = P("inputs/background/fma_small_train_00000.parquet")
RIRS = P("inputs/rirs")                               # 270 x 16 kHz WAV
SVARAH = [P(f"inputs/svarah/test-0000{i}-of-00003.parquet") for i in range(3)]
PARLER = P("inputs/models/indic-parler-tts")          # model, config, prompt tokenizer
FLAN_T5 = P("inputs/models/flan-t5-large")            # Parler's description tokenizer
WHISPER = P("inputs/models/faster-whisper-medium")
PIPER = {"pratham": P("inputs/models/piper/hi_IN-pratham-medium.onnx"),
         "priyamvada": P("inputs/models/piper/hi_IN-priyamvada-medium.onnx")}
LIBRITTS = P("inputs/models/libritts_r/en_US-libritts_r-medium.pt")
OWW_MODELS = {f: P(f"inputs/models/openwakeword/{f}") for f in ("embedding_model.onnx", "melspectrogram.onnx")}
OWW_SRC = P("inputs/src/openwakeword")                # at OWW_COMMIT, unpatched
PSG_SRC = P("inputs/src/piper-sample-generator")      # at PSG_TAG
RECORDINGS = P("inputs/recordings/recordings_upload.zip")
BENCH = P("inputs/bench")
WHEELS = {"linux": P("env/wheels/linux"), "linux-cu118": P("env/wheels/linux-cu118")}
PYTHON_LINUX = P("env/python")                        # python-build-standalone tarball
CODE = P("code")                                      # snapshot of the runner
MANIFEST = P("manifest.json")

OWW_COMMIT = "368c03716d1e92591906a84949bc477f3a834455"
PSG_TAG = "v2.0.0"
PSG_COMMIT_URL = "https://github.com/rhasspy/piper-sample-generator"
OWW_URL = "https://github.com/dscripka/openwakeword"
