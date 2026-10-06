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
- A message in the open chat is a Text element whose name is the message,
  inside a row that also holds a Button named "<time> <status>", e.g.
  "20:11 Read". The chat list on the left repeats the last message of each
  chat inside a DataGrid; those are not messages in the open chat.
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
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger(__name__)

#: "20:11 Read", "8:05 PM Delivered". The status names follow WhatsApp's own
#: labels; "Pending" is the clock shown before the server has the message.
_STATUS = re.compile(
    r"^\s*\d{1,2}:\d{2}(?:\s*[AaPp]\.?[Mm]\.?)?\s+(Pending|Sent|Delivered|Read)\s*$",
)

#: How far above a message's text its row reaches. The status button sat two
#: levels up from the text, in the same row.
_ROW_LEVELS = 4

#: More than a whole WhatsApp window has; a bound on a tree gone wrong.
_MAX_NODES = 20_000

EDIT, TEXT, BUTTON, DATAGRID = "edit", "text", "button", "datagrid"


class Node(Protocol):
    """The little of a UI element this module reads."""

    key: Any            # stable identity (UI Automation runtime id)
    kind: str           # EDIT, TEXT, BUTTON, DATAGRID or anything else
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
    """The focused message box and the open chat's messages whose text is exactly `text`."""
    compose: str | None = None
    messages: dict[Any, Message] = {}
    seen: set[Any] = set()
    count = 0
    stack: list[tuple[Node, tuple[Node, ...], bool]] = [(window, (), False)]
    while stack and count < _MAX_NODES:
        node, ancestors, in_chat_list = stack.pop()
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
            elif child.kind == TEXT and not listed and child.name == text and child.key not in messages:
                messages[child.key] = Message(child.key, _status_near((*ancestors, node)))
            stack.append((child, (*ancestors, node), listed))
    return View(compose, list(messages.values()))


def _status_near(ancestors: tuple[Node, ...]) -> str | None:
    """The status in the row holding a message: a "<time> <status>" button under a near ancestor."""
    for row in reversed(ancestors[-_ROW_LEVELS:]):
        for node in _descendants(row, depth=_ROW_LEVELS + 2):
            if node.kind == BUTTON:
                m = _STATUS.match(node.name)
                if m:
                    return m.group(1).lower()
    return None


def _descendants(node: Node, depth: int) -> Iterator[Node]:
    if depth <= 0:
        return
    for child in node.children():
        yield child
        yield from _descendants(child, depth - 1)


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
        out = []
        child = self._walker.GetFirstChildElement(self._el)
        while child:
            out.append(_UiaNode(child, self._uia, self._walker))
            child = self._walker.GetNextSiblingElement(child)
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
