"""What pyproject.toml declares, checked against the failures it prevents.

An import test cannot catch these. python-dotenv was importable on every
clean install only because chromadb pulls it in, and PyAV 19 installed fine
and only failed when a file was transcribed. The declarations themselves are
what has to hold, so these tests read pyproject.toml and evaluate its
requirements the way pip does.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet

PYPROJECT = Path(__file__).resolve().parents[3] / "pyproject.toml"


@pytest.fixture(scope="module")
def project() -> dict:
    with PYPROJECT.open("rb") as f:
        return tomllib.load(f)["project"]


@pytest.fixture(scope="module")
def requirements(project: dict) -> dict[str, Requirement]:
    reqs = (Requirement(line) for line in project["dependencies"])
    return {r.name.lower(): r for r in reqs}


def test_python_dotenv_is_declared(requirements: dict[str, Requirement]) -> None:
    """main.py drops every .env setting without a word when it is missing."""
    assert "python-dotenv" in requirements


@pytest.mark.parametrize("version", ["3.11.0", "3.12.9", "3.13.15"])
def test_supported_pythons_are_accepted(project: dict, version: str) -> None:
    assert version in SpecifierSet(project["requires-python"])


def test_python_314_is_refused_up_front(project: dict) -> None:
    """kokoro-onnx has no 3.14 release; pip must say so, not fail on kokoro-onnx."""
    assert "3.14.0" not in SpecifierSet(project["requires-python"])


def test_pyav_that_removed_metadata_errors_is_excluded(
    requirements: dict[str, Requirement],
) -> None:
    """faster-whisper 1.2.1 passes av.open(metadata_errors=); PyAV 19.0.0 removed it."""
    assert "faster-whisper" in requirements
    av = requirements.get("av")
    assert av is not None, "av must be declared with an upper bound"
    assert "19.0.0" not in av.specifier
    assert "18.1.0" in av.specifier


def test_cuda_libraries_are_optional(project: dict, requirements: dict[str, Requirement]) -> None:
    """About 2 GB that only NVIDIA machines can use must stay out of every install."""
    assert not [name for name in requirements if name.startswith("nvidia-")]
    gpu = {Requirement(line).name.lower() for line in project["optional-dependencies"]["gpu"]}
    assert {"nvidia-cublas-cu12", "nvidia-cudnn-cu12"} <= gpu
