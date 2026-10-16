"""Engines that speak the OpenAI chat API: llama.cpp server, vLLM, LM Studio, SGLang, and the cloud.

The runtime served Ollama only, so a model that runs faster in another
engine on this GPU (llama.cpp with partial offload, vLLM on a bigger
card) could not be tried without code changes, and every cloud model
name was refused. Each of those engines, and the OpenAI, Anthropic and
Google APIs, accepts POST /chat/completions in the OpenAI shape. This
one adapter covers them; llm_runtime.py decides which base URL a model
goes to:

    engine:<model>   the owner's local engine at AGENT_GURU_ENGINE_URL
                     (key in AGENT_GURU_ENGINE_KEY when it wants one)
    gpt-*, o1-*, o3-*, claude-*, gemini-*
                     the provider's cloud, only with AGENT_GURU_ALLOW_CLOUD
                     and that provider's key: OPENAI_API_KEY,
                     ANTHROPIC_API_KEY, GEMINI_API_KEY

Streaming parses server-sent events; tool calls arrive in fragments and
are joined before they are returned, as Ollama's adapter returns them.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from Agent_Guru.llm.models import (
    CompletionRequest,
    CompletionResponse,
    Message,
    ModelProvider,
    StreamChunk,
    TokenUsage,
    ToolCall,
)
from Agent_Guru.llm.providers.base import ProviderAdapter

_TIMEOUT_S = 120.0


@dataclass(frozen=True, slots=True)
class Endpoint:
    base_url: str
    key: str
    model: str
    cloud: bool


def cloud_allowed() -> bool:
    return os.environ.get("AGENT_GURU_ALLOW_CLOUD", "").strip().lower() in {"1", "true", "yes", "on"}


_CLOUD = (
    (("gpt-", "o1-", "o3-", "o4-"), "https://api.openai.com/v1", "OPENAI_API_KEY"),
    (("claude-",), "https://api.anthropic.com/v1", "ANTHROPIC_API_KEY"),
    (("gemini-",), "https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY"),
)


def cloud_key_env(model: str) -> str:
    """The environment variable holding the key for cloud *model*, or "" when it is not a cloud model."""
    return next((env for prefixes, _, env in _CLOUD if model.startswith(prefixes)), "")


def endpoint_for(model: str) -> Endpoint | None:
    """Where *model* is served, or None when this adapter does not serve it (or the owner has not allowed it)."""
    if model.startswith("engine:"):
        base = os.environ.get("AGENT_GURU_ENGINE_URL", "").strip().rstrip("/")
        if not base:
            return None
        return Endpoint(base, os.environ.get("AGENT_GURU_ENGINE_KEY", "").strip(), model.removeprefix("engine:"), False)
    for prefixes, base, env in _CLOUD:
        if model.startswith(prefixes):
            key = os.environ.get(env, "").strip()
            if not (cloud_allowed() and key):
                return None
            return Endpoint(base, key, model, True)
    return None


def _wire_messages(messages: list[Message]) -> list[dict[str, Any]]:
    wire: list[dict[str, Any]] = []
    pending_ids: list[str] = []
    for i, m in enumerate(messages):
        item: dict[str, Any] = {"role": m.role, "content": m.content or ""}
        if m.tool_calls:
            ids = [f"call_{i}_{n}" for n in range(len(m.tool_calls))]
            pending_ids = list(ids)
            item["tool_calls"] = [
                {"id": cid, "type": "function", "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
                for cid, c in zip(ids, m.tool_calls, strict=True)
            ]
        if m.role == "tool":
            item["tool_call_id"] = pending_ids.pop(0) if pending_ids else f"call_{i}"
            if m.name:
                item["name"] = m.name
        wire.append(item)
    return wire


def _payload(request: CompletionRequest, model: str, stream: bool, *, cloud: bool = False) -> dict[str, Any]:
    body: dict[str, Any] = {"model": model, "messages": _wire_messages(request.messages),
                            "temperature": request.temperature, "stream": stream}
    # gemma4 through Ollama's OpenAI API thought until max_tokens ran out and
    # answered "" (40 of 40 tokens spent thinking); "none" answered "Four" in
    # 2. The assistant runs local models with thinking off, so local engines
    # get "none" unless AGENT_GURU_ENGINE_REASONING says otherwise ("" sends
    # nothing, for an engine that rejects the field). Not sent to the cloud:
    # non-reasoning OpenAI models refuse it.
    effort = os.environ.get("AGENT_GURU_ENGINE_REASONING", "none").strip()
    if effort and not cloud:
        body["reasoning_effort"] = effort
    if request.max_tokens:
        body["max_tokens"] = request.max_tokens
    if request.functions:
        body["tools"] = [{"type": "function", "function": {"name": f.name, "description": f.description,
                                                           "parameters": f.parameters}} for f in request.functions]
    if stream:
        body["stream_options"] = {"include_usage": True}
    return body


def _tool_calls(raw: list[dict[str, Any]] | None) -> list[ToolCall]:
    calls = []
    for c in raw or []:
        fn = c.get("function") or {}
        try:
            arguments = json.loads(fn.get("arguments") or "{}")
        except ValueError:
            arguments = {"_unparsed": fn.get("arguments", "")}
        if fn.get("name"):
            calls.append(ToolCall(name=fn["name"], arguments=arguments if isinstance(arguments, dict) else {}))
    return calls


def _usage(raw: dict[str, Any] | None) -> TokenUsage:
    raw = raw or {}
    prompt, completion = int(raw.get("prompt_tokens") or 0), int(raw.get("completion_tokens") or 0)
    return TokenUsage(prompt_tokens=prompt, completion_tokens=completion, total_tokens=prompt + completion, estimated_cost=0.0)


class OpenAICompatibleAdapter(ProviderAdapter):
    """POST /chat/completions and /embeddings against the endpoint each model maps to."""

    def _endpoint(self, model: str) -> Endpoint:
        point = endpoint_for(model)
        if point is None:
            from Agent_Guru.llm.models import ProviderNotSupportedError

            msg = (f"{model} has no engine: set AGENT_GURU_ENGINE_URL for engine: models, or allow the cloud "
                   f"(AGENT_GURU_ALLOW_CLOUD) and set {cloud_key_env(model) or 'its key'}")
            raise ProviderNotSupportedError(msg)
        return point

    @staticmethod
    def _headers(point: Endpoint) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if point.key:
            headers["Authorization"] = f"Bearer {point.key}"
        return headers

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        import httpx

        point = self._endpoint(request.model)
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            response = await client.post(f"{point.base_url}/chat/completions", headers=self._headers(point),
                                         json=_payload(request, point.model, stream=False, cloud=point.cloud))
        response.raise_for_status()
        body = response.json()
        choice = (body.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        return CompletionResponse(
            content=message.get("content") or "", model=request.model,
            provider=ModelProvider.OPENAI_COMPATIBLE, finish_reason=choice.get("finish_reason") or "stop",
            usage=_usage(body.get("usage")), latency_ms=(time.perf_counter() - started) * 1000,
            timestamp=datetime.now(tz=UTC), tool_calls=_tool_calls(message.get("tool_calls")),
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        import httpx

        point = self._endpoint(request.model)
        fragments: dict[int, dict[str, str]] = {}
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client, client.stream(
            "POST", f"{point.base_url}/chat/completions", headers=self._headers(point),
            json=_payload(request, point.model, stream=True, cloud=point.cloud),
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                except ValueError:
                    continue
                if event.get("usage") and not event.get("choices"):
                    yield StreamChunk(content="", usage=_usage(event["usage"]))
                    continue
                choice = (event.get("choices") or [{}])[0]
                delta = choice.get("delta") or {}
                for part in delta.get("tool_calls") or []:
                    slot = fragments.setdefault(int(part.get("index", 0)), {"name": "", "arguments": ""})
                    fn = part.get("function") or {}
                    slot["name"] += fn.get("name") or ""
                    slot["arguments"] += fn.get("arguments") or ""
                finish = choice.get("finish_reason")
                calls = None
                if finish and fragments:
                    calls = _tool_calls([{"function": fragments[i]} for i in sorted(fragments)])
                    fragments.clear()
                if delta.get("content") or finish or calls:
                    yield StreamChunk(content=delta.get("content") or "", finish_reason=finish, tool_calls=calls,
                                      usage=_usage(event["usage"]) if event.get("usage") else None)

    async def embed(self, text: str | list[str], model: str) -> list[list[float]]:
        import httpx

        point = self._endpoint(model)
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            response = await client.post(f"{point.base_url}/embeddings", headers=self._headers(point),
                                         json={"model": point.model, "input": text})
        response.raise_for_status()
        return [item["embedding"] for item in response.json().get("data") or []]

    async def supports_tool_calling(self, model: str) -> bool:
        # Every engine on this API takes "tools"; one that ignores them
        # answers in text, which the tool loop already handles.
        return endpoint_for(model) is not None
