"""iOS Input Automation stub. Will be implemented in Task 6."""
from typing import Optional, Dict
from ...interfaces import InputAutomation, AutomationTarget

class iOSInputAutomation(InputAutomation):
    def type_text(self, text: str, target: Optional[AutomationTarget] = None) -> bool:
        raise NotImplementedError("iOSInputAutomation will be implemented in Task 6 - iOS severely restricts automation")
    def click(self, target: AutomationTarget) -> bool:
        raise NotImplementedError("iOSInputAutomation will be implemented in Task 6 - iOS does not allow clicking")
    def focus_app(self, app_id: str) -> bool:
        raise NotImplementedError("iOSInputAutomation will be implemented in Task 6")
    def get_capabilities(self) -> Dict[str, bool]:
        return {'can_type_text': False, 'can_click': False, 'can_focus_apps': False, 'has_full_automation': False, 'requires_permission': False}
