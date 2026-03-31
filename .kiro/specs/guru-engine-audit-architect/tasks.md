# Implementation Plan: Guru Engine Audit & Architect

## Overview

Surgical fixes across six areas: canonical utility consolidation, language pipeline repair,
controller wiring, error elimination, nosec annotations, and property-based + unit tests.
Each task builds on the previous; the final task wires everything together and verifies
end-to-end correctness.

## Tasks

- [x] 1. Create `Agent_Guru/platform/utils.py` with canonical fuzzy_match
  - Create `Agent_Guru/platform/utils.py` with `normalize(name: str) -> str` and
    `fuzzy_match(query: str, candidate: str) -> bool` exactly as specified in the design
  - Add module-level docstring documenting symmetry guarantee
  - _Requirements: 3.6, 4.5_

  - [ ]* 1.1 Write property test for fuzzy_match symmetry
    - **Property 3: Fuzzy Match Symmetry**
    - **Validates: Requirements 3.6, 4.5**
    - File: `Agent_Guru/platform/tests/test_utils_properties.py`
    - Use `@given(a=st.text(min_size=1), b=st.text(min_size=1))`, `@settings(max_examples=100)`
    - Assert `fuzzy_match(normalize(a), normalize(b)) == fuzzy_match(normalize(b), normalize(a))`

- [x] 2. Replace local `_fuzzy_match()` in three controllers with import alias
  - In `platform/controllers/desktop_app_controller.py`: remove local `_normalize` and
    `_fuzzy_match`, add `from Agent_Guru.platform.utils import fuzzy_match as _fuzzy_match`
  - Repeat for `platform/controllers/mobile_app_controller.py`
  - Repeat for `platform/controllers/messaging_controller.py`
  - Verify all existing call sites (`_fuzzy_match(...)`) still resolve correctly
  - _Requirements: 3.6_

- [x] 3. Consolidate `_detect_platform()` — replace 10 local copies with thin wrapper
  - For each of the 10 files listed below, remove the local `_PLATFORM_CACHE` global and
    the full `_detect_platform()` body; replace with the two-line wrapper that delegates to
    `PlatformDetector.detect().os_name.lower()`
  - Files: `platform/controllers/desktop_app_controller.py`,
    `platform/controllers/desktop_file_controller.py`,
    `platform/controllers/desktop_text_controller.py`,
    `platform/controllers/mobile_app_controller.py`,
    `platform/controllers/messaging_controller.py`,
    `platform/controllers/settings_controller.py`,
    `speech/stt_manager.py`,
    `speech/tts_manager.py`,
    `speech/wake_word_manager.py`,
    `memory/memory_manager.py`
  - Add `-> str` return type annotation to every wrapper
  - _Requirements: 3.3, 3.4_

  - [ ]* 3.1 Write property test for platform detection consistency
    - **Property 2: Platform Detection Consistency**
    - **Validates: Requirements 3.3, 3.4**
    - File: `Agent_Guru/platform/tests/test_platform_detector_properties.py`
    - For each fixed module, import its `_detect_platform` and assert it equals
      `PlatformDetector.detect().os_name.lower()`
    - Use `@given(st.none())`, `@settings(max_examples=100)`

- [x] 4. Add `nosec B603 B607` annotations to unguarded subprocess calls
  - In `Agent_Guru/platform/platform_detector.py` `_is_android()`: add
    `# nosec B603 B607` inline comment to the `subprocess.run(["uname", "-o"], ...)` call;
    add module-level justification comment above the function
  - In `Agent_Guru/platform/controllers/settings_controller.py` `_detect_platform()`:
    add the same `# nosec B603 B607` inline comment to its `subprocess.run` call
  - _Requirements: 7.3, 7.9_

- [x] 5. Add `detected_language` field to `PipelineResult` and update `_stage_stt()`
  - In `Agent_Guru/integration/orchestrator.py`, add `detected_language: str = ""`
    field to the `PipelineResult` dataclass (after `transcript`)
  - Change `_stage_stt()` return type from `str` to `tuple[str, str]`
  - Update the return statements in `_stage_stt()`:
    - async/mock path: return `(text, "")` or `(result.text, result.language)` when
      the result has a `.language` attribute
    - sync numpy path: after extracting `text`, also extract `language` from result if
      available, else `""`; return `(text, language)`
    - all early-exit paths (too short, too quiet, alignment error): return `("", "")`
  - _Requirements: 5.1, 5.4_

- [x] 6. Thread `detected_language` through `run_pipeline()` and `_stage_llm()`
  - In `run_pipeline()`, unpack Stage 1 result:
    `result.transcript, result.detected_language = await self._stage_stt(wake_event.audio)`
  - Add `language_code: str = ""` parameter to `_stage_llm()`
  - Pass `result.detected_language` as `language_code` at the Stage 4 call site
  - Inside `_stage_llm()`, build `lang_instruction` when `language_code` is non-empty
    and not `"en"`, and append it to the system prompt sent to `LLMRuntime.complete()`
  - After Stage 4 and before Stage 5, add the `TranslationEngine` fallback block:
    check `result.detected_language`, detect response language, call
    `self._translation_engine.translate(...)` if the attribute exists and languages differ
  - _Requirements: 5.3, 5.4, 5.6_

- [x] 7. Checkpoint — verify pipeline language threading
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Wire `DesktopApplicationController` into `OSController`
  - Add `_safe_init(self, cls, *args, **kwargs) -> Any` method to `OSController`
    with per-controller `try/except Exception` and `logger.warning` on failure
  - Add `_safe_init_desktop_app(self) -> Any` method that imports
    `DesktopApplicationController`, catches `RuntimeError` (mobile guard) separately,
    and returns `None` on any failure
  - Refactor `_init_controllers()` to call `_safe_init(...)` for each of the 12
    existing controllers and `_safe_init_desktop_app()` for `_desktop_app_controller`
  - Update `open_application()` to try `_desktop_app_controller.open_app(app_name)`
    first (when non-None), falling back to `_app_controller.open_application()`
  - Add missing `-> None` return type annotations to `_init_audit_log`,
    `_init_controllers`, `_log_operation`, `_require_confirmation`
  - Add `-> Any` return type annotation to `_safe_init`
  - _Requirements: 4.7, 2.5, 7.7_

- [x] 9. Eliminate bare `except:` clauses in production speech modules
  - In `Agent_Guru/speech/tts/tts_engine.py`: replace bare `except:` in
    `_get_wav_duration()` with `except Exception:`
  - In `Agent_Guru/speech/mobile/ios_tts.py`: replace bare `except:` in temp-file
    cleanup with `except OSError:` and in synthesizer stop/shutdown with
    `except Exception as exc:` (log `exc`)
  - In `Agent_Guru/speech/mobile/android_tts.py`: apply the same two replacements
    as `ios_tts.py`
  - _Requirements: 7.5_

- [x] 10. Checkpoint — verify error elimination and controller wiring
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Write property-based tests for the orchestrator pipeline
  - Create `Agent_Guru/integration/tests/test_orchestrator_properties.py`
  - Implement the following property tests using `hypothesis` with
    `@settings(max_examples=100)` and the tag comment format
    `# Feature: guru-engine-audit-architect, Property N: <text>`:

  - [ ]* 11.1 Write property test for language preservation
    - **Property 1: Language Preservation**
    - **Validates: Requirements 5.3, 5.4, 11.7**
    - `@given(language_code=st.sampled_from(["hi","ta","fa","kn","te","ml","gu","fr","de","en"]))`
    - Mock STT to return `TranscriptionResult` with the given language code
    - Assert `result.detected_language == language_code`

  - [ ]* 11.2 Write property test for pipeline stage count
    - **Property 4: Pipeline Stage Count**
    - **Validates: Requirements 6.1, 11.1, 11.2**
    - `@given(audio=st.binary(min_size=6400, max_size=32000))`
    - Use fully-mocked orchestrator; assert `result.stages_completed == 8`

  - [ ]* 11.3 Write property test for policy deny skips action
    - **Property 5: Policy Deny Skips Action**
    - **Validates: Requirements 6.3**
    - `@given(intent=st.text(min_size=1, max_size=100))`
    - Use deny-all policy mock; assert `result.action_result is None`
      and `result.stages_completed == 8`

  - [ ]* 11.4 Write property test for pipeline exception safety
    - **Property 6: Pipeline Exception Safety**
    - **Validates: Requirements 6.8**
    - `@given(failing_stage=st.integers(min_value=1, max_value=8))`
    - Inject a raising mock at the given stage; assert `result.error is not None`
      and `isinstance(result, PipelineResult)`

  - [ ]* 11.5 Write property test for audit log per run
    - **Property 7: Audit Log Per Run**
    - **Validates: Requirements 11.6**
    - `@given(st.none())`
    - Use a recording audit logger; assert exactly 1 event recorded with
      `actor_id == "guru_pipeline"`

  - [ ]* 11.6 Write property test for TTS response non-None on success
    - **Property 9: TTS Response Non-None for Successful Run**
    - **Validates: Requirements 11.4**
    - `@given(st.none())`
    - Use fully-mocked orchestrator; when `stages_completed == 8` and `error is None`,
      assert `result.tts_response is not None`

- [x] 12. Write unit tests for controller wiring, caches, and pipeline guards
  - Create or extend `Agent_Guru/platform/tests/test_os_controller_unit.py`:
    - Verify `OSController(require_confirmation=False)` instantiates all 13 controller
      types (including `_desktop_app_controller`) without raising
      (_Requirements: 4.7, 11.9_)
    - Verify `demo_live.py` can import `OSController` without error
      (_Requirements: 11.8_)
  - Create or extend `Agent_Guru/integration/tests/test_orchestrator_unit.py`:
    - Verify `_stt_fn` and `_tts_fn` are non-None after `startup()`
      (_Requirements: 6.4, 6.5, 8.7_)
    - Verify `_stage_stt` returns `("", "")` for audio shorter than 1600 samples
      (_Requirements: 8.8_)
    - Verify `_stage_stt` returns `("", "")` for audio with RMS < 0.001
      (_Requirements: 8.8_)
    - Verify `handle_concurrent_event` returns a 2-tuple
      (_Requirements: 6.6_)

- [x] 13. Final checkpoint — full suite green
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Property tests use `hypothesis >= 6.92.0` already in project dependencies
- Test files follow the existing convention: `Agent_Guru/{module}/tests/test_*.py`
- The `_safe_init` / `_safe_init_desktop_app` helpers use `_safe_init` as the name
  (the design document also shows `_try_init` as an alias — use `_safe_init` consistently)
- `open_application()` fallback chain: try `_desktop_app_controller.open_app()` first
  (async — must be awaited or called via `asyncio.run` depending on call context),
  then fall back to `_app_controller.open_application()`
