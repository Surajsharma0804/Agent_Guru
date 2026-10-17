# Agent Guru Skill SDK

The Agent Guru Skill SDK enables developers to create third-party skills that extend the capabilities of the Agent Guru reasoning engine.

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Creating a Skill](#creating-a-skill)
- [Skill Capabilities](#skill-capabilities)
- [Manifest Generation](#manifest-generation)
- [Permissions](#permissions)
- [Testing Your Skill](#testing-your-skill)
- [Publishing Your Skill](#publishing-your-skill)
- [Examples](#examples)

## Installation

```bash
pip install agent-guru-sdk
```

Or install from source:

```bash
git clone https://github.com/agent-guru/sdk.git
cd sdk
pip install -e .
```

## Quick Start

Create a simple skill in 5 minutes:

```python
from agent_guru_sdk import Skill, skill_capability

class HelloSkill(Skill):
    @skill_capability("greet", "Greet a person by name")
    async def greet(self, name: str) -> dict:
        return {"message": f"Hello, {name}!"}

# Generate manifest
if __name__ == "__main__":
    from pathlib import Path
    from agent_guru_sdk import ManifestGenerator
    
    ManifestGenerator.generate_and_save(
        skill_class=HelloSkill,
        output_path=Path("hello_skill_manifest.json"),
        skill_id="com.example.hello",
        version="1.0.0",
        name="Hello Skill",
        description="A simple greeting skill",
        author="Your Name",
    )
```

## Creating a Skill

### Step 1: Define Your Skill Class

All skills must inherit from the `Skill` base class:

```python
from agent_guru_sdk import Skill

class MySkill(Skill):
    def __init__(self):
        super().__init__()
        # Initialize your skill here
```

### Step 2: Add Capabilities

Use the `@skill_capability` decorator to define what your skill can do:

```python
from agent_guru_sdk import skill_capability

class MySkill(Skill):
    @skill_capability("my_capability", "Description of what this does")
    async def my_method(self, param1: str, param2: int) -> dict:
        # Your implementation here
        return {"result": "success"}
```

### Step 3: Implement Your Logic

Implement the actual functionality in your capability methods:

```python
@skill_capability("calculate_tip", "Calculate tip amount")
async def calculate_tip(self, bill_amount: float, tip_percent: float = 15.0) -> dict:
    tip = bill_amount * (tip_percent / 100)
    total = bill_amount + tip
    
    return {
        "bill_amount": bill_amount,
        "tip_percent": tip_percent,
        "tip_amount": tip,
        "total_amount": total,
    }
```

## Skill Capabilities

### Defining Capabilities

Capabilities are the actions your skill can perform. Each capability:

- Must be an async method
- Must use the `@skill_capability` decorator
- Must return a dictionary
- Can have typed parameters

```python
@skill_capability("capability_name", "Human-readable description")
async def method_name(self, param1: str, param2: int = 10) -> dict:
    return {"key": "value"}
```

### Parameter Types

Supported parameter types:

- `str` - String values
- `int` - Integer values
- `float` - Floating point values
- `bool` - Boolean values
- `list` - Array values
- `dict` - Object values

### Return Values

All capabilities must return a dictionary. The structure is up to you, but should be consistent and well-documented.

## Manifest Generation

The manifest describes your skill to Agent Guru. Generate it automatically:

```python
from pathlib import Path
from agent_guru_sdk import ManifestGenerator

manifest = ManifestGenerator.generate_and_save(
    skill_class=MySkill,
    output_path=Path("my_skill_manifest.json"),
    skill_id="com.yourcompany.myskill",  # Unique identifier
    version="1.0.0",                      # Semantic version
    name="My Skill",                      # Display name
    description="What your skill does",   # Description
    author="Your Name",                   # Author name
    required_permissions=[                # Permissions needed
        "network_access",
        "file_read",
    ],
    max_latency=5000,                     # Max execution time (ms)
    dependencies=[                        # Python dependencies
        "requests>=2.28.0",
        "beautifulsoup4>=4.11.0",
    ],
    metadata={                            # Additional metadata
        "allowed_endpoints": [
            "api.example.com",
        ],
    },
)
```

### Manifest Fields

- **skill_id**: Unique identifier (reverse domain notation recommended)
- **version**: Semantic version (MAJOR.MINOR.PATCH)
- **name**: Human-readable name
- **description**: What your skill does
- **author**: Your name or organization
- **required_permissions**: List of permissions needed
- **max_latency**: Maximum execution time in milliseconds
- **dependencies**: Python packages required
- **metadata**: Additional configuration

## Permissions

Skills must request permissions for sensitive operations:

### Available Permissions

- `network_access` - Make HTTP requests
- `file_read` - Read files from disk
- `file_write` - Write files to disk
- `location_access` - Access user location
- `calendar_access` - Access calendar events
- `contacts_access` - Access contacts
- `system_control` - Control system settings

### Requesting Permissions

Specify permissions in your manifest:

```python
required_permissions=[
    "network_access",
    "file_read",
]
```

Users will be prompted to grant these permissions when your skill is first used.

### Permission Best Practices

1. **Request only what you need** - Don't ask for unnecessary permissions
2. **Explain why** - Document why each permission is needed
3. **Handle denials gracefully** - Your skill should work (with reduced functionality) if permissions are denied

## Testing Your Skill

### Unit Testing

Test your capabilities directly:

```python
import pytest
from my_skill import MySkill

@pytest.mark.asyncio
async def test_my_capability():
    skill = MySkill()
    result = await skill.execute_capability(
        "my_capability",
        param1="test",
        param2=42,
    )
    
    assert result["success"] == True
```

### Integration Testing

Test with the Agent Guru runtime:

```python
from agent_guru_sdk.testing import SkillTester

async def test_skill_integration():
    tester = SkillTester(MySkill)
    
    result = await tester.test_capability(
        "my_capability",
        parameters={"param1": "test", "param2": 42},
    )
    
    assert result.success
    assert result.execution_time_ms < 5000
```

## Publishing Your Skill

### Package Structure

```
my-skill/
├── my_skill/
│   ├── __init__.py
│   └── skill.py
├── tests/
│   └── test_skill.py
├── my_skill_manifest.json
├── README.md
├── LICENSE
└── setup.py
```

### Publishing Steps

1. **Test thoroughly** - Ensure all capabilities work correctly
2. **Generate manifest** - Create the manifest file
3. **Package your skill** - Create a Python package
4. **Submit to marketplace** - (Coming soon)

## Examples

### Weather Skill

```python
from agent_guru_sdk import Skill, skill_capability
import requests

class WeatherSkill(Skill):
    @skill_capability("get_weather", "Get current weather")
    async def get_weather(self, location: str) -> dict:
        # Call weather API
        response = requests.get(
            f"https://api.weather.com/v1/current",
            params={"location": location},
        )
        data = response.json()
        
        return {
            "location": location,
            "temperature": data["temp"],
            "condition": data["condition"],
        }
```

### Calculator Skill

```python
from agent_guru_sdk import Skill, skill_capability
import math

class CalculatorSkill(Skill):
    @skill_capability("calculate", "Evaluate math expression")
    async def calculate(self, expression: str) -> dict:
        try:
            result = eval(expression, {"__builtins__": {}}, {
                "sqrt": math.sqrt,
                "sin": math.sin,
                "cos": math.cos,
                "pi": math.pi,
            })
            return {"result": result, "success": True}
        except Exception as e:
            return {"error": str(e), "success": False}
```

### News Skill

```python
from agent_guru_sdk import Skill, skill_capability
import requests

class NewsSkill(Skill):
    @skill_capability("get_headlines", "Get top news headlines")
    async def get_headlines(self, category: str = "general") -> dict:
        response = requests.get(
            "https://newsapi.org/v2/top-headlines",
            params={"category": category},
        )
        data = response.json()
        
        return {
            "category": category,
            "headlines": data["articles"][:5],
        }
```

## Advanced Topics

### Error Handling

Always handle errors gracefully:

```python
@skill_capability("my_capability")
async def my_capability(self, param: str) -> dict:
    try:
        # Your logic here
        result = do_something(param)
        return {"result": result, "success": True}
    except ValueError as e:
        return {"error": str(e), "success": False}
    except Exception as e:
        return {"error": "Unexpected error", "success": False}
```

### Async Operations

Use async/await for I/O operations:

```python
import aiohttp

@skill_capability("fetch_data")
async def fetch_data(self, url: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            return {"data": data}
```

### Resource Management

Clean up resources properly:

```python
class MySkill(Skill):
    def __init__(self):
        super().__init__()
        self.connection = None
    
    async def __aenter__(self):
        self.connection = await create_connection()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            await self.connection.close()
```

## Support

- **Documentation**: https://docs.agent-guru.com/sdk
- **GitHub**: https://github.com/agent-guru/sdk
- **Discord**: https://discord.gg/agent-guru
- **Email**: sdk-support@agent-guru.com

## License

Apache License 2.0 - see the LICENSE and NOTICE files for details
