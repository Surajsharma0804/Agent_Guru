"""
Shared fixtures for deployment system tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from Agent_Guru.deployment.models import Configuration, RepositoryConfig, VerificationPolicy


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory."""
    return tmp_path


@pytest.fixture
def config(tmp_path: Path) -> Configuration:
    """Provide a test configuration with temp directories."""
    return Configuration(
        repositories=[
            RepositoryConfig(name="test-repo", url="https://test.example.com", priority=0)
        ],
        verification_policy=VerificationPolicy.STRICT,
        cache_dir=tmp_path / "cache",
        network_timeout=5,
        max_retries=2,
        require_space_checks=False,
    )


@pytest.fixture
def permissive_config(tmp_path: Path) -> Configuration:
    """Configuration with PERMISSIVE verification policy."""
    return Configuration(
        verification_policy=VerificationPolicy.PERMISSIVE,
        cache_dir=tmp_path / "cache",
        network_timeout=5,
        max_retries=1,
        require_space_checks=False,
    )


@pytest.fixture
def sample_package_file(tmp_path: Path) -> Path:
    """Create a sample package file for testing."""
    pkg = tmp_path / "sample-1.0.0.whl"
    pkg.write_bytes(b"PK\x03\x04" + b"fake wheel content" * 100)
    return pkg
