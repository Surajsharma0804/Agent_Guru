# Parity with the reference project

The owner's condition for deleting the reference copy (2026-10-17): every
capability the reference project has is in Agent Guru as its own code, working,
at least as well, or is consciously left out with a reason. This is the record
of that check, area by area, written before the copy was deleted so the
decision can be read later without it.

States:

- **Present**: Agent Guru has it; the evidence column says where and how it
  was checked.
- **Built 2026-10-17**: added for this check, with tests.
- **Partial**: the useful part is present; what is missing is named.
- **Not built**: missing, and why it was not done yet.
- **Rejected**: left out on purpose; the reason is given.
- **Not applicable**: needs hardware or an OS this assistant does not run on
  (Apple), or exists only to serve the reference project's own structure.

## Agents

| Reference | Agent Guru | State | Evidence or reason |
|---|---|---|---|
| ReAct / orchestrator / simple agents, loop guard, tool resolver | `integration/tool_loop.py` | Present | one loop for typed and spoken turns, budgets, repeats refused; `scripts/tool_loop_eval.py` 27/33 on gemma4 |
| Deep research, research loop | `integration/research.py` | Present | sources numbered and answers held to them; `scripts/research_eval.py` 6/6 |
| Morning digest, digest store | `platform/features/briefing.py` | Built 2026-10-17 | local clock (it spoke UTC), today's reminders, calendar and tasks from connected accounts; "good morning" reached the briefing for the first time (it was answered "Sorry, I couldn't do that") |
| Proactive agent, operators, monitor operative, scheduler | reminder manager scheduled checks and actions | Partial | checks repeat a read-only tool and speak; actions run on an approval bound to the exact call. The monitor operative's strategy axes are a benchmark harness, not taken |
| Channel agent | `platform/channels/inbound.py` | Partial | the owner's Telegram chats as typed turns; other services send only |
| Code interpreter, REPL, shell | `integration/code_tools.py` on `reasoning/tools/skills/wsl_sandbox.py` | Built 2026-10-17 | run_python and run_shell in a WSL boundary attacked 18 ways from Python and 5 from a shell (reasoning/tools/tests/test_wsl_sandbox_boundary.py), owner's yes before every run. A persistent REPL is not kept: each run starts empty by design |
| Coding agents that wrap other products (Claude Code, OpenCode, OpenHands, RLM) | none | Not built | they drive external tools and accounts and edit a workspace; the sandbox now exists to host one, but a 4 GB GPU model writing and editing code unattended was not judged useful enough to build blind |
| Hybrid local plus cloud agents (Minions, Archon, Conductor, SkillOrchestra, ToolOrchestra, mini SWE agent) | model routing with cloud only for hard questions (`llm/model_router`) | Not built | research protocols that need cloud model keys; nothing here can measure them without the owner's keys |

## Tools

| Reference | Agent Guru | State | Evidence or reason |
|---|---|---|---|
| Browser (Playwright), accessibility tree | `integration/browser_tools.py` | Built 2026-10-17 | numbered elements, owner's yes naming the element and site, fresh profile, private-address guard; tests against real Edge or Chrome |
| Web search, HTTP GET of pages | `platform/features/web_search.py`, `web_fetch.py` | Present, built further | news provider added 2026-10-17 for questions about now (it answered "not found"); every page hop checked for private addresses |
| General HTTP requests (POST and others) | none | Rejected | a model-driven POST tool can change things anywhere on the web; page reading is GET only through the guard |
| File read and write, apply_patch | `reasoning/tools/system/file_operations.py`, sensitive-file policy | Partial | file operations exist behind the policy; patch application to source files is not offered |
| Git tool | none | Not built | belongs to a coding agent (above) |
| Database queries, knowledge SQL, chunk scanning | none | Rejected | the documents and memory searches answer questions about the owner's data; raw SQL against them adds a path around those checks |
| PDF text | `platform/features/documents.py` (.pdf) | Present | passages searchable after `documents add` |
| Memory and profile management, retrieval | `memory/`, `platform/features/user_memory.py`, `memory` command, search_memory tool | Present | facts quarantined when flagged |
| Text to speech | Kokoro, pyttsx3 fallback | Present | Kokoro files pinned and verified |
| Calculator, think, LLM sub-call | calculator tool; routing and fallback engine | Present | think is not needed with thinking off |
| Image generation (cloud), audio transcription (cloud) | none | Not built | cloud only; needs the owner's keys to verify |
| MCP client and server, adapter | `integration/mcp_tools.py` | Present | owner-allowed tools with declared risk only |

## Channels

| Reference | Agent Guru | State |
|---|---|---|
| Telegram, Slack, email, Discord, Signal, SMS, Matrix, Zulip, Mastodon, LINE, Viber, Messenger, Reddit, IRC, Twitch, Teams, Google Chat, Mattermost, Rocket.Chat, Feishu, webhooks | `platform/channels` | Present (no tests existed for these until 2026-10-17; the new channels have them) |
| X (Twitter) | `XChannel` | Built 2026-10-17: posts and direct messages (the reference only posted); OAuth 1.0a checked against X's documented example |
| XMPP | `XmppChannel` | Built 2026-10-17 without a library; tried against a real Prosody server |
| Nostr | `NostrChannel`, own BIP340 | Built 2026-10-17; all 19 BIP340 vectors; encrypted DMs (NIP-04) |
| Web chat | the local API's chat page | Present |
| WhatsApp (Cloud API, unofficial web protocol) | WhatsApp Desktop with read-back and delivery status | Present, stronger for the owner's own account |
| iMessage, BlueBubbles, Sendblue | none | Not applicable (Apple) |
| Inbound bots for every channel | Telegram inbound | Partial: other services send only |

## Connectors

| Reference | Agent Guru | State |
|---|---|---|
| Gmail, Outlook, IMAP, Google Calendar, contacts, Drive, Tasks, Notion, Obsidian, Dropbox, GitHub notifications, Oura, Strava, Spotify, news and Hacker News, OAuth | `connectors/` | Present; accounts not tried live (no credentials here) |
| Weather | briefing and weather tools (wttr.in) | Present |
| Slack as a data source | none | Not built: Slack sends only |
| Granola meeting notes | none | Not built: needs the owner's Granola account |
| Apple Calendar, Contacts, Health, Music, Notes, iMessage | none | Not applicable (Apple) |
| Sync engine, chunker, embeddings, hybrid search, store | `platform/features/documents.py`, memory search | Partial: Agent Guru queries accounts when asked instead of copying them into a store |

## Engines and speech

| Reference | Agent Guru | State |
|---|---|---|
| Ollama, cloud (OpenAI, Anthropic, Gemini), LiteLLM, multi-engine | `llm/`, OpenAI-compatible adapter, fallback engine | Present; cloud only with AGENT_GURU_ALLOW_CLOUD |
| vLLM, SGLang, llama.cpp, NVIDIA NIM | the OpenAI-compatible adapter (`engine:<model>`) | Present (they serve the same API) |
| gemma.cpp, Nexa | none | Not built: no server API on this machine and not installed |
| Apple Foundation Models, MLX | none | Not applicable (Apple) |
| Model catalog, hardware detection, recommendation | `llm/model_catalog.py`, `init` | Built 2026-10-17 (recommendation); catalog present |
| faster-whisper, Kokoro | speech engine | Present |
| Deepgram, Cartesia, OpenAI speech | none | Not built: cloud keys needed to verify |

## Security

| Reference | Agent Guru | State |
|---|---|---|
| Injection scanner, credential stripping, file policy, taint, audit log with signing, SSRF guard, rate limiting, capabilities | `security/`, `llm/security.py` and `memory/security.py` (redaction), `platform/network/rate_limiter.py`, `policy/` | Present; the classifier goes further (off by default) |
| Subprocess sandbox, Docker or WASM runner, mount security | WSL boundary | Built 2026-10-17 |
| Encrypted credential vault | `security/vault.py` (DPAPI) | Built 2026-10-17 |
| Privacy scan | `doctor` privacy checks | Present |

## Learning, evaluation, telemetry

| Reference | Agent Guru | State |
|---|---|---|
| Traces, analyzer, feedback | turn records, `learn`, spoken "that was wrong" | Present |
| Evaluation runner and benchmarks | `eval`, `bench`, eval scripts | Partial: real turns and the owner's rated turns, not the reference's third-party benchmark datasets |
| Prompt optimisation (DSPy, GEPA, ACE, agent evolver, spec search) | `self_improvement/prompt_tuning.py` with an evaluation gate | Partial: rules and demonstrations behind a gate; the reflective search optimisers need many model runs, not done without Ollama running |
| SFT, GRPO, LoRA training | dataset export; A100 plan | Partial: training needs a larger GPU |
| Routing (heuristic, learned) | `llm/model_router` | Present |
| Skill discovery, skill import and sources | `reasoning/tools/skills` | Present; Hermes and OpenClaw catalogs are not wired, git, zip and folder are |
| Telemetry: tokens, TTFT, inter-token latency, NVIDIA energy and GPU | turn records, NVML | Present |
| AMD, Apple and RAPL energy | none | Not applicable on this hardware |
| Usage analytics sent off the device | none | Rejected: the owner's data stays local |

## Platform and command line

| Reference | Agent Guru | State |
|---|---|---|
| OpenAI-compatible server, A2A, API keys, dashboard, uploads | `integration/local_api.py`, `api` command | Present except uploads (documents are added from the command line) |
| Daemon, gateway, start, stop, status, service files | `utils/service.py`, `service` command | Built 2026-10-17: clean stop through the assistant's own shutdown, start at log-in |
| init, quickstart, doctor | `init`, `doctor` | Built 2026-10-17 (init) |
| self-update | `update` | Built 2026-10-17: fast-forward only |
| vault, connect, channels, memory, model, config, ask, chat, bench, eval, feedback, skills, tasks, MCP add | matching commands | Present |
| Tunnel (public URL to the local server) | none | Rejected: it would put an assistant that controls this computer on the public internet; Telegram inbound gives remote use with no open port |
| Host (download and serve a model) | Ollama, `model` command | Present |
| Workflow engine, compose, recipes, templates, registries, event bus | `utils/recipes.py`, `integration/events.py` | Present where used; the workflow engine is unused in both projects |
| Terminal dashboard, GUI | the local API dashboard page | Partial: a web page instead of a terminal UI |
| Crypto mining | none | Rejected: it would compete with the voice loop for the GPU |

## What is still open

Each of these needs something this machine does not have today: the owner's
cloud keys (cloud speech, image generation, hybrid agents), the owner's
accounts (Granola, Slack as a source), Ollama running for many model runs
(reflective prompt optimisers, the two-tool chaining limit of the tool loop),
or a decision that it is wanted (a coding agent that edits files, inbound
messages on channels other than Telegram). None of them needs the reference
copy to be built later: the design notes above are enough.
