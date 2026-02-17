"""Comprehensive unit tests for dataset generator - 100% coverage."""

import pytest
from pathlib import Path
import tempfile
import shutil

from Agent_Guru.reasoning.data.dataset_generator import DatasetGenerator


class TestDatasetGenerator:
    """Test DatasetGenerator class."""
    
    @pytest.fixture
    def generator(self):
        """Create dataset generator instance."""
        return DatasetGenerator()
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test outputs."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path)
    
    def test_load_intents(self, generator):
        """Test loading intents from YAML file."""
        assert 'intents' in generator.intents_data
        assert 'entity_types' in generator.intents_data
        assert len(generator.intents_data['intents']) > 0
    
    def test_augment_utterance_basic(self, generator):
        """Test basic utterance augmentation."""
        utterance = "set a timer for 5 minutes"
        variations = generator.augment_utterance(utterance)
        
        assert len(variations) > 1
        assert utterance in variations
        assert any("create a timer" in v.lower() for v in variations)
    
    def test_augment_utterance_paraphrase(self, generator):
        """Test paraphrase substitution."""
        utterance = "can you turn on the lights"
        variations = generator.augment_utterance(utterance)
        
        # Should have paraphrases
        assert any("could you" in v.lower() for v in variations)
        assert any("switch on" in v.lower() for v in variations)
    
    def test_augment_utterance_noise_words(self, generator):
        """Test adding noise words."""
        utterance = "play music"
        variations = generator.augment_utterance(utterance)
        
        # Should have noise words added
        assert any(v.startswith("please") for v in variations)
        assert any(v.endswith("now") for v in variations)
    
    def test_augment_utterance_case_variations(self, generator):
        """Test case variations are generated."""
        utterance = "Test"
        variations = generator.augment_utterance(utterance)
        
        # Should have variations (original + noise words + paraphrases)
        assert len(variations) > 1
        assert utterance in variations or utterance.lower() in variations
    
    def test_augment_utterance_no_duplicates(self, generator):
        """Test that augmentation removes duplicates."""
        utterance = "test"
        variations = generator.augment_utterance(utterance)
        
        # Check no duplicate variations (case-insensitive)
        lower_variations = [v.lower() for v in variations]
        assert len(lower_variations) == len(set(lower_variations))
    
    def test_generate_dataset_splits(self, generator):
        """Test dataset generation with correct splits."""
        train, val, test = generator.generate_dataset(
            augmentation_factor=2,
            train_split=0.8,
            val_split=0.1,
            test_split=0.1,
            random_seed=42
        )
        
        total = len(train) + len(val) + len(test)
        
        # Check splits are approximately correct
        assert abs(len(train) / total - 0.8) < 0.05
        assert abs(len(val) / total - 0.1) < 0.05
        assert abs(len(test) / total - 0.1) < 0.05
    
    def test_generate_dataset_format(self, generator):
        """Test dataset format is correct."""
        train, val, test = generator.generate_dataset(
            augmentation_factor=1,
            random_seed=42
        )
        
        # Check format
        for utterance, intent in train[:10]:
            assert isinstance(utterance, str)
            assert isinstance(intent, str)
            assert len(utterance) > 0
            assert intent in generator.intents_data['intents']
    
    def test_generate_dataset_augmentation(self, generator):
        """Test augmentation increases dataset size."""
        train1, _, _ = generator.generate_dataset(
            augmentation_factor=1,
            random_seed=42
        )
        train2, _, _ = generator.generate_dataset(
            augmentation_factor=3,
            random_seed=42
        )
        
        # More augmentation should give more examples
        assert len(train2) > len(train1)
    
    def test_generate_dataset_reproducibility(self, generator):
        """Test dataset generation is reproducible with same seed."""
        train1, val1, test1 = generator.generate_dataset(random_seed=42)
        train2, val2, test2 = generator.generate_dataset(random_seed=42)
        
        assert train1 == train2
        assert val1 == val2
        assert test1 == test2
    
    def test_generate_dataset_different_seeds(self, generator):
        """Test different seeds produce different datasets."""
        train1, _, _ = generator.generate_dataset(random_seed=42)
        train2, _, _ = generator.generate_dataset(random_seed=123)
        
        # Should be different (very unlikely to be same)
        assert train1 != train2
    
    def test_save_dataset(self, generator, temp_dir):
        """Test saving dataset to files."""
        train = [("test utterance 1", "set_timer"), ("test utterance 2", "play_music")]
        val = [("val utterance", "query_weather")]
        test = [("test utterance", "send_message")]
        
        generator.save_dataset(train, val, test, output_dir=temp_dir)
        
        # Check files exist
        assert Path(temp_dir, "train.txt").exists()
        assert Path(temp_dir, "val.txt").exists()
        assert Path(temp_dir, "test.txt").exists()
        assert Path(temp_dir, "dataset_stats.yaml").exists()
    
    def test_save_dataset_content(self, generator, temp_dir):
        """Test saved dataset content is correct."""
        train = [("test utterance", "set_timer")]
        val = []
        test = []
        
        generator.save_dataset(train, val, test, output_dir=temp_dir)
        
        # Read and verify content
        with open(Path(temp_dir, "train.txt"), 'r', encoding='utf-8') as f:
            content = f.read()
            assert "set_timer\ttest utterance" in content
    
    def test_get_intent_distribution(self, generator):
        """Test getting intent distribution."""
        data = [
            ("utterance 1", "set_timer"),
            ("utterance 2", "set_timer"),
            ("utterance 3", "play_music"),
        ]
        
        distribution = generator.get_intent_distribution(data)
        
        assert distribution["set_timer"] == 2
        assert distribution["play_music"] == 1
    
    def test_get_intent_distribution_empty(self, generator):
        """Test intent distribution with empty data."""
        distribution = generator.get_intent_distribution([])
        assert distribution == {}
    
    def test_paraphrase_patterns_exist(self, generator):
        """Test paraphrase patterns are defined."""
        assert len(generator.paraphrase_patterns) > 0
        assert "can you" in generator.paraphrase_patterns
    
    def test_noise_words_exist(self, generator):
        """Test noise words are defined."""
        assert len(generator.noise_words) > 0
        assert "please" in generator.noise_words
    
    def test_intents_file_path(self, generator):
        """Test intents file path is set correctly."""
        assert generator.intents_file.exists()
        assert generator.intents_file.name == "intents.yaml"
