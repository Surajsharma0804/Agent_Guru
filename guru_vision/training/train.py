"""
ArcFace Model Training Module

This module provides functions for training custom ArcFace face recognition models
using the InsightFace framework. It supports fine-tuning ResNet-50 backbone with
ArcFace loss on custom datasets.

Requirements: 1.1, 1.5, 1.6, 1.7, 26.1, 26.2, 26.3, 28.1, 28.3, 28.4, 28.5
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import torchvision.transforms as transforms
from PIL import Image
import numpy as np

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """
    Configuration for ArcFace model training.
    
    Attributes:
        batch_size: Number of samples per batch (default: 32)
        learning_rate: Initial learning rate (default: 0.1)
        num_epochs: Number of training epochs (default: 20)
        backbone: Backbone architecture (default: "r50" for ResNet-50)
        embedding_size: Dimension of face embeddings (default: 512)
        num_workers: Number of data loading workers (default: 4)
        use_gpu: Whether to use GPU acceleration (default: True)
        momentum: SGD momentum (default: 0.9)
        weight_decay: L2 regularization weight (default: 5e-4)
        lr_schedule: Learning rate schedule type (default: "cosine")
        save_interval: Save checkpoint every N epochs (default: 5)
        validation_split: Fraction of data for validation (default: 0.1)
    
    Requirements: 1.7, 28.3, 28.4, 28.5
    """
    batch_size: int = 32
    learning_rate: float = 0.1
    num_epochs: int = 20
    backbone: str = "r50"  # ResNet-50
    embedding_size: int = 512
    num_workers: int = 4
    use_gpu: bool = True
    momentum: float = 0.9
    weight_decay: float = 5e-4
    lr_schedule: str = "cosine"
    save_interval: int = 5
    validation_split: float = 0.1
    
    # ArcFace loss parameters
    arcface_scale: float = 64.0
    arcface_margin: float = 0.5
    
    # Output paths
    output_dir: str = "guru_face/model"
    checkpoint_dir: str = "guru_face/checkpoints"
    
    def __post_init__(self):
        """Create output directories if they don't exist."""
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.checkpoint_dir, exist_ok=True)


class FaceDataset(Dataset):
    """
    Dataset for loading aligned face images for training.
    
    Expects directory structure: aligned_dataset/{IdentityName}/*.jpg
    """
    
    def __init__(self, dataset_dir: str, transform=None):
        """
        Initialize face dataset.
        
        Args:
            dataset_dir: Path to aligned dataset directory
            transform: Optional image transformations
        """
        self.dataset_dir = Path(dataset_dir)
        self.transform = transform
        self.samples = []
        self.class_to_idx = {}
        self.idx_to_class = {}
        
        # Load dataset structure
        self._load_dataset()
        
        logger.info(f"Loaded dataset with {len(self.samples)} images "
                   f"from {len(self.class_to_idx)} identities")
    
    def _load_dataset(self):
        """Load dataset structure and create class mappings."""
        if not self.dataset_dir.exists():
            raise ValueError(f"Dataset directory not found: {self.dataset_dir}")
        
        # Get all identity directories
        identity_dirs = sorted([d for d in self.dataset_dir.iterdir() if d.is_dir()])
        
        if not identity_dirs:
            raise ValueError(f"No identity directories found in {self.dataset_dir}")
        
        # Create class mappings
        for idx, identity_dir in enumerate(identity_dirs):
            identity_name = identity_dir.name
            self.class_to_idx[identity_name] = idx
            self.idx_to_class[idx] = identity_name
            
            # Load all images for this identity
            image_extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
            for img_path in identity_dir.iterdir():
                if img_path.suffix.lower() in image_extensions:
                    self.samples.append((str(img_path), idx))
        
        if not self.samples:
            raise ValueError(f"No images found in dataset directory: {self.dataset_dir}")
    
    def __len__(self) -> int:
        return len(self.samples)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, int]:
        """
        Get a sample from the dataset.
        
        Args:
            idx: Sample index
            
        Returns:
            Tuple of (image_tensor, class_label)
        """
        img_path, label = self.samples[idx]
        
        # Load image
        image = Image.open(img_path).convert('RGB')
        
        # Apply transformations
        if self.transform:
            image = self.transform(image)
        
        return image, label


class ArcFaceHead(nn.Module):
    """
    ArcFace loss head for face recognition.
    
    Implements additive angular margin loss as described in:
    "ArcFace: Additive Angular Margin Loss for Deep Face Recognition"
    """
    
    def __init__(self, embedding_size: int, num_classes: int, 
                 scale: float = 64.0, margin: float = 0.5):
        """
        Initialize ArcFace head.
        
        Args:
            embedding_size: Dimension of input embeddings
            num_classes: Number of identity classes
            scale: Feature scale (s in paper)
            margin: Angular margin (m in paper)
        """
        super(ArcFaceHead, self).__init__()
        self.embedding_size = embedding_size
        self.num_classes = num_classes
        self.scale = scale
        self.margin = margin
        
        # Weight matrix for classification
        self.weight = nn.Parameter(torch.FloatTensor(num_classes, embedding_size))
        nn.init.xavier_uniform_(self.weight)
    
    def forward(self, embeddings: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
        """
        Forward pass with ArcFace loss.
        
        Args:
            embeddings: Input embeddings (batch_size, embedding_size)
            labels: Ground truth labels (batch_size,)
            
        Returns:
            Logits for cross-entropy loss
        """
        # Normalize embeddings and weights
        embeddings = nn.functional.normalize(embeddings, p=2, dim=1)
        weight = nn.functional.normalize(self.weight, p=2, dim=1)
        
        # Compute cosine similarity
        cosine = nn.functional.linear(embeddings, weight)
        
        # Compute angular margin
        theta = torch.acos(torch.clamp(cosine, -1.0 + 1e-7, 1.0 - 1e-7))
        
        # Add margin to target class
        one_hot = torch.zeros_like(cosine)
        one_hot.scatter_(1, labels.view(-1, 1), 1.0)
        
        # Apply margin
        theta_m = theta + self.margin * one_hot
        cosine_m = torch.cos(theta_m)
        
        # Scale and return
        output = cosine_m * self.scale
        
        return output


def setup_arcface_training(num_classes: int, config: TrainingConfig) -> Tuple[nn.Module, nn.Module, optim.Optimizer]:
    """
    Initialize ResNet-50 backbone with ArcFace loss for training.
    
    This function sets up the complete training architecture including:
    - ResNet-50 backbone for feature extraction
    - ArcFace head for classification with angular margin
    - SGD optimizer with momentum
    
    Args:
        num_classes: Number of identity classes in the dataset
        config: Training configuration
        
    Returns:
        Tuple of (backbone_model, arcface_head, optimizer)
        
    Requirements: 1.1, 1.7, 26.1, 26.2, 26.3, 28.3, 28.4, 28.5
    """
    logger.info(f"Setting up ArcFace training with {config.backbone} backbone")
    logger.info(f"Number of classes: {num_classes}")
    logger.info(f"Embedding size: {config.embedding_size}")
    
    # Import torchvision models
    import torchvision.models as models
    
    # Initialize ResNet-50 backbone
    if config.backbone == "r50":
        backbone = models.resnet50(weights=None)
        
        # Modify the final layer to output embeddings
        # Remove the original FC layer
        backbone.fc = nn.Linear(backbone.fc.in_features, config.embedding_size)
        
        logger.info("Initialized ResNet-50 backbone")
    else:
        raise ValueError(f"Unsupported backbone: {config.backbone}. Only 'r50' is supported.")
    
    # Initialize ArcFace head
    arcface_head = ArcFaceHead(
        embedding_size=config.embedding_size,
        num_classes=num_classes,
        scale=config.arcface_scale,
        margin=config.arcface_margin
    )
    
    logger.info(f"Initialized ArcFace head with scale={config.arcface_scale}, "
               f"margin={config.arcface_margin}")
    
    # Move models to GPU if available
    device = torch.device("cuda" if config.use_gpu and torch.cuda.is_available() else "cpu")
    backbone = backbone.to(device)
    arcface_head = arcface_head.to(device)
    
    if device.type == "cuda":
        logger.info(f"Using GPU: {torch.cuda.get_device_name(0)}")
    else:
        logger.info("Using CPU for training")
    
    # Initialize optimizer
    # Combine parameters from both backbone and ArcFace head
    params = list(backbone.parameters()) + list(arcface_head.parameters())
    optimizer = optim.SGD(
        params,
        lr=config.learning_rate,
        momentum=config.momentum,
        weight_decay=config.weight_decay
    )
    
    logger.info(f"Initialized SGD optimizer with lr={config.learning_rate}, "
               f"momentum={config.momentum}")
    
    return backbone, arcface_head, optimizer


def get_data_transforms() -> Tuple[transforms.Compose, transforms.Compose]:
    """
    Get data augmentation transforms for training and validation.
    
    Returns:
        Tuple of (train_transform, val_transform)
    """
    # Training transforms with augmentation
    train_transform = transforms.Compose([
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5])
    ])
    
    # Validation transforms without augmentation
    val_transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5])
    ])
    
    return train_transform, val_transform


def create_data_loaders(dataset_dir: str, config: TrainingConfig) -> Tuple[DataLoader, DataLoader, int]:
    """
    Create training and validation data loaders.
    
    Args:
        dataset_dir: Path to aligned dataset directory
        config: Training configuration
        
    Returns:
        Tuple of (train_loader, val_loader, num_classes)
    """
    logger.info(f"Creating data loaders from {dataset_dir}")
    
    # Get transforms
    train_transform, val_transform = get_data_transforms()
    
    # Load full dataset
    full_dataset = FaceDataset(dataset_dir, transform=train_transform)
    num_classes = len(full_dataset.class_to_idx)
    
    # Split into train and validation
    dataset_size = len(full_dataset)
    val_size = int(dataset_size * config.validation_split)
    train_size = dataset_size - val_size
    
    train_dataset, val_dataset = torch.utils.data.random_split(
        full_dataset, [train_size, val_size]
    )
    
    # Update validation dataset transform
    val_dataset.dataset.transform = val_transform
    
    # Create data loaders
    train_loader = DataLoader(
        train_dataset,
        batch_size=config.batch_size,
        shuffle=True,
        num_workers=config.num_workers,
        pin_memory=config.use_gpu
    )
    
    val_loader = DataLoader(
        val_dataset,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=config.num_workers,
        pin_memory=config.use_gpu
    )
    
    logger.info(f"Created data loaders: train={train_size}, val={val_size}, "
               f"classes={num_classes}")
    
    return train_loader, val_loader, num_classes



def train_arcface_model(aligned_dataset_dir: str, config: TrainingConfig = None) -> str:
    """
    Train ArcFace model on aligned dataset.
    
    This function implements the complete training pipeline:
    1. Create data loaders from aligned dataset
    2. Initialize model and optimizer
    3. Train for specified number of epochs
    4. Monitor validation performance
    5. Save best checkpoint
    
    Args:
        aligned_dataset_dir: Path to aligned dataset directory
        config: Training configuration (uses defaults if None)
        
    Returns:
        Path to saved model checkpoint (guru_face_model.pth)
        
    Requirements: 1.1, 1.5, 1.6, 28.1, 28.5
    """
    # Use default config if not provided
    if config is None:
        config = TrainingConfig()
    
    logger.info("=" * 80)
    logger.info("Starting ArcFace Model Training")
    logger.info("=" * 80)
    logger.info(f"Dataset: {aligned_dataset_dir}")
    logger.info(f"Batch size: {config.batch_size}")
    logger.info(f"Learning rate: {config.learning_rate}")
    logger.info(f"Epochs: {config.num_epochs}")
    logger.info(f"Backbone: {config.backbone}")
    
    # Create data loaders
    train_loader, val_loader, num_classes = create_data_loaders(
        aligned_dataset_dir, config
    )
    
    # Setup training components
    backbone, arcface_head, optimizer = setup_arcface_training(num_classes, config)
    
    # Setup learning rate scheduler
    if config.lr_schedule == "cosine":
        scheduler = optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=config.num_epochs
        )
    elif config.lr_schedule == "step":
        scheduler = optim.lr_scheduler.StepLR(
            optimizer, step_size=10, gamma=0.1
        )
    else:
        scheduler = None
    
    # Loss function
    criterion = nn.CrossEntropyLoss()
    
    # Device
    device = torch.device("cuda" if config.use_gpu and torch.cuda.is_available() else "cpu")
    
    # Training state
    best_val_acc = 0.0
    best_model_path = None
    training_history = {
        'train_loss': [],
        'train_acc': [],
        'val_loss': [],
        'val_acc': []
    }
    
    # Training loop
    logger.info("Starting training loop...")
    
    for epoch in range(config.num_epochs):
        logger.info(f"\nEpoch {epoch + 1}/{config.num_epochs}")
        logger.info("-" * 40)
        
        # Training phase
        backbone.train()
        arcface_head.train()
        
        train_loss = 0.0
        train_correct = 0
        train_total = 0
        
        for batch_idx, (images, labels) in enumerate(train_loader):
            images = images.to(device)
            labels = labels.to(device)
            
            # Forward pass
            embeddings = backbone(images)
            logits = arcface_head(embeddings, labels)
            loss = criterion(logits, labels)
            
            # Backward pass
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            # Statistics
            train_loss += loss.item()
            _, predicted = torch.max(logits.data, 1)
            train_total += labels.size(0)
            train_correct += (predicted == labels).sum().item()
            
            # Log progress
            if (batch_idx + 1) % 10 == 0:
                logger.info(f"Batch [{batch_idx + 1}/{len(train_loader)}] "
                           f"Loss: {loss.item():.4f}")
        
        # Calculate training metrics
        train_loss = train_loss / len(train_loader)
        train_acc = 100.0 * train_correct / train_total
        
        # Validation phase
        backbone.eval()
        arcface_head.eval()
        
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        
        with torch.no_grad():
            for images, labels in val_loader:
                images = images.to(device)
                labels = labels.to(device)
                
                # Forward pass
                embeddings = backbone(images)
                logits = arcface_head(embeddings, labels)
                loss = criterion(logits, labels)
                
                # Statistics
                val_loss += loss.item()
                _, predicted = torch.max(logits.data, 1)
                val_total += labels.size(0)
                val_correct += (predicted == labels).sum().item()
        
        # Calculate validation metrics
        val_loss = val_loss / len(val_loader)
        val_acc = 100.0 * val_correct / val_total
        
        # Update learning rate
        if scheduler:
            scheduler.step()
        
        # Log epoch results
        logger.info(f"Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.2f}%")
        logger.info(f"Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.2f}%")
        logger.info(f"Learning Rate: {optimizer.param_groups[0]['lr']:.6f}")
        
        # Save training history
        training_history['train_loss'].append(train_loss)
        training_history['train_acc'].append(train_acc)
        training_history['val_loss'].append(val_loss)
        training_history['val_acc'].append(val_acc)
        
        # Save checkpoint at intervals
        if (epoch + 1) % config.save_interval == 0:
            checkpoint_path = os.path.join(
                config.checkpoint_dir,
                f"checkpoint_epoch_{epoch + 1}.pth"
            )
            torch.save({
                'epoch': epoch + 1,
                'backbone_state_dict': backbone.state_dict(),
                'arcface_head_state_dict': arcface_head.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'train_loss': train_loss,
                'val_loss': val_loss,
                'val_acc': val_acc,
                'config': config
            }, checkpoint_path)
            logger.info(f"Saved checkpoint: {checkpoint_path}")
        
        # Save best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_model_path = os.path.join(config.output_dir, "guru_face_model.pth")
            
            # Save only the backbone (for inference)
            torch.save({
                'epoch': epoch + 1,
                'backbone_state_dict': backbone.state_dict(),
                'embedding_size': config.embedding_size,
                'backbone': config.backbone,
                'val_acc': val_acc,
                'num_classes': num_classes,
                'training_history': training_history
            }, best_model_path)
            
            logger.info(f"New best model! Val Acc: {val_acc:.2f}% - Saved to {best_model_path}")
    
    # Training complete
    logger.info("=" * 80)
    logger.info("Training Complete!")
    logger.info(f"Best Validation Accuracy: {best_val_acc:.2f}%")
    logger.info(f"Best Model Saved: {best_model_path}")
    logger.info("=" * 80)
    
    return best_model_path


def load_trained_model(model_path: str, device: str = "cpu") -> nn.Module:
    """
    Load a trained ArcFace model from checkpoint.
    
    Args:
        model_path: Path to model checkpoint (.pth file)
        device: Device to load model on ("cpu" or "cuda")
        
    Returns:
        Loaded backbone model ready for inference
    """
    logger.info(f"Loading model from {model_path}")
    
    # Load checkpoint
    checkpoint = torch.load(model_path, map_location=device)
    
    # Get model configuration
    embedding_size = checkpoint.get('embedding_size', 512)
    backbone_type = checkpoint.get('backbone', 'r50')
    
    # Initialize backbone
    import torchvision.models as models
    if backbone_type == "r50":
        backbone = models.resnet50(weights=None)
        backbone.fc = nn.Linear(backbone.fc.in_features, embedding_size)
    else:
        raise ValueError(f"Unsupported backbone: {backbone_type}")
    
    # Load weights
    backbone.load_state_dict(checkpoint['backbone_state_dict'])
    backbone.to(device)
    backbone.eval()
    
    logger.info(f"Model loaded successfully (Val Acc: {checkpoint.get('val_acc', 'N/A')})")
    
    return backbone


if __name__ == "__main__":
    """
    Example usage for training ArcFace model.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Train ArcFace face recognition model")
    parser.add_argument("--dataset", type=str, required=True,
                       help="Path to aligned dataset directory")
    parser.add_argument("--batch-size", type=int, default=32,
                       help="Batch size for training")
    parser.add_argument("--epochs", type=int, default=20,
                       help="Number of training epochs")
    parser.add_argument("--lr", type=float, default=0.1,
                       help="Learning rate")
    parser.add_argument("--output-dir", type=str, default="guru_face/model",
                       help="Output directory for trained model")
    parser.add_argument("--no-gpu", action="store_true",
                       help="Disable GPU acceleration")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create training config
    config = TrainingConfig(
        batch_size=args.batch_size,
        num_epochs=args.epochs,
        learning_rate=args.lr,
        output_dir=args.output_dir,
        use_gpu=not args.no_gpu
    )
    
    # Train model
    model_path = train_arcface_model(args.dataset, config)
    
    print(f"\nTraining complete! Model saved to: {model_path}")
