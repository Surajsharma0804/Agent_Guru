# Dependency vulnerability triage, 2026-09-24

GitHub reports 145 Dependabot alerts on `main`: 7 critical, 57 high, 63
moderate, 18 low. None had been looked at. This document triages every
critical and high alert and summarises the rest, so that the fixes in the
follow-up change can be judged against a written reason rather than a count.

## Summary

Of the 64 critical and high alerts:

| Verdict | Critical | High | What happens |
|---|---|---|---|
| Reachable, fixed by an upgrade | 2 | 3 | torch (`requirements-torch.txt`), GitPython (critical), aiohttp, cryptography OpenSSL, transformers |
| Barely reachable (developer scripts), cheap patch upgrade | 2 | 9 | nltk |
| Not reachable, but in a package upgraded anyway for a reachable one | 0 | 18 | 17 GitPython highs, and PyJWT's high (upgraded for a reachable moderate) |
| Not reachable, no fix, accepted | 2 | 3 | ChromaDB server (2 critical, 2 high), nltk GHSA-8mgp |
| Not reachable, transitive, left | 0 | 9 | httplib2, langsmith, msgpack, pyasn1 (3), starlette, cryptography X.509 and PKCS#7 |
| Orphan in the lock, removed | 1 | 15 | Jupyter, vLLM, mcp, mistune, soupsieve, tornado, js2py |
| **Total** | **7** | **57** | |

The one that matters most is torch 2.2.2 in `requirements-torch.txt`: a
code-execution bug in `torch.load(weights_only=True)`, which the vision
training code calls on user-supplied checkpoints and treats as safe. The
alert count also hides two findings Dependabot does not show. The CI audit
has never checked torch at all, and a pytorch-lightning checkpoint RCE is
filed under a different package name, so it raises no alert.

After the follow-up change, the lock and torch manifests carry 14 critical
and high alerts. Each has a written reason above, and the new CI audit
accepts them explicitly.

## How the alert list was obtained

The Dependabot alerts API was not reachable from the environment this was
done in (HTTP 403), so the alert set was rebuilt from the same source
Dependabot uses: the GitHub Advisory Database, read through the OSV export
of the PyPI ecosystem taken on 2026-09-24. Each manifest was matched against
it the way Dependabot does it, by exact pin only.

The rebuild gives 7 critical, 57 high, 62 moderate and 17 low: the critical
and high counts match GitHub's exactly, and moderate and low are one short
each. If someone opens the Dependabot tab, those two missing alerts will be
moderate or low. They are not in this document.

**Where the alerts come from.** Only two files contain exact pins:

| File | Alerts | What installs it |
|---|---|---|
| `requirements-lock.txt` | 134 | Nothing automated. Only the CI `pip-audit` step reads it. |
| `requirements-torch.txt` | 9 | Nobody automatically. The Dockerfile comment points GPU builds at it. |

Every other manifest (`requirements.txt`, `requirements-cpu.txt`,
`requirements-docker.txt`, `requirements-reasoning.txt`, `pyproject.toml`)
uses `>=` floors. Dependabot raises no alerts for those, and a fresh install
from them resolves to current releases, most of which are already fixed. That
changes the risk picture:

- The lock file is a `pip freeze` of one developer machine. It pins 446
  packages, and **136 of them are not required by anything this project
  declares or imports** (Jupyter, vLLM, trl/peft/datasets, streamlit, js2py
  and their trees). 16 of the 64 critical and high alerts are in those
  orphans. They are not a risk to anyone who installs Agent Guru. They are
  noise that hides the alerts that matter, and the right fix is to remove
  them from the lock, not to upgrade them.
- `>=` floors do not protect an existing environment. If `pip install -r
  requirements.txt` runs in a venv that already has GitPython 3.1.40 or
  torch 2.2, pip keeps them. Where the vulnerable path is reachable and
  critical, the floor matters as much as the lock pin.

**Two gaps no alert shows.**

1. The CI audit has never checked torch. The lock pins
   `torch==2.11.0+cu128`, and pip-audit cannot find a `+cu128` local version
   on PyPI, so it writes `skip_reason: Dependency not found on PyPI` for
   torch, torchvision and torchaudio. Then `|| true` throws the result away.
2. `pytorch-lightning==2.6.5` in the lock is affected by
   [GHSA-qqmf-gpg7-g8gw](https://github.com/advisories/GHSA-qqmf-gpg7-g8gw)
   (code execution from a crafted checkpoint through `load_from_checkpoint`,
   high). GitHub files that advisory under the `lightning` package name, so
   Dependabot raises nothing for `pytorch-lightning`. PyPI's advisory feed,
   which pip-audit reads, maps it correctly. It is not counted in the 145.

## Exploitability model

Agent Guru is an offline-first desktop assistant. The questions that decide
real risk are:

- Does the project import the package and call the vulnerable function, or
  is the package only present because something else pulled it in?
- Who supplies the input that reaches that function? The user's own files
  and repositories, a web page the agent fetched, a model or checkpoint
  downloaded from a hub, or a network client connecting to a server port?
- Does that code run on every start, or only in a developer's training
  script?

A server-side bug is only a risk if this project runs that server. The
desktop app runs no FastAPI, Jupyter, Chroma or vLLM server. The FastAPI
reasoning API exists, but it runs only in the Docker image.

## Verdict by package, critical and high

Ordered by real risk to this project, highest first.

### 1. torch 2.2.2 in `requirements-torch.txt`: reachable, the real critical

- **Alert:** GHSA-53q9-r3pm-6pq6 (critical). `torch.load(..., weights_only=True)`
  can still execute code from a crafted file. Fixed in 2.6.0.
- **Reachable: yes.** `vision/training/evaluation.py:434` and
  `vision/training/export.py:61,136` load user-supplied checkpoint paths with
  `weights_only=True`, which is the exact protection this advisory breaks.
  The code was written on the assumption that it is safe. Third-party loaders
  on the runtime path (`openai-whisper`'s `load_model`, `.bin` weights through
  transformers) also go through `torch.load`.
- **Exploitability: high.** This is a deserialisation flaw in a model
  loader. A checkpoint someone shares, or a model file swapped in a cache,
  looks like data and runs as code. It is the one alert here that matches
  how the project is actually used.
- **Exposure:** the lock already has torch 2.11.0, so a lock install is not
  affected. The exposure comes from `requirements-torch.txt`, which pins
  2.2.2 exactly, and from the `torch>=2.1.0` floors in `requirements.txt`,
  `requirements-reasoning.txt` and `pyproject.toml`. Those floors accept 2.2.
- **Fix:** move `requirements-torch.txt` to torch 2.11.0, torchvision 0.26.0
  and torchaudio 2.11.0, the versions already in the lock, and raise the torch
  floors to `>=2.6.0`, with torchvision and torchaudio floors to match.
  torchaudio 2.9 removed its I/O functions, but the project only uses
  `torchaudio.transforms`, which is still there. The 8 moderate and low torch
  alerts in the same file are fixed by the same move.

### 2. GitPython 3.1.50: reachable, low-to-moderate in practice

- **Alerts:** 1 critical (GHSA-284h-m62q-gf8w) and 17 high, plus 5 moderate.
  All are fixed in 3.1.60.
- **Reachable: partly.** `self_improvement/git_integration.py` calls
  `Repo()`, `index.add`, `index.commit`, `remote().push` and `config_writer()`
  (lines 343 and 370). `config_writer()` reads `.git/config`, modifies it and
  writes it back, which is exactly the path in the critical: dormant
  multi-line values get rewritten as live directives such as `core.hooksPath`.
  `goal_manager/goal_executor.py` calls `Repo()` and `git.add(A=True)`. Most
  of the highs are argument injection in APIs the project never calls
  (`clone_from`, `archive`, `ls_remote`, `IndexFile.checkout`,
  `create_remote`, `Repo.init --template`, `diff --output`). Two of them,
  GHSA-3rp5 and GHSA-jm78, are injection through config section and option
  names. The project does call `set_value`, but always with the constant
  names `"credential"` and `"helper"`, so no attacker-controlled name reaches
  the vulnerable check.
- **Exploitability:** the critical needs attacker-controlled content already
  in the `.git/config` of the repository the agent operates on. `.git/config`
  does not travel with a clone. On a desktop, that means the user's own
  repository, so the practical risk is low. It is still the project's own
  code on the vulnerable path, the fix is a patch release, and the result is
  command execution.
- **Fix:** 3.1.60, and raise the `gitpython>=3.1.40` floors to `>=3.1.60`.
  Checked: the token credential helper is written and then cleared, and
  `index.add` and `commit` work with 3.1.60.

### 3. aiohttp 3.13.5: reachable, moderate

- **Alert:** GHSA-cq5v-8q36-5273 (high). Out-of-bounds heap read in the C
  HTTP response parser on a malformed chunked response. Fixed in 3.14.3. Also
  fixes 9 moderate and 4 low.
- **Reachable: yes.** 22 modules use `aiohttp.ClientSession`, including
  web search and browsing. Those fetch pages from arbitrary hosts, so a
  hostile web server can send the malformed response.
- **Exploitability: moderate.** The attacker only needs to be a server the
  agent fetches from. The likely result is a crash or a leak of process
  memory, not code execution.
- **Fix:** 3.14.3.

### 4. cryptography 48.0.0: one of three reachable

- **GHSA-537c-gmf6-5ccf (high), reachable.** The wheels statically link a
  vulnerable OpenSSL. Fixed in 48.0.1. The project uses AESGCM, Fernet,
  PBKDF2HMAC and Ed25519 for memory encryption at rest, the key store and
  identity, and those run on the bundled OpenSSL on every start. I could not
  read the OpenSSL advisory from this environment, so I cannot say whether it
  affects those primitives specifically. It is treated as reachable. Taking a
  patch release to close that uncertainty costs nothing.
- **GHSA-jwv3-5hgf-82ww (high, X.509 path building, fixed in 49.0.0) and
  GHSA-g6cj-pr64-35w5 (high, PKCS#7 decryption oracle, fixed in 50.0.0): not
  reachable.** Nothing in the project imports `cryptography.x509` or
  `pkcs7`. The same applies to the moderate GHSA-m2h6 (X.509 name
  constraints).
- **Fix:** 48.0.1. Do not take 49 or 50 for these. They are major releases,
  and the only thing they would fix here is code the project never calls.
  Dismiss the two highs in Dependabot as "vulnerable code is not actually
  used", and revisit if the project ever verifies certificates itself.

### 5. transformers 5.8.0: reachable in developer scripts only

- **Alert:** GHSA-xrqw-3rrv-vx5w (high). `save_pretrained` path traversal:
  chat-template names from a model's config can write files outside the
  output directory.
- **Reachable:** `reasoning/scripts/train_intent_classifier.py:1172-1173` and
  `train_ner_model.py:329` call `save_pretrained` on tokenizers loaded from
  the model hub. The desktop runtime does not.
- **Exploitability: low.** A developer would have to pick a hostile base
  model to train from.
- **Fix:** 5.10.4. **5.10.0, the first fixed version, was yanked upstream**
  ("pushed from a week old main branch"). 5.10.4 is the last patch of that
  line. Checked: 5.10.4 rejects `../` template names that 5.8.0 accepted.

### 6. nltk 3.10.0: developer training script only, very low

- **Alerts:** 2 critical, 10 high, 7 moderate, 1 low.
- **Reachable: barely.** nltk is imported only by
  `reasoning/scripts/train_intent_classifier.py`, a developer training script
  the application never loads. It calls `nltk.download` and `nltk.data.find`
  for wordnet and the perceptron tagger. The two criticals are in the pickle
  allowlist loaders (`punkt_pickle_load`, `TransitionParser`) and the
  Stanford Java wrappers. Neither is called. The highs are corpus-reader
  sandbox bypasses, ReDoS in `tgrep` and `TweetTokenizer`, an SSRF behind a
  proxy, entity expansion and the Graphviz search path. None of those is
  called either.
- **Fix:** 3.10.3, a patch release of a declared direct dependency with no
  API change. It closes 19 of the 20 alerts.
- **Residual:** GHSA-8mgp-746c-j5xp (high, model-artifact APIs bypass
  `pathsec`) has no fix. It is not reachable, because the script never
  calls those APIs.

### 7. PyJWT 2.12.1: high not reachable, moderate DoS reachable in the Docker API

- **GHSA-xgmm-8j9v-c9wx (high).** A public JWK is accepted as an HMAC secret,
  but only when mixed key families are allowed. `reasoning/api/auth.py:578`
  decodes with `algorithms=["HS256"]` and a string secret, so this is **not
  reachable.**
- **Why upgrade anyway:** GHSA-w7vc-732c-9m39 (moderate) is an
  unauthenticated DoS during Base64URL decoding. `verify_token` decodes every
  bearer token the API receives, from any client, so it is reachable in the
  Docker deployment. 2.13.0 is a minor release, and
  create, verify, tamper, `alg=none` and wrong-key checks against `auth.py`
  give the same results on 2.12.1 and 2.13.0.
- **Found while reading auth.py, not a dependency issue:** `JWT_SECRET`
  falls back to the literal `"your-secret-key-change-in-production"` when
  the environment variable is unset. Any deployment that forgets the variable
  accepts tokens that anyone can forge. This should fail at startup instead.
  It is out of scope here, and needs its own change.
  Since fixed: `auth.py` now has no fallback, and the API refuses to
  start until `JWT_SECRET` is set.

### 8. pytorch-lightning 2.6.5: not in the 145, reachable in the training script

- **GHSA-qqmf-gpg7-g8gw (high)**, see "Two gaps" above. `load_from_checkpoint`
  is called at `train_intent_classifier.py:1163` on the checkpoint the script
  itself just wrote. To exploit it, an attacker would have to replace that
  file between the write and the read. The risk is low, and the fix is a
  patch release: **2.6.6.**

### 9. ChromaDB 1.5.9: not reachable, no fix exists

- **Alerts:** GHSA-f4j7-r4q5-qw2c and GHSA-36p7-vc44-83pf (critical, code
  injection through `trust_remote_code` on the `/api/v2/.../collections` HTTP
  endpoints), GHSA-xph7-9rjv-w5fr and GHSA-2wm9-hf6c-p5cr (high, cross-tenant
  authorisation in the server's RBAC provider).
- **Reachable: no.** All four are in Chroma's HTTP server, the one started by
  `chroma run`. `reasoning/memory/vector_db.py:126,132` uses
  `chromadb.Client` and `chromadb.PersistentClient`, which run embedded in the
  process. They open no port and have no tenants or HTTP routes.
- **Fix:** none published. 1.5.9 is the latest release.
- **Residual risk:** none as the project uses Chroma. If someone ever runs
  `chroma run` against the memory directory, for example to inspect it, they
  would start an unauthenticated server with remote code execution on
  whatever interface it binds. Dismiss as "vulnerable code is not actually
  used", and re-check when Chroma ships a fix.

### 10. Transitive and not reachable: leave

| Package | Pulled in by | Why the vulnerable code is not reached |
|---|---|---|
| httplib2 0.31.2 (1 high, gzip bomb) | google-generativeai -> google-api-python-client | `vision/vqa.py` only calls `GenerativeModel.generate_content`, which goes through google-api-core, not the httplib2 discovery client. It would also need a hostile Google endpoint. |
| langsmith 0.8.9 (1 high, TracingMiddleware file read) | langchain-core | Server-side tracing middleware. Nothing imports langsmith. |
| msgpack 1.1.2 (1 high, Unpacker reuse after error) | librosa | The project never unpacks msgpack streams. |
| pyasn1 0.6.3 (3 high, BER decoder DoS) | google-auth -> pyasn1-modules/rsa | google-auth only uses it in its pure-Python RSA fallback, to parse a service-account key. cryptography is installed, so that fallback is not used, and the key would be the user's own file. |
| starlette 1.2.1 (1 high, urlencoded `form()` limits) | fastapi (Docker API only) | No route calls `request.form()` or declares `Form(...)` / `UploadFile`. |

Upgrading these would clear alerts without reducing any risk, and each
upgrade has its own chance of breaking something. Dismiss them in Dependabot
with the reason above.

### 11. Orphans in the lock: remove, do not upgrade

| Package | Critical / high | Why it is in the lock |
|---|---|---|
| jupyter-server 2.19.0 | 1 / 1 | Jupyter |
| jupyterlab 4.5.7 | 0 / 2 | Jupyter |
| tornado 6.5.6 | 0 / 1 | Jupyter, streamlit |
| mistune 3.2.1 | 0 / 4 | nbconvert |
| soupsieve 2.8.3 | 0 / 2 | beautifulsoup4 <- nbconvert |
| vllm 0.22.0 | 0 / 3 | vLLM (a GPU inference server) |
| mcp 1.27.2 | 0 / 1 | vllm |
| js2py 0.74 | 0 / 1 | nothing (installed directly; no fix exists) |

Of everything the lock pins, these are the only ones none of the six
manifests declares, nothing declared requires, and no module in the
repository imports. The same holds for the moderate and low orphans:
accelerate, bleach, datasets, diskcache and python-multipart. Removing them,
along with the packages that exist only to serve them (78 pins in all), is
the correct fix. It is also the only fix for js2py and diskcache, which have
no patched release.

The other 58 orphan pins stay. None has an advisory, and several are only
orphans because the metadata is incomplete: pyautogui publishes no
dependency list on PyPI, and some pins exist only for Windows or Python 3.13.
A separate problem sits next to them. Some packages are imported by the code
but declared in no manifest: ollama, pyperclip, pycaw, silero-vad,
playwright and locust. Those are kept in the lock, and the triage treats them
as used. The proper cleanup is to declare what is imported, then regenerate
the lock from a clean install.

## Moderate and low, summary

| Package | Moderate / low | Disposition |
|---|---|---|
| aiohttp | 9 / 4 | Fixed by 3.14.3 |
| GitPython | 5 / 0 | Fixed by 3.1.60 |
| nltk | 7 / 1 | Fixed by 3.10.3 |
| torch (`requirements-torch.txt`) | 3 / 5 | Fixed by 2.11.0, except GHSA-rrmf (low, `torch.jit.script`, fixed in 2.13), which stays, as in the lock row below. The three with no listed fix do not affect 2.11.0. |
| torch 2.11.0+cu128 (lock) | 0 / 1 | GHSA-rrmf, `torch.jit.script` memory corruption, fixed in 2.13. Only affects scripting untrusted code, which the project does not do. Leave. |
| PyJWT | 3 / 1 | Fixed by 2.13.0 |
| cryptography | 1 / 0 | X.509 only, not reachable. Leave. |
| pydantic-settings | 1 / 0 | `NestedSecretsSettingsSource` is not used. Leave. |
| setuptools | 1 / 0 | Build-time sdist `MANIFEST.in` issue. Leave. |
| starlette | 0 / 1 | Not reachable, see above. Leave. |
| vllm, jupyterlab, mistune, tornado, soupsieve, bleach, accelerate, diskcache, python-multipart | 32 / 4 | Orphans, removed. |

## Pre-existing lock problem noticed

`grpcio-tools==1.83.0` in the lock requires `protobuf>=7.35.1`, but the lock
pins `protobuf==5.29.6`, so `pip install -r requirements-lock.txt` cannot
succeed as written. grpcio-tools is another orphan, but it has no advisory, so
it is not touched here. It is further evidence the lock needs regenerating.

## Update 2026-10-05: upgrades, ChromaDB removed, one acceptance left

Of the 14 critical and high advisories accepted above, 13 are gone and
one remains accepted.

- **Fixed by upgrading (9 high).** cryptography 48.0.1 -> 50.0.2,
  httplib2 0.31.2 -> 0.32.0, langsmith 0.8.9 -> 0.8.18, msgpack 1.1.2 ->
  1.2.3, pyasn1 0.6.3 -> 0.6.4, starlette 1.2.1 -> 1.3.1: the first release
  line with each fix, at its latest patch. Their reachability arguments
  (sections 7 and 10) were sound, but an upgrade does not depend on
  them staying sound. The whole lock was installed from scratch on Python
  3.13 with CPU torch: exactly the pinned versions, nothing extra, and
  `pip check` clean. The moderate advisories for cryptography and starlette
  went with them.
- **Removed (2 critical, 2 high).** Section 9 was right that the project
  never ran Chroma's server, but it missed that nothing used ChromaDB at
  all: `VectorDatabase` and `MemoryStoragePipeline` were constructed only
  by their tests, while `reasoning/memory/__init__.py` imported them
  eagerly, so every process that loaded the embedder imported chromadb
  (import of the embedder: 5.7-7.3 s with it, 3.9-4.5 s without). The two
  modules, their tests, the declarations and the lock pin were removed,
  with the 13 pins only chromadb required (bcrypt, build, durationpy,
  importlib_resources, kubernetes, mmh3, oauthlib, overrides, pybase64,
  PyPika, pyproject_hooks, requests-oauthlib, websocket-client). The code
  is in history at d6c2b4cc.
- **Still accepted (1 high): nltk GHSA-8mgp-746c-j5xp.** No fixed release.
  The earlier reason said the training script calls none of the affected
  APIs; that was not quite right. Through nlpaug's WordNet augmenter it
  does reach the perceptron tagger, whose model loading is among the
  affected functions. What keeps it unreachable is narrower: the advisory
  is a path traversal past nltk's opt-in pathsec sandbox when an attacker
  controls the model path, the tagger only loads from nltk's own data
  directory, and the project never enables pathsec. nltk is in the test and
  training extras only and is never imported by the assistant. Review by
  2026-12-31.

Audit result after these changes: no new critical or high findings, no
stale acceptances, 5 moderate/low (pydantic-settings, pyjwt, setuptools,
torch x2).

## Every critical and high alert

`File` is the manifest holding the pin: `lock` is `requirements-lock.txt` and
`torch` is `requirements-torch.txt`. `Reachable` is the verdict argued in the
sections above.

| Severity | Package | File | Advisory | Summary | Fixed in | Reachable | Action |
|---|---|---|---|---|---|---|---|
| Critical | chromadb 1.5.9 | lock | [GHSA-36p7-vc44-83pf](https://github.com/advisories/GHSA-36p7-vc44-83pf) | ChromaDB has a code injection vulnerability | none | No (server only) | Accept, no fix |
| Critical | chromadb 1.5.9 | lock | [GHSA-f4j7-r4q5-qw2c](https://github.com/advisories/GHSA-f4j7-r4q5-qw2c) | ChromaDB Python project has a pre-authentication code injection vulnerability | none | No (server only) | Accept, no fix |
| Critical | gitpython 3.1.50 | lock | [GHSA-284h-m62q-gf8w](https://github.com/advisories/GHSA-284h-m62q-gf8w) | GitPython: Dormant multi-line git-config values are corrupted into live injected directives... | 3.1.59 | Yes (`config_writer`) | Upgrade 3.1.60 |
| Critical | jupyter-server 2.19.0 | lock | [GHSA-fcw5-x6j4-ccmp](https://github.com/advisories/GHSA-fcw5-x6j4-ccmp) | Jupyter Server: Stored XSS in `NbconvertFileHandler` / `NbconvertPostHandler` via missing... | 2.20.0 | No (orphan) | Remove from lock |
| Critical | nltk 3.10.0 | lock | [GHSA-m4rf-3fr8-xwx3](https://github.com/advisories/GHSA-m4rf-3fr8-xwx3) | NLTK: JVM argument injection bypass via per-call options in the NLTK Stanford wrappers... | 3.10.3 | Dev script | Upgrade 3.10.3 |
| Critical | nltk 3.10.0 | lock | [GHSA-x99w-6fgc-pmfw](https://github.com/advisories/GHSA-x99w-6fgc-pmfw) | NLTK: Allowlisted pickle loaders still permit code execution in current source | 3.10.3 | Dev script | Upgrade 3.10.3 |
| Critical | torch 2.2.2 | torch | [GHSA-53q9-r3pm-6pq6](https://github.com/advisories/GHSA-53q9-r3pm-6pq6) | PyTorch: `torch.load` with `weights_only=True` leads to remote code execution | 2.6.0 | Yes | Upgrade 2.11.0 |
| High | aiohttp 3.13.5 | lock | [GHSA-cq5v-8q36-5273](https://github.com/advisories/GHSA-cq5v-8q36-5273) | AIOHTTP: Out-of-bounds heap read in C HTTP response parser error path (malformed chunked... | 3.14.3 | Yes | Upgrade 3.14.3 |
| High | chromadb 1.5.9 | lock | [GHSA-2wm9-hf6c-p5cr](https://github.com/advisories/GHSA-2wm9-hf6c-p5cr) | ChromaDB allows any authenticated users to arbitrarily read, write, update, or delete data... | none | No (server only) | Accept, no fix |
| High | chromadb 1.5.9 | lock | [GHSA-xph7-9rjv-w5fr](https://github.com/advisories/GHSA-xph7-9rjv-w5fr) | ChromaDB's SimpleRBACAuthorizationProvider doesn't check which tenant, database, or... | none | No (server only) | Accept, no fix |
| High | cryptography 48.0.0 | lock | [GHSA-537c-gmf6-5ccf](https://github.com/advisories/GHSA-537c-gmf6-5ccf) | Vulnerable OpenSSL included in cryptography wheels | 48.0.1 | Yes | Upgrade 48.0.1 |
| High | cryptography 48.0.0 | lock | [GHSA-g6cj-pr64-35w5](https://github.com/advisories/GHSA-g6cj-pr64-35w5) | cryptography: PKCS#7 EnvelopedData decryption exposes a Bleichenbacher oracle through... | 50.0.0 | No (no PKCS#7) | Leave, needs 50.x |
| High | cryptography 48.0.0 | lock | [GHSA-jwv3-5hgf-82ww](https://github.com/advisories/GHSA-jwv3-5hgf-82ww) | python-cryptography: Duplicate self-signed intermediates can cause exponential path-building | 49.0.0 | No (no X.509 verification) | Leave, needs 49.x |
| High | gitpython 3.1.50 | lock | [GHSA-2f96-g7mh-g2hx](https://github.com/advisories/GHSA-2f96-g7mh-g2hx) | GitPython: Command Injection via git long-option prefix abbreviation bypass of... | 3.1.51 | No (API not called) | Upgrade 3.1.60 |
| High | gitpython 3.1.50 | lock | [GHSA-3f7w-8rr8-f37f](https://github.com/advisories/GHSA-3f7w-8rr8-f37f) | GitPython: Unguarded git option forwarding in IndexFile.checkout() and... | 3.1.57 | No (API not called) | Upgrade 3.1.60 |
| High | gitpython 3.1.50 | lock | [GHSA-3rp5-jjmw-4wv2](https://github.com/advisories/GHSA-3rp5-jjmw-4wv2) | GitPython: git-config section-name injection enables arbitrary config directives... | 3.1.53 | Called, constant arguments | Upgrade 3.1.60 |
| High | gitpython 3.1.50 | lock | [GHSA-4gmw-gg2m-w46p](https://github.com/advisories/GHSA-4gmw-gg2m-w46p) | GitPython: Unguarded git read-tree option forwarding in... | 3.1.58 | No (API not called) | Upgrade 3.1.60 |
| High | gitpython 3.1.50 | lock | [GHSA-6p8h-3wgx-97gf](https://github.com/advisories/GHSA-6p8h-3wgx-97gf) | GitPython: Incomplete unsafe_git_clone_options denylist omits --template enabling arbitrary... | 3.1.54 | No (API not called) | Upgrade 3.1.60 |
| High | gitpython 3.1.50 | lock | [GHSA-7833-fr7j-v32q](https://github.com/advisories/GHSA-7833-fr7j-v32q) | GitPython: Arbitrary local file content disclosure via [include] directive in untrusted... | 3.1.59 | No (API not called) | Upgrade 3.1.60 |
| High | gitpython 3.1.50 | lock | [GHSA-8mcc-hrx5-hvxc](https://github.com/advisories/GHSA-8mcc-hrx5-hvxc) | GitPython: clone_from()/clone() omit --separate-git-dir from unsafe_git_clone_options,... | 3.1.59 | No (API not called) | Upgrade 3.1.60 |
| High | gitpython 3.1.50 | lock | [GHSA-94p4-4cq8-9g67](https://github.com/advisories/GHSA-94p4-4cq8-9g67) | GitPython: Environment-variable exfiltration via Repo.create_remote() / Remote.add() URL... | 3.1.55 | No (API not called) | Upgrade 3.1.60 |
| High | gitpython 3.1.50 | lock | [GHSA-956x-8gvw-wg5v](https://github.com/advisories/GHSA-956x-8gvw-wg5v) | GitPython: command injection via unguarded Git options in `Repo.archive()`,... | 3.1.51 | No (API not called) | Upgrade 3.1.60 |
| High | gitpython 3.1.50 | lock | [GHSA-9rj7-rf2p-w77r](https://github.com/advisories/GHSA-9rj7-rf2p-w77r) | GitPython: Unguarded git option forwarding in Repo.init enables arbitrary command execution... | 3.1.58 | No (API not called) | Upgrade 3.1.60 |
| High | gitpython 3.1.50 | lock | [GHSA-fjr4-x663-mwxc](https://github.com/advisories/GHSA-fjr4-x663-mwxc) | GitPython: Arbitrary file overwrite via git diff --output argument injection in... | 3.1.54 | No (API not called) | Upgrade 3.1.60 |
| High | gitpython 3.1.50 | lock | [GHSA-hmq2-w58f-27jc](https://github.com/advisories/GHSA-hmq2-w58f-27jc) | GitPython: Arbitrary Git Repository Creation Outside the Working Tree via Unvalidated... | 3.1.58 | No (API not called) | Upgrade 3.1.60 |
| High | gitpython 3.1.50 | lock | [GHSA-jm78-9fvv-mhgr](https://github.com/advisories/GHSA-jm78-9fvv-mhgr) | GitPython: git-config OPTION-name injection via =/#/whitespace bypasses name validator,... | 3.1.58 | Called, constant arguments | Upgrade 3.1.60 |
| High | gitpython 3.1.50 | lock | [GHSA-r9mr-m37c-5fr3](https://github.com/advisories/GHSA-r9mr-m37c-5fr3) | GitPython: Unsafe git option guard bypass via single-character kwarg value token smuggling... | 3.1.54 | No (API not called) | Upgrade 3.1.60 |
| High | gitpython 3.1.50 | lock | [GHSA-rwj8-pgh3-r573](https://github.com/advisories/GHSA-rwj8-pgh3-r573) | GitPython: Environment-variable exfiltration via os.path.expandvars() on Repo.clone_from() URL | 3.1.52 | No (API not called) | Upgrade 3.1.60 |
| High | gitpython 3.1.50 | lock | [GHSA-v396-v7q4-x2qj](https://github.com/advisories/GHSA-v396-v7q4-x2qj) | GitPython unsafe clone option gate bypass through joined short options | 3.1.51 | No (API not called) | Upgrade 3.1.60 |
| High | gitpython 3.1.50 | lock | [GHSA-wvpp-8hx9-p66j](https://github.com/advisories/GHSA-wvpp-8hx9-p66j) | GitPython: Unsafe git option guard bypass via split_single_char_options=False short-option... | 3.1.58 | No (API not called) | Upgrade 3.1.60 |
| High | httplib2 0.31.2 | lock | [GHSA-j5g9-f88f-gfj3](https://github.com/advisories/GHSA-j5g9-f88f-gfj3) | httplib2: Decompression Bomb Denial of Service via Unbounded gzip/deflate Response Handling | 0.32.0 | No | Leave |
| High | js2py 0.74 | lock | [GHSA-h95x-26f3-88hr](https://github.com/advisories/GHSA-h95x-26f3-88hr) | js2py allows remote code execution | none | No (orphan) | Remove from lock |
| High | jupyter-server 2.19.0 | lock | [GHSA-c3mw-737p-c7g2](https://github.com/advisories/GHSA-c3mw-737p-c7g2) | Jupyter Server: 5xx request logging leaks token-bearing Referer header values | 2.21.0 | No (orphan) | Remove from lock |
| High | jupyterlab 4.5.7 | lock | [GHSA-gx64-gj6p-pc4c](https://github.com/advisories/GHSA-gx64-gj6p-pc4c) | JupyterLab: Image viewer allows XSS when opening malicious image in new browser tab | 4.5.10 | No (orphan) | Remove from lock |
| High | jupyterlab 4.5.7 | lock | [GHSA-pppj-hq3g-57pj](https://github.com/advisories/GHSA-pppj-hq3g-57pj) | JupyterLab: Cross-site scripting (XSS) via crafted settings file (`overrides.json`) | 4.5.10 | No (orphan) | Remove from lock |
| High | langsmith 0.8.9 | lock | [GHSA-f4xh-w4cj-qxq8](https://github.com/advisories/GHSA-f4xh-w4cj-qxq8) | LangSmith SDK TracingMiddleware: Arbitrary server-side file read | 0.8.18 | No | Leave |
| High | mcp 1.27.2 | lock | [GHSA-vj7q-gjh5-988w](https://github.com/advisories/GHSA-vj7q-gjh5-988w) | MCP Python SDK: WebSocket server transport does not support Host/Origin validation | 1.28.1 | No (orphan) | Remove from lock |
| High | mistune 3.2.1 | lock | [GHSA-4j32-57v6-6g45](https://github.com/advisories/GHSA-4j32-57v6-6g45) | Mistune inline_parser: quadratic-time parsing on long runs of `**x**` and `***x***`... | 3.3.0 | No (orphan) | Remove from lock |
| High | mistune 3.2.1 | lock | [GHSA-c8j7-8cv4-2xmq](https://github.com/advisories/GHSA-c8j7-8cv4-2xmq) | Mistune plugins/formatting: quadratic-time parsing on long runs of `~~x~~`, `==x==`, and... | 3.3.0 | No (orphan) | Remove from lock |
| High | mistune 3.2.1 | lock | [GHSA-ffq3-xpv3-j92q](https://github.com/advisories/GHSA-ffq3-xpv3-j92q) | Mistune block_parser: quadratic-time parsing on long lists of repeated reference-link... | 3.3.0 | No (orphan) | Remove from lock |
| High | mistune 3.2.1 | lock | [GHSA-qcq2-496w-v96p](https://github.com/advisories/GHSA-qcq2-496w-v96p) | Mistune: Potential DoS via quadratic-time parsing in parse_link_text | 3.3.0 | No (orphan) | Remove from lock |
| High | msgpack 1.1.2 | lock | [GHSA-6v7p-g79w-8964](https://github.com/advisories/GHSA-6v7p-g79w-8964) | MessagePack for Python: Out-of-bounds read / crash on Unpacker reuse after a caught error | 1.2.1 | No | Leave |
| High | nltk 3.10.0 | lock | [GHSA-3gq4-3j92-5w49](https://github.com/advisories/GHSA-3gq4-3j92-5w49) | NLTK: Corpus Reader Sandbox Bypass | 3.10.3 | Dev script | Upgrade 3.10.3 |
| High | nltk 3.10.0 | lock | [GHSA-5gh2-94qg-qppq](https://github.com/advisories/GHSA-5gh2-94qg-qppq) | NLTK AllowlistUnpickler dotted-name validation bypass allows remote code execution | 3.10.3 | Dev script | Upgrade 3.10.3 |
| High | nltk 3.10.0 | lock | [GHSA-6hwm-xvph-95vm](https://github.com/advisories/GHSA-6hwm-xvph-95vm) | NLTK: Uncontrolled search path when invoking the Graphviz 'dot' binary | 3.10.3 | Dev script | Upgrade 3.10.3 |
| High | nltk 3.10.0 | lock | [GHSA-6ww7-3frv-cqxh](https://github.com/advisories/GHSA-6ww7-3frv-cqxh) | NLTK: pathsec SSRF protection can be bypassed when a proxy is configured | 3.10.3 | Dev script | Upgrade 3.10.3 |
| High | nltk 3.10.0 | lock | [GHSA-8mgp-746c-j5xp](https://github.com/advisories/GHSA-8mgp-746c-j5xp) | NLTK: Model-artifact APIs bypass pathsec and touch files outside allowed roots | none | Dev script | No fix; unreachable |
| High | nltk 3.10.0 | lock | [GHSA-97qj-x29f-37w7](https://github.com/advisories/GHSA-97qj-x29f-37w7) | NLTK: Entity-expansion DoS (billion laughs) via remaining raw ElementTree parses | 3.10.3 | Dev script | Upgrade 3.10.3 |
| High | nltk 3.10.0 | lock | [GHSA-f833-7jw8-xwrv](https://github.com/advisories/GHSA-f833-7jw8-xwrv) | NLTK: Symlink-based sandbox bypass in FramenetCorpusReader (bypasses the fix for... | 3.10.2 | Dev script | Upgrade 3.10.3 |
| High | nltk 3.10.0 | lock | [GHSA-p4rw-rvv2-7xwr](https://github.com/advisories/GHSA-p4rw-rvv2-7xwr) | NLTK: Corpus readers follow symlinks outside trusted roots despite pathsec enforcement | 3.10.3 | Dev script | Upgrade 3.10.3 |
| High | nltk 3.10.0 | lock | [GHSA-qx2g-xrx7-vfh8](https://github.com/advisories/GHSA-qx2g-xrx7-vfh8) | NLTK TweetTokenizer vulnerable to denial of service through catastrophic regex backtracking | 3.10.1 | Dev script | Upgrade 3.10.3 |
| High | nltk 3.10.0 | lock | [GHSA-w3v8-gmh9-3wv7](https://github.com/advisories/GHSA-w3v8-gmh9-3wv7) | NLTK: ReDoS in nltk.tgrep via unvalidated user-supplied regular expressions | 3.10.3 | Dev script | Upgrade 3.10.3 |
| High | pyasn1 0.6.3 | lock | [GHSA-8ppf-4f7h-5ppj](https://github.com/advisories/GHSA-8ppf-4f7h-5ppj) | pyasn1: Quadratic complexity in OBJECT IDENTIFIER and RELATIVE-OID processing allows denial... | 0.6.4 | No | Leave |
| High | pyasn1 0.6.3 | lock | [GHSA-hm4w-wwcw-mr6r](https://github.com/advisories/GHSA-hm4w-wwcw-mr6r) | pyasn1: Uncontrolled resource consumption when converting decoded REAL values | 0.6.4 | No | Leave |
| High | pyasn1 0.6.3 | lock | [GHSA-m4p7-r5rc-7g4j](https://github.com/advisories/GHSA-m4p7-r5rc-7g4j) | pyasn1 BER/CER/DER decoder denial of service via unbounded long-form tag IDs | 0.6.4 | No | Leave |
| High | pyjwt 2.12.1 | lock | [GHSA-xgmm-8j9v-c9wx](https://github.com/advisories/GHSA-xgmm-8j9v-c9wx) | PyJWT: Public-key JWK accepted as HMAC secret enables forged HS256 tokens when mixed... | 2.13.0 | No | Upgrade 2.13.0 (see note) |
| High | soupsieve 2.8.3 | lock | [GHSA-2wc2-fm75-p42x](https://github.com/advisories/GHSA-2wc2-fm75-p42x) | Soup Sieve has Memory Exhaustion via Large Comma-Separated Selector Lists | 2.8.4 | No (orphan) | Remove from lock |
| High | soupsieve 2.8.3 | lock | [GHSA-836r-79rf-4m37](https://github.com/advisories/GHSA-836r-79rf-4m37) | Soup Sieve: Regular Expression Denial of Service (ReDoS) via Selector Parser | 2.8.4 | No (orphan) | Remove from lock |
| High | starlette 1.2.1 | lock | [GHSA-82w8-qh3p-5jfq](https://github.com/advisories/GHSA-82w8-qh3p-5jfq) | Starlette: request.form() limits silently ignored for application/x-www-form-urlencoded... | 1.3.1 | No | Leave |
| High | tornado 6.5.6 | lock | [GHSA-mpf4-983q-p7j4](https://github.com/advisories/GHSA-mpf4-983q-p7j4) | Tornado: Urlencoded body parsing omits max_num_fields, so one request can stall the event loop | 6.5.8 | No (orphan) | Remove from lock |
| High | transformers 5.8.0 | lock | [GHSA-xrqw-3rrv-vx5w](https://github.com/advisories/GHSA-xrqw-3rrv-vx5w) | Transformers save_pretrained path traversal allows arbitrary file writes through chat... | 5.10.0 | Dev scripts | Upgrade 5.10.4 |
| High | vllm 0.22.0 | lock | [GHSA-33cg-gxv8-3p8g](https://github.com/advisories/GHSA-33cg-gxv8-3p8g) | vLLM denial of service via prompt embeds on M-RoPE models | 0.24.0 | No (orphan) | Remove from lock |
| High | vllm 0.22.0 | lock | [GHSA-8wr5-jm2h-8r4f](https://github.com/advisories/GHSA-8wr5-jm2h-8r4f) | vLLM has Remote DoS via Invalid Recovered Token Reinjection | 0.24.0 | No (orphan) | Remove from lock |
| High | vllm 0.22.0 | lock | [GHSA-rwxx-mrjm-wc2m](https://github.com/advisories/GHSA-rwxx-mrjm-wc2m) | vLLM: ReDoS via structured_outputs.regex compiled without timeout in xgrammar and outlines... | 0.24.0 | No (orphan) | Remove from lock |
