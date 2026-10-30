"""How many recorded commands the fallback wake's name check would drop.

    python scripts/name_check_eval.py <folder of .wav takes> [<folder> ...]

Each take is transcribed the way the assistant transcribes a command (SpeechEngine's Whisper settings)
and checked with the same rule a fallback wake uses (speech/audio/wake_word.py, wake_name). Every take
here is a command said to the assistant, so every one the rule rejects is a false reject: the owner
would have spoken and heard nothing. Record takes with
wakeword_training/scripts/record_wake.py --speaker <name> --commands.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SR = 16000


def main(folders: list[str]) -> int:
    import numpy as np
    import soundfile as sf

    from Agent_Guru.speech.audio.wake_word import wake_name
    from Agent_Guru.speech.config import STTConfig
    from Agent_Guru.speech.stt.whisper_stt import WhisperTranscriber

    stt = STTConfig()
    whisper = WhisperTranscriber(model_size=stt.model_size, model_path=stt.model_path,
                                 compute_type=stt.compute_type, beam_size=stt.beam_size, device=stt.device)
    takes = sorted(f for folder in folders for f in Path(folder).rglob("*.wav"))
    if not takes:
        print("no .wav takes found")
        return 2
    rejected = []
    for wav in takes:
        audio, rate = sf.read(wav, dtype="float32", always_2d=True)
        audio = audio.mean(axis=1)
        if rate != SR:
            from scipy.signal import resample_poly

            audio = resample_poly(audio, SR, rate).astype(np.float32)
        text = whisper.transcribe(audio, SR).text
        if wake_name(text) is None:
            rejected.append((wav.name, text))
    print(f"{len(takes) - len(rejected)} of {len(takes)} takes heard as naming Guru or Maya; "
          f"{len(rejected)} would be dropped ({len(rejected) / len(takes):.0%})")
    for name, text in rejected:
        print(f"  dropped {name}: heard {text!r}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]) if len(sys.argv) > 1 else (print(__doc__) or 2))
