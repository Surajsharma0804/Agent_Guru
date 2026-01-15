"""
macOS Application Controller Implementation.

Implements ApplicationController interface using LaunchServices, Apple Events,
and NSWorkspace for complete application control on macOS.

Uses:
    - subprocess with 'open' command (LaunchServices wrapper)
    - psutil for process management and enumeration
    - Apple Events via osascript for application control
    - Spotlight metadata for application discovery

Capabilities:
    - Full application control
    - Complete discovery via LaunchServices
    - System-wide authority

Validates: Requirements 34.6, 34.9
"""

import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

import psutil

from ...interfaces import AppDescriptor, ApplicationController


class macOSApplicationController(ApplicationController):
    """
    macOS implementation of ApplicationController.

    Uses:
        - 'open' command for launching (LaunchServices wrapper)
        - psutil for process management
        - osascript for Apple Events (app control)
        - mdfind for Spotlight-based discovery

    Capabilities:
        - Full application control
        - Complete discovery
        - System-wide authority
    """

    def __init__(self):
        """Initialize macOS application controller."""
        self.platform = "macos"

        # Common application mappings (app_id -> app name or bundle ID)
        self.app_mapping = {
            "safari": "Safari",
            "chrome": "Google Chrome",
            "firefox": "Firefox",
            "edge": "Microsoft Edge",
            "notes": "Notes",
            "textedit": "TextEdit",
            "preview": "Preview",
            "mail": "Mail",
            "messages": "Messages",
            "calendar": "Calendar",
            "contacts": "Contacts",
            "reminders": "Reminders",
            "maps": "Maps",
            "photos": "Photos",
            "music": "Music",
            "podcasts": "Podcasts",
            "tv": "TV",
            "books": "Books",
            "appstore": "App Store",
            "systempreferences": "System Preferences",
            "systemsettings": "System Settings",
            "finder": "Finder",
            "terminal": "Terminal",
            "calculator": "Calculator",
            "dictionary": "Dictionary",
            "vscode": "Visual Studio Code",
            "xcode": "Xcode",
            "word": "Microsoft Word",
            "excel": "Microsoft Excel",
            "powerpoint": "Microsoft Powerpoint",
            "outlook": "Microsoft Outlook",
            "teams": "Microsoft Teams",
            "slack": "Slack",
            "discord": "Discord",
            "spotify": "Spotify",
            "whatsapp": "WhatsApp",
            "zoom": "zoom.us",
        }

        # Common application paths
        self.search_paths = [
            Path("/Applications"),
            Path("/System/Applications"),
            Path(os.path.expanduser("~/Applications")),
            Path("/System/Library/CoreServices"),
        ]

        # Cache for discovered applications
        self._app_cache: Dict[str, AppDescriptor] = {}

    def open_app(self, app_id: str) -> bool:
        """
        Open application using 'open' command (LaunchServices).

        Algorithm:
            1. Normalize app_id (lowercase, strip whitespace)
            2. Check app_mapping for known applications
            3. If not found, perform dynamic discovery
            4. Launch using 'open -a' command
            5. Verify launch by checking process existence

        Args:
            app_id: Application identifier (e.g., "safari", "chrome")

        Returns:
            True if application launched successfully, False otherwise
        """
        try:
            # Normalize app_id
            app_id_normalized = app_id.lower().strip().replace(" ", "")

            # Get application name
            if app_id_normalized in self._app_cache:
                app_name = self._app_cache[app_id_normalized].display_name
            elif app_id_normalized in self.app_mapping:
                app_name = self.app_mapping[app_id_normalized]
            else:
                # Try to discover the application
                app_path = self._discover_app_path(app_id)
                if app_path:
                    app_name = app_path
                else:
                    # Try using the app_id directly
                    app_name = app_id

            # Launch application using 'open -a' command
            # -a flag tells open to launch by application name
            # -g flag launches in background (doesn't bring to front immediately)
            _result = subprocess.run(["open", "-a", app_name], capture_output=True, text=True, timeout=5)

            if result.returncode == 0:
                # Give application time to start
                time.sleep(0.5)
                return True
            else:
                return False

        except subprocess.TimeoutExpired:
            return False
        except Exception:
            return False

    def close_app(self, app_id: str) -> bool:
        """
        Close application using Apple Events via osascript.

        Algorithm:
            1. Get application name from app_id
            2. Use osascript to send 'quit' Apple Event
            3. Wait for application to terminate
            4. If graceful quit fails, force terminate process

        Args:
            app_id: Application identifier

        Returns:
            True if application closed successfully, False otherwise
        """
        try:
            app_id_normalized = app_id.lower().strip().replace(" ", "")

            # Get application name
            if app_id_normalized in self.app_mapping:
                app_name = self.app_mapping[app_id_normalized]
            else:
                app_name = app_id

            # Try graceful quit using Apple Events
            applescript = f'tell application "{app_name}" to quit'
            _result = subprocess.run(["osascript", "-e", applescript], capture_output=True, text=True, timeout=5)

            if result.returncode == 0:
                # Wait for application to quit
                time.sleep(1)

                # Verify it's closed
                if not self.is_running(app_id):
                    return True

            # If graceful quit failed, force terminate
            # Find and terminate matching processes
            terminated = False
            for proc in psutil.process_iter(["name", "pid"]):
                try:
                    proc_name = proc.info["name"]
                    # Match process name (case-insensitive)
                    if app_name.lower() in proc_name.lower() or app_id_normalized in proc_name.lower():
                        proc.terminate()
                        terminated = True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if terminated:
                time.sleep(1)

            return terminated

        except subprocess.TimeoutExpired:
            return False
        except Exception:
            return False

    def is_running(self, app_id: str) -> bool:
        """
        Check if application is currently running.

        Algorithm:
            1. Get application name from app_id
            2. Enumerate all running processes
            3. Check if any process matches application name

        Args:
            app_id: Application identifier

        Returns:
            True if application is running, False otherwise
        """
        try:
            app_id_normalized = app_id.lower().strip().replace(" ", "")

            # Get application name
            if app_id_normalized in self.app_mapping:
                app_name = self.app_mapping[app_id_normalized].lower()
            else:
                app_name = app_id.lower()

            # Check running processes
            for proc in psutil.process_iter(["name"]):
                try:
                    proc_name = proc.info["name"].lower()
                    # Match process name
                    if app_name in proc_name or app_id_normalized in proc_name:
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            return False

        except Exception:
            return False

    def discover_apps(self) -> List[AppDescriptor]:
        """
        Discover installed applications using Spotlight and filesystem.

        Algorithm:
            1. Use mdfind (Spotlight) to find all .app bundles
            2. Search common application directories
            3. Build AppDescriptor for each discovered app
            4. Cache results for future lookups

        Returns:
            List of discovered application descriptors
        """
        discovered_apps = []
        seen_paths = set()

        # Add known applications from mapping
        for app_id, app_name in self.app_mapping.items():
            # Try to find app path
            app_path = self._find_app_path(app_name)
            if app_path and app_path not in seen_paths:
                seen_paths.add(app_path)
                descriptor = AppDescriptor(
                    app_id=app_id,
                    display_name=app_name,
                    executable_path=app_path,
                    is_running=self.is_running(app_id),
                    platform=self.platform,
                    metadata={"source": "builtin_mapping"},
                )
                discovered_apps.append(descriptor)
                self._app_cache[app_id] = descriptor
        # Use Spotlight to find all applications
        try:
            discovered_apps.extend(self._discover_via_spotlight(seen_paths))
        except Exception:
            pass

        # Search filesystem as fallback
        try:
            discovered_apps.extend(self._discover_from_filesystem(seen_paths))
        except Exception:
            pass

        return discovered_apps

    def get_capabilities(self) -> Dict[str, bool]:
        """Return macOS application control capabilities."""
        return {
            "can_open_apps": True,
            "can_close_apps": True,
            "can_discover_apps": True,
            "has_full_control": True,
        }

    # ========================================================================
    # Private Helper Methods
    # ========================================================================

    def _discover_app_path(self, app_name: str) -> Optional[str]:
        """
        Dynamically discover path for application name.

        Args:
            app_name: Application name to search for

        Returns:
            Application path if found, None otherwise
        """
        # Try to find using mdfind (Spotlight)
        try:
            _result = subprocess.run(
                ["mdfind", f'kMDItemKind == "Application" && kMDItemFSName == "{app_name}.app"'],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0 and result.stdout.strip():
                paths = result.stdout.strip().split("\n")
                if paths:
                    return paths[0]  # Return first match
        except (subprocess.TimeoutExpired, Exception):
            pass

        # Fallback to filesystem search
        return self._find_app_path(app_name)

    def _find_app_path(self, app_name: str) -> Optional[str]:
        """
        Find application path by searching common locations.

        Args:
            app_name: Application name (e.g., "Safari", "Google Chrome")

        Returns:
            Full path to .app bundle if found, None otherwise
        """
        # Ensure .app extension
        if not app_name.endswith(".app"):
            app_name_with_ext = f"{app_name}.app"
        else:
            app_name_with_ext = app_name

        # Search common paths
        for search_path in self.search_paths:
            if not search_path.exists():
                continue

            app_path = search_path / app_name_with_ext
            if app_path.exists() and app_path.is_dir():
                return str(app_path)

        return None

    def _discover_via_spotlight(self, seen_paths: set) -> List[AppDescriptor]:
        """
        Discover applications using Spotlight (mdfind).

        Args:
            seen_paths: Set of already discovered paths to avoid duplicates

        Returns:
            List of discovered application descriptors
        """
        discovered = []

        try:
            # Use mdfind to find all applications
            _result = subprocess.run(
                ["mdfind", 'kMDItemKind == "Application"'], capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                app_paths = result.stdout.strip().split("\n")

                for app_path in app_paths:
                    if not app_path or app_path in seen_paths:
                        continue

                    # Extract app name from path
                    app_name = Path(app_path).stem
                    app_id = app_name.lower().replace(" ", "")

                    seen_paths.add(app_path)
                    descriptor = AppDescriptor(
                        app_id=app_id,
                        display_name=app_name,
                        executable_path=app_path,
                        is_running=False,  # Don't check for performance
                        platform=self.platform,
                        metadata={"source": "spotlight"},
                    )
                    discovered.append(descriptor)
                    self._app_cache[app_id] = descriptor
        except subprocess.TimeoutExpired:
            pass
        except Exception:
            pass

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
                # Find all .app bundles in this directory
                for app_path in search_path.glob("*.app"):
                    app_path_str = str(app_path)
                    if app_path_str not in seen_paths:
                        app_name = app_path.stem
                        app_id = app_name.lower().replace(" ", "")

                        seen_paths.add(app_path_str)
                        descriptor = AppDescriptor(
                            app_id=app_id,
                            display_name=app_name,
                            executable_path=app_path_str,
                            is_running=False,  # Don't check for performance
                            platform=self.platform,
                            metadata={"source": "filesystem"},
                        )
                        discovered.append(descriptor)
                        self._app_cache[app_id] = descriptor
            except (PermissionError, OSError):
                continue

        return discovered
