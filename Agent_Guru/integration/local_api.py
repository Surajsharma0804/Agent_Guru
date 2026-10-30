"""The assistant over HTTP on this machine: typed turns, live events, agent-to-agent, a web page.

Everything the assistant does was reachable only by voice or by running a
script inside its process. This serves the running assistant on
127.0.0.1, off unless AGENT_GURU_API is set:

    GET  /                          a chat page for the browser
    GET  /v1/health                 is it up (no key needed)
    POST /v1/turn {"text": ...}     one typed turn, the same pipeline as speech
    GET  /v1/events                 what happens, as server-sent events
    GET  /.well-known/agent-card.json   who this agent is, for other agents
    POST /a2a                       agent-to-agent JSON-RPC: message/send

Every route but health and the agent card needs the owner's key in the
X-API-Key header (`python -m Agent_Guru api key` prints it). The key is
made on first use and kept encrypted in the data folder
(security/secret_store.py); it goes through the same APIKeyManager and
rate limiter as the reasoning API. A turn from here is a typed turn: the
same policy, the same confirmation before a change ("yes" is the owner's
next request), the same turn record. Turns from the API run one at a time.

Only 127.0.0.1 is served: the API answers whoever holds the key, and
nothing here is meant to be reachable from the network.
"""


import argparse
import asyncio
import contextlib
import json
import logging
import os
import secrets
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_PORT = 8765
HOST = "127.0.0.1"
_KEY_NAME = "api_key"
_MAX_TEXT = 4000
_MAX_UPLOAD_BYTES = 20 * 1024 * 1024
#: What `documents add` reads (presentation.read_source_text).
_DOCUMENT_SUFFIXES = frozenset({".txt", ".md", ".markdown", ".docx", ".pdf"})


def enabled() -> bool:
    return os.environ.get("AGENT_GURU_API", "").strip().lower() in {"1", "true", "yes", "on"}


def port() -> int:
    try:
        return int(os.environ.get("AGENT_GURU_API_PORT", DEFAULT_PORT))
    except ValueError:
        return DEFAULT_PORT


def owner_key(*, new: bool = False) -> str:
    """The owner's API key, made and kept the first time; *new* replaces it."""
    from Agent_Guru.security import secret_store

    if new:
        secret_store.delete(_KEY_NAME)
    return secret_store.load_or_create(_KEY_NAME, lambda: secrets.token_urlsafe(32).encode()).decode()


def create_app(orchestrator: Any) -> Any:
    """The FastAPI app for *orchestrator*; the owner's key is registered with the shared APIKeyManager."""
    from fastapi import Depends, FastAPI, Request
    from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
    from pydantic import BaseModel, Field

    from Agent_Guru.reasoning.api.auth import Role, get_api_key_manager, get_current_user

    get_api_key_manager().register_key(owner_key(), user_id="owner", role=Role.ADMIN, name="assistant owner")
    app = FastAPI(title="Agent Guru", docs_url=None, redoc_url=None, openapi_url=None)

    class TurnRequest(BaseModel):
        text: str = Field(min_length=1, max_length=_MAX_TEXT)

    class MicRequest(BaseModel):
        muted: bool

    async def run_turn(text: str, source: str) -> dict[str, Any]:
        # No lock of its own any more: it kept API turns apart from each other
        # but not from a voice turn. The orchestrator's turn gate serializes
        # every source, and the source decides who may answer its questions.
        result = await orchestrator.run_text_turn(text, source=source)
        status = getattr(result, "action_status", None)
        reply = result.llm_response or (result.action_result if isinstance(result.action_result, str) else "")
        if not reply:
            # The voice path says what happened when nothing else did ("I can't do that - it
            # isn't allowed in my current settings."); this returned "" and `ask` printed
            # "(no reply)", so a typed turn could not tell a refusal from a hang.
            from Agent_Guru.integration.orchestrator import _STATUS_REPLIES

            reply = _STATUS_REPLIES.get(status, _STATUS_REPLIES[None])
        orchestrator.events.publish("api.turn", source=source, chars=len(text), status=getattr(status, "value", None))
        return {
            "reply": reply or "",
            "status": getattr(status, "value", None),
            "awaiting_reply": bool(getattr(result, "awaiting_reply", False)),
            "sources": list(getattr(result, "sources", []) or []),
            "error": result.error,
        }

    @app.get("/v1/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/turn")
    async def turn(body: TurnRequest, _user: dict = Depends(get_current_user)) -> dict[str, Any]:  # noqa: B008
        return await run_turn(body.text, "api")

    def mic_state() -> str:
        mic = getattr(orchestrator, "microphone", None)
        if mic is None:
            return "none"
        return "muted" if mic.muted else "listening"

    @app.get("/v1/mic")
    async def mic_view(_user: dict = Depends(get_current_user)) -> dict[str, str]:  # noqa: B008
        return {"microphone": mic_state()}

    @app.post("/v1/mic")
    async def mic_set(body: MicRequest, _user: dict = Depends(get_current_user)) -> JSONResponse:  # noqa: B008
        """Mute or unmute listening. There was no way to stop it listening short of quitting."""
        mic = getattr(orchestrator, "microphone", None)
        if mic is None:
            return JSONResponse({"microphone": "none", "error": "nothing is listening"}, status_code=409)
        mic.set_muted(body.muted)
        orchestrator.events.publish("mic", muted=body.muted)
        return JSONResponse({"microphone": mic_state()})

    @app.get("/v1/events")
    async def events(request: Request, _user: dict = Depends(get_current_user)) -> StreamingResponse:  # noqa: B008
        queue, unsubscribe = orchestrator.events.stream("*")

        async def body() -> Any:
            try:
                yield ": connected\n\n"
                while not await request.is_disconnected():
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=15)
                    except TimeoutError:
                        yield ": keep-alive\n\n"
                        continue
                    payload = json.dumps({"topic": event.topic, "at": event.at, **event.data}, default=str)
                    yield f"event: {event.topic}\ndata: {payload}\n\n"
            finally:
                unsubscribe()

        return StreamingResponse(body(), media_type="text/event-stream")

    @app.get("/.well-known/agent-card.json")
    async def agent_card() -> dict[str, Any]:
        return {
            "protocolVersion": "0.3.0",
            "name": "Agent Guru",
            "description": "A local voice assistant: answers questions, controls this computer, "
                           "reminds and schedules, researches with sources. Changes ask the owner first.",
            "url": f"http://{HOST}:{port()}/a2a",
            "preferredTransport": "JSONRPC",
            "version": "1.0.0",
            "capabilities": {"streaming": False, "pushNotifications": False},
            "defaultInputModes": ["text/plain"],
            "defaultOutputModes": ["text/plain"],
            "securitySchemes": {"apiKey": {"type": "apiKey", "in": "header", "name": "X-API-Key"}},
            "security": [{"apiKey": []}],
            "skills": [
                {"id": "ask", "name": "Ask", "description": "Answer a question, with sources when it searched.",
                 "tags": ["question", "research"]},
                {"id": "do", "name": "Do", "description": "Do something on this computer; the owner confirms changes.",
                 "tags": ["action"]},
            ],
        }

    @app.post("/a2a")
    async def a2a(request: Request, _user: dict = Depends(get_current_user)) -> JSONResponse:  # noqa: B008
        try:
            call = await request.json()
        except ValueError:
            return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
        call_id = call.get("id") if isinstance(call, dict) else None
        if not isinstance(call, dict) or call.get("jsonrpc") != "2.0" or not isinstance(call.get("method"), str):
            return JSONResponse({"jsonrpc": "2.0", "id": call_id, "error": {"code": -32600, "message": "invalid request"}})
        if call["method"] != "message/send":
            return JSONResponse({"jsonrpc": "2.0", "id": call_id,
                                 "error": {"code": -32601, "message": f"{call['method']} is not supported"}})
        message = (call.get("params") or {}).get("message") or {}
        text = " ".join(
            p.get("text", "") for p in message.get("parts") or []
            if isinstance(p, dict) and p.get("kind", "text") == "text"
        ).strip()
        if not text or len(text) > _MAX_TEXT:
            return JSONResponse({"jsonrpc": "2.0", "id": call_id,
                                 "error": {"code": -32602, "message": f"a text part of 1 to {_MAX_TEXT} characters is needed"}})
        # Another agent's words are outside text: they are scanned like a
        # web page before they reach the model.
        from Agent_Guru.llm.security import guard_external_text_async

        if not await guard_external_text_async(text, "agent-to-agent message"):
            return JSONResponse({"jsonrpc": "2.0", "id": call_id,
                                 "error": {"code": -32602, "message": "the message tried to give the assistant instructions"}})
        answer = await run_turn(text, "a2a")
        return JSONResponse({"jsonrpc": "2.0", "id": call_id, "result": {
            "kind": "message", "role": "agent", "messageId": secrets.token_hex(8),
            "parts": [{"kind": "text", "text": answer["reply"]}],
            "metadata": {"status": answer["status"], "awaiting_reply": answer["awaiting_reply"]},
        }})

    # ---- OpenAI-compatible: any OpenAI client (Open WebUI, editor plugins,
    # the openai package with base_url) talks to the assistant. Such clients
    # send the key as "Authorization: Bearer <key>", which get_current_user
    # would read as a JWT and refuse, so the owner's key is accepted here
    # as a bearer too (compared in constant time).
    import hmac

    def openai_auth(request: Request) -> None:
        sent = request.headers.get("x-api-key") or ""
        bearer = request.headers.get("authorization", "")
        if bearer.lower().startswith("bearer "):
            sent = sent or bearer[7:].strip()
        if not sent or not hmac.compare_digest(sent.encode(), owner_key().encode()):
            from fastapi import HTTPException

            raise HTTPException(status_code=401, detail="invalid API key")

    class ChatMessage(BaseModel):
        role: str
        content: str | list[dict[str, Any]] | None = None

    class ChatRequest(BaseModel):
        model: str = "agent-guru"
        messages: list[ChatMessage] = Field(min_length=1)
        stream: bool = False

    def _text(content: Any) -> str:
        if isinstance(content, str):
            return content
        return " ".join(p.get("text", "") for p in content or [] if isinstance(p, dict) and p.get("type") == "text")

    @app.get("/v1/models")
    async def models(_: None = Depends(openai_auth)) -> dict[str, Any]:  # noqa: B008
        return {"object": "list", "data": [{"id": "agent-guru", "object": "model", "owned_by": "local"}]}

    @app.post("/v1/chat/completions")
    async def chat_completions(body: ChatRequest, _: None = Depends(openai_auth)) -> Any:  # noqa: B008
        # The assistant keeps its own conversation and memory, so only the
        # newest user message is a turn; earlier messages are the client's copy.
        last = next((_text(m.content) for m in reversed(body.messages) if m.role == "user"), "").strip()
        if not last or len(last) > _MAX_TEXT:
            return JSONResponse({"error": {"message": f"a user message of 1 to {_MAX_TEXT} characters is needed",
                                           "type": "invalid_request_error"}}, status_code=400)
        answer = await run_turn(last, "openai")
        created, ident = int(__import__("time").time()), f"chatcmpl-{secrets.token_hex(12)}"
        if not body.stream:
            return {"id": ident, "object": "chat.completion", "created": created, "model": body.model,
                    "choices": [{"index": 0, "finish_reason": "stop",
                                 "message": {"role": "assistant", "content": answer["reply"]}}],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}

        async def events() -> Any:
            base = {"id": ident, "object": "chat.completion.chunk", "created": created, "model": body.model}
            first = {**base, "choices": [{"index": 0, "delta": {"role": "assistant", "content": answer["reply"]},
                                          "finish_reason": None}]}
            yield f"data: {json.dumps(first)}\n\n"
            yield f"data: {json.dumps({**base, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    # ---- the dashboard's views: read only, the owner's key required ----

    @app.get("/v1/status")
    async def status_view(_user: dict = Depends(get_current_user)) -> dict[str, Any]:  # noqa: B008
        from Agent_Guru.connectors.oauth import connected
        from Agent_Guru.llm.model_router import turn_routing
        from Agent_Guru.platform.channels import CHANNELS

        return {
            "model": os.environ.get("OLLAMA_MODEL", "gemma4"),
            "fallback_model": os.environ.get("AGENT_GURU_FALLBACK_MODEL", ""),
            "routing": turn_routing.enabled(),
            "cloud_allowed": os.environ.get("AGENT_GURU_ALLOW_CLOUD", "").lower() in {"1", "true", "yes", "on"},
            "accounts": connected(),
            "channels": sorted(name for name, c in CHANNELS.items() if c.configured()),
            "microphone": mic_state(),
        }

    @app.get("/v1/turns")
    async def turns_view(limit: int = 20, _user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:  # noqa: B008
        store = getattr(orchestrator, "trace_store", None)
        if store is None:
            return []
        turns = await asyncio.to_thread(store.recent, limit=max(1, min(limit, 200)))
        return [{"at": t.started_at, "seconds": round(t.seconds, 2), "heard": t.heard, "said": t.said,
                 "intent": t.intent, "status": t.action_status, "outcome": t.outcome, "model": t.model,
                 "rating": t.rating} for t in turns]

    @app.get("/v1/tasks")
    async def tasks_view(_user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:  # noqa: B008
        manager = orchestrator._reminders()
        return [{"id": r.reminder_id, "kind": r.kind, "message": r.message, "fire_at": r.fire_at,
                 "every_s": r.every_s, "tool": r.tool, "enabled": r.enabled,
                 "last": (r.runs[-1] if r.runs else None)} for r in manager.list_reminders()]

    @app.get("/v1/memory")
    async def memory_view(_user: dict = Depends(get_current_user)) -> dict[str, Any]:  # noqa: B008
        from Agent_Guru.platform.features.user_memory import get_user_memory

        return get_user_memory().get_all()

    @app.get("/v1/documents")
    async def documents_view(_user: dict = Depends(get_current_user)) -> list[dict[str, Any]]:  # noqa: B008
        store = getattr(orchestrator, "_documents", None)
        return [] if store is None else store.documents()

    @app.post("/v1/documents")
    async def documents_add(request: Request, name: str, _user: dict = Depends(get_current_user)) -> JSONResponse:  # noqa: B008
        """Add a document to answer from: the file is the request body, its name in ?name=.

        Documents could be added only with `documents add` at this computer.
        The body is read raw (no multipart parser is installed), capped at
        20 MB, saved under the data folder's uploads with a cleaned name,
        then added exactly as `documents add` adds a file.
        """
        import re as _re

        from Agent_Guru.utils.path_utils import app_data_dir

        store = getattr(orchestrator, "_documents", None)
        if store is None:
            return JSONResponse({"error": "documents are not set up"}, status_code=503)
        # No separators survive, and no run of dots, so the file stays in uploads.
        clean = _re.sub(r"\.{2,}", ".", _re.sub(r"[^A-Za-z0-9._ -]+", "_", name)).strip(" ._")[:120]
        if Path(clean).suffix.lower() not in _DOCUMENT_SUFFIXES:
            return JSONResponse({"error": f"only {', '.join(sorted(_DOCUMENT_SUFFIXES))} files"}, status_code=415)
        body = await request.body()
        if not body or len(body) > _MAX_UPLOAD_BYTES:
            return JSONResponse({"error": "the file is empty or larger than 20 MB"}, status_code=413)
        target = app_data_dir("uploads", create=True) / clean
        target.write_bytes(body)
        added = await store.add(target)
        orchestrator.events.publish("api.document", name=clean, status=added.status)
        return JSONResponse({"name": added.name, "status": added.status, "passages": added.passages})

    @app.get("/", response_class=HTMLResponse)
    async def page() -> str:
        return _PAGE

    return app


async def serve(orchestrator: Any, stop: asyncio.Event) -> None:
    """Serve the API until *stop* is set; logs and returns if the port is taken."""
    import uvicorn

    config = uvicorn.Config(create_app(orchestrator), host=HOST, port=port(), log_level="warning", lifespan="off")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    logger.info("Local API on http://%s:%d (key: python -m Agent_Guru api key)", HOST, port())
    waiter = asyncio.create_task(stop.wait())
    await asyncio.wait({task, waiter}, return_when=asyncio.FIRST_COMPLETED)
    server.should_exit = True
    with contextlib.suppress(Exception):
        await task
    waiter.cancel()


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m Agent_Guru api", description="The assistant's local HTTP API.")
    sub = parser.add_subparsers(dest="action")
    key = sub.add_parser("key", help="print the owner's API key")
    key.add_argument("--new", action="store_true", help="replace it; the old key stops working at the next start")
    args = parser.parse_args(argv)
    if args.action == "key":
        print(owner_key(new=args.new))  # noqa: T201  the command's output
        return 0
    state = "on" if enabled() else "off (set AGENT_GURU_API = true in settings.toml)"
    print(f"Local API: {state}, http://{HOST}:{port()}/")  # noqa: T201
    return 0


_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agent Guru</title>
<style>
:root{--bg:#f7f7f5;--fg:#1d1d1b;--muted:#6b6b66;--card:#fff;--line:#dedcd6;--accent:#2f5d8a}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#ecebe6;--muted:#9a9890;--card:#201f1d;--line:#34332f;--accent:#7fa8d6}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif}
main{max-width:860px;margin:0 auto;padding:16px;display:flex;flex-direction:column;min-height:100vh}
h1{font-size:20px;margin:8px 0}nav{display:flex;gap:4px;flex-wrap:wrap;border-bottom:1px solid var(--line);margin-bottom:8px}
nav button{background:none;color:var(--muted);border:0;border-bottom:2px solid transparent;padding:8px 10px;font:inherit;cursor:pointer}
nav button.on{color:var(--fg);border-color:var(--accent)}section{display:none;flex:1}section.on{display:flex;flex-direction:column}
#log{flex:1;overflow-y:auto}.msg{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin:8px 0;white-space:pre-wrap;overflow-wrap:anywhere}
.me{border-color:var(--accent)}.meta{color:var(--muted);font-size:13px}
form{display:flex;gap:8px;margin-top:8px}input{flex:1;min-width:0;padding:10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--fg);font:inherit}
.btn{padding:10px 16px;border:0;border-radius:8px;background:var(--accent);color:#fff;font:inherit;cursor:pointer}
table{width:100%;border-collapse:collapse;font-size:14px}td,th{text-align:left;padding:6px;border-bottom:1px solid var(--line);vertical-align:top;overflow-wrap:anywhere}
th{color:var(--muted);font-weight:600}.wrap{overflow-x:auto}
</style></head><body><main>
<h1>Agent Guru</h1>
<nav id="tabs"><button data-t="chat" class="on">Chat</button><button data-t="activity">Activity</button>
<button data-t="turns">Turns</button><button data-t="tasks">Tasks</button><button data-t="memory">Memory</button><button data-t="status">Status</button></nav>
<section id="chat" class="on"><div id="log"></div>
<form id="f"><input id="t" autocomplete="off" placeholder="Type to the assistant" required><button class="btn">Send</button></form><p class="meta" id="s"></p></section>
<section id="activity"><div id="events" class="wrap"></div></section>
<section id="turns"><div class="wrap" id="turnsv"></div></section>
<section id="tasks"><div class="wrap" id="tasksv"></div></section>
<section id="memory"><div class="wrap" id="memoryv"></div></section>
<section id="status"><div class="wrap" id="statusv"></div></section>
</main>
<script>
const $=id=>document.getElementById(id);
function key(){let k='';try{k=sessionStorage.getItem('k')||''}catch(e){}if(!k){k=prompt('API key (python -m Agent_Guru api key)')||'';try{sessionStorage.setItem('k',k)}catch(e){}}return k}
async function api(path,opts){const r=await fetch(path,{...(opts||{}),headers:{'Content-Type':'application/json','X-API-Key':key(),...((opts||{}).headers||{})}});
 if(r.status===401){try{sessionStorage.removeItem('k')}catch(e){}throw new Error('wrong key')}return r.json()}
function esc(v){return String(v==null?'':v).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function table(rows,cols){if(!rows.length)return '<p class="meta">Nothing yet.</p>';
 return '<table><tr>'+cols.map(c=>'<th>'+esc(c[0])+'</th>').join('')+'</tr>'+rows.map(r=>'<tr>'+cols.map(c=>'<td>'+esc(c[1](r))+'</td>').join('')+'</tr>').join('')+'</table>'}
function when(t){return t?new Date(t*1000).toLocaleString():''}
function add(text,cls,meta){const d=document.createElement('div');d.className='msg '+(cls||'');d.textContent=text;
 if(meta){const m=document.createElement('div');m.className='meta';m.textContent=meta;d.appendChild(m)}$('log').appendChild(d);$('log').scrollTop=1e9}
$('f').onsubmit=async e=>{e.preventDefault();const text=$('t').value.trim();if(!text)return;$('t').value='';add(text,'me');$('s').textContent='Thinking...';
 try{const j=await api('/v1/turn',{method:'POST',body:JSON.stringify({text})});
 add(j.reply||j.error||'(no reply)','',[j.status,j.awaiting_reply?'waiting for your answer':'',(j.sources||[]).map(x=>x.url||x.title).filter(Boolean).join(' ')].filter(Boolean).join(' - '));$('s').textContent=''}
 catch(err){$('s').textContent='Could not reach the assistant: '+err.message}};
const views={
 turns:async()=>{$('turnsv').innerHTML=table(await api('/v1/turns?limit=50'),[['When',r=>when(r.at)],['Heard',r=>r.heard],['Said',r=>r.said],['Status',r=>r.status||r.outcome||''],['Model',r=>r.model],['s',r=>r.seconds]])},
 tasks:async()=>{$('tasksv').innerHTML=table(await api('/v1/tasks'),[['Kind',r=>r.kind],['What',r=>r.message||r.tool],['Next',r=>when(r.fire_at)],['Every',r=>r.every_s?Math.round(r.every_s/60)+' min':''],['On',r=>r.enabled?'yes':'no'],['Last run',r=>r.last?r.last.status:'']])},
 memory:async()=>{const m=await api('/v1/memory');$('memoryv').innerHTML=table(Object.entries(m),[['What',r=>r[0]],['Remembered',r=>typeof r[1]==='string'?r[1]:JSON.stringify(r[1])]])},
 status:async()=>{const s=await api('/v1/status');$('statusv').innerHTML=table([
  ['Model',s.model],['Fallback model',s.fallback_model||'none'],['Routing by difficulty',s.routing?'on':'off'],['Cloud allowed',s.cloud_allowed?'yes':'no'],
  ['Accounts',Object.entries(s.accounts).filter(x=>x[1]).map(x=>x[0]).join(', ')||'none'],['Channels',s.channels.join(', ')||'none']],[['',r=>r[0]],['',r=>r[1]]])}};
document.querySelectorAll('#tabs button').forEach(b=>b.onclick=()=>{document.querySelectorAll('#tabs button,section').forEach(x=>x.classList.remove('on'));
 b.classList.add('on');$(b.dataset.t).classList.add('on');if(views[b.dataset.t])views[b.dataset.t]().catch(e=>$(b.dataset.t).insertAdjacentHTML('beforeend','<p class="meta">'+esc(e.message)+'</p>'))});
(async()=>{try{const r=await fetch('/v1/events',{headers:{'X-API-Key':key()}});const rd=r.body.getReader(),dec=new TextDecoder();let buf='';
 for(;;){const {value,done}=await rd.read();if(done)break;buf+=dec.decode(value,{stream:true});let i;while((i=buf.indexOf('\n\n'))>=0){const chunk=buf.slice(0,i);buf=buf.slice(i+2);
 const data=chunk.split('\n').find(l=>l.startsWith('data: '));if(!data)continue;const ev=JSON.parse(data.slice(6));
 const line=document.createElement('div');line.className='msg';line.textContent=new Date(ev.at*1000).toLocaleTimeString()+'  '+ev.topic+'  '+
  (ev.heard?('heard: '+ev.heard):'')+(ev.task_id?(' task '+ev.task_id+': '+ev.status):'')+(ev.channel?(' '+ev.channel+(ev.allowed===false?' (ignored)':'')):'');
 $('events').prepend(line);if(ev.topic==='turn.finished'&&ev.heard)$('s').textContent='Heard: '+ev.heard}}}catch(e){}})();
</script></body></html>
"""
