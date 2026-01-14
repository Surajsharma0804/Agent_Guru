"""iOS Application Controller stub. Will be implemented in Task 6."""
from typing import List, Dict
from ...interfaces import ApplicationController, AppDescriptor

class iOSApplicationController(ApplicationController):
    def open_app(self, app_id: str) -> bool:
        raise NotImplementedError("iOSApplicationController will be implemented in Task 6")
    def close_app(self, app_id: str) -> bool:
        raise NotImplementedError("iOSApplicationController will be implemented in Task 6 - iOS does not allow closing apps")
    def is_running(self, app_id: str) -> bool:
        raise NotImplementedError("iOSApplicationController will be implemented in Task 6")
    def discover_apps(self) -> List[AppDescriptor]:
        raise NotImplementedError("iOSApplicationController will be implemented in Task 6")
    def get_capabilities(self) -> Dict[str, bool]:
        return {'can_open_apps': True, 'can_close_apps': False, 'can_discover_apps': False, 'has_full_control': False}
