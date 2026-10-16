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
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_PORT = 8765
HOST = "127.0.0.1"
_KEY_NAME = "api_key"
_MAX_TEXT = 4000


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
    turn_lock = asyncio.Lock()

    class TurnRequest(BaseModel):
        text: str = Field(min_length=1, max_length=_MAX_TEXT)

    async def run_turn(text: str, source: str) -> dict[str, Any]:
        async with turn_lock:
            result = await orchestrator.run_text_turn(text)
        status = getattr(result, "action_status", None)
        reply = result.llm_response or (result.action_result if isinstance(result.action_result, str) else "")
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
        from Agent_Guru.llm.security import guard_external_text

        if not guard_external_text(text, "agent-to-agent message"):
            return JSONResponse({"jsonrpc": "2.0", "id": call_id,
                                 "error": {"code": -32602, "message": "the message tried to give the assistant instructions"}})
        answer = await run_turn(text, "a2a")
        return JSONResponse({"jsonrpc": "2.0", "id": call_id, "result": {
            "kind": "message", "role": "agent", "messageId": secrets.token_hex(8),
            "parts": [{"kind": "text", "text": answer["reply"]}],
            "metadata": {"status": answer["status"], "awaiting_reply": answer["awaiting_reply"]},
        }})

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
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif}
main{max-width:760px;margin:0 auto;padding:16px;display:flex;flex-direction:column;min-height:100vh;box-sizing:border-box}
h1{font-size:20px;margin:8px 0 12px}#log{flex:1;overflow-y:auto}
.msg{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin:8px 0;white-space:pre-wrap}
.me{border-color:var(--accent)}.meta{color:var(--muted);font-size:13px}
form{display:flex;gap:8px;margin-top:8px}input{flex:1;min-width:0;padding:10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--fg);font:inherit}
button{padding:10px 16px;border:0;border-radius:8px;background:var(--accent);color:#fff;font:inherit;cursor:pointer}
</style></head><body><main>
<h1>Agent Guru</h1><div id="log"></div>
<form id="f"><input id="t" autocomplete="off" placeholder="Type to the assistant" required><button>Send</button></form>
<p class="meta" id="s"></p></main>
<script>
const log=document.getElementById('log'),s=document.getElementById('s');
function key(){let k=sessionStorage.getItem('k');if(!k){k=prompt('API key (python -m Agent_Guru api key)')||'';sessionStorage.setItem('k',k)}return k}
function add(text,cls,meta){const d=document.createElement('div');d.className='msg '+(cls||'');d.textContent=text;
 if(meta){const m=document.createElement('div');m.className='meta';m.textContent=meta;d.appendChild(m)}log.appendChild(d);log.scrollTop=log.scrollHeight}
document.getElementById('f').onsubmit=async e=>{e.preventDefault();const t=document.getElementById('t'),text=t.value.trim();if(!text)return;t.value='';add(text,'me');
 s.textContent='Thinking...';try{const r=await fetch('/v1/turn',{method:'POST',headers:{'Content-Type':'application/json','X-API-Key':key()},body:JSON.stringify({text})});
 if(r.status===401){sessionStorage.removeItem('k');s.textContent='Wrong key.';return}const j=await r.json();
 add(j.reply||j.error||'(no reply)','',[j.status,j.awaiting_reply?'waiting for your answer':'',(j.sources||[]).map(x=>x.url||x.title).filter(Boolean).join(' ')].filter(Boolean).join(' - '));s.textContent=''}
 catch(err){s.textContent='Could not reach the assistant: '+err}};
(async()=>{try{const r=await fetch('/v1/events',{headers:{'X-API-Key':key()}});const rd=r.body.getReader(),dec=new TextDecoder();let buf='';
 for(;;){const {value,done}=await rd.read();if(done)break;buf+=dec.decode(value,{stream:true});let i;while((i=buf.indexOf('\\n\\n'))>=0){const chunk=buf.slice(0,i);buf=buf.slice(i+2);
 const data=chunk.split('\\n').find(l=>l.startsWith('data: '));if(!data)continue;const ev=JSON.parse(data.slice(6));
 if(ev.topic==='turn.finished'&&ev.heard)s.textContent='Heard: '+ev.heard;if(ev.topic==='task.ran')add('Scheduled task '+ev.task_id+': '+ev.status,'')}}}catch(e){}})();
</script></body></html>
"""
