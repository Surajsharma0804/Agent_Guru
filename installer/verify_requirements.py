"""
Agent Guru - System Requirements Verification

Checks all system requirements before installation or launch.
Exits with code 0 if all requirements met, non-zero otherwise.

Requirements checked:
- OS version (Windows 10+ / macOS 11+ / Ubuntu 20.04+)
- Python version (3.11+)
- Available disk space (2GB minimum)
- Available RAM (4GB minimum)
- Microphone availability
- Internet connectivity (for cloud LLM providers)

Usage:
    python installer/verify_requirements.py
    python installer/verify_requirements.py --json   # JSON output
    python installer/verify_requirements.py --strict # Fail on warnings

Author: Agent Guru Team
Date: 2026-03-19
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class CheckStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class CheckResult:
    name: str
    status: CheckStatus
    message: str
    detail: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "detail": self.detail,
        }


# -------------------------------------------------------
# Individual checks
# -------------------------------------------------------

def check_os_version() -> CheckResult:
    """Verify OS version meets minimum requirements."""
    system = platform.system()

    if system == "Windows":
        version = platform.version()
        # Windows 10 = 10.0.10240+
        major = int(platform.release()) if platform.release().isdigit() else 0
        if major >= 10:
            return CheckResult("OS Version", CheckStatus.PASS, f"Windows {platform.release()} ({version})")
        return CheckResult("OS Version", CheckStatus.FAIL,
                           f"Windows {platform.release()} not supported",
                           "Agent Guru requires Windows 10 or later")

    elif system == "Darwin":
        mac_ver = platform.mac_ver()[0]
        parts = mac_ver.split(".")
        major = int(parts[0]) if parts else 0
        if major >= 11:
            return CheckResult("OS Version", CheckStatus.PASS, f"macOS {mac_ver}")
        return CheckResult("OS Version", CheckStatus.FAIL,
                           f"macOS {mac_ver} not supported",
                           "Agent Guru requires macOS 11 (Big Sur) or later")

    elif system == "Linux":
        try:
            import distro  # type: ignore
            name = distro.name(pretty=True)
        except ImportError:
            name = platform.platform()
        return CheckResult("OS Version", CheckStatus.PASS, f"Linux: {name}")

    return CheckResult("OS Version", CheckStatus.WARN,
                       f"Unknown OS: {system}",
                       "Agent Guru may not work correctly on this platform")


def check_python_version() -> CheckResult:
    """Verify Python 3.11+ is available."""
    ver = sys.version_info
    version_str = f"{ver.major}.{ver.minor}.{ver.micro}"

    if ver >= (3, 11):
        return CheckResult("Python Version", CheckStatus.PASS, f"Python {version_str}")
    elif ver >= (3, 9):
        return CheckResult("Python Version", CheckStatus.WARN,
                           f"Python {version_str} (3.11+ recommended)",
                           "Some features may not work optimally")
    return CheckResult("Python Version", CheckStatus.FAIL,
                       f"Python {version_str} not supported",
                       "Agent Guru requires Python 3.11 or later")


def check_disk_space() -> CheckResult:
    """Verify at least 2GB free disk space."""
    min_gb = 2.0
    try:
        usage = shutil.disk_usage(".")
        free_gb = usage.free / (1024 ** 3)
        if free_gb >= min_gb:
            return CheckResult("Disk Space", CheckStatus.PASS,
                               f"{free_gb:.1f} GB free")
        elif free_gb >= 1.0:
            return CheckResult("Disk Space", CheckStatus.WARN,
                               f"Only {free_gb:.1f} GB free (2 GB recommended)",
                               "Installation may fail if space runs out")
        return CheckResult("Disk Space", CheckStatus.FAIL,
                           f"Only {free_gb:.1f} GB free",
                           f"Agent Guru requires at least {min_gb} GB free disk space")
    except Exception as e:
        return CheckResult("Disk Space", CheckStatus.WARN,
                           f"Could not check disk space: {e}")


def check_ram() -> CheckResult:
    """Verify at least 4GB RAM available."""
    min_gb = 4.0
    try:
        import psutil  # type: ignore
        total_gb = psutil.virtual_memory().total / (1024 ** 3)
        available_gb = psutil.virtual_memory().available / (1024 ** 3)

        if total_gb >= min_gb:
            return CheckResult("RAM", CheckStatus.PASS,
                               f"{total_gb:.1f} GB total, {available_gb:.1f} GB available")
        return CheckResult("RAM", CheckStatus.WARN,
                           f"Only {total_gb:.1f} GB RAM",
                           f"Agent Guru recommends at least {min_gb} GB RAM for optimal performance")
    except ImportError:
        return CheckResult("RAM", CheckStatus.WARN,
                           "psutil not installed - cannot check RAM",
                           "Install psutil: pip install psutil")
    except Exception as e:
        return CheckResult("RAM", CheckStatus.WARN, f"Could not check RAM: {e}")


def check_microphone() -> CheckResult:
    """Verify microphone is available."""
    try:
        import pyaudio  # type: ignore
        pa = pyaudio.PyAudio()
        device_count = pa.get_device_count()
        input_devices = []

        for i in range(device_count):
            info = pa.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0:
                input_devices.append(info.get("name", f"Device {i}"))

        pa.terminate()

        if input_devices:
            return CheckResult("Microphone", CheckStatus.PASS,
                               f"{len(input_devices)} input device(s) found",
                               f"Devices: {', '.join(input_devices[:3])}")
        return CheckResult("Microphone", CheckStatus.FAIL,
                           "No microphone found",
                           "Agent Guru requires a microphone for voice commands")

    except ImportError:
        return CheckResult("Microphone", CheckStatus.WARN,
                           "pyaudio not installed - cannot check microphone",
                           "Microphone will be verified at runtime")
    except Exception as e:
        return CheckResult("Microphone", CheckStatus.WARN,
                           f"Could not check microphone: {e}",
                           "Microphone will be verified at runtime")


def check_internet() -> CheckResult:
    """Verify internet connectivity (for cloud LLM providers)."""
    import socket
    try:
        with socket.create_connection(("8.8.8.8", 53), timeout=30):
            pass
        return CheckResult("Internet", CheckStatus.PASS,
                           "Internet connection available")
    except OSError:
        return CheckResult("Internet", CheckStatus.WARN,
                           "No internet connection",
                           "Cloud LLM providers (OpenAI, Gemini, Claude) will not be available. "
                           "Local Ollama will still work.")


def check_gpu() -> CheckResult:
    """Check GPU availability for acceleration."""
    try:
        import torch  # type: ignore
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            return CheckResult("GPU (CUDA)", CheckStatus.PASS,
                               f"{gpu_name} ({vram_gb:.1f} GB VRAM)")
        return CheckResult("GPU (CUDA)", CheckStatus.WARN,
                           "No CUDA GPU found",
                           "Agent Guru will run on CPU (slower). GPU recommended for best performance.")
    except ImportError:
        return CheckResult("GPU (CUDA)", CheckStatus.WARN,
                           "PyTorch not installed - cannot check GPU")
    except Exception as e:
        return CheckResult("GPU (CUDA)", CheckStatus.WARN, f"GPU check failed: {e}")


# -------------------------------------------------------
# Main verification runner
# -------------------------------------------------------

def run_checks() -> List[CheckResult]:
    """Run all system requirement checks."""
    checks = [
        check_os_version,
        check_python_version,
        check_disk_space,
        check_ram,
        check_microphone,
        check_internet,
        check_gpu,
    ]
    return [check() for check in checks]


def print_results(results: List[CheckResult], use_json: bool = False) -> None:
    """Print check results to stdout."""
    if use_json:
        print(json.dumps([r.to_dict() for r in results], indent=2))
        return

    icons = {
        CheckStatus.PASS: "✓",
        CheckStatus.WARN: "⚠",
        CheckStatus.FAIL: "✗",
    }
    colors = {
        CheckStatus.PASS: "\033[92m",  # Green
        CheckStatus.WARN: "\033[93m",  # Yellow
        CheckStatus.FAIL: "\033[91m",  # Red
    }
    reset = "\033[0m"

    print("\nAgent Guru - System Requirements Check")
    print("=" * 50)

    for r in results:
        icon = icons[r.status]
        color = colors[r.status]
        print(f"  {color}{icon}{reset} {r.name}: {r.message}")
        if r.detail:
            print(f"      {r.detail}")

    fails = sum(1 for r in results if r.status == CheckStatus.FAIL)
    warns = sum(1 for r in results if r.status == CheckStatus.WARN)
    passes = sum(1 for r in results if r.status == CheckStatus.PASS)

    print("=" * 50)
    print(f"  Results: {passes} passed, {warns} warnings, {fails} failed")

    if fails == 0 and warns == 0:
        print("\n  \033[92mAll requirements met. Ready to install.\033[0m")
    elif fails == 0:
        print("\n  \033[93mRequirements met with warnings. Installation may proceed.\033[0m")
    else:
        print("\n  \033[91mRequirements not met. Please resolve failures before installing.\033[0m")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent Guru system requirements check")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    args = parser.parse_args()

    results = run_checks()
    print_results(results, use_json=args.json)

    fails = sum(1 for r in results if r.status == CheckStatus.FAIL)
    warns = sum(1 for r in results if r.status == CheckStatus.WARN)

    if fails > 0:
        return 1
    if args.strict and warns > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
