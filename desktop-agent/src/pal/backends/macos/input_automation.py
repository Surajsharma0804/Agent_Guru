"""macOS Input Automation stub. Will be implemented in Task 4."""
from typing import Optional, Dict
from ...interfaces import InputAutomation, AutomationTarget

class macOSInputAutomation(InputAutomation):
    def type_text(self, text: str, target: Optional[AutomationTarget] = None) -> bool:
        raise NotImplementedError("macOSInputAutomation will be implemented in Task 4")
    def click(self, target: AutomationTarget) -> bool:
        raise NotImplementedError("macOSInputAutomation will be implemented in Task 4")
    def focus_app(self, app_id: str) -> bool:
        raise NotImplementedError("macOSInputAutomation will be implemented in Task 4")
    def get_capabilities(self) -> Dict[str, bool]:
        return {'can_type_text': True, 'can_click': True, 'can_focus_apps': True, 'has_full_automation': True, 'requires_permission': True}
