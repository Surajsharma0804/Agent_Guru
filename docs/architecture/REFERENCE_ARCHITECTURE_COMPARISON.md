# Architecture comparison: AGENT_GURU and the reference project

How the two systems are put together, measured from code, not from their
READMEs. The per-capability detail is in `REFERENCE_GAP_MATRIX.md`.

## Shape

| | AGENT_GURU | Reference project |
|---|---|---|
| What it is | an always-on voice assistant for one person's computer | a local-first assistant backend: CLI, HTTP server, desktop app, many channels |
| Entry point | `main.py`: wake word, then one `IntegrationOrchestrator.run_pipeline` per spoken command | a Click CLI, a FastAPI server command, a Tauri desktop app |
| Composition | `main.py` `_load_*` functions construct each subsystem and pass them to the orchestrator | `SystemBuilder` reads TOML and wires one system object; decorator registries for engines, agents, tools, memory backends |
| Unit of work | a voice turn with fixed stages | a query handled by an engine call or an agent loop |
| Model use | one local model through Ollama (gemma4 on a 4 GB GPU) | many engines (Ollama, vLLM, SGLang, llama.cpp, MLX, cloud, LiteLLM), routed per query |
| Native code | none on the live path | 18 Rust crates; several Python modules have no Python fallback |
| Size | 705 source modules, 340 test files | 683 source modules, 698 test files |

## AGENT_GURU's live turn

Measured: imports traced from `main.py`, modules loaded at startup recorded
with `python -X importtime`, and the orchestrator's calls read.

1. Wake word (`speech/wake_word_manager.py`), command capture until the
   speaker stops (`speech/audio/command_capture.py`).
2. STT: Whisper.
3. Pending message draft, then user-taught reaction rules.
4. Memory: `MemoryManager.search`, dense cosine with fixed cutoffs.
5. Intent: rule-based recognizer (`platform/intent_recognizer.py`).
6. Policy: `PolicyEngine`, fail closed on timeout.
7. Action: `_dispatch_action` to `OSController`, results verified where
   the outcome can be observed (app open/close, WhatsApp delivery).
8. Answer: `LLMRuntime` to Ollama, streamed sentence by sentence into
   Kokoro TTS.
9. Memory write, audit event, and (since 98718451) a turn record.

`ReasoningEngine`, `AgentOrchestrator` and the self-improvement engine are
constructed at startup but do no per-turn work. 397 of 705 modules cannot
be reached from `main.py` at all.

## The reference project's request path

A query goes to `QueryOrchestrator`, which either calls an engine directly
or runs an agent (`NativeReActAgent`, `OrchestratorAgent` and others) that
loops over tool calls through `ToolExecutor`. Around that sit the trace
collector, telemetry wrappers on the engine, security guardrails on the
engine and tools, memory context injection, and an event bus that feeds
traces, telemetry and analytics.

## Where each is stronger

AGENT_GURU: the voice loop (wake word, end-of-speech capture, streamed
speech, filler audio), OS control with verified results, vision, emotion
and personality, and a policy engine with spoken confirmation of
destructive actions.

The reference project: observability (traces, telemetry, energy), evaluation and
benchmarking, multi-engine inference, agent loops, connectors and
channels, persistent scheduling, and learning from traces.

## Consequences for integration

- AGENT_GURU's turn has fixed stages, so per-stage records fit it
  directly; the reference project's agent-step model does not need to be imported.
- AGENT_GURU has no event bus. Adding one only to carry traces would be a
  second mechanism beside direct calls; the turn record is written
  directly by the orchestrator instead.
- Pieces that depend on the reference project's Rust extension cannot be taken as
  Python alone; AGENT_GURU writes its own where it needs them.
- One model on a 4 GB GPU makes routing between models and a second LLM
  call per turn expensive. Anything that adds a model call per turn has to
  be measured against the next reply's latency first.
