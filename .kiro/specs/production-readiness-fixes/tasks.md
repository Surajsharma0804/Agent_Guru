# Implementation Plan

- [x] 1. Write bug condition exploration property tests (BEFORE implementing any fix)
  - **Property 1: Bug Condition** - Security Defect Exploration Across All 23 Vulnerability Classes
  - **CRITICAL**: These tests MUST FAIL on unfixed code — failure confirms the bugs exist
  - **DO NOT attempt to fix the test or the code when it fails**
  - **GOAL**: Surface counterexamples that demonstrate each defect class on unfixed code
  - **Scoped PBT Approach**: Scope each property to the concrete failing case(s) for reproducibility
  - Create `Agent_Guru/reasoning/tests/test_security_bug_conditions.py`
  - CWE-94: Call `calculator_skill.dispatch("__import__('os').system('id')")` — expect no error on unfixed code; expect `ValueError` on fixed code
  - CWE-798: Grep source for literal credential patterns — expect matches on unfixed code; expect zero matches on fixed code
  - CWE-77: Call a platform command function with `; id` appended to a filename argument — expect shell execution on unfixed code
  - CWE-22: Pass `"../../etc/passwd"` to `file_operations` read function — expect file read on unfixed code; expect `PermissionError` on fixed code
  - CWE-396: Trigger an exception in a function with `except Exception: pass` — expect silent swallow on unfixed code; expect log entry on fixed code
  - CWE-400: Induce an exception mid-function that opens a file without `with` — expect leaked descriptor on unfixed code (detectable via `psutil.Process().open_files()`)
  - PyTorch: Run inference without `no_grad` and measure GPU memory — expect elevated memory on unfixed code
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests FAIL (this is correct — it proves the bugs exist)
  - Document counterexamples found to understand root cause
  - Mark task complete when tests are written, run, and failures are documented
  - _Requirements: 1.1, 1.6, 1.9, 1.10, 1.28, 1.84, 1.157, 1.286, 1.355_


- [x] 2. Write preservation property tests (BEFORE implementing any fix)
  - **Property 2: Preservation** - Non-Buggy Site Behavior Unchanged Across All Fix Categories
  - **IMPORTANT**: Follow observation-first methodology — observe UNFIXED code behavior first
  - Create `Agent_Guru/reasoning/tests/test_security_preservation.py`
  - Subprocess preservation: For internally-constructed argument lists with no user input, observe and record `CompletedProcess` results on unfixed code
  - Path preservation: For paths constructed from internal constants, observe `Path(p).resolve()` results on unfixed code
  - Exception preservation: For expected exceptions (e.g. `FileNotFoundError` on optional config), observe handler behavior on unfixed code
  - Query preservation: For queries with internally-validated parameters, observe result sets on unfixed code
  - Crypto preservation: For data encrypted with current algorithm, observe round-trip encrypt/decrypt on unfixed code
  - Training preservation: For training runs with seeds already set, observe model weights on unfixed code
  - Write property-based tests (Hypothesis) capturing all observed behavior patterns from Preservation Requirements 3.1–3.10
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10_


- [x] 3. Add shared security utilities (prerequisite for all fix batches)

  - [x] 3.1 Create `Agent_Guru/platform/subprocess_utils.py` — safe subprocess wrapper
    - Add `run_cmd(args: list[str], *, cwd: Path | None = None, timeout: int = 30, check: bool = True) -> subprocess.CompletedProcess`
    - Enforce `shell=False` unconditionally; raise `TypeError` if `args` is a string
    - Add `validate_arg(value: str, allowlist: set[str] | None = None) -> str` for user-supplied args
    - Add type hints and docstring with performance characteristics
    - _Bug_Condition: isBugCondition(X) where X.type = subprocess_call AND X.shell = true_
    - _Requirements: 2.7_

  - [x] 3.2 Create `Agent_Guru/security/path_utils.py` — safe path resolver
    - Add `safe_path(user_input: str | Path, base_dir: Path) -> Path`
    - Call `Path(user_input).resolve()` and assert `resolved.is_relative_to(base_dir.resolve())`
    - Raise `PermissionError` with descriptive message when path escapes base directory
    - Add type hints and docstring
    - _Bug_Condition: isBugCondition(X) where X.type = file_path_op AND X.canonicalized = false_
    - _Requirements: 2.8_

  - [x] 3.3 Create `set_deterministic_seeds` helper in `Agent_Guru/reasoning/scripts/train_intent_classifier.py` and extract to `Agent_Guru/training/seed_utils.py`
    - Implement `set_deterministic_seeds(seed: int = 42) -> None` calling `random.seed`, `np.random.seed`, `torch.manual_seed`, `torch.cuda.manual_seed_all`
    - Log the seed value at INFO level
    - _Bug_Condition: isBugCondition(X) where X.type = training_init AND X.random_seeds_set = false_
    - _Requirements: 2.24_

  - [x] 3.4 Create `safe_xml_parse` helper — add to `Agent_Guru/security/xml_utils.py`
    - Implement `safe_xml_parse(source: str | Path | IO) -> ET.Element` using `defusedxml.ElementTree.parse()`
    - Raise `ValueError` for any source that triggers external entity resolution
    - _Bug_Condition: isBugCondition(X) where X.type = xml_parse AND X.external_entities_disabled = false_
    - _Requirements: 2.18_

  - [x] 3.5 Write unit and property-based tests for all shared utilities
    - `test_subprocess_utils.py`: Property — for any list of strings, `run_cmd` never invokes a shell; raises `TypeError` on string input
    - `test_path_utils.py`: Property — for any string input, `safe_path` either returns path within `BASE_DIR` or raises `PermissionError`; never returns path outside `BASE_DIR`
    - `test_seed_utils.py`: `set_deterministic_seeds(42)` produces identical random sequences across two calls
    - `test_xml_utils.py`: XXE payload raises or returns no external data
    - Run `bandit -r Agent_Guru/security/ Agent_Guru/platform/subprocess_utils.py` — expect zero issues
    - _Requirements: 2.7, 2.8, 2.18, 2.24_


- [x] 4. Batch 1 — Critical: Code Injection (CWE-94) — 8 files

  - [x] 4.1 Fix `Agent_Guru/__init__.py` line 37 — replace `exec`/`eval` with structured dispatch
    - Add `_ALLOWED_ACTIONS: dict[str, Callable]` allowlist mapping
    - Implement `dispatch(action: str, **kwargs: Any) -> Any` raising `ValueError` for unknown actions
    - Remove the `exec(user_code)` / `eval(user_expression)` call entirely
    - _Bug_Condition: X.type = code_exec_site AND X.uses_exec_or_eval = true AND X.input_is_user_controlled = true_
    - _Expected_Behavior: ValueError raised for any input not in allowlist; no user-controlled code executed_
    - _Requirements: 2.1_

  - [x] 4.2 Fix `Agent_Guru/platform/async_executor.py` line 162 — replace `exec`/`eval`
    - Replace with structured dispatch or sandboxed allowlist; remove raw `exec`/`eval`
    - _Requirements: 2.4_

  - [x] 4.3 Fix `Agent_Guru/deployment/loader.py` line 165 — replace `exec`/`eval`
    - Replace plugin loader `exec` with `importlib.import_module` + explicit interface check
    - _Requirements: 2.4_

  - [x] 4.4 Fix `Agent_Guru/skills/calculator_skill.py` line 47 — replace `eval` with safe math parser
    - Implement `safe_eval_expr(expr: str) -> float` using `ast.parse(expr, mode="eval")` + `_eval_node`
    - Define `_SAFE_OPS = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv}`
    - Raise `ValueError` for any non-numeric or non-operator AST node
    - _Requirements: 2.5_

  - [x] 4.5 Fix `Agent_Guru/scripts/run_100_task_cycle.py` line 35, `Agent_Guru/sandbox/sandbox.py` line 29, `Agent_Guru/scripts/verify_installation.py` lines 43 and 71 — replace `exec`/`eval`
    - Replace each with structured dispatch or `importlib`-based dynamic loading
    - _Requirements: 2.6_

  - [x] 4.6 Write/update tests for Batch 1 fixes
    - `test_dispatch.py`: `dispatch("unknown")` raises `ValueError`; `dispatch("known_action")` calls correct handler
    - `test_safe_eval_expr.py`: `safe_eval_expr("2+3")` returns `5.0`; `safe_eval_expr("__import__('os')")` raises `ValueError`
    - Property: for any string not in allowlist, `dispatch` raises `ValueError`
    - Run `bandit -r` on all 8 fixed files — expect zero B102/B307 issues
    - _Requirements: 2.1, 2.4, 2.5, 2.6_

  - [x] 4.7 Run Bandit on Batch 1 files and verify zero CWE-94 issues remain
    - `bandit -r Agent_Guru/__init__.py Agent_Guru/platform/async_executor.py Agent_Guru/deployment/loader.py Agent_Guru/skills/calculator_skill.py Agent_Guru/scripts/ Agent_Guru/sandbox/sandbox.py`
    - Confirm zero B102 (exec used) and B307 (eval used) findings
    - _Requirements: 2.1, 2.4, 2.5, 2.6_


- [x] 5. Batch 2 — Critical: Hardcoded Credentials (CWE-798) — 22+ production files and all test files

  - [x] 5.1 Fix production credential files — replace literals with `os.environ` reads
    - `Agent_Guru/memory/conversation_memory.py` line 38: `API_KEY = os.environ["SERVICE_API_KEY"]`
    - `Agent_Guru/security/auditor.py` line 589: replace literal with `os.environ` read
    - `Agent_Guru/llm/providers/ollama_provider.py` line 49: `API_KEY: str = os.environ["OLLAMA_API_KEY"]`
    - `Agent_Guru/git/git_integration.py` line 48: replace literal with `os.environ` read
    - `Agent_Guru/platform/ios/ios_stt.py` lines 374 and 409: replace literals with `os.environ` reads
    - `Agent_Guru/scripts/autogen_benchmark.py` line 51: replace literal with `os.environ` read
    - `Agent_Guru/scripts/git_integration_example.py` line 86: replace literal with `os.environ` read
    - `Agent_Guru/scripts/verify_requirements.py` line 37: replace literal with `os.environ` read
    - All production files: use `os.environ["KEY"]` (raises `KeyError` if unset — fail fast)
    - _Bug_Condition: X.type = credential_source AND X.is_literal_in_source = true_
    - _Expected_Behavior: no credential literal in source; KeyError raised at startup if env var unset_
    - _Requirements: 2.2_

  - [x] 5.2 Fix test file credentials — replace with clearly-marked placeholders
    - `tests/test_security.py` line 40: replace with `PLACEHOLDER_KEY = "test-placeholder-not-real"  # noqa: S105`
    - `tests/test_cloud_sync.py` line 30: replace with placeholder
    - `tests/test_coverage_boost.py` line 635: replace with placeholder
    - `tests/test_crypto_identity.py` lines 23, 193, 209, 221, 231, 236, 256, 272, 287: replace all with placeholders
    - `tests/test_key_store.py` lines 22, 95, 134, 148, 161: replace all with placeholders
    - `tests/test_security_system.py` line 24: replace with placeholder
    - `tests/test_zk_proofs.py` lines 26, 189, 207, 225, 251: replace all with placeholders
    - `htmlcov/z_537e56f9c393debd_auditor_py.html` line 658: replace with placeholder (or exclude from scan)
    - All test placeholders must use string `"test-placeholder-not-real"` with `# noqa: S105` comment
    - _Requirements: 2.2_

  - [x] 5.3 Write/update tests for Batch 2 fixes
    - `test_no_hardcoded_credentials.py`: grep/AST-scan all production source files for credential literal patterns; assert zero matches
    - Verify each production module raises `KeyError` at import time when the required env var is unset
    - Run `bandit -r Agent_Guru/ -t B105,B106,B107` — expect zero findings
    - _Requirements: 2.2_

  - [x] 5.4 Run Bandit on all credential files and verify zero CWE-798 issues remain
    - `bandit -r Agent_Guru/ -t B105,B106,B107`
    - Confirm zero hardcoded password/credential findings
    - _Requirements: 2.2_


- [x] 6. Batch 3 — Critical: Weak Cryptography (CWE-327) — `file_operations.py`, `key_store.py`

  - [x] 6.1 Fix `Agent_Guru/platform/file_operations.py` line 1079 — replace MD5/SHA-1 with SHA-256
    - Replace `hashlib.md5(data).hexdigest()` with `hashlib.sha256(data).hexdigest()`
    - Replace any `hashlib.sha1` calls with `hashlib.sha256`
    - Also fix deprecated API at line 1081 (see Batch 13)
    - _Bug_Condition: X.type = crypto_op AND X.algorithm IN {MD5, SHA1}_
    - _Expected_Behavior: SHA-256 or stronger used; MD5/SHA-1 absent_
    - _Requirements: 2.3_

  - [x] 6.2 Fix `Agent_Guru/security/key_store.py` line 65 — replace MD5 key derivation with Argon2id
    - Replace `hashlib.md5(password.encode()).digest()` with Argon2id KDF
    - `from cryptography.hazmat.primitives.kdf.argon2 import Argon2id`
    - Parameters: `time=3, memory_cost=65536, parallelism=4, length=32`
    - Generate and store a random 16-byte salt per key derivation
    - Also fix hardcoded credential at line 39 (covered by Batch 2) and resource leaks at lines 41, 94, 118, 129, 166 (covered by Batch 12)
    - _Requirements: 2.3_

  - [x] 6.3 Write/update tests for Batch 3 fixes
    - `test_crypto_strength.py`: assert `hashlib.md5` and `hashlib.sha1` do not appear in `file_operations.py` or `key_store.py` (AST scan)
    - `test_key_derivation.py`: Argon2id round-trip — `derive(password, salt)` then verify; different salts produce different keys
    - Property: for any plaintext, AES-256-GCM encrypt then decrypt returns original plaintext
    - Run `bandit -r Agent_Guru/security/key_store.py Agent_Guru/platform/file_operations.py -t B303,B324` — expect zero findings
    - _Requirements: 2.3_

  - [x] 6.4 Run Bandit on crypto files and verify zero CWE-327 issues remain
    - `bandit -r Agent_Guru/ -t B303,B304,B305,B324`
    - Confirm zero weak-hash and weak-cipher findings
    - _Requirements: 2.3_


- [x] 7. Batch 4 — High: OS Command Injection (CWE-77/78/88) — 200+ locations across 50+ files

  - [x] 7.1 Fix automation and platform controller files (highest-risk production code)
    - `Agent_Guru/platform/application_control.py` lines 630, 654, 666, 753, 769, 778, 865, 881, 970, 986, 995, 1147, 1171: replace `subprocess.run(cmd, shell=True)` with `run_cmd([binary, *args])` from `subprocess_utils`
    - `Agent_Guru/platform/desktop_app_controller.py` lines 63, 95, 356, 376, 520, 535, 579, 612, 627, 640, 658, 675, 691, 708: same pattern
    - `Agent_Guru/platform/desktop_text_controller.py` lines 118, 471: same pattern
    - `Agent_Guru/platform/media_control.py` lines 352, 533, 556, 584: same pattern
    - `Agent_Guru/platform/messaging_controller.py` lines 79, 634: same pattern
    - `Agent_Guru/platform/messaging.py` lines 377, 379: same pattern
    - `Agent_Guru/platform/mobile_app_controller.py` lines 62, 399, 414, 452, 498, 542: same pattern
    - `Agent_Guru/platform/mobile_file_controller.py` line 81: same pattern
    - `Agent_Guru/platform/mobile_text_controller.py` lines 107, 439, 466, 514, 597, 666: same pattern
    - `Agent_Guru/platform/screen_capture.py` lines 201, 241, 262, 295: same pattern
    - `Agent_Guru/platform/settings_controller.py` line 67: same pattern
    - `Agent_Guru/platform/system_settings.py` lines 315, 342, 434, 442, 461, 474, 487, 500, 526, 542, 551, 574, 588, 607, 640, 666, 694, 709, 724, 739, 759, 775, 784, 809, 825, 841, 856, 894, 912, 935, 952: same pattern
    - `Agent_Guru/platform/window_management.py` lines 264, 309, 586, 627, 651, 805, 830, 1061, 1087, 1182, 1218, 1311, 1340, 1423: same pattern
    - _Bug_Condition: X.type = subprocess_call AND X.shell = true AND X.input_is_user_controlled = true_
    - _Expected_Behavior: shell=False; args passed as list; user input validated against allowlist_
    - _Requirements: 2.7_

  - [x] 7.2 Fix platform integration files
    - `Agent_Guru/platform/integration.py` (platform) lines 240, 298, 348, 410, 472, 573: replace with `run_cmd`
    - `Agent_Guru/platform/controller.py` (platform) lines 208, 244, 323, 406, 528, 580, 630: replace with `run_cmd`
    - `Agent_Guru/platform/macos/integration.py` lines 410, 526, 678, 777: replace with `run_cmd`
    - `Agent_Guru/platform/windows/integration.py` lines 504, 518, 531: replace with `run_cmd`
    - `Agent_Guru/platform/linux/controller.py` lines 221, 234, 253, 528, 580, 630: replace with `run_cmd`
    - `Agent_Guru/platform/process_manager.py` line 281: replace with `run_cmd`
    - `Agent_Guru/platform/integrator.py` line 2136: replace with `run_cmd`
    - _Requirements: 2.7_

  - [x] 7.3 Fix speech, vision, and ML pipeline files
    - `Agent_Guru/speech/engine.py` (intent) line 492: replace with `run_cmd`
    - `Agent_Guru/speech/synthesizer.py` line 583: replace with `run_cmd`
    - `Agent_Guru/speech/wake_word.py` line 244: replace with `run_cmd`
    - `Agent_Guru/speech/engine.py` (speech) line 511: replace with `run_cmd`
    - `Agent_Guru/platform/voice_context.py` line 145: replace with `run_cmd`
    - `Agent_Guru/memory/memory_manager.py` line 72: replace with `run_cmd`
    - `Agent_Guru/platform/runtime.py` line 314: replace with `run_cmd`
    - `Agent_Guru/security/encryption.py` line 356: replace with `run_cmd`
    - `Agent_Guru/security/logging.py` line 48: replace with `run_cmd`
    - `Agent_Guru/platform/rollback_monitor.py` lines 364, 405, 415, 426, 436: replace with `run_cmd`
    - `Agent_Guru/platform/async_executor.py` line 162: replace with `run_cmd` (also covered by Batch 1)
    - `Agent_Guru/intelligence/intelligence.py` lines 397, 466: replace with `run_cmd`
    - `Agent_Guru/sandbox/sandbox.py` line 207: replace with `run_cmd`
    - `Agent_Guru/deployment/loader.py` line 165: replace with `run_cmd` (also covered by Batch 1)
    - `Agent_Guru/vision/main.py` line 19: replace with `run_cmd`
    - `Agent_Guru/scripts/download_models.py` lines 189, 276, 293: replace with `run_cmd`
    - `Agent_Guru/scripts/check_gpu.py` line 52: replace with `run_cmd`
    - _Requirements: 2.7_

  - [x] 7.4 Fix automation skill files
    - `Agent_Guru/platform/app_control.py` lines 43, 46, 53, 90, 102, 114, 166, 178, 190: replace with `run_cmd`
    - `Agent_Guru/platform/process_control.py` lines 40, 66, 149: replace with `run_cmd`
    - `Agent_Guru/platform/system_control.py` lines 52, 64, 76, 125, 137, 149, 156, 204, 217, 230, 295, 308, 321: replace with `run_cmd`
    - `Agent_Guru/skills/calculator_skill.py` line 47: replace with `run_cmd` (also covered by Batch 1)
    - `Agent_Guru/scripts/run_100_task_cycle.py` line 35: replace with `run_cmd` (also covered by Batch 1)
    - `Agent_Guru/sandbox/sandbox.py` line 29: replace with `run_cmd` (also covered by Batch 1)
    - `Agent_Guru/scripts/verify_installation.py` lines 43, 71: replace with `run_cmd` (also covered by Batch 1)
    - _Requirements: 2.7_

  - [x] 7.5 Fix test files using `subprocess.run(shell=True)`
    - `tests/conftest.py` lines 37, 38, 39: replace with `run_cmd`
    - `tests/test_goal_manager.py` lines 68, 69, 70, 74, 75: replace with `run_cmd`
    - `tests/test_properties.py` lines 8442, 8443, 8444, 8449, 8450: replace with `run_cmd`
    - `tests/test_auto_commit.py` lines 32, 33, 39, 49, 50: replace with `run_cmd`
    - `tests/test_integrator_message_generation.py` lines 27, 28, 34, 44, 45: replace with `run_cmd`
    - `tests/test_integrator.py` lines 42, 50, 56, 161, 184, 190: replace with `run_cmd`
    - `tests/test_pr_creation.py` lines 672, 673, 679, 689, 690: replace with `run_cmd`
    - `tests/test_pr_integration.py` lines 28, 43, 61, 72, 223, 231, 237, 247, 253: replace with `run_cmd`
    - `tests/test_conflict_resolution.py` lines 456, 457, 462: replace with `run_cmd`
    - `tests/test_duplicate_integration.py` lines 294, 302, 308: replace with `run_cmd`
    - `Agent_Guru/platform/installer_builder.py` lines 187, 189: replace with `run_cmd`
    - _Requirements: 2.7_

  - [x] 7.6 Write/update tests for Batch 4 fixes
    - `test_subprocess_injection.py`: inject `; id` into each previously-vulnerable call site; assert `subprocess.CalledProcessError` or sanitised call (no shell execution)
    - Property: for any string argument containing shell metacharacters (`; | & $ \``), `run_cmd` passes it verbatim as a single argument without shell interpretation
    - Run `bandit -r Agent_Guru/ -t B602,B603,B604,B605` — expect zero findings
    - _Requirements: 2.7_

  - [x] 7.7 Run Bandit on all Batch 4 files and verify zero CWE-77/78/88 issues remain
    - `bandit -r Agent_Guru/ -t B602,B603,B604,B605`
    - Confirm zero shell-injection findings
    - _Requirements: 2.7_


- [x] 8. Batch 5 — High: Path Traversal (CWE-22) — 70+ locations across 60+ files

  - [x] 8.1 Fix core storage and config files
    - `Agent_Guru/memory/storage.py` line 124: wrap with `safe_path(user_path, DATA_DIR)`
    - `Agent_Guru/config/config.py` lines 90, 162, 200: wrap each user-derived path with `safe_path`
    - `Agent_Guru/avatar/engine.py` lines 89, 114, 134, 138: wrap each user-derived path with `safe_path(user_path, AVATAR_ASSETS_DIR)`
    - `Agent_Guru/security/crypto_verifier.py` line 172: wrap with `safe_path`
    - `Agent_Guru/deployment/package_manager.py` lines 199, 228, 249: wrap with `safe_path`
    - `Agent_Guru/deployment/rollback_manager.py` lines 114, 149: wrap with `safe_path`
    - `Agent_Guru/deployment/update_manager.py` lines 162, 239: wrap with `safe_path`
    - `Agent_Guru/reasoning/goal_storage.py` lines 91, 551, 585: wrap with `safe_path`
    - `Agent_Guru/memory/federated.py` line 49: wrap with `safe_path`
    - `Agent_Guru/config/config_loader.py` lines 85, 96, 101: wrap with `safe_path`
    - `Agent_Guru/memory/github_sync.py` line 177: wrap with `safe_path`
    - `Agent_Guru/security/audit_logger.py` line 110: wrap with `safe_path`
    - _Bug_Condition: X.type = file_path_op AND X.path_is_user_controlled = true AND X.canonicalized = false_
    - _Expected_Behavior: PermissionError raised for paths escaping BASE_DIR; valid paths returned unchanged_
    - _Requirements: 2.8_

  - [x] 8.2 Fix platform file operation files
    - `Agent_Guru/platform/application_control.py` lines 315, 330, 336, 343, 381: wrap with `safe_path`
    - `Agent_Guru/platform/file_operations.py` lines 304, 379, 438, 1090: wrap with `safe_path`
    - `Agent_Guru/platform/mobile_file_controller.py` line 128: wrap with `safe_path`
    - `Agent_Guru/git/integrator.py` lines 2014, 2019: wrap with `safe_path`
    - `Agent_Guru/git/message_generator.py` lines 149, 272: wrap with `safe_path`
    - `Agent_Guru/network/manager.py` lines 1298, 1441: wrap with `safe_path`
    - `Agent_Guru/platform/path_checker.py` lines 262, 285, 466, 482, 498: wrap with `safe_path`
    - `Agent_Guru/security/auditor.py` (platform security) line 335: wrap with `safe_path`
    - `Agent_Guru/policy/compliance.py` line 1421: wrap with `safe_path`
    - _Requirements: 2.8_

  - [x] 8.3 Fix training and ML pipeline files
    - `Agent_Guru/training/dataset_generator.py` lines 20, 157, 161, 166, 171, 184: wrap with `safe_path`
    - `Agent_Guru/training/entity_annotator.py` lines 19, 186, 214, 232: wrap with `safe_path`
    - `Agent_Guru/reasoning/scripts/train_intent_classifier.py` lines 394, 810, 811, 840, 850, 851, 852, 950, 959, 967, 1093, 1115, 1119: wrap with `safe_path`
    - `Agent_Guru/training/train_ner_model.py` lines 79, 225, 226, 227, 328, 341, 344: wrap with `safe_path`
    - `Agent_Guru/training/dataset_manager.py` lines 364, 387, 436, 437, 482: wrap with `safe_path`
    - `Agent_Guru/training/evaluation.py` lines 128, 169: wrap with `safe_path`
    - `Agent_Guru/training/export.py` lines 69, 72: wrap with `safe_path`
    - `Agent_Guru/training/failure_analysis.py` lines 262, 264, 292: wrap with `safe_path`
    - `Agent_Guru/training/integration.py` lines 99, 135, 181, 197, 220: wrap with `safe_path`
    - `Agent_Guru/training/pipeline.py` line 211: wrap with `safe_path`
    - `Agent_Guru/training/preprocess.py` lines 107, 151, 197, 198: wrap with `safe_path`
    - `Agent_Guru/training/report.py` lines 264, 267, 286, 289, 310: wrap with `safe_path`
    - `Agent_Guru/training/train.py` lines 155, 282: wrap with `safe_path`
    - `Agent_Guru/vision/config.py` line 132: wrap with `safe_path`
    - `Agent_Guru/vision/train.py` lines 83, 112, 200, 229, 231: wrap with `safe_path`
    - `Agent_Guru/vision/logging.py` line 78: wrap with `safe_path`
    - _Requirements: 2.8_

  - [x] 8.4 Fix benchmark, script, and plugin files
    - `Agent_Guru/benchmarks/base_benchmark.py` lines 89, 291: wrap with `safe_path`
    - `Agent_Guru/benchmarks/comprehensive_report.py` lines 64, 268, 450: wrap with `safe_path`
    - `Agent_Guru/benchmarks/run_benchmark.py` lines 80, 102, 120, 138, 156, 173: wrap with `safe_path`
    - `Agent_Guru/scripts/generate_final_report.py` lines 22, 318: wrap with `safe_path`
    - `Agent_Guru/scripts/run_100_task_cycle.py` lines 361, 570, 571, 576, 577, 582, 599: wrap with `safe_path`
    - `Agent_Guru/scripts/verify_execution_time.py` lines 22, 256: wrap with `safe_path`
    - `Agent_Guru/scripts/verify_git_integration.py` line 200: wrap with `safe_path`
    - `Agent_Guru/scripts/verify_improvement.py` line 109: wrap with `safe_path`
    - `Agent_Guru/scripts/verify_reasoning_accuracy.py` lines 22, 265: wrap with `safe_path`
    - `Agent_Guru/scripts/verify_system_stability.py` lines 25, 322: wrap with `safe_path`
    - `Agent_Guru/scripts/cleanup_model_checkpoints.py` line 51: wrap with `safe_path`
    - `Agent_Guru/scripts/evaluate_models.py` lines 97, 105: wrap with `safe_path`
    - `Agent_Guru/scripts/download_models.py` line 480: wrap with `safe_path`
    - `Agent_Guru/plugins/command_registry.py` lines 81, 85: wrap with `safe_path`
    - `Agent_Guru/platform/fast_router.py` lines 146, 150: wrap with `safe_path`
    - `Agent_Guru/platform/local_server.py` line 69: wrap with `safe_path`
    - `Agent_Guru/plugins/installer.py` line 391: wrap with `safe_path`
    - `Agent_Guru/plugins/loader.py` line 35: wrap with `safe_path`
    - `Agent_Guru/plugins/manifest.py` lines 91, 96: wrap with `safe_path`
    - `Agent_Guru/plugins/discovery.py` line 25: wrap with `safe_path`
    - _Requirements: 2.8_

  - [x] 8.5 Fix behavioral tracking and vector DB files
    - `Agent_Guru/tracking/app_tracker.py` line 48: wrap with `safe_path`
    - `Agent_Guru/tracking/behavioral_engine.py` line 70: wrap with `safe_path`
    - `Agent_Guru/tracking/command_tracker.py` line 47: wrap with `safe_path`
    - `Agent_Guru/tracking/feedback_store.py` line 51: wrap with `safe_path`
    - `Agent_Guru/tracking/goal_engine.py` line 68: wrap with `safe_path`
    - `Agent_Guru/tracking/pattern_detector.py` line 61: wrap with `safe_path`
    - `Agent_Guru/tracking/preference_learner.py` line 58: wrap with `safe_path`
    - `Agent_Guru/models/download_model.py` line 57: wrap with `safe_path`
    - `Agent_Guru/memory/vector_db.py` line 96: wrap with `safe_path`
    - `Agent_Guru/security/audit.py` lines 453, 456: wrap with `safe_path`
    - `Agent_Guru/database/database_schema.py` line 62: wrap with `safe_path`
    - `Agent_Guru/database/migrations.py` line 625: wrap with `safe_path`
    - `Agent_Guru/git/git_integration.py` lines 128, 145, 413, 422, 426: wrap with `safe_path`
    - `Agent_Guru/speech/whisper_stt.py` line 170: wrap with `safe_path`
    - `Agent_Guru/speech/voice_cloner.py` lines 766, 790: wrap with `safe_path`
    - `Agent_Guru/config/config_manager.py` lines 147, 257, 260, 303, 307, 312: wrap with `safe_path`
    - _Requirements: 2.8_

  - [x] 8.6 Write/update tests for Batch 5 fixes
    - `test_path_traversal.py`: pass `"../../etc/passwd"` to each previously-vulnerable file-reading function; assert `PermissionError` raised
    - Property: for any string input, `safe_path` either returns path within `BASE_DIR` or raises `PermissionError`; never returns path outside `BASE_DIR` (re-run from task 3.5)
    - Run `bandit -r Agent_Guru/ -t B101` (assert_used) and check path-related findings
    - _Requirements: 2.8_

  - [x] 8.7 Run Bandit on all Batch 5 files and verify zero CWE-22 issues remain
    - `bandit -r Agent_Guru/ -t B101` and review path traversal findings
    - Confirm zero open-without-canonicalization findings
    - _Requirements: 2.8_


- [x] 9. Batch 6 — High: Generic Exception Pass (CWE-396/397) — 68+ locations across 50+ files

  - [x] 9.1 Fix test setup/teardown files — replace `except Exception: pass` with typed + logged handlers
    - `tests/test_agent_lifecycle.py` line 39: `except OSError as exc: logger.debug("Cleanup skipped: %s", exc)`
    - `tests/test_specialization_tracker.py` line 40: same pattern
    - `tests/test_storage.py` line 56: same pattern
    - `tests/test_agent_merger_property.py` line 172: same pattern
    - `tests/test_orchestrator_integration.py` lines 43, 337: same pattern
    - `tests/test_state_manager.py` line 64: same pattern
    - `tests/test_error_logging_property.py` lines 130, 179, 220: same pattern
    - `tests/test_retry_logic.py` lines 108, 143, 179, 244: same pattern
    - `tests/test_integration.py` line 588: same pattern
    - `tests/test_runtime_integration.py` lines 45, 314: same pattern
    - `tests/test_macos_integration_integration.py` lines 66, 274: same pattern
    - `tests/test_auditor_comprehensive.py` line 1481: same pattern
    - `tests/test_integration_e2e.py` line 413: same pattern
    - `tests/test_windows_integration_exceptions.py` lines 208, 318, 348: same pattern
    - `tests/test_windows_integration_properties.py` lines 203, 343: same pattern
    - `tests/test_fallback_processor.py` line 581: same pattern
    - `tests/test_circuit_breaker.py` lines 380, 610: same pattern
    - `tests/test_integrator_message_generation.py` line 72: same pattern
    - `tests/test_background_service.py` line 776: same pattern
    - `tests/test_liveness_detection.py` line 293: same pattern
    - `tests/test_speech_engine.py` line 343: same pattern
    - `tests/test_language_detector.py` line 831: same pattern
    - `tests/test_tts_properties.py` lines 24, 559: same pattern
    - `tests/test_speech_integration.py` lines 327, 342: same pattern
    - `tests/test_catastrophic_recovery.py` line 64: same pattern
    - `tests/test_conflict_resolution.py` line 45: same pattern
    - `tests/test_ensemble_voting.py` line 479: same pattern
    - `tests/test_git_integration.py` lines 54, 817, 869, 967, 1058, 1209, 1277, 1490: same pattern
    - `tests/test_hardest_learning.py` line 42: same pattern
    - `tests/test_memory_integration.py` lines 40, 159: same pattern
    - `tests/test_meta_learner.py` lines 66, 542, 630, 708, 896, 1169, 1270, 1356: same pattern
    - `tests/test_policy_integration.py` lines 41, 212: same pattern
    - `tests/test_rollback_manager.py` line 48: same pattern
    - `tests/test_root_cause_investigator.py` line 52: same pattern
    - `tests/test_self_improvement_engine.py` line 47: same pattern
    - `tests/test_task_decomposer_property.py` lines 103, 132, 159, 191, 221, 249, 289, 329, 380, 410, 448, 486: same pattern
    - `tests/test_integration_checkpoint.py` lines 508, 627, 717: same pattern
    - `tests/test_vector_db.py` lines 57, 483, 612: same pattern
    - `tests/test_face_features_property.py` line 99: same pattern
    - _Bug_Condition: X.type = exception_handler AND X.handler_type = generic AND X.action = pass_
    - _Expected_Behavior: specific exception type caught; exception logged at WARNING or higher; never silently swallowed_
    - _Requirements: 2.9_

  - [x] 9.2 Fix production code files — replace `except Exception: pass` with typed + logged handlers
    - `Agent_Guru/avatar/renderer.py` line 314: `except (RenderError, ValueError) as exc: logger.warning("Render failed: %s", exc)`
    - `Agent_Guru/deployment/dependency_resolver.py` line 214: typed handler with logger.warning
    - `Agent_Guru/deployment/rollback_manager.py` line 239: typed handler with logger.warning
    - `Agent_Guru/reasoning/goal_storage.py` line 107: typed handler with logger.warning
    - `Agent_Guru/platform/runtime.py` line 197: typed handler with logger.warning
    - `Agent_Guru/platform/macos/controller.py` lines 522, 625: typed handler with logger.warning
    - `Agent_Guru/platform/linux/controller.py` lines 524, 559, 565, 713, 719: typed handler with logger.warning
    - `Agent_Guru/platform/windows/integration.py` line 526: typed handler with logger.warning
    - `Agent_Guru/platform/platform_detector.py` lines 314, 341: typed handler with logger.warning
    - `Agent_Guru/llm/fallback.py` lines 111, 243, 354: typed handler with logger.warning
    - `Agent_Guru/speech/synthesizer.py` line 586: typed handler with logger.warning
    - `Agent_Guru/monitoring/alerting.py` line 259: typed handler with logger.warning
    - `Agent_Guru/sandbox/sandbox.py` line 82: typed handler with logger.warning
    - `Agent_Guru/speech/wake_word.py` line 571: typed handler with logger.warning
    - `Agent_Guru/speech/engine.py` (speech) line 346: typed handler with logger.warning
    - `Agent_Guru/speech/android_tts.py` lines 137, 274: typed handler with logger.warning
    - `Agent_Guru/speech/ios_tts.py` line 301: typed handler with logger.warning
    - `Agent_Guru/speech/noise.py` lines 54, 66: typed handler with logger.warning
    - `Agent_Guru/speech/tts_engine.py` lines 80, 213: typed handler with logger.warning
    - `Agent_Guru/security/identity.py` lines 129, 192: typed handler with logger.warning
    - `Agent_Guru/speech/manager.py` lines 245, 274: typed handler with logger.warning
    - `Agent_Guru/benchmarks/agent_guru_benchmark.py` line 235: typed handler with logger.warning
    - `Agent_Guru/benchmarks/base_benchmark.py` line 148: typed handler with logger.warning
    - `Agent_Guru/database/connection_pool.py` lines 316, 449: typed handler with logger.warning
    - `Agent_Guru/training/ensemble_voting.py` line 738: typed handler with logger.warning
    - `Agent_Guru/database/migrations.py` lines 460, 511: typed handler with logger.warning
    - `Agent_Guru/reasoning/scripts/train_intent_classifier.py` line 227: typed handler with logger.warning
    - `Agent_Guru/vision/handwriting.py` line 140: typed handler with logger.warning
    - `Agent_Guru/vision/main.py` line 334: typed handler with logger.warning
    - _Requirements: 2.9_

  - [x] 9.3 Write/update tests for Batch 6 fixes
    - `test_exception_handling.py`: trigger an exception in each previously-silent handler; assert `logger.warning` was called (use `unittest.mock.patch`)
    - Property: for any exception raised inside a fixed handler, the exception is either logged or re-raised — never silently swallowed
    - Run `bandit -r Agent_Guru/ -t B110` (try-except-pass) — expect zero findings
    - _Requirements: 2.9_

  - [x] 9.4 Run Bandit on all Batch 6 files and verify zero CWE-396/397 issues remain
    - `bandit -r Agent_Guru/ -t B110,B112`
    - Confirm zero try-except-pass findings
    - _Requirements: 2.9_


- [x] 10. Batch 7 — High: XSS (CWE-79/80) — 26 locations across 20+ files

  - [x] 10.1 Fix orchestrator and sync engine files
    - `Agent_Guru/agents/orchestrator.py` lines 734, 768, 802, 807: wrap each user-supplied string with `html.escape()` before interpolation into output
    - `Agent_Guru/memory/github_sync_engine.py` line 146: apply `html.escape()`
    - `Agent_Guru/memory/github_sync.py` line 268: apply `html.escape()`
    - `Agent_Guru/reasoning/goal_decomposer.py` line 168: apply `html.escape()`
    - `Agent_Guru/policy/permissions.py` lines 105, 152: apply `html.escape()`
    - `Agent_Guru/platform/confirmation.py` line 314: apply `html.escape()`
    - _Bug_Condition: X.type = output_render AND X.data_is_user_supplied = true AND X.escaped = false_
    - _Expected_Behavior: html.escape() applied to all user-supplied strings before output; CSP header added to HTTP responses_
    - _Requirements: 2.10_

  - [x] 10.2 Fix speech synthesis and ML output files
    - `Agent_Guru/speech/normalizer.py` lines 451, 453, 455, 457: apply `html.escape()`
    - `Agent_Guru/speech/synthesizer.py` lines 1324, 1328, 1577: apply `html.escape()`
    - `Agent_Guru/training/feedback_loop.py` lines 595, 596: apply `html.escape()`
    - `Agent_Guru/training/suggestion_generator.py` lines 331, 333, 335, 337: apply `html.escape()`
    - `Agent_Guru/llm/context_injector.py` lines 296, 302: apply `html.escape()`
    - `Agent_Guru/llm/output_parser.py` line 461: apply `html.escape()`
    - `Agent_Guru/llm/prompt_templates.py` line 176: apply `html.escape()`
    - `Agent_Guru/training/meta_learner.py` line 714: apply `html.escape()`
    - `Agent_Guru/training/prompt_evolution.py` line 792: apply `html.escape()`
    - `Agent_Guru/deployment/rollback_manager.py` line 234: apply `html.escape()`
    - `Agent_Guru/training/strategy_optimizer.py` line 700: apply `html.escape()`
    - `Agent_Guru/vision/engine.py` line 139: apply `html.escape()`
    - `Agent_Guru/training/report.py` line 458: apply `html.escape()`
    - `Agent_Guru/vision/vqa.py` line 123: apply `html.escape()`
    - `Agent_Guru/scripts/verify_improvement.py` line 589: apply `html.escape()`
    - `Agent_Guru/platform/goal_manager_client.py` line 172: apply `html.escape()`
    - `Agent_Guru/platform/tool_cache.py` line 246: apply `html.escape()`
    - `Agent_Guru/self_improvement/integration.py` lines 661, 717, 757: apply `html.escape()`
    - `Agent_Guru/self_improvement/controller.py` line 101: apply `html.escape()`
    - For all HTTP response sites: add `response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'none'; object-src 'none'"`
    - _Requirements: 2.10_

  - [x] 10.3 Write/update tests for Batch 7 fixes
    - `test_xss_prevention.py`: pass `<script>alert(1)</script>` as user input to each previously-vulnerable output site; assert output contains `&lt;script&gt;` not `<script>`
    - Property: for any string containing HTML special characters, the escaped output never contains unescaped `<`, `>`, `&`, `"`, `'`
    - Run `bandit -r Agent_Guru/` and check for B703 (Jinja2 autoescape disabled) findings
    - _Requirements: 2.10_

  - [x] 10.4 Run Bandit on all Batch 7 files and verify zero CWE-79/80 issues remain
    - `bandit -r Agent_Guru/ -t B703`
    - Confirm zero XSS-related findings
    - _Requirements: 2.10_


- [x] 11. Batch 8 — High: SQL & NoSQL Injection (CWE-89, CWE-943) — 10 files

  - [x] 11.1 Fix SQL injection sites — replace f-string interpolation with parameterized queries
    - `Agent_Guru/reasoning/goal_engine.py` line 265: `session.execute(text("SELECT * FROM goals WHERE id=:id"), {"id": user_id})`
    - `Agent_Guru/database/connection_pool.py` lines 294, 429: replace f-string SQL with `session.execute(text(sql), params)`
    - `Agent_Guru/database/create_database.py` lines 92, 108: replace f-string SQL with parameterized `cursor.execute(sql, params)`
    - _Bug_Condition: X.type = sql_query AND X.uses_parameterized_api = false AND X.input_is_user_controlled = true_
    - _Expected_Behavior: parameterized queries used; no string interpolation of user input into SQL_
    - _Requirements: 2.12_

  - [x] 11.2 Fix NoSQL injection sites — replace string interpolation with typed filter objects
    - `Agent_Guru/platform/command_checker.py` line 583: validate type, use `{"field": {"$eq": user_input}}`
    - `Agent_Guru/security/security.py` lines 127, 140, 154: same pattern
    - `Agent_Guru/security/security_audit.py` lines 164, 200: same pattern
    - `Agent_Guru/training/convert_to_onnx.py` line 48: same pattern
    - `Agent_Guru/scripts/evaluate_models.py` line 113: same pattern
    - `Agent_Guru/reasoning/scripts/train_intent_classifier.py` line 52: same pattern
    - `Agent_Guru/training/export.py` lines 66, 138: same pattern
    - For each: validate `isinstance(user_input, str)` and type-check before query; use `$eq` operator
    - _Bug_Condition: X.type = nosql_query AND X.uses_parameterized_api = false AND X.input_is_user_controlled = true_
    - _Expected_Behavior: typed filter objects used; no string interpolation of user input into NoSQL queries_
    - _Requirements: 2.11_

  - [x] 11.3 Write/update tests for Batch 8 fixes
    - `test_sql_injection.py`: pass `"'; DROP TABLE goals; --"` to each SQL query site; assert query executes safely and returns expected result (not error)
    - `test_nosql_injection.py`: pass `{"$gt": ""}` as user input to each NoSQL query site; assert `ValueError` raised or query uses `$eq` operator
    - Property: for any string value passed as a query parameter, the parameterized query returns the same result as a manually-verified safe query with the same value
    - Run `bandit -r Agent_Guru/ -t B608` — expect zero findings
    - _Requirements: 2.11, 2.12_

  - [x] 11.4 Run Bandit on all Batch 8 files and verify zero CWE-89/943 issues remain
    - `bandit -r Agent_Guru/ -t B608`
    - Confirm zero SQL injection findings
    - _Requirements: 2.11, 2.12_


- [x] 12. Batch 9 — High: Embedding Authentication Thresholds (CWE-200/284/20) — 9 files

  - [x] 12.1 Add `verify_embedding` helper and enforce thresholds at all 9 sites
    - Add to `Agent_Guru/security/embedding_auth.py`:
      ```python
      BIOMETRIC_THRESHOLD = 0.97   # FAR < 0.1%
      RETRIEVAL_THRESHOLD = 0.85
      def verify_embedding(query: np.ndarray, stored: np.ndarray, threshold: float = BIOMETRIC_THRESHOLD) -> bool:
          score = float(np.dot(query, stored) / (np.linalg.norm(query) * np.linalg.norm(stored)))
          return score >= threshold
      ```
    - `Agent_Guru/llm/openai_adapter.py` line 181: replace bare similarity check with `verify_embedding(q, s, RETRIEVAL_THRESHOLD)`
    - `Agent_Guru/memory/memory_retriever.py` line 420: replace with `verify_embedding(q, s, RETRIEVAL_THRESHOLD)`
    - `Agent_Guru/memory/embedding.py` line 250: replace with `verify_embedding(q, s, RETRIEVAL_THRESHOLD)`
    - `Agent_Guru/security/biometric_auth.py` line 38: replace with `verify_embedding(q, s, BIOMETRIC_THRESHOLD)` + secondary liveness check
    - `Agent_Guru/speech/voice_auth.py` line 261: replace with `verify_embedding(q, s, BIOMETRIC_THRESHOLD)`
    - `Agent_Guru/vision/face_db.py` line 300: replace with `verify_embedding(q, s, BIOMETRIC_THRESHOLD)`
    - `Agent_Guru/vision/recognizer.py` line 78: replace with `verify_embedding(q, s, BIOMETRIC_THRESHOLD)`
    - `Agent_Guru/speech/wake_word.py` line 370: replace with `verify_embedding(q, s, RETRIEVAL_THRESHOLD)`
    - `Agent_Guru/speech/voice_cloner.py` lines 417, 677: replace with `verify_embedding(q, s, BIOMETRIC_THRESHOLD)`
    - _Bug_Condition: X.type = embedding_auth AND X.threshold_validated = false_
    - _Expected_Behavior: cosine similarity >= 0.97 for biometric; >= 0.85 for retrieval; below threshold rejected_
    - _Requirements: 2.13_

  - [x] 12.2 Write/update tests for Batch 9 fixes
    - `test_embedding_auth.py`: `verify_embedding` returns `True` iff cosine similarity >= threshold; returns `False` for near-miss below threshold
    - Property: for any pair of random unit vectors, `verify_embedding` returns `True` iff cosine similarity >= threshold — no false positives above threshold, no false negatives below
    - Test biometric auth rejects embeddings with similarity 0.96 (below 0.97 threshold)
    - Test retrieval accepts embeddings with similarity 0.86 (above 0.85 threshold)
    - _Requirements: 2.13_

  - [x] 12.3 Run mypy on embedding auth files and verify type correctness
    - `mypy Agent_Guru/security/embedding_auth.py Agent_Guru/security/biometric_auth.py Agent_Guru/speech/voice_auth.py Agent_Guru/vision/face_db.py`
    - Confirm zero type errors
    - _Requirements: 2.13_


- [x] 13. Batch 10 — High: Sensitive Data Redaction (CWE-200) — 5 files

  - [x] 13.1 Add `redact` helper and apply at all sensitive output sites
    - Add to `Agent_Guru/security/redaction.py`:
      ```python
      _REDACT_KEYS = frozenset({"password", "api_key", "token", "secret", "credential", "key"})
      def redact(data: dict) -> dict:
          return {k: "***REDACTED***" if k.lower() in _REDACT_KEYS else v for k, v in data.items()}
      ```
    - `Agent_Guru/platform/multi_step_executor.py` line 457: `logger.info("Result: %s", redact(result))`
    - `Agent_Guru/platform/app_control.py` lines 55, 124: apply `redact()` before logging
    - `Agent_Guru/platform/process_control.py` lines 94, 161: apply `redact()` before logging
    - `Agent_Guru/platform/system_control.py` lines 87, 167, 241, 332: apply `redact()` before logging
    - _Bug_Condition: X.type = sensitive_output AND X.data_redacted = false_
    - _Expected_Behavior: sensitive fields masked as "***REDACTED***" in all log output and error responses_
    - _Requirements: 2.14_

  - [x] 13.2 Write/update tests for Batch 10 fixes
    - `test_redaction.py`: `redact({"api_key": "secret123", "name": "test"})` returns `{"api_key": "***REDACTED***", "name": "test"}`
    - Property: for any dict, `redact` masks all keys in `_REDACT_KEYS` and preserves all other keys unchanged
    - Assert log output at each fixed site does not contain raw credential values
    - _Requirements: 2.14_


- [x] 14. Batch 11 — High: Permissions, Platform API, XXE, Language, Param Validation — 12 files

  - [x] 14.1 Fix loose file permissions (CWE-732/266)
    - `tests/test_goal_storage.py` lines 197, 240: replace `path.touch()` with `path.touch(mode=0o600)` and `path.mkdir(mode=0o700, parents=True)`
    - _Bug_Condition: X.type = file_permission AND X.permissions_restrictive = false_
    - _Expected_Behavior: files created with 0o600; directories with 0o700_
    - _Requirements: 2.15_

  - [x] 14.2 Fix platform API issues
    - `Agent_Guru/policy/compliance.py` lines 1110, 1153, 1194: guard `os.close(fd)` with `if sys.platform != "win32":` or replace with `pathlib`/`io` abstraction
    - `tests/conftest.py` line 37: replace deprecated `mp.Pool` usage with `ctx = mp.get_context("spawn"); ctx.Pool(processes=N)` (also covered by Batch 15)
    - _Bug_Condition: X.type = platform_api_call AND X.api_works_on_all_platforms = false_
    - _Expected_Behavior: platform-specific calls guarded; cross-platform abstractions used_
    - _Requirements: 2.16, 2.17_

  - [x] 14.3 Fix XXE injection (CWE-611)
    - `Agent_Guru/platform/output_validator.py` lines 100, 155: replace `xml.etree.ElementTree.parse()` with `defusedxml.ElementTree.parse()`; add `defusedxml` to requirements
    - `tests/test_testing_mode_property.py` line 54: replace with `defusedxml.ElementTree.parse()`
    - _Bug_Condition: X.type = xml_parse AND X.external_entities_disabled = false_
    - _Expected_Behavior: defusedxml used; external entities disabled by default_
    - _Requirements: 2.18_

  - [x] 14.4 Fix unprofessional language
    - `Agent_Guru/avatar/scene.py` line 33: replace unprofessional comment/string with professional equivalent
    - _Bug_Condition: X.type = language_content AND X.is_unprofessional = true_
    - _Expected_Behavior: professional, neutral language used throughout_
    - _Requirements: 2.19_

  - [x] 14.5 Fix public method parameter validation (CWE-20)
    - `tests/test_auditor.py` line 531: add `isinstance` checks and `ValueError` raises for invalid inputs at the public method entry point
    - `tests/test_properties.py` line 397: same pattern
    - `tests/test_tracking_property.py` line 104: same pattern
    - `tests/test_training_pipeline_property.py` line 171: same pattern
    - `Agent_Guru/training/train_all.py` line 29: add parameter validation
    - `tests/test_performance_tracker.py` line 419: same pattern
    - Pattern: `if not isinstance(value, str) or not value.strip(): raise ValueError(f"value must be non-empty string, got {value!r}")`
    - _Bug_Condition: X.type = public_method_call AND X.parameters_validated = false_
    - _Expected_Behavior: ValueError/TypeError raised with descriptive message for invalid inputs_
    - _Requirements: 2.20_

  - [x] 14.6 Write/update tests for Batch 11 fixes
    - `test_permissions.py`: assert created files have mode `0o600` and directories have mode `0o700`
    - `test_xxe.py`: pass crafted XXE payload to `safe_xml_parse`; assert no external data returned (re-run from task 3.5)
    - `test_param_validation.py`: pass `None`, `""`, `-1` to each public method with new validation; assert `ValueError` raised
    - Run `bandit -r Agent_Guru/ -t B320,B321` (XML parsing) — expect zero findings
    - _Requirements: 2.15, 2.16, 2.17, 2.18, 2.19, 2.20_


- [x] 15. Batch 12 — Medium: Resource Leaks (CWE-400/664) — 86+ locations across 50+ files

  - [x] 15.1 Fix core storage and memory files
    - `Agent_Guru/memory/storage.py` line 120: wrap `open(path)` with `with open(path) as f:`
    - `Agent_Guru/agents/agent_storage.py` lines 70, 79, 80, 185, 213, 257, 301, 377, 418, 473, 540: wrap each `open()` call with `with` statement
    - `Agent_Guru/security/audit.py` lines 76, 100, 157, 180, 192, 201: wrap each `open()` call with `with` statement
    - `Agent_Guru/reasoning/goal_storage.py` line 93: wrap with `with` statement
    - `Agent_Guru/platform/session_manager.py` line 147: wrap with `with` statement
    - `Agent_Guru/agents/orchestrator.py` line 886: wrap with `with` statement
    - `Agent_Guru/memory/github_sync.py` lines 74, 115, 143: wrap each with `with` statement
    - `Agent_Guru/database/wal.py` lines 48, 98, 115: wrap each with `with` statement
    - `Agent_Guru/security/audit_logger.py` line 67: wrap with `with` statement
    - `Agent_Guru/policy/policy_storage.py` lines 91, 114: wrap each with `with` statement
    - `Agent_Guru/policy/permissions.py` lines 204, 270, 370, 463, 548, 591: wrap each with `with` statement
    - `Agent_Guru/security/key_store.py` lines 41, 94, 118, 129, 166: wrap each with `with` statement
    - _Bug_Condition: X.type = resource_open AND X.uses_context_manager = false AND X.has_finally_close = false_
    - _Expected_Behavior: all resources closed via context manager; closed even when exceptions occur_
    - _Requirements: 2.21_

  - [x] 15.2 Fix platform and automation files
    - `Agent_Guru/platform/automation.py` lines 45, 75, 113: wrap each with `with` statement
    - `Agent_Guru/platform/runtime.py` lines 304, 312: wrap each with `with` statement
    - `Agent_Guru/security/manager.py` lines 69, 289, 310, 348, 403, 421, 438: wrap each with `with` statement
    - `Agent_Guru/database/connection_pool.py` lines 98, 281: wrap each with `with` statement
    - `Agent_Guru/database/database_schema.py` lines 64, 65, 603, 604, 626, 627: wrap each with `with` statement
    - `Agent_Guru/database/create_database.py` lines 57, 58: wrap each with `with` statement
    - `Agent_Guru/database/health_check.py` lines 117, 118, 211, 212, 269, 270, 337, 338: wrap each with `with` statement
    - `Agent_Guru/database/migrations.py` lines 90, 91, 247, 305, 306, 423, 425, 482: wrap each with `with` statement
    - `Agent_Guru/database/monitoring.py` lines 77, 78, 135, 136, 206, 207, 285, 286: wrap each with `with` statement
    - `Agent_Guru/training/prompt_evolution.py` line 941: wrap with `with` statement
    - `Agent_Guru/training/meta_learner.py` lines 197, 198, 400, 401, 451, 452, 515, 516, 726, 727, 812, 813, 925, 926: wrap each with `with` statement
    - `Agent_Guru/platform/cache.py` lines 41, 75, 81, 101: wrap each with `with` statement
    - `Agent_Guru/platform/logger.py` lines 102, 311: wrap each with `with` statement
    - _Requirements: 2.21_

  - [x] 15.3 Fix speech and vision files
    - `Agent_Guru/speech/tts_manager.py` line 918: wrap with `with` statement
    - `Agent_Guru/speech/synthesis_engine.py` line 417: wrap with `with` statement
    - `Agent_Guru/speech/tts_engine.py` lines 78, 84, 461, 583: wrap each with `with` statement
    - `Agent_Guru/benchmarks/result_storage.py` lines 36, 135, 162, 183: wrap each with `with` statement
    - `Agent_Guru/platform/iot/automation.py` lines 45, 75, 113: wrap each with `with` statement (if separate from platform automation)
    - _Requirements: 2.21_

  - [x] 15.4 Fix test files with resource leaks
    - `tests/test_adversarial.py` lines 83, 84: wrap each with `with` statement
    - `tests/test_error_logging_property.py` lines 129, 174, 175, 178, 214, 217, 251, 264: wrap each with `with` statement
    - `tests/test_goal_storage.py` lines 62, 63, 277, 278, 305, 306, 330, 331, 355, 356, 380, 381, 405, 406, 445, 446, 467, 468, 610, 611, 645, 646: wrap each with `with` statement
    - `tests/test_properties.py` lines 7409, 7410, 7589, 7590, 7707, 7708, 7805, 7806: wrap each with `with` statement
    - `tests/test_session_manager.py` lines 161, 162, 204, 205, 246, 247, 286, 287, 325, 326: wrap each with `with` statement
    - `tests/test_orchestrator.py` lines 255, 350, 361: wrap each with `with` statement
    - `tests/test_iot_property.py` line 55: wrap with `with` statement
    - `tests/test_iot.py` lines 22, 28, 33, 39, 59: wrap each with `with` statement
    - `tests/test_integration.py` lines 58, 59: wrap each with `with` statement
    - `tests/test_desktop_app_controller_property.py` lines 92, 348: wrap each with `with` statement
    - `tests/test_desktop_file_controller.py` lines 281, 647: wrap each with `with` statement
    - `tests/test_desktop_text_controller.py` lines 181, 207, 218, 236: wrap each with `with` statement
    - `tests/test_key_store.py` line 87: wrap with `with` statement
    - `tests/test_connection_pool.py` lines 468, 471: wrap each with `with` statement
    - `tests/test_database_constraints_property.py` lines 960, 961, 1002, 1003, 1040, 1041, 1061, 1062: wrap each with `with` statement
    - `tests/test_database_schema.py` lines 53, 54, 80, 81, 101, 102, 121, 122, 141, 142, 162, 163, 181, 182: wrap each with `with` statement
    - `tests/test_meta_learner.py` lines 201, 202, 224, 225: wrap each with `with` statement
    - `tests/test_migrations.py` lines 58, 59, 164, 165, 208, 209, 233, 234, 258, 259, 276, 277, 298, 299, 393, 394: wrap each with `with` statement
    - `tests/test_error_handling_properties.py` lines 322, 409, 440, 474, 503: wrap each with `with` statement
    - `tests/test_stt_manager_property.py` lines 126, 146, 181, 212, 365, 404, 433: wrap each with `with` statement
    - `tests/test_tts_manager.py` lines 579, 596, 614, 632, 650: wrap each with `with` statement
    - `tests/test_wake_word_manager_property.py` line 149: wrap with `with` statement
    - `tests/test_verifier_system_property.py` lines 120, 306, 318, 361, 373: wrap each with `with` statement
    - `tests/test_depth.py` lines 212, 247, 280: wrap each with `with` statement
    - `tests/test_gesture.py` lines 234, 266, 295, 317: wrap each with `with` statement
    - `tests/test_handwriting.py` line 223: wrap with `with` statement
    - `tests/test_ocr.py` lines 225, 262, 301, 366: wrap each with `with` statement
    - `tests/test_privacy.py` line 108: wrap with `with` statement
    - `tests/test_scene.py` lines 339, 376: wrap each with `with` statement
    - `Agent_Guru/scripts/verify_execution_time.py` line 29: wrap with `with` statement
    - `Agent_Guru/scripts/verify_improvement.py` lines 203, 204: wrap each with `with` statement
    - `Agent_Guru/scripts/verify_reasoning_accuracy.py` line 29: wrap with `with` statement
    - `Agent_Guru/scripts/verify_system_stability.py` lines 32, 56, 105, 149: wrap each with `with` statement
    - _Requirements: 2.21_

  - [x] 15.5 Write/update tests for Batch 12 fixes
    - `test_resource_closure.py`: induce an exception mid-function at each previously-leaking site; assert file descriptor is closed (use `psutil.Process().open_files()` before and after)
    - Property: for any sequence of operations that may raise, a function using `with open(...)` always closes the file descriptor regardless of which operation raises
    - Run `bandit -r Agent_Guru/ -t B403` and check resource-related findings
    - _Requirements: 2.21_

  - [x] 15.6 Run Bandit on all Batch 12 files and verify zero CWE-400/664 issues remain
    - `bandit -r Agent_Guru/` and review resource-leak findings
    - Confirm zero open-without-context-manager findings
    - _Requirements: 2.21_


- [x] 16. Batch 13 — Medium: Deprecated APIs — 7 files

  - [x] 16.1 Replace deprecated API calls with current equivalents
    - `Agent_Guru/deployment/package_manager.py` line 220: replace `distutils` usage with `importlib.metadata`
    - `tests/test_installer_builder.py` lines 61, 94, 184, 225: replace deprecated calls with current API
    - `Agent_Guru/deployment/update_manager.py` lines 227, 244: replace deprecated calls with current API
    - `Agent_Guru/platform/file_operations.py` line 1081: replace deprecated `imp` with `importlib` (also covered by Batch 3)
    - `Agent_Guru/platform/output_validator.py` lines 100, 155: replace `xml.etree.ElementTree` with `defusedxml.ElementTree` (also covered by Batch 11)
    - `tests/test_testing_mode_property.py` line 54: replace deprecated XML parser with `defusedxml` (also covered by Batch 11)
    - `Agent_Guru/scripts/download_models.py` lines 504, 519: replace deprecated model download API with current `huggingface_hub` or equivalent
    - _Bug_Condition: X.type = deprecated_api_call AND X.api_is_current = false_
    - _Expected_Behavior: current recommended API used; no deprecation warnings at runtime_
    - _Requirements: 2.22_

  - [x] 16.2 Write/update tests for Batch 13 fixes
    - `test_no_deprecated_apis.py`: run each fixed module and assert no `DeprecationWarning` is emitted
    - Run `python -W error::DeprecationWarning -m pytest` on affected test files — expect zero deprecation warnings
    - _Requirements: 2.22_


- [x] 17. Batch 14 — Medium: PyTorch Best Practices — 15 files

  - [x] 17.1 Add `torch.no_grad()` guards to all inference/evaluation sites
    - `Agent_Guru/training/convert_to_onnx.py` line 48: wrap forward pass with `with torch.no_grad():`
    - `Agent_Guru/scripts/evaluate_models.py` line 132: wrap forward pass with `with torch.no_grad():`
    - `Agent_Guru/training/evaluation.py` line 435: wrap forward pass with `with torch.no_grad():`
    - `Agent_Guru/training/export.py` line 147: wrap forward pass with `with torch.no_grad():`
    - `Agent_Guru/vision/train.py` line 308: wrap eval forward pass with `with torch.no_grad():`
    - `Agent_Guru/scripts/download_models.py` lines 144, 215, 318, 352: wrap each eval forward pass with `with torch.no_grad():`
    - _Bug_Condition: X.type = eval_mode AND X.no_grad_context = false_
    - _Expected_Behavior: torch.no_grad() applied; gradient tracking disabled during evaluation; GPU memory at baseline_
    - _Requirements: 2.23_

  - [x] 17.2 Add deterministic seed calls to all training/evaluation entry points
    - `Agent_Guru/scripts/evaluate_models.py` line 40: call `set_deterministic_seeds(seed)` before evaluation loop
    - `Agent_Guru/reasoning/scripts/train_intent_classifier.py` line 72: call `set_deterministic_seeds(seed)` before training
    - `tests/test_train_intent_classifier.py` line 26: call `set_deterministic_seeds(42)` in test setup
    - `Agent_Guru/training/dataset_manager.py` line 286: call `set_deterministic_seeds(seed)` before data loading
    - `Agent_Guru/training/export.py` line 56: call `set_deterministic_seeds(seed)` before export
    - `Agent_Guru/vision/train.py` line 75: call `set_deterministic_seeds(seed)` before training
    - `Agent_Guru/scripts/download_models.py` line 136: call `set_deterministic_seeds(seed)` before model loading
    - _Bug_Condition: X.type = training_init AND X.random_seeds_set = false_
    - _Expected_Behavior: random.seed, np.random.seed, torch.manual_seed, torch.cuda.manual_seed_all all called; seed logged_
    - _Requirements: 2.24_

  - [x] 17.3 Fix tensor creation on wrong device
    - `Agent_Guru/reasoning/scripts/train_intent_classifier.py` line 980: replace `tensor.to(device)` with `torch.zeros(shape, device=device)` at creation time
    - _Bug_Condition: X.type = tensor_creation AND X.created_on_cpu_then_moved = true_
    - _Expected_Behavior: tensors created directly on target device; no CPU-to-GPU copy_
    - _Requirements: 2.25_

  - [x] 17.4 Fix DataLoader configuration
    - `Agent_Guru/reasoning/scripts/train_intent_classifier.py` DataLoader usage: set `num_workers=min(4, os.cpu_count() or 1)`, `persistent_workers=True`, `pin_memory=True`
    - _Bug_Condition: X.type = dataloader_config AND X.num_workers_causes_memory_growth = true_
    - _Expected_Behavior: memory-stable DataLoader configuration; no memory growth over iterations_
    - _Requirements: 2.26_

  - [x] 17.5 Write/update tests for Batch 14 fixes
    - `test_pytorch_best_practices.py`: run inference with `no_grad` and measure GPU memory before/after — assert within 5% of baseline
    - `test_deterministic_seeds.py`: call `set_deterministic_seeds(42)` twice; assert identical random sequences produced (re-run from task 3.5)
    - `test_tensor_device.py`: assert tensor created with `device=device` has correct device attribute without intermediate CPU allocation
    - Run `mypy Agent_Guru/reasoning/scripts/train_intent_classifier.py Agent_Guru/training/` — expect zero type errors
    - _Requirements: 2.23, 2.24, 2.25, 2.26_


- [x] 18. Batch 15 — Medium: Multiprocessing & Network Timeout — 2 files

  - [x] 18.1 Fix multiprocessing in `Agent_Guru/sandbox/sandbox.py` line 75
    - Replace improper `multiprocessing.Process` usage with:
      ```python
      ctx = multiprocessing.get_context("spawn")
      proc = ctx.Process(target=fn, args=args)
      proc.start()
      proc.join(timeout=30)
      if proc.is_alive():
          proc.terminate()
      ```
    - _Bug_Condition: X.type = multiprocessing_call AND X.correct_api_and_params = false_
    - _Expected_Behavior: correct start_method used; join with timeout; terminate if still alive; no deadlocks_
    - _Requirements: 2.27_

  - [x] 18.2 Fix network timeout in `Agent_Guru/scripts/verify_requirements.py` line 196
    - Replace bare `socket.connect()` with `socket.create_connection((host, port), timeout=30)` or set `socket.setdefaulttimeout(30)` before connection
    - _Bug_Condition: X.type = network_connection AND X.timeout_set = false_
    - _Expected_Behavior: connection timeout set to 30s; connection never blocks indefinitely_
    - _Requirements: 2.28_

  - [x] 18.3 Write/update tests for Batch 15 fixes
    - `test_multiprocessing.py`: spawn a process that sleeps 60s; assert `proc.join(timeout=5)` returns and `proc.is_alive()` is `False` after `terminate()`
    - `test_network_timeout.py`: connect to a non-routable address (e.g. `192.0.2.1`); assert `socket.timeout` raised within 35s
    - Run `bandit -r Agent_Guru/sandbox/sandbox.py Agent_Guru/scripts/verify_requirements.py` — expect zero findings
    - _Requirements: 2.27, 2.28_


- [x] 19. Verify bug condition exploration test now passes (post-fix validation)

  - [x] 19.1 Re-run the SAME exploration tests from task 1 on FIXED code
    - **Property 1: Expected Behavior** - Security Defect Exploration Tests Now Pass
    - **IMPORTANT**: Re-run the SAME test from task 1 — do NOT write new tests
    - The tests from task 1 encode the expected behavior
    - When these tests pass, it confirms the expected behavior is satisfied
    - Run `pytest Agent_Guru/reasoning/tests/test_security_bug_conditions.py`
    - **EXPECTED OUTCOME**: All tests PASS (confirms all bugs are fixed)
    - CWE-94: `dispatch("__import__('os').system('id')")` now raises `ValueError`
    - CWE-798: grep finds zero credential literals in production source
    - CWE-77: injected metacharacters do not execute; `subprocess.CalledProcessError` or sanitised call
    - CWE-22: `"../../etc/passwd"` path raises `PermissionError`
    - CWE-396: exception is logged, not silently swallowed
    - CWE-400: file descriptor is closed after exception
    - PyTorch: GPU memory within 5% of baseline after `no_grad`-wrapped inference
    - _Requirements: 2.1, 2.7, 2.8, 2.9, 2.21, 2.23_

- [x] 20. Verify preservation tests still pass (regression check)

  - [x] 20.1 Re-run the SAME preservation tests from task 2 on FIXED code
    - **Property 2: Preservation** - Non-Buggy Site Behavior Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 — do NOT write new tests
    - Run `pytest Agent_Guru/reasoning/tests/test_security_preservation.py`
    - **EXPECTED OUTCOME**: All tests PASS (confirms no regressions)
    - Subprocess preservation: internally-constructed calls produce same `CompletedProcess` as before
    - Path preservation: internal-constant paths resolve identically
    - Exception preservation: expected exceptions still caught and handled gracefully
    - Query preservation: parameterized queries return same result sets
    - Crypto preservation: round-trip encrypt/decrypt returns original plaintext
    - Training preservation: same seed + same data produces same model weights
    - Confirm all Preservation Requirements 3.1–3.10 satisfied
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10_


- [x] 21. Run full Bandit scan and verify zero HIGH/MEDIUM issues remain

  - [x] 21.1 Run full Bandit scan across entire codebase
    - `bandit -r Agent_Guru/ -ll` (HIGH and MEDIUM severity only)
    - Confirm zero HIGH findings (B102, B105, B106, B107, B303, B304, B305, B307, B324, B602, B603, B604, B605, B608, B703)
    - Confirm zero MEDIUM findings (B110, B112, B320, B321, B403)
    - If any findings remain, fix them before proceeding
    - _Requirements: 2.1–2.28_

  - [x] 21.2 Run mypy strict type check across all modified files
    - `mypy Agent_Guru/ --strict`
    - Confirm zero type errors in all modified files
    - Fix any type errors introduced by the fixes
    - _Requirements: 2.1–2.28_

  - [x] 21.3 Run integration tests for critical paths
    - End-to-end platform command execution: voice command → `PlatformController.execute_command` → subprocess → result, with injected metacharacters; verify no shell injection
    - End-to-end file operation: user-supplied filename with traversal path → `file_operations` → verify `PermissionError` raised
    - End-to-end biometric auth: near-match embedding below 0.97 threshold → verify access denied
    - End-to-end training run: two runs with same seed → verify identical loss curves
    - End-to-end inference: GPU memory before/after `no_grad`-wrapped inference within 5% of baseline
    - _Requirements: 2.7, 2.8, 2.13, 2.23, 2.24_

- [-] 22. Run full test suite and verify all tests pass

  - [ ] 22.1 Run complete pytest suite
    - `pytest --cov=Agent_Guru --cov-report=html -x`
    - Confirm all existing tests pass (zero regressions)
    - Confirm coverage >= 80% across all modified modules
    - Fix any test failures before marking complete
    - _Requirements: 3.1–3.10_

  - [~] 22.2 Run property-based tests with increased iterations
    - `pytest -m property --hypothesis-seed=0`
    - Confirm all property-based tests pass with deterministic seed
    - Confirm Property 1 (Bug Condition) tests pass on fixed code
    - Confirm Property 2 (Preservation) tests pass on fixed code
    - _Requirements: 2.1–2.28, 3.1–3.10_

  - [~] 22.3 Checkpoint — Ensure all tests pass and zero Bandit issues remain
    - All 22 task groups complete
    - `bandit -r Agent_Guru/ -ll` reports zero HIGH/MEDIUM issues
    - `mypy Agent_Guru/ --strict` reports zero errors
    - `pytest` reports zero failures
    - All 1,000 defects across 23 vulnerability classes addressed
    - Ask the user if any questions arise before closing
    - _Requirements: 2.1–2.28, 3.1–3.10_
