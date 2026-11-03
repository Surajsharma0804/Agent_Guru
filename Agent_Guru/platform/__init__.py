"""Platform Integration System for Agent Guru.

This package provides comprehensive cross-platform OS control, hardware abstraction,
and permission management for the AGENT_GURU AI operating system.

Modules:
    windows: Windows-specific integration using pywin32
    macos: macOS-specific integration using pyobjc
    linux: Linux-specific integration using dbus-python
    android: Android-specific integration using pyjnius
    ios: iOS-specific integration using pyobjus
    hardware: Cross-platform hardware monitoring using psutil and GPUtil
    permissions: Permission validation and management
    controllers: Specialized controllers for various operations
    mobile: Mobile-specific functionality and background services

The system abstracts platform-specific operations behind common interfaces,
allowing AGENT_GURU to control system functions, monitor hardware, and manage
permissions without needing to understand the underlying OS implementation details.

Performance Targets:
    - Platform detection: <10ms
    - Hardware queries: <1s
    - Permission checks: <100ms
    - Command execution: Platform-dependent

Architecture:
    The system uses a strategy pattern where platform-specific implementations
    are abstracted behind common interfaces, with specialized controllers for
    each operation category.
"""

import sys as _sys

if __name__ == "platform":
    # This folder has the same name as the standard library's platform
    # module. When the Agent_Guru folder itself is on sys.path, which is
    # what `python -m pytest`, `python -c` or `python -m <anything>` do when
    # started from inside it, `import platform` found this package instead.
    # The first caller that needed the real module then failed: pytest
    # crashed while loading its plugins with "module 'platform' has no
    # attribute 'python_implementation'", before any test ran, while the
    # same command from the repository root passed.
    #
    # Renaming the package would have been the clean fix, but 121 files in
    # the package and 18 outside it (build spec, installers, scripts,
    # docs) name Agent_Guru.platform. Instead, when this file is imported
    # under the bare name, it loads the standard library module from every
    # sys.path entry except the folder that holds this package, and puts
    # that module in sys.modules. The import system hands back whatever is
    # in sys.modules once this file finishes, so every `import platform`
    # gets the real module. Imported as Agent_Guru.platform, as the
    # application does, none of this runs.
    import importlib.machinery as _machinery
    import os as _os
    from importlib.util import module_from_spec as _module_from_spec

    _shadowing_dir = _os.path.normcase(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    _search_path = [
        entry
        for entry in _sys.path
        if _os.path.normcase(_os.path.abspath(entry or _os.getcwd())) != _shadowing_dir
    ]
    _spec = _machinery.PathFinder.find_spec("platform", _search_path)
    if _spec is None or _spec.loader is None:
        raise ImportError(
            "the standard library platform module was not found outside "
            f"{_shadowing_dir}, which holds the Agent_Guru.platform package"
        )
    _stdlib_platform = _module_from_spec(_spec)
    _sys.modules["platform"] = _stdlib_platform
    _spec.loader.exec_module(_stdlib_platform)
else:
    __version__ = "1.0.0"

    __all__: list[str] = []
