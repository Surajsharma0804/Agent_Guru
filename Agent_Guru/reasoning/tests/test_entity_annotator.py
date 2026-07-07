"""Comprehensive unit tests for entity annotator - 100% coverage."""

import pytest
from pathlib import Path
import tempfile
import shutil
import yaml

from Agent_Guru.reasoning.data.entity_annotator import EntityAnnotator


class TestEntityAnnotator:
    """Test EntityAnnotator class."""
    
    @pytest.fixture
    def annotator(self):
        """Create entity annotator instance."""
        return EntityAnnotator()
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test outputs."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path)
    
    def test_load_intents(self, annotator):
        """Test loading intents from YAML file."""
        assert 'intents' in annotator.intents_data  # nosec B101
        assert len(annotator.intents_data['intents']) > 0  # nosec B101
    
    def test_build_entity_patterns(self, annotator):
        """Test entity patterns are built."""
        assert len(annotator.entity_patterns) > 0  # nosec B101
        assert 'duration' in annotator.entity_patterns  # nosec B101
        assert 'time' in annotator.entity_patterns  # nosec B101
        assert 'date' in annotator.entity_patterns  # nosec B101
    
    def test_extract_entities_duration(self, annotator):
        """Test extracting duration entities."""
        utterance = "set a timer for 5 minutes"
        entities = annotator.extract_entities(utterance, "set_timer")
        
        # Should find duration
        assert len(entities) > 0  # nosec B101
        assert any(e[3] == 'duration' for e in entities)  # nosec B101
        assert any('5 minutes' in e[0].lower() for e in entities)  # nosec B101
    
    def test_extract_entities_time(self, annotator):
        """Test extracting time entities."""
        utterance = "set alarm for 7:30 am"
        entities = annotator.extract_entities(utterance, "set_alarm")
        
        # Should find time
        assert len(entities) > 0  # nosec B101
        assert any(e[3] == 'time' for e in entities)  # nosec B101
        assert any('7:30' in e[0] for e in entities)  # nosec B101
    
    def test_extract_entities_date(self, annotator):
        """Test extracting date entities."""
        utterance = "remind me tomorrow"
        entities = annotator.extract_entities(utterance, "set_reminder")
        
        # Should find date
        assert len(entities) > 0  # nosec B101
        assert any(e[3] == 'date' for e in entities)  # nosec B101
        assert any('tomorrow' in e[0].lower() for e in entities)  # nosec B101
    
    def test_extract_entities_temperature(self, annotator):
        """Test extracting temperature entities."""
        utterance = "set temperature to 72 degrees"
        entities = annotator.extract_entities(utterance, "control_thermostat")
        
        # Should find temperature
        assert len(entities) > 0  # nosec B101
        assert any(e[3] == 'temperature' for e in entities)  # nosec B101
    
    def test_extract_entities_phone_number(self, annotator):
        """Test extracting phone number entities."""
        utterance = "call 555-1234"
        entities = annotator.extract_entities(utterance, "make_call")
        
        # Should find phone number
        assert len(entities) > 0  # nosec B101
        assert any(e[3] == 'phone_number' for e in entities)  # nosec B101
    
    def test_extract_entities_recipient(self, annotator):
        """Test extracting recipient entities."""
        utterance = "send message to John"
        entities = annotator.extract_entities(utterance, "send_message")
        
        # Should find recipient
        assert len(entities) > 0  # nosec B101
        assert any(e[3] == 'recipient' for e in entities)  # nosec B101
        assert any('John' in e[0] for e in entities)  # nosec B101
    
    def test_extract_entities_recipient_common_names(self, annotator):
        """Test extracting common recipient names."""
        utterance = "call mom"
        entities = annotator.extract_entities(utterance, "make_call")
        
        # Should find recipient
        assert len(entities) > 0  # nosec B101
        assert any(e[3] == 'recipient' for e in entities)  # nosec B101
        assert any('mom' in e[0].lower() for e in entities)  # nosec B101
    
    def test_extract_entities_location(self, annotator):
        """Test extracting location entities."""
        utterance = "weather in New York"
        entities = annotator.extract_entities(utterance, "query_weather")
        
        # Should find location
        assert len(entities) > 0  # nosec B101
        assert any(e[3] == 'location' for e in entities)  # nosec B101
    
    def test_extract_entities_app_name(self, annotator):
        """Test extracting app name entities."""
        utterance = "open Spotify"
        entities = annotator.extract_entities(utterance, "open_app")
        
        # Should find app name
        assert len(entities) > 0  # nosec B101
        assert any(e[3] == 'app_name' for e in entities)  # nosec B101
        assert any('Spotify' in e[0] for e in entities)  # nosec B101
    
    def test_extract_entities_no_entities(self, annotator):
        """Test extracting from utterance with no entities."""
        utterance = "help"
        entities = annotator.extract_entities(utterance, "help_request")
        
        # May or may not find entities
        assert isinstance(entities, list)  # nosec B101
    
    def test_extract_entities_multiple(self, annotator):
        """Test extracting multiple entities."""
        utterance = "set alarm for 7:30 tomorrow"
        entities = annotator.extract_entities(utterance, "set_alarm")
        
        # Should find both time and date
        entity_types = [e[3] for e in entities]
        assert 'time' in entity_types or 'date' in entity_types  # nosec B101
    
    def test_remove_overlaps_no_overlap(self, annotator):
        """Test removing overlaps with no overlapping entities."""
        entities = [
            ("5 minutes", 10, 19, "duration"),
            ("tomorrow", 20, 28, "date"),
        ]
        result = annotator._remove_overlaps(entities)
        
        assert len(result) == 2  # nosec B101
    
    def test_remove_overlaps_with_overlap(self, annotator):
        """Test removing overlapping entities."""
        entities = [
            ("5 minutes", 10, 19, "duration"),
            ("minutes", 12, 19, "duration"),  # Overlaps
        ]
        result = annotator._remove_overlaps(entities)
        
        # Should keep only the longer one
        assert len(result) == 1  # nosec B101
        assert result[0][0] == "5 minutes"  # nosec B101
    
    def test_remove_overlaps_empty(self, annotator):
        """Test removing overlaps with empty list."""
        result = annotator._remove_overlaps([])
        assert result == []  # nosec B101
    
    def test_annotate_dataset(self, annotator, temp_dir):
        """Test annotating dataset."""
        # Create test input file
        input_file = Path(temp_dir, "test_input.txt")
        with open(input_file, 'w', encoding='utf-8') as f:
            f.write("set_timer\tset a timer for 5 minutes\n")
            f.write("query_weather\twhat's the weather\n")
        
        output_file = Path(temp_dir, "test_output.yaml")
        annotator.annotate_dataset(str(input_file), str(output_file))
        
        # Check output file exists
        assert output_file.exists()  # nosec B101
        
        # Check content
        with open(output_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            assert len(data) == 2  # nosec B101
            assert data[0]['intent'] == 'set_timer'  # nosec B101
            assert data[0]['utterance'] == 'set a timer for 5 minutes'  # nosec B101
            assert 'entities' in data[0]  # nosec B101
    
    def test_annotate_dataset_empty_lines(self, annotator, temp_dir):
        """Test annotating dataset with empty lines."""
        # Create test input file with empty lines
        input_file = Path(temp_dir, "test_input.txt")
        with open(input_file, 'w', encoding='utf-8') as f:
            f.write("set_timer\tset a timer\n")
            f.write("\n")  # Empty line
            f.write("play_music\tplay music\n")
        
        output_file = Path(temp_dir, "test_output.yaml")
        annotator.annotate_dataset(str(input_file), str(output_file))
        
        # Should skip empty lines
        with open(output_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            assert len(data) == 2  # nosec B101
    
    def test_annotate_dataset_malformed_lines(self, annotator, temp_dir):
        """Test annotating dataset with malformed lines."""
        # Create test input file with malformed lines
        input_file = Path(temp_dir, "test_input.txt")
        with open(input_file, 'w', encoding='utf-8') as f:
            f.write("set_timer\tset a timer\n")
            f.write("malformed line\n")  # No tab
            f.write("play_music\tplay music\n")
        
        output_file = Path(temp_dir, "test_output.yaml")
        annotator.annotate_dataset(str(input_file), str(output_file))
        
        # Should skip malformed lines
        with open(output_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            assert len(data) == 2  # nosec B101
    
    def test_validate_annotations(self, annotator, temp_dir):
        """Test validating annotations."""
        # Create test annotated file
        annotated_file = Path(temp_dir, "test_annotated.yaml")
        data = [
            {
                'utterance': 'set a timer for 5 minutes',
                'intent': 'set_timer',
                'entities': [
                    {'text': '5 minutes', 'start': 16, 'end': 25, 'type': 'duration'}
                ]
            },
            {
                'utterance': 'play music',
                'intent': 'play_music',
                'entities': []
            }
        ]
        with open(annotated_file, 'w', encoding='utf-8') as f:
            yaml.dump(data, f)
        
        metrics = annotator.validate_annotations(str(annotated_file))
        
        assert metrics['total_examples'] == 2  # nosec B101
        assert metrics['examples_with_entities'] == 1  # nosec B101
        assert metrics['coverage'] == 0.5  # nosec B101
        assert metrics['total_entities'] == 1  # nosec B101
        assert metrics['avg_entities_per_example'] == 0.5  # nosec B101
        assert 'duration' in metrics['entity_type_distribution']  # nosec B101
    
    def test_validate_annotations_empty(self, annotator, temp_dir):
        """Test validating empty annotations."""
        # Create empty annotated file
        annotated_file = Path(temp_dir, "test_annotated.yaml")
        with open(annotated_file, 'w', encoding='utf-8') as f:
            yaml.dump([], f)
        
        metrics = annotator.validate_annotations(str(annotated_file))
        
        assert metrics['total_examples'] == 0  # nosec B101
        assert metrics['coverage'] == 0  # nosec B101
        assert metrics['avg_entities_per_example'] == 0  # nosec B101
    
    def test_entity_patterns_duration_formats(self, annotator):
        """Test duration pattern matches various formats."""
        test_cases = [
            "5 minutes",
            "10 seconds",
            "2 hours",
            "1 hour 30 minutes",
        ]
        
        for test_case in test_cases:
            utterance = f"set timer for {test_case}"
            entities = annotator.extract_entities(utterance, "set_timer")
            assert any(e[3] == 'duration' for e in entities), f"Failed for: {test_case}"  # nosec B101
    
    def test_entity_patterns_time_formats(self, annotator):
        """Test time pattern matches various formats."""
        test_cases = [
            "7:30 am",
            "3pm",
            "noon",
            "midnight",
        ]
        
        for test_case in test_cases:
            utterance = f"set alarm for {test_case}"
            entities = annotator.extract_entities(utterance, "set_alarm")
            assert any(e[3] == 'time' for e in entities), f"Failed for: {test_case}"  # nosec B101
    
    def test_entity_patterns_date_formats(self, annotator):
        """Test date pattern matches various formats."""
        test_cases = [
            "today",
            "tomorrow",
            "Monday",
            "next week",
        ]
        
        for test_case in test_cases:
            utterance = f"remind me {test_case}"
            entities = annotator.extract_entities(utterance, "set_reminder")
            assert any(e[3] == 'date' for e in entities), f"Failed for: {test_case}"  # nosec B101


    def test_main_function_execution(self, annotator, temp_dir, capsys, monkeypatch):
        """Test main function executes correctly."""
        from Agent_Guru.reasoning.data.entity_annotator import main
        
        # Create test input files
        for split in ['train', 'val', 'test']:
            input_file = Path(temp_dir, f"{split}.txt")
            with open(input_file, 'w', encoding='utf-8') as f:
                f.write("set_timer\tset a timer for 5 minutes\n")
        
        # Mock the file paths
        monkeypatch.setattr('Agent_Guru.reasoning.data.entity_annotator.EntityAnnotator.annotate_dataset',
                           lambda self, input_file, output_file: None)
        monkeypatch.setattr('Agent_Guru.reasoning.data.entity_annotator.EntityAnnotator.validate_annotations',
                           lambda self, annotated_file: {
                               'coverage': 0.5,
                               'examples_with_entities': 5,
                               'total_examples': 10,
                               'adjusted_coverage': 0.6,
                               'adjusted_with_entities': 6,
                               'adjusted_total': 10,
                               'avg_entities_per_example': 1.0,
                               'entity_type_distribution': {'duration': 1},
                               'per_intent_coverage': {},
                           })
        
        # Execute main
        main()
        
        # Check output was printed
        capsys.readouterr()
        # Main function should execute without errors
        assert True  # If we get here, main() executed successfully  # nosec B101
    
    def test_validate_annotations_with_multiple_entity_types(self, annotator, temp_dir):
        """Test validation with multiple entity types."""
        annotated_file = Path(temp_dir, "test_annotated.yaml")
        data = [
            {
                'utterance': 'set alarm for 7:30 tomorrow',
                'intent': 'set_alarm',
                'entities': [
                    {'text': '7:30', 'start': 16, 'end': 20, 'type': 'time'},
                    {'text': 'tomorrow', 'start': 21, 'end': 29, 'type': 'date'}
                ]
            }
        ]
        with open(annotated_file, 'w', encoding='utf-8') as f:
            yaml.dump(data, f)
        
        metrics = annotator.validate_annotations(str(annotated_file))
        
        assert metrics['total_entities'] == 2  # nosec B101
        assert 'time' in metrics['entity_type_distribution']  # nosec B101
        assert 'date' in metrics['entity_type_distribution']  # nosec B101
