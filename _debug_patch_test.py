"""Debug script to understand why patch.object isn't working."""
import sys
from unittest.mock import MagicMock, patch

mock_jnius = MagicMock()
with patch.dict('sys.modules', {'jnius': mock_jnius}):
    mock_jnius.autoclass = MagicMock()
    mock_jnius.cast = MagicMock()
    from Agent_Guru.platform.android.integration import (
        AndroidIntegration, AndroidIntegrationError
    )

import Agent_Guru.platform.android.integration as _integration_mod

print("=== Module identity check ===")
print(f"_integration_mod id: {id(_integration_mod)}")
print(f"sys.modules entry id: {id(sys.modules.get('Agent_Guru.platform.android.integration'))}")
print(f"Same? {_integration_mod is sys.modules.get('Agent_Guru.platform.android.integration')}")
print(f"__init__.__globals__ is _integration_mod.__dict__: {AndroidIntegration.__init__.__globals__ is _integration_mod.__dict__}")
print(f"ANDROID_AVAILABLE: {_integration_mod.ANDROID_AVAILABLE}")
print(f"_is_android_available(): {_integration_mod._is_android_available()}")

print("\n=== Patching test ===")
with patch.object(_integration_mod, '_is_android_available', return_value=False):
    fn_in_globals = AndroidIntegration.__init__.__globals__['_is_android_available']
    print(f"fn in globals type: {type(fn_in_globals)}")
    print(f"fn in globals call: {fn_in_globals()}")
    print(f"_integration_mod._is_android_available(): {_integration_mod._is_android_available()}")
    try:
        obj = AndroidIntegration()
        print("NO RAISE - obj created, context:", obj.context)
    except AndroidIntegrationError as e:
        print(f"RAISED AndroidIntegrationError: {e}")
    except Exception as e:
        print(f"RAISED other: {type(e).__name__}: {e}")
