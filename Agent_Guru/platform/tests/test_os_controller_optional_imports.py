"""A controller module that fails to import disables only its own controllers."""

import importlib
import sys

import Agent_Guru.platform as platform_package
from Agent_Guru.platform import os_controller as original_os_controller


class _NoDisplay:
    """What importing pyautogui does on Linux with no display: mouseinfo reads os.environ['DISPLAY']."""

    def find_spec(self, name, path=None, target=None):
        if name == "pyautogui":
            missing = "DISPLAY"
            raise KeyError(missing)


def test_a_controller_failing_with_a_non_import_error_disables_only_itself(monkeypatch):
    # Before the fix this re-import raised KeyError('DISPLAY'): on the CI
    # runner OSController could not be imported at all, and two test modules
    # failed to collect, which stopped the whole Python 3.13 run.
    monkeypatch.setattr(sys, "meta_path", [_NoDisplay(), *sys.meta_path])
    for name in ("pyautogui", "Agent_Guru.platform.controllers.input_control", "Agent_Guru.platform.os_controller"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setattr(platform_package, "os_controller", original_os_controller)

    fresh = importlib.import_module("Agent_Guru.platform.os_controller")

    assert (fresh.KeyboardController, fresh.MouseController) == (None, None)  # nosec B101
    assert fresh.FileOperationsController is not None  # nosec B101
