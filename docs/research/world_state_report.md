# Agent Guru — World-State Research & Improvement Report

**Date:** 2026-09-13
**Scope of this report:** the companion/emotion, long-term-memory, and control-system (messaging + file-to-presentation) work completed in this session, following the first-round audit at `docs/audit/claude_companion_and_control_audit_2026-09-13.md`.
**Honesty note up front:** the directive this report responds to asked for research and benchmarking across roughly forty engineering areas (LLM orchestration, RAG, voice, vision, avatar, deployment, security, and more) plus a full competitor comparison against Siri, Gemini, Claude Desktop, and ChatGPT Desktop. That full scope is not something one session can do with integrity — genuine research, genuine benchmarking, and genuine verification for forty subsystems is weeks of work, not one sitting. This report documents, honestly and completely, the research that *was* done and the changes it produced. The "Out of scope this round" section at the end lists everything that still needs the same treatment, so nothing is quietly dropped.

---

## 1. Technologies researched

| Area | Question being asked | Why it mattered for this round's changes |
|---|---|---|
| Agent long-term memory architectures | Does a full vector-DB/graph memory stack outperform a simpler embedding+SQL approach in practice? | Decided whether to wire the existing but unused ChromaDB stack (`reasoning/memory/`) into the pipeline, or make the already-wired `MemoryManager` genuinely functional instead. |
| Sentence embedding models | Is `all-MiniLM-L6-v2` (already chosen elsewhere in this codebase) still a reasonable choice for local, offline embedding? | `memory/memory_manager.py` previously used a 26-dimension letter-frequency stub in place of real embeddings — the fix needed a real, already-adopted-elsewhere model rather than introducing a new one. |
| WhatsApp/Telegram automation risk | What happens to an account/session that automates sending on WhatsApp Web via browser control? | Decided against building automatic "press send" browser automation for WhatsApp (see Rejected Improvements). |
| Gamma's presentation-generation API | What is the exact, current request contract for generating a deck via Gamma instead of locally? | Needed for the optional cloud path in `platform/features/presentation.py`, gated behind a user-supplied API key. |
| python-pptx / python-docx / pypdf | Are these still the standard, maintained libraries for offline `.pptx` generation and `.docx`/`.pdf` text extraction in Python? | Confirmed via installed versions (python-pptx 1.0.2, current) and used for real, tested `.pptx` generation with no cloud dependency. |

## 2. Sources consulted

- [Benchmarking AI Agent Memory: Is a Filesystem All You Need? — Letta](https://www.letta.com/blog/benchmarking-ai-agent-memory/) — LoCoMo benchmark results comparing filesystem/search-based memory to graph-based memory (Mem0).
- [sentence-transformers/all-MiniLM-L6-v2 — Hugging Face](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) — model card: 384-dim output, 22.7M parameters, sentence/short-paragraph encoder.
- [WhatsApp Bot Banned in 2026? — Achiya Automation](https://achiya-automation.com/en/blog/whatsapp-spam-detection-2026/) — WhatsApp's own published enforcement figure and an honest statement that unofficial-tool ban-rate data is not systematically published.
- [Gamma Developer Docs — Create Generation](https://developers.gamma.app/generations/create-generation) — exact endpoint, headers, and request body fields for Gamma's public generation API (fetched directly, not guessed).
- Direct reading of this repository's own source (`memory/memory_manager.py`, `reasoning/memory/*`, `reasoning/tools/*`, `integration/orchestrator.py`, `llm/companion_prompts.py`, `platform/controllers/messaging_controller.py`, `platform/features/web_search.py`) — the ground truth for what actually runs today versus what merely exists in the tree.

## 3. Engineering patterns discovered (in this codebase, worth following elsewhere)

- **Soft-dependency pattern.** Throughout `platform/features/*` and `memory/memory_manager.py`: a capability lazily imports its optional library inside a `try/except ImportError`, logs a debug/warning hint with the exact `pip install` command, and degrades gracefully rather than crashing the whole subsystem. Followed for the new `presentation.py` module (python-docx/pypdf/python-pptx) and reused rather than reinvented.
- **Duck-typed subsystem calls in the orchestrator.** `integration/orchestrator.py` probes for `getattr(subsystem, "method_a", None) or getattr(subsystem, "method_b", None)`, checks `inspect.iscoroutinefunction`, and falls back to `run_in_executor` for sync implementations. This is why `_store_turn_in_memory()` (added this round) was written the same way — it fits how every other stage already talks to its subsystems.
- **A well-built, entirely orphaned subsystem.** `reasoning/memory/` (ChromaDB + real `EmbeddingGenerator` + dedup pipeline) and `reasoning/tools/` (a complete `Tool`/`ToolRegistry` plugin framework with sandboxing) are both high-quality and both **never imported by `integration/orchestrator.py`** (confirmed by grep — zero references). This is a recurring shape in the repository: capability exists, wiring does not. Worth checking for elsewhere before assuming a feature is "done" because the file exists.

## 4. Candidate improvements considered

1. Fully migrate `MemoryManager` onto the existing ChromaDB/`Intent`-based RAG stack in `reasoning/memory/`.
2. Make `MemoryManager`'s existing SQLite-backed store use real embeddings instead of its stub, and persist them.
3. Wire the orphaned `reasoning/tools/external/messaging.py` tool framework (currently hardcoded fake-success placeholders) into the live pipeline as-is.
4. Add a real, local contact-resolution layer to `platform/controllers/messaging_controller.py` and use it in `send_message()`.
5. Build fully automated WhatsApp Web "type and press send" browser automation.
6. Add local, offline file-to-presentation generation (`platform/features/presentation.py`).
7. Fix the emotion-tier keyword bug and dead crisis-tier code in `llm/companion_prompts.py` (already fully diagnosed in the first-round audit).
8. Fix the duplicate chat-history write and the hardcoded `"neutral"` emotion label found in `integration/orchestrator.py` while wiring memory storage.

## 5. Accepted improvements

- **#2 (real embeddings in `MemoryManager`), not #1.** Real `sentence-transformers` embeddings (via the existing `reasoning/memory/embedding.py::EmbeddingGenerator`, not a new dependency) now back the already-wired `MemoryManager`, with embeddings persisted to a new SQLite column and an automatic `ALTER TABLE` migration for existing databases. Verified end-to-end: store → SQLite persistence → restart → warm-cache reload → legacy-DB migration, all against a real `aiosqlite` connection in an isolated test.
- **#4 (local contact resolution), not #3.** `messaging_controller.py` gained a small on-device JSON contacts store (`add_contact`/`remove_contact`/`list_contacts`/`resolve_contact`), and `send_message()` now resolves a display name through it before dispatching. This also fixed a real, previously silent bug: sending to a non-phone-number WhatsApp/email "contact" used to build a URL with no recipient and still report success; it now correctly reports failure and explains why. Verified with 16 passing checks including the exact before/after behavior change.
- **#6 (local presentation generation).** `platform/features/presentation.py`: offline-first `.pptx` generation from `.txt`/`.md`/`.docx`/`.pdf`/other text sources, with a dependency-free heuristic outline builder that's markdown-header-aware, an optional LLM-assisted outline upgrade reusing the orchestrator's existing `CompletionRequest`/`Message` pattern, and an explicitly opt-in Gamma API path. Verified against real generated `.docx` (via python-docx) and `.pdf` (via reportlab) sources, producing real, re-opened `.pptx` files — 20 passing checks total.
- **#7 and #8**, from the first-round audit: fixed in `llm/companion_prompts.py` and `integration/orchestrator.py` respectively, verified via a real `EmotionDetector`/`EmpathyAdapter` integration test and `py_compile` + careful call-site tracing.

## 6. Rejected improvements

- **#1 — full ChromaDB/RAG migration.** Rejected *for this round*, not permanently.
- **#3 — wiring the orphaned tool framework as-is.** Rejected as-is; its messaging tools are hardcoded fake-success placeholders (`"note": "This is a placeholder. Real implementation would use WhatsApp API."`), so wiring them in unmodified would have made the fake-success problem *worse*, not better.
- **#5 — automated WhatsApp "press send" browser automation.** Rejected.

## 7. Reasons for rejection

- **#1 (full RAG migration):** Letta's own published LoCoMo results (see Sources) show a simpler filesystem/search-based memory approach at 74.0% versus a graph-based approach's 68.5% on their top-performing variant — concrete evidence that more architectural complexity in memory retrieval is not automatically better. Migrating to the full ChromaDB/`Intent`-based stack is also the highest-integration-risk change available (it touches storage format, retrieval call sites, and the `MemoryLLMIntegration`/`Intent` contract) at a time when the orchestrator's full pipeline cannot be executed end-to-end from this session (`device_bash` is down — see the audit report). Shipping the smaller, fully-verified fix now and leaving the bigger migration as a deliberate, documented future phase is the honest trade-off given what could actually be tested this round.
- **#3 (orphaned tool framework as-is):** the framework's `SendWhatsAppTool`/`SendSMSTool`/etc. always return `{"success": True, ...}` with a `"note"` admitting they're placeholders. Wiring a fake-success tool into the live action-dispatch path would mean the agent could now confidently tell the user "sent!" for messages that never left the process — strictly worse than the current state where these tools are simply unreachable.
- **#5 (automated WhatsApp send):** WhatsApp's own Help Center states it bans over 8 million accounts per month for abusive/automated behavior (see Sources); independent write-ups of unofficial automation tools describe the ban risk as real but *not* reliably quantifiable — the honest research finding here is "meaningfully risky, un-bounded severity" rather than a specific percentage. Given that Agent Guru is meant to be the user's own persistent WhatsApp account, not a disposable bot number, the downside of a real account ban clearly outweighs the convenience of not having to click "send" once. The accepted alternative — opening a correctly pre-filled, correctly-addressed compose window (once contact resolution is fixed) and letting the user press send themselves — keeps the capability useful without that risk.

## 8. Expected impact

- **Memory:** interaction recall/search now uses real semantic similarity (384-dim sentence embeddings) instead of a 26-dimension letter-frequency stub — meaningfully better relevance for `MemoryManager.search()`, with embeddings computed once and persisted (not recomputed on every app restart, which would have been a real startup-latency regression for users with large histories).
- **Emotion/tone:** the empathy-adaptation result (tone/pacing/vocabulary) is now actually computed from the real transcript and injected into the system prompt as a "TONE NOTE," and a real, non-dead crisis-resource mention is included for genuinely distressed turns — previously this logic existed but was called with an empty string and its output discarded.
- **Follow-up conversation:** every completed turn is now actually persisted to `MemoryManager` (previously computed, never stored) and the chat-history double-write bug is fixed, so the 24-message in-RAM window and the persistent memory no longer drift out of sync with each other.
- **Messaging:** a WhatsApp/email send to a saved contact by name now actually reaches that contact instead of silently opening an unaddressed compose window while reporting success — this is a correctness fix, not just a feature addition.
- **File → presentation:** a capability that did not exist at all (there was no code path from "here's a file" to "here's a deck" anywhere in the repository) now exists, is offline-first, and is independently verified — not yet reachable by voice command (see below).

## 9. Benchmark comparisons

Full competitor benchmarking (Siri, Gemini, Claude Desktop, ChatGPT Desktop) as the original directive requested was **not performed this round** — it requires running those products against a shared task set, which is out of scope for a codebase-audit session. The one benchmark comparison genuinely available and used is the Letta LoCoMo figures cited above (74.0% vs. 68.5%), which informed the memory-architecture decision in Section 7. Claiming a broader competitive benchmark without having actually run one would be exactly the "manufactured success" the project's own mission statement prohibits, so none is presented here.

## 10. Risks

- **Verification tier differs by file.** `llm/companion_prompts.py`, `memory/memory_manager.py`, and `platform/features/presentation.py`/`platform/controllers/messaging_controller.py` were verified by constructing isolated integration tests with real dependencies (real `aiosqlite`, real `EmotionDetector`/`EmpathyAdapter`, real `python-pptx`/`python-docx`/`pypdf`/`reportlab`) and actually executing them. `integration/orchestrator.py`'s new wiring (`_store_turn_in_memory`, the emotion/tone system-prompt additions) was verified by `py_compile` plus careful reading and call-site tracing — the full 8-stage pipeline could not be executed end-to-end because `device_bash` (the only way to run this repository's real test suite on the user's machine) is currently broken by a Windows update issue. This should be re-verified with the real test suite the moment that's possible.
- **`presentation.py` is not wired into the live pipeline.** It is a complete, independently-tested capability, but a voice command like "make a PPT from this file" will not yet reach it — see the module's own docstring for the specific, documented wiring plan, left undone deliberately rather than as an unverified edit to the ~2800-line orchestrator dispatch tables.
- **Contact resolution changes `send_message()`'s return value for previously "successful" but non-functional calls.** Any code relying on the old (incorrect) `True` return for an unresolvable WhatsApp/email contact will now see `False`. This is treated as a bug fix, not a breaking change, but it is a real behavior change worth flagging.
- **Gamma API path is unauthenticated by default and untested against the live API** (no API key was available in this sandbox) — the request shape is confirmed from Gamma's own documentation but has not been exercised against the real endpoint.

## 11. Compatibility assessment

- All changes are additive or in-place fixes to existing files — no new parallel files, no `_v2`/`_new` modules, per the project's explicit rule.
- New dependencies (`python-pptx`, `python-docx`, `pypdf`) were added to `requirements.txt` as clearly-scoped, optional-by-nature additions; `python-pptx` is required only for the new presentation module's render path, and the other two only if the source document is `.docx`/`.pdf`.
- No existing public method signatures were removed; `MessagingController.__init__` gained an optional `contacts_path_override` parameter (default `None`, fully backward compatible); `MessagingController.send_message()`'s behavior change is the one documented above.
- Cross-platform: the new contacts store reuses the exact OS-directory-resolution pattern already in `memory/memory_manager.py` (`%LOCALAPPDATA%` on Windows, `$XDG_DATA_HOME`/`~/.local/share` elsewhere), so it needs no new platform-specific code.

## 12. Out of scope this round (explicit backlog, not silently dropped)

Voice pipeline (STT/TTS/wake-word) tuning and research; vision/OCR subsystem audit; avatar subsystem audit; deployment hardening across Windows/macOS/Linux packaging; a full security audit (auth, sandboxing, secrets, supply chain) beyond what the first-round audit already covered; wiring `reasoning/memory/`'s ChromaDB stack as a considered future phase (Section 6); wiring `presentation.py` into the live intent/action-dispatch pipeline; a genuine, executed competitor benchmark against Siri/Gemini/Claude Desktop/ChatGPT Desktop; and the full 20-section `/AUDIT_REPORT_MASTER.md` deliverable. These are listed here, not silently abandoned, so a future session can pick any one of them up as its own properly-scoped piece of work.
