"""Type stubs for soundfile."""
from typing import Any, Optional, Tuple
import numpy as np
from numpy.typing import NDArray

class SoundFileInfo:
    duration: float
    samplerate: int
    channels: int
    format: str
    subtype: str

def read(
    file: str,
    frames: int = -1,
    start: int = 0,
    stop: Optional[int] = None,
    dtype: str = "float64",
    always_2d: bool = False,
    fill_value: Optional[float] = None,
    out: Optional[NDArray[Any]] = None,
    samplerate: Optional[int] = None,
    channels: Optional[int] = None,
    format: Optional[str] = None,
    subtype: Optional[str] = None,
    endian: Optional[str] = None,
    closefd: bool = True,
) -> Tuple[NDArray[Any], int]: ...

def write(
    file: str,
    data: NDArray[Any],
    samplerate: int,
    subtype: Optional[str] = None,
    endian: Optional[str] = None,
    format: Optional[str] = None,
    closefd: bool = True,
) -> None: ...

def info(file: str) -> SoundFileInfo: ...
