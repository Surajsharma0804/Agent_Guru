"""Tests for action sensitivity classifier."""


from Agent_Guru.reasoning.models.action import ActionSensitivity, Tool
from Agent_Guru.reasoning.safety.classifier import (
    ActionSensitivityClassifier,
    SensitivityRule,
)


class TestSensitivityRule:
    """Tests for SensitivityRule."""

    def test_rule_creation(self):
        """Test creating a sensitivity rule."""
        rule = SensitivityRule(
            tool_pattern=r".*delete.*",
            parameter_checks={},
            sensitivity=ActionSensitivity.DANGEROUS,
            reason="Deletion is dangerous",
            priority=100,
        )

        assert rule.tool_pattern == r".*delete.*"  # nosec B101
        assert rule.sensitivity == ActionSensitivity.DANGEROUS  # nosec B101
        assert rule.priority == 100  # nosec B101

    def test_rule_matches_tool_pattern(self):
        """Test rule matching by tool pattern."""
        rule = SensitivityRule(
            tool_pattern=r".*delete.*file.*",
            parameter_checks={},
            sensitivity=ActionSensitivity.DANGEROUS,
            reason="File deletion",
            priority=100,
        )

        assert rule.matches("delete_file", {})  # nosec B101
        assert rule.matches("delete_user_file", {})  # nosec B101
        assert not rule.matches("create_file", {})  # nosec B101

    def test_rule_matches_parameters(self):
        """Test rule matching with parameter checks."""
        rule = SensitivityRule(
            tool_pattern=r".*send.*",
            parameter_checks={"recipient": r".*@external\.com"},
            sensitivity=ActionSensitivity.SENSITIVE,
            reason="External communication",
            priority=50,
        )

        assert rule.matches("send_email", {"recipient": "user@external.com"})  # nosec B101
        assert not rule.matches("send_email", {"recipient": "user@internal.com"})  # nosec B101
        assert not rule.matches("send_email", {})  # Missing parameter  # nosec B101

    def test_rule_matches_multiple_parameters(self):
        """Test rule matching with multiple parameter checks."""
        rule = SensitivityRule(
            tool_pattern=r".*payment.*",
            parameter_checks={
                "amount": r"\d{4,}",  # 4+ digits
                "currency": r"USD",
            },
            sensitivity=ActionSensitivity.DANGEROUS,
            reason="Large payment",
            priority=100,
        )

        assert rule.matches("make_payment", {"amount": "1000", "currency": "USD"})  # nosec B101
        assert not rule.matches("make_payment", {"amount": "100", "currency": "USD"})  # nosec B101
        assert not rule.matches("make_payment", {"amount": "1000", "currency": "EUR"})  # nosec B101


class TestActionSensitivityClassifier:
    """Tests for ActionSensitivityClassifier."""

    def test_classifier_initialization(self):
        """Test classifier initializes with default rules."""
        classifier = ActionSensitivityClassifier()

        rules = classifier.get_rules()
        assert len(rules) > 0  # nosec B101

        # Check rules are sorted by priority
        priorities = [r.priority for r in rules]
        assert priorities == sorted(priorities, reverse=True)  # nosec B101

    def test_classify_safe_action(self):
        """Test classifying a safe action."""
        classifier = ActionSensitivityClassifier()

        tool = Tool(
            tool_id="get_weather",
            name="Get Weather",
            description="Get weather information",
            sensitivity=ActionSensitivity.SAFE,
        )

        sensitivity, reason = classifier.classify(tool, {})

        assert sensitivity == ActionSensitivity.SAFE  # nosec B101
        assert "No sensitivity rules matched" in reason  # nosec B101

    def test_classify_dangerous_delete_action(self):
        """Test classifying a dangerous delete action."""
        classifier = ActionSensitivityClassifier()

        tool = Tool(
            tool_id="delete_file",
            name="Delete File",
            description="Delete a file",
            sensitivity=ActionSensitivity.SAFE,  # Will be overridden by rules
        )

        sensitivity, reason = classifier.classify(tool, {"path": "/important/file.txt"})

        assert sensitivity == ActionSensitivity.DANGEROUS  # nosec B101
        assert "deletion" in reason.lower() or "data loss" in reason.lower()  # nosec B101

    def test_classify_sensitive_messaging_action(self):
        """Test classifying a sensitive messaging action."""
        classifier = ActionSensitivityClassifier()

        tool = Tool(
            tool_id="send_message",
            name="Send Message",
            description="Send a text message",
            sensitivity=ActionSensitivity.SAFE,  # Will be overridden by rules
        )

        sensitivity, reason = classifier.classify(tool, {"recipient": "+1234567890"})

        assert sensitivity == ActionSensitivity.SENSITIVE  # nosec B101
        assert "communication" in reason.lower() or "messaging" in reason.lower()  # nosec B101

    def test_classify_respects_tool_declared_sensitivity(self):
        """Test that tool's declared sensitivity is respected."""
        classifier = ActionSensitivityClassifier()

        tool = Tool(
            tool_id="custom_tool",
            name="Custom Tool",
            description="A custom tool",
            sensitivity=ActionSensitivity.DANGEROUS,  # Explicitly dangerous
        )

        sensitivity, reason = classifier.classify(tool, {})

        assert sensitivity == ActionSensitivity.DANGEROUS  # nosec B101
        assert "declared" in reason.lower()  # nosec B101

    def test_add_custom_rule(self):
        """Test adding a custom sensitivity rule."""
        classifier = ActionSensitivityClassifier()

        custom_rule = SensitivityRule(
            tool_pattern=r".*custom.*",
            parameter_checks={},
            sensitivity=ActionSensitivity.SENSITIVE,
            reason="Custom rule",
            priority=200,  # High priority
        )

        classifier.add_rule(custom_rule)

        tool = Tool(
            tool_id="custom_action",
            name="Custom Action",
            description="A custom action",
            sensitivity=ActionSensitivity.SAFE,
        )

        sensitivity, reason = classifier.classify(tool, {})

        assert sensitivity == ActionSensitivity.SENSITIVE  # nosec B101
        assert reason == "Custom rule"  # nosec B101

    def test_remove_rule(self):
        """Test removing a sensitivity rule."""
        classifier = ActionSensitivityClassifier()

        initial_count = len(classifier.get_rules())

        # Remove a rule
        removed = classifier.remove_rule(r".*delete.*file.*")

        assert removed  # nosec B101
        assert len(classifier.get_rules()) == initial_count - 1  # nosec B101

    def test_remove_nonexistent_rule(self):
        """Test removing a nonexistent rule."""
        classifier = ActionSensitivityClassifier()

        removed = classifier.remove_rule(r".*nonexistent.*")

        assert not removed  # nosec B101

    def test_clear_rules(self):
        """Test clearing all rules."""
        classifier = ActionSensitivityClassifier()

        classifier.clear_rules()

        assert len(classifier.get_rules()) == 0  # nosec B101

    def test_load_rules_from_config(self):
        """Test loading rules from configuration."""
        classifier = ActionSensitivityClassifier()

        config = {
            "rules": [
                {
                    "tool_pattern": r".*test.*",
                    "parameter_checks": {},
                    "sensitivity": "sensitive",
                    "reason": "Test rule",
                    "priority": 100,
                },
                {
                    "tool_pattern": r".*admin.*",
                    "parameter_checks": {"action": r"delete"},
                    "sensitivity": "dangerous",
                    "reason": "Admin delete",
                    "priority": 200,
                },
            ]
        }

        classifier.load_rules_from_config(config)

        rules = classifier.get_rules()
        assert len(rules) == 2  # nosec B101
        assert rules[0].priority == 200  # Highest priority first  # nosec B101
        assert rules[1].priority == 100  # nosec B101

    def test_rule_priority_ordering(self):
        """Test that rules are checked in priority order."""
        classifier = ActionSensitivityClassifier()
        classifier.clear_rules()

        # Add low priority rule
        classifier.add_rule(
            SensitivityRule(
                tool_pattern=r".*action.*",
                parameter_checks={},
                sensitivity=ActionSensitivity.SAFE,
                reason="Low priority",
                priority=10,
            )
        )

        # Add high priority rule
        classifier.add_rule(
            SensitivityRule(
                tool_pattern=r".*action.*",
                parameter_checks={},
                sensitivity=ActionSensitivity.DANGEROUS,
                reason="High priority",
                priority=100,
            )
        )

        tool = Tool(
            tool_id="test_action",
            name="Test Action",
            description="Test",
            sensitivity=ActionSensitivity.SAFE,
        )

        sensitivity, reason = classifier.classify(tool, {})

        # Should match high priority rule
        assert sensitivity == ActionSensitivity.DANGEROUS  # nosec B101
        assert reason == "High priority"  # nosec B101

    def test_classify_system_config_action(self):
        """Test classifying system configuration action."""
        classifier = ActionSensitivityClassifier()

        tool = Tool(
            tool_id="system_config_update",
            name="Update System Config",
            description="Update system configuration",
            sensitivity=ActionSensitivity.SAFE,
        )

        sensitivity, reason = classifier.classify(tool, {})

        assert sensitivity == ActionSensitivity.DANGEROUS  # nosec B101

    def test_classify_payment_action(self):
        """Test classifying payment action."""
        classifier = ActionSensitivityClassifier()

        tool = Tool(
            tool_id="make_payment",
            name="Make Payment",
            description="Process a payment",
            sensitivity=ActionSensitivity.SAFE,
        )

        sensitivity, reason = classifier.classify(tool, {"amount": 100})

        assert sensitivity == ActionSensitivity.SENSITIVE  # nosec B101

    def test_classify_smart_home_action(self):
        """Test classifying smart home action."""
        classifier = ActionSensitivityClassifier()

        tool = Tool(
            tool_id="smart_home_control",
            name="Smart Home Control",
            description="Control smart home devices",
            sensitivity=ActionSensitivity.SAFE,
        )

        sensitivity, reason = classifier.classify(tool, {})

        assert sensitivity == ActionSensitivity.SENSITIVE  # nosec B101

    def test_classify_data_export_action(self):
        """Test classifying data export action."""
        classifier = ActionSensitivityClassifier()

        tool = Tool(
            tool_id="export_user_data",
            name="Export User Data",
            description="Export user data",
            sensitivity=ActionSensitivity.SAFE,
        )

        sensitivity, reason = classifier.classify(tool, {})

        assert sensitivity == ActionSensitivity.SENSITIVE  # nosec B101

    def test_get_rules_returns_copy(self):
        """Test that get_rules returns a copy."""
        classifier = ActionSensitivityClassifier()

        rules1 = classifier.get_rules()
        rules2 = classifier.get_rules()

        assert rules1 is not rules2  # nosec B101
        assert len(rules1) == len(rules2)  # nosec B101
