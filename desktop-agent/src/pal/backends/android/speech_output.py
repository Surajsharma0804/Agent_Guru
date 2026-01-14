"""Android Speech Output stub. Will be implemented in Task 5."""
from typing import Dict
from ...interfaces import SpeechOutput, TTSPriority

class AndroidSpeechOutput(SpeechOutput):
    def speak(self, text: str, priority: TTSPriority = TTSPriority.NORMAL, interrupt: bool = False) -> None:
        raise NotImplementedError("AndroidSpeechOutput will be implemented in Task 5")
    def stop(self) -> None:
        raise NotImplementedError("AndroidSpeechOutput will be implemented in Task 5")
    def is_speaking(self) -> bool:
        raise NotImplementedError("AndroidSpeechOutput will be implemented in Task 5")
    def set_volume(self, volume: int) -> None:
        raise NotImplementedError("AndroidSpeechOutput will be implemented in Task 5")
    def set_rate(self, rate: int) -> None:
        raise NotImplementedError("AndroidSpeechOutput will be implemented in Task 5")
    def get_capabilities(self) -> Dict[str, bool]:
        return {'has_priority_queue': True, 'can_interrupt': True, 'can_control_volume': True, 'can_control_rate': True}
