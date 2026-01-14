"""iOS Speech Input stub. Will be implemented in Task 6."""
from typing import Dict
from ...interfaces import SpeechInput, Transcription

class iOSSpeechInput(SpeechInput):
    def start_listening(self) -> None:
        raise NotImplementedError("iOSSpeechInput will be implemented in Task 6")
    def stop_listening(self) -> None:
        raise NotImplementedError("iOSSpeechInput will be implemented in Task 6")
    def transcribe(self, audio_data: bytes) -> Transcription:
        raise NotImplementedError("iOSSpeechInput will be implemented in Task 6")
    def calibrate_microphone(self) -> float:
        raise NotImplementedError("iOSSpeechInput will be implemented in Task 6")
    def get_capabilities(self) -> Dict[str, bool]:
        return {'has_local_processing': False, 'requires_cloud': True, 'supports_wake_word': False, 'supports_continuous': True}
