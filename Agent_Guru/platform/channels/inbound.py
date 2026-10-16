"""Talk to the assistant from Telegram: messages from the owner's chats become typed turns.

The assistant could be asked something only at the computer. With
AGENT_GURU_TELEGRAM_INBOUND set (and TELEGRAM_BOT_TOKEN), this polls the
bot's updates; Telegram long polling needs no open port, so nothing on
this machine becomes reachable from the network.

Only chats listed in TELEGRAM_ALLOWED_CHATS (comma-separated chat ids)
are answered. A message from any other chat is not read to the model:
it is logged, published as message.in with allowed=False, and dropped,
and the bot does not reply (a reply would confirm to a stranger that the
bot is live). An allowed message is the owner typing: one typed turn,
with the same policy and the same yes before a change; the owner's
next message answers the question. Turns from here run one at a time.

To find a chat id, send the bot a message and run
`python -m Agent_Guru telegram chats`, which lists who has written.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import os
from typing import Any

from Agent_Guru.platform.channels import TelegramChannel

logger = logging.getLogger(__name__)

_POLL_S = 25
_MAX_TEXT = 4000


def enabled() -> bool:
    return os.environ.get("AGENT_GURU_TELEGRAM_INBOUND", "").strip().lower() in {"1", "true", "yes", "on"}


def allowed_chats() -> set[str]:
    return {c.strip() for c in os.environ.get("TELEGRAM_ALLOWED_CHATS", "").split(",") if c.strip()}


async def poll(orchestrator: Any, stop: asyncio.Event, channel: TelegramChannel | None = None) -> None:
    """Answer allowed chats until *stop* is set. Never raises; network errors back off and retry."""
    channel = channel or TelegramChannel()
    if not channel.configured():
        logger.warning("Telegram inbound is on but TELEGRAM_BOT_TOKEN is not set")
        return
    allowed = allowed_chats()
    if not allowed:
        logger.warning("Telegram inbound is on but TELEGRAM_ALLOWED_CHATS is empty: no chat would be answered")
        return
    offset = 0
    backoff = 1.0
    lock = asyncio.Lock()
    logger.info("Telegram inbound: answering %d chat(s)", len(allowed))
    while not stop.is_set():
        try:
            body = await channel.call("getUpdates", offset=offset, timeout=_POLL_S, allowed_updates=["message"])
            backoff = 1.0
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Telegram poll failed (%s); retrying in %.0fs", exc, backoff)
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), backoff)
            backoff = min(backoff * 2, 60.0)
            continue
        for update in body.get("result") or []:
            offset = max(offset, int(update.get("update_id", 0)) + 1)
            message = update.get("message") or {}
            chat = str((message.get("chat") or {}).get("id", ""))
            text = (message.get("text") or "").strip()
            if not chat or not text:
                continue
            if chat not in allowed:
                logger.warning("Telegram message from chat %s ignored: not in TELEGRAM_ALLOWED_CHATS", chat)
                orchestrator.events.publish("message.in", channel="telegram", chat=chat, allowed=False)
                continue
            orchestrator.events.publish("message.in", channel="telegram", chat=chat, allowed=True, chars=len(text))
            async with lock:
                try:
                    result = await orchestrator.run_text_turn(text[:_MAX_TEXT])
                    reply = result.llm_response or (result.action_result if isinstance(result.action_result, str) else "")
                except Exception:
                    logger.exception("Telegram turn failed")
                    reply = "Sorry, something went wrong with that."
            delivery = await channel.send(chat, reply or "Done.")
            if not delivery.sent:
                logger.warning("Telegram reply not delivered: %s", delivery.error)


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m Agent_Guru telegram", description="The Telegram bot.")
    sub = parser.add_subparsers(dest="action")
    sub.add_parser("chats", help="who has written to the bot recently, with their chat ids")
    args = parser.parse_args(argv)
    channel = TelegramChannel()
    if not channel.configured():
        print("Set TELEGRAM_BOT_TOKEN in the environment or .env first.")  # noqa: T201  the command's output
        return 1
    if args.action == "chats":
        body = asyncio.run(channel.call("getUpdates", timeout=0))
        seen: dict[str, str] = {}
        for update in body.get("result") or []:
            chat = (update.get("message") or {}).get("chat") or {}
            if chat.get("id") is not None:
                seen[str(chat["id"])] = chat.get("username") or chat.get("title") or chat.get("first_name") or ""
        for chat_id, who in seen.items():
            print(f"{chat_id:>15}  {who}")  # noqa: T201
        if not seen:
            print("No messages yet: send the bot a message, then run this again.")  # noqa: T201
        return 0
    state = "on" if enabled() else "off (AGENT_GURU_TELEGRAM_INBOUND = true in settings.toml)"
    print(f"Telegram inbound: {state}; allowed chats: {', '.join(sorted(allowed_chats())) or 'none'}")  # noqa: T201
    return 0
