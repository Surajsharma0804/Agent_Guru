# Reference project gap matrix

Capability-by-capability comparison of AGENT_GURU against the reference project, made to decide what AGENT_GURU should reuse, adapt,
build or leave alone. AGENT_GURU is the product; the reference project is a source of
code and design. Where this file disagrees with the code, the code wins:
re-check before acting on a row.

## What was compared

| | AGENT_GURU | Reference project |
|---|---|---|
| Snapshot | commit `30b0a327` (2026-10-06) | local copy under `reference/` (untracked, never committed, no `.git`); CHANGELOG top release `1.0.2` plus an Unreleased section; tree fingerprint sha256 `a48f8af83dea40c0...` over 2,169 files (node_modules excluded) |
| License | Apache-2.0 (MIT until 2026-10-17) | Apache-2.0, copyright held by its authors, no NOTICE file |
| Python source modules (tests excluded) | 705 | 683 (plus 18 Rust crates) |
| Test files | 340 | 698 |

The reference copy has no upstream commit hash. Any later re-comparison
must first check the fingerprint (method: sha256 of the sorted
`sha256sum` list of every file, node_modules excluded) to know whether the
reference changed.

## How "exists" was decided

A capability counts as present in AGENT_GURU only if the voice assistant
can use it. Three levels were measured, not inferred from file names:

- **live**: on the path of a voice turn. `main.py` builds
  `IntegrationOrchestrator`, and a turn runs STT (Whisper), the intent
  recognizer (`platform/intent_recognizer.py`), memory search
  (`MemoryManager.search`), the policy engine, the action
  (`OSController` through `_dispatch_action`), the answer (`LLMRuntime` to
  Ollama, streamed into Kokoro TTS) and an audit event.
- **loaded**: imported when the app starts (272 AGENT_GURU modules,
  measured with `python -X importtime main.py` until "Agent Guru is
  running") but not called by a turn. `ReasoningEngine`,
  `AgentOrchestrator` (its `execute()` returns `None` and hands the turn
  back) and the self-improvement engine are constructed and never asked to
  do anything per turn.
- **unwired**: not reachable from `main.py` through any import, lazy ones
  included (397 of 705 modules). Code that cannot run in production is
  listed, but it is not counted as AGENT_GURU having the capability.

## Inspection depth

- **D** (detailed): the implementation was read on both sides.
  TRC-1..3, TEL-1, TEL-4, MEM-1..4, SCH-1, SEC-4, INT-7, INT-9, AGT-2,
  TOOL-4 and the Rust dependency of each reuse candidate.
- **S** (structural): module, class and function inventory with
  docstrings and the live/loaded/unwired measurement above, plus targeted
  reads. Rows marked S can be wrong in detail; read the code before acting
  on one.

## Reference-project modules that cannot be copied alone

These Python modules call the compiled compiled Rust extension through
`_rust_bridge.get_rust_module()`, which states "there is no Python
fallback" (SSRF is the one module with a fallback). Reusing them means
adding a Rust build to AGENT_GURU or porting the Rust logic:

`agents/loop_guard.py`, `security/capabilities.py`, `security/file_policy.py`,
`security/injection_scanner.py`, `security/rate_limiter.py`,
`security/scanner.py`, `tools/calculator.py`, `tools/file_read.py`,
`tools/file_write.py`, `tools/git_tool.py`, `tools/http_request.py`,
`tools/shell_exec.py`, `tools/think.py`, `tools/storage/bm25.py`,
`tools/storage/sqlite.py`, `cli/_bg_state.py`.

## Matrix

Status values: EXISTS_STRONGER (AGENT_GURU better), EXISTS_EQUIVALENT,
EXISTS_PARTIAL, EXISTS_WEAKER, MISSING, NOT_APPLICABLE.

Action values: KEEP_GURU, REUSE_REFERENCE (copy with its license notice),
ADAPT_REFERENCE (copy and change, with its notice), IMPROVE_GURU (change
the existing AGENT_GURU code), NEW_GURU_IMPLEMENTATION (written for
AGENT_GURU; design ideas only), REJECT, LEGALLY_BLOCKED, and DEFER: worth
having, but blocked on a prerequisite named in the Dependencies column,
usually an evaluation set or a measurement that does not exist yet.

Decided by the owner (2026-10-07): every capability taken from the
reference is written as AGENT_GURU's own code, so no reference code and no
third-party notice enters the repository. REUSE_REFERENCE and
ADAPT_REFERENCE are therefore not used. The goal is every capability that
makes AGENT_GURU better, built to do more than the reference does, and
each one measured before it is called better.

Priority: P0 = gap on the live path with a measured cost and a low-risk
fix; P1 = real gap that needs a measurement or a decision first; P2 =
worth doing after its prerequisite; P3 = not now.

| ID | Capability | Reference location | Reference approach | AGENT_GURU location | AGENT_GURU approach | Status | Better | Reuse possible? | Strategy | Priority | Dependencies | Risk | Performance impact | Security impact | Provenance |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| TRC-1 | Persistent interaction trace (one record per turn) | `traces/store.py`, `core/types.py` (Trace, TraceStep); done in 98718451 as `integration/turn_trace.py` | SQLite + FTS5, one row per trace, one per step, append-only, thread-locked | none on the live path; `PipelineResult` is logged by `main.py` and dropped; audit events go to an in-memory DB; `platform/integration/tracing.py` is unwired W3C span tracing | nothing persisted per turn | MISSING | Reference project | design only; the store was written for AGENT_GURU, nothing copied | NEW_GURU_IMPLEMENTATION | P0 | TRC-2 | low: new file, written after the reply | one SQLite write per turn off the event loop | stores transcripts and replies locally, as `memory.db` already does | independent; design informed by `traces/store.py` (see THIRD_PARTY_PROVENANCE.md) |
| TRC-2 | Per-stage latency of a turn | `TraceStep.duration_seconds`; done in 98718451 | each step timed | `integration/orchestrator.py` `_run_turn` | only wake-to-first-speech, on two shortcut paths | MISSING | Reference project | design only | IMPROVE_GURU | P0 | none | low | a few `perf_counter` calls | none | design from `core/types.py` |
| TRC-3 | Trace analysis (per-route and per-tool stats) | `traces/analyzer.py` | read-only queries over the store | none | none | MISSING | Reference project | yes | IMPROVE_GURU | P2 | TRC-1 data | low | none | none | n/a |
| TRC-4 | Trace collector wrapping agents | `traces/collector.py` | wraps `BaseAgent.run` | no agent loop on the live path | n/a | NOT_APPLICABLE | n/a | no | IMPROVE_GURU | P2 | AGT-1: when a tool loop exists, its steps are recorded as stages of the turn record | n/a | n/a | n/a | n/a |
| TEL-1 | Token counts and time to first token for streamed answers | `engine/ollama.py`, `telemetry/instrumented_engine.py` | reads `prompt_eval_count`, `eval_count`, `prompt_eval_duration` from Ollama's last chunk | `llm/providers/ollama_adapter.py` `stream()` | the last chunk's counts are discarded; only the rarely used `complete()` keeps them | EXISTS_WEAKER | Reference project | method only | NEW_GURU_IMPLEMENTATION | P1 | TRC-1 | low | none | none | method from `engine/ollama.py` |
| TEL-2 | Inter-token latency percentiles | `telemetry/itl.py` | per-token timestamps | none | none | MISSING | Reference project | yes | DEFER | P3 | TEL-1 | low | per-token timestamps | none | n/a |
| TEL-3 | GPU and energy measurement | `telemetry/energy_*.py`, `gpu_monitor.py` | NVML/RAPL/AMD/Apple counters | `platform/hardware/monitor.py` (unwired) | GPU info only | MISSING | Reference project | yes | DEFER | P3 | none | medium (NVML polling) | background poller | none | n/a |
| TEL-4 | Separate telemetry store and aggregator | `telemetry/store.py`, `aggregator.py` | 60-column table per inference | none | none | MISSING | n/a | yes | IMPROVE_GURU | P1 | TEL-1: the same metrics go into the answer stage of the turn record, one store | a second store would duplicate TRC-1 | n/a | n/a | n/a |
| MEM-1 | Durable fact extraction from conversation | `memory/extractor.py`, `memory/service.py` | small local model distils facts on a background thread, dedupes, caps, never raises | `platform/features/user_memory.py` `extract_user_fact` (live) | about 25 regexes, one fact per turn; its docstring records false captures ("I am trying to lose weight" stored as the name) | EXISTS_WEAKER | Reference project | yes, pure Python | NEW_GURU_IMPLEMENTATION | P1 | measure GPU contention on the 4 GB card; EVAL-1 | medium: a second Ollama call per turn can delay the next reply | one extra LLM call per turn | facts reach the prompt; needs MEM-2 | n/a |
| MEM-2 | Fact provenance and quarantine | `memory/store.py` (`TRUST_*`) | facts flagged by the injection scanner are stored but never recalled | none | every stored fact is used | EXISTS_WEAKER | Reference project | yes (scanner is Rust) | NEW_GURU_IMPLEMENTATION | P1 | MEM-1, SEC-2 | low | none | closes a prompt-injection path into memory | n/a |
| MEM-3 | Conversation memory retrieval | `tools/storage/dense.py`, `sqlite.py`, `bm25.py` | dense, FTS5 and BM25 backends | `memory/memory_manager.py` `search` (live) | dense cosine, cutoff 0.25, redundancy 0.70, measured and fixed by the user's decision | EXISTS_PARTIAL | equal for meaning; the reference project adds keyword recall | dense yes; BM25/SQLite need Rust | DEFER | P2 | EVAL-1 | medium: changes what reaches the prompt | depends | none | n/a |
| MEM-4 | Rank fusion of keyword and semantic results | `tools/storage/hybrid.py` `reciprocal_rank_fusion` | RRF, k=60 | none | none | MISSING | Reference project | yes, pure Python | DEFER | P2 | MEM-3, EVAL-1 | medium | small | none | n/a |
| MEM-5 | Document ingestion, chunking, knowledge store | `connectors/pipeline.py`, `chunker.py`, `store.py`, `retriever.py` | dedupe, type-aware chunks, FTS5, rerank | `reasoning/knowledge/synthesizer.py` (loaded) | answers over stored memories, no document ingestion | MISSING | Reference project | partly | DEFER | P3 | MEM-3 | medium | ingestion is offline | private documents | n/a |
| MEM-6 | Knowledge graph | `tools/storage/knowledge_graph.py` | entity-relation SQLite | `memory/knowledge_graph.py` (unwired) | entity-relation | EXISTS_EQUIVALENT | equal (both unused) | n/a | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| MEM-7 | Deduplication | `tools/storage/dense.py` `dedupe_chunks` | n-gram Jaccard with union-find | `MemoryManager` REDUNDANT_SIMILARITY (live), `memory/deduplication.py` (unwired) | embedding redundancy filter | EXISTS_EQUIVALENT | equal for the live path | n/a | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| MEM-8 | Session compression | `sessions/compression.py` | rule-based, model summary, tiered | `MemoryManager.compress_history`, `llm/context_manager.py` (live) | history compression | EXISTS_EQUIVALENT | equal | n/a | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| INT-1 | Inference engine abstraction | `engine/*` (Ollama, vLLM, SGLang, llama.cpp, MLX, cloud, LiteLLM, multi) | one ABC, many backends | `llm/llm_runtime.py`, `llm/providers/ollama_adapter.py` (live) | Ollama only on the live path | EXISTS_PARTIAL | Reference project broader; AGENT_GURU fits the measured 4 GB setup | yes | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| INT-2 | Engine discovery and health probe | `engine/_discovery.py` | probe running engines | `reasoning/llm/ollama_server.py` (loaded), `llm/failover_router.py` (lazy) | Ollama health and failover | EXISTS_EQUIVALENT | equal for Ollama | n/a | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| INT-3 | Model catalog with sizes and VRAM | `intelligence/model_catalog.py` | built-in ModelSpec entries | `llm/model_router/registry.py` (unwired) | metadata models | EXISTS_WEAKER | Reference project | yes | DEFER | P3 | INT-4 | low | none | none | n/a |
| INT-4 | Hardware detection and model recommendation | `core/config.py` `detect_hardware`, `recommend_model` | GPU/VRAM detection picks engine and model | `reasoning/llm/generation.py` (env), `core/device_manager.py` | settings from environment | EXISTS_PARTIAL | Reference project | yes | NEW_GURU_IMPLEMENTATION | P2 | CLI-1 | low | startup only | none | n/a |
| INT-5 | Model routing by query complexity | `learning/routing/*` | heuristic and learned routers | `reasoning/llm/router.py`, `llm/model_router/*` (unwired) | one model in use | EXISTS_WEAKER | Reference project | yes | DEFER | P3 | a second model that fits beside gemma4 on 4 GB (swap measured at 17-19 s) | high | swaps cost seconds | none | n/a |
| INT-6 | Learned router from traces | `learning/routing/learned_router.py` | query class to model from trace outcomes | `llm/model_router/learning_engine.py` (unwired) | none live | MISSING | Reference project | yes | DEFER | P3 | TRC-1, INT-5 | high | n/a | none | n/a |
| INT-7 | Prompt construction | `prompt/builder.py` | sectioned system prompt | orchestrator `_build_llm_request` (live) | cache-aware layout: first token 1.40 to 0.88 s median, measured | EXISTS_STRONGER | AGENT_GURU | n/a | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| INT-8 | Context length checks | `engine/_base.py` | token estimate, context-error detection | `reasoning/llm/generation.py` `context_fits`, `llm/token_counter.py` | per-call fit check | EXISTS_EQUIVALENT | equal | n/a | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| INT-9 | Streaming answers | `engine/*` stream | token stream | `_speak_llm_reply`, `speech/tts/streaming.py` (live) | spoken sentence by sentence as written; first audio 8.87 to 6.17 s, measured | EXISTS_STRONGER | AGENT_GURU | n/a | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| AGT-1 | Tool-calling agent loop (ReAct, orchestrator) | `agents/native_react.py`, `agents/orchestrator.py` | multi-turn tool loop | `reasoning/execution/multi_step_executor.py` (loaded, not per turn) | one rule-matched action per turn | MISSING (live) | Reference project | yes | DEFER | P2 | TRC-1, EVAL-1; user roadmap puts planner/agents last | high | multi-call turns | tool authority grows | n/a |
| AGT-2 | Degenerate tool-loop guard | `agents/loop_guard.py` (Rust) | repeat and ping-pong detection | `agents/loop_detector.py`, `verifier/loop_detector.py` | loop detection | EXISTS_EQUIVALENT | equal; no live loop yet | Rust only | KEEP_GURU | P3 | AGT-1 | n/a | n/a | n/a | n/a |
| AGT-3 | Persistent managed agents | `agents/manager.py`, `executor.py`, `errors.py`, `scheduler.py` | lifecycle, ticks, retry classes | `agent_orchestration/*`, `agents/background/*` (unwired) | none live | MISSING (live) | Reference project | yes | DEFER | P3 | AGT-1, SCH-1 | high | background work | autonomous actions | n/a |
| AGT-4 | Deep research with citations | `agents/deep_research.py`, `research_loop.py` | multi-hop retrieval, cited report | `platform/features/web_search.py` (live) | one search, summarized | EXISTS_WEAKER | Reference project | partly | DEFER | P2 | AGT-1, MEM-5 | medium | many calls | untrusted web text in prompts (SEC-2) | n/a |
| AGT-5 | Code-execution agents (CodeAct, OpenHands, RLM) | `agents/native_openhands.py`, `rlm.py`, `opencode.py` | agent writes and runs code | none | none | MISSING | n/a | yes | DEFER | P3 | SBX-1 sandbox and a policy rule that gates running code, spoken confirmation | high for a voice assistant with OS control | n/a | arbitrary code | n/a |
| AGT-6 | Hybrid local-cloud paradigms | `agents/hybrid/*` | research ports (Minions, Archon, Conductor, ToolOrchestra) | none | none | MISSING | n/a | yes | DEFER | P3 | cloud keys | n/a | n/a | data leaves the device | n/a |
| TOOL-1 | Tool registry and bounded executor | `tools/_stubs.py` `ToolExecutor` | per-call timeout runner | `reasoning/tools/registry.py`, `selector.py` (loaded); live path `_dispatch_action` | rule dispatch to controllers | EXISTS_EQUIVALENT | equal for the live path | n/a | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| TOOL-2 | Destructive-action gating | `security/capabilities.py`, `tools/approval_store.py` | RBAC grants, approval queue | `platform/features/confirmation.py`, policy engine, speaker-verified restricted mode (live) | spoken confirmation, fail-closed policy | EXISTS_STRONGER | AGENT_GURU for voice | n/a | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| TOOL-3 | Safe calculator | `tools/calculator.py` (Rust) | AST evaluation | `reasoning/tools/knowledge/information.py` CalculateTool | AST evaluation | EXISTS_EQUIVALENT | equal | Rust only | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| TOOL-4 | Shell execution limits | `tools/shell_exec.py` (Rust), `security/subprocess_sandbox.py` | allowlisted env, process-tree kill | `reasoning/tools/system/_command.py`, `platform/subprocess_utils.py` (live) | bounded subprocesses, argument validation; no free-form shell on the voice path | EXISTS_EQUIVALENT | equal | partly | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| TOOL-5 | HTTP request tool with SSRF guard | `tools/http_request.py` (Rust), `security/ssrf.py` | private-IP and metadata blocking | none (no arbitrary fetch on the live path) | n/a | NOT_APPLICABLE | n/a | yes | KEEP_GURU | P3 | AGT-1 | n/a | n/a | n/a | n/a |
| TOOL-6 | Browser automation | `tools/browser.py` | Playwright actions | `platform/browser_manager.py` (loaded) | opens URLs | EXISTS_PARTIAL | Reference project | yes | DEFER | P3 | AGT-1 | medium | heavy dependency | web actions | n/a |
| TOOL-7 | MCP client and server | `mcp/*` | JSON-RPC, stdio and HTTP transports | none | none | MISSING | Reference project | yes | DEFER | P2 | security review of external tool servers | medium | none | external tools gain reach | n/a |
| TOOL-8 | Agent-to-agent protocol | `a2a/*` | Google A2A | none | none | MISSING | n/a | yes | DEFER | P3 | API-1 server with authentication; off by default | n/a | n/a | network exposure | n/a |
| SKL-1 | Skill system | `skills/*` | manifests, deps, executor, trust tiers | `reasoning/tools/skills/*` (loaded) and `skills/*` (unwired): two implementations inside AGENT_GURU | manifests, sandbox, permissions | EXISTS_EQUIVALENT | equal | n/a | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| SKL-2 | External skill catalogs | `skills/sources/*`, `importer.py` | Hermes, OpenClaw, GitHub | `reasoning/tools/skills/installer.py` | local install | EXISTS_PARTIAL | Reference project | yes | DEFER | P3 | SEC-8 | medium | none | third-party code | n/a |
| SKL-3 | Skill discovery from traces | `learning/agents/skill_discovery.py` | mines tool sequences | none | none | MISSING | Reference project | yes | DEFER | P3 | TRC-1, AGT-1 | low | offline | none | n/a |
| SCH-1 | Persistent scheduling | `scheduler/scheduler.py`, `store.py` | cron/interval/once in SQLite, polling thread | `platform/features/reminders.py` (live) | asyncio tasks in memory: a reminder is lost if the app restarts before it fires | EXISTS_WEAKER | Reference project | yes, pure Python (cron needs `croniter`) | NEW_GURU_IMPLEMENTATION | P1 | decide what to do with reminders missed while the app was off | low | negligible | none | n/a |
| SCH-2 | Operators and proactive agents | `operators/*`, `agents/proactive_agent.py`, `tools/approval_store.py` | scheduled autonomous agents with approvals | `proactive/engine.py` (unwired), `reasoning/learning/goal_engine.py` (loaded) | none live | MISSING (live) | Reference project | yes | DEFER | P3 | SCH-1, AGT-3 | high | background work | autonomous actions | n/a |
| SCH-3 | Morning digest | `agents/morning_digest.py`, `tools/digest_collect.py` | multi-source briefing | `platform/features/briefing.py` (lazy) | briefing on request | EXISTS_EQUIVALENT | equal in scope used | n/a | KEEP_GURU | P3 | CON-1 | n/a | n/a | n/a | n/a |
| CON-1 | Data connectors | `connectors/*` (Gmail, Calendar, Contacts, Drive, Notion, Slack, Apple apps, RSS, weather) | sync into the knowledge store | `reasoning/tools/external/*` (loaded) | email, calendar, maps, news tools | EXISTS_PARTIAL | Reference project broader | yes | DEFER | P3 | CON-2, MEM-5 | medium | sync work | private data, OAuth tokens | n/a |
| CON-2 | OAuth helpers | `connectors/oauth.py`, `google_auth.py` | token storage and refresh | none | none | MISSING | Reference project | yes | DEFER | P3 | CON-1 | medium | none | token handling | n/a |
| CHN-1 | Messaging channels | `channels/*` (Telegram, Slack, Discord, WhatsApp Cloud API and Baileys, email, SMS, many more) | one ABC, API adapters | `platform/controllers/messaging_controller.py` (live) | WhatsApp Desktop with read-back before send and verified delivery status | EXISTS_PARTIAL | AGENT_GURU for verified WhatsApp; the reference project broader | yes | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| CHN-2 | Inbound message bots and webhooks | `channels/*_daemon.py`, `server/webhook_routes.py` | receive and answer | none | none | MISSING | Reference project | yes | DEFER | P3 | API-1 | medium | background service | inbound commands from networks | n/a |
| SBX-1 | Isolated execution | `sandbox/runner.py`, `wasm_runner.py`, `mount_security.py` | Docker/WASM with mount allowlist | `reasoning/tools/skills/sandbox.py` (loaded) | subprocess limits | EXISTS_PARTIAL | Reference project | yes | DEFER | P3 | AGT-5 | medium | container start-up | stronger isolation | n/a |
| SEC-1 | Authorization | `security/capabilities.py` (Rust) | per-tool RBAC | `policy/*` (live), restricted mode, confirmation | ABAC policy engine, fail-closed timeout | EXISTS_STRONGER | AGENT_GURU | n/a | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| SEC-2 | Prompt-injection scanning | `security/injection_scanner.py` (Rust) | pattern scan with severity | `llm/security.py` `detect_prompt_injection` (unwired) | pattern scan, not used | EXISTS_WEAKER | Reference project | Rust only | DEFER | P2 | needed once MEM-1 or AGT-4 put untrusted text in prompts | low | small | closes an injection path | n/a |
| SEC-3 | Secret and PII redaction | `security/scanner.py` (Rust), `credential_stripper.py` | scanners on outputs | `security/redaction.py` (live), audit detail scrubbing | redaction | EXISTS_EQUIVALENT | equal | partly | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| SEC-4 | Persistent tamper-evident audit log | `security/audit.py` | SQLite with Merkle hash chain | `security/audit/logger.py` (live) | Ed25519-signed entries, but the orchestrator creates it with the default `:memory:` store: every turn's audit event is lost when the app exits, and a persistent log would need a stable key | EXISTS_WEAKER | Reference project in practice | design | IMPROVE_GURU | P1 | key persistence via `security/crypto/key_store.py` | low | one write per turn | restores an audit trail | n/a |
| SEC-5 | SSRF protection | `security/ssrf.py` | private-IP and metadata blocking, Python fallback | `platform/permissions/network_checker.py` (unwired) | URL checks | NOT_APPLICABLE | n/a (no arbitrary fetch live) | yes | KEEP_GURU | P3 | TOOL-5 | n/a | n/a | n/a | n/a |
| SEC-6 | Sensitive-file policy | `security/file_policy.py` (Rust) | blocks key and credential paths | `platform/permissions/path_checker.py` (unwired), file-ops controller (live) | path checks in file operations | EXISTS_PARTIAL | Reference project | Rust only | DEFER | P2 | none | low | none | protects secrets | n/a |
| SEC-7 | Taint tracking | `security/taint.py` | information-flow labels | none | none | MISSING | Reference project | yes | DEFER | P3 | AGT-1 | low | small | data-flow control | n/a |
| SEC-8 | Signed manifests | `security/signing.py` | Ed25519 | `security/crypto/identity.py`, `deployment/crypto_verifier.py` | Ed25519 | EXISTS_EQUIVALENT | equal | n/a | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| SEC-9 | Rate limiting | `security/rate_limiter.py` (Rust) | token bucket | `platform/network/rate_limiter.py` (unwired), proactive token bucket | token bucket | EXISTS_EQUIVALENT | equal | Rust only | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| SEC-10 | Secure file creation | `security/file_utils.py` | owner-only files | `utils/secure_file.py` (live) | owner-only files, icacls on Windows | EXISTS_EQUIVALENT | equal | n/a | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| SEC-11 | Local privacy scan | `cli/scan_cmd.py` | audits the environment | none | none | MISSING | Reference project | yes | DEFER | P3 | CLI-1 | low | on demand | none | n/a |
| SEC-12 | Credential vault | `cli/vault_cmd.py` | encrypted store | `security/crypto/key_store.py` (loaded) | AES-256-GCM, PBKDF2 | EXISTS_EQUIVALENT | equal | n/a | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| EVAL-1 | Evaluation framework | `evals/*` (datasets, scorers, runner, LLM judge, trackers) | reproducible suites | `vision/eval_set.py`, `self_improvement/benchmarks/*` (synthetic), scratch scripts outside the repo | ad hoc measurement | EXISTS_WEAKER | Reference project | yes | NEW_GURU_IMPLEMENTATION | P2 | TRC-1 | low | offline | none | n/a |
| EVAL-2 | Latency and throughput benchmarks | `bench/*` | engine benches with stats | none in the repo | scratch scripts | EXISTS_WEAKER | Reference project | yes | NEW_GURU_IMPLEMENTATION | P2 | EVAL-1 | low | offline | none | n/a |
| LRN-1 | Prompt and agent optimization | `learning/agents/*`, `learning/optimize/*`, `learning/spec_search/*` | DSPy, GEPA, ACE, spec search with gates and rollback | `self_improvement/prompt_evolution.py` (loaded, not per turn) | prompt versions | EXISTS_WEAKER | Reference project | yes | DEFER | P3 | TRC-1, EVAL-1 | high | offline | changes model behaviour | n/a |
| LRN-2 | Fine-tuning from traces | `learning/intelligence/*`, `learning/training/*` | SFT, GRPO, LoRA | `training/seed_utils.py`, vision training | none for the LLM | MISSING | Reference project | yes | DEFER | P3 | TRC-1 data | high | GPU time | none | n/a |
| LRN-3 | Feedback on interactions | `TraceStore.update_feedback`, `cli/feedback_cmd.py` | score a trace | `reasoning/learning/feedback_store.py` (loaded) | intent feedback | EXISTS_PARTIAL | Reference project | yes | IMPROVE_GURU | P2 | TRC-1 | low | none | none | n/a |
| API-1 | OpenAI-compatible HTTP server | `server/*` | FastAPI, auth middleware, SSE | `reasoning/api/app.py` (unwired) | FastAPI app, unused | EXISTS_WEAKER | Reference project | yes | DEFER | P3 | none | medium | a server process | network exposure | n/a |
| API-2 | Programmatic SDK | `sdk.py` | one facade class | `sdk/*` | skill SDK client | EXISTS_PARTIAL | different purpose | n/a | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| CLI-1 | Installation diagnostics | `cli/doctor_cmd.py` | Python, config, engines, models, optional deps | none (startup log only) | none | MISSING | Reference project | yes | NEW_GURU_IMPLEMENTATION | P2 | none | low | on demand | none | n/a |
| CLI-2 | Full CLI | `cli/*` (init, model, config, bench, eval, memory, agents) | Click commands | `main.py` only | none | MISSING | Reference project | partly | DEFER | P3 | CLI-1 | low | none | none | n/a |
| DSK-1 | Desktop app and web UI | `desktop/` (Tauri), `frontend/` | GUI | `avatar/*` (headless renderer live) | avatar state only | NOT_APPLICABLE | different product shape | n/a | DEFER | P3 | none | n/a | n/a | n/a | n/a |
| ARCH-1 | Plugin registries | `core/registry.py` | decorator registries | constructor wiring in `main.py` | fixed wiring | EXISTS_PARTIAL | depends on need | yes | DEFER | P3 | none | n/a | n/a | n/a | n/a |
| ARCH-2 | Event bus | `core/events.py` | thread-safe pub/sub | `vision/bus.py` (unwired) | none live | MISSING | Reference project | yes | DEFER | P3 | a consumer that needs it | low | none | none | n/a |
| ARCH-3 | File-based configuration | `core/config.py`, `core/paths.py` | TOML with env-aware paths | `llm/config_loader.py`, environment variables | environment | EXISTS_PARTIAL | Reference project | yes | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| ARCH-4 | System composition | `system/builder.py`, `core.py` | fluent builder | `main.py` `_load_*`, concurrent subsystem start | direct construction | EXISTS_EQUIVALENT | equal | n/a | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| WFL-1 | DAG workflows | `workflow/*` | topological execution | `goal_manager/dependency_resolver.py` (unwired), `agents/executor.py` | dependency ordering | EXISTS_EQUIVALENT | equal (both unused) | n/a | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| REC-1 | Recipes and templates | `recipes/*`, `templates/*` | TOML compositions | none | none | MISSING | n/a | yes | DEFER | P3 | ARCH-1 and ARCH-3 configuration | n/a | n/a | n/a | n/a |
| ANL-1 | External usage analytics | `analytics/*` | PostHog events | `deployment/monitoring.py` (unwired) | none sent | MISSING | n/a | yes | REJECT | P3 | n/a | sends usage data off the device; AGENT_GURU is local-first | n/a | data leaves the device | n/a |
| MIN-1 | Crypto mining | `mining/*` | Pearl mining sidecars | none | none | MISSING | n/a | yes | REJECT | P3 | n/a | competes for the 4 GB GPU; unrelated to the product | n/a | n/a | n/a |
| DEP-1 | Deployment and services | `deploy/`, `daemon/service.py`, `cli/self_update_cmd.py` | Docker, systemd/launchd units, self-update | `deployment/*` (loaded via OnboardingManager) | installers, update manager | EXISTS_EQUIVALENT | equal | n/a | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| SPC-1 | Speech to text | `speech/faster_whisper.py`, cloud backends | file transcription | `speech/stt/whisper_stt.py`, `speech/audio/command_capture.py` (live) | CUDA-prepared Whisper, Silero end-of-speech capture, language detection | EXISTS_STRONGER | AGENT_GURU | n/a | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| SPC-2 | Text to speech | `speech/kokoro_tts.py`, cloud backends | whole-reply synthesis | `speech/tts/*`, `speech/filler_response.py` (live) | Kokoro ONNX streamed by sentence, cached filler | EXISTS_STRONGER | AGENT_GURU | n/a | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| SPC-3 | Wake word, speaker verification | none | none | `speech/wake_word_manager.py`, `speech/biometric/*` (live) | always-on wake, restricted mode for unknown speakers | EXISTS_STRONGER | AGENT_GURU | n/a | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| VIS-1 | Vision | `cli/_screen.py` (capture only) | screenshot to a vision model | `vision/*` (live) | face recognition, VQA, OCR, screen reading | EXISTS_STRONGER | AGENT_GURU | n/a | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| OS-1 | OS control with verified results | none | none | `platform/*` (live) | app open/close judged by what then runs, graceful close, verified WhatsApp delivery | EXISTS_STRONGER | AGENT_GURU | n/a | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| EMO-1 | Emotion, personality, avatar | none | none | `emotion/*`, `avatar/*` (live) | two personalities, emotion-aware tone | EXISTS_STRONGER | AGENT_GURU | n/a | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |
| TST-1 | Test infrastructure | `tests/` (698 files) | unit, integration, eval tests | `*/tests/` (340 files, 5,979 tests passing) | unit, integration, property tests | EXISTS_EQUIVALENT | equal | n/a | KEEP_GURU | P3 | none | n/a | n/a | n/a | n/a |

## Totals

88 capabilities compared, counted from the rows above; "MISSING (live)"
rows count as MISSING.

| Status | Count |
|---|---|
| EXISTS_STRONGER | 10 |
| EXISTS_EQUIVALENT | 20 |
| EXISTS_PARTIAL | 13 |
| EXISTS_WEAKER | 13 |
| MISSING | 28 |
| NOT_APPLICABLE | 4 |

| Action | Count |
|---|---|
| KEEP_GURU | 36 |
| DEFER | 35 |
| NEW_GURU_IMPLEMENTATION | 9 |
| IMPROVE_GURU | 6 |
| REJECT | 2 |

P0: TRC-1, TRC-2 (done, 98718451). P1: TEL-1, MEM-1, MEM-2, SCH-1, SEC-4.
`REFERENCE_INTEGRATION_PLAN.md` covers each P0 and P1 row.

## Findings about AGENT_GURU itself

Measured while building this matrix; none is fixed by it.

- 397 of 705 AGENT_GURU modules cannot be reached from `main.py`.
- Two skill systems exist side by side (`reasoning/tools/skills/` loaded,
  `skills/` unwired).
- The per-turn audit log is in memory only (SEC-4).
- `memory.db` inherits its folder's permissions (SYSTEM and
  Administrators can read it); the new `turns.db` is owner-only.
- With the production policy, a plain question is recorded with action
  status `denied` (the conversation intent is refused) although the
  answer is spoken. Seen in the first real turn records.
- Reminders do not survive a restart (SCH-1).
