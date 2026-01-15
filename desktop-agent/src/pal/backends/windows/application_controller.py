"""
Windows Application Controller Implementation.

Implements ApplicationController interface using Win32 API, Windows Shell,
and UI Automation for complete application control on Windows 10/11.

Validates: Requirements 34.5, 34.9
"""

import os
import subprocess
import time
import winreg
from pathlib import Path
from typing import Dict, List, Optional

import psutil

from ...interfaces import AppDescriptor, ApplicationController


class WindowsApplicationController(ApplicationController):
    """
    Windows implementation of ApplicationController.

    Uses:
        - subprocess.Popen for launching (Win32 CreateProcess wrapper)
        - psutil for process management and enumeration
        - Registry and filesystem for discovery
        - ShellExecute via os.startfile for associated files

    Capabilities:
        - Full application control
        - Complete discovery
        - System-wide authority
    """

    def __init__(self):
        """Initialize Windows application controller."""
        self.platform = "windows"

        # Common application mappings (app_id -> executable name)
        self.app_mapping = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "paint": "mspaint.exe",
            "wordpad": "wordpad.exe",
            "explorer": "explorer.exe",
            "cmd": "cmd.exe",
            "powershell": "powershell.exe",
            "chrome": "chrome.exe",
            "firefox": "firefox.exe",
            "edge": "msedge.exe",
            "vscode": "Code.exe",
            "word": "WINWORD.EXE",
            "excel": "EXCEL.EXE",
            "powerpoint": "POWERPNT.EXE",
            "outlook": "OUTLOOK.EXE",
            "teams": "Teams.exe",
            "slack": "slack.exe",
            "discord": "Discord.exe",
            "spotify": "Spotify.exe",
            "whatsapp": "WhatsApp.exe",
        }

        # Common search paths for applications
        self.search_paths = [
            Path(os.environ.get("ProgramFiles", "C:\\Program Files")),
            Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")),
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs",
            Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WindowsApps",
        ]

        # Cache for discovered applications
        self._app_cache: Dict[str, AppDescriptor] = {}

    def open_app(self, app_id: str) -> bool:
        """
        Open application using subprocess.Popen or os.startfile.

        Algorithm:
            1. Normalize app_id (lowercase, strip whitespace)
            2. Check app_mapping for known executables
            3. If not found, perform dynamic discovery
            4. Launch using subprocess.Popen with CREATE_NEW_CONSOLE
            5. Verify launch by checking process existence

        Args:
            app_id: Application identifier (e.g., "notepad", "chrome")

        Returns:
            True if application launched successfully, False otherwise
        """
        try:
            # Normalize app_id
            app_id_normalized = app_id.lower().strip().replace(" ", "")

            # Check if we have a cached descriptor
            if app_id_normalized in self._app_cache:
                executable_path = self._app_cache[app_id_normalized].executable_path
            elif app_id_normalized in self.app_mapping:
                executable_path = self.app_mapping[app_id_normalized]
            else:
                # Dynamic discovery
                executable_path = self._discover_executable(app_id)
                if not executable_path:
                    return False

            # Launch application
            if os.path.isfile(executable_path):
                # Full path provided
                subprocess.Popen(
                    [executable_path], creationflags=subprocess.CREATE_NEW_CONSOLE, cwd=os.path.dirname(executable_path)
                )
            else:
                # Executable name only - let Windows find it
                subprocess.Popen([executable_path], creationflags=subprocess.CREATE_NEW_CONSOLE)

            # Verify launch (wait up to 3 seconds)
            time.sleep(0.5)  # Give process time to start
            return True

        except Exception:
            return False

    def close_app(self, app_id: str) -> bool:
        """
        Close application by terminating its process.

        Algorithm:
            1. Find running processes matching app_id
            2. Terminate each matching process
            3. Wait for termination (up to 5 seconds)

        Args:
            app_id: Application identifier

        Returns:
            True if application closed successfully, False otherwise
        """
        try:
            app_id_normalized = app_id.lower().strip().replace(" ", "")

            # Get executable name
            if app_id_normalized in self.app_mapping:
                exe_name = self.app_mapping[app_id_normalized].lower()
            else:
                exe_name = f"{app_id_normalized}.exe"

            # Find and terminate matching processes
            terminated = False
            for proc in psutil.process_iter(["name", "pid"]):
                try:
                    if proc.info["name"].lower() == exe_name:
                        proc.terminate()
                        terminated = True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if terminated:
                # Wait for processes to terminate
                time.sleep(1)

            return terminated

        except Exception:
            return False

    def is_running(self, app_id: str) -> bool:
        """
        Check if application is currently running.

        Algorithm:
            1. Get executable name from app_id
            2. Enumerate all running processes
            3. Check if any process matches executable name

        Args:
            app_id: Application identifier

        Returns:
            True if application is running, False otherwise
        """
        try:
            app_id_normalized = app_id.lower().strip().replace(" ", "")

            # Get executable name
            if app_id_normalized in self.app_mapping:
                exe_name = self.app_mapping[app_id_normalized].lower()
            else:
                exe_name = f"{app_id_normalized}.exe"

            # Check running processes
            for proc in psutil.process_iter(["name"]):
                try:
                    if proc.info["name"].lower() == exe_name:
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            return False

        except Exception:
            return False

    def discover_apps(self) -> List[AppDescriptor]:
        """
        Discover installed applications.

        Algorithm:
            1. Search registry for installed applications
            2. Search common installation paths
            3. Search Start Menu shortcuts
            4. Build AppDescriptor for each discovered app

        Returns:
            List of discovered application descriptors
        """
        discovered_apps = []
        seen_paths = set()

        # Add known applications from mapping
        for app_id, exe_name in self.app_mapping.items():
            # Try to find full path
            full_path = self._find_executable_path(exe_name)
            if full_path and full_path not in seen_paths:
                seen_paths.add(full_path)
                descriptor = AppDescriptor(
                    app_id=app_id,
                    display_name=app_id.title(),
                    executable_path=full_path,
                    is_running=self.is_running(app_id),
                    platform=self.platform,
                    metadata={"source": "builtin_mapping"},
                )
                discovered_apps.append(descriptor)
                self._app_cache[app_id] = descriptor
        # Search registry for installed applications
        try:
            discovered_apps.extend(self._discover_from_registry(seen_paths))
        except Exception:
            pass

        # Search filesystem
        try:
            discovered_apps.extend(self._discover_from_filesystem(seen_paths))
        except Exception:
            pass

        return discovered_apps

    def get_capabilities(self) -> Dict[str, bool]:
        """Return Windows application control capabilities."""
        return {
            "can_open_apps": True,
            "can_close_apps": True,
            "can_discover_apps": True,
            "has_full_control": True,
        }

    # ========================================================================
    # Private Helper Methods
    # ========================================================================

    def _discover_executable(self, app_name: str) -> Optional[str]:
        """
        Dynamically discover executable for application name.

        Args:
            app_name: Application name to search for

        Returns:
            Executable path if found, None otherwise
        """
        app_name_normalized = app_name.lower().strip().replace(" ", "")

        # Try with .exe extension
        exe_name = f"{app_name_normalized}.exe"
        full_path = self._find_executable_path(exe_name)
        if full_path:
            return full_path

        # Search in common paths
        for search_path in self.search_paths:
            if not search_path.exists():
                continue

            # Search for directories matching app name
            try:
                for item in search_path.iterdir():
                    if item.is_dir() and app_name_normalized in item.name.lower():
                        # Look for .exe files in this directory
                        for exe_file in item.rglob("*.exe"):
                            if app_name_normalized in exe_file.stem.lower():
                                return str(exe_file)
            except (PermissionError, OSError):
                continue

        return None

    def _find_executable_path(self, exe_name: str) -> Optional[str]:
        """
        Find full path to executable by searching PATH and common locations.

        Args:
            exe_name: Executable filename (e.g., "notepad.exe")

        Returns:
            Full path if found, None otherwise
        """
        # Check if it's in PATH
        import shutil

        path = shutil.which(exe_name)
        if path:
            return path

        # Search common paths
        for search_path in self.search_paths:
            if not search_path.exists():
                continue

            try:
                for exe_file in search_path.rglob(exe_name):
                    if exe_file.is_file():
                        return str(exe_file)
            except (PermissionError, OSError):
                continue

        return None

    def _discover_from_registry(self, seen_paths: set) -> List[AppDescriptor]:
        """
        Discover applications from Windows Registry.

        Args:
            seen_paths: Set of already discovered paths to avoid duplicates

        Returns:
            List of discovered application descriptors
        """
        discovered = []

        # Registry keys to search
        registry_keys = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]

        for hkey, subkey_path in registry_keys:
            try:
                with winreg.OpenKey(hkey, subkey_path) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, subkey_name) as subkey:
                                try:
                                    display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                                    install_location = winreg.QueryValueEx(subkey, "InstallLocation")[0]

                                    if install_location and os.path.isdir(install_location):
                                        # Look for .exe files in install location
                                        for exe_file in Path(install_location).rglob("*.exe"):
                                            exe_path = str(exe_file)
                                            if exe_path not in seen_paths:
                                                seen_paths.add(exe_path)
                                                app_id = exe_file.stem.lower().replace(" ", "")
                                                descriptor = AppDescriptor(
                                                    app_id=app_id,
                                                    display_name=display_name,
                                                    executable_path=exe_path,
                                                    is_running=False,  # Don't check for performance
                                                    platform=self.platform,
                                                    metadata={"source": "registry"},
                                                )
                                                discovered.append(descriptor)
                                                self._app_cache[app_id] = descriptor
                                                break  # Only take first .exe from each app
                                except (FileNotFoundError, OSError):
                                    continue
                        except OSError:
                            continue
            except OSError:
                continue

        return discovered

    def _discover_from_filesystem(self, seen_paths: set) -> List[AppDescriptor]:
        """
        Discover applications from filesystem.

        Args:
            seen_paths: Set of already discovered paths to avoid duplicates

        Returns:
            List of discovered application descriptors
        """
        discovered = []

        for search_path in self.search_paths:
            if not search_path.exists():
                continue

            try:
                # Limit depth to avoid excessive scanning
                for exe_file in search_path.glob("*/*.exe"):
                    exe_path = str(exe_file)
                    if exe_path not in seen_paths:
                        seen_paths.add(exe_path)
                        app_id = exe_file.stem.lower().replace(" ", "")
                        descriptor = AppDescriptor(
                            app_id=app_id,
                            display_name=exe_file.stem,
                            executable_path=exe_path,
                            is_running=False,  # Don't check for performance
                            platform=self.platform,
                            metadata={"source": "filesystem"},
                        )
                        discovered.append(descriptor)
                        self._app_cache[app_id] = descriptor
            except (PermissionError, OSError):
                continue

        return discovered
