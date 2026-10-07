# Rejected features

The owner's goal (2026-10-07) is every reference-project capability that
makes AGENT_GURU better. Two would make it worse, and are rejected for
that reason alone. Reopen one if its reason stops being true.

| ID | Capability | Reason |
|---|---|---|
| ANL-1 | usage analytics sent to an external service (PostHog) | sends the owner's usage data off the device; AGENT_GURU keeps everything local. Local, on-device usage statistics are covered by the turn records instead. |
| MIN-1 | crypto mining sidecars | competes with the voice loop for the 4 GB GPU and has nothing to do with an assistant |

## Deferred, not rejected

Everything else is in the program, with the condition it needs written in
the gap matrix's Dependencies column. The ones with a safety condition:

| ID | Capability | Condition |
|---|---|---|
| AGT-5 | agents that write and run code | the sandbox (SBX-1) and a policy rule with spoken confirmation before any code runs |
| TOOL-8 | agent-to-agent protocol | the HTTP API (API-1) with authentication, off by default |
| INT-5 | routing between models | a second model that fits beside the main one on the GPU; a swap was measured at 17-19 s |
| REC-1 | recipes and templates | file-based configuration (ARCH-3) |
