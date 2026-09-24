"""
Integration tests for Policy Engine Integration.

Tests the integration between self-improvement engine and policy engine.

**Validates: Requirements 18.1-18.3, Policy engine integration**

Author: Agent Guru Team
Date: 2026-02-28
"""

import pytest
import tempfile
import os
import time

from Agent_Guru.self_improvement.policy_integration import (
    PolicyIntegration,
    PolicyDecision,
    create_policy_integration
)
from Agent_Guru.self_improvement.self_improvement_engine import SelfImprovementEngine
import logging

logger = logging.getLogger(__name__)


class TestPolicyIntegration:
    """Integration tests for policy engine."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            try:
                os.unlink(path)
            except PermissionError:
                time.sleep(0.1)
                try:
                    os.unlink(path)
                except Exception as e:
                    logger.warning("Suppressed exception: %s", e)
    
    @pytest.fixture
    def engine(self, temp_db):
        """Create self-improvement engine for testing."""
        engine = SelfImprovementEngine(
            storage_path=temp_db,
            improvement_threshold=0.15,
            measurement_window=100,
            enable_git_commits=False
        )
        yield engine
        engine.close()
        time.sleep(0.1)
    
    @pytest.fixture
    def policy_integration(self, engine):
        """Create policy integration."""
        return PolicyIntegration(
            self_improvement_engine=engine,
            policy_engine=None,  # No policy engine for now
            enforce_policies=True
        )
    
    def test_policy_integration_initialization(self, policy_integration, engine):
        """Test that policy integration initializes correctly."""
        assert policy_integration.engine is engine  # nosec B101
        assert policy_integration.policy_engine is None  # nosec B101
        assert policy_integration.enforce_policies is True  # nosec B101
        assert "allow_strategy_changes" in policy_integration.default_policies  # nosec B101
    
    def test_check_strategy_policy_without_policy_engine(self, policy_integration):
        """Test checking strategy policy without policy engine."""
        decision = policy_integration.check_strategy_policy(
            strategy_id="test_strategy",
            task_type="test_task"
        )
        
        # Should allow by default
        assert decision == PolicyDecision.ALLOW  # nosec B101
    
    def test_check_strategy_policy_with_enforcement_disabled(self, engine):
        """Test strategy policy check with enforcement disabled."""
        integration = PolicyIntegration(
            self_improvement_engine=engine,
            policy_engine=None,
            enforce_policies=False
        )
        
        decision = integration.check_strategy_policy(
            strategy_id="test_strategy",
            task_type="test_task"
        )
        
        # Should always allow when enforcement disabled
        assert decision == PolicyDecision.ALLOW  # nosec B101
    
    def test_check_prompt_evolution_policy_without_policy_engine(self, policy_integration):
        """Test checking prompt evolution policy without policy engine."""
        decision = policy_integration.check_prompt_evolution_policy(
            prompt_type="test_prompt",
            current_content="Old prompt",
            proposed_content="New prompt"
        )
        
        # Should allow by default
        assert decision == PolicyDecision.ALLOW  # nosec B101
    
    def test_check_prompt_evolution_policy_with_enforcement_disabled(self, engine):
        """Test prompt evolution policy check with enforcement disabled."""
        integration = PolicyIntegration(
            self_improvement_engine=engine,
            policy_engine=None,
            enforce_policies=False
        )
        
        decision = integration.check_prompt_evolution_policy(
            prompt_type="test_prompt",
            current_content="Old prompt",
            proposed_content="New prompt"
        )
        
        # Should always allow when enforcement disabled
        assert decision == PolicyDecision.ALLOW  # nosec B101
    
    def test_get_allowed_strategies_without_policy_engine(self, policy_integration, engine):
        """Test getting allowed strategies without policy engine."""
        # Register some strategies
        engine.strategy_optimizer.register_strategy(
            strategy_id="strategy_1",
            name="Strategy 1",
            description="Test strategy 1",
            task_types=["test_task"],
            parameters={}
        )
        
        engine.strategy_optimizer.register_strategy(
            strategy_id="strategy_2",
            name="Strategy 2",
            description="Test strategy 2",
            task_types=["test_task"],
            parameters={}
        )
        
        # Get allowed strategies
        allowed = policy_integration.get_allowed_strategies(task_type="test_task")
        
        # Should return all strategies
        assert isinstance(allowed, list)  # nosec B101
        assert len(allowed) == 2  # nosec B101
        assert "strategy_1" in allowed  # nosec B101
        assert "strategy_2" in allowed  # nosec B101
    
    def test_set_policy(self, policy_integration):
        """Test setting default policy values."""
        # Set policy
        policy_integration.set_policy("allow_strategy_changes", False)
        
        # Verify policy changed
        assert policy_integration.default_policies["allow_strategy_changes"] is False  # nosec B101
        
        # Check strategy policy now denies
        decision = policy_integration.check_strategy_policy(
            strategy_id="test_strategy",
            task_type="test_task"
        )
        
        assert decision == PolicyDecision.DENY  # nosec B101
    
    def test_get_policy_status(self, policy_integration):
        """Test getting policy status."""
        status = policy_integration.get_policy_status()
        
        assert "policy_engine_connected" in status  # nosec B101
        assert status["policy_engine_connected"] is False  # nosec B101
        assert "enforce_policies" in status  # nosec B101
        assert status["enforce_policies"] is True  # nosec B101
        assert "default_policies" in status  # nosec B101
        assert isinstance(status["default_policies"], dict)  # nosec B101
    
    def test_create_policy_integration(self, engine):
        """Test convenience function for creating integration."""
        integration = create_policy_integration(engine)
        
        assert integration is not None  # nosec B101
        assert integration.engine is engine  # nosec B101
        assert integration.policy_engine is None  # nosec B101
        assert integration.enforce_policies is True  # nosec B101
        
        # Test it works
        decision = integration.check_strategy_policy(
            strategy_id="test_strategy",
            task_type="test_task"
        )
        assert decision == PolicyDecision.ALLOW  # nosec B101


@pytest.mark.integration
class TestPolicyIntegrationWithMockEngine:
    """Tests with mock policy engine."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            try:
                os.unlink(path)
            except Exception as e:
                logger.warning("Suppressed exception: %s", e)
    
    @pytest.fixture
    def engine(self, temp_db):
        """Create self-improvement engine."""
        engine = SelfImprovementEngine(
            storage_path=temp_db,
            improvement_threshold=0.15,
            measurement_window=100,
            enable_git_commits=False
        )
        yield engine
        engine.close()
        time.sleep(0.1)
    
    @pytest.fixture
    def mock_policy_engine(self):
        """Create mock policy engine."""
        class MockPolicyEngine:
            def __init__(self):
                self.policies = {}
            
            def evaluate(self, policy_name, context):
                return self.policies.get(policy_name, True)
            
            def set_policy(self, policy_name, value):
                self.policies[policy_name] = value
        
        return MockPolicyEngine()
    
    @pytest.fixture
    def policy_integration(self, engine, mock_policy_engine):
        """Create policy integration with mock engine."""
        return PolicyIntegration(
            self_improvement_engine=engine,
            policy_engine=mock_policy_engine,
            enforce_policies=True
        )
    
    def test_policy_integration_with_mock_engine(self, policy_integration):
        """Test policy integration with mock policy engine."""
        # Check strategy policy
        decision = policy_integration.check_strategy_policy(
            strategy_id="test_strategy",
            task_type="test_task"
        )
        
        # Should allow (mock engine allows by default)
        assert decision == PolicyDecision.ALLOW  # nosec B101
    
    def test_prompt_evolution_with_mock_engine(self, policy_integration):
        """Test prompt evolution policy with mock engine."""
        # Check prompt evolution policy
        decision = policy_integration.check_prompt_evolution_policy(
            prompt_type="test_prompt",
            current_content="Old",
            proposed_content="New"
        )
        
        # Should allow (mock engine allows by default)
        assert decision == PolicyDecision.ALLOW  # nosec B101
