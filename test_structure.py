"""
Test script to verify Agent_Guru package structure
"""

def test_package_imports():
    """Test that all Agent_Guru submodules can be imported"""
    try:
        import Agent_Guru
        print(f"✓ Agent_Guru v{Agent_Guru.__version__}")
        
        # Test all submodules
        modules = [
            'speech', 'vision', 'llm', 'platform', 
            'agents', 'memory', 'deployment', 
            'policy', 'security', 'avatar'
        ]
        
        for module in modules:
            try:
                exec(f"from Agent_Guru import {module}")
                print(f"✓ Agent_Guru.{module}")
            except ImportError as e:
                print(f"✗ Agent_Guru.{module}: {e}")
                return False
        
        print("\n✅ All modules imported successfully!")
        print(f"\nAvailable modules: {', '.join(Agent_Guru.__all__)}")
        return True
        
    except Exception as e:
        print(f"✗ Failed to import Agent_Guru: {e}")
        return False

if __name__ == "__main__":
    success = test_package_imports()
    exit(0 if success else 1)
