"""Write <work>/out/REPORT.md (for a person) and report.json (for a program), and package the models.

One file, readable without anyone to explain it: what was trained and on what, how it
scored on the held-back benchmark, the operating threshold, and every count and rate the
run produced (generation, rejections, caps, pauses per text, timings, machine).
"""
from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

import numpy as np


def _pct(h, n):
    return f"{h}/{n} ({100 * h / n:.0f}%)" if n else "n/a"


def _auc(pos, neg):
    return float((pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean())


def feature_probe(work, models, validation_path, cap=2000):
    """Held-out AUC of a ridge probe on each model's own feature files.

    The dry run's models scored a constant 0.0655 on everything and train.py reported recall
    0.0; from that alone, broken features and an undertrained model look the same. This probe
    tells them apart: features that carry the wake word separate from ordinary speech (the
    false-positive validation windows) almost perfectly with a straight line (0.99 and 0.98
    on the dry run), whatever the network learned. Separating from the adversarial phrases is
    what the network is for, so a low number there is expected at small scale.
    """
    rng = np.random.default_rng(0)

    def pooled(x):
        x = np.asarray(x, dtype=np.float32).reshape(len(x), 16, 96)
        return np.hstack([x.mean(1), x[:, -4:].mean(1)])

    def load(path):
        a = np.load(path, mmap_mode="r")
        return pooled(a[np.sort(rng.choice(len(a), min(cap, len(a)), replace=False))])

    v = np.load(validation_path, mmap_mode="r")
    start = int(rng.integers(0, max(1, len(v) - 16 * 2 * cap)))
    frames = np.asarray(v[start:start + 16 * 2 * cap], dtype=np.float32)
    speech = pooled(np.stack([frames[i:i + 16] for i in range(0, len(frames) - 16, 16)]))
    half = len(speech) // 2
    out = {}
    for name in models:
        d = Path(work) / "models" / name
        p, pt = load(d / "positive_features_train.npy"), load(d / "positive_features_test.npy")
        a, at = load(d / "negative_features_train.npy"), load(d / "negative_features_test.npy")
        res = {}
        for label, neg, negt in (("vs ordinary speech", speech[:half], speech[half:]), ("vs adversarial phrases", a, at)):
            x = np.vstack([p, neg])
            y = np.r_[np.ones(len(p)), np.zeros(len(neg))]
            mu, sd = x.mean(0), x.std(0) + 1e-6
            z = (x - mu) / sd
            w = np.linalg.solve(z.T @ z + 10 * np.eye(z.shape[1]), z.T @ (y - y.mean()))
            res[label] = round(_auc(((pt - mu) / sd) @ w, ((negt - mu) / sd) @ w), 3)
        res["test clips"] = len(pt)
        out[name] = res
    return out


def write(work, st, models, args, mix, rec, validation_path=None):
    out = work / "out"
    out.mkdir(exist_ok=True)
    b = st.info("benchmark")
    env = st.load("environment", {})
    ledger = st.load("parler_ledger", {"by": {}, "kept": {}, "gaps": {}, "gave_up": []})
    timings = st.load("timings", {})
    ps = st.load("parler_settings", {})
    L = []
    w = L.append
    w(f"# Wake-word training report: {args.models} models\n")
    w(f"Run of {Path(work).name}, scale {args.scale}" + (" (DRY RUN at reduced size: the numbers check the pipeline, "
                                                           "not the models)" if args.scale < 1 else "") + ".\n")
    w("**First-run models are not expected to be final.** Read the benchmark below, then tune: the operating "
      "threshold, negative weighting and steps, the custom negative phrases (add whatever the false wakes were), "
      "and the voice-mix shares. A retrain that reuses these clips and features costs only the training step.\n")
    op = b["operating_point"]
    w("## Result\n")
    if args.models == "bare" and not any(k.split("/")[-1] in models for k in rec["train"]):
        # The runner falls back to the "hey" takes when no bare takes are recorded; without this
        # line the report gave no sign that the bare models never heard a bare recording.
        w("- **No bare-name recordings were used.** These models were trained on your \"hey\" takes "
          "(the name is in them), and the threshold is chosen on the TTS held-out set. Record with "
          "`record_wake.py --bare`, re-pack, re-run prepare, and retrain.\n")
    if op.get("threshold") is None:
        w(f"- No operating threshold: {op.get('note', '')}\n")
    else:
        w(f"- Operating threshold **{op['threshold']}**: detection {op['detection'] * 100:.0f}% on {op['basis']}, "
          f"{op['false_wakes_per_hour']} false wakes per hour (speech stream and Svarah together).\n")
    row = next(r for r in b["table"] if r["threshold"] == op.get("threshold")) if op.get("threshold") else \
        min(b["table"], key=lambda r: sum(v["count"] for v in r["false_wakes"].values()))
    w(f"\n### At threshold {row['threshold']}\n")
    w("| Positive set | Detected | Wrong name | Whisper-confirmed subset |\n|---|---|---|---|")
    for k, v in row["sets"].items():
        conf = v.get("whisper_confirmed")
        w(f"| {k} | {_pct(v['hits'], v['n'])} | {v['wrong']} | {_pct(conf['hits'], conf['n']) if conf else '-'} |")
    w("\n| Negative stream | False wakes | Hours | Per hour |\n|---|---|---|---|")
    for k, v in row["false_wakes"].items():
        w(f"| {k} | {v['count']} | {v['hours']} | {v['per_hour']} |")
    if row["your_negatives"]:
        w("\n| Your recorded negatives | Clips that woke it | Which |\n|---|---|---|")
        for k, v in row["your_negatives"].items():
            w(f"| {k} | {v['woke']}/{v['n']} | {', '.join(v['clips']) or '-'} |")
    w("\nPer language (all positive sets at this threshold):")
    by_lang = {}
    for v in row["sets"].values():
        for lang, g in v["by_lang"].items():
            t = by_lang.setdefault(lang, [0, 0])
            t[0] += g["n"]
            t[1] += g["hits"]
    for lang, (n, h) in by_lang.items():
        w(f"- {'Hindi' if lang == 'hi' else 'English'}: {_pct(h, n)}")
    w("\nPer speaker (your takes):")
    for k, v in row["sets"].items():
        if k.startswith("your takes"):
            w(f"- {k}: " + ", ".join(f"{s} {_pct(g['hits'], g['n'])}" for s, g in v["by_speaker"].items()))
    w("\n### Every threshold\n")
    sets = list(b["table"][0]["sets"])
    w("| thr | " + " | ".join(sets) + " | false wakes/h (speech) | false wakes/h (Svarah) |")
    w("|---|" + "---|" * (len(sets) + 2))
    for r in b["table"]:
        fw = list(r["false_wakes"].values())
        w(f"| {r['threshold']} | " + " | ".join(f"{100 * r['sets'][s]['hits'] / max(r['sets'][s]['n'], 1):.0f}%" for s in sets)
          + f" | {fw[0]['per_hour']} | {fw[1]['per_hour']} |")
    if b.get("selftest"):
        w("\nScorer self-test (a speech detector named hey_guru, run before the real models): "
          f"{json.dumps(b['selftest'])}. It must wake on the Guru clips, wake on the Maya clips as the wrong "
          "name, and wake in speech; the run stops if it does not, so these numbers are the scorer's, not the "
          "models'.")
    sep = b.get("separation")
    if sep:
        # Read this before the detection tables. At the dry run's size every model scored near
        # zero everywhere and detection was 0% at every threshold; this table is what shows
        # whether positives still score above negatives, i.e. whether more training will help.
        w("\n### Score separation (no threshold involved)\n")
        w("Positives: the highest score inside each clip (or 1 s after) for the model that should wake. "
          "Negatives: every 80 ms frame's highest score across the models. A useful model has positive "
          "medians well above the negatives' p99.9.\n")
        w("| Set | n | p10 | median | p90 | max | p99.9 |\n|---|---|---|---|---|---|---|")
        for group, sets in sep.items():
            for k, v in sets.items():
                w(f"| {k} ({group.split(' ')[0]}) | {v['n']} | {v['p10']} | {v['median']} | {v['p90']} | "
                  f"{v['max']} | {v.get('p99_9', '-')} |")
    probe = None
    if validation_path is not None:
        probe = feature_probe(work, models, validation_path)
        w("\n### Feature check (independent of the trained network)\n")
        w("Held-out AUC of a straight-line probe on each model's own training features. Near 1.0 against "
          "ordinary speech means the features carry the wake word; if that is low, the clips or the feature "
          "step are broken and no amount of training will help. Against the adversarial phrases it is "
          "expected to be lower: telling those apart is the network's job.\n")
        w("| Model | vs ordinary speech | vs adversarial phrases | Test clips |\n|---|---|---|---|")
        for name, r in probe.items():
            w(f"| {name} | {r['vs ordinary speech']} | {r['vs adversarial phrases']} | {r['test clips']} |")
    w("\n## What the models were trained on\n")
    tr = env.get("training", {})
    # This line used to print the scale under the label "Steps" ("Steps: 0.01 scale"), which
    # read as a step count; the real counts were not in the report at all.
    w(f"- Training steps {tr.get('steps', '?')}, {tr.get('n_samples', '?')} generated positives and as many "
      f"adversarial negatives per model, {tr.get('n_samples_val', '?')} of each for validation "
      f"(scale {args.scale}). Positives per model, by source:")
    for name, splits in mix.items():
        for split, c in splits.items():
            w(f"  - {name} {split}: " + ", ".join(f"{k} {v}" for k, v in c.items()) + f" (total {sum(c.values())})")
    w(f"- Your recordings used for training: {json.dumps(rec['train'])}; held back for this benchmark: {json.dumps(rec['bench'])}")
    w("\n## Parler-TTS generation\n")
    w(f"- Precision {ps.get('dtype')}, batch {ps.get('parler_batch')} (one prompt text per batch; mixed-text batches "
      f"change the audio). Batch probe: {ps.get('probe')}")
    w("- Caps: English 5.0 s, Hindi 6.0 s (above the longest of 480 measured clips). bf16 is the default on Ampere "
      "and newer because fp16 produced broken clips: English empties fell from 3.1% to 0.3% and Hindi from 12.0% "
      "to 5.2% at equal quality, a correctness finding about fp16, not a speed choice.")
    w("\n| Language | Text | Kept | Rejected empty | Rejected at cap | Pause >= 150 ms | Pause median / p90 |\n|---|---|---|---|---|---|---|")
    for k, kept in sorted(ledger["kept"].items()):
        lang, text = k.split("|")
        empty = ledger["by"].get(f"{lang}|{text}|empty", 0)
        capped = ledger["by"].get(f"{lang}|{text}|capped", 0)
        gaps = np.array(ledger["gaps"].get(k, [0]))
        tried = kept + empty + capped
        w(f"| {lang} | {text} | {kept} | {_pct(empty, tried)} | {_pct(capped, tried)} | "
          f"{_pct(int((gaps >= 150).sum()), len(gaps))} | {np.median(gaps):.0f} / {np.percentile(gaps, 90):.0f} ms |")
    w(f"- Clips given up after 3 tries: {len(ledger['gave_up'])}. The empty rate per text records the bias "
      "regeneration introduces: for a text that fails often, the kept clips lean toward what Parler finds easy.")
    w(f"- 50-clip check: {json.dumps(st.info('parler_check'))}")
    w("\n## Svarah split\n")
    w(f"- {json.dumps(st.info('svarah'))}")
    w("\n## Time and machine\n")
    for k, v in timings.items():
        w(f"- {k}: {v / 60:.1f} min")
    w(f"- Machine: {json.dumps(env.get('machine'))}")
    w(f"- Chosen settings: {json.dumps(env.get('chosen'))}")
    (out / "REPORT.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    (out / "report.json").write_text(json.dumps({"benchmark": b, "voice_mix": mix, "ledger_by": ledger["by"],
                                                 "kept": ledger["kept"], "timings": timings, "environment": env,
                                                 "feature_probe": probe},
                                                ensure_ascii=False, indent=1), encoding="utf-8")
    zpath = out / f"agent_guru_wakewords_{args.models}.zip"
    tmp = Path(str(zpath) + ".tmp")
    with zipfile.ZipFile(tmp, "w") as z:
        for name in models:
            z.write(work / "models" / f"{name}.onnx", f"{name}.onnx")
        for f in ("REPORT.md", "report.json"):
            z.write(out / f, f)
        z.write(work / "svarah_split.json", "svarah_split.json")
    os.replace(tmp, zpath)
