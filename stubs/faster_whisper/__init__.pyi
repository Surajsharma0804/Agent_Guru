"""Type stubs for faster_whisper."""
from typing import Any, Iterator, Optional, Tuple, List, Union
import numpy as np

class WhisperModel:
    def __init__(
        self,
        model_size_or_path: str,
        device: str = "auto",
        device_index: Union[int, List[int]] = 0,
        compute_type: str = "default",
        cpu_threads: int = 0,
        num_workers: int = 1,
        download_root: Optional[str] = None,
        local_files_only: bool = False,
    ) -> None: ...
    
    def transcribe(
        self,
        audio: Union[str, np.ndarray[Any, Any]],
        language: Optional[str] = None,
        task: str = "transcribe",
        beam_size: int = 5,
        best_of: int = 5,
        patience: float = 1.0,
        length_penalty: float = 1.0,
        temperature: Union[float, List[float], Tuple[float, ...]] = 0.0,
        compression_ratio_threshold: Optional[float] = 2.4,
        log_prob_threshold: Optional[float] = -1.0,
        no_speech_threshold: Optional[float] = 0.6,
        condition_on_previous_text: bool = True,
        initial_prompt: Optional[str] = None,
        prefix: Optional[str] = None,
        suppress_blank: bool = True,
        suppress_tokens: Optional[List[int]] = None,
        without_timestamps: bool = False,
        max_initial_timestamp: float = 1.0,
        word_timestamps: bool = False,
        prepend_punctuations: str = "\"'([{-",
        append_punctuations: str = "\"'.,:)]}",
        vad_filter: bool = False,
        vad_parameters: Optional[dict[str, Any]] = None,
    ) -> Tuple[Iterator[Any], Any]: ...

class BatchedInferencePipeline:
    def __init__(self, model: WhisperModel) -> None: ...
