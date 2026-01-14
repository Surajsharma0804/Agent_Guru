"""macOS Security Enforcer stub. Will be implemented in Task 4."""
from typing import Dict
from ...interfaces import SecurityEnforcer

class macOSSecurityEnforcer(SecurityEnforcer):
    def lock_session(self, reason: str) -> bool:
        raise NotImplementedError("macOSSecurityEnforcer will be implemented in Task 4")
    def get_lock_scope(self) -> str:
        return "screen"
    def get_capabilities(self) -> Dict[str, bool]:
        return {'can_lock_system': False, 'can_lock_screen': True, 'can_lock_app': True, 'has_system_authority': True}
