# MCP client: the reference project and AGENT_GURU

Roadmap batch 4.1 (gap TOOL-7). How AGENT_GURU talks to MCP servers, what
was learned from the reference project's client, and where AGENT_GURU
does it differently. No code was copied; see `THIRD_PARTY_PROVENANCE.md`.

## What MCP gives AGENT_GURU

An MCP server is a separate program offering tools (read files, query a
service, run a search) over JSON-RPC 2.0. A client discovers its tools
with `tools/list` and runs one with `tools/call`. For AGENT_GURU this is a
way to gain abilities without writing each one, at the price that every
server is someone else's code with reach into the owner's machine.

Batch 4.1 is the client and the gate in front of it. A voice turn choosing
and calling tools is batch 4.2 (the tool loop).

## The reference project's client, as read

`mcp/client.py`, `mcp/transport.py`, `mcp/loader.py`, `tools/mcp_adapter.py`
(about 800 lines on the client side).

- Synchronous, one thread lock per client; the stdio transport reads
  stdout on a background thread into a bounded queue and drains stderr on
  another.
- Skips lines that are not the reply to the current request, so stray
  notifications do not end a request early.
- Closes a client whose initialize fails, and loads each configured
  server separately, so one broken server does not stop the others.
- Every listed tool becomes a usable tool, filtered only by optional
  include and exclude lists. Tool annotations are not read.
- Arguments are passed to the server unchecked.
- Every call waits up to 600 s.
- A call's result is the server's `isError` flag: success unless the
  server says otherwise.
- Tool output text goes to the model as returned.
- The server process inherits the whole environment.

## AGENT_GURU's client

Files: `reasoning/tools/mcp_client.py` (the connection),
`reasoning/tools/mcp_schema.py` (argument checking),
`integration/mcp_tools.py` (configuration, policy, status, audit, the
`python -m Agent_Guru mcp` command).

### Kept from the reference, as ideas

- stderr is drained continuously. AGENT_GURU reads it in chunks rather
  than lines: a line-based reader stopped at a 6 MB line without a
  newline, and the server then blocked (found by this batch's tests).
- A reply only completes the request with its id. AGENT_GURU matches by
  id across concurrent requests (20 in flight in the tests) instead of
  serialising them, and drops late, repeated or invented ids.
- Per-server isolation and closing a server that failed to start.

### Different on purpose

| Concern | Reference project | AGENT_GURU |
|---|---|---|
| Who decides a tool may run | the server lists it | the owner allows that exact tool and declares its risk in `settings.toml`; the policy engine then allows `external:mcp:<server>:<tool>` |
| Server's own risk hints | ignored | shown to the owner; a `read_only` declaration contradicted by the server's hints is refused |
| Arguments | sent as written | checked against the tool's schema first, undeclared fields refused, nesting and size bounded |
| Schema features not understood | n/a | the tool is not offered (`anyOf`, `$ref`, `pattern` and similar) |
| Time limit | 600 s | per server, 30 s default; read-only timeout is FAILED, a timeout on a tool that changes things is UNVERIFIED |
| Result status | success unless `isError` | ActionStatus: SUCCESS only for read-only tools; a tool that changes things is UNVERIFIED, since nothing checks the change |
| Output | as returned | text only (images and resources named), control characters removed, cut at 8,000 characters, injection-guarded, and given to the model labelled as tool data |
| Message size | unbounded line | per-server limit (1 MB default); over it the connection is closed and the call fails |
| Environment | inherited | only what a program needs plus the variables named in `env` and `pass_env`; measured with the official test server: 118 variables including a planted token before, 49 and no token after |
| Child processes | the started process | the whole process tree, through a Windows job object (`npx` starts cmd.exe, which starts node) |
| Cancellation | close the transport | the server is told, the server is ended, the call is CANCELLED, or UNVERIFIED for a tool that changes things |
| Records | none | every call in the signed audit log (secret-looking arguments removed) and, when given, as an `mcp_call` stage of the turn record |
| Concurrency model | threads and locks | asyncio, one reader task per server |

## Policy integration

No second policy engine. `install_mcp_policies` adds one ALLOW policy per
tool the owner allowed with a declared risk, matching the action string
exactly. The toolbox asks the orchestrator's own policy stage before every
call, never caching the answer. The command line builds its toolbox the
same way (`build_toolbox`), so `mcp call` cannot reach a tool a voice turn
could not.

## Testing

- `Agent_Guru/reasoning/tools/tests/test_mcp_schema.py`: the schema
  checker (unsupported and malformed schemas, types, nullability, enums,
  nesting, limits).
- `Agent_Guru/integration/tests/test_mcp_tools.py`: a real server process
  over stdio (`mcp_test_server.py`) covering allow and deny, risk, hint
  conflicts, the policy engine, argument checks, injection in output,
  output and message size, wrong and repeated ids, stray output,
  concurrency, timeouts, cancellation, crashes, start failure, stderr
  floods, process-tree cleanup, environment isolation, audit and turn
  records, settings parsing and the command. Each gate was removed in turn
  and its test failed.
- Live: `@modelcontextprotocol/server-everything@2026.8.31` through npx,
  in a scratch data folder. Not a dependency of AGENT_GURU.

## Not in this batch

- Voice turns using MCP tools (4.2). The assistant does not load the MCP
  code until then.
- HTTP transports, MCP resources and prompts, and the server side (exposing
  AGENT_GURU's own tools over MCP).
