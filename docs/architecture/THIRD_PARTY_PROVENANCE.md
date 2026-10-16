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
| `Agent_Guru/reasoning/tools/mcp_client.py`, `mcp_schema.py`, `Agent_Guru/integration/mcp_tools.py` | Reference project: `mcp/client.py`, `mcp/transport.py`, `mcp/loader.py`, `tools/mcp_adapter.py` | Independent implementation. Ideas taken: drain the server's stderr, match replies by id and skip stray lines, close a server whose start failed, isolate servers from each other. Written for AGENT_GURU on asyncio with its policy engine, ActionStatus, audit log and turn record; see `REFERENCE_MCP_COMPARISON.md` for what differs. | None | No | 2026-10-07 | the 4.1 commit |
| `Agent_Guru/integration/tool_loop.py`, tool turns in `integration/orchestrator.py` | Reference project: `agents/native_react.py`, `agents/orchestrator.py`, `agents/loop_guard.py` | Independent implementation. Ideas taken: a bounded loop of model steps and tool calls, refusing a repeated call. Written for AGENT_GURU's voice turn: tools only through MCPToolbox.call, owner confirmation for changes, statuses from ActionStatus, checks on claimed and promised actions. | None | No | 2026-10-11 | the 4.2 commit |
| `Agent_Guru/integration/research.py`, `platform/features/web_fetch.py`, structured search in `platform/features/web_search.py` | Reference project: `agents/deep_research.py`, `agents/research_loop.py`, `tools/web_search.py`, `tools/browser.py` | Independent implementation. Ideas taken: numbered sources the answer must cite, trimming tool results before they reach the model. Written for AGENT_GURU: sources checked against the answer after it is written, private-address checks on every fetch hop with the connection pinned to the checked address, providers that answer through an API. | None | No | 2026-10-11 | the 4.3 commit |
| Scheduled checks and actions in `Agent_Guru/platform/features/reminders.py`, `Agent_Guru/integration/task_tools.py` | Reference project: `agents/scheduler.py`, `agents/monitor_operative.py`, `agents/operative.py`, `tools/approval_store.py` | Independent implementation. Ideas taken: recurring monitoring jobs, keeping an approval apart from the action it approves. Written for AGENT_GURU: the existing reminder manager and store, approvals bound to a fingerprint of tool and arguments, policy asked again at run time, interrupted actions never rerun. | None | No | 2026-10-12 | the 4.4 commit |
| Sensitive-file policy and taint labels in `security/file_policy.py`, `security/taint.py` | Reference project: `security/file_policy.py` (Rust), `security/taint.py` | Independent implementation. Ideas taken: blocking key and credential paths; marking outside text. Written for AGENT_GURU's existing policy, toolbox, turn records and settings. | None | No | 2026-10-16 | phase 5 commits |
| Event bus, telemetry, model catalog, recipes in `integration/events.py`, `llm/telemetry.py`, `platform/hardware/nvml.py`, `llm/model_catalog.py`, `utils/recipes.py` | Reference project: `core/events.py`, `telemetry/itl.py`, `telemetry/energy_*.py`, `intelligence/model_catalog.py`, `recipes/*` | Independent implementation. Ideas taken: publishing events; inter-token percentiles; GPU energy; a model catalog; named configurations. Written for AGENT_GURU's existing policy, toolbox, turn records and settings. | None | No | 2026-10-16 | phase 5 commits |
| Local API, OpenAI-compatible routes, A2A and dashboard in `integration/local_api.py` | Reference project: `server/*`, `a2a/*`, `frontend/` | Independent implementation. Ideas taken: serving the assistant over HTTP; an agent card. Written for AGENT_GURU's existing policy, toolbox, turn records and settings. | None | No | 2026-10-16 | phase 5 commits |
| Channels in `platform/channels/` | Reference project: `channels/*` | Independent implementation. Ideas taken: one interface for many services; inbound bots. Written for AGENT_GURU's existing policy, toolbox, turn records and settings. | None | No | 2026-10-16 | phase 5 commits |
| Connectors and OAuth in `connectors/` | Reference project: `connectors/*`, `connectors/oauth.py` | Independent implementation. Ideas taken: account connectors; PKCE sign-in. Written for AGENT_GURU's existing policy, toolbox, turn records and settings. | None | No | 2026-10-16 | phase 5 commits |
| Engines, fallback and routing in `llm/providers/openai_compatible.py`, `llm/llm_runtime.py`, `llm/model_router/turn_routing.py` | Reference project: `engine/*`, `learning/routing/*` | Independent implementation. Ideas taken: OpenAI-compatible engines; routing by query difficulty and from traces. Written for AGENT_GURU's existing policy, toolbox, turn records and settings. | None | No | 2026-10-16 | phase 5 commits |
| Prompt tuning, training export, skill import and discovery in `self_improvement/`, `reasoning/tools/skills/` | Reference project: `learning/optimize/*`, `learning/training/*`, `skills/importer.py`, `learning/agents/skill_discovery.py` | Independent implementation. Ideas taken: optimising prompts with an evaluation; exporting traces; importing and mining skills. Written for AGENT_GURU's existing policy, toolbox, turn records and settings. | None | No | 2026-10-16 | phase 5 commits |

No reference-project code is in the repository as of the phase 5 commits, so no
`third_party/` license copy is shipped.
