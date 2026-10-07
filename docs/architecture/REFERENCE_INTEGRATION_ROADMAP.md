# Integration roadmap

The owner's goal (2026-10-07): AGENT_GURU gets every reference-project
capability that makes it better, written as its own code, and each one
should do more than the reference does. "Better" is claimed only where it
was measured.

Each batch is one or more feature commits with tests, the full suite,
Ruff, Bandit, a startup check and a real run before anything is pushed.
IDs refer to `REFERENCE_GAP_MATRIX.md`.

## Phase 1: see what the assistant does

| Batch | Items | Beyond the reference | State |
|---|---|---|---|
| 1.1 | TRC-1, TRC-2 turn records with stage timings | records the verified action status and the voice stages (speech, first audio), which the reference has no notion of | done, 98718451 |
| 1.2 | TEL-1, TEL-4 tokens, time to first token and decode speed in the answer stage | one store instead of two | next |
| 1.3 | TRC-3, LRN-3 queries over turn records, rating a turn by voice | spoken "that was wrong" marks the turn | planned |
| 1.4 | EVAL-1, EVAL-2 evaluation runner and latency bench fed by real turns | benchmarks built from the owner's own turns, not public datasets only | planned |
| 1.5 | CLI-1, CLI-2, INT-4, SEC-11 `doctor` and a command line: Ollama, model, GPU and VRAM, microphone, speaker, data folder, privacy checks | checks the audio devices a voice assistant depends on | planned |

## Phase 2: things that must survive a restart

| Batch | Items | Condition | State |
|---|---|---|---|
| 2.1 | SEC-4 audit log on disk, tamper-evident | signing key kept in the key store | planned |
| 2.2 | SCH-1 reminders and schedules in SQLite | owner's rule for reminders due while the app was off | waiting on owner |
| 2.3 | ARCH-3, ARCH-1 file-based configuration | keep environment variables working | planned |

## Phase 3: memory

| Batch | Items | Condition | State |
|---|---|---|---|
| 3.1 | SEC-2 injection scan for text entering prompts from outside | none | planned |
| 3.2 | MEM-1, MEM-2 durable facts extracted by the model, with provenance and quarantine | GPU cost of the extra model call measured; run when idle if it delays replies | planned |
| 3.3 | MEM-3, MEM-4 keyword and meaning search fused | evaluation set from 1.4; the 0.25 cutoff stays | planned |
| 3.4 | MEM-5 document ingestion into a knowledge store | 3.3 | planned |

## Phase 4: doing more

| Batch | Items | Condition | State |
|---|---|---|---|
| 4.1 | TOOL-7 MCP client behind the policy engine | security review | planned |
| 4.2 | AGT-1, AGT-2, TRC-4 tool loop with loop guard, recorded in the turn | 1.4 | planned |
| 4.3 | AGT-4, TOOL-6 multi-step research with sources, browser actions | 4.2, 3.1 | planned |
| 4.4 | SCH-2, AGT-3, ARCH-2 scheduled and monitoring agents with approval, on an internal event bus | 2.2, 4.2 | planned |
| 4.5 | SBX-1, AGT-5 sandbox, then code-running agents | policy rule and spoken confirmation | planned |

## Phase 5: reach

| Batch | Items | Condition | State |
|---|---|---|---|
| 5.1 | CON-1, CON-2 connectors (mail, calendar, contacts, files) with OAuth | owner's accounts and consent | planned |
| 5.2 | CHN-1, CHN-2 more channels (Telegram, Slack, email) beside verified WhatsApp | inbound commands pass the same policy | planned |
| 5.3 | API-1, TOOL-8 local HTTP API, then agent-to-agent | authentication, off by default | planned |
| 5.4 | INT-1, INT-2, INT-3, INT-5, INT-6, AGT-6 more engines, model routing, local plus cloud combinations | hardware that fits a second model; cloud use only with owner's keys and consent | planned |
| 5.5 | LRN-1, LRN-2, SKL-2, SKL-3 learning from turns (prompt tuning, fine-tuning) | enough turn records; the A100 plan | planned |
| 5.6 | DSK-1, REC-1, WFL-1, TEL-2, TEL-3, SEC-6, SEC-7 remaining items | as listed in the matrix | planned |

Outside this roadmap and pending from earlier work: the production policy
still refuses app open and close although both are implemented and
verified.
