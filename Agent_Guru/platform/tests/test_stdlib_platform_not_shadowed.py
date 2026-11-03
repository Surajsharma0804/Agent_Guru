"""The Agent_Guru.platform package must never stand in for the stdlib platform.

The package folder is named platform. With the Agent_Guru folder first on
sys.path, which `python -m pytest` and `python -c` do when started from
inside it, `import platform` used to find the package. pytest then died
while loading its plugins, before collecting a single test:

    AttributeError: module 'platform' has no attribute 'python_implementation'

The same command from the repository root passed, so the failure depended
only on which folder the terminal was in. The first two tests start a
child interpreter from inside the Agent_Guru folder, the only way to put
that folder on sys.path the way a user's command does.
"""

import os
import subprocess  # nosec B404 - runs this interpreter on fixed arguments
import sys
import sysconfig
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[2]
THIS_FILE_FROM_PACKAGE_DIR = Path(__file__).resolve().relative_to(PACKAGE_DIR).as_posix()


def _run_in_package_dir(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    # PYTHONSAFEPATH stops Python putting the working folder on sys.path,
    # which would hide the bug and let these tests pass against the old
    # package.
    env.pop("PYTHONSAFEPATH", None)
    return subprocess.run(  # nosec B603 - sys.executable with literal arguments
        [sys.executable, *args],
        cwd=PACKAGE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )


def test_import_platform_inside_the_package_folder_gets_the_stdlib():
    result = _run_in_package_dir(
        "-c",
        "import platform; print(platform.python_implementation()); print(platform.__file__)",
    )

    assert result.returncode == 0, result.stderr  # nosec B101
    implementation, module_file = result.stdout.split()
    assert implementation in {"CPython", "PyPy"}  # nosec B101
    stdlib_dir = Path(sysconfig.get_path("stdlib")).resolve()
    assert Path(module_file).resolve().parent == stdlib_dir  # nosec B101


def test_pytest_starts_inside_the_package_folder():
    # Collecting is enough: the old crash happened while pytest loaded its
    # plugins, before collection, and running the tests would recurse.
    result = _run_in_package_dir(
        "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", THIS_FILE_FROM_PACKAGE_DIR
    )

    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]  # nosec B101
    assert "3 tests collected" in result.stdout  # nosec B101


def test_the_package_still_imports_under_its_own_name():
    import platform

    import Agent_Guru.platform as package

    assert package.__name__ == "Agent_Guru.platform"  # nosec B101
    assert package.__version__ == "1.0.0"  # nosec B101
    assert platform is not package  # nosec B101
    assert callable(platform.python_implementation)  # nosec B101
