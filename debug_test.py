import sys
from unittest.mock import MagicMock, patch

mock_jnius = MagicMock()
mock_autoclass = MagicMock()
mock_cast = MagicMock()

with patch.dict(sys.modules, {'jnius': mock_jnius}):
    mock_jnius.autoclass = mock_autoclass
    mock_jnius.cast = mock_cast
    
    from Agent_Guru.platform.android.integration import (
        AndroidIntegration,
        AndroidIntegrationError,
    )

import Agent_Guru.platform.android.integration as android_mod
print('Module ANDROID_AVAILABLE:', android_mod.ANDROID_AVAILABLE)
print('Same dict?', android_mod.__dict__ is AndroidIntegration.__init__.__globals__)
print('__globals__ ANDROID_AVAILABLE:', AndroidIntegration.__init__.__globals__['ANDROID_AVAILABLE'])

android_mod.ANDROID_AVAILABLE = False
print('After set - Module:', android_mod.ANDROID_AVAILABLE)
print('After set - __globals__:', AndroidIntegration.__init__.__globals__['ANDROID_AVAILABLE'])

try:
    ai = AndroidIntegration()
    print('ERROR: No exception raised!')
except AndroidIntegrationError as e:
    print('OK: Got expected error:', e)
except Exception as e:
    print('UNEXPECTED:', type(e).__name__, e)
