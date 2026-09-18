# AGENT_GURU — Round 11: Deployment System Hardening (Backlog #35)

**Date:** 2026-09-13
**Scope:** Full audit of `Agent_Guru/deployment/` (16 files) — closing out backlog task #35 ("verify/harden cross-platform deployment").

This round closes the deployment-hardening backlog item opened in Round 8. Every file in `deployment/` was read in full (not just the ones suspected of being interesting): `crypto_verifier.py`, `update_manager.py`, `update_orchestrator.py`, `package_manager.py`, `dependency_resolver.py`, `rollback_manager.py`, `installer_builder.py`, `build_installers.py`, `onboarding.py`, `monitoring.py`, `production.py`, `models.py`, `exceptions.py`, `__init__.py`. Four real, previously-undiscovered bugs were found and fixed, each with a standalone executed regression test proving the bug existed on the old code and is closed on the new code. Two further findings are documented but deliberately **not** fixed this round, with the reason stated plainly, per the project's "explain exactly why" mandate.

---

## Fix 1 — Ed25519 signature verification was never wired into the live update flow

**File:** `deployment/update_manager.py`

**Problem:** `UpdateManager.verify_update()` only checked a SHA-256 checksum against a value pulled from the *same* update manifest it had just downloaded. It never called `CryptoVerifier` at all. `Configuration.verification_policy` defaults to `VerificationPolicy.STRICT`, and the entire Ed25519 signing infrastructure (`CryptoVerifier`, the SQLite trust store, `add_trusted_key`) already existed and worked — but the one code path that actually gates a downloaded update package never invoked any of it. In practice, a compromised or spoofed update server could serve any payload with any checksum of its own choosing and it would sail through as "verified."

**Root cause:** the auto-update path (`UpdateManager`) and the multi-package transaction path (`UpdateOrchestrator`, which *does* call `CryptoVerifier.verify_package_signature` correctly) were built as two separate flows, and only one of them was ever wired to the verifier.

**Fix:**
- `UpdateManager.__init__` now accepts an optional `crypto_verifier: CryptoVerifier | None`.
- `UpdateInfo` now carries `signature` and `key_id` parsed from the manifest.
- `verify_update()` now calls `self._crypto_verifier.verify_package_signature(...)` when a verifier is configured, and raises `SignatureVerificationError` outright if a signature is present but its `key_id` does not resolve to a key in the local trust store.
- **Trust-pinning design choice, deliberately:** the verification key is *always* resolved from the local SQLite trust store by `key_id` (`_resolve_trusted_key()`), and the manifest's own `public_key` field is never used as the verification key. A signature verification scheme that accepts "here is the key that proves I'm legitimate" from the same untrusted channel as the payload is not a security boundary — it's theater. This was a deliberate design decision, not an oversight, and it's why the fix adds a `key_id` indirection rather than just passing the manifest's key straight through.
- When no `CryptoVerifier` is configured at all, the manager logs a warning and falls back to checksum-only (documented, not silent).

**Tested:** real Ed25519 keypairs, real SQLite trust store, real file I/O — 6/6 checks: a legitimately signed update (trusted key_id) is accepted; a payload "signed" by an attacker's own key under an unrecognized key_id is rejected; a tampered signature under a *valid* key_id is rejected; an unsigned update under the default STRICT policy is rejected; base64 manifest round-trip is correct; the no-verifier fallback still functions.

---

## Fix 2 — Trust store writes were silently discarded (never committed to disk)

**File:** `deployment/crypto_verifier.py`

**Problem:** `CryptoVerifier._connect()` used `with closing(sqlite3.connect(...)) as conn: yield conn`. `contextlib.closing()` guarantees the connection is *closed* — it does not commit. Python's `sqlite3` module does not auto-commit on `close()`. So every `add_trusted_key()` and `remove_trusted_key()` call logged `"trusted_key_added"` / `"trusted_key_removed"` and appeared to succeed, but the underlying `INSERT OR REPLACE` / `DELETE` was rolled back for free the instant the connection closed. This bug was masking Fix 1's entire trust model: even after wiring signature verification in, trusted keys added at runtime would not have actually persisted.

**Found by:** this was caught only because the Fix 1 test suite insisted on a real round-trip (add a key, then immediately try to use it) rather than trusting that `add_trusted_key()` "looked correct." The very first run of that test failed with `SignatureVerificationError: ... unrecognized key_id 'vendor-2026' ...` even though the key had just been added — which traced directly to this bug.

**Fix:** `_connect()` now opens the connection manually, commits explicitly on success, rolls back on any exception, and closes in a `finally` block — the standard, correct pattern for `sqlite3` transaction lifecycles.

**Tested:** standalone script confirming `add_trusted_key` → `get_trusted_keys()` (same instance, and separately, a *new* `CryptoVerifier` instance pointed at the same DB file) both see the key; `remove_trusted_key` persists across instances; `KeyNotFoundError` on removing an unknown key still raises correctly. Combined with Fix 1's test suite: 6/6.

---

## Fix 3 — `PackageManager` leaked one SQLite connection (and OS file descriptor) per database operation

**File:** `deployment/package_manager.py`

**Problem:** `_connect()` returned a bare `sqlite3.Connection` and every call site used it as `with self._connect() as conn:`. This is a well-known Python gotcha in the opposite direction from Fix 2: `sqlite3.Connection.__enter__`/`__exit__` manage the **transaction** (commit/rollback) but explicitly do **not** close the connection (confirmed directly against the Python docs and with a standalone repro: after 5 calls through this pattern, 5/5 connections were still open and usable). Every call to `_init_db()`, `get_installed_packages()`, `_register_package()`, `_unregister_package()`, and `_is_registered()` therefore opened a new SQLite connection — and its underlying OS file descriptor — that was never released for the remaining life of the process. `PackageManager` is meant to be a long-lived component (it's constructed once and reused for every install/remove/update over the life of the app), so this is a genuine, unbounded file-descriptor leak that would eventually exhaust the process's fd limit under sustained package activity — not a "rarely occurs" edge case, but a guaranteed leak on every single operation.

**Fix:** `_connect()` is now a proper `@contextmanager` generator that yields the connection and closes it in a `finally` block, while preserving the existing autocommit (`isolation_level = None`) behavior. Every existing `with self._connect() as conn:` call site works unchanged.

**Tested:** real `PackageManager` against a real SQLite file — 17/17 checks: zero live/usable `sqlite3.Connection` objects remain reachable (via `gc`) after `__init__`, after 10 registrations, after 10 lookups, after a full listing, and after 10 unregistrations; all existing insert/lookup/list/delete semantics verified unchanged.

---

## Fix 4 — `DependencyResolver`'s cache returned stale, wrong dependency graphs after the environment changed

**File:** `deployment/dependency_resolver.py`

**Problem:** `resolve_dependencies()` cached results keyed only on `(package_name, version)`. But the graph it builds also depends on `installed_packages` and `available_packages` — `_get_package_deps()` picks a dependency's resolved version preferentially from whichever packages are currently installed, falling back to the available-package registry. A single `DependencyResolver` instance is meant to be reused across an entire update session (`UpdateOrchestrator` holds one long-lived instance). So: resolve `app==1.0` once with an empty environment, then install some packages or have the available-package registry change, then resolve `app==1.0` again — the second call silently returned the **stale graph from the first call**, with none of the new dependency information, and no error was raised. This is a real correctness bug in the exact code path that decides installation order for update transactions.

**Fix:** the cache key now includes a fingerprint (`_environment_fingerprint()`) of both `installed_map` and `available_packages`, so a resolution is only ever reused when the environment it was computed under is unchanged, while an unchanged environment still gets the full O(1) cache-hit benefit the docstring promises.

**Tested:** 6/6 checks against the fixed code (same environment twice → real cache hit by object identity; environment changes via `available_packages` → fresh, correct graph, not the stale one; changed environment resolved again → cache hit; environment changes via `installed_packages` → dependency version correctly picked up from the newly-installed package). Confirmed the bug was real by running the identical test against a reconstructed copy of the pre-fix code: it failed 3 of 6 checks and crashed outright (`StopIteration`) on the installed-packages scenario, because the stale cached graph didn't even contain the dependency node.

---

## Findings documented but *not* fixed this round (with reasons)

**`deployment/onboarding.py` persists cloud LLM API keys in plaintext.** `LLMConfig.api_key` (an OpenAI/Anthropic/Gemini/DeepSeek key) flows straight into `OnboardingState`, which `_save_state()` writes to disk as `self._state.model_dump_json(indent=2)` — an unencrypted JSON file at `.guru/onboarding_state.json`. The repository already has exactly the right tool for this: `Agent_Guru/security/crypto/key_store.py`'s `KeyStore` class (AES-256-GCM at rest, PBKDF2-derived key, already used elsewhere in `security/crypto/`). I did not wire it in this round because doing so correctly requires knowing how this app's master/device key is meant to be sourced for `KeyStore(master_password=...)` — that's an architectural decision that lives outside `deployment/`, and I did not have time this round to trace where (or whether) a device-level master key is already established elsewhere before deciding how `onboarding.py` should obtain one. Wiring `KeyStore` in with a guessed or hardcoded password would be worse than the current gap (false sense of security). **Recommendation:** trace the master-key-sourcing pattern used elsewhere in `security/crypto/` (start with `identity.py`, which wasn't read this round) and route `LLMConfig.api_key` through `KeyStore.store_key()`/`retrieve_key()` instead of the plain pydantic JSON dump.

**`deployment/update_orchestrator.py`'s multi-package path takes a raw `public_key` per package from its caller, with no `key_id` concept at all.** `_run_transaction()` does `sig, pub_key = signatures.get(pkg_name, (None, None))` and passes `pub_key` straight into `CryptoVerifier.verify_package_signature()`. This is architecturally weaker than the Fix 1 design: there's no way for `UpdateOrchestrator` itself to enforce "resolve the key from the trust store by id" — it depends entirely on whatever code calls `execute_transaction()` to have already done that correctly. I searched the entire `deployment/` directory and could not find any caller of `execute_transaction()` — it must be invoked from a service/CLI layer elsewhere in the repository that I have not yet audited. I'm flagging this rather than claiming it's safe: until that caller is located and confirmed to resolve trusted keys correctly (rather than trusting a self-declared key bundled with the same payload, exactly the trap Fix 1 avoids), this path's real-world safety is unverified. **Recommendation:** either locate and audit that caller, or — the more robust fix — give `UpdateOrchestrator` the same `key_id`-based resolution `UpdateManager` now has, so the safety property is enforced at the primitive level instead of depending on every future caller getting it right.

---

## Files modified

- `Agent_Guru/deployment/update_manager.py`
- `Agent_Guru/deployment/crypto_verifier.py`
- `Agent_Guru/deployment/package_manager.py`
- `Agent_Guru/deployment/dependency_resolver.py`

All four were verified via `python3 -m py_compile` and committed to the device with anti-clobber (`expectedMtimeMs`) guards after being staged, edited, re-staged (to capture fresh mtimes), and restored from md5-verified local backups — the same recovery discipline used in every prior round.

## Files read and cleared (no bugs found)

`installer_builder.py`, `build_installers.py`, `production.py`, `monitoring.py`, `rollback_manager.py`, `models.py`, `exceptions.py`, `__init__.py`.

## Status

Backlog task #35 is considered closed for this round's scope: every file in `deployment/` has now had the same close read as the four controllers audited in Round 9. The two documented-but-unfixed findings above are carried forward as new, explicit backlog items rather than silently dropped.
