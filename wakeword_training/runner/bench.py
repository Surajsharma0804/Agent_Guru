"""Score trained wake-word models on the held-back benchmark; returns everything the report prints.

Detector, as Agent Guru runs it and as scripts/score_oww.py scored it: one continuous stream
of 80 ms frames with model state carried across; a wake is the first frame scoring at or over
the threshold, then a 3 s cooldown; the wake's name is whichever model scored higher.

Positives (a hit is the right name within the clip or 1 s after it):
  your takes (recordings zip, bench/ half): "hey" phrases, bare names, Hindi phrasing, per speaker
  wake_pos (28, 7 TTS voices), wake_heldout (80, 10 unseen TTS voices, 10 dB SNR)
  hindi_pos (48, Kokoro Hindi voices), bare_pos (40, Kokoro + Windows SAPI); for these two the
  subset Whisper medium confirmed is scored too, because some of those voices mispronounce
Negatives:
  wake_neg (16.1 min of speech with no wake phrase), Svarah's held-out speakers (Indian English),
  your recorded negatives, split: the ones containing the name ("My guru told me something",
  "The gurudwara is near the market", "Maya is coming home") are their own category
"""
from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path

import numpy as np

SR, FRAME, COOLDOWN = 16000, 1280, 3.0
THRESHOLDS = [round(x, 2) for x in np.arange(0.1, 0.96, 0.05)]
FLOOR_RMS, SPEECH_RMS = 0.00002, 0.025
FW_TARGET = 0.5        # false wakes per hour the operating threshold must stay under


def _devanagari(s):
    return any("ऀ" <= c <= "ॿ" for c in s)


def _name_of(text):
    t = text.lower()
    return "maya" if ("maya" in t or "माया" in text) else "guru"


def dev_set_name(clip):
    """Wake name of a clip in the TTS dev and held-out sets, which name clips by take number."""
    return "maya" if re.search(r"(_1|_3|_01\.wav|_03\.wav)$", clip) else "guru"


def _stream(clips, rng, gap=(3.0, 5.0)):
    parts, spans, t = [], [], 0.0
    for meta, a in clips:
        g = float(rng.uniform(*gap))
        parts += [rng.normal(0, FLOOR_RMS, int(SR * g)).astype(np.float32), a.astype(np.float32)]
        t += g
        spans.append({**meta, "t0": t, "t1": t + len(a) / SR})
        t += len(a) / SR
    parts.append(rng.normal(0, FLOOR_RMS, SR * 4).astype(np.float32))
    return np.concatenate(parts), spans


def real_sets(zip_path, rng):
    """The held-back half of the user's recordings, as one stream per category."""
    import soundfile as sf
    z = zipfile.ZipFile(zip_path)
    cats = {"hey": [], "bare": [], "hindi": [], "negative": []}
    for name in sorted(n for n in z.namelist() if n.startswith("bench/") and n.endswith(".wav")):
        folder, fname = name.split("/")[1], name.split("/")[-1]
        a, sr = sf.read(io.BytesIO(z.read(name)), dtype="float32")
        assert sr == SR, name
        speaker = fname.split("_")[0]
        if folder == "negative":
            cat, wake = "negative", None
            contains = bool(re.search(r"guru|maya", fname.lower()))
        else:
            cat = "hindi" if _devanagari(folder) else "bare" if folder in ("guru", "maya") else "hey"
            wake, contains = _name_of(folder), True
        cats[cat].append(({"clip": fname, "speaker": speaker, "wake": wake, "contains_name": contains,
                           "lang": "hi" if cat == "hindi" else "en"}, a))
    return {c: _stream(v, rng) for c, v in cats.items() if v}


def tts_set(bench_dir, npy, spans_file, lang, labeller):
    a = np.load(bench_dir / npy)
    spans = json.loads((bench_dir / spans_file).read_text(encoding="utf-8"))
    tx = {}
    if (bench_dir / "bench_extra_tx.json").exists():
        tx = json.loads((bench_dir / "bench_extra_tx.json").read_text(encoding="utf-8"))
    out = []
    for clip, t0, t1 in spans:
        wake = labeller(clip)
        heard = tx.get(clip, {}).get("heard")
        out.append({"clip": clip, "wake": wake, "lang": lang, "t0": t0, "t1": t1, "speaker": clip.split("_")[0],
                    "whisper_confirmed": None if heard is None else _heard(heard, wake)})
    return a, out


def _heard(text, name):
    words = re.sub(r"[^a-zऀ-ॿ]+", " ", text.lower()).split()
    dev = {"guru": ("गुरु", "गुरू"), "maya": ("माया",)}[name]

    def lev(a, b):
        d = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            p, d[0] = d[0], i
            for j, cb in enumerate(b, 1):
                p, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, p + (ca != cb))
        return d[-1]
    return any(lev(w, name) <= 1 or w in dev for w in words)


def svarah_stream(svarah_paths, split_json, fraction, rng):
    """Svarah's held-out speakers at the live mic's speech level (as scripts/svarah_bench.py)."""
    import pyarrow.parquet as pq
    import scipy.signal
    import soundfile as sf
    split = json.loads(Path(split_json).read_text(encoding="utf-8"))
    rows = split["bench_rows"]
    wanted = set(rows[: max(1, int(len(rows) * fraction))])
    parts, row = [], 0
    for path in svarah_paths:
        for b in pq.ParquetFile(path).iter_batches(batch_size=64, columns=["audio_filepath"]):
            for cell in b.column(0).to_pylist():
                if row in wanted:
                    a, sr = sf.read(io.BytesIO(cell["bytes"]), dtype="float32")
                    a = a.mean(axis=1) if a.ndim > 1 else a
                    a = scipy.signal.resample_poly(a, SR, sr).astype(np.float32) if sr != SR else a
                    a = a * (SPEECH_RMS / max(float(np.sqrt(np.mean(a ** 2))), 1e-9))
                    parts += [a.astype(np.float32), rng.normal(0, FLOOR_RMS, int(SR * 0.6)).astype(np.float32)]
                row += 1
    keys = split.get("bench_speaker_keys", split["bench_speakers"])   # older splits: a count, or a list
    return np.concatenate(parts), len(wanted), keys if isinstance(keys, int) else len(keys)


class Scorer:
    def __init__(self, model_paths):
        from openwakeword.model import Model
        self.m = Model(wakeword_models=[str(p) for p in model_paths], inference_framework="onnx")
        self.keys = list(self.m.models)
        self.names = [_name_of(Path(p).stem) for p in model_paths]

    def scores(self, stream):
        self.m.reset()
        pcm = (np.clip(stream, -1, 1) * 32767).astype(np.int16)
        out = []
        for s in range(0, len(pcm) - FRAME + 1, FRAME):
            p = self.m.predict(pcm[s:s + FRAME])
            out.append([p[k] for k in self.keys])
        return np.array(out)

    def wakes(self, sc, thr):
        found, last = [], -1e9
        for i, row in enumerate(sc):
            t = (i + 1) * FRAME / SR
            if t - last < COOLDOWN or row.max() < thr:
                continue
            found.append((t, self.names[int(row.argmax())]))
            last = t
        return found


def _peak_scores(scorer, sc, spans):
    """Each clip's highest score for the model that should wake, within the clip or 1 s after."""
    peaks = []
    for s in spans:
        col = scorer.names.index(s["wake"]) if s.get("wake") in scorer.names else None
        a, b = int(s["t0"] * SR / FRAME), int((s["t1"] + 1.0) * SR / FRAME) + 1
        seg = sc[max(0, a - 1): b]
        if col is not None and len(seg):
            peaks.append(float(seg[:, col].max()))
    return peaks


def _summary(xs):
    xs = np.array(xs) if len(xs) else np.zeros(1)
    return {"n": int(len(xs)), "p10": round(float(np.percentile(xs, 10)), 4), "median": round(float(np.median(xs)), 4),
            "p90": round(float(np.percentile(xs, 90)), 4), "max": round(float(xs.max()), 4)}


def _positives(scorer, sc, spans, thr):
    found = scorer.wakes(sc, thr)
    res = []
    for s in spans:
        hit = next((name for t, name in found if s["t0"] <= t <= s["t1"] + 1.0), None)
        res.append({**s, "hit": hit == s["wake"], "wrong_name": hit is not None and hit != s["wake"]})
    return res


def _clip_negatives(scorer, sc, spans, thr):
    found = scorer.wakes(sc, thr)
    return [{**s, "woke": any(s["t0"] <= t <= s["t1"] + 1.0 for t, _ in found)} for s in spans]


def run(model_paths, model_set, bench_dir, zip_path, svarah_paths, split_json, svarah_fraction, log,
        validation_dir=None):
    import bench_selftest
    selftest = bench_selftest.run(bench_dir, log)       # raises if the scorer cannot see a known detector
    rng = np.random.default_rng(41)
    scorer = Scorer(model_paths)
    pos, neg_streams = {}, {}
    real = real_sets(zip_path, rng)
    for cat in ("hey", "bare", "hindi"):
        if cat in real:
            pos[f"your takes: {cat}"] = (*real[cat], "real")
    tail = lambda clip: clip.rsplit("_", 1)[1]                                                 # noqa: E731
    pos["TTS dev 28"] = (*tts_set(bench_dir, "wake_pos.npy", "wake_pos_spans.json", "en", dev_set_name), "tts")
    pos["TTS held-out 80"] = (*tts_set(bench_dir, "wake_heldout.npy", "wake_heldout_spans.json", "en", dev_set_name), "tts")
    pos["TTS Hindi 48"] = (*tts_set(bench_dir, "hindi_pos.npy", "hindi_pos_spans.json", "hi", tail), "tts")
    pos["TTS bare names 40"] = (*tts_set(bench_dir, "bare_pos.npy", "bare_pos_spans.json", "en", tail), "tts")
    log("benchmark: scoring positives")
    scored = {k: (scorer.scores(a), spans, kind) for k, (a, spans, kind) in pos.items()}
    log("benchmark: scoring negatives")
    neg = np.load(bench_dir / "wake_neg.npy")
    neg_streams["16.1 min of speech"] = (scorer.scores(neg), len(neg) / SR / 3600)
    sv, n_utts, n_speakers = svarah_stream(svarah_paths, split_json, svarah_fraction, rng)
    neg_streams[f"Svarah, {n_speakers} held-out speakers"] = (scorer.scores(sv), len(sv) / SR / 3600)
    # Validation audio: training-pool clips the models never read (scripts/wake_audio_pools.json),
    # built by build_validation.py. Only these and VALIDATION_POSITIVES choose the threshold.
    val_streams = {}
    for f in sorted(Path(validation_dir).glob("val_*.npy")) if validation_dir else []:
        a = np.load(f)
        val_streams[f.stem] = (scorer.scores(a), len(a) / SR / 3600)
    negs_sc = None
    if "negative" in real:
        negs_sc = (scorer.scores(real["negative"][0]), real["negative"][1])
    # Score separation, independent of any threshold: a weak model shows here whether its
    # positives at least score above its negatives (the dry run's tiny models score near zero
    # everywhere, and a table of 0% alone could not tell that apart from a broken scorer).
    separation = {"positives (each clip's peak)": {k: _summary(_peak_scores(scorer, sc, spans))
                                                   for k, (sc, spans, kind) in scored.items()},
                  "negatives (frame scores)": {k: {**_summary(sc.max(axis=1)),
                                                   "p99_9": round(float(np.percentile(sc.max(axis=1), 99.9)), 4)}
                                               for k, (sc, hours) in neg_streams.items()}}
    table = []
    for thr in THRESHOLDS:
        row = {"threshold": thr, "sets": {}, "false_wakes": {}, "your_negatives": {}, "validation": {}}
        for k, (sc, spans, kind) in scored.items():
            r = _positives(scorer, sc, spans, thr)
            row["sets"][k] = {"n": len(r), "hits": sum(x["hit"] for x in r), "wrong": sum(x["wrong_name"] for x in r),
                              "by_speaker": _group(r, "speaker"), "by_lang": _group(r, "lang")}
            conf = [x for x in r if x.get("whisper_confirmed")]
            if conf:
                row["sets"][k]["whisper_confirmed"] = {"n": len(conf), "hits": sum(x["hit"] for x in conf)}
        for k, (sc, hours) in neg_streams.items():
            fw = len(scorer.wakes(sc, thr))
            row["false_wakes"][k] = {"count": fw, "hours": round(hours, 3), "per_hour": round(fw / hours, 2)}
        row["validation"] = {
            "positives": {k: v for k, v in row["sets"][VALIDATION_POSITIVES].items() if k in ("n", "hits", "wrong")},
            "false_wakes": {k: {"count": len(scorer.wakes(sc, thr)), "hours": round(hours, 3)}
                            for k, (sc, hours) in val_streams.items()},
        }
        if negs_sc:
            r = _clip_negatives(scorer, *negs_sc, thr)
            for label, keep in (("containing the name", True), ("other phrases", False)):
                sub = [x for x in r if x["contains_name"] == keep]
                if sub:
                    row["your_negatives"][label] = {"n": len(sub), "woke": sum(x["woke"] for x in sub),
                                                    "clips": sorted({x["clip"] for x in sub if x["woke"]})}
        table.append(row)
    return {"model_set": model_set, "models": [str(p) for p in model_paths], "table": table,
            "separation": separation, "selftest": selftest,
            "operating_point": choose_threshold([validation_view(r) for r in table], model_set),
            "svarah_utterances": n_utts}


def _group(rows, key):
    out = {}
    for x in rows:
        g = out.setdefault(x.get(key) or "?", [0, 0])
        g[0] += 1
        g[1] += x["hit"]
    return {k: {"n": n, "hits": h} for k, (n, h) in out.items()}


#: The positive set the operating threshold is chosen on. Neither training nor any held-out report
#: uses it; the held-out sets are scored at the chosen threshold, never to choose it.
VALIDATION_POSITIVES = "TTS dev 28"


def choose_threshold(table, model_set):
    """Highest detection on the validation positives with false wakes on the validation audio under FW_TARGET.

    It reads row["validation"] and nothing else. It used to pick the threshold with the most
    detections on "your takes", the owner's 16 held-out takes (or, without them, "TTS held-out
    80"), with false wakes counted on the speech stream and Svarah's held-out speakers: every set
    it then reported was a set the threshold had been tuned on, so the reported detection and
    false wake rates were optimistic by an unknown amount. Without validation audio it chooses
    nothing and says so, instead of falling back to a held-out set.
    """
    if not table or not table[0]["validation"]["false_wakes"]:
        return {"threshold": None, "note": "no validation audio (inputs/validation/val_*.npy), so no threshold is "
                                           "chosen; held-out sets are never used to choose one"}
    best = None
    for row in table:
        val = row["validation"]
        fw = sum(v["count"] for v in val["false_wakes"].values())
        hours = sum(v["hours"] for v in val["false_wakes"].values())
        s = val["positives"]
        rate = s["hits"] / max(s["n"], 1)
        # rate > 0: the first dry run "chose" 0.1 with 0% detection, an operating point that is no point.
        if hours and fw / hours <= FW_TARGET and rate > 0 and (best is None or rate > best[1]):
            best = (row["threshold"], rate, fw / hours)
    if best is None:
        return {"threshold": None, "note": f"no threshold both detects anything on {VALIDATION_POSITIVES} and keeps "
                                           f"validation false wakes under {FW_TARGET}/hour; see the score separation table"}
    return {"threshold": best[0], "detection": round(best[1], 3), "false_wakes_per_hour": round(best[2], 2),
            "basis": f"{VALIDATION_POSITIVES} and the validation audio"}


def validation_view(row):
    """The part of one table row that choose_threshold may read: validation sets only."""
    return {"threshold": row["threshold"], "validation": row["validation"]}
