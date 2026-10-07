# Extraction record

What was taken from the reference project, in what form, and how it was
checked. Code-level provenance for anything in the repository is in
`THIRD_PARTY_PROVENANCE.md`; this file records the method and the ideas.

## Method

1. Both trees indexed with an AST pass (module, docstring summary,
   top-level classes with bases, public functions), BOM-tolerant, because
   35 AGENT_GURU files start with a byte-order mark that `ast.parse`
   rejects.
2. AGENT_GURU's reachable modules computed from `main.py` through every
   import, including imports inside functions; the modules actually loaded
   at startup recorded with `python -X importtime main.py`; the
   orchestrator's per-turn calls read.
3. Reference-project modules that call its compiled Rust extension listed, since
   they cannot be taken as Python alone.
4. Reuse candidates read in full on both sides before any decision.

## Taken

| Idea | From | Into | Form |
|---|---|---|---|
| One row per interaction plus one per step, with full-text search over the text, so slow stages and failures can be queried later | `traces/store.py`, `core/types.py` | `integration/turn_trace.py`, orchestrator stage timing | design only; AGENT_GURU code written for its fixed voice-turn stages |
| Outcome recorded as unknown, not success, when it was not verified | `core/types.py` `Trace.outcome` | `TurnRecord.outcome` | design only; matches AGENT_GURU's existing action truthfulness rules |

## Read and planned, not yet taken

Reading Ollama's last-chunk token counts on a streamed call
(`engine/ollama.py`); background fact extraction with trust tiers
(`memory/*`); SQLite-persisted schedules (`scheduler/*`); a hash-chained
audit log (`security/audit.py`); installation diagnostics
(`cli/doctor_cmd.py`). Each has an entry in the integration plan.

## Not reusable as Python

`agents/loop_guard.py`, `security/capabilities.py`, `file_policy.py`,
`injection_scanner.py`, `rate_limiter.py`, `scanner.py`, the calculator,
file, git, HTTP and shell tools, and the BM25 and SQLite memory backends
call the Rust extension and have no Python fallback (SSRF protection is
the exception).
