import sys
sys.path.insert(0, 'src')

try:
    from tests import test_failure_orchestrator_properties
    print("Import successful")
    print(f"Functions: {[x for x in dir(test_failure_orchestrator_properties) if x.startswith('test_')]}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
