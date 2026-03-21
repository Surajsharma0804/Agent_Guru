"""
Pytest fixtures for Goal Manager tests.

Provides common fixtures and test utilities.
"""

import pytest
import tempfile
import os
from pathlib import Path
from typing import Generator
from datetime import datetime

from Agent_Guru.goal_manager.models import Goal, GoalStatus, Priority


@pytest.fixture
def temp_db_path() -> Generator[str, None, None]:
    """Provide a temporary database path for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    yield db_path
    
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def temp_git_repo() -> Generator[Path, None, None]:
    """Provide a temporary git repository for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        
        # Initialize git repo
        os.system(f"cd {repo_path} && git init")
        os.system(f"cd {repo_path} && git config user.email 'test@example.com'")
        os.system(f"cd {repo_path} && git config user.name 'Test User'")
        
        yield repo_path


@pytest.fixture
def sample_goal() -> Goal:
    """Provide a sample goal for testing."""
    return Goal(
        description="Test goal",
        status=GoalStatus.PENDING,
        priority=Priority.MEDIUM,
        progress=0.0,
        created_at=datetime.now(),
    )


@pytest.fixture
def sample_goal_with_subgoals() -> Goal:
    """Provide a sample goal with sub-goals for testing."""
    parent = Goal(
        description="Parent goal",
        status=GoalStatus.PENDING,
        priority=Priority.HIGH,
        progress=0.0,
        created_at=datetime.now(),
    )
    
    # Create sub-goals
    sub1 = Goal(
        description="Sub-goal 1",
        parent_id=parent.id,
        status=GoalStatus.PENDING,
        priority=Priority.HIGH,
        progress=0.0,
        created_at=datetime.now(),
    )
    
    sub2 = Goal(
        description="Sub-goal 2",
        parent_id=parent.id,
        status=GoalStatus.PENDING,
        priority=Priority.HIGH,
        progress=0.0,
        created_at=datetime.now(),
    )
    
    parent.sub_goal_ids = [sub1.id, sub2.id]
    
    return parent


import asyncio
import gc


@pytest.fixture(autouse=True)
async def cancel_background_tasks():
    """Cancel any lingering asyncio tasks after each test to prevent hangs."""
    yield
    # Cancel all tasks except the current one
    current = asyncio.current_task()
    tasks = [t for t in asyncio.all_tasks() if t is not current and not t.done()]
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    # Force garbage collection to close any open SQLite connections
    gc.collect()
