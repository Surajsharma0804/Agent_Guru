"""Module: Agent_Guru.vision.training.train
Purpose: ArcFace model training pipeline.

Trains a ResNet-50 backbone with ArcFace loss on an aligned face dataset.
Saves the best checkpoint (lowest validation loss) as guru_face_model.pth.

Requirements: 1.1, 1.5, 1.6, 1.7, 26.1, 26.2, 26.3, 28.1, 28.3, 28.4, 28.5
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

logger = logging.getLogger("guruvision.training.train")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class TrainingConfig:
    """Hyperparameters and paths for ArcFace training.

    Attributes:
        dataset_dir: Path to the aligned dataset root.
        output_dir: Directory where checkpoints and the final model are saved.
        num_classes: Number of identity classes in the dataset.
        embedding_dim: Embedding dimension (512 for ArcFace).
        batch_size: Training batch size.
        learning_rate: Initial SGD learning rate.
        momentum: SGD momentum.
        weight_decay: SGD weight decay.
        epochs: Total training epochs.
        val_split: Fraction of data used for validation.
        arcface_scale: ArcFace scale (s) parameter.
        arcface_margin: ArcFace margin (m) parameter in radians.
        use_gpu: Use CUDA when True and a GPU is available.
        checkpoint_name: Filename for the best model checkpoint.
        seed: Random seed for reproducibility.

    """

    dataset_dir: str = "Agent_Guru/vision/data/aligned_dataset"
    output_dir: str = "Agent_Guru/vision/data/model"
    num_classes: int = 0  # set automatically from dataset
    embedding_dim: int = 512
    batch_size: int = 32
    learning_rate: float = 0.1
    momentum: float = 0.9
    weight_decay: float = 5e-4
    epochs: int = 20
    val_split: float = 0.1
    arcface_scale: float = 64.0
    arcface_margin: float = 0.5
    use_gpu: bool = True
    checkpoint_name: str = "guru_face_model.pth"
    seed: int = 42


# ---------------------------------------------------------------------------
# ArcFace loss
# ---------------------------------------------------------------------------


def _build_arcface_loss(
    num_classes: int,
    embedding_dim: int,
    scale: float,
    margin: float,
) -> object:
    """Build an ArcFace classification head.

    Returns a torch.nn.Module when PyTorch is available, otherwise raises
    ImportError so the caller can handle the no-torch case gracefully.
    """
    import math

    import torch
    import torch.nn.functional as F  # noqa: N812
    from torch import nn

    class ArcFaceLoss(nn.Module):
        """ArcFace additive angular margin loss (Deng et al., 2019)."""

        def __init__(self) -> None:
            super().__init__()
            self.weight = nn.Parameter(torch.FloatTensor(num_classes, embedding_dim))
            nn.init.xavier_uniform_(self.weight)
            self.scale = scale
            self.margin = margin
            self.cos_m = math.cos(margin)
            self.sin_m = math.sin(margin)
            self.th = math.cos(math.pi - margin)
            self.mm = math.sin(math.pi - margin) * margin

        def forward(self, embeddings: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
            cosine = F.linear(F.normalize(embeddings), F.normalize(self.weight))
            sine = torch.sqrt(1.0 - torch.clamp(cosine**2, 0, 1))
            phi = cosine * self.cos_m - sine * self.sin_m
            phi = torch.where(cosine > self.th, phi, cosine - self.mm)
            one_hot = torch.zeros_like(cosine)
            one_hot.scatter_(1, labels.view(-1, 1).long(), 1)
            output = (one_hot * phi) + ((1.0 - one_hot) * cosine)
            output *= self.scale
            return F.cross_entropy(output, labels)

    return ArcFaceLoss()


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------


def _build_dataset(dataset_dir: str, val_split: float, seed: int) -> tuple[object, object, int]:
    """Build train/val datasets from an aligned dataset directory.

    Returns:
        (train_dataset, val_dataset, num_classes)

    """
    from pathlib import Path as _Path

    import torch
    from torch.utils.data import Dataset, random_split

    try:
        import cv2  # type: ignore[import]  # noqa: F401

        _has_cv2 = True
    except ImportError:
        _has_cv2 = False

    class FaceDataset(Dataset):  # type: ignore[type-arg]
        def __init__(self, samples: list) -> None:
            self.samples = samples  # list of (path, label)

        def __len__(self) -> int:
            return len(self.samples)

        def __getitem__(self, idx: int) -> tuple[torch.Tensor, int]:
            path, label = self.samples[idx]
            if _has_cv2:
                import cv2 as _cv2  # type: ignore[import]

                img = _cv2.imread(str(path))
                if img is None:
                    img = np.zeros((112, 112, 3), dtype=np.uint8)
                img = _cv2.resize(img, (112, 112))
                rgb = img[:, :, ::-1].copy()
            else:
                import numpy as np

                rgb = np.zeros((112, 112, 3), dtype=np.uint8)

            import numpy as np

            tensor = torch.from_numpy(rgb.astype(np.float32).transpose(2, 0, 1) / 127.5 - 1.0)
            return tensor, label

    root = _Path(dataset_dir)
    identity_dirs = sorted(p for p in root.iterdir() if p.is_dir())
    samples = []
    for label, identity_dir in enumerate(identity_dirs):
        for img_path in identity_dir.iterdir():
            if img_path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}:
                samples.append((img_path, label))

    num_classes = len(identity_dirs)
    full_dataset = FaceDataset(samples)

    val_size = max(1, int(len(samples) * val_split))
    train_size = len(samples) - val_size
    generator = torch.Generator().manual_seed(seed)
    train_ds, val_ds = random_split(full_dataset, [train_size, val_size], generator=generator)
    return train_ds, val_ds, num_classes


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def setup_arcface_training(config: TrainingConfig) -> tuple[object, object, object, object]:
    """Initialise ResNet-50 backbone, ArcFace head, optimiser, and device.

    Args:
        config: Training configuration.

    Returns:
        (backbone, arcface_head, optimiser, device)

    Raises:
        ImportError: If PyTorch is not installed.
        ValueError: If num_classes is 0.

    """
    import torch
    from torch import nn
    from torchvision import models  # type: ignore[import]

    if config.num_classes <= 0:
        msg = (
            f"num_classes must be > 0, got {config.num_classes}. "
            "Set it from the dataset before calling setup_arcface_training()."
        )
        raise ValueError(
            msg,
        )

    torch.manual_seed(config.seed)

    device = torch.device("cuda" if config.use_gpu and torch.cuda.is_available() else "cpu")
    logger.info("Training device: %s", device)

    # ResNet-50 backbone - replace final FC with embedding projection.
    backbone = models.resnet50(weights=None)
    backbone.fc = nn.Linear(backbone.fc.in_features, config.embedding_dim)
    backbone = backbone.to(device)

    arcface_head = _build_arcface_loss(
        num_classes=config.num_classes,
        embedding_dim=config.embedding_dim,
        scale=config.arcface_scale,
        margin=config.arcface_margin,
    ).to(device)

    optimiser = torch.optim.SGD(
        list(backbone.parameters()) + list(arcface_head.parameters()),
        lr=config.learning_rate,
        momentum=config.momentum,
        weight_decay=config.weight_decay,
    )

    return backbone, arcface_head, optimiser, device


def train_arcface_model(config: TrainingConfig) -> str:
    """Train ArcFace model and save the best checkpoint.

    Args:
        config: Training configuration.  config.num_classes is set
            automatically from the dataset if it is 0.

    Returns:
        Path to the saved best checkpoint (.pth file).

    Raises:
        ImportError: If PyTorch is not installed.
        FileNotFoundError: If dataset_dir does not exist.

    """
    import torch
    from torch.utils.data import DataLoader

    dataset_dir = config.dataset_dir
    if not os.path.isdir(dataset_dir):  # noqa: PTH112
        msg = f"Dataset directory not found: {dataset_dir}"
        raise FileNotFoundError(msg)

    train_ds, val_ds, num_classes = _build_dataset(dataset_dir, config.val_split, config.seed)
    if config.num_classes == 0:
        config.num_classes = num_classes
    logger.info(
        "Dataset loaded: %d classes, %d train, %d val samples",
        num_classes,
        len(train_ds),
        len(val_ds),
    )

    backbone, arcface_head, optimiser, device = setup_arcface_training(config)

    train_loader = DataLoader(
        train_ds,
        batch_size=config.batch_size,
        shuffle=True,
        num_workers=0,
        pin_memory=(str(device) != "cpu"),
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=0,
    )

    scheduler = torch.optim.lr_scheduler.MultiStepLR(optimiser, milestones=[10, 16], gamma=0.1)

    output_path = Path(config.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    checkpoint_path = str(output_path / config.checkpoint_name)

    best_val_loss = float("inf")

    for epoch in range(1, config.epochs + 1):
        # --- Training ---
        backbone.train()
        arcface_head.train()
        train_loss = 0.0
        for images, labels in train_loader:
            images = images.to(device)
            labels = labels.to(device)
            optimiser.zero_grad()
            embeddings = backbone(images)
            loss = arcface_head(embeddings, labels)
            loss.backward()
            optimiser.step()
            train_loss += loss.item()

        train_loss /= max(len(train_loader), 1)

        # --- Validation ---
        backbone.eval()
        val_loss = 0.0
        with torch.no_grad():
            for images, labels in val_loader:
                images = images.to(device)
                labels = labels.to(device)
                embeddings = backbone(images)
                loss = arcface_head(embeddings, labels)
                val_loss += loss.item()
        val_loss /= max(len(val_loader), 1)

        scheduler.step()

        logger.info(
            "Epoch %d/%d - train_loss=%.4f  val_loss=%.4f",
            epoch,
            config.epochs,
            train_loss,
            val_loss,
        )

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(
                {
                    "epoch": epoch,
                    "backbone_state_dict": backbone.state_dict(),
                    "arcface_state_dict": arcface_head.state_dict(),
                    "optimiser_state_dict": optimiser.state_dict(),
                    "val_loss": val_loss,
                    "num_classes": num_classes,
                    "embedding_dim": config.embedding_dim,
                },
                checkpoint_path,
            )
            logger.info("Saved best checkpoint → %s (val_loss=%.4f)", checkpoint_path, val_loss)

    logger.info("Training complete. Best val_loss=%.4f", best_val_loss)
    return checkpoint_path
