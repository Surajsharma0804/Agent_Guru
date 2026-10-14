"""Policy checks running on several threads at once, as the orchestrator runs them."""

import logging
from concurrent.futures import ThreadPoolExecutor

from Agent_Guru.policy import PolicyEngine
from Agent_Guru.policy.defaults import install_default_policies
from Agent_Guru.policy.models import AccessDecision, Principal, Resource


def test_concurrent_evaluations_on_the_default_engine_all_decide_and_are_audited(caplog):
    """The default engine keeps one in-memory SQLite connection for storage and audit.

    The orchestrator evaluates policy on thread-pool threads. With that
    connection shared unguarded, 16 threads raised in about 250 of 2,000
    evaluations and about 260 audit writes failed; every exception became
    a deny, which is how concurrent MCP calls were refused on CI.
    """
    engine = PolicyEngine(enable_caching=False)
    install_default_policies(engine)
    principal = Principal(id="guru_pipeline", attributes={"role": "assistant"})
    resource = Resource(id="action", type="command")
    errors: list[str] = []

    def check(_: int) -> None:
        try:
            decision = engine.evaluate_policy(principal, resource, "information:question")
            assert isinstance(decision, AccessDecision)  # nosec B101
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")

    with caplog.at_level(logging.ERROR, logger="Agent_Guru.policy.engine"):
        with ThreadPoolExecutor(16) as pool:
            list(pool.map(check, range(1000)))

    assert errors == []  # nosec B101
    assert not [r for r in caplog.records if "Audit log write failed" in r.getMessage()]  # nosec B101
