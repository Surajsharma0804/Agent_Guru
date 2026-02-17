"""Comprehensive unit tests for action models - 100% coverage."""

import pytest

from Agent_Guru.reasoning.models.action import (
    Action,
    ActionSensitivity,
    Tool,
    Parameter,
)


class TestParameter:
    """Test Parameter model."""
    
    def test_parameter_creation_valid(self):
        """Test creating a valid parameter."""
        param = Parameter(
            name="duration",
            param_type="int",
            required=True,
            description="Duration in seconds",
            validation_rules={"min": 1, "max": 86400},
        )
        
        assert param.name == "duration"
        assert param.param_type == "int"
        assert param.required
        assert param.description == "Duration in seconds"
        assert param.validation_rules == {"min": 1, "max": 86400}
    
    def test_parameter_param_type_validation_invalid(self):
        """Test parameter type validation fails for invalid type."""
        with pytest.raises(ValueError, match="Parameter type must be one of"):
            Parameter(
                name="test",
                param_type="invalid_type",
            )
    
    def test_parameter_equality(self):
        """Test parameter equality comparison."""
        param1 = Parameter(name="duration", param_type="int")
        param2 = Parameter(name="duration", param_type="int")
        param3 = Parameter(name="duration", param_type="str")
        
        assert param1 == param2
        assert param1 != param3
        assert param1 != "not a parameter"
    
    def test_parameter_hash(self):
        """Test parameter hashing."""
        param1 = Parameter(name="duration", param_type="int")
        param2 = Parameter(name="duration", param_type="int")
        
        assert hash(param1) == hash(param2)


class TestTool:
    """Test Tool model."""
    
    def test_tool_creation_valid(self):
        """Test creating a valid tool."""
        param = Parameter(name="duration", param_type="int", required=True)
        tool = Tool(
            tool_id="set_timer",
            name="Set Timer",
            description="Set a countdown timer",
            parameters=[param],
            sensitivity=ActionSensitivity.SAFE,
            estimated_latency=0.05,
            requires_permission=False,
            tags=["time", "scheduling"],
        )
        
        assert tool.tool_id == "set_timer"
        assert tool.name == "Set Timer"
        assert len(tool.parameters) == 1
        assert tool.sensitivity == ActionSensitivity.SAFE
        assert tool.estimated_latency == 0.05
        assert not tool.requires_permission
        assert "time" in tool.tags
    
    def test_tool_id_validation_invalid(self):
        """Test tool ID validation fails for invalid ID."""
        with pytest.raises(ValueError, match="Tool ID must be alphanumeric"):
            Tool(
                tool_id="",
                name="Test",
                description="Test",
            )
    
    def test_tool_latency_validation_invalid(self):
        """Test latency validation fails for negative value."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            Tool(
                tool_id="test",
                name="Test",
                description="Test",
                estimated_latency=-1.0,
            )
    
    def test_tool_get_required_parameters(self):
        """Test getting required parameters."""
        param1 = Parameter(name="duration", param_type="int", required=True)
        param2 = Parameter(name="label", param_type="str", required=False)
        tool = Tool(
            tool_id="set_timer",
            name="Set Timer",
            description="Test",
            parameters=[param1, param2],
        )
        
        required = tool.get_required_parameters()
        assert len(required) == 1
        assert required[0].name == "duration"
    
    def test_tool_get_optional_parameters(self):
        """Test getting optional parameters."""
        param1 = Parameter(name="duration", param_type="int", required=True)
        param2 = Parameter(name="label", param_type="str", required=False)
        tool = Tool(
            tool_id="set_timer",
            name="Set Timer",
            description="Test",
            parameters=[param1, param2],
        )
        
        optional = tool.get_optional_parameters()
        assert len(optional) == 1
        assert optional[0].name == "label"
    
    def test_tool_validate_parameters_valid(self):
        """Test parameter validation with valid parameters."""
        param = Parameter(name="duration", param_type="int", required=True)
        tool = Tool(
            tool_id="set_timer",
            name="Set Timer",
            description="Test",
            parameters=[param],
        )
        
        is_valid, errors = tool.validate_parameters({"duration": 300})
        assert is_valid
        assert len(errors) == 0
    
    def test_tool_validate_parameters_missing_required(self):
        """Test parameter validation fails for missing required parameter."""
        param = Parameter(name="duration", param_type="int", required=True)
        tool = Tool(
            tool_id="set_timer",
            name="Set Timer",
            description="Test",
            parameters=[param],
        )
        
        is_valid, errors = tool.validate_parameters({})
        assert not is_valid
        assert "Missing required parameter: duration" in errors
    
    def test_tool_validate_parameters_unknown(self):
        """Test parameter validation fails for unknown parameter."""
        tool = Tool(
            tool_id="set_timer",
            name="Set Timer",
            description="Test",
            parameters=[],
        )
        
        is_valid, errors = tool.validate_parameters({"unknown": 123})
        assert not is_valid
        assert "Unknown parameter: unknown" in errors
    
    def test_tool_validate_parameters_wrong_type(self):
        """Test parameter validation fails for wrong type."""
        param = Parameter(name="duration", param_type="int", required=True)
        tool = Tool(
            tool_id="set_timer",
            name="Set Timer",
            description="Test",
            parameters=[param],
        )
        
        is_valid, errors = tool.validate_parameters({"duration": "not an int"})
        assert not is_valid
        assert "must be int" in errors[0]
    
    def test_tool_validate_parameters_str_type(self):
        """Test parameter validation for str type."""
        param = Parameter(name="message", param_type="str", required=True)
        tool = Tool(
            tool_id="send_message",
            name="Send Message",
            description="Test",
            parameters=[param],
        )
        
        is_valid, errors = tool.validate_parameters({"message": 123})
        assert not is_valid
        assert "must be str" in errors[0]
    
    def test_tool_validate_parameters_bool_type(self):
        """Test parameter validation for bool type."""
        param = Parameter(name="enabled", param_type="bool", required=True)
        tool = Tool(
            tool_id="toggle",
            name="Toggle",
            description="Test",
            parameters=[param],
        )
        
        is_valid, errors = tool.validate_parameters({"enabled": "yes"})
        assert not is_valid
        assert "must be bool" in errors[0]
    
    def test_tool_equality(self):
        """Test tool equality comparison."""
        tool1 = Tool(tool_id="set_timer", name="Timer", description="Test")
        tool2 = Tool(tool_id="set_timer", name="Timer", description="Test")
        tool3 = Tool(tool_id="set_alarm", name="Alarm", description="Test")
        
        assert tool1 == tool2
        assert tool1 != tool3
        assert tool1 != "not a tool"
    
    def test_tool_hash(self):
        """Test tool hashing."""
        tool1 = Tool(tool_id="set_timer", name="Timer", description="Test")
        tool2 = Tool(tool_id="set_timer", name="Timer", description="Test")
        
        assert hash(tool1) == hash(tool2)


class TestAction:
    """Test Action model."""
    
    def test_action_creation_valid(self):
        """Test creating a valid action."""
        action = Action(
            action_id="action_123",
            tool_id="set_timer",
            parameters={"duration": 300},
            is_sensitive=False,
            estimated_duration=0.05,
            requires_confirmation=False,
        )
        
        assert action.action_id == "action_123"
        assert action.tool_id == "set_timer"
        assert action.parameters == {"duration": 300}
        assert not action.is_sensitive
        assert action.estimated_duration == 0.05
        assert not action.requires_confirmation
    
    def test_action_id_validation_invalid(self):
        """Test action ID validation fails for empty ID."""
        with pytest.raises(ValueError, match="Action ID cannot be empty"):
            Action(
                action_id="",
                tool_id="test",
            )
    
    def test_action_tool_id_validation_invalid(self):
        """Test tool ID validation fails for empty ID."""
        with pytest.raises(ValueError, match="Tool ID cannot be empty"):
            Action(
                action_id="action_123",
                tool_id="",
            )
    
    def test_action_duration_validation_invalid(self):
        """Test duration validation fails for negative value."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            Action(
                action_id="action_123",
                tool_id="test",
                estimated_duration=-1.0,
            )
    
    def test_action_equality(self):
        """Test action equality comparison."""
        action1 = Action(action_id="action_123", tool_id="test")
        action2 = Action(action_id="action_123", tool_id="test")
        action3 = Action(action_id="action_456", tool_id="test")
        
        assert action1 == action2
        assert action1 != action3
        assert action1 != "not an action"
    
    def test_action_hash(self):
        """Test action hashing."""
        action1 = Action(action_id="action_123", tool_id="test")
        action2 = Action(action_id="action_123", tool_id="test")
        
        assert hash(action1) == hash(action2)
    
    def test_action_sensitivity_enum(self):
        """Test action sensitivity enum values."""
        assert ActionSensitivity.SAFE == "safe"
        assert ActionSensitivity.SENSITIVE == "sensitive"
        assert ActionSensitivity.DANGEROUS == "dangerous"
