"""What WhatsApp Desktop shows: its message box and the messages in the open chat.

The assistant reported a WhatsApp message as sent once it had pressed Enter
with a window titled "WhatsApp" in front. Nothing looked at what Enter did,
and opening a whatsapp://send link adds its text to whatever is already in
the chat's message box: with an unsent draft there, Enter sent the draft and
the new message together, and the reply still said the message had been
sent.

This reads WhatsApp Desktop's accessibility tree (UI Automation, through
comtypes) so the sender can check the message box before pressing Enter and
look for the sent message afterwards. It only reads; it never focuses,
clicks or types.

What was found on WhatsApp Desktop for Windows (WebView2), 2026-10-06:
- The message box is an Edit control holding keyboard focus; its Value is
  the text in it. UI Automation's own focused element stops at the WebView2
  host pane, so the Edit's HasKeyboardFocus is what identifies it.
- A message in the open chat is a DataItem row. Its text is the row's Text
  elements in order: WhatsApp splits a message at links, so "Agent Guru
  final verification 2026-10-06." is the Texts "Agent Guru final
  verification ", "2026-10-06" (inside a Hyperlink) and ".". The row also
  holds a Button named "<time> <status> ", e.g. "20:31 Read ", whose own
  Text (the time) is not message text. The chat list on the left repeats
  the last message of each chat inside a DataGrid; those are not messages
  in the open chat.
- The page's tree is exposed only while WhatsApp has been on screen, and
  every subtree appears twice; elements are told apart by runtime id.
- Walking the whole window (about 1,700 elements) takes about 1 s; asking
  UI Automation for all descendants of a type took about 13 s, so the tree
  is walked directly.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)

#: "20:11 Read", "8:05 PM Delivered". The status names follow WhatsApp's own
#: labels; "Pending" is the clock shown before the server has the message.
_STATUS = re.compile(
    r"^\s*\d{1,2}:\d{2}(?:\s*[AaPp]\.?[Mm]\.?)?\s+(Pending|Sent|Delivered|Read)\s*$",
)

#: How deep under a message row its text and status button lie. They were
#: five levels down; this leaves room without walking into another row.
_ROW_DEPTH = 10

#: More than a whole WhatsApp window has; a bound on a tree gone wrong.
_MAX_NODES = 20_000

EDIT, TEXT, BUTTON, DATAGRID, ROW = "edit", "text", "button", "datagrid", "row"


class Node(Protocol):
    """The little of a UI element this module reads."""

    key: Any            # stable identity (UI Automation runtime id)
    kind: str           # EDIT, TEXT, BUTTON, DATAGRID, ROW (a DataItem) or anything else
    name: str
    value: str | None   # Value pattern text, for an Edit
    has_focus: bool

    def children(self) -> list[Node]: ...


@dataclass
class Message:
    """A message in the open chat with the given text."""

    key: Any
    status: str | None  # "pending", "sent", "delivered", "read", or None if not shown


@dataclass
class View:
    """The message box and the open chat's messages that match one text."""

    compose: str | None                  # text in the focused message box; None if none was found
    messages: list[Message] = field(default_factory=list)


def read_view(window: Node, text: str) -> View:
    """The focused message box and the open chat's messages whose text is `text`.

    A message matches when its row's text equals `text` with runs of
    whitespace counted as one. Matching single Text elements found nothing
    for a message containing a link (WhatsApp splits it there), and it took
    the text inside the message box for a message in the chat.
    """
    want = " ".join(text.split())
    compose: str | None = None
    messages: dict[Any, Message] = {}
    seen: set[Any] = set()
    count = 0
    stack: list[tuple[Node, bool]] = [(window, False)]
    while stack and count < _MAX_NODES:
        node, in_chat_list = stack.pop()
        for child in node.children():
            count += 1
            if child.key in seen:
                continue
            seen.add(child.key)
            listed = in_chat_list or child.kind == DATAGRID
            if child.kind == EDIT and child.has_focus and compose is None:
                # An empty message box reports "\n", one with text reports
                # the text alone, so a trailing newline is not text.
                compose = (child.value or "").rstrip("\n")
            elif child.kind == ROW and not listed:
                said, status = _row(child)
                if " ".join(said.split()) == want:
                    messages[child.key] = Message(child.key, status)
            stack.append((child, listed))
    return View(compose, list(messages.values()))


def _row(row: Node) -> tuple[str, str | None]:
    """A message row's text (its Texts in order, not the status button's) and status."""
    parts: list[str] = []
    status: str | None = None
    stack = [(c, 0) for c in reversed(row.children())]
    while stack:
        node, depth = stack.pop()
        if node.kind == BUTTON:
            m = _STATUS.match(node.name)
            if m and status is None:
                status = m.group(1).lower()
            continue
        if node.kind == TEXT:
            parts.append(node.name)
        if depth < _ROW_DEPTH:
            stack.extend((c, depth + 1) for c in reversed(node.children()))
    return "".join(parts), status


# ---------------------------------------------------------------------------
# UI Automation
# ---------------------------------------------------------------------------


class _UiaNode:
    """A UI Automation element seen through the Node interface (raw view)."""

    __slots__ = ("_el", "_uia", "_walker", "has_focus", "key", "kind", "name", "value")

    def __init__(self, el: Any, uia: Any, walker: Any) -> None:
        self._el, self._uia, self._walker = el, uia, walker
        self.key = tuple(el.GetRuntimeId())
        ctype = el.CurrentControlType
        self.kind = {
            uia.UIA_EditControlTypeId: EDIT, uia.UIA_TextControlTypeId: TEXT,
            uia.UIA_ButtonControlTypeId: BUTTON, uia.UIA_DataGridControlTypeId: DATAGRID,
            uia.UIA_DataItemControlTypeId: ROW,
        }.get(ctype, "")
        self.name = el.CurrentName or ""
        self.has_focus = bool(el.CurrentHasKeyboardFocus) if self.kind == EDIT else False
        self.value = None
        if self.kind == EDIT:
            try:
                v = el.GetCurrentPropertyValue(uia.UIA_ValueValuePropertyId)
                self.value = v if isinstance(v, str) else None
            except Exception:
                # An element without a value is just one without text.
                self.value = None

    def children(self) -> list[Any]:
        """The element's children; one that cannot be read ends the list there.

        Right after a send WhatsApp re-renders the chat. On the real send of
        "Agent Guru final verification 2026-10-06 run 2." the first read
        after Enter ran 10.6 s and failed as a whole, so the send was
        reported unchecked although WhatsApp showed it read; a read a
        minute later took 38.5 s, the next ones 1 to 1.6 s. An element that
        goes away while it is being read now costs the rest of its siblings
        on this read, not the read.
        """
        out = []
        try:
            child = self._walker.GetFirstChildElement(self._el)
            while child:
                out.append(_UiaNode(child, self._uia, self._walker))
                child = self._walker.GetNextSiblingElement(child)
        except Exception:
            logger.debug("WhatsApp view: a child element could not be read", exc_info=True)
        return out


def whatsapp_view(text: str) -> View | None:
    """Read WhatsApp Desktop's message box and open chat; None if it cannot be read.

    Blocking (about 1 s); call it from a worker thread.
    """
    try:
        import comtypes.client

        comtypes.client.GetModule("UIAutomationCore.dll")
        from comtypes.gen import UIAutomationClient  # type: ignore[import-not-found]

        auto = comtypes.client.CreateObject(
            UIAutomationClient.CUIAutomation, interface=UIAutomationClient.IUIAutomation,
        )
        walker = auto.RawViewWalker
        el = walker.GetFirstChildElement(auto.GetRootElement())
        while el:
            if (el.CurrentName or "") == "WhatsApp":
                return read_view(_UiaNode(el, UIAutomationClient, walker), text)
            el = walker.GetNextSiblingElement(el)
        logger.info("WhatsApp view: no WhatsApp window")
        return None
    except Exception:
        logger.warning("WhatsApp view could not be read", exc_info=True)
        return None
