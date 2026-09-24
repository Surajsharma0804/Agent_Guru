# AGENT_GURU - Round 8 Fixes (2026-09-13)

## Central finding of this round

Rounds 4-7 hardened the `platform/os_controller.py` + `platform/controllers/*.py` + `platform/process_manager.py` layer extensively: protected-process deny-lists, AppleScript/PowerShell injection sanitization, path-traversal-safe file operations, and more.

This round discovered that **a second, independent implementation of the same OS-control functionality exists at `Agent_Guru/reasoning/tools/system/{app_control,process_control,file_operations,system_control}.py`** - registered as `@tool`-decorated classes (`app.open`, `app.close`, `app.switch`, `process.list`, `process.kill`, `file.read`, `file.write`, `file.delete`, `file.move`, `file.copy`, plus `system_control.py`'s four tools) via `reasoning/tools/registry.py`. This is exactly the "parallel architectures" / "duplicate implementations" the project mandate explicitly prohibits - and it is almost certainly the more important surface of the two, since it is the layer an LLM agent actually invokes through tool-calling, not a UI-driven convenience layer.

Before this round, this layer had received **none** of the platform layer's security hardening. It had the same classes of vulnerability that were fixed in the platform layer across Rounds 4-7, unpatched: no protected-process guard, no injection sanitization, no filesystem sandboxing.

`reasoning/tools/base.py` was read in full to confirm: `ToolSensitivity` (SAFE/SENSITIVE/DANGEROUS) is **pure metadata** with no enforcement anywhere in the framework. A tool marked `DANGEROUS` runs exactly the same as one marked `SAFE` - any confirmation gating happens (if at all) elsewhere in the pipeline, not as a property of the tool itself. Each tool's `execute()` is fully responsible for its own safety.

`device_list_dir` confirmed `reasoning/tools/system/` contains exactly these four files - no others were missed.

## Fixes applied

| File | Change | Verification |
|---|---|---|
| `reasoning/tools/system/app_control.py` | `close_app()`: added an unconditional protected-process guard (checks both `app_name` and `app_name.exe` against `is_protected_process_name`) before any platform dispatch, on all three platforms. | Real test: `close_app("explorer")` refused with **zero** `subprocess.run` calls; `close_app("notepad")` still succeeds, correct `taskkill` argv captured. |
| `reasoning/tools/system/app_control.py` | `close_app()` (darwin): sanitizes `app_name` via `sanitize_window_identifier()` before embedding it in the AppleScript `quit app "..."` string, instead of raw f-string interpolation. | Real test: AppleScript-injection payload refused with zero `subprocess.run` calls; normal app name still quits correctly via osascript. |
| `reasoning/tools/system/app_control.py` | `switch_app()` (windows) - **most severe fix this round**: sanitizes `app_name` before interpolating into the PowerShell `-Command` script (`Where-Object {{$_.MainWindowTitle -like "*{app_name}*"}}`). Previously, this was direct, unsanitized string interpolation into a PowerShell command block - full arbitrary command execution was reachable via a crafted `app_name` (e.g. `x" }} ; Remove-Item -Recurse -Force C:\Users ; $y = "`). | Real test: PowerShell-injection payload refused with zero `subprocess.run` calls; `switch_app("Google Chrome")` still works, safe name correctly embedded in the captured script. |
| `reasoning/tools/system/app_control.py` | `switch_app()` (darwin): same sanitization pattern applied to the `tell application "..." to activate` AppleScript. | Real test: injection payload refused, normal case still switches. |
| `reasoning/tools/system/process_control.py` | `kill_process()`: added a protected-PID/name guard before dispatch - refuses PID 1 unconditionally, and refuses any PID whose `psutil`-resolved process name matches the protected-process deny-list. | Real test: `kill_process(1, force=True)` refused; a real spawned child process disguised as `explorer.exe` (via a fake `psutil` injected into `sys.modules`) refused and confirmed still running afterward; a second real spawned child genuinely killed via the unmocked path, proving the guard isn't overbroad. |
| `reasoning/tools/system/file_operations.py` | All 5 tools (`FileReadTool`, `FileWriteTool`, `FileDeleteTool`, `FileMoveTool`, `FileCopyTool`) previously used bare `Path(...).resolve()` with **zero sandboxing** - any path, anywhere on the filesystem the process could reach, was readable/writable/deletable. Replaced with `safe_path(path, _FILE_TOOLS_BASE_DIR)` (the pre-existing, already-audited traversal-safe resolver from `security/path_utils.py`), sandboxed to `Path.home()` - matching `OSController`'s own `file_base_dir` default (Round 5) for consistency between the two layers. `FileMoveTool`/`FileCopyTool` sandbox **both** source and destination. | Real test: reads/writes/deletes outside the sandbox refused with the outside file provably untouched; in-sandbox operations still succeed; move/copy refused when *either* endpoint is outside the sandbox, even if the other is safe; fully in-sandbox move/copy still succeeds. |
| `reasoning/tools/system/file_operations.py` | `FileReadTool.execute()`: added `except ValueError as e: return {"success": False, "error": str(e)}` **after** the existing `except UnicodeDecodeError:` clause (ordering matters - `UnicodeDecodeError` is a `ValueError` subclass and must be matched first) to surface `safe_path()`'s traversal error as a clean tool failure instead of an unhandled exception. | Confirmed via the same sandbox-escape tests above; no unhandled exceptions during the run. |
| `reasoning/tools/system/system_control.py` | Reviewed in full, **left unmodified**. All PowerShell/AppleScript/shell interpolations use only bounds-checked integers (`0 <= level <= 100`, validated before use) or hardcoded literals from a small fixed set - no injection surface exists. | Existing implementation assessed as already correct; no change made per the mandate ("if the existing implementation is already superior, keep it"). |

All new cross-layer imports (`is_protected_process_name`, `sanitize_window_identifier` from `platform/`) follow the codebase's established convention: lazy, function-scoped imports marked `# layer-exempt: lazy import avoids module-level reasoning→platform dependency`, matching the existing pattern already used by `open_app()`'s import of `run_cmd`.

## Testing performed

A real, executed test suite (not simulated, not "should work") - **29/29 checks passing** - covering, for every fix:
1. The attack is refused with **zero** dangerous subprocess/Popen calls (captured via monkeypatched `subprocess.run`/`Popen`, asserted empty).
2. The legitimate, non-malicious case still works exactly as before (regression check).

Process-kill tests used real spawned child processes (`subprocess.Popen`), not mocks of the code under test - one genuinely protected via a faked `psutil.Process.name()`, one genuinely killed via the real, unmocked code path, to prove the guard is neither bypassable nor overbroad.

## Deferred / not fixed this round (documented backlog)

- **`platform/controllers/input_control.py`**: read in full; confirmed to be dead code - `OSController` constructs `MouseController`/`KeyboardController` but never calls any method on them (the real, live `type_text()` goes through `platform/controllers/text_input.py`, which already has mature Unicode support via clipboard-paste typing). Minor bugs found but not fixed, given the higher severity of the `reasoning/tools/system/` findings: inconsistent screen-bounds validation (`move_to()` validates, `click_at()`/`drag_to()`/`drag_relative()`/`scroll()` don't); a redundant, unlogged list-input special case in `KeyboardController.press()`; and a real "stuck modifier key" bug in `KeyHoldContext` - if a key press mid-list raises inside `__enter__()`, already-pressed keys are never released (Python `with`-statement semantics: `__exit__` never runs if `__enter__` raises), and `__exit__()` doesn't guard against one `key_up()` failure aborting release of the rest.
- **Architectural duplication itself**: this round patched the `reasoning/tools/system/` layer in place rather than consolidating it with the already-hardened `platform/` layer, because the async `Tool`/registry framework and its full set of callers were not yet completely read/understood - a rewrite under those conditions was assessed as too high-risk for this round's effort budget. Recommend a future round evaluate having `reasoning/tools/system/*.py` delegate to `platform/`'s implementations instead of maintaining two independently-patched copies indefinitely.
- **`system_settings.py`, `screen_capture.py`, `media_control.py`** (Round 7's original backlog): still unaudited.
- **`reasoning/tools/skills/sandbox.py` + `sandbox_executor.py`**: newly discovered this round via `device_list_dir` - a third-party skill installation/execution subsystem with a declared sandbox and permissions model (`permissions.py`). This is a high-risk, arbitrary-code-execution-by-design surface that has not been audited in any round to date and should be a priority for a future round: does the sandbox actually constrain filesystem/network/process access, is `permissions.py` enforced rather than declarative-only (the same trap `ToolSensitivity` turned out to be), and do `installer.py`/`loader.py` validate skill packages before execution.
- **`reasoning/tools/external/*.py`** (`messaging.py`, `email.py`, `calendar.py`, `maps.py`, `information.py`) and `reasoning/tools/knowledge/*.py`: also newly surfaced by this round's directory listing; not yet audited.

## Files changed this round

- `Agent_Guru/reasoning/tools/system/app_control.py`
- `Agent_Guru/reasoning/tools/system/process_control.py`
- `Agent_Guru/reasoning/tools/system/file_operations.py`

All three committed to the device at their original paths under `Agent_Guru/Agent_Guru/reasoning/tools/system/`.
