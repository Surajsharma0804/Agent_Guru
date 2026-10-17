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
| 1.2 | TEL-1, TEL-4 tokens, time to first token and decode speed in the answer stage | one store instead of two | done, bb2ef774 |
| 1.3 | TRC-3, LRN-3 queries over turn records, rating a turn by voice | spoken "that was wrong" or "galat hai" marks the last answer; stage medians and p95 from the records | done |
| 1.4 | EVAL-1, EVAL-2 evaluation runner and latency bench fed by real turns | cases from real turns, plus the owner's voice-rated turns (`--rated`); real speech in and out for latency | done |
| 1.5 | CLI-1, CLI-2, INT-4, SEC-11 `doctor` and a command line: Ollama, model, GPU and VRAM, microphone, speaker, data folder, privacy checks | checks the audio devices and a real speech round trip (Kokoro speaks, Whisper must hear it), and who can read the owner's databases | `agent-guru doctor` done; still open: model recommendation from the hardware (INT-4) and commands beyond `doctor` (CLI-2) |

## Phase 2: things that must survive a restart

| Batch | Items | Condition | State |
|---|---|---|---|
| 2.1 | SEC-4 audit log on disk, tamper-evident | signing key kept with Windows DPAPI for the owner's account (the key store's master password is empty everywhere, so it would protect nothing) | done |
| 2.2 | SCH-1 reminders and schedules kept on disk | owner's rule (2026-10-07): a reminder due while the app was off is said on the next start, with how late | done; the production policy still refuses reminders, so the voice command reaches this only once the owner allows it |
| 2.3 | ARCH-3, ARCH-1 file-based configuration | keep environment variables working | settings.toml done (ARCH-3): fills in the variables every module already reads, the environment still wins, secrets refused; plugin registries (ARCH-1) not needed, no plugin system to register |

## Phase 3: memory

| Batch | Items | Condition | State |
|---|---|---|---|
| 3.1 | SEC-2 injection scan for text entering prompts from outside | none | done: web results, clipboard and screen text are scanned; old patterns flagged 4 of 8 ordinary sentences and missed 6 of 8 attacks, the new ones 0 and 0 |
| 3.2 | MEM-1, MEM-2 durable facts extracted by the model, with provenance and quarantine | GPU cost of the extra model call measured; run when idle if it delays replies | done: gemma4 reads each conversational exchange after the reply (0.84-1.18 s on real runs, off the reply path) and keeps up to 50 facts; flagged facts are quarantined and never reach a prompt; AGENT_GURU_LEARN_FACTS turns it off. Open: a fact keeps no date or source turn |
| 3.3 | MEM-3, MEM-4 keyword and meaning search fused | evaluation set from 1.4; the 0.25 cutoff stays | done: names and long numbers in a question now steer memory search; `scripts/memory_recall_eval.py` went from 14 of 25 questions right (2 missed, 9 leaked) to 18 of 25 (0 missed, 7 leaked), search time unchanged at 1,000 memories. Reciprocal rank fusion was not taken: it always returns the top results, which would undo the 0.25 cutoff. The 7 leaks left are meaning matches with no name to go on ("prime minister of India" brings three memories at 0.26-0.29); only the cutoff decides those |
| 3.4 | MEM-5 document ingestion into a knowledge store | 3.3 | done: `python -m Agent_Guru documents add|remove|list` (.txt, .md, .docx, .pdf); passages of 300 characters, cutoff 0.35 chosen with `scripts/document_recall_eval.py` (22 of 24 right, none missed); passages pass the injection guard; not used for live information or commands. Real gemma4 answered the lease, hotel booking and insurance questions from the documents and said it did not know without them. Adding embeds 162 passages a second, a search takes 11 ms. Open: no voice command to add a document |

## Phase 4: doing more

| Batch | Items | Condition | State |
|---|---|---|---|
| 4.1 | TOOL-7 MCP client behind the policy engine | security review | done: stdio client, owner-allowed tools only with declared risk, policy action `external:mcp:<server>:<tool>`, schema-checked arguments, guarded output, ActionStatus results, audit and turn-record entries; `python -m Agent_Guru mcp list|call`. Security review and comparison in `REFERENCE_MCP_COMPARISON.md`. Voice use comes with 4.2 |
| 4.2 | AGT-1, AGT-2, TRC-4 tool loop with loop guard, recorded in the turn | 1.4 | done: one loop for typed and spoken turns (`integration/tool_loop.py`), only callable MCP tools shown, every call through MCPToolbox.call, a change asks the owner first, budgets (4 calls, 4 steps, 40 s, 6,000 characters), repeats refused, claimed or promised actions without a tool corrected. `scripts/tool_loop_eval.py` on gemma4: 27 of 33 tool choices right over 3 runs, no fact invented in the misses. Open: two dependent tools in a row (booking, then flight) was not chained in any run |
| 4.3 | AGT-4, TOOL-6 multi-step research with sources, browser actions | 4.2, 3.1 | research done: search keeps title, URL, provider and retrieval time (Wikipedia API, DuckDuckGo instant answers); pages read without scripts behind a private-address check on every hop; web, document and memory sources numbered S/D/M per turn; answers held to them (unknown ids and URLs removed, numbers and names checked against the cited text); a live-data question is researched before the model answers. `scripts/research_eval.py`: 6 of 6 typed and spoken. Browser actions added 2026-10-17 (`integration/browser_tools.py`, AGENT_GURU_BROWSER_TOOLS): Playwright on the installed Edge or Chrome, numbered elements, the owner's yes naming the element and site, a fresh profile and the private-address guard. News added 2026-10-17: questions about now also search Bing News, newest first |
| 4.4 | SCH-2, AGT-3, ARCH-2 scheduled and monitoring agents with approval, on an internal event bus | 2.2, 4.2 | scheduling done in the reminder manager (one scheduler, one store): checks repeat a read-only tool at least 5 minutes apart and only speak; actions run on the owner's approval bound to the exact tool and arguments, with an expiry, and the policy is asked again at run time; each run is written as running first, so a restart records an interrupted action as unverified and never reruns it; missed checks run once, missed actions are not run late; a lock file stops a second copy running the tasks. Created through the tool loop (`tasks` tools), so creating one needs the owner's yes. gemma4 scheduled the Delhi weather check correctly in 6 of 6 runs once a focused step fills the repeated tool's arguments (0 of 6 before). Also fixed: "remind me at 3pm" was read as 3 pm UTC. Event bus (ARCH-2) not built: nothing here needed one |
| 4.5 | SBX-1, AGT-5 sandbox, then code-running agents | policy rule and spoken confirmation | done 2026-10-17: each run is a transient systemd service in WSL2 Ubuntu (automount and interop off) as the unprivileged user agsandbox, with no network, none of anyone's files, its own PID namespace and devices, no privileges or new namespaces, a system call filter and limits on memory, tasks, CPU, file size and time (`reasoning/tools/skills/wsl_sandbox.py`, `python -m Agent_Guru sandbox`); 18 attacks from Python and 5 from a shell are blocked in tests. run_python and run_shell (`integration/code_tools.py`, AGENT_GURU_CODE_SANDBOX) run only after the owner's yes, with the program read back. The AppContainer launcher (error 203) was deleted. Not built: a coding agent that edits files in a workspace |

## Phase 5: reach

| Batch | Items | Condition | State |
|---|---|---|---|
| 5.1 | CON-1, CON-2 connectors (mail, calendar, contacts, files) with OAuth | owner's accounts and consent | done: OAuth with PKCE and state for Google, Microsoft, Strava and Spotify, tokens kept with DPAPI and refreshed (`connectors/oauth.py`); in-process tools through the toolbox (`connectors/tools.py`): mail search, read and send (Gmail, Outlook, IMAP, SMTP), calendar events and add (Google, Outlook, .ics), contacts, files by name, news and Hacker News, Drive, Tasks, Notion, Obsidian, GitHub notifications, Dropbox, Oura, Strava, Spotify; each offered only when set up; sending, adding and playback wait for the owner's yes. Accounts not tried live: no credentials here |
| 5.2 | CHN-1, CHN-2 more channels (Telegram, Slack, email) beside verified WhatsApp | inbound commands pass the same policy | done: 21 channels behind one interface (`platform/channels`): Telegram, Slack, SMTP, Discord, Signal, Twilio SMS, Matrix, Zulip, Mastodon, LINE, Viber, Messenger, Reddit, IRC, Twitch, and signed webhooks for Teams, Google Chat, Mattermost, Rocket.Chat, Feishu and any URL; "sent" only when the service confirmed it. Inbound: the owner's Telegram chats as typed turns by long polling (no open port), every other chat ignored. X, XMPP and Nostr added 2026-10-17 (OAuth 1.0a, a library-free XMPP client tried on Prosody, BIP340 written here and checked against all 19 vectors) |
| 5.3 | API-1, TOOL-8 local HTTP API, then agent-to-agent | authentication, off by default | done: `integration/local_api.py` on 127.0.0.1, off unless AGENT_GURU_API: typed turns, server-sent events, OpenAI-compatible /v1/chat/completions and /v1/models, agent card and A2A message/send (injection-scanned), and a dashboard page (chat, activity, turns, tasks, memory, status); the owner's key kept with DPAPI. Fixed on the way: an API key could never authenticate (HTTPBearer refused first) |
| 5.4 | INT-1, INT-2, INT-3, INT-5, INT-6, AGT-6 more engines, model routing, local plus cloud combinations | hardware that fits a second model; cloud use only with owner's keys and consent | done: OpenAI-compatible adapter for llama.cpp, vLLM, LM Studio, SGLang and LiteLLM (`engine:<model>`) and the OpenAI, Anthropic and Gemini APIs only with AGENT_GURU_ALLOW_CLOUD; one fallback engine when the main one fails; model catalog from Ollama and NVML (`models`); routing by difficulty on the existing ModelRouter, learning from turn records, never swapping for an easy question (swap 17 to 19 s), cloud only for hard ones; off unless AGENT_GURU_ROUTER = auto |
| 5.5 | LRN-1, LRN-2, SKL-2, SKL-3 learning from turns (prompt tuning, fine-tuning) | enough turn records; the A100 plan | done: prompt tuning with rules from marked mistakes and demonstrations from good answers, behind an evaluation gate (more cases pass, none lost, at most 20 % slower) with rollback; fine-tuning dataset export with personal details masked (training itself needs a bigger GPU); skill import from git, zip or folder after a static scan and Ed25519 signature check; repeated tool sequences found in turn records |
| 5.6 | DSK-1, REC-1, WFL-1, TEL-2, TEL-3, SEC-6, SEC-7 remaining items | as listed in the matrix | done: sensitive-file policy for file tools, documents and tool arguments; taint labels in the confirmation question; inter-token latency percentiles; GPU energy and clock per turn through NVML; recipes of settings; event bus; dashboard page (DSK-1, instead of a separate desktop app); 18 commands (`python -m Agent_Guru help`). WFL-1 kept as it was (equivalent and unused in both) |

Found by the turn records (2026-10-07) and fixed: the first-turn note told
the model to greet and ask what's up whatever was said, so a first question
was answered after a sentence of small talk (answer at character 128,
median of 10 with gemma4); now 42, and greetings are still greeted.

Measured by `scripts/turn_eval.py` (2026-10-07, gemma4):

- Scoring: 20 of 23 cases pass. First questions 3/3, long-term memory 2/2
  (0/1 before the memory fix in 6bec04ec), commands 5/5, feedback 2/2.
- Latency over 9 spoken turns: speech recognition 1.08 s median (2.91 s
  p95), intent 0.001 s, policy 0.001 s, memory 0.012 s median, first text
  0.72 s, first audio ready 2.51 s, whole turn 8.0 s. Not measured: wake word
  and microphone capture, speaker output.

Findings from it, each to fix in its own batch:

- After the first turn the answer is still often behind persona filler
  ("Haha, seriously? Still doing basic math, bro?"): answer at characters
  93 and 68 in two of three cases.
- "open zxqvbn", an application that does not exist, is recognized as a
  website to open.
- Whisper runs on the CPU because the CUDA 12 libraries are missing
  (cublas64_12.dll); the app's own log puts the GPU at about 0.2 s against
  1.1 s measured.
- The first memory search after start loads the embedding model and hits
  the 5 s memory timeout (p95 5.00 s), so the first answer gets no
  memories; that turn took 16 s.

First `agent-guru doctor` run on the development laptop (2026-10-07): 9 ok,
3 warnings, 0 failed. Warnings: under 2 GB RAM free; Whisper on the CPU
(cublas64_12.dll missing); memory.db readable by SYSTEM and Administrators.
The model took 26.7 s to answer its first token from cold (23.7 s loading),
2.8 s warm. The speech engine also logs that the Kokoro model and voices
files have no pinned SHA-256.

Outside this roadmap and pending from earlier work: the production policy
still refuses app open and close although both are implemented and
verified.

## Parity check (2026-10-17)

Before the reference copy is deleted, every area of the reference project is mapped in `REFERENCE_PARITY.md`: present, built for the check, partial, not built (with what it needs), rejected or not applicable. Also built for it: the encrypted vault, the background service, `init` with a model recommendation, `update`, and the briefing with reminders, calendar and tasks (it had spoken UTC, and "good morning" never reached it).
