"""Tests for Phase 1 Repository Intelligence Scan analyzers.

This module tests the new analyzers added in Task 2.4:
- ExternalServiceAnalyzer
- ConfigurationMapper
- CacheAnalyzer
"""

from __future__ import annotations

from pathlib import Path

import pytest

from audit.phases.phase1_repo_scan import (
    CacheAnalyzer,
    ConfigurationMapper,
    ExternalServiceAnalyzer,
)


class TestExternalServiceAnalyzer:
    """Tests for ExternalServiceAnalyzer."""

    def test_initialization(self) -> None:
        """Test analyzer initialization."""
        package_root = Path("Agent_Guru")
        analyzer = ExternalServiceAnalyzer(package_root)

        assert analyzer.package_root == package_root
        assert isinstance(analyzer.external_services, dict)
        assert "openai" in analyzer.external_services
        assert "anthropic" in analyzer.external_services

    def test_enumerate_external_services_returns_list(self) -> None:
        """Test that enumerate_external_services returns a list."""
        # Use current directory as package root for testing
        package_root = Path(__file__).parent.parent.parent / "Agent_Guru"

        if not package_root.exists():
            pytest.skip("Agent_Guru package not found")

        analyzer = ExternalServiceAnalyzer(package_root)
        services = analyzer.enumerate_external_services()

        assert isinstance(services, list)
        # Each service should be a dictionary
        for service in services:
            assert isinstance(service, dict)
            assert "service" in service
            assert "category" in service
            assert "protocol" in service
            assert "library" in service

    def test_generate_service_table(self) -> None:
        """Test service table generation."""
        package_root = Path("Agent_Guru")
        analyzer = ExternalServiceAnalyzer(package_root)

        # Create sample services
        services = [
            {
                "service": "openai",
                "category": "LLM Provider",
                "protocol": "HTTPS/REST",
                "library": "openai",
                "has_error_handling": True,
            },
        ]

        table = analyzer.generate_service_table(services)

        assert isinstance(table, str)
        assert "External Service Boundaries" in table
        assert "openai" in table
        assert "LLM Provider" in table


class TestConfigurationMapper:
    """Tests for ConfigurationMapper."""

    def test_initialization(self) -> None:
        """Test mapper initialization."""
        repo_root = Path(".")
        mapper = ConfigurationMapper(repo_root)

        assert mapper.repo_root == repo_root
        assert isinstance(mapper.config_files, list)
        assert ".env" in mapper.config_files
        assert "pyproject.toml" in mapper.config_files

    def test_map_configuration_entry_points_returns_list(self) -> None:
        """Test that map_configuration_entry_points returns a list."""
        # Use current directory as repo root for testing
        repo_root = Path(__file__).parent.parent.parent

        mapper = ConfigurationMapper(repo_root)
        config_entries = mapper.map_configuration_entry_points()

        assert isinstance(config_entries, list)
        # Each entry should be a dictionary
        for entry in config_entries:
            assert isinstance(entry, dict)
            assert "file" in entry
            assert "type" in entry
            assert "exists" in entry

    def test_infer_config_type(self) -> None:
        """Test configuration type inference."""
        repo_root = Path(".")
        mapper = ConfigurationMapper(repo_root)

        assert mapper._infer_config_type(".env") == "Environment Variables"
        assert mapper._infer_config_type("pyproject.toml") == "Project Configuration"
        assert mapper._infer_config_type("pytest.ini") == "Test Configuration"
        assert mapper._infer_config_type("mypy.ini") == "Type Checking Configuration"

    def test_generate_config_table(self) -> None:
        """Test configuration table generation."""
        repo_root = Path(".")
        mapper = ConfigurationMapper(repo_root)

        # Create sample config entries
        config_entries = [
            {
                "file": ".env",
                "type": "Environment Variables",
                "exists": True,
                "keys": ["OPENAI_API_KEY"],
                "consumers": {"OPENAI_API_KEY": ["llm/providers/openai_adapter.py"]},
            },
        ]

        table = mapper.generate_config_table(config_entries)

        assert isinstance(table, str)
        assert "Configuration Entry Points" in table
        assert ".env" in table
        assert "Environment Variables" in table


class TestCacheAnalyzer:
    """Tests for CacheAnalyzer."""

    def test_initialization(self) -> None:
        """Test analyzer initialization."""
        repo_root = Path(".")
        analyzer = CacheAnalyzer(repo_root)

        assert analyzer.repo_root == repo_root

    def test_analyze_cache_files_returns_dict(self) -> None:
        """Test that analyze_cache_files returns a dictionary."""
        # Use current directory as repo root for testing
        repo_root = Path(__file__).parent.parent.parent

        analyzer = CacheAnalyzer(repo_root)
        cache_info = analyzer.analyze_cache_files()

        assert isinstance(cache_info, dict)
        assert "pycache_directories" in cache_info
        assert "pyc_files" in cache_info
        assert "total_pycache_dirs" in cache_info
        assert "total_pyc_files" in cache_info
        assert "total_size_bytes" in cache_info
        assert "total_size_mb" in cache_info

        # Check types
        assert isinstance(cache_info["pycache_directories"], list)
        assert isinstance(cache_info["pyc_files"], list)
        assert isinstance(cache_info["total_pycache_dirs"], int)
        assert isinstance(cache_info["total_pyc_files"], int)
        assert isinstance(cache_info["total_size_bytes"], int)
        assert isinstance(cache_info["total_size_mb"], (int, float))

    def test_generate_cache_summary(self) -> None:
        """Test cache summary generation."""
        repo_root = Path(".")
        analyzer = CacheAnalyzer(repo_root)

        # Create sample cache info
        cache_info = {
            "pycache_directories": ["Agent_Guru/__pycache__"],
            "pyc_files": ["Agent_Guru/__pycache__/main.cpython-311.pyc"],
            "total_pycache_dirs": 1,
            "total_pyc_files": 1,
            "total_size_bytes": 1024,
            "total_size_mb": 0.001,
        }

        summary = analyzer.generate_cache_summary(cache_info)

        assert isinstance(summary, str)
        assert "Python Cache Files" in summary
        assert "__pycache__ Directories" in summary
        assert ".pyc Files" in summary


class TestIntegration:
    """Integration tests for all analyzers."""

    def test_all_analyzers_work_together(self) -> None:
        """Test that all analyzers can run together without errors."""
        # Use current directory structure for testing
        repo_root = Path(__file__).parent.parent.parent
        package_root = repo_root / "Agent_Guru"

        if not package_root.exists():
            pytest.skip("Agent_Guru package not found")

        # Initialize all analyzers
        external_service_analyzer = ExternalServiceAnalyzer(package_root)
        config_mapper = ConfigurationMapper(repo_root)
        cache_analyzer = CacheAnalyzer(repo_root)

        # Run all analyses
        external_services = external_service_analyzer.enumerate_external_services()
        config_entries = config_mapper.map_configuration_entry_points()
        cache_info = cache_analyzer.analyze_cache_files()

        # Verify results
        assert isinstance(external_services, list)
        assert isinstance(config_entries, list)
        assert isinstance(cache_info, dict)

        # Generate reports
        service_table = external_service_analyzer.generate_service_table(
            external_services,
        )
        config_table = config_mapper.generate_config_table(config_entries)
        cache_summary = cache_analyzer.generate_cache_summary(cache_info)

        assert isinstance(service_table, str)
        assert isinstance(config_table, str)
        assert isinstance(cache_summary, str)
