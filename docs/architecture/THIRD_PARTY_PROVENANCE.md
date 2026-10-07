# Third-party provenance

Where AGENT_GURU code came from, when it was not written from scratch for
AGENT_GURU. One entry per integrated component. Check this file before
copying code from another project, and add the entry in the same commit
as the code.

## Rules

- Code copied or adapted from another project keeps that project's
  required notices in the file itself, and its license text ships under
  `third_party/<project>/`. Removing a required notice is not allowed,
  whatever the naming preference.
- Code written for AGENT_GURU after reading another project is
  AGENT_GURU's own and carries no notice. It is still listed here, so a
  reviewer can see what it was informed by and check that nothing was
  copied.
- An entry is never written as "independently implemented" for code that
  was materially copied.

## Reference sources

| Source | Where | License | Identification |
|---|---|---|---|
| Reference project | local copy under `reference/` (untracked, never committed or shipped) | Apache-2.0, copyright held by its authors, no NOTICE file | CHANGELOG top release 1.0.2 plus an Unreleased section; no `.git`; tree fingerprint sha256 `a48f8af83dea40c049b4b5837db782ecc68b8a3197131faef863901ce189cc61` (sha256 of the sorted `sha256sum` list of all 2,169 files, node_modules excluded) |

AGENT_GURU is MIT-licensed. Apache-2.0 code may be included if each copied
file keeps its copyright notice and a statement of changes, and the
Apache-2.0 license text is distributed with it.

## Components

| AGENT_GURU component | Source consulted | Relationship | Copied code | Notice required | Date | Commit |
|---|---|---|---|---|---|---|
| `Agent_Guru/integration/turn_trace.py` (`TurnTraceStore`, `TurnRecord`, `StageTiming`), turn recording in `integration/orchestrator.py` and `main.py` | Reference project: `traces/store.py` and the `Trace`/`TraceStep` types in `core/types.py` | Independent implementation. Idea taken: keep one SQLite row per interaction and one per step, with an FTS5 index over the text. Written for AGENT_GURU's voice turn: different tables, fields, API and connection model (a connection per call through `utils.sqlite.open_sqlite`, no shared connection or lock), owner-only file through `utils.secure_file`. | None. An adapted copy was written first and deleted before any commit; it was never pushed. | No | 2026-10-07 | 98718451 |

No reference-project code is in the repository as of 98718451, so no
`third_party/` license copy is shipped.
