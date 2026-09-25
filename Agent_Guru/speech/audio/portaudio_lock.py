"""One lock for everything in this process that uses PortAudio.

Recovering a lost microphone sometimes needs PortAudio re-initialised
(``sd._terminate()`` then ``sd._initialize()``): it enumerates devices once,
so a reconnected mic or a new Windows default device is invisible until it
does. That call is process-wide. It destroys every stream PortAudio has open,
not just the dead microphone, and the same PortAudio instance plays the
filler clip, the thinking beep and every spoken answer.

Doing that while another thread was playing was measured on Windows (Intel
Smart Sound laptop, sounddevice 0.5.5, PortAudio 19.7):

- ``sd.play()`` + ``sd.wait()``, one re-initialise: the audio stopped at the
  instant of the re-initialise in 8 of 8 trials, and ``sd.wait()`` returned
  normally, so the caller believed the whole answer had been spoken.
- The same playback against repeated re-initialises (a mic that stays
  unplugged is retried every 10 s): the process died with an access
  violation in 5 of 5 trials.
- A thread writing to an ``OutputStream``: heap corruption
  (0xc0000374) and the process died in 3 of 3 trials.
- Device queries raised ``PortAudioError`` tens of thousands of times.

Re-initialising between two playbacks, on one thread, was clean in every
trial. So the danger is overlap only, and a lock is enough: every PortAudio
user holds it for as long as its stream runs, and the re-initialise only
happens when it can take the lock without waiting.

There is no way to refresh the device list without tearing PortAudio down:
the bundled PortAudio exports no ``Pa_UpdateAvailableDeviceInfo`` or
equivalent.
"""

from __future__ import annotations

import contextlib
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

# Re-entrant: a helper that plays audio may be called from code that already
# holds the lock, and must not deadlock against itself.
_PORTAUDIO_LOCK = threading.RLock()


@contextlib.contextmanager
def portaudio_in_use() -> Iterator[None]:
    """Hold while a PortAudio stream runs or its device list is read.

    The microphone recovery path will not re-initialise PortAudio while this
    is held anywhere in the process.
    """
    with _PORTAUDIO_LOCK:
        yield


def play_and_wait(samples: Any, samplerate: int) -> None:
    """Play *samples* and block until done, safe against microphone recovery."""
    import sounddevice as sd  # type: ignore[import]

    with _PORTAUDIO_LOCK:
        sd.play(samples, samplerate=samplerate)
        sd.wait()


def reinitialise_if_idle() -> bool:
    """Re-initialise PortAudio unless another thread is using it.

    Never waits: if something is playing, this returns False at once, and the
    caller tries again later rather than cutting off, or crashing, what is
    playing.
    """
    if not _PORTAUDIO_LOCK.acquire(blocking=False):
        return False
    try:
        import sounddevice as sd  # type: ignore[import]

        sd._terminate()
        sd._initialize()
        return True
    finally:
        _PORTAUDIO_LOCK.release()
