"""macOS Application Controller stub. Will be implemented in Task 4."""
from typing import List, Dict
from ...interfaces import ApplicationController, AppDescriptor

class macOSApplicationController(ApplicationController):
    def open_app(self, app_id: str) -> bool:
        raise NotImplementedError("macOSApplicationController will be implemented in Task 4")
    def close_app(self, app_id: str) -> bool:
        raise NotImplementedError("macOSApplicationController will be implemented in Task 4")
    def is_running(self, app_id: str) -> bool:
        raise NotImplementedError("macOSApplicationController will be implemented in Task 4")
    def discover_apps(self) -> List[AppDescriptor]:
        raise NotImplementedError("macOSApplicationController will be implemented in Task 4")
    def get_capabilities(self) -> Dict[str, bool]:
        return {'can_open_apps': True, 'can_close_apps': True, 'can_discover_apps': True, 'has_full_control': True}
