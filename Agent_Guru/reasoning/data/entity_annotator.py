"""Entity annotation pipeline for training data."""

import re
from pathlib import Path
from typing import Dict, List, Tuple

import yaml


class EntityAnnotator:
    """Annotate training data with entity spans and types."""
    
    def __init__(self, intents_file: str = "Agent_Guru/reasoning/data/intents.yaml"):
        """Initialize entity annotator.
        
        Args:
            intents_file: Path to intents YAML file
        """
        self.intents_file = Path(intents_file)
        self.intents_data = self._load_intents()
        self.entity_patterns = self._build_entity_patterns()
    
    def _load_intents(self) -> Dict:
        """Load intents from YAML file."""
        with open(self.intents_file, 'r') as f:
            return yaml.safe_load(f)
    
    def _build_entity_patterns(self) -> Dict[str, List[str]]:
        """Build regex patterns for entity extraction.
        
        Returns:
            Dictionary mapping entity type to regex patterns
        """
        patterns = {
            'duration': [
                r'\d+\s*(?:second|sec|minute|min|hour|hr)s?',
                r'\d+\s*(?:second|sec|minute|min|hour|hr)s?\s*(?:and|&)?\s*\d+\s*(?:second|sec|minute|min|hour|hr)s?',
            ],
            'time': [
                r'\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)?',
                r'\d{1,2}\s*(?:am|pm|AM|PM|o\'clock)',
                r'(?:noon|midnight|morning|evening|night)',
            ],
            'date': [
                r'(?:today|tomorrow|yesterday)',
                r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)',
                r'(?:next|last)\s+(?:week|month|year|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)',
                r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}',
            ],
            'temperature': [
                r'\d+\s*(?:degrees?|°)?(?:\s*(?:fahrenheit|celsius|F|C))?',
            ],
            'phone_number': [
                r'\d{3}-\d{3}-\d{4}',
                r'\d{3}-\d{4}',
            ],
            'percentage': [
                r'\d+\s*%',
            ],
        }
        return patterns
    
    def extract_entities(
        self, 
        utterance: str, 
        intent: str
    ) -> List[Tuple[str, int, int, str]]:
        """Extract entities from utterance.
        
        Args:
            utterance: Input utterance
            intent: Intent type
            
        Returns:
            List of (entity_text, start_pos, end_pos, entity_type)
        """
        entities = []
        
        # Get expected entity types for this intent
        intent_data = self.intents_data['intents'].get(intent, {})
        expected_entities = intent_data.get('entities', [])
        
        # Extract entities using patterns
        for entity_type, patterns in self.entity_patterns.items():
            if entity_type in expected_entities or not expected_entities:
                for pattern in patterns:
                    for match in re.finditer(pattern, utterance, re.IGNORECASE):
                        entities.append((
                            match.group(),
                            match.start(),
                            match.end(),
                            entity_type
                        ))
        
        # Extract named entities (simple heuristics)
        if 'recipient' in expected_entities:
            # Look for names after "to", "call", "message", "text"
            name_patterns = [
                r'(?:to|call|message|text)\s+([A-Z][a-z]+)',
                r'(?:to|call|message|text)\s+(mom|dad|boss|wife|husband)',
            ]
            for pattern in name_patterns:
                for match in re.finditer(pattern, utterance):
                    entities.append((
                        match.group(1),
                        match.start(1),
                        match.end(1),
                        'recipient'
                    ))
        
        if 'location' in expected_entities:
            # Look for location names (capitalized words)
            location_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b'
            for match in re.finditer(location_pattern, utterance):
                # Skip common words
                if match.group(1).lower() not in ['i', 'a', 'the']:
                    entities.append((
                        match.group(1),
                        match.start(1),
                        match.end(1),
                        'location'
                    ))
        
        if 'app_name' in expected_entities:
            # Look for app names (capitalized words)
            app_pattern = r'\b([A-Z][a-z]+)\b'
            for match in re.finditer(app_pattern, utterance):
                entities.append((
                    match.group(1),
                    match.start(1),
                    match.end(1),
                    'app_name'
                ))
        
        # Remove overlapping entities (keep longest)
        entities = self._remove_overlaps(entities)
        
        return entities
    
    def _remove_overlaps(
        self, 
        entities: List[Tuple[str, int, int, str]]
    ) -> List[Tuple[str, int, int, str]]:
        """Remove overlapping entities, keeping the longest.
        
        Args:
            entities: List of entities
            
        Returns:
            List of non-overlapping entities
        """
        if not entities:
            return []
        
        # Sort by start position, then by length (descending)
        sorted_entities = sorted(
            entities, 
            key=lambda x: (x[1], -(x[2] - x[1]))
        )
        
        non_overlapping = []
        last_end = -1
        
        for entity in sorted_entities:
            start = entity[1]
            if start >= last_end:
                non_overlapping.append(entity)
                last_end = entity[2]
        
        return non_overlapping
    
    def annotate_dataset(
        self, 
        input_file: str,
        output_file: str
    ):
        """Annotate dataset with entities.
        
        Args:
            input_file: Input dataset file (intent\tutterance format)
            output_file: Output annotated file
        """
        annotated_data = []
        
        with open(input_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                parts = line.split('\t')
                if len(parts) != 2:
                    continue
                
                intent, utterance = parts
                entities = self.extract_entities(utterance, intent)
                
                annotated_data.append({
                    'utterance': utterance,
                    'intent': intent,
                    'entities': [
                        {
                            'text': text,
                            'start': start,
                            'end': end,
                            'type': entity_type
                        }
                        for text, start, end, entity_type in entities
                    ]
                })
        
        # Save annotated data
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(annotated_data, f, default_flow_style=False, allow_unicode=True)
        
        print(f"Annotated {len(annotated_data)} examples")
        print(f"Saved to {output_file}")
    
    def validate_annotations(
        self, 
        annotated_file: str
    ) -> Dict[str, float]:
        """Validate annotation quality.
        
        Args:
            annotated_file: Annotated dataset file
            
        Returns:
            Dictionary with validation metrics
        """
        with open(annotated_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        total_examples = len(data)
        examples_with_entities = sum(1 for item in data if item['entities'])
        total_entities = sum(len(item['entities']) for item in data)
        
        # Count entity types
        entity_type_counts = {}
        for item in data:
            for entity in item['entities']:
                entity_type = entity['type']
                entity_type_counts[entity_type] = entity_type_counts.get(entity_type, 0) + 1
        
        metrics = {
            'total_examples': total_examples,
            'examples_with_entities': examples_with_entities,
            'coverage': examples_with_entities / total_examples if total_examples > 0 else 0,
            'total_entities': total_entities,
            'avg_entities_per_example': total_entities / total_examples if total_examples > 0 else 0,
            'entity_type_distribution': entity_type_counts,
        }
        
        return metrics


def main():
    """Annotate datasets with entities."""
    annotator = EntityAnnotator()
    
    # Annotate train, val, and test sets
    for split in ['train', 'val', 'test']:
        input_file = f"Agent_Guru/reasoning/data/{split}.txt"
        output_file = f"Agent_Guru/reasoning/data/{split}_annotated.yaml"
        
        print(f"\nAnnotating {split} set...")
        annotator.annotate_dataset(input_file, output_file)
        
        # Validate annotations
        metrics = annotator.validate_annotations(output_file)
        print(f"Coverage: {metrics['coverage']:.2%}")
        print(f"Avg entities per example: {metrics['avg_entities_per_example']:.2f}")
        print(f"Entity type distribution:")
        for entity_type, count in sorted(
            metrics['entity_type_distribution'].items(), 
            key=lambda x: x[1], 
            reverse=True
        ):
            print(f"  {entity_type}: {count}")


if __name__ == "__main__":
    main()
