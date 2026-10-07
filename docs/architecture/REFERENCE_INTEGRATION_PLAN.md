# Integration plan

What to build in AGENT_GURU from the comparison, item by item. IDs refer
to `REFERENCE_GAP_MATRIX.md`. Every item is written as AGENT_GURU's own
code (owner's decision, 2026-10-07): the reference is read for design, no
code is copied, and no third-party notice enters the repository. What each
item was informed by is recorded in `THIRD_PARTY_PROVENANCE.md` in the same
commit. The order is in `REFERENCE_INTEGRATION_ROADMAP.md`.

Every item: one feature commit (implementation, tests, configuration
together), its targeted tests verified at that commit, the full suite,
Ruff, Bandit and a startup check before it is pushed.

## Done

### TRC-1, TRC-2: turn records with stage timings (98718451)

- Existing: `PipelineResult` (logged and dropped), in-memory audit log.
- Destination: `Agent_Guru/integration/turn_trace.py`, stage timing in
  `integration/orchestrator.py`, store created in `main.py`.
- Tests: `integration/tests/test_turn_trace_store.py`,
  `integration/tests/test_turn_traces.py` (the latter fail against the
  previous orchestrator).
- Measured: 1.1 ms median per write, about 1.2 KB per turn.
- Security: owner-only file; transcripts already kept in `memory.db`.
- Rollback: `AGENT_GURU_TRACES=0` stops recording; reverting the commit
  removes it; `turns.db` can be deleted at any time.

## P1

### TEL-1: token counts and time to first token in the turn record

- Existing: `llm/providers/ollama_adapter.py` `stream()` drops Ollama's
  last-chunk counts; `complete()` keeps them.
- Design source: the reference project's `engine/ollama.py` reads `prompt_eval_count`,
  `eval_count` and `prompt_eval_duration` from that chunk.
- Change: carry the counts on the final `StreamChunk`, measure time to the
  first chunk in the orchestrator's answer stage, put both in the answer
  stage's `detail`.
- Tests: a fake stream whose last chunk carries counts; a stream without
  them leaves the fields empty, never zero-filled guesses.
- Benchmark: none needed beyond confirming no change to first-audio time.
- Rollback: revert; records simply lack the fields.

### SCH-1: reminders that survive a restart

- Existing: `platform/features/reminders.py` keeps reminders as asyncio
  tasks; a restart before one fires loses it silently.
- Design source: the reference project's `scheduler/store.py` (SQLite rows with next
  run time and run log).
- Change: persist each reminder in AGENT_GURU's data directory, reload on
  startup, and decide what a missed reminder does. Proposed: say it late
  with how late it is, never drop it silently. That rule needs the user's
  agreement before it ships.
- Tests: create, restart (new manager on the same file), fire; missed
  while off; cancel survives restart.
- Dependencies: none new (no cron syntax is needed for spoken reminders).

### SEC-4: an audit log that outlives the process

- Existing: `security/audit/logger.py` signs entries, but the orchestrator
  creates it with the default in-memory store, and a persistent log would
  need the same signing key across runs.
- Design source: the reference project's `security/audit.py` hash chain.
- Change: give the orchestrator's audit logger a file in the data
  directory and a key kept in `security/crypto/key_store.py`; consider
  chaining entries so deletions show.
- Tests: entries written by one process verify in the next; tampering is
  reported.
- Security review: key storage and file permissions.

### MEM-1, MEM-2: durable facts extracted by the model, with provenance

- Existing: `platform/features/user_memory.py`, about 25 regexes, one fact
  per turn, with recorded false captures.
- Design source: the reference project's `memory/extractor.py`, `memory/service.py`,
  `memory/store.py` (background extraction, dedupe, trust tiers,
  quarantine of injection-flagged facts).
- Precondition: measure what a second Ollama call per turn does to the
  next reply on the 4 GB GPU. If it delays the next turn, extraction runs
  only when the assistant has been idle for a while, or not at all.
- Tests: extraction parsing (JSON, bullets, prose), dedupe, quarantine,
  a turn whose reply is unaffected by a slow extractor.
- Security: facts reach the prompt; scanner-flagged text must never be
  recalled (needs SEC-2).
- User decision recorded: the 0.25 memory cutoff stays.

## P2

| ID | Change | Precondition |
|---|---|---|
| EVAL-1, EVAL-2 | an evaluation runner and latency bench in the repo, fed from turn records | TRC-1 data |
| TRC-3, LRN-3 | queries over turn records (slowest stages, unverified actions) and a way to rate a turn | TRC-1 data |
| CLI-1, INT-4 | `python -m Agent_Guru doctor`: Ollama reachable, model present, GPU and VRAM, microphone, data directory | none |
| SEC-2 | prompt-injection scan on text that enters prompts from outside (web results, extracted facts) | MEM-1 or AGT-4 |
| SEC-6 | sensitive-file policy for file operations | none |
| MEM-3, MEM-4 | keyword recall fused with the dense search | an evaluation set of real recall questions |
| TOOL-7 | MCP client behind the policy engine | security review |
| AGT-1, AGT-4 | a tool loop and multi-step research | TRC-1, EVAL-1; the user's roadmap puts planning last |
