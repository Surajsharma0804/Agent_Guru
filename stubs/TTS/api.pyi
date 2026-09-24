"""Type stubs for TTS.api."""
from typing import Any, Optional, List
from numpy.typing import NDArray

class TTS:
    def __init__(
        self,
        model_name: Optional[str] = None,
        model_path: Optional[str] = None,
        config_path: Optional[str] = None,
        vocoder_path: Optional[str] = None,
        vocoder_config_path: Optional[str] = None,
        progress_bar: bool = True,
        gpu: bool = False,
    ) -> None: ...
    
    @property
    def speakers(self) -> Optional[List[str]]: ...
    
    def to(self, device: str) -> "TTS": ...
    
    def tts(
        self,
        text: str,
        speaker: Optional[str] = None,
        language: Optional[str] = None,
        speaker_wav: Optional[str] = None,
        emotion: Optional[str] = None,
        speed: float = 1.0,
    ) -> NDArray[Any]: ...
    
    def tts_to_file(
        self,
        text: str,
        file_path: str,
        speaker: Optional[str] = None,
        language: Optional[str] = None,
        speaker_wav: Optional[str] = None,
        emotion: Optional[str] = None,
        speed: float = 1.0,
    ) -> str: ...
