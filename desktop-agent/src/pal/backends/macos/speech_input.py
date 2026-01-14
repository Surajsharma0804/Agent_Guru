"""macOS Speech Input stub. Will be implemented in Task 4."""
from typing import Dict
from ...interfaces import SpeechInput, Transcription

class macOSSpeechInput(SpeechInput):
    def start_listening(self) -> None:
        raise NotImplementedError("macOSSpeechInput will be implemented in Task 4")
    def stop_listening(self) -> None:
        raise NotImplementedError("macOSSpeechInput will be implemented in Task 4")
    def transcribe(self, audio_data: bytes) -> Transcription:
        raise NotImplementedError("macOSSpeechInput will be implemented in Task 4")
    def calibrate_microphone(self) -> float:
        raise NotImplementedError("macOSSpeechInput will be implemented in Task 4")
    def get_capabilities(self) -> Dict[str, bool]:
        return {'has_local_processing': True, 'requires_cloud': False, 'supports_wake_word': True, 'supports_continuous': True}
