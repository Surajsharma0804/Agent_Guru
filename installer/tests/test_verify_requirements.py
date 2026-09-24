"""
Tests for installer/verify_requirements.py

Validates that the system requirements checker:
- Correctly identifies OS version
- Correctly identifies Python version
- Correctly checks disk space
- Correctly checks RAM
- Correctly checks microphone
- Correctly checks internet
- Returns correct exit codes

Author: Agent Guru Team
Date: 2026-03-19
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch


# Add installer to path
sys.path.insert(0, "installer")
from verify_requirements import (
    CheckStatus,
    check_disk_space,
    check_internet,
    check_microphone,
    check_os_version,
    check_python_version,
    check_ram,
    run_checks,
)


class TestOSVersionCheck:
    def test_windows_10_passes(self):
        with patch("platform.system", return_value="Windows"), \
             patch("platform.release", return_value="10"), \
             patch("platform.version", return_value="10.0.19041"):
            result = check_os_version()
        assert result.status == CheckStatus.PASS

    def test_windows_7_fails(self):
        with patch("platform.system", return_value="Windows"), \
             patch("platform.release", return_value="7"), \
             patch("platform.version", return_value="6.1.7601"):
            result = check_os_version()
        assert result.status == CheckStatus.FAIL

    def test_macos_12_passes(self):
        with patch("platform.system", return_value="Darwin"), \
             patch("platform.mac_ver", return_value=("12.6.0", ("", "", ""), "")):
            result = check_os_version()
        assert result.status == CheckStatus.PASS

    def test_macos_10_fails(self):
        with patch("platform.system", return_value="Darwin"), \
             patch("platform.mac_ver", return_value=("10.15.7", ("", "", ""), "")):
            result = check_os_version()
        assert result.status == CheckStatus.FAIL

    def test_linux_passes(self):
        with patch("platform.system", return_value="Linux"), \
             patch("platform.platform", return_value="Linux-5.15.0"):
            result = check_os_version()
        assert result.status == CheckStatus.PASS

    def test_unknown_os_warns(self):
        with patch("platform.system", return_value="FreeBSD"):
            result = check_os_version()
        assert result.status == CheckStatus.WARN


class TestPythonVersionCheck:
    """Use a simple mock object that supports attribute access and comparison."""

    @staticmethod
    def _vi(major, minor, micro):
        """Create a mock version_info with attribute access and tuple comparison."""
        class _VI:
            def __init__(self, ma, mi, mc):
                self.major, self.minor, self.micro = ma, mi, mc
            def __ge__(self, other): return (self.major, self.minor) >= other[:2]
            def __lt__(self, other): return (self.major, self.minor) < other[:2]
        return _VI(major, minor, micro)

    def test_python_311_passes(self):
        with patch("verify_requirements.sys") as mock_sys:
            mock_sys.version_info = self._vi(3, 11, 0)
            result = check_python_version()
        assert result.status == CheckStatus.PASS

    def test_python_312_passes(self):
        with patch("verify_requirements.sys") as mock_sys:
            mock_sys.version_info = self._vi(3, 12, 0)
            result = check_python_version()
        assert result.status == CheckStatus.PASS

    def test_python_39_warns(self):
        with patch("verify_requirements.sys") as mock_sys:
            mock_sys.version_info = self._vi(3, 9, 0)
            result = check_python_version()
        assert result.status == CheckStatus.WARN

    def test_python_38_fails(self):
        with patch("verify_requirements.sys") as mock_sys:
            mock_sys.version_info = self._vi(3, 8, 0)
            result = check_python_version()
        assert result.status == CheckStatus.FAIL

    def test_python_27_fails(self):
        with patch("verify_requirements.sys") as mock_sys:
            mock_sys.version_info = self._vi(2, 7, 18)
            result = check_python_version()
        assert result.status == CheckStatus.FAIL


class TestDiskSpaceCheck:
    def test_ample_space_passes(self):
        mock_usage = MagicMock()
        mock_usage.free = 50 * 1024 ** 3  # 50 GB
        with patch("shutil.disk_usage", return_value=mock_usage):
            result = check_disk_space()
        assert result.status == CheckStatus.PASS

    def test_exactly_2gb_passes(self):
        mock_usage = MagicMock()
        mock_usage.free = 2 * 1024 ** 3  # exactly 2 GB
        with patch("shutil.disk_usage", return_value=mock_usage):
            result = check_disk_space()
        assert result.status == CheckStatus.PASS

    def test_1gb_warns(self):
        mock_usage = MagicMock()
        mock_usage.free = 1.5 * 1024 ** 3  # 1.5 GB
        with patch("shutil.disk_usage", return_value=mock_usage):
            result = check_disk_space()
        assert result.status == CheckStatus.WARN

    def test_500mb_fails(self):
        mock_usage = MagicMock()
        mock_usage.free = 500 * 1024 ** 2  # 500 MB
        with patch("shutil.disk_usage", return_value=mock_usage):
            result = check_disk_space()
        assert result.status == CheckStatus.FAIL

    def test_exception_warns(self):
        with patch("shutil.disk_usage", side_effect=OSError("Permission denied")):
            result = check_disk_space()
        assert result.status == CheckStatus.WARN


class TestRAMCheck:
    def test_16gb_passes(self):
        mock_mem = MagicMock()
        mock_mem.total = 16 * 1024 ** 3
        mock_mem.available = 8 * 1024 ** 3
        with patch("psutil.virtual_memory", return_value=mock_mem):
            result = check_ram()
        assert result.status == CheckStatus.PASS

    def test_4gb_passes(self):
        mock_mem = MagicMock()
        mock_mem.total = 4 * 1024 ** 3
        mock_mem.available = 2 * 1024 ** 3
        with patch("psutil.virtual_memory", return_value=mock_mem):
            result = check_ram()
        assert result.status == CheckStatus.PASS

    def test_2gb_warns(self):
        mock_mem = MagicMock()
        mock_mem.total = 2 * 1024 ** 3
        mock_mem.available = 1 * 1024 ** 3
        with patch("psutil.virtual_memory", return_value=mock_mem):
            result = check_ram()
        assert result.status == CheckStatus.WARN

    def test_psutil_missing_warns(self):
        with patch.dict("sys.modules", {"psutil": None}):
            result = check_ram()
        assert result.status == CheckStatus.WARN


class TestMicrophoneCheck:
    def test_microphone_found_passes(self):
        mock_pa = MagicMock()
        mock_pa.get_device_count.return_value = 2
        mock_pa.get_device_info_by_index.side_effect = [
            {"maxInputChannels": 2, "name": "Built-in Microphone"},
            {"maxInputChannels": 0, "name": "Built-in Output"},
        ]
        with patch("pyaudio.PyAudio", return_value=mock_pa):
            result = check_microphone()
        assert result.status == CheckStatus.PASS

    def test_no_microphone_fails(self):
        mock_pa = MagicMock()
        mock_pa.get_device_count.return_value = 1
        mock_pa.get_device_info_by_index.return_value = {
            "maxInputChannels": 0, "name": "Output Only"
        }
        with patch("pyaudio.PyAudio", return_value=mock_pa):
            result = check_microphone()
        assert result.status == CheckStatus.FAIL

    def test_pyaudio_missing_warns(self):
        with patch.dict("sys.modules", {"pyaudio": None}):
            result = check_microphone()
        assert result.status == CheckStatus.WARN


class TestInternetCheck:
    def test_connected_passes(self):
        mock_sock = MagicMock()
        with patch("socket.socket", return_value=mock_sock):
            result = check_internet()
        assert result.status == CheckStatus.PASS

    def test_no_connection_warns(self):
        with patch("socket.socket") as mock_sock_class:
            mock_sock_class.return_value.connect.side_effect = OSError("Network unreachable")
            result = check_internet()
        assert result.status == CheckStatus.WARN


class TestRunChecks:
    def test_returns_list_of_results(self):
        results = run_checks()
        assert isinstance(results, list)
        assert len(results) > 0

    def test_all_results_have_required_fields(self):
        results = run_checks()
        for r in results:
            assert r.name
            assert r.status in list(CheckStatus)
            assert r.message

    def test_to_dict_serializable(self):
        import json
        results = run_checks()
        data = [r.to_dict() for r in results]
        # Should serialize without error
        json.dumps(data)
