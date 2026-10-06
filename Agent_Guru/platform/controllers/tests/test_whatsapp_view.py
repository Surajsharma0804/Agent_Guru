"""Reading WhatsApp Desktop's message box and open chat from its accessibility tree.

The shapes here are the ones measured on WhatsApp Desktop for Windows
(WebView2): the message box is the Edit holding keyboard focus and reports
"\n" when empty; a message is a Text whose name is its text, in a row with a
"<time> <status>" button; the chat list repeats each chat's last message
inside a DataGrid; every subtree appears twice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from Agent_Guru.platform.controllers.whatsapp_view import BUTTON, DATAGRID, EDIT, TEXT, read_view

_keys = iter(range(1, 10_000))


@dataclass
class N:
    kind: str = ""
    name: str = ""
    value: str | None = None
    has_focus: bool = False
    kids: list[Any] = field(default_factory=list)
    key: Any = None

    def __post_init__(self):
        if self.key is None:
            self.key = next(_keys)

    def children(self):
        return self.kids


def bubble(text, status_button, key=None):
    """A message row as WhatsApp shows it: the text, and next to it the time and status."""
    t = N(TEXT, text, key=key)
    return N(kids=[N(kids=[N(kids=[t]), N(kids=[N(BUTTON, status_button)])])])


def window(*conversation, compose="\n", chat_list=()):
    box = N(EDIT, "Type to John", value=compose, has_focus=True)
    search = N(EDIT, "Search or start a new chat", value="", has_focus=False)
    grid = N(DATAGRID, "Chat list", kids=[N(kids=[N(TEXT, t)]) for t in chat_list])
    return N(kids=[N(kids=[search, grid]), N(kids=[*conversation, box])])


def test_the_focused_box_is_the_message_box_and_newline_means_empty():
    assert read_view(window(), "hi").compose == ""  # nosec B101
    assert read_view(window(compose="hi"), "hi").compose == "hi"  # nosec B101


def test_no_focused_box_reads_as_none():
    win = N(kids=[N(EDIT, "Search", value="", has_focus=False)])
    assert read_view(win, "hi").compose is None  # nosec B101


def test_a_message_and_its_status_are_found():
    view = read_view(window(bubble("I'll reach in 10 minutes", "20:11 Read")), "I'll reach in 10 minutes")
    assert [m.status for m in view.messages] == ["read"]  # nosec B101


def test_only_exact_text_matches():
    view = read_view(window(bubble("I'll reach in 10 minutes, sorry", "20:11 Sent")), "I'll reach in 10 minutes")
    assert view.messages == []  # nosec B101


def test_the_chat_list_preview_is_not_a_message_in_the_chat():
    view = read_view(window(chat_list=["hello"]), "hello")
    assert view.messages == []  # nosec B101


def test_a_repeated_subtree_counts_once():
    text_key = ("runtime", 7)
    row = bubble("hello", "9:05 Delivered", key=text_key)
    view = read_view(N(kids=[N(kids=[row]), N(kids=[row])]), "hello")
    assert [m.status for m in view.messages] == ["delivered"]  # nosec B101


def test_status_forms():
    for button, status in (("20:11 Pending", "pending"), ("8:05 PM Sent", "sent"),
                           ("8:05 p.m. Delivered", "delivered"), ("12:00 Read", "read")):
        view = read_view(window(bubble("x y z", button)), "x y z")
        assert [m.status for m in view.messages] == [status], button  # nosec B101


def test_a_message_without_a_status_button_has_no_status():
    view = read_view(window(bubble("hello", "Reply")), "hello")
    assert [m.status for m in view.messages] == [None]  # nosec B101
