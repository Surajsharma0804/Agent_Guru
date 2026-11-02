"""Indic Parler-TTS and Piper clip generation: batched by prompt text, capped per language, resumable.

Batching: every batch holds one prompt text only. This model adds positions by plain count
and ignores the prompt padding mask (rope_embeddings and prompt_cross_attention are both off;
Parler's own source carries a TODO saying so), so a padded prompt shifts every later position
and changes that clip: in a mixed-text batch 12 of 16 clips differed from their solo
generation; with one text per batch 16 of 16 were bit-identical. Descriptions may differ in
length; their padding was shown not to leak.

Caps: English 5.0 s, Hindi 6.0 s, above the longest of 480 measured clips (English p99 2.85 s,
longest 4.13; Hindi p99 4.29 s, longest 4.99). A clip that comes back empty (< 0.3 s, Parler
stops at once) or reaches its cap is regenerated with a new description, up to PARLER_TRIES
times; both are counted per language and text, and so is each clip's longest internal pause.
"""
from __future__ import annotations

import collections
import io
import math
import random
import time
import wave
from pathlib import Path

import numpy as np

FRAMES_PER_S, DAC_DELAY = 86.13, 9
CAP_S = {"en": 5.0, "hi": 6.0}
CAP_STEPS = {lang: math.ceil(s * FRAMES_PER_S) + DAC_DELAY for lang, s in CAP_S.items()}
EMPTY_S = 0.3
PARLER_TRIES = 3
PACES = ["slow", "slightly slow", "moderate", "slightly fast", "fast"]
PITCHES = ["low", "moderate", "slightly high", "high"]
STYLES = ["monotone", "slightly expressive", "expressive"]
QUALITIES = ["very clear audio, very close-sounding", "clear audio", "slightly noisy audio, with some room echo"]


def describe(speaker, key):
    """Voice description drawn from a generator seeded by the clip's file name and attempt, so a
    resumed run asks for exactly the clips the interrupted one would have."""
    rng = random.Random(key)
    return (f"{speaker} speaks at a {rng.choice(PACES)} pace with a {rng.choice(PITCHES)} pitch and a "
            f"{rng.choice(STYLES)} delivery. The recording has {rng.choice(QUALITIES)}.")


def max_gap_ms(a, sr):
    """Longest pause inside the speech: 10 ms frames, -30 dB below the loudest frame."""
    f = int(sr * 0.01)
    n = len(a) // f
    if n < 3:
        return 0
    rms = np.sqrt(np.mean(a[: n * f].reshape(n, f) ** 2, axis=1)) + 1e-9
    db = 20 * np.log10(rms / rms.max())
    on = np.flatnonzero(db > -30)
    best = run = 0
    for quiet in db[on[0]: on[-1] + 1] <= -30:
        run = run + 1 if quiet else 0
        best = max(best, run)
    return best * 10


def write16k(path, audio, sr):
    """16 kHz int16 WAV under a temporary name, then renamed: a kill never leaves a half clip
    that a resumed run would take for a finished one."""
    import os

    import scipy.io.wavfile
    import scipy.signal
    a = np.asarray(audio, dtype=np.float32)
    a = a.mean(axis=1) if a.ndim > 1 else a
    if np.abs(a).max() > 1.5:
        a = a / 32768.0
    a = scipy.signal.resample_poly(a, 16000, sr).astype(np.float32) if sr != 16000 else a
    tmp = Path(str(path) + ".tmp")
    with open(tmp, "wb") as f:
        scipy.io.wavfile.write(f, 16000, (np.clip(a, -1, 1) * 32767).astype(np.int16))
    os.replace(tmp, path)


class Parler:
    def __init__(self, model_dir, tokenizer_dir, dtype, device="cuda"):
        import torch
        from parler_tts import ParlerTTSForConditionalGeneration
        from transformers import AutoTokenizer
        self.torch, self.device = torch, device
        self.model = ParlerTTSForConditionalGeneration.from_pretrained(
            str(model_dir), torch_dtype=getattr(torch, dtype), local_files_only=True).to(device).eval()
        self.p_tok = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True)
        self.d_tok = AutoTokenizer.from_pretrained(str(tokenizer_dir), local_files_only=True)
        self.sr = self.model.config.sampling_rate
        self.hop = round(self.sr / FRAMES_PER_S)

    def generate(self, text, descs, lang):
        """[(audio or None, reason)] for one prompt text; reason "ok", "empty" or "capped"."""
        cap = CAP_STEPS[lang]
        d = self.d_tok(descs, return_tensors="pt", padding=True).to(self.device)
        p = self.p_tok([text] * len(descs), return_tensors="pt", padding=True).to(self.device)
        assert int(p.attention_mask.min()) == 1, "a prompt was padded: a batch must share one text"
        with self.torch.no_grad():
            out = self.model.generate(input_ids=d.input_ids, attention_mask=d.attention_mask,
                                      prompt_input_ids=p.input_ids, prompt_attention_mask=p.attention_mask,
                                      max_new_tokens=cap, return_dict_in_generate=True)
        res = []
        for i in range(len(descs)):
            a = out.sequences[i, :out.audios_length[i]].float().cpu().numpy()
            if len(a) < EMPTY_S * self.sr:
                res.append((None, "empty"))
            elif len(a) >= (cap - DAC_DELAY - 1) * self.hop:
                res.append((None, "capped"))
            else:
                res.append((a, "ok"))
        return res


class Ledger:
    """Rejected attempts by language, text and reason, and each kept clip's longest pause;
    saved after every batch, so the counts survive any number of restarts."""

    def __init__(self, state):
        self.state = state
        self.d = state.load("parler_ledger", {"attempts": {}, "gave_up": [], "by": {}, "kept": {}, "gaps": {}})

    def tries(self, fname):
        return len(self.d["attempts"].get(fname, []))

    def reject(self, fname, lang, text, reason):
        self.d["attempts"].setdefault(fname, []).append(reason)
        k = f"{lang}|{text}|{reason}"
        self.d["by"][k] = self.d["by"].get(k, 0) + 1

    def keep(self, lang, text, gap_ms):
        k = f"{lang}|{text}"
        self.d["kept"][k] = self.d["kept"].get(k, 0) + 1
        self.d["gaps"].setdefault(k, []).append(int(gap_ms))

    def give_up(self, fname):
        if fname not in self.d["gave_up"]:
            self.d["gave_up"].append(fname)

    def save(self):
        self.state.save("parler_ledger", self.d)


def pick_batch(tts, text, lang, speakers, ceiling, log):
    """Fastest batch size up to the ceiling, measured on one text: one batch per size, doubling
    while seconds per clip keeps improving by more than 5%. The clips are thrown away."""
    sizes = [s for s in (8, 16, 32, 64, 128, 256, 512) if s <= ceiling] or [ceiling]
    best, best_rate, rows = sizes[0], None, []
    for s in sizes:
        descs = [describe(speakers[i % len(speakers)], f"probe/{s}/{i}") for i in range(s)]
        try:
            tts.torch.cuda.synchronize() if tts.device == "cuda" else None
            t = time.time()
            tts.generate(text, descs, lang)
            tts.torch.cuda.synchronize() if tts.device == "cuda" else None
        except tts.torch.OutOfMemoryError:
            log(f"  batch {s}: out of memory")
            tts.torch.cuda.empty_cache()
            break
        rate = (time.time() - t) / s
        peak = tts.torch.cuda.max_memory_allocated() / 2**30 if tts.device == "cuda" else 0
        rows.append({"batch": s, "s_per_clip": round(rate, 3), "peak_gib": round(peak, 2)})
        log(f"  batch {s}: {rate:.3f} s/clip, peak {peak:.2f} GiB")
        if best_rate is not None and rate > best_rate * 0.95:
            break
        if best_rate is None or rate < best_rate:
            best, best_rate = s, rate
    return best, rows


def run_parler(tts, ledger, jobs, out_dir, batch, log, label):
    """Generate every (fname, speaker, text, lang) job not on disk, batched by text, retrying rejects."""
    t0, made = time.time(), 0
    todo = [j for j in jobs if not (out_dir / j[0]).exists() and j[0] not in ledger.d["gave_up"]]
    log(f"{label}: {len(jobs) - len(todo)} of {len(jobs)} clips already done, {len(todo)} to generate")
    by_text = collections.defaultdict(list)
    for j in todo:
        by_text[(j[2], j[3])].append(j)
    for (text, lang), group in by_text.items():
        queue = list(group)
        while queue:
            chunk, queue = queue[:batch], queue[batch:]
            descs = [describe(spk, f"{fname}#{ledger.tries(fname)}") for fname, spk, _, _ in chunk]
            for (fname, spk, _, _), (audio, reason) in zip(chunk, tts.generate(text, descs, lang)):
                if reason == "ok":
                    write16k(out_dir / fname, audio, tts.sr)
                    ledger.keep(lang, text, max_gap_ms(audio, tts.sr))
                    made += 1
                    continue
                ledger.reject(fname, lang, text, reason)
                if ledger.tries(fname) < PARLER_TRIES:
                    queue.append((fname, spk, text, lang))
                else:
                    ledger.give_up(fname)
            ledger.save()
        log(f"{label}: {text!r} done, {made} made so far")
    return made, time.time() - t0


def run_piper(voice_paths, jobs, out_dir):
    """Piper hi_IN clips, one at a time (fast), each with lengths seeded by its file name."""
    import scipy.io.wavfile
    from piper import PiperVoice, SynthesisConfig
    voices = {}
    made = 0
    for fname, voice, text in jobs:
        if (out_dir / fname).exists():
            continue
        if voice not in voices:
            voices[voice] = PiperVoice.load(str(voice_paths[voice]))
        rng = random.Random(fname)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            voices[voice].synthesize_wav(text, w, syn_config=SynthesisConfig(
                length_scale=rng.choice([0.7, 0.8, 0.9, 1.0, 1.1, 1.25, 1.4]),
                noise_scale=rng.choice([0.5, 0.667, 0.8, 1.0]), noise_w_scale=rng.choice([0.6, 0.8, 1.0])))
        buf.seek(0)
        sr, a = scipy.io.wavfile.read(buf)
        write16k(out_dir / fname, a, sr)
        made += 1
    return made
