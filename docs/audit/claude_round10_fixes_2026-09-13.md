# AGENT_GURU — Round 10 Fixes (2026-09-13)

Closes the first item of the outstanding backlog from the Round 9 status check: verifying (and, since it turned out to be missing, actually wiring) `platform/features/presentation.py` into the live orchestrator.

## What was found

`presentation.py`'s own module docstring already carried an honest note from whoever built it: it was intentionally NOT connected to `integration/orchestrator.py`'s intent-routing yet, with a sketched plan for how to do it safely. That confirmed the standing question from Round 9 — the feature existed but a user asking Agent Guru to "make a presentation from my notes" would get no response from this code path at all.

## What was done

- **Wired `presentation.py` into `integration/orchestrator.py`** via a new `_handle_presentation_request()` method, hooked into `_detect_universal_features()` — the same "runs for every intent type, before system_control/file_ops dispatch" mechanism that `briefing`/`dictation`/`clipboard`/`screen-reading` detection already use. This required no changes to the 45KB rule-based `platform/intent_recognizer.py`, matching the module docstring's own recommendation to avoid "an unverified edit deep into the orchestrator's ~2800-line dispatch tables" — the hook point used here is an existing, narrow, well-tested seam instead.
- **Added `extract_source_path()`** to `presentation.py` for slot-filling: recognizes a quoted path or a bare filename ending in a known extension (`.txt/.md/.markdown/.rst/.log/.docx/.pdf`). This is honestly scoped — it does not resolve "my notes" to an actual file without an extension; that case now falls through to the conversational LLM to ask a clarifying question rather than guessing wrong.
- **Security**: the extracted source path is resolved through `security.path_utils.safe_path()`, sandboxed to the user's home directory — the same boundary Round 8 applied to `reasoning/tools/system/file_operations.py` — before any file is read. A path-traversal attempt is refused with a clear message and no file is touched.
- **Found and fixed a real bug in the trigger phrase matching** while writing the end-to-end test: the pre-existing `wants_presentation()` regex only matched "turn *this*/*it* into slides" (an anaphoric reference), never "turn notes.txt into a presentation" or "convert report.docx to slides" — both natural phrasings once this feature is actually reachable with a real file reference. Broadened to a general `turn/convert ... into/to ... <presentation-word>` alternative, verified NOT to false-positive on unrelated commands like "turn the volume down to 20" or "turn off the lights".

## Verification

Real, executed, end-to-end test (11/11 checks) — imported the actual, unmodified `orchestrator.py` and `presentation.py` (only `Agent_Guru.security.audit.logger`, an unrelated top-level dependency, was stubbed) and called `_handle_presentation_request()` directly:

- Non-presentation transcript → not handled (returns `None`, LLM gets the turn).
- Presentation request with no identifiable file → not handled (asks rather than guesses).
- Real in-sandbox `.md` source with markdown headings → a real `.pptx` was rendered on disk and re-opened with `python-pptx` to confirm multiple real slides.
- Quoted filename with spaces → handled correctly.
- `"convert X to a powerpoint"` phrasing → handled correctly (the regex fix).
- Outside-the-sandbox source (`safe_path()` boundary) → refused with a clear message, no `.pptx` written.
- Two false-positive guards (`"turn the volume down to 20"`, `"turn off the lights"`) → correctly not detected as presentation requests.

`py_compile` clean on both files. Committed to the device.

## Files changed this round

- `Agent_Guru/platform/features/presentation.py`
- `Agent_Guru/integration/orchestrator.py`

## Status of the rest of the Round 9 backlog

Not yet started this round: voice/vision/avatar subsystem audit, deployment hardening across Windows/macOS/Linux, the full ChromaDB/RAG memory migration, a genuine competitor benchmark, and the full comprehensive audit report. Continuing through these next.
