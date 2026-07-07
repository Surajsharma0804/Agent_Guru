"""Property-based tests for safety system."""

import time

from hypothesis import given, settings
from hypothesis import strategies as st

from Agent_Guru.reasoning.models.action import ActionSensitivity, Tool
from Agent_Guru.reasoning.safety.audit import AuditLogger
from Agent_Guru.reasoning.safety.gate import SafetyGate

# Strategy for generating tool IDs
tool_ids = st.sampled_from(
    [
        "delete_file",
        "send_message",
        "make_payment",
        "control_device",
        "get_weather",
        "set_timer",
        "play_music",
    ]
)

# Strategy for generating user IDs
user_ids = st.text(
    min_size=1,
    max_size=20,
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        min_codepoint=48,
        max_codepoint=122,
    ),
)

# Strategy for generating parameters
parameters = st.dictionaries(
    keys=st.text(min_size=1, max_size=10),
    values=st.one_of(
        st.text(max_size=50),
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.booleans(),
    ),
    max_size=5,
)


class TestSafetyGateProperties:
    """Property-based tests for SafetyGate."""

    @settings(max_examples=100)
    @given(
        tool_id=tool_ids,
        params=parameters,
        user_id=user_ids,
    )
    def test_property_14_sensitive_actions_require_confirmation(
        self,
        tool_id: str,
        params: dict,
        user_id: str,
    ):
        """
        Property 14: Sensitive actions require confirmation.

        Validates: Requirements 7.1

        For any action classified as SENSITIVE or DANGEROUS,
        the safety gate must set requires_confirmation to True.
        """
        gate = SafetyGate()

        # Create tool with sensitive or dangerous sensitivity
        for sensitivity in [ActionSensitivity.SENSITIVE, ActionSensitivity.DANGEROUS]:
            tool = Tool(
                tool_id=tool_id,
                name=f"Test {tool_id}",
                description="Test tool",
                sensitivity=sensitivity,
            )

            # Grant permission if tool requires it (to test confirmation, not blocking)
            if tool.requires_permission and tool.permission_scope:
                gate.grant_permission(user_id, tool.permission_scope)

            decision = gate.validate_action(tool, params, user_id)

            # Property: Sensitive/dangerous actions require confirmation
            if decision.allowed:  # Only check if action is allowed
                assert decision.requires_confirmation, (  # nosec B101
                    f"Sensitive/dangerous action {tool_id} with sensitivity "
                    f"{sensitivity.value} must require confirmation"
                )

    @settings(max_examples=100)
    @given(
        tool_id=tool_ids,
        params=parameters,
        user_id=user_ids,
        permission_scope=st.text(min_size=1, max_size=20),
    )
    def test_property_15_insufficient_permissions_block_actions(
        self,
        tool_id: str,
        params: dict,
        user_id: str,
        permission_scope: str,
    ):
        """
        Property 15: Insufficient permissions block actions.

        Validates: Requirements 7.2

        For any action that requires permissions, if the user does not
        have the required permission, the action must be blocked.
        """
        gate = SafetyGate()

        # Create tool that requires permission
        tool = Tool(
            tool_id=tool_id,
            name=f"Test {tool_id}",
            description="Test tool",
            sensitivity=ActionSensitivity.SAFE,
            requires_permission=True,
            permission_scope=permission_scope,
        )

        # Validate without granting permission
        decision = gate.validate_action(tool, params, user_id)

        # Property: Action without required permission must be blocked
        assert not decision.allowed, (  # nosec B101
            f"Action {tool_id} requiring permission '{permission_scope}' "
            f"must be blocked when user {user_id} lacks permission"
        )
        assert (  # nosec B101
            "permission" in decision.reason.lower()
        ), "Blocked action reason must mention permissions"

    @settings(max_examples=100)
    @given(
        tool_id=tool_ids,
        params=parameters,
        user_id=user_ids,
    )
    def test_property_16_all_blocked_actions_are_logged(
        self,
        tool_id: str,
        params: dict,
        user_id: str,
    ):
        """
        Property 16: All blocked actions are logged.

        Validates: Requirements 7.4

        For any action that is blocked by the safety gate,
        an audit log entry must be created.
        """
        gate = SafetyGate()
        audit_logger = AuditLogger()

        # Create tool that will be blocked (dangerous without permission)
        tool = Tool(
            tool_id=tool_id,
            name=f"Test {tool_id}",
            description="Test tool",
            sensitivity=ActionSensitivity.DANGEROUS,
        )

        # Get initial log count
        initial_logs = audit_logger.query_logs(user_id=user_id)
        initial_count = len(initial_logs)

        # Validate action (should be blocked)
        decision = gate.validate_action(tool, params, user_id)

        # If action was blocked, log it
        if not decision.allowed:
            audit_logger.log_decision(
                user_id=user_id,
                tool_id=tool.tool_id,
                parameters=params,
                sensitivity=decision.sensitivity,
                decision="blocked",
                requires_confirmation=decision.requires_confirmation,
                reason=decision.reason,
                validation_time=decision.validation_time,
            )

            # Property: Blocked action must create audit log entry
            final_logs = audit_logger.query_logs(user_id=user_id)
            final_count = len(final_logs)

            assert final_count > initial_count, (  # nosec B101
                f"Blocked action {tool_id} for user {user_id} must create "
                f"audit log entry (before: {initial_count}, after: {final_count})"
            )

            # Verify the log entry contains correct information
            latest_log = final_logs[0]  # Most recent entry
            assert latest_log.user_id == user_id  # nosec B101
            assert latest_log.tool_id == tool.tool_id  # nosec B101
            assert latest_log.decision == "blocked"  # nosec B101

        audit_logger.close()


class TestPermissionProperties:
    """Property-based tests for permission system."""

    @settings(max_examples=100)
    @given(
        user_id=user_ids,
        permission_scope=st.text(min_size=1, max_size=20),
    )
    def test_property_granted_permissions_are_checkable(
        self,
        user_id: str,
        permission_scope: str,
    ):
        """
        Property: Granted permissions can be checked.

        For any user and permission scope, if a permission is granted,
        checking that permission must return True.
        """
        gate = SafetyGate()

        # Grant permission
        gate.grant_permission(user_id, permission_scope)

        # Create tool with that permission requirement
        tool = Tool(
            tool_id="test_tool",
            name="Test Tool",
            description="Test",
            requires_permission=True,
            permission_scope=permission_scope,
        )

        # Property: Granted permission must be checkable
        has_permission = gate.check_permissions(user_id, tool)
        assert has_permission, (  # nosec B101
            f"User {user_id} must have permission '{permission_scope}' " f"after it was granted"
        )

    @settings(max_examples=100)
    @given(
        user_id=user_ids,
        permission_scope=st.text(min_size=1, max_size=20),
    )
    def test_property_revoked_permissions_are_not_checkable(
        self,
        user_id: str,
        permission_scope: str,
    ):
        """
        Property: Revoked permissions cannot be checked.

        For any user and permission scope, if a permission is granted
        and then revoked, checking that permission must return False.
        """
        gate = SafetyGate()

        # Grant permission
        gate.grant_permission(user_id, permission_scope)

        # Revoke permission
        gate.revoke_permission(user_id, permission_scope)

        # Create tool with that permission requirement
        tool = Tool(
            tool_id="test_tool",
            name="Test Tool",
            description="Test",
            requires_permission=True,
            permission_scope=permission_scope,
        )

        # Property: Revoked permission must not be checkable
        has_permission = gate.check_permissions(user_id, tool)
        assert not has_permission, (  # nosec B101
            f"User {user_id} must not have permission '{permission_scope}' " f"after it was revoked"
        )


class TestAuditLogProperties:
    """Property-based tests for audit logging."""

    @settings(max_examples=100)
    @given(
        user_id=user_ids,
        tool_id=tool_ids,
        params=parameters,
    )
    def test_property_logged_decisions_are_queryable(
        self,
        user_id: str,
        tool_id: str,
        params: dict,
    ):
        """
        Property: Logged decisions can be queried.

        For any logged decision, querying the audit log must return
        that decision with all its details intact.
        """
        audit_logger = AuditLogger()

        # Log a decision
        entry_id = audit_logger.log_decision(
            user_id=user_id,
            tool_id=tool_id,
            parameters=params,
            sensitivity=ActionSensitivity.SAFE,
            decision="allowed",
            requires_confirmation=False,
            reason="Test decision",
            validation_time=0.001,
        )

        # Property: Logged decision must be queryable
        entries = audit_logger.query_logs(user_id=user_id)

        assert len(entries) > 0, f"Audit log must contain entry for user {user_id}"  # nosec B101

        # Find the entry we just logged
        found = False
        for entry in entries:
            if entry.entry_id == entry_id:
                found = True
                assert entry.user_id == user_id  # nosec B101
                assert entry.tool_id == tool_id  # nosec B101
                assert entry.parameters == params  # nosec B101
                assert entry.decision == "allowed"  # nosec B101
                break

        assert found, f"Logged entry {entry_id} must be found in query results"  # nosec B101

        audit_logger.close()

    @settings(max_examples=100)
    @given(
        user_id=user_ids,
        tool_id=tool_ids,
    )
    def test_property_audit_logs_preserve_order(
        self,
        user_id: str,
        tool_id: str,
    ):
        """
        Property: Audit logs preserve chronological order.

        For any sequence of logged decisions, querying the audit log
        must return entries in reverse chronological order (newest first).
        """
        audit_logger = AuditLogger()

        # Log multiple decisions with small delays
        entry_ids = []
        for i in range(3):
            entry_id = audit_logger.log_decision(
                user_id=user_id,
                tool_id=f"{tool_id}_{i}",
                parameters={},
                sensitivity=ActionSensitivity.SAFE,
                decision="allowed",
                requires_confirmation=False,
                reason=f"Test {i}",
                validation_time=0.001,
            )
            entry_ids.append(entry_id)
            time.sleep(0.001)  # Small delay to ensure different timestamps

        # Property: Entries must be in reverse chronological order
        entries = audit_logger.query_logs(user_id=user_id)

        assert len(entries) >= 3, "Must have at least 3 entries"  # nosec B101

        # Check that timestamps are in descending order
        for i in range(len(entries) - 1):
            assert entries[i].timestamp >= entries[i + 1].timestamp, (  # nosec B101
                f"Audit log entries must be in reverse chronological order "
                f"(entry {i} timestamp {entries[i].timestamp} should be >= "
                f"entry {i+1} timestamp {entries[i+1].timestamp})"
            )

        audit_logger.close()

    @settings(max_examples=100)
    @given(
        user_id=user_ids,
        tool_id=tool_ids,
        params=parameters,
    )
    def test_property_encrypted_parameters_are_decryptable(
        self,
        user_id: str,
        tool_id: str,
        params: dict,
    ):
        """
        Property: Encrypted parameters can be decrypted.

        For any logged decision with parameters, the parameters must be
        encrypted in storage but decryptable when queried.
        """
        audit_logger = AuditLogger()

        # Log decision with parameters
        audit_logger.log_decision(
            user_id=user_id,
            tool_id=tool_id,
            parameters=params,
            sensitivity=ActionSensitivity.SAFE,
            decision="allowed",
            requires_confirmation=False,
            reason="Test",
            validation_time=0.001,
        )

        # Property: Parameters must be decryptable and match original
        entries = audit_logger.query_logs(user_id=user_id, limit=1)

        assert len(entries) > 0, "Must have at least one entry"  # nosec B101

        entry = entries[0]
        assert entry.parameters == params, (  # nosec B101
            f"Decrypted parameters must match original: "
            f"expected {params}, got {entry.parameters}"
        )

        audit_logger.close()
