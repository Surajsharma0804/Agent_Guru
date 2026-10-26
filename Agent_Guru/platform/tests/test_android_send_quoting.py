"""What the phone's shell receives when a message is opened on Android through adb.

`adb shell` joins its arguments into one line for /system/bin/sh. The link's
"&text=" ended the command there, and a contact that was not all digits ran
as shell text. adb is not run here: its argument list is recorded, and the
remote line is split the way sh splits words (shlex, POSIX rules).
"""

from __future__ import annotations

import asyncio
import shlex
import urllib.parse

import pytest

from Agent_Guru.platform.controllers import messaging_controller
from Agent_Guru.platform.controllers.messaging_controller import MessagingController


@pytest.fixture
def adb(monkeypatch, tmp_path):
    seen: list[tuple[str, ...]] = []

    class Done:
        returncode = 0

        async def wait(self):
            return 0

    async def record(*argv, **kwargs):
        seen.append(argv)
        return Done()

    monkeypatch.setattr(messaging_controller.asyncio, "create_subprocess_exec", record)
    return MessagingController(platform_override="android", contacts_path_override=tmp_path / "c.json"), seen


def _words(argv):
    assert argv[:2] == ("adb", "shell") and len(argv) == 3  # nosec B101  one line for the remote shell
    return shlex.split(argv[2])


def test_the_whole_link_reaches_am_start(adb):
    controller, seen = adb
    assert asyncio.run(controller._send_android_whatsapp("+91 99999 99999", "Running late & sorry")) is True  # nosec B101
    words = _words(seen[0])
    link = words[words.index("-d") + 1]
    assert link == "whatsapp://send?phone=919999999999&text=" + urllib.parse.quote("Running late & sorry")  # nosec B101


@pytest.mark.parametrize("contact", ["x;rm -rf /sdcard", "x$(reboot)", "x`id`", "x && reboot", "x|sh"])
def test_a_contact_is_one_argument_not_shell_text(adb, contact):
    controller, seen = adb
    asyncio.run(controller._send_android_whatsapp(contact, "hi"))
    words = _words(seen[0])
    # Exactly the words am start takes; the contact stays inside the link.
    assert words[:4] == ["am", "start", "-a", "android.intent.action.VIEW"] and words[4] == "-d"  # nosec B101
    assert words[5].startswith(f"whatsapp://send?phone={contact}&text=") and len(words) <= 8  # nosec B101
