"""Tests for safety gate."""


from Agent_Guru.reasoning.models.action import ActionSensitivity, Tool
from Agent_Guru.reasoning.safety.classifier import ActionSensitivityClassifier
from Agent_Guru.reasoning.safety.gate import SafetyDecision, SafetyGate


class TestSafetyDecision:
    """Tests for SafetyDecision."""

    def test_decision_creation(self):
        """Test creating a safety decision."""
        decision = SafetyDecision(
            allowed=True,
            requires_confirmation=False,
            reason="Action is safe",
            sensitivity=ActionSensitivity.SAFE,
            validation_time=0.001,
        )

        assert decision.allowed
        assert not decision.requires_confirmation
        assert decision.sensitivity == ActionSensitivity.SAFE
        assert decision.validation_time > 0


class TestSafetyGate:
    """Tests for SafetyGate."""

    def test_gate_initialization(self):
        """Test safety gate initialization."""
        gate = SafetyGate()

        assert gate is not None
        assert len(gate.get_sensitive_categories()) > 0

    def test_gate_with_custom_classifier(self):
        """Test safety gate with custom classifier."""
        classifier = ActionSensitivityClassifier()
        gate = SafetyGate(classifier=classifier)

        assert gate is not None

    def test_validate_safe_action(self):
        """Test validating a safe action."""
        gate = SafetyGate()

        tool = Tool(
            tool_id="get_weather",
            name="Get Weather",
            description="Get weather information",
            sensitivity=ActionSensitivity.SAFE,
        )

        decision = gate.validate_action(tool, {}, "user123")

        assert decision.allowed
        assert not decision.requires_confirmation
        assert decision.sensitivity == ActionSensitivity.SAFE
        assert decision.validation_time > 0

    def test_validate_sensitive_action_requires_confirmation(self):
        """Test that sensitive actions require confirmation."""
        gate = SafetyGate()

        tool = Tool(
            tool_id="send_message",
            name="Send Message",
            description="Send a text message",
            sensitivity=ActionSensitivity.SAFE,  # Will be classified as sensitive
        )

        decision = gate.validate_action(tool, {"recipient": "+1234567890"}, "user123")

        assert decision.allowed
        assert decision.requires_confirmation
        assert decision.sensitivity == ActionSensitivity.SENSITIVE

    def test_validate_dangerous_action_without_permission(self):
        """Test that dangerous actions are blocked without permission."""
        gate = SafetyGate()

        tool = Tool(
            tool_id="delete_file",
            name="Delete File",
            description="Delete a file",
            sensitivity=ActionSensitivity.SAFE,  # Will be classified as dangerous
        )

        decision = gate.validate_action(tool, {"path": "/important/file.txt"}, "user123")

        assert not decision.allowed
        assert not decision.requires_confirmation  # Blocked, not just requiring confirmation
        assert decision.sensitivity == ActionSensitivity.DANGEROUS
        assert "blocked" in decision.reason.lower()

    def test_validate_dangerous_action_with_permission(self):
        """Test that dangerous actions are allowed with permission."""
        gate = SafetyGate()

        tool = Tool(
            tool_id="delete_file",
            name="Delete File",
            description="Delete a file",
            sensitivity=ActionSensitivity.DANGEROUS,
            requires_permission=True,
            permission_scope="file_deletion",
        )

        # Grant permission
        gate.grant_permission("user123", "file_deletion")

        decision = gate.validate_action(tool, {"path": "/important/file.txt"}, "user123")

        assert decision.allowed
        assert decision.requires_confirmation  # Still requires confirmation
        assert decision.sensitivity == ActionSensitivity.DANGEROUS

    def test_validate_action_without_required_permission(self):
        """Test that actions requiring permissions are blocked without them."""
        gate = SafetyGate()

        tool = Tool(
            tool_id="send_email",
            name="Send Email",
            description="Send an email",
            sensitivity=ActionSensitivity.SENSITIVE,
            requires_permission=True,
            permission_scope="messaging",
        )

        decision = gate.validate_action(tool, {"to": "user@example.com"}, "user123")

        assert not decision.allowed
        assert "permission" in decision.reason.lower()

    def test_validate_action_with_required_permission(self):
        """Test that actions with required permissions are allowed."""
        gate = SafetyGate()

        tool = Tool(
            tool_id="send_email",
            name="Send Email",
            description="Send an email",
            sensitivity=ActionSensitivity.SENSITIVE,
            requires_permission=True,
            permission_scope="messaging",
        )

        # Grant permission
        gate.grant_permission("user123", "messaging")

        decision = gate.validate_action(tool, {"to": "user@example.com"}, "user123")

        assert decision.allowed
        assert decision.requires_confirmation

    def test_grant_permission(self):
        """Test granting permission to user."""
        gate = SafetyGate()

        gate.grant_permission("user123", "messaging")

        perms = gate.get_user_permissions("user123")
        assert "messaging" in perms

    def test_grant_multiple_permissions(self):
        """Test granting multiple permissions."""
        gate = SafetyGate()

        gate.grant_permission("user123", "messaging")
        gate.grant_permission("user123", "file_deletion")

        perms = gate.get_user_permissions("user123")
        assert "messaging" in perms
        assert "file_deletion" in perms

    def test_revoke_permission(self):
        """Test revoking permission from user."""
        gate = SafetyGate()

        gate.grant_permission("user123", "messaging")
        revoked = gate.revoke_permission("user123", "messaging")

        assert revoked
        perms = gate.get_user_permissions("user123")
        assert "messaging" not in perms

    def test_revoke_nonexistent_permission(self):
        """Test revoking permission user doesn't have."""
        gate = SafetyGate()

        revoked = gate.revoke_permission("user123", "messaging")

        assert not revoked

    def test_get_user_permissions_empty(self):
        """Test getting permissions for user with none."""
        gate = SafetyGate()

        perms = gate.get_user_permissions("user123")

        assert len(perms) == 0

    def test_get_user_permissions_returns_copy(self):
        """Test that get_user_permissions returns a copy."""
        gate = SafetyGate()

        gate.grant_permission("user123", "messaging")

        perms1 = gate.get_user_permissions("user123")
        perms2 = gate.get_user_permissions("user123")

        assert perms1 is not perms2
        assert perms1 == perms2

    def test_check_permissions_no_requirement(self):
        """Test checking permissions for tool without requirements."""
        gate = SafetyGate()

        tool = Tool(
            tool_id="get_weather",
            name="Get Weather",
            description="Get weather",
            requires_permission=False,
        )

        has_permission = gate.check_permissions("user123", tool)

        assert has_permission

    def test_check_permissions_with_requirement(self):
        """Test checking permissions for tool with requirements."""
        gate = SafetyGate()

        tool = Tool(
            tool_id="send_email",
            name="Send Email",
            description="Send email",
            requires_permission=True,
            permission_scope="messaging",
        )

        # Without permission
        assert not gate.check_permissions("user123", tool)

        # With permission
        gate.grant_permission("user123", "messaging")
        assert gate.check_permissions("user123", tool)

    def test_add_sensitive_category(self):
        """Test adding a sensitive category."""
        gate = SafetyGate()

        gate.add_sensitive_category("custom_category")

        categories = gate.get_sensitive_categories()
        assert "custom_category" in categories

    def test_remove_sensitive_category(self):
        """Test removing a sensitive category."""
        gate = SafetyGate()

        gate.add_sensitive_category("custom_category")
        removed = gate.remove_sensitive_category("custom_category")

        assert removed
        categories = gate.get_sensitive_categories()
        assert "custom_category" not in categories

    def test_remove_nonexistent_category(self):
        """Test removing nonexistent category."""
        gate = SafetyGate()

        removed = gate.remove_sensitive_category("nonexistent")

        assert not removed

    def test_get_sensitive_categories_returns_copy(self):
        """Test that get_sensitive_categories returns a copy."""
        gate = SafetyGate()

        cats1 = gate.get_sensitive_categories()
        cats2 = gate.get_sensitive_categories()

        assert cats1 is not cats2
        assert cats1 == cats2

    def test_blocked_actions_logged(self):
        """Test that blocked actions are logged."""
        gate = SafetyGate()

        tool = Tool(
            tool_id="delete_file",
            name="Delete File",
            description="Delete a file",
            sensitivity=ActionSensitivity.DANGEROUS,
        )

        # This should be blocked
        gate.validate_action(tool, {"path": "/file.txt"}, "user123")

        blocked = gate.get_blocked_actions()
        assert len(blocked) > 0

        # Check last blocked action
        timestamp, user_id, tool_id, reason = blocked[-1]
        assert user_id == "user123"
        assert tool_id == "delete_file"

    def test_blocked_actions_filtered_by_user(self):
        """Test filtering blocked actions by user."""
        gate = SafetyGate()

        tool = Tool(
            tool_id="delete_file",
            name="Delete File",
            description="Delete a file",
            sensitivity=ActionSensitivity.DANGEROUS,
        )

        # Block actions for different users
        gate.validate_action(tool, {}, "user1")
        gate.validate_action(tool, {}, "user2")
        gate.validate_action(tool, {}, "user1")

        # Get blocked actions for user1
        blocked = gate.get_blocked_actions(user_id="user1")

        assert len(blocked) == 2
        assert all(entry[1] == "user1" for entry in blocked)

    def test_blocked_actions_limit(self):
        """Test limiting blocked actions returned."""
        gate = SafetyGate()

        tool = Tool(
            tool_id="delete_file",
            name="Delete File",
            description="Delete a file",
            sensitivity=ActionSensitivity.DANGEROUS,
        )

        # Block multiple actions
        for i in range(10):
            gate.validate_action(tool, {}, f"user{i}")

        # Get limited results
        blocked = gate.get_blocked_actions(limit=5)

        assert len(blocked) == 5

    def test_clear_blocked_actions_log(self):
        """Test clearing blocked actions log."""
        gate = SafetyGate()

        tool = Tool(
            tool_id="delete_file",
            name="Delete File",
            description="Delete a file",
            sensitivity=ActionSensitivity.DANGEROUS,
        )

        gate.validate_action(tool, {}, "user123")

        assert len(gate.get_blocked_actions()) > 0

        gate.clear_blocked_actions_log()

        assert len(gate.get_blocked_actions()) == 0

    def test_validation_time_measured(self):
        """Test that validation time is measured."""
        gate = SafetyGate()

        tool = Tool(
            tool_id="get_weather",
            name="Get Weather",
            description="Get weather",
            sensitivity=ActionSensitivity.SAFE,
        )

        decision = gate.validate_action(tool, {}, "user123")

        assert decision.validation_time > 0
        assert decision.validation_time < 1.0  # Should be fast

    def test_sensitive_category_requires_confirmation(self):
        """Test that tools in sensitive categories require confirmation."""
        gate = SafetyGate()

        tool = Tool(
            tool_id="custom_tool",
            name="Custom Tool",
            description="Custom tool",
            sensitivity=ActionSensitivity.SAFE,
            permission_scope="financial",  # Sensitive category
        )

        decision = gate.validate_action(tool, {}, "user123")

        assert decision.allowed
        assert decision.requires_confirmation
