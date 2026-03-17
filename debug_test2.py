import sys
from unittest.mock import MagicMock, patch

# Block the full package import
sys.modules['Agent_Guru'] = MagicMock()
sys.modules['Agent_Guru.platform'] = MagicMock()
sys.modules['Agent_Guru.platform.android'] = MagicMock()

mock_jnius = MagicMock()
mock_autoclass = MagicMock()
mock_cast = MagicMock()
sys.modules['jnius'] = mock_jnius
mock_jnius.autoclass = mock_autoclass
mock_jnius.cast = mock_cast

# Now import just the integration module directly
import importlib.util
spec = importlib.util.spec_from_file_location(
    "Agent_Guru.platform.android.integration",
    "Agent_Guru/platform/android/integration.py"
)
mod = importlib.util.module_from_spec(spec)
sys.modules["Agent_Guru.platform.android.integration"] = mod
spec.loader.exec_module(mod)

AndroidIntegration = mod.AndroidIntegration
AndroidIntegrationError = mod.AndroidIntegrationError

print('Module ANDROID_AVAILABLE:', mod.ANDROID_AVAILABLE)
print('Same dict?', mod.__dict__ is AndroidIntegration.__init__.__globals__)
print('__globals__ ANDROID_AVAILABLE:', AndroidIntegration.__init__.__globals__['ANDROID_AVAILABLE'])

mod.ANDROID_AVAILABLE = False
print('After set - Module:', mod.ANDROID_AVAILABLE)
print('After set - __globals__:', AndroidIntegration.__init__.__globals__['ANDROID_AVAILABLE'])

try:
    ai = AndroidIntegration()
    print('ERROR: No exception raised!')
except AndroidIntegrationError as e:
    print('OK: Got expected error:', e)
except Exception as e:
    print('UNEXPECTED:', type(e).__name__, e)
