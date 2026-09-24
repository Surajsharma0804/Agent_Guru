"""Type stubs for noisereduce."""
from typing import Any, Optional
from numpy.typing import NDArray

def reduce_noise(
    y: NDArray[Any],
    sr: int,
    stationary: bool = False,
    prop_decrease: float = 1.0,
    freq_mask_smooth_hz: int = 500,
    time_mask_smooth_ms: int = 50,
    thresh_n_mult_nonstationary: float = 2.0,
    sigmoid_slope_nonstationary: float = 10.0,
    n_std_thresh_stationary: float = 1.5,
    tmp_folder: Optional[str] = None,
    chunk_size: int = 600000,
    padding: int = 30000,
    n_fft: int = 1024,
    win_length: Optional[int] = None,
    hop_length: Optional[int] = None,
    clip_noise_stationary: bool = True,
    use_tensorflow: bool = False,
    n_jobs: int = 1,
) -> NDArray[Any]: ...
