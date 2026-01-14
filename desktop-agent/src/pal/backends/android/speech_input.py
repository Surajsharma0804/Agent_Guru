"""Android Speech Input stub. Will be implemented in Task 5."""
from typing import Dict
from ...interfaces import SpeechInput, Transcription

class AndroidSpeechInput(SpeechInput):
    def start_listening(self) -> None:
        raise NotImplementedError("AndroidSpeechInput will be implemented in Task 5")
    def stop_listening(self) -> None:
        raise NotImplementedError("AndroidSpeechInput will be implemented in Task 5")
    def transcribe(self, audio_data: bytes) -> Transcription:
        raise NotImplementedError("AndroidSpeechInput will be implemented in Task 5")
    def calibrate_microphone(self) -> float:
        raise NotImplementedError("AndroidSpeechInput will be implemented in Task 5")
    def get_capabilities(self) -> Dict[str, bool]:
        return {'has_local_processing': True, 'requires_cloud': False, 'supports_wake_word': True, 'supports_continuous': True}
