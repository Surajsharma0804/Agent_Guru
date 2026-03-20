"""Mock server for SDK testing using aiohttp."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from aiohttp import web
    _AIOHTTP_AVAILABLE = True
except ImportError:
    _AIOHTTP_AVAILABLE = False


class MockServer:
    """Configurable mock server for SDK testing."""

    def __init__(self, fixtures: Optional[Dict[str, Any]] = None) -> None:
        self.fixtures = fixtures or {}
        self._webhook_deliveries: List[Dict[str, Any]] = []
        self._app: Optional[Any] = None
        self._runner: Optional[Any] = None
        self._port = 0

    def set_fixture(self, path: str, response: Any) -> None:
        self.fixtures[path] = response

    async def start(self, port: int = 0) -> int:
        """Start the mock server. Returns actual port."""
        if not _AIOHTTP_AVAILABLE:
            logger.warning("aiohttp not available; mock server is a stub")
            self._port = port or 18080
            return self._port

        self._app = web.Application()
        self._app.router.add_route("*", "/{path_info:.*}", self._handle)
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "127.0.0.1", port)
        await site.start()
        self._port = site._server.sockets[0].getsockname()[1]  # type: ignore[union-attr]
        return self._port

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()

    async def _handle(self, request: Any) -> Any:
        path = "/" + request.match_info.get("path_info", "")
        fixture = self.fixtures.get(path, {"status": "ok"})
        return web.Response(
            text=json.dumps(fixture),
            content_type="application/json",
        )

    async def deliver_webhook(
        self,
        url: str,
        payload: Dict[str, Any],
        max_attempts: int = 3,
    ) -> bool:
        """Deliver webhook with exponential backoff (1s, 2s, 4s)."""
        try:
            import httpx
        except ImportError:
            self._webhook_deliveries.append({"url": url, "payload": payload, "delivered": True})
            return True

        for attempt in range(max_attempts):
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code < 500:
                        self._webhook_deliveries.append({"url": url, "payload": payload, "delivered": True})
                        return True
            except Exception as e:
                logger.warning("Webhook attempt %d failed: %s", attempt + 1, e)
            if attempt < max_attempts - 1:
                await asyncio.sleep(2 ** attempt)

        self._webhook_deliveries.append({"url": url, "payload": payload, "delivered": False})
        return False

    def get_deliveries(self) -> List[Dict[str, Any]]:
        return list(self._webhook_deliveries)
