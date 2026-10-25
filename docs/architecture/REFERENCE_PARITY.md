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
| Channel agent | `platform/channels/inbound.py` | Built 2026-10-18 | Telegram, Slack, Discord, Matrix and email, each by polling with an allow list; strangers get no reply; messages from before the start are skipped. Email first trusted the From header and a forged mail was taken as the owner; fixed in the release audit (7a6be1a4): only mail the owner's server authenticated (DMARC, or DKIM of the From domain) counts. Not tried against real accounts |
| Code interpreter, REPL, shell | `integration/code_tools.py` on `reasoning/tools/skills/wsl_sandbox.py` | Built 2026-10-17 | run_python and run_shell in a WSL boundary attacked 18 ways from Python and 5 from a shell (reasoning/tools/tests/test_wsl_sandbox_boundary.py), owner's yes before every run. A persistent REPL is not kept: each run starts empty by design |
| Coding agents (Claude Code, OpenCode, OpenHands, RLM) | `integration/coding_tools.py`, `utils/patching.py` | Built 2026-10-18 | read a project, try a unified diff on a sandbox copy and run its tests there, apply it to the real files after the owner's yes with backups; tried end to end in the real sandbox. A Windows junction in a project let it read and overwrite a file outside; fixed in the release audit (d869db88): links and paths resolving outside the project are skipped and refused. External coding products are not wrapped: the loop runs on Agent Guru's own tools |
| Hybrid local plus cloud agents (Minions and the like) | `integration/hybrid.py` (read_long_document) | Built 2026-10-18 | the local model reads every passage, the cloud (when allowed) or the local model plans and answers from the findings; the document never leaves the machine; gemma4 found a clause among 59 in 59 s. The other research protocols (Archon, Conductor, SkillOrchestra, ToolOrchestra) are not built: they need cloud keys to measure |

## Tools

| Reference | Agent Guru | State | Evidence or reason |
|---|---|---|---|
| Browser (Playwright), accessibility tree | `integration/browser_tools.py`, the `browser` extra | Built 2026-10-17 | numbered elements, owner's yes naming the element and site, fresh profile, private-address guard; tests against real Edge or Chrome. The guard first checked only the first request and a redirect to localhost loaded the local page; fixed in the release audit (a6e51fd4): every hop is checked. Playwright was pinned only in the lock; declared as the browser extra on 2026-10-18 |
| Web search, HTTP GET of pages | `platform/features/web_search.py`, `web_fetch.py` | Present, built further | news provider added 2026-10-17 for questions about now (it answered "not found"); every page hop checked for private addresses |
| General HTTP requests (POST and others) | none | Rejected | a model-driven POST tool can change things anywhere on the web; page reading is GET only through the guard |
| File read and write, apply_patch | file operations behind the policy; `utils/patching.py` | Present | diffs apply all or nothing, through the coding tools |
| Git tool | project_git (status, diff, log) | Built 2026-10-18 | read-only |
| Database queries, knowledge SQL, chunk scanning | none | Rejected | the documents and memory searches answer questions about the owner's data; raw SQL against them adds a path around those checks |
| PDF text | `platform/features/documents.py` (.pdf) | Present | passages searchable after `documents add` |
| Memory and profile management, retrieval | `memory/`, `platform/features/user_memory.py`, `memory` command, search_memory tool | Present | facts quarantined when flagged |
| Text to speech | Kokoro, pyttsx3 fallback | Present | Kokoro files pinned and verified |
| Calculator, think, LLM sub-call | calculator tool; routing and fallback engine | Present | think is not needed with thinking off |
| Image generation, audio transcription | `integration/media_tools.py` | Built 2026-10-18 | transcription with the local Whisper (tried live); image generation through OpenAI only with cloud allowed and a key (request shape tested, not tried live: no key) |
| MCP client and server, adapter | `integration/mcp_tools.py` | Present | owner-allowed tools with declared risk only |

## Channels

| Reference | Agent Guru | State |
|---|---|---|
| Telegram, Slack, email, Discord, Signal, SMS, Matrix, Zulip, Mastodon, LINE, Viber, Messenger, Reddit, IRC, Twitch, Teams, Google Chat, Mattermost, Rocket.Chat, Feishu, webhooks | `platform/channels` | Present; tested 2026-10-26 against stand-in services (`test_channel_sends.py`): request shape, refusals, network failures. That found two defects, both fixed: the webhook signature was over different bytes than were sent, and IRC reported a refused message (401, 404, 474) as sent. Not tried against real accounts |
| X (Twitter) | `XChannel` | Built 2026-10-17: posts and direct messages (the reference only posted); OAuth 1.0a checked against X's documented example |
| XMPP | `XmppChannel` | Built 2026-10-17 without a library; tried against a real Prosody server |
| Nostr | `NostrChannel`, own BIP340, the `nostr` extra | Built 2026-10-17; all 19 BIP340 vectors; encrypted DMs (NIP-04). websockets was not declared, so a normal install could not publish; declared as the nostr extra on 2026-10-18. Not tried against a public relay |
| Web chat | the local API's chat page | Present |
| WhatsApp (Cloud API, unofficial web protocol) | WhatsApp Desktop with read-back and delivery status | Present, stronger for the owner's own account |
| iMessage, BlueBubbles, Sendblue | none | Not applicable (Apple) |
| Inbound bots for every channel | `platform/channels/inbound.py` | Built 2026-10-18: Telegram, Slack, Discord, Matrix, email |

## Connectors

| Reference | Agent Guru | State |
|---|---|---|
| Gmail, Outlook, IMAP, Google Calendar, contacts, Drive, Tasks, Notion, Obsidian, Dropbox, GitHub notifications, Oura, Strava, Spotify, news and Hacker News, OAuth | `connectors/` | Present; tested 2026-10-26 against stand-in services, a scripted IMAP server and the real OAuth listener (`test_account_connectors.py`). Fixed on the way: Outlook event times read and written in the wrong zone, Oura and Spotify refusals read as data, wrong Spotify advice, IMAP searches for non-ASCII names, and a refresh failure that did not say to sign in again. Accounts not tried live (no credentials here) |
| Weather | briefing and weather tools (wttr.in) | Present |
| Slack as a data source | slack_search | Built 2026-10-18 (user token; not tried live) |
| Granola meeting notes | meetings_search, meeting_read | Built 2026-10-18 (Granola public API; not tried live) |
| Apple Calendar, Contacts, Health, Music, Notes, iMessage | none | Not applicable (Apple) |
| Sync engine, chunker, embeddings, hybrid search, store | `platform/features/documents.py`, memory search | Partial: Agent Guru queries accounts when asked instead of copying them into a store |

## Engines and speech

| Reference | Agent Guru | State |
|---|---|---|
| Ollama, cloud (OpenAI, Anthropic, Gemini), LiteLLM, multi-engine | `llm/`, OpenAI-compatible adapter, fallback engine | Present; cloud only with AGENT_GURU_ALLOW_CLOUD |
| vLLM, SGLang, llama.cpp, NVIDIA NIM | the OpenAI-compatible adapter (`engine:<model>`) | Present (they serve the same API) |
| gemma.cpp, Nexa | none | Not applicable: neither serves an API on this machine; a server that speaks the OpenAI API is reached through `engine:` |
| Apple Foundation Models, MLX | none | Not applicable (Apple) |
| Model catalog, hardware detection, recommendation | `llm/model_catalog.py`, `init` | Built 2026-10-17 (recommendation); catalog present |
| faster-whisper, Kokoro | speech engine | Present |
| Deepgram, Cartesia, OpenAI speech | `speech/cloud_speech.py` | Built 2026-10-18: cloud voices and recognition before the local ones, only when allowed and chosen; request shapes tested, not tried live (no keys) |

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
| Evaluation runner and benchmarks | `eval`, `bench`, eval scripts | Partial by choice: real turns and the owner's rated turns; the reference's third-party benchmark datasets compare research agents, not a personal assistant |
| Prompt optimisation (DSPy, GEPA, ACE, agent evolver, spec search) | `self_improvement/prompt_tuning.py` | Built 2026-10-18 | `learn tune --strategy evolve`: rounds of reflective rewriting over a Pareto front, adopted only through the gate; also rules and demonstrations |
| SFT, GRPO, LoRA training | dataset export; A100 plan | Partial: training needs a larger GPU. Since 2026-10-26 the export keeps only answers the owner rated right (`--include-unrated` adds unrated successes without refusals) |
| Routing (heuristic, learned) | `llm/model_router` | Present |
| Skill discovery, skill import and sources | `reasoning/tools/skills`, `instruction_skills.py` | Built 2026-10-18 | Hermes and OpenClaw catalogs listed and learned live (Markdown only, scripts never copied), offered as use_skill |
| Telemetry: tokens, TTFT, inter-token latency, NVIDIA energy and GPU | turn records, NVML | Present |
| AMD, Apple and RAPL energy | none | Not applicable on this hardware |
| Usage analytics sent off the device | none | Rejected: the owner's data stays local |

## Platform and command line

| Reference | Agent Guru | State |
|---|---|---|
| OpenAI-compatible server, A2A, API keys, dashboard, uploads | `integration/local_api.py`, `api` command | Present; uploads built 2026-10-18 (POST /v1/documents) |
| Daemon, gateway, start, stop, status, service files | `utils/service.py`, `service` command | Built 2026-10-17: clean stop through the assistant's own shutdown, start at log-in |
| init, quickstart, doctor | `init`, `doctor` | Built 2026-10-17 (init) |
| self-update | `update` | Built 2026-10-17: fast-forward only |
| vault, connect, channels, memory, model, config, ask, chat, bench, eval, feedback, skills, tasks, MCP add | matching commands | Present |
| Tunnel (public URL to the local server) | none | Rejected: it would put an assistant that controls this computer on the public internet; Telegram inbound gives remote use with no open port |
| Host (download and serve a model) | Ollama, `model` command | Present |
| Workflow engine, compose, recipes, templates, registries, event bus | `utils/recipes.py`, `integration/events.py` | Present where used; the workflow engine is unused in both projects |
| Terminal dashboard, GUI | `dashboard` command, the local API page | Built 2026-10-18 (terminal view) |
| Crypto mining | none | Rejected: it would compete with the voice loop for the GPU |

## What is still open

Built on 2026-10-18 and tested here, but not tried against the real
service, because no keys or accounts are on this machine: cloud voices and
recognition (OpenAI, Cartesia, Deepgram), image generation, Slack search,
Granola notes, and inbound Slack, Discord, Matrix and email. Their request
formats follow each provider's documentation and are pinned by tests;
the first real use with the owner's keys is their live check.

The two-tool chaining limit of the tool loop is fixed: over four runs of
`scripts/tool_loop_eval.py` on gemma4 every answer was right (11 of 11),
where both chains were wrong before.

Left out on purpose, with the reasons above: a public tunnel, a model-driven
POST tool, raw SQL over the owner's data, off-device analytics, mining, a
persistent REPL (sandbox runs start empty by design), the third-party
benchmark datasets, the research protocols that need cloud keys to measure,
and what needs Apple hardware or another GPU vendor. None of them needs the
reference copy: the design notes above are enough.

## Found while testing the rest (2026-10-26)

- A "|" in a dictated message let a second action run unchecked: the
  policy read the whole string as a message, the action stage split it
  and typed text into the window in front. Each step is now checked on
  its own and a message is never split.
- The starting policy allowed only messaging, so opening and closing
  apps, volume, reminders and the briefing were refused. Reversible
  device actions are now allowed; typing, settings, power and uninstall
  stay refused.
- Scheduling a repeated check asked the owner a yes/no question in raw
  JSON; it is now asked in words built from the call that will run.
- On this laptop gemma4 no longer fits the 4 GB GPU under Ollama 0.35:
  12 of 43 layers are offloaded and generation runs at 2.7 tokens a
  second, so live turns take 40 to 140 s and some reach the 60 s model
  limit. Forcing every layer onto the GPU was slower (1.55 tokens a
  second). This is the hardware and runtime, not this code, and it is
  open.
