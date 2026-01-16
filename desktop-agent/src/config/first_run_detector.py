"""
First-Run Detection Module

Detects whether this is the first time GURU is being launched and
manages the setup wizard flow.

Requirements: 16.1 - Detect first run
"""

import sys
from pathlib import Path


class FirstRunDetector:
    """
    Production-grade first-run detection.

    Checks for:
    - User configuration file existence
    - Valid user profile
    - Completed setup wizard

    Features:
    - Reliable detection across restarts
    - Setup completion tracking
    - Configuration validation
    """

    def __init__(self, config_dir: str = ".guru"):
        """Initialize first-run detector"""
        self.config_dir = Path.home() / config_dir
        self.config_file = self.config_dir / "user_config.json"
        self.setup_complete_marker = self.config_dir / ".setup_complete"

    def is_first_run(self) -> bool:
        """
        Check if this is the first run.

        Returns:
            True if first run, False otherwise
        """
        # Check if config file exists
        if not self.config_file.exists():
            return True

        # Check if setup complete marker exists
        if not self.setup_complete_marker.exists():
            return True

        # Validate configuration
        try:
            from .user_config import get_config_manager

            config_manager = get_config_manager()

            # If profile doesn't exist, it's first run
            if config_manager.is_first_time_setup():
                return True

            # Verify profile has required fields
            profile = config_manager.get_profile()
            if not profile:
                return True

            if not profile.user_name or not profile.display_name:
                return True

            return False

        except Exception:
            # If we can't validate, assume first run to be safe
            return True

    def mark_setup_complete(self):
        """Mark setup as complete"""
        try:
            # Create config directory if needed
            self.config_dir.mkdir(parents=True, exist_ok=True)

            # Create setup complete marker
            self.setup_complete_marker.touch()

        except Exception:
            pass

    def reset_setup(self):
        """Reset setup (for testing or reconfiguration)"""
        try:
            if self.setup_complete_marker.exists():
                self.setup_complete_marker.unlink()
        except Exception:
            pass


def detect_first_run() -> bool:
    """
    Convenience function to detect first run.

    Returns:
        True if first run, False otherwise
    """
    detector = FirstRunDetector()
    return detector.is_first_run()


def mark_setup_complete():
    """Convenience function to mark setup as complete"""
    detector = FirstRunDetector()
    detector.mark_setup_complete()


def run_setup_wizard_if_needed() -> bool:
    """
    Run setup wizard if this is first run.

    Returns:
        True if setup was run and completed, False if not needed or cancelled
    """
    detector = FirstRunDetector()

    if not detector.is_first_run():
        return False

    try:
        from PyQt6.QtWidgets import QApplication

        from gui.setup_wizard import run_setup_wizard

        # Create Qt application if needed
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
            app.setApplicationName("GURU Setup")

        # Run setup wizard
        setup_data = run_setup_wizard()

        if not setup_data:
            return False

        # Mark setup as complete
        detector.mark_setup_complete()

        return True

    except Exception:
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Test first-run detection
    detector = FirstRunDetector()
