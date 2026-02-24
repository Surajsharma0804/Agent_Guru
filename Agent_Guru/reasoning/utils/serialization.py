"""
Optimized JSON serialization using orjson for 5-10x performance improvement.

This module provides a drop-in replacement for the standard json module
with significantly better performance for serialization/deserialization.

Performance Comparison:
    Standard json.dumps: ~100ms for 1MB data
    orjson.dumps: ~10-20ms for 1MB data (5-10x faster)

Usage:
    # Instead of:
    import json
    data = json.dumps(obj)
    obj = json.loads(data)
    
    # Use:
    from Agent_Guru.reasoning.utils.serialization import dumps, loads
    data = dumps(obj)
    obj = loads(data)
"""

from typing import Any, Optional, Callable
import datetime
import uuid

try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    import json
    HAS_ORJSON = False


def _default_serializer(obj: Any) -> Any:
    """
    Default serializer for types not natively supported by orjson.
    
    Handles:
    - datetime objects -> ISO format strings
    - UUID objects -> string representation
    - Custom objects with __dict__ -> dictionary
    
    Args:
        obj: Object to serialize
        
    Returns:
        Serializable representation
        
    Raises:
        TypeError: If object cannot be serialized
    """
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    elif isinstance(obj, datetime.date):
        return obj.isoformat()
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    elif hasattr(obj, '__dict__'):
        return obj.__dict__
    else:
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def dumps(
    obj: Any,
    *,
    default: Optional[Callable[[Any], Any]] = None,
    option: int = 0
) -> bytes:
    """
    Serialize object to JSON bytes using orjson (5-10x faster than json.dumps).
    
    Args:
        obj: Object to serialize
        default: Custom serializer function for unsupported types
        option: orjson options (e.g., orjson.OPT_INDENT_2 for pretty printing)
        
    Returns:
        JSON bytes
        
    Example:
        >>> data = {"name": "test", "value": 123}
        >>> json_bytes = dumps(data)
        >>> json_bytes
        b'{"name":"test","value":123}'
    """
    if HAS_ORJSON:
        serializer = default or _default_serializer
        return orjson.dumps(obj, default=serializer, option=option)
    else:
        # Fallback to standard json
        serializer = default or _default_serializer
        return json.dumps(obj, default=serializer).encode('utf-8')


def dumps_str(
    obj: Any,
    *,
    default: Optional[Callable[[Any], Any]] = None,
    option: int = 0
) -> str:
    """
    Serialize object to JSON string using orjson.
    
    Args:
        obj: Object to serialize
        default: Custom serializer function for unsupported types
        option: orjson options
        
    Returns:
        JSON string
        
    Example:
        >>> data = {"name": "test", "value": 123}
        >>> json_str = dumps_str(data)
        >>> json_str
        '{"name":"test","value":123}'
    """
    return dumps(obj, default=default, option=option).decode('utf-8')


def loads(data: bytes | str) -> Any:
    """
    Deserialize JSON bytes/string to Python object using orjson (2-3x faster than json.loads).
    
    Args:
        data: JSON bytes or string
        
    Returns:
        Deserialized Python object
        
    Example:
        >>> json_bytes = b'{"name":"test","value":123}'
        >>> obj = loads(json_bytes)
        >>> obj
        {'name': 'test', 'value': 123}
    """
    if HAS_ORJSON:
        if isinstance(data, str):
            data = data.encode('utf-8')
        return orjson.loads(data)
    else:
        # Fallback to standard json
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        return json.loads(data)


def pretty_dumps(obj: Any, *, default: Optional[Callable[[Any], Any]] = None) -> str:
    """
    Serialize object to pretty-printed JSON string.
    
    Args:
        obj: Object to serialize
        default: Custom serializer function
        
    Returns:
        Pretty-printed JSON string
        
    Example:
        >>> data = {"name": "test", "nested": {"value": 123}}
        >>> print(pretty_dumps(data))
        {
          "name": "test",
          "nested": {
            "value": 123
          }
        }
    """
    if HAS_ORJSON:
        return dumps(obj, default=default, option=orjson.OPT_INDENT_2).decode('utf-8')
    else:
        serializer = default or _default_serializer
        return json.dumps(obj, default=serializer, indent=2)


# Compatibility aliases for drop-in replacement
dump = dumps  # Note: orjson doesn't support file objects, so this writes bytes
load = loads


# Performance benchmarking function
def benchmark_serialization(obj: Any, iterations: int = 1000) -> dict:
    """
    Benchmark serialization performance.
    
    Args:
        obj: Object to serialize
        iterations: Number of iterations
        
    Returns:
        Dictionary with timing results
    """
    import time
    
    # Benchmark orjson
    if HAS_ORJSON:
        start = time.perf_counter()
        for _ in range(iterations):
            dumps(obj)
        orjson_time = time.perf_counter() - start
    else:
        orjson_time = None
    
    # Benchmark standard json
    import json as std_json
    start = time.perf_counter()
    for _ in range(iterations):
        std_json.dumps(obj, default=_default_serializer).encode('utf-8')
    json_time = time.perf_counter() - start
    
    result = {
        'iterations': iterations,
        'json_time': json_time,
        'json_avg': json_time / iterations * 1000,  # ms
    }
    
    if orjson_time is not None:
        result['orjson_time'] = orjson_time
        result['orjson_avg'] = orjson_time / iterations * 1000  # ms
        result['speedup'] = json_time / orjson_time
    
    return result


if __name__ == "__main__":
    # Example usage and benchmarking
    print("Optimized Serialization Module")
    print("=" * 80)
    print(f"Using: {'orjson' if HAS_ORJSON else 'standard json (fallback)'}")
    print()
    
    # Example data
    data = {
        "name": "Agent Guru",
        "version": "1.0.0",
        "timestamp": datetime.datetime.now(),
        "uuid": uuid.uuid4(),
        "nested": {
            "values": list(range(100)),
            "metadata": {"key": "value"}
        }
    }
    
    # Serialize
    json_bytes = dumps(data)
    print(f"Serialized size: {len(json_bytes)} bytes")
    
    # Deserialize
    restored = loads(json_bytes)
    print(f"Deserialized keys: {list(restored.keys())}")
    
    # Benchmark
    print("\nBenchmarking (1000 iterations):")
    results = benchmark_serialization(data, iterations=1000)
    print(f"  Standard json: {results['json_avg']:.3f}ms avg")
    if 'orjson_avg' in results:
        print(f"  orjson: {results['orjson_avg']:.3f}ms avg")
        print(f"  Speedup: {results['speedup']:.1f}x faster")
