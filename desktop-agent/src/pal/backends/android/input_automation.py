"""Android Input Automation stub. Will be implemented in Task 5."""
from typing import Optional, Dict
from ...interfaces import InputAutomation, AutomationTarget

class AndroidInputAutomation(InputAutomation):
    def type_text(self, text: str, target: Optional[AutomationTarget] = None) -> bool:
        raise NotImplementedError("AndroidInputAutomation will be implemented in Task 5")
    def click(self, target: AutomationTarget) -> bool:
        raise NotImplementedError("AndroidInputAutomation will be implemented in Task 5")
    def focus_app(self, app_id: str) -> bool:
        raise NotImplementedError("AndroidInputAutomation will be implemented in Task 5")
    def get_capabilities(self) -> Dict[str, bool]:
        return {'can_type_text': True, 'can_click': True, 'can_focus_apps': True, 'has_full_automation': False, 'requires_permission': True}
