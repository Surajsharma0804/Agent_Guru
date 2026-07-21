"""Type stubs for openwakeword.model."""
from typing import Any

class Model:
    def __init__(
        self,
        wakeword_models: list[str] | None = None,
        inference_framework: str = "onnx",
        **kwargs: Any,
    ) -> None: ...
    def predict(self, audio_data: Any) -> dict[str, float]: ...
    def reset(self) -> None: ...
