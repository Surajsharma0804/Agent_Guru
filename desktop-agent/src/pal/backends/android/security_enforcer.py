"""Android Security Enforcer stub. Will be implemented in Task 5."""
from typing import Dict
from ...interfaces import SecurityEnforcer

class AndroidSecurityEnforcer(SecurityEnforcer):
    def lock_session(self, reason: str) -> bool:
        raise NotImplementedError("AndroidSecurityEnforcer will be implemented in Task 5")
    def get_lock_scope(self) -> str:
        return "app"
    def get_capabilities(self) -> Dict[str, bool]:
        return {'can_lock_system': False, 'can_lock_screen': False, 'can_lock_app': True, 'has_system_authority': False}
