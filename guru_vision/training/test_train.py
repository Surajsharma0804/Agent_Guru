"""
Unit tests for ArcFace training module.

Tests the training pipeline components including configuration,
model setup, and data loading.
"""

import pytest
import torch
import torch.nn as nn
from pathlib import Path
import tempfile
import shutil
from PIL import Image
import numpy as np

from guru_vision.training.train import (
    TrainingConfig,
    FaceDataset,
    ArcFaceHead,
    setup_arcface_training,
    get_data_transforms,
    create_data_loaders
)


class TestTrainingConfig:
    """Test TrainingConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = TrainingConfig()
        
        assert config.batch_size == 32
        assert config.learning_rate == 0.1
        assert config.num_epochs == 20
        assert config.backbone == "r50"
        assert config.embedding_size == 512
        assert config.use_gpu is True
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = TrainingConfig(
            batch_size=64,
            learning_rate=0.01,
            num_epochs=10,
            use_gpu=False
        )
        
        assert config.batch_size == 64
        assert config.learning_rate == 0.01
        assert config.num_epochs == 10
        assert config.use_gpu is False
    
    def test_output_directories_created(self, tmp_path):
        """Test that output directories are created."""
        output_dir = tmp_path / "output"
        checkpoint_dir = tmp_path / "checkpoints"
        
        config = TrainingConfig(
            output_dir=str(output_dir),
            checkpoint_dir=str(checkpoint_dir)
        )
        
        assert output_dir.exists()
        assert checkpoint_dir.exists()


class TestFaceDataset:
    """Test FaceDataset class."""
    
    @pytest.fixture
    def sample_dataset(self, tmp_path):
        """Create a sample dataset for testing."""
        dataset_dir = tmp_path / "aligned_dataset"
        
        # Create two identity directories
        for identity in ["person1", "person2"]:
            identity_dir = dataset_dir / identity
            identity_dir.mkdir(parents=True)
            
            # Create 5 sample images per identity
            for i in range(5):
                img = Image.new('RGB', (112, 112), color=(i * 50, i * 50, i * 50))
                img.save(identity_dir / f"image_{i}.jpg")
        
        return dataset_dir
    
    def test_dataset_loading(self, sample_dataset):
        """Test dataset loads correctly."""
        dataset = FaceDataset(str(sample_dataset))
        
        assert len(dataset) == 10  # 2 identities * 5 images
        assert len(dataset.class_to_idx) == 2
        assert "person1" in dataset.class_to_idx
        assert "person2" in dataset.class_to_idx
    
    def test_dataset_getitem(self, sample_dataset):
        """Test getting items from dataset."""
        from torchvision import transforms
        
        transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5])
        ])
        
        dataset = FaceDataset(str(sample_dataset), transform=transform)
        
        image, label = dataset[0]
        
        assert isinstance(image, torch.Tensor)
        assert image.shape == (3, 112, 112)
        assert isinstance(label, int)
        assert 0 <= label < 2
    
    def test_dataset_empty_directory(self, tmp_path):
        """Test dataset raises error for empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        with pytest.raises(ValueError, match="No identity directories found"):
            FaceDataset(str(empty_dir))
    
    def test_dataset_nonexistent_directory(self):
        """Test dataset raises error for nonexistent directory."""
        with pytest.raises(ValueError, match="Dataset directory not found"):
            FaceDataset("/nonexistent/path")


class TestArcFaceHead:
    """Test ArcFace loss head."""
    
    def test_arcface_initialization(self):
        """Test ArcFace head initialization."""
        head = ArcFaceHead(
            embedding_size=512,
            num_classes=10,
            scale=64.0,
            margin=0.5
        )
        
        assert head.embedding_size == 512
        assert head.num_classes == 10
        assert head.scale == 64.0
        assert head.margin == 0.5
        assert head.weight.shape == (10, 512)
    
    def test_arcface_forward(self):
        """Test ArcFace forward pass."""
        head = ArcFaceHead(embedding_size=512, num_classes=10)
        
        # Create sample input
        batch_size = 4
        embeddings = torch.randn(batch_size, 512)
        labels = torch.randint(0, 10, (batch_size,))
        
        # Forward pass
        logits = head(embeddings, labels)
        
        assert logits.shape == (batch_size, 10)
        assert not torch.isnan(logits).any()
        assert not torch.isinf(logits).any()


class TestSetupArcFaceTraining:
    """Test setup_arcface_training function."""
    
    def test_setup_training_cpu(self):
        """Test training setup on CPU."""
        config = TrainingConfig(use_gpu=False)
        num_classes = 10
        
        backbone, arcface_head, optimizer = setup_arcface_training(num_classes, config)
        
        # Check backbone
        assert isinstance(backbone, nn.Module)
        assert hasattr(backbone, 'fc')
        assert backbone.fc.out_features == 512
        
        # Check ArcFace head
        assert isinstance(arcface_head, ArcFaceHead)
        assert arcface_head.num_classes == num_classes
        
        # Check optimizer
        assert isinstance(optimizer, torch.optim.SGD)
    
    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_setup_training_gpu(self):
        """Test training setup on GPU."""
        config = TrainingConfig(use_gpu=True)
        num_classes = 10
        
        backbone, arcface_head, optimizer = setup_arcface_training(num_classes, config)
        
        # Check models are on GPU
        assert next(backbone.parameters()).is_cuda
        assert next(arcface_head.parameters()).is_cuda
    
    def test_setup_training_invalid_backbone(self):
        """Test setup with invalid backbone raises error."""
        config = TrainingConfig(backbone="invalid")
        
        with pytest.raises(ValueError, match="Unsupported backbone"):
            setup_arcface_training(10, config)


class TestDataTransforms:
    """Test data transformation functions."""
    
    def test_get_data_transforms(self):
        """Test getting data transforms."""
        train_transform, val_transform = get_data_transforms()
        
        assert train_transform is not None
        assert val_transform is not None
        
        # Test transforms work
        img = Image.new('RGB', (112, 112), color=(128, 128, 128))
        
        train_img = train_transform(img)
        val_img = val_transform(img)
        
        assert isinstance(train_img, torch.Tensor)
        assert isinstance(val_img, torch.Tensor)
        assert train_img.shape == (3, 112, 112)
        assert val_img.shape == (3, 112, 112)


class TestCreateDataLoaders:
    """Test data loader creation."""
    
    @pytest.fixture
    def sample_dataset(self, tmp_path):
        """Create a sample dataset for testing."""
        dataset_dir = tmp_path / "aligned_dataset"
        
        # Create three identity directories
        for identity in ["person1", "person2", "person3"]:
            identity_dir = dataset_dir / identity
            identity_dir.mkdir(parents=True)
            
            # Create 10 sample images per identity
            for i in range(10):
                img = Image.new('RGB', (112, 112), color=(i * 25, i * 25, i * 25))
                img.save(identity_dir / f"image_{i}.jpg")
        
        return dataset_dir
    
    def test_create_data_loaders(self, sample_dataset):
        """Test creating data loaders."""
        config = TrainingConfig(
            batch_size=4,
            num_workers=0,  # Use 0 for testing
            validation_split=0.2
        )
        
        train_loader, val_loader, num_classes = create_data_loaders(
            str(sample_dataset), config
        )
        
        # Check loaders
        assert train_loader is not None
        assert val_loader is not None
        assert num_classes == 3
        
        # Check batch sizes
        train_batch = next(iter(train_loader))
        assert len(train_batch) == 2  # images, labels
        assert train_batch[0].shape[0] <= 4  # batch size
        
        val_batch = next(iter(val_loader))
        assert len(val_batch) == 2
        assert val_batch[0].shape[0] <= 4
    
    def test_data_loader_split(self, sample_dataset):
        """Test train/val split is correct."""
        config = TrainingConfig(
            batch_size=4,
            num_workers=0,
            validation_split=0.2
        )
        
        train_loader, val_loader, _ = create_data_loaders(
            str(sample_dataset), config
        )
        
        # Total samples: 3 identities * 10 images = 30
        # Val split: 20% = 6 samples
        # Train split: 80% = 24 samples
        
        train_samples = len(train_loader.dataset)
        val_samples = len(val_loader.dataset)
        
        assert train_samples + val_samples == 30
        assert val_samples == 6
        assert train_samples == 24


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
