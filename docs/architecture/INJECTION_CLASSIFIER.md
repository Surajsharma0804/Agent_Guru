# Local prompt-injection classifier

A second opinion on outside text, beside the rules in
`Agent_Guru/llm/security.py`. Code: `Agent_Guru/security/injection_classifier.py`.
Off by default; switched on with `AGENT_GURU_INJECTION_CLASSIFIER=1` after
`python -m Agent_Guru injection-model install`.

## What it is allowed to do

The classifier is a detector, not a boundary. It can only add a mark to text
the rules already let through. It cannot make text more trusted, allow a
tool, answer a confirmation, or change policy. Every outside text still goes
through the single chokepoint, `guard_external_text` (sync) or
`guard_external_text_async`:

1. The rules run first. A high-severity finding drops the text; nothing the
   classifier says can undo that.
2. If the classifier is switched on and returns `injection`, the text is kept
   and wrapped in `CLASSIFIER_NOTICE ... CLASSIFIER_NOTICE_END`, which tell the
   model the text came from a third party and is information only. The flag
   is logged with the source, score and window count, never with the text.
3. `benign`, `suspicious` and `unknown` leave the text exactly as the rules
   left it. A missing, broken, slow or failing model is `unknown`.

Tools that change things still need the owner's spoken or typed yes through
the existing tool loop and policy, whatever is in the context.

### Where it runs

| Untrusted text | Call site | Path |
|---|---|---|
| Output of every MCP and in-process tool (research, documents, mail, calendar, connectors, tasks) | `integration/mcp_tools.py` `_run` | async |
| Research sources (snippets, pages, documents) | `integration/research.py` `_guarded` | async |
| Legacy web-search snippet, document passages | `integration/orchestrator.py` | async |
| Agent-to-agent messages | `integration/local_api.py` | async |
| Tool descriptions and schema text shown to the model | `integration/tool_loop.py` | sync; warmed at MCP discovery |
| Clipboard text | `integration/orchestrator.py` `_enrich_prompt` | sync |

The sync form never runs the model on the caller's thread: it uses a verdict
already in the cache and otherwise queues one for next time. A first-time
clipboard text therefore gets the rules only. All model runs go through one
worker thread with a bounded queue (64); the async form waits at most
`AGENT_GURU_INJECTION_TIMEOUT_S` (default 2 s) and then goes on with the
rules' decision.

The cache is keyed by a hash of the text plus the model revision, the
preprocessing version and both thresholds. It holds verdicts, never
authorisation.

## Model

| | |
|---|---|
| Model | `protectai/deberta-v3-base-prompt-injection-v2` |
| Revision | `90c9989b1a342275dd0d1a95aad283c04e075671` |
| License | Apache-2.0 (model card and `LICENSE` at that revision) |
| Format | ONNX, run with onnxruntime on the CPU provider only |
| Files | `onnx/model.onnx` (738,563,188 bytes, sha256 `f0ea7f23...`), `onnx/tokenizer.json`, `onnx/config.json` |
| Upstream status | archived by Protect AI; no further updates expected |
| Card limitations | English only, not meant for jailbreaks, false positives on system prompts |

Never downloaded: `training_args.bin` (a pickle) and the safetensors copy.
onnxruntime and tokenizers were already dependencies; nothing new is installed.

### Candidates considered (Hugging Face API, 2026-10-17)

| Model | License | Access | Size | Outcome |
|---|---|---|---|---|
| protectai/deberta-v3-base-prompt-injection-v2 | Apache-2.0 | open | 739 MB | chosen |
| protectai/deberta-v3-small-prompt-injection-v2 | Apache-2.0 | gated (login) | 568 MB | not evaluated: needs a Hugging Face account |
| meta-llama/Llama-Prompt-Guard-2-22M | Llama 4 license | gated, manual approval | 283 MB | not evaluated: owner must accept the license |
| meta-llama/Llama-Prompt-Guard-2-86M | Llama 4 license | gated, manual | 1.1 GB | too large |
| qualifire / rogue-security sentinels | other | gated | 1.2-1.6 GB | too large |
| testsavantai/...-base-v0-onnx | none stated | open | 268 MB | rejected: no license |

An INT8 dynamic quantisation of the chosen model (244 MB) was tried and
rejected: it flagged 0 of 75 development attacks.

## Installation and integrity

`install()` fetches each file from
`https://huggingface.co/<model>/resolve/<revision>/<path>` into `<name>.part`,
refuses more bytes than pinned, checks the size and hash (sha256 for the LFS
model file, the git blob id for the two small files), and only then renames
it. An interrupted or altered file is deleted and never has its real name.
`install --from <folder>` does the same from a local copy, for machines
without internet. After install, `verified.json` records each file's size and
modification time; at load, any difference makes the hashes be checked again
before the model is used, and a mismatch makes the classifier unavailable.

Folder: `~/.cache/agent_guru/prompt-injection/90c9989b1a34/`, or
`AGENT_GURU_INJECTION_MODEL_DIR`. Nothing is downloaded during a conversation.

## How text is classified

- Empty text: benign, the model is not run.
- Text that is plainly not English (mostly non-Latin letters, or Latin text
  with under 12% English function words): `unknown`. The model scored ordinary
  Spanish, German and Italian sentences 1.0; the rules' multilingual patterns
  decide for such text.
- One sentence: classified whole.
- Several sentences: only sentences that could steer an assistant are kept
  (addressed to "you" or an AI, or about instructions, rules, secrets, sending,
  revealing, running), joined, and cut into 254-token windows overlapping by 32;
  at most 8 windows, beyond which the result says `truncated`.
- Decoded forms: the text is also classified as the rules' bounded
  decoder rewrites it (zero-width characters removed, spaced or separated
  letters joined, leetspeak undone, printable base64 decoded), at most 4
  forms. The highest score over the text and its forms decides, and the
  result says whether a decoded form decided it. Nothing is executed or
  fetched, and the model is always given the text as written.
- Score: the highest softmax "INJECTION" output over the windows. It is not
  a calibrated probability. `injection` at >= 0.98, `suspicious` at >= 0.50
  (logged, no effect).

## Evaluation

All runs used identical inputs for rules only, classifier only, and both.
Datasets (kept outside the repository, in the work folder of 2026-10-17):

| Set | Attacks | Benign | Use |
|---|---|---|---|
| 1 development | 30 | 20 | rules were tuned on it; thresholds chosen on 1-3 |
| 2 held-out 1 | 25 | 25 | rules were tuned on it afterwards |
| 3 fresh | 20 | 30 | written after the rules; its benign texts informed three rule fixes |
| 4 final | 64 | 69 | written before any model ran; never used for any choice; scored once |

Set 4 covers override, persona, extraction, exfiltration, tool abuse, indirect
instructions in ordinary content, obfuscation, eight languages and attacks
buried in long pages; its benign side has general text, instructions meant for
people, security writing that quotes attacks, normal role prompts, technical
text, other languages, long pages and malformed input.

Thresholds, the language gate and the sentence filter were chosen on sets 1-3
and on long development pages built from a different page and set 1-3
attacks. On those pages the sentence filter caught 16 of 24 buried attacks in
40 ms, against 11 of 24 in 2.0 s for full 512-token windows.

### Set 4, final held-out (64 attacks, 69 benign)

| Configuration | TP | FP | TN | FN | Recall | Precision | F1 | False-positive rate |
|---|---|---|---|---|---|---|---|---|
| Rules only | 4 | 0 | 69 | 60 | 4/64 (6%) | 1.00 | 0.12 | 0/69 (0%) |
| Classifier only | 33 | 12 | 57 | 31 | 33/64 (52%) | 0.73 | 0.61 | 12/69 (17%) |
| Rules + classifier | 36 | 12 | 57 | 28 | 36/64 (56%) | 0.75 | 0.64 | 12/69 (17%) |

"Classifier" positives are marked, not dropped; rule positives are dropped.
By category (rules / classifier / both caught): override 0/7/7 of 8, persona
0/5/5 of 7, extraction 0/5/5 of 6, exfiltration 0/3/3 of 5, tool abuse 0/0/0
of 7, indirect 1/5/6 of 10, obfuscated 2/3/5 of 7, multilingual 0/1/1 of 8,
buried in long pages 1/4/4 of 6.

False positives (all marked, none dropped): instructions for people 3/12
("Do not share your OTP with anyone"), security writing 4/12, AI role text
1/8, technical text 2/8, malformed input 2/6 (5,000 "a", a row of brackets).

### Development sets, for comparison (same configuration)

| Set | Rules only | Rules + classifier | Benign marked |
|---|---|---|---|
| 1 | 27/30 | 30/30 | 3/20 |
| 2 | 23/25 | 24/25 | 2/25 |
| 3 | 7/20 | 18/20 | 5/30 |

Percentages across sets are not comparable: the sets differ in difficulty.

### Effect of the mark on the local model

gemma4 (Agent Guru's default model) summarised an ordinary page with one
injected instruction asking for a checkable marker; 12 instructions, 3 runs
each, temperature 0.7, a short system prompt resembling the assistant's (not
the full production prompt):

| Text given to the model | Instruction followed |
|---|---|
| Unmarked | 29/36 and 28/36 (two runs of the experiment) |
| One-line note in front | 20/36 |
| Start and end markers (shipped) | 14/36 |

On six ordinary pages the summary kept the key fact 10/12 unmarked and 9/12
with the markers. The mark halves compliance but does not stop it; gemma4
followed injected instructions in about four of five unmarked pages.

## Performance (measured)

Windows 11, Intel 12th-generation (family 6 model 154), 12 logical CPUs, 16.9
GB RAM, Python 3.13, onnxruntime 1.30, 4 inference threads, memory arena off:

| | |
|---|---|
| Model load | 3.4 s (4.8 s in the `status` command, first run) |
| One sentence | 40 ms median, 42 ms p95 |
| 1,000-character page | 107 ms median |
| 4,000-character page, half of it candidate sentences | 665 ms median, 680 ms p95 |
| 8,000 characters, all candidate sentences (8 windows) | 2.86 s median: over the 2 s timeout, so `unknown` |
| 40 snippets at once | 1.37 s, 29 per second, none unknown |
| Guard on a 4,000-character page | 4.7 ms off, 681 ms on |
| Memory | about +800 MB once loaded, peak about 1.2 GB while loading |
| Disk | 747 MB |

Linux (WSL2 Ubuntu 26.04 on the same machine, Python 3.12, onnxruntime 1.31):
load 3.5-4.3 s, classification median 42 ms over 238 short texts.

The 50-100 ms per page goal is met for snippets and short pages only.

## Platforms

| Platform | Verified |
|---|---|
| Windows 11 | install, hash check, load, CPU inference, all 33 classifier tests including the real-model ones |
| Linux (WSL2 Ubuntu) | install, hash check, load, CPU inference, evaluation, full test suite |
| macOS | CI runner `macos-latest`, run 39015632954 on e50a9beb: the pinned model installed and verified, and all 33 classifier tests passed, the three real-model ones included (first load and inference 7.3 s). Not run on a physical Mac. |
| Windows (CI) | the same run installed and verified the model on Windows 3.11, 3.12 and 3.13, but each test suite was stopped at about 4% by an unrelated hang (pyttsx3 voice set-up in a spoken research test on a runner with no audio), so the classifier tests did not run there |

## Known limitations

- Detection: 26 of 64 set-4 attacks and 9 of 24 set-5b attacks were missed. Tool-abuse requests
  ("Open the banking app and transfer 500 ...") and many indirect instructions
  score near 0 (set 5b: 1 of 4 caught). Decoded forms only cover what the
  rules decode: hex, ROT13 and URL encoding are not decoded (the model still
  read some of them as written).
- False positives: 17% of held-out benign texts were marked, including
  security writing and ordinary instructions. The scores of these are 0.99-1.0,
  so no threshold separates them.
- Not multilingual. Non-English attacks rely on the rules.
- Long pages take 0.7-2.9 s on a laptop CPU; past the timeout the verdict is
  unknown for that call (the result still fills the cache).
- About 0.8-1.2 GB of memory beside the local LLM.
- A first-time clipboard text and the first tool descriptions after startup
  may get the rules only, until the queued verdicts are ready.
- The model is archived upstream.

## Set 5 and decoded forms (2026-10-17)

Set 5 (48 attacks, 43 benign) was written before anything ran on it: leetspeak,
base64, other encodings, attacks embedded in ordinary pages, tool abuse, eight
languages; and on the benign side encoded data, security writing, ordinary
text, other languages and malformed or oversized input. It is split
deterministically per category into 5a (the 1st, 3rd, ... text of each
category) and 5b (the rest). 5a decided one question, whether to classify the
decoded forms; 5b was scored once afterwards, through `classify_all()` as
shipped.

5a (24 attacks, 22 benign), used for the decision:

| Configuration | Recall | Benign marked | F1 |
|---|---|---|---|
| Rules + classifier on the text as written | 11/24 | 3/22 | 0.58 |
| Rules + classifier on the text or its decoded forms | 16/24 | 5/22 | 0.71 |

5b (24 attacks, 21 benign), held out:

| Configuration | TP | FN | FP | TN | Recall | Precision | F1 | FP rate |
|---|---|---|---|---|---|---|---|---|
| Rules only | 5 | 19 | 0 | 21 | 5/24 (21%) | 1.00 | 0.34 | 0/21 (0%) |
| Classifier only, text as written | 8 | 16 | 2 | 19 | 8/24 (33%) | 0.80 | 0.47 | 2/21 (10%) |
| Rules + classifier, text as written | 10 | 14 | 2 | 19 | 10/24 (42%) | 0.83 | 0.56 | 2/21 (10%) |
| Rules + `classify_all()` (shipped) | 15 | 9 | 3 | 18 | 15/24 (62%) | 0.83 | 0.71 | 3/21 (14%) |

5b by category, rules only / shipped: leetspeak 1/4 / 4/4, base64 2/4 / 4/4,
other encodings 1/4 / 3/4, embedded 1/4 / 3/4, tool abuse 0/4 / 1/4,
non-English 0/4 / 0/4. Benign marked: encoded data 2/4, malformed 1/3, security
writing 0/4, ordinary 0/7, other languages 0/3.

Set 4 rescored with `classify_all()` (set 4 played no part in the decision):
36/64 caught before, 38/64 now, the same 12/69 benign marked; obfuscated 5/7 to
7/7.

Latency of `classify_all()` on the Linux sandbox: median 50 ms over 45 texts;
the slowest, 5.3 s, was a 40,000-character single "sentence" with no full stop,
classified as 8 whole windows: past the 2 s timeout that text gets no verdict
and the rules decide.

A smaller candidate, protectai/deberta-v3-small-prompt-injection-v2 (revision
d7c8842d, Apache-2.0 in its card metadata, no LICENSE file in the repository,
568 MB ONNX), returns HTTP 401 without a Hugging Face login that has accepted
its terms; it is evaluated only once the owner provides a token.

