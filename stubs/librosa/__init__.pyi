"""Type stubs for librosa (audio analysis library)."""
from typing import Any

import numpy as np

def load(
    path: str,
    sr: int | None = 22050,
    mono: bool = True,
    offset: float = 0.0,
    duration: float | None = None,
) -> tuple[np.ndarray, int]: ...

def stft(
    y: np.ndarray,
    n_fft: int = 2048,
    hop_length: int | None = None,
    **kwargs: Any,
) -> np.ndarray: ...

def piptrack(
    y: np.ndarray | None = None,
    sr: int = 22050,
    S: np.ndarray | None = None,
    **kwargs: Any,
) -> tuple[np.ndarray, np.ndarray]: ...

class beat:
    @staticmethod
    def beat_track(
        y: np.ndarray | None = None,
        sr: int = 22050,
        **kwargs: Any,
    ) -> tuple[Any, np.ndarray]: ...

class feature:
    @staticmethod
    def mfcc(
        y: np.ndarray | None = None,
        sr: int = 22050,
        n_mfcc: int = 20,
        **kwargs: Any,
    ) -> np.ndarray: ...

    @staticmethod
    def rms(
        y: np.ndarray | None = None,
        **kwargs: Any,
    ) -> np.ndarray: ...

    @staticmethod
    def zero_crossing_rate(
        y: np.ndarray,
        **kwargs: Any,
    ) -> np.ndarray: ...

    @staticmethod
    def spectral_centroid(
        y: np.ndarray | None = None,
        sr: int = 22050,
        **kwargs: Any,
    ) -> np.ndarray: ...

    @staticmethod
    def spectral_rolloff(
        y: np.ndarray | None = None,
        sr: int = 22050,
        **kwargs: Any,
    ) -> np.ndarray: ...

    @staticmethod
    def spectral_bandwidth(
        y: np.ndarray | None = None,
        sr: int = 22050,
        **kwargs: Any,
    ) -> np.ndarray: ...
