#!/usr/bin/env python3
"""
Verification script for Core Reasoning Engine setup.
Checks that all components of Task 1 are properly implemented.
"""

import sys
import os
from pathlib import Path
import tomllib


def check_mark(condition: bool) -> str:
    """Return checkmark or X based on condition."""
    return "✅" if condition else "❌"


def verify_directory_structure() -> bool:
    """Verify the directory structure is correct."""
    print("\n📁 Verifying Directory Structure...")
    
    required_dirs = [
        "Agent_Guru/reasoning",
        "Agent_Guru/reasoning/models",
        "Agent_Guru/reasoning/state",
        "Agent_Guru/reasoning/tools",
        "Agent_Guru/reasoning/config",
        "Agent_Guru/reasoning/tests",
    ]
    
    all_exist = True
    for dir_path in required_dirs:
        exists = Path(dir_path).is_dir()
        print(f"  {check_mark(exists)} {dir_path}")
        all_exist = all_exist and exists
    
    return all_exist


def verify_init_files() -> bool:
    """Verify all __init__.py files exist."""
    print("\n📄 Verifying __init__.py Files...")
    
    required_inits = [
        "Agent_Guru/reasoning/__init__.py",
        "Agent_Guru/reasoning/models/__init__.py",
        "Agent_Guru/reasoning/state/__init__.py",
        "Agent_Guru/reasoning/tools/__init__.py",
        "Agent_Guru/reasoning/config/__init__.py",
        "Agent_Guru/reasoning/tests/__init__.py",
    ]
    
    all_exist = True
    for init_path in required_inits:
        exists = Path(init_path).is_file()
        print(f"  {check_mark(exists)} {init_path}")
        all_exist = all_exist and exists
    
    return all_exist


def verify_config_files() -> bool:
    """Verify configuration files exist and are valid."""
    print("\n⚙️  Verifying Configuration Files...")
    
    config_files = {
        "pyproject.toml": "TOML configuration",
        "mypy.ini": "MyPy configuration",
        ".pre-commit-config.yaml": "Pre-commit hooks",
        "Dockerfile": "Docker configuration",
        "docker-compose.yml": "Docker Compose configuration",
        "setup_dev.sh": "Linux/macOS setup script",
        "setup_dev.bat": "Windows setup script",
    }
    
    all_exist = True
    for file_path, description in config_files.items():
        exists = Path(file_path).is_file()
        print(f"  {check_mark(exists)} {file_path} ({description})")
        all_exist = all_exist and exists
    
    return all_exist


def verify_pyproject_toml() -> bool:
    """Verify pyproject.toml has required dependencies."""
    print("\n📦 Verifying pyproject.toml Dependencies...")
    
    try:
        with open("pyproject.toml", "rb") as f:
            config = tomllib.load(f)
        
        # Check Python version
        python_version = config["project"]["requires-python"]
        has_python_311 = "3.11" in python_version
        print(f"  {check_mark(has_python_311)} Python version: {python_version}")
        
        # Check core dependencies
        required_deps = [
            "pydantic",
            "structlog",
            "prometheus-client",
            "asyncio" if "asyncio" in str(config["project"]["dependencies"]) else None,
        ]
        
        deps = config["project"]["dependencies"]
        deps_str = " ".join(deps)
        
        has_pydantic = any("pydantic" in dep for dep in deps)
        has_structlog = any("structlog" in dep for dep in deps)
        has_prometheus = any("prometheus-client" in dep for dep in deps)
        
        print(f"  {check_mark(has_pydantic)} pydantic")
        print(f"  {check_mark(has_structlog)} structlog")
        print(f"  {check_mark(has_prometheus)} prometheus-client")
        
        # Check dev dependencies
        dev_deps = config["project"]["optional-dependencies"]["dev"]
        dev_deps_str = " ".join(dev_deps)
        
        has_pytest = any("pytest" in dep for dep in dev_deps)
        has_hypothesis = any("hypothesis" in dep for dep in dev_deps)
        has_black = any("black" in dep for dep in dev_deps)
        has_ruff = any("ruff" in dep for dep in dev_deps)
        has_mypy = any("mypy" in dep for dep in dev_deps)
        
        print(f"  {check_mark(has_pytest)} pytest")
        print(f"  {check_mark(has_hypothesis)} hypothesis")
        print(f"  {check_mark(has_black)} black")
        print(f"  {check_mark(has_ruff)} ruff")
        print(f"  {check_mark(has_mypy)} mypy")
        
        # Check tool configurations
        has_black_config = "tool" in config and "black" in config["tool"]
        has_ruff_config = "tool" in config and "ruff" in config["tool"]
        has_mypy_config = "tool" in config and "mypy" in config["tool"]
        has_pytest_config = "tool" in config and "pytest" in config["tool"]
        
        print(f"  {check_mark(has_black_config)} black configuration")
        print(f"  {check_mark(has_ruff_config)} ruff configuration")
        print(f"  {check_mark(has_mypy_config)} mypy configuration")
        print(f"  {check_mark(has_pytest_config)} pytest configuration")
        
        return all([
            has_python_311,
            has_pydantic,
            has_structlog,
            has_prometheus,
            has_pytest,
            has_hypothesis,
            has_black,
            has_ruff,
            has_mypy,
            has_black_config,
            has_ruff_config,
            has_mypy_config,
            has_pytest_config,
        ])
        
    except Exception as e:
        print(f"  ❌ Error reading pyproject.toml: {e}")
        return False


def verify_imports() -> bool:
    """Verify Python packages can be imported."""
    print("\n🐍 Verifying Python Imports...")
    
    try:
        import Agent_Guru.reasoning
        print(f"  ✅ Agent_Guru.reasoning")
        
        from Agent_Guru.reasoning import models, state, tools, config, tests
        print(f"  ✅ All submodules (models, state, tools, config, tests)")
        
        return True
    except ImportError as e:
        print(f"  ❌ Import error: {e}")
        return False


def verify_documentation() -> bool:
    """Verify documentation files exist."""
    print("\n📚 Verifying Documentation...")
    
    doc_files = [
        "Agent_Guru/reasoning/README.md",
    ]
    
    all_exist = True
    for doc_path in doc_files:
        exists = Path(doc_path).is_file()
        print(f"  {check_mark(exists)} {doc_path}")
        all_exist = all_exist and exists
    
    return all_exist


def verify_mypy_strict_mode() -> bool:
    """Verify mypy is configured in strict mode."""
    print("\n🔍 Verifying MyPy Strict Mode...")
    
    try:
        with open("mypy.ini", "r") as f:
            content = f.read()
        
        has_strict = "strict = True" in content
        has_python_311 = "python_version = 3.11" in content
        
        print(f"  {check_mark(has_strict)} strict = True")
        print(f"  {check_mark(has_python_311)} python_version = 3.11")
        
        return has_strict and has_python_311
    except Exception as e:
        print(f"  ❌ Error reading mypy.ini: {e}")
        return False


def main():
    """Run all verification checks."""
    print("=" * 70)
    print("🔍 Core Reasoning Engine - Task 1 Verification")
    print("=" * 70)
    
    checks = [
        ("Directory Structure", verify_directory_structure),
        ("__init__.py Files", verify_init_files),
        ("Configuration Files", verify_config_files),
        ("pyproject.toml", verify_pyproject_toml),
        ("Python Imports", verify_imports),
        ("Documentation", verify_documentation),
        ("MyPy Strict Mode", verify_mypy_strict_mode),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Error in {name}: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 Verification Summary")
    print("=" * 70)
    
    for name, result in results:
        print(f"  {check_mark(result)} {name}")
    
    all_passed = all(result for _, result in results)
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✅ ALL CHECKS PASSED - Task 1 is fully implemented!")
    else:
        print("❌ SOME CHECKS FAILED - Please review the issues above")
    print("=" * 70)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
