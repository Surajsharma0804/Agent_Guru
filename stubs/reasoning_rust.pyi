"""Type stubs for reasoning_rust Rust extension module."""

from typing import List, Tuple, Dict, Optional

def parse_command(text: str) -> Optional[Tuple[int, List[str]]]:
    """Parse command from text.
    
    Args:
        text: Input text to parse
        
    Returns:
        Tuple of (command_id, arguments) or None if no command found
    """
    ...

def extract_entities(text: str) -> str:
    """Extract entities from text.
    
    Args:
        text: Input text
        
    Returns:
        Extracted entities as string
    """
    ...

def tokenize_fast(text: str) -> Dict[str, List[str]]:
    """Fast tokenization using Rust.
    
    Args:
        text: Input text to tokenize
        
    Returns:
        Dictionary with tokenization results
    """
    ...

def compute_similarity(text1: str, text2: str) -> List[Tuple[int, float]]:
    """Compute similarity between two texts.
    
    Args:
        text1: First text
        text2: Second text
        
    Returns:
        List of (index, similarity_score) tuples
    """
    ...

def fast_pattern_match(text: str, patterns: List[str]) -> Optional[Tuple[int, List[str]]]:
    """Fast pattern matching using Rust.
    
    Args:
        text: Input text
        patterns: List of patterns to match
        
    Returns:
        Tuple of (match_position, captured_groups) or None
    """
    ...

def fast_normalize(text: str, remove_punctuation: bool = True) -> str:
    """Fast text normalization using Rust.
    
    Args:
        text: Input text to normalize
        remove_punctuation: Whether to remove punctuation
        
    Returns:
        Normalized text
    """
    ...

def fast_entity_extract(text: str, entity_types: List[str]) -> Dict[str, List[str]]:
    """Fast entity extraction using Rust.
    
    Args:
        text: Input text
        entity_types: List of entity types to extract
        
    Returns:
        Dictionary of entity types to entity values
    """
    ...

def fast_similarity_score(text: str, patterns: List[str]) -> List[Tuple[int, float]]:
    """Fast similarity scoring using Rust.
    
    Args:
        text: First text
        patterns: List of patterns to compare against
        
    Returns:
        List of (position, score) tuples
    """
    ...

def fast_json_parse(json_str: str) -> Dict[str, List[str]]:
    """Fast JSON parsing using Rust.
    
    Args:
        json_str: JSON string to parse
        
    Returns:
        Parsed JSON as dictionary
    """
    ...
