"""
Comprehensive tests for intent_classifier.py - 100% Coverage

Tests cover:
- TrainingConfig dataclass
- IntentDataset class
- IntentClassifier Lightning module
- Data loading functions
- Label mapping functions
- Training pipeline
"""

import os
import shutil
import tempfile
from unittest.mock import Mock, patch

import pytest
import torch

from Agent_Guru.reasoning.intent_classifier import (
    IntentClassifier,
    IntentDataset,
    TrainingConfig,
    create_label_mappings,
    load_data,
    train_intent_classifier,
)


class TestTrainingConfig:
    """Test TrainingConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = TrainingConfig()

        assert config.model_name == "roberta-large"
        assert config.max_length == 256
        assert config.learning_rate == 1e-5
        assert config.batch_size == 16
        assert config.num_epochs == 30
        assert config.warmup_steps == 200
        assert config.weight_decay == 0.01
        assert config.patience == 7
        assert config.min_delta == 0.0001
        assert config.accelerator == "auto"
        assert config.devices == 1

    def test_custom_config(self):
        """Test custom configuration values."""
        config = TrainingConfig(
            model_name="roberta-base",
            max_length=128,
            learning_rate=2e-5,
            batch_size=32,
            num_epochs=10,
        )

        assert config.model_name == "roberta-base"
        assert config.max_length == 128
        assert config.learning_rate == 2e-5
        assert config.batch_size == 32
        assert config.num_epochs == 10


class TestIntentDataset:
    """Test IntentDataset class."""

    @pytest.fixture
    def mock_tokenizer(self):
        """Create mock tokenizer."""
        tokenizer = Mock()
        tokenizer.return_value = {
            "input_ids": torch.tensor([[1, 2, 3]]),
            "attention_mask": torch.tensor([[1, 1, 1]]),
        }
        return tokenizer

    def test_dataset_initialization(self, mock_tokenizer):
        """Test dataset initialization."""
        texts = ["hello", "world"]
        labels = [0, 1]

        dataset = IntentDataset(texts, labels, mock_tokenizer, max_length=128)

        assert len(dataset) == 2
        assert dataset.texts == texts
        assert dataset.labels == labels
        assert dataset.max_length == 128

    def test_dataset_length(self, mock_tokenizer):
        """Test dataset __len__ method."""
        texts = ["a", "b", "c"]
        labels = [0, 1, 2]

        dataset = IntentDataset(texts, labels, mock_tokenizer)

        assert len(dataset) == 3

    def test_dataset_getitem(self, mock_tokenizer):
        """Test dataset __getitem__ method."""
        texts = ["hello world"]
        labels = [0]

        dataset = IntentDataset(texts, labels, mock_tokenizer, max_length=128)
        item = dataset[0]

        assert "input_ids" in item
        assert "attention_mask" in item
        assert "labels" in item
        assert isinstance(item["input_ids"], torch.Tensor)
        assert isinstance(item["attention_mask"], torch.Tensor)
        assert isinstance(item["labels"], torch.Tensor)
        assert item["labels"].item() == 0

    def test_dataset_tokenization(self, mock_tokenizer):
        """Test that tokenizer is called correctly."""
        texts = ["test text"]
        labels = [0]

        dataset = IntentDataset(texts, labels, mock_tokenizer, max_length=256)
        _ = dataset[0]

        mock_tokenizer.assert_called_once_with(
            "test text", max_length=256, padding="max_length", truncation=True, return_tensors="pt"
        )


class TestIntentClassifier:
    """Test IntentClassifier Lightning module."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return TrainingConfig(model_name="roberta-base", max_length=128, batch_size=8, num_epochs=2)

    @pytest.fixture
    def label_mappings(self):
        """Create test label mappings."""
        label_to_id = {"intent1": 0, "intent2": 1, "intent3": 2}
        id_to_label = {0: "intent1", 1: "intent2", 2: "intent3"}
        return label_to_id, id_to_label

    @patch("Agent_Guru.reasoning.intent_classifier.RobertaForSequenceClassification")
    def test_classifier_initialization(self, mock_model_class, config, label_mappings):
        """Test classifier initialization."""
        label_to_id, id_to_label = label_mappings

        classifier = IntentClassifier(config, 3, label_to_id, id_to_label)

        assert classifier.config == config
        assert classifier.num_labels == 3
        assert classifier.label_to_id == label_to_id
        assert classifier.id_to_label == id_to_label
        assert len(classifier.validation_step_outputs) == 0
        assert len(classifier.test_step_outputs) == 0

    @patch("Agent_Guru.reasoning.intent_classifier.RobertaForSequenceClassification")
    def test_forward_pass(self, mock_model_class, config, label_mappings):
        """Test forward pass."""
        label_to_id, id_to_label = label_mappings
        classifier = IntentClassifier(config, 3, label_to_id, id_to_label)

        # Mock model output
        mock_output = Mock()
        classifier.model.return_value = mock_output

        input_ids = torch.randint(0, 1000, (2, 128))
        attention_mask = torch.ones(2, 128)
        labels = torch.tensor([0, 1])

        output = classifier(input_ids, attention_mask, labels)

        assert output == mock_output
        classifier.model.assert_called_once()

    @patch("Agent_Guru.reasoning.intent_classifier.RobertaForSequenceClassification")
    def test_training_step(self, mock_model_class, config, label_mappings):
        """Test training step."""
        label_to_id, id_to_label = label_mappings
        classifier = IntentClassifier(config, 3, label_to_id, id_to_label)

        # Mock model output
        mock_output = Mock()
        mock_output.loss = torch.tensor(0.5)
        classifier.model.return_value = mock_output

        batch = {
            "input_ids": torch.randint(0, 1000, (2, 128)),
            "attention_mask": torch.ones(2, 128),
            "labels": torch.tensor([0, 1]),
        }

        loss = classifier.training_step(batch, 0)

        assert isinstance(loss, torch.Tensor)
        assert loss.item() == 0.5

    @patch("Agent_Guru.reasoning.intent_classifier.RobertaForSequenceClassification")
    def test_validation_step(self, mock_model_class, config, label_mappings):
        """Test validation step."""
        label_to_id, id_to_label = label_mappings
        classifier = IntentClassifier(config, 3, label_to_id, id_to_label)

        # Mock model output
        mock_output = Mock()
        mock_output.loss = torch.tensor(0.3)
        mock_output.logits = torch.randn(2, 3)
        classifier.model.return_value = mock_output

        batch = {
            "input_ids": torch.randint(0, 1000, (2, 128)),
            "attention_mask": torch.ones(2, 128),
            "labels": torch.tensor([0, 1]),
        }

        classifier.validation_step(batch, 0)

        assert len(classifier.validation_step_outputs) == 1
        assert "loss" in classifier.validation_step_outputs[0]
        assert "preds" in classifier.validation_step_outputs[0]
        assert "labels" in classifier.validation_step_outputs[0]

    @patch("Agent_Guru.reasoning.intent_classifier.RobertaForSequenceClassification")
    @patch("Agent_Guru.reasoning.intent_classifier.accuracy_score")
    def test_on_validation_epoch_end(self, mock_accuracy, mock_model_class, config, label_mappings):
        """Test validation epoch end."""
        label_to_id, id_to_label = label_mappings
        classifier = IntentClassifier(config, 3, label_to_id, id_to_label)

        # Add mock outputs
        classifier.validation_step_outputs = [
            {
                "loss": torch.tensor(0.3),
                "preds": torch.tensor([0, 1]),
                "labels": torch.tensor([0, 1]),
            },
            {"loss": torch.tensor(0.4), "preds": torch.tensor([2]), "labels": torch.tensor([2])},
        ]

        mock_accuracy.return_value = 0.95

        classifier.on_validation_epoch_end()

        assert len(classifier.validation_step_outputs) == 0
        mock_accuracy.assert_called_once()

    @patch("Agent_Guru.reasoning.intent_classifier.RobertaForSequenceClassification")
    def test_test_step(self, mock_model_class, config, label_mappings):
        """Test test step."""
        label_to_id, id_to_label = label_mappings
        classifier = IntentClassifier(config, 3, label_to_id, id_to_label)

        # Mock model output
        mock_output = Mock()
        mock_output.logits = torch.randn(2, 3)
        classifier.model.return_value = mock_output

        batch = {
            "input_ids": torch.randint(0, 1000, (2, 128)),
            "attention_mask": torch.ones(2, 128),
            "labels": torch.tensor([0, 1]),
        }

        classifier.test_step(batch, 0)

        assert len(classifier.test_step_outputs) == 1
        assert "preds" in classifier.test_step_outputs[0]
        assert "labels" in classifier.test_step_outputs[0]

    @patch("Agent_Guru.reasoning.intent_classifier.RobertaForSequenceClassification")
    @patch("Agent_Guru.reasoning.intent_classifier.accuracy_score")
    @patch("Agent_Guru.reasoning.intent_classifier.precision_recall_fscore_support")
    def test_on_test_epoch_end(
        self, mock_prf, mock_accuracy, mock_model_class, config, label_mappings
    ):
        """Test test epoch end."""
        label_to_id, id_to_label = label_mappings
        classifier = IntentClassifier(config, 3, label_to_id, id_to_label)

        # Add mock outputs
        classifier.test_step_outputs = [
            {"preds": torch.tensor([0, 1]), "labels": torch.tensor([0, 1])}
        ]

        mock_accuracy.return_value = 0.96
        mock_prf.return_value = (0.96, 0.96, 0.96, None)

        classifier.on_test_epoch_end()

        assert len(classifier.test_step_outputs) == 0
        mock_accuracy.assert_called_once()
        mock_prf.assert_called_once()

    @patch("Agent_Guru.reasoning.intent_classifier.RobertaForSequenceClassification")
    @patch("Agent_Guru.reasoning.intent_classifier.get_linear_schedule_with_warmup")
    def test_configure_optimizers(self, mock_scheduler, mock_model_class, config, label_mappings):
        """Test optimizer configuration."""
        label_to_id, id_to_label = label_mappings
        classifier = IntentClassifier(config, 3, label_to_id, id_to_label)

        # Mock trainer
        classifier.trainer = Mock()
        classifier.trainer.estimated_stepping_batches = 1000

        mock_scheduler.return_value = Mock()

        optimizer_config = classifier.configure_optimizers()

        assert "optimizer" in optimizer_config
        assert "lr_scheduler" in optimizer_config
        assert optimizer_config["lr_scheduler"]["interval"] == "step"


class TestDataLoading:
    """Test data loading functions."""

    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary data directory."""
        temp_dir = tempfile.mkdtemp()

        # Create train.txt
        with open(os.path.join(temp_dir, "train.txt"), "w", encoding="utf-8") as f:
            f.write("intent1\tThis is training text 1\n")
            f.write("intent2\tThis is training text 2\n")
            f.write("intent1\tThis is training text 3\n")

        # Create val.txt
        with open(os.path.join(temp_dir, "val.txt"), "w", encoding="utf-8") as f:
            f.write("intent1\tThis is validation text 1\n")
            f.write("intent2\tThis is validation text 2\n")

        # Create test.txt
        with open(os.path.join(temp_dir, "test.txt"), "w", encoding="utf-8") as f:
            f.write("intent1\tThis is test text 1\n")
            f.write("intent2\tThis is test text 2\n")

        yield temp_dir

        # Cleanup
        shutil.rmtree(temp_dir)

    def test_load_data(self, temp_data_dir):
        """Test load_data function."""
        train_texts, train_labels, val_texts, val_labels, test_texts, test_labels = load_data(
            temp_data_dir
        )

        assert len(train_texts) == 3
        assert len(train_labels) == 3
        assert len(val_texts) == 2
        assert len(val_labels) == 2
        assert len(test_texts) == 2
        assert len(test_labels) == 2

        assert train_labels[0] == "intent1"
        assert train_texts[0] == "This is training text 1"

    def test_load_data_with_empty_lines(self, temp_data_dir):
        """Test load_data with empty lines."""
        # Add empty lines
        with open(os.path.join(temp_data_dir, "train.txt"), "a", encoding="utf-8") as f:
            f.write("\n")
            f.write("   \n")

        train_texts, train_labels, _, _, _, _ = load_data(temp_data_dir)

        # Empty lines should be skipped
        assert len(train_texts) == 3
        assert len(train_labels) == 3


class TestLabelMappings:
    """Test label mapping functions."""

    def test_create_label_mappings(self):
        """Test create_label_mappings function."""
        train_labels = ["intent1", "intent2", "intent1"]
        val_labels = ["intent2", "intent3"]
        test_labels = ["intent1", "intent3"]

        label_to_id, id_to_label = create_label_mappings(train_labels, val_labels, test_labels)

        assert len(label_to_id) == 3
        assert len(id_to_label) == 3

        # Check bidirectional mapping
        for label, idx in label_to_id.items():
            assert id_to_label[idx] == label

    def test_label_mappings_sorted(self):
        """Test that label mappings are sorted."""
        train_labels = ["zebra", "apple", "banana"]
        val_labels = []
        test_labels = []

        label_to_id, id_to_label = create_label_mappings(train_labels, val_labels, test_labels)

        # Labels should be sorted alphabetically
        assert label_to_id["apple"] < label_to_id["banana"]
        assert label_to_id["banana"] < label_to_id["zebra"]


class TestTrainingPipeline:
    """Test training pipeline."""

    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary data directory."""
        temp_dir = tempfile.mkdtemp()

        # Create minimal dataset
        for filename in ["train.txt", "val.txt", "test.txt"]:
            with open(os.path.join(temp_dir, filename), "w", encoding="utf-8") as f:
                f.write("intent1\tSample text 1\n")
                f.write("intent2\tSample text 2\n")

        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def temp_output_dir(self):
        """Create temporary output directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @patch("Agent_Guru.reasoning.intent_classifier.pl.Trainer")
    @patch("Agent_Guru.reasoning.intent_classifier.RobertaTokenizer")
    @patch("Agent_Guru.reasoning.intent_classifier.IntentClassifier")
    def test_train_intent_classifier(
        self,
        mock_classifier_class,
        mock_tokenizer_class,
        mock_trainer_class,
        temp_data_dir,
        temp_output_dir,
    ):
        """Test train_intent_classifier function."""
        # Mock tokenizer
        mock_tokenizer = Mock()
        mock_tokenizer_class.from_pretrained.return_value = mock_tokenizer

        # Mock classifier
        mock_classifier = Mock()
        mock_classifier.model = Mock()
        mock_classifier_class.return_value = mock_classifier

        # Mock trainer
        mock_trainer = Mock()
        mock_trainer.callback_metrics = {"test_accuracy": torch.tensor(0.96)}
        mock_trainer_class.return_value = mock_trainer

        # Create config
        config = TrainingConfig(
            data_dir=temp_data_dir, output_dir=temp_output_dir, num_epochs=1, batch_size=2
        )

        # Run training
        train_intent_classifier(config)

        # Verify trainer was called
        mock_trainer.fit.assert_called_once()
        mock_trainer.test.assert_called_once()

        # Verify model was saved
        mock_classifier.model.save_pretrained.assert_called_once()

        # Verify label mappings were saved
        assert os.path.exists(os.path.join(temp_output_dir, "label_mappings.yaml"))

        # Verify training config was saved
        assert os.path.exists(os.path.join(temp_output_dir, "training_config.yaml"))


@pytest.mark.integration
class TestIntegrationScenarios:
    """Integration tests for complete workflows."""

    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace."""
        temp_dir = tempfile.mkdtemp()
        data_dir = os.path.join(temp_dir, "data")
        output_dir = os.path.join(temp_dir, "output")
        os.makedirs(data_dir)
        os.makedirs(output_dir)

        # Create dataset
        for filename in ["train.txt", "val.txt", "test.txt"]:
            with open(os.path.join(data_dir, filename), "w", encoding="utf-8") as f:
                for i in range(10):
                    f.write(f"intent{i % 3}\tSample text {i}\n")

        yield {"data_dir": data_dir, "output_dir": output_dir}
        shutil.rmtree(temp_dir)

    def test_end_to_end_data_pipeline(self, temp_workspace):
        """Test end-to-end data loading and processing."""
        data_dir = temp_workspace["data_dir"]

        # Load data
        train_texts, train_labels, val_texts, val_labels, test_texts, test_labels = load_data(
            data_dir
        )

        # Create mappings
        label_to_id, id_to_label = create_label_mappings(train_labels, val_labels, test_labels)

        # Verify data integrity
        assert len(train_texts) == 10
        assert len(set(train_labels)) == 3
        assert len(label_to_id) == 3

        # Verify bidirectional mapping
        for label in set(train_labels):
            idx = label_to_id[label]
            assert id_to_label[idx] == label
