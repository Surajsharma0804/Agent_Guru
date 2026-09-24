"""Type stubs for sounddevice."""
from typing import Any, Optional, Callable, Dict
from numpy.typing import NDArray

def query_devices(device: Optional[int] = None, kind: Optional[str] = None) -> Any: ...

def rec(
    frames: int,
    samplerate: int,
    channels: int = 1,
    dtype: str = "float32",
    device: Optional[int] = None,
    blocking: bool = False,
) -> NDArray[Any]: ...

def wait() -> None: ...

def info() -> Dict[str, Any]: ...

class InputStream:
    def __init__(
        self,
        samplerate: int,
        channels: int = 1,
        dtype: str = "float32",
        callback: Optional[Callable[[NDArray[Any], int, Any, Any], None]] = None,
        blocksize: int = 0,
        device: Optional[int] = None,
        latency: Optional[float] = None,
    ) -> None: ...
    
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def close(self) -> None: ...
    def __enter__(self) -> "InputStream": ...
    def __exit__(self, *args: Any) -> None: ...
