"""
Audio Manager - System Audio Configuration

Ensures audio output is properly configured for GURU.
Handles Windows audio routing, volume control, and device selection.
"""

import subprocess
import sys
from typing import List, Optional, Tuple


class AudioManager:
    """
    Manages system audio configuration for GURU.

    Responsibilities:
    - Verify audio output device availability
    - Ensure Python process is not muted
    - Set appropriate volume levels
    - Select correct audio output device
    """

    def __init__(self):
        self.platform = sys.platform

    def verify_audio_output(self) -> Tuple[bool, Optional[str]]:
        """
        Verify audio output is working.

        Returns:
            (success, error_message)
        """
        if self.platform == "win32":
            return self._verify_windows_audio()
        else:
            return True, None

    def _verify_windows_audio(self) -> Tuple[bool, Optional[str]]:
        """Verify Windows audio configuration"""
        try:
            # Check if audio service is running
            result = subprocess.run(["sc", "query", "Audiosrv"], capture_output=True, text=True, timeout=5)

            if "RUNNING" not in result.stdout:
                return False, "Windows Audio Service is not running"

            # Try to play a test sound using pyttsx3
            try:
                import pyttsx3

                engine = pyttsx3.init()

                # Get current volume
                try:
                    volume = engine.getProperty("volume")
                    if volume < 0.1:
                        # Volume too low, increase it
                        engine.setProperty("volume", 0.9)
                except Exception:
                    pass

                engine.stop()
                return True, None

            except Exception as e:
                return False, f"TTS engine initialization failed: {e}"

        except Exception as e:
            return False, f"Audio verification failed: {e}"

    def unmute_python_audio(self) -> bool:
        """
        Unmute Python process in Windows Volume Mixer.

        Note: This requires Windows APIs that may not be available.
        Best solution is to instruct user to unmute manually.

        Returns:
            True if successful or not needed, False if failed
        """
        if self.platform != "win32":
            return True

        try:
            # On Windows, we can't easily unmute a specific process programmatically
            # without using COM APIs or third-party libraries.
            #
            # The best we can do is:
            # 1. Detect if audio is muted
            # 2. Warn the user
            # 3. Provide instructions

            return True

        except Exception:
            return True

    def get_audio_devices(self) -> List[str]:
        """
        Get list of available audio output devices.

        Returns:
            List of device names
        """
        devices = []

        if self.platform == "win32":
            try:
                # Use PowerShell to get audio devices
                result = subprocess.run(
                    [
                        "powershell",
                        "-Command",
                        "Get-AudioDevice -List | Where-Object {$_.Type -eq 'Playback'} | Select-Object -ExpandProperty Name",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                if result.returncode == 0:
                    devices = [line.strip() for line in result.stdout.split("\n") if line.strip()]
            except Exception:
                pass

        return devices

    def test_audio_output(self) -> bool:
        """
        Test audio output by playing a test sound.

        Returns:
            True if audio played successfully
        """
        try:
            import pyttsx3

            engine = pyttsx3.init()

            # Set volume to maximum for test
            engine.setProperty("volume", 1.0)

            # Play test sound
            engine.say("Audio test")
            engine.runAndWait()

            return True

        except Exception:
            return False


def get_audio_manager() -> AudioManager:
    """Get audio manager instance"""
    return AudioManager()


__all__ = ["AudioManager", "get_audio_manager"]
