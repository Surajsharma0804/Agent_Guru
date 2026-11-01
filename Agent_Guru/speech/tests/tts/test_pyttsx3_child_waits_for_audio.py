"""The pyttsx3 child process waits for its WAV file before it exits.

pyttsx3 2.99's eSpeak driver can return from runAndWait() before eSpeak's own thread has written the
file, and the child process exited with an empty file: the fallback voice then played silence. On
Linux under CPU load that happened in 9 runs of 10 of the audio quality test. Here a stand-in
pyttsx3 returns from runAndWait() at once and writes the file half a second later from a daemon
thread, as eSpeak's callback thread does, so the race is the same every time and needs no eSpeak.
"""

from __future__ import annotations

import subprocess  # nosec B404 - runs this interpreter on a fixed script
import sys
import textwrap
import wave

from Agent_Guru.speech.tts.tts_engine import _PYTTSX3_SCRIPT

FAKE_PYTTSX3 = textwrap.dedent('''
    import threading, time, wave

    class _Engine:
        def setProperty(self, name, value):
            pass

        def save_to_file(self, text, path):
            self._text, self._path = text, path

        def runAndWait(self):
            def write():
                time.sleep(0.5)
                with wave.open(self._path, "wb") as f:
                    f.setnchannels(1)
                    f.setsampwidth(2)
                    f.setframerate(22050)
                    f.writeframes(b"\\x10\\x00" * 2205)
            threading.Thread(target=write, daemon=True).start()

    def init():
        return _Engine()
''')


def test_the_child_waits_for_a_file_written_after_run_and_wait_returns(tmp_path):
    (tmp_path / "pyttsx3.py").write_text(FAKE_PYTTSX3, encoding="utf-8")
    out = tmp_path / "out.wav"
    out.write_bytes(b"")  # the caller creates the file with mkstemp before the child runs
    done = subprocess.run(  # nosec B603 - this interpreter, fixed script, no shell
        [sys.executable, "-c", _PYTTSX3_SCRIPT, str(out), "", "160", "1.0", ""],
        input=b"Hello there.", capture_output=True, timeout=30, check=False,
        env={"PYTHONPATH": str(tmp_path), "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")},
    )
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")[-300:]  # nosec B101
    with wave.open(str(out), "rb") as f:
        assert f.getnframes() == 2205  # nosec B101
