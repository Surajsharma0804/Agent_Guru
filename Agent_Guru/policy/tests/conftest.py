"""Shared fixtures and helpers for policy engine tests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from Agent_Guru.policy.engine import PolicyEngine
from Agent_Guru.policy.models import (
    Policy,
    PolicyEffect,
    Principal,
    Resource,
    Role,
)


def make_policy(
    policy_id: str = "p1",
    name: str = "Test Policy",
    effect: PolicyEffect = PolicyEffect.ALLOW,
    priority: int = 0,
    principals: list | None = None,
    resources: list | None = None,
    actions: list | None = None,
    conditions: dict[str, Any] | None = None,
    active: bool = True,
) -> Policy:
    return Policy(
        id=policy_id,
        version=1,
        name=name,
        description="",
        effect=effect,
        priority=priority,
        principals=principals or ["*"],
        resources=resources or ["*"],
        actions=actions or ["*"],
        conditions=conditions or {},
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
        active=active,
    )


def make_principal(pid: str = "user1", **attrs: Any) -> Principal:
    return Principal(id=pid, attributes=dict(attrs))


def make_resource(rid: str = "res1", rtype: str = "file", **attrs: Any) -> Resource:
    return Resource(id=rid, type=rtype, attributes=dict(attrs))


def make_role(
    role_id: str = "r1",
    name: str = "TestRole",
    permissions: list | None = None,
    parent_role_id: str | None = None,
) -> Role:
    return Role(
        id=role_id,
        name=name,
        permissions=permissions or [],
        created_at=datetime.now(tz=timezone.utc),
        parent_role_id=parent_role_id,
    )


@pytest.fixture
def engine() -> PolicyEngine:
    return PolicyEngine(enable_caching=True, default_ttl=300)


@pytest.fixture
def engine_no_cache() -> PolicyEngine:
    return PolicyEngine(enable_caching=False)
