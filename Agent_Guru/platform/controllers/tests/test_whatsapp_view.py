"""Reading WhatsApp Desktop's message box and open chat from its accessibility tree.

The shapes here are the ones measured on WhatsApp Desktop for Windows
(WebView2): the message box is the Edit holding keyboard focus and reports
"\n" when empty; a message is a DataItem row whose Texts, in order, are its
text (split at links), beside a "You:" label and a "<time> <status> " button
holding the time as a Text; the chat list repeats each chat's last message
inside a DataGrid; every subtree appears twice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from Agent_Guru.platform.controllers.whatsapp_view import BUTTON, DATAGRID, EDIT, ROW, TEXT, read_view

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


def bubble(text, status_button, key=None, parts=None):
    """A message row as WhatsApp shows it: "You:", the text, then the time and status."""
    texts = [N(TEXT, p) for p in (parts or [text])]
    time = status_button.split()[0]
    button = N(BUTTON, status_button, kids=[N(TEXT, time), N(kids=[N(kind="image", name="wds-ic-read")])])
    return N(ROW, key=key, kids=[N(kids=[N(kids=[N(name="You:"), N(kids=texts), N(kids=[button])])])])


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
    row = bubble("hello", "9:05 Delivered", key=("runtime", 7))
    view = read_view(N(kids=[N(kids=[row]), N(kids=[row])]), "hello")
    assert [m.status for m in view.messages] == ["delivered"]  # nosec B101


def test_status_forms():
    for button, status in (("20:11 Pending", "pending"), ("8:05 PM Sent", "sent"), ("20:31 Read ", "read"),
                           ("8:05 p.m. Delivered", "delivered"), ("12:00 Read", "read")):
        view = read_view(window(bubble("x y z", button)), "x y z")
        assert [m.status for m in view.messages] == [status], button  # nosec B101


def test_a_message_without_a_status_button_has_no_status():
    view = read_view(window(bubble("hello", "Reply")), "hello")
    assert [m.status for m in view.messages] == [None]  # nosec B101


def test_a_message_split_at_a_link_is_read_whole():
    # Measured: "Agent Guru final verification 2026-10-06." came as three Texts,
    # the date inside a Hyperlink. Matching single Texts found nothing.
    link = N(kind="hyperlink", name="2026-10-06", kids=[N(TEXT, "2026-10-06")])
    row = bubble("", "20:31 Read ", parts=["Agent Guru final verification "])
    row.kids[0].kids[0].kids[1].kids += [link, N(TEXT, ".")]
    view = read_view(window(row), "Agent Guru final verification 2026-10-06.")
    assert [m.status for m in view.messages] == ["read"]  # nosec B101


def test_text_in_the_message_box_is_not_a_message():
    # Before sending, the box's own text was taken for a message in the chat.
    box = N(EDIT, "Type to John", value="hello", has_focus=True, kids=[N(TEXT, "hello")])
    view = read_view(N(kids=[N(kids=[box])]), "hello")
    assert view.compose == "hello" and view.messages == []  # nosec B101


def test_the_label_and_the_time_are_not_part_of_the_text():
    view = read_view(window(bubble("see you at 5", "17:02 Sent")), "see you at 5")
    assert [m.status for m in view.messages] == ["sent"]  # nosec B101


def test_an_element_that_goes_away_mid_read_does_not_fail_the_read():
    # Right after a send WhatsApp re-renders the chat; the first read after
    # Enter failed as a whole on the real app and the send went unchecked.
    from types import SimpleNamespace

    from Agent_Guru.platform.controllers.whatsapp_view import _UiaNode

    uia = SimpleNamespace(
        UIA_EditControlTypeId=1, UIA_TextControlTypeId=2, UIA_ButtonControlTypeId=3,
        UIA_DataGridControlTypeId=4, UIA_DataItemControlTypeId=5, UIA_ValueValuePropertyId=6,
    )

    class El:
        def __init__(self, n):
            self.n = n
            self.CurrentControlType, self.CurrentName, self.CurrentHasKeyboardFocus = 2, f"t{n}", 0

        def GetRuntimeId(self):
            return [self.n]

    class Walker:
        def GetFirstChildElement(self, el):
            return El(1) if el.n == 0 else None

        def GetNextSiblingElement(self, el):
            if el.n == 2:
                raise OSError("element not available")  # comtypes raises COMError here
            return El(el.n + 1)

    kids = _UiaNode(El(0), uia, Walker()).children()
    assert [k.name for k in kids] == ["t1", "t2"]  # nosec B101
