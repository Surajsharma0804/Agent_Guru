"""
Intent Classification Model Training and Inference

This module implements fine-tuning of RoBERTa-base for intent classification
with PyTorch Lightning for production-grade training.

Performance Requirements:
- Training: Achieve >95% accuracy on test set
- Inference: <200ms P95 latency
- Model size: <500MB for deployment

Author: Agent Guru Team
Date: 2026-02-18
"""

import os
from dataclasses import dataclass
from typing import Optional

import pytorch_lightning as pl
import torch
import yaml
from pytorch_lightning.callbacks import EarlyStopping, ModelCheckpoint
from pytorch_lightning.loggers import TensorBoardLogger
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from torch.utils.data import DataLoader, Dataset
from transformers import (
    RobertaForSequenceClassification,
    RobertaTokenizer,
    get_linear_schedule_with_warmup,
)

# Import GPU device manager for automatic GPU acceleration


@dataclass
class TrainingConfig:
    """Configuration for intent classification training - PRODUCTION GRADE."""

    # Model configuration - BEST MODEL (355M parameters)
    model_name: str = "roberta-large"  # Changed from roberta-base for maximum accuracy
    max_length: int = 256  # Increased from 128 for better context

    # Training hyperparameters - OPTIMIZED FOR PRODUCTION
    learning_rate: float = 1e-5  # Lower LR for large model stability
    batch_size: int = 16  # Smaller batch for large model
    num_epochs: int = 30  # Increased from 10 for maximum convergence
    warmup_steps: int = 200  # Increased warmup for better training
    weight_decay: float = 0.01

    # Early stopping - MORE PATIENCE
    patience: int = 7  # Increased from 3 for better convergence
    min_delta: float = 0.0001  # Smaller delta for fine-grained improvements

    # Paths
    data_dir: str = "Agent_Guru/reasoning/data"
    output_dir: str = "Agent_Guru/reasoning/models/intent_classifier"

    # Device
    accelerator: str = "auto"  # "gpu" if available, else "cpu"
    devices: int = 1


class IntentDataset(Dataset):
    """Dataset for intent classification."""

    def __init__(
        self,
        texts: list[str],
        labels: list[int],
        tokenizer: RobertaTokenizer,
        max_length: int = 128,
    ):
        """Initialize dataset.

        Args:
            texts: List of input texts
            labels: List of intent labels (as integers)
            tokenizer: RoBERTa tokenizer
            max_length: Maximum sequence length
        """
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        """Get a single item from dataset.

        Args:
            idx: Index of item

        Returns:
            Dictionary with input_ids, attention_mask, and labels
        """
        text = self.texts[idx]
        label = self.labels[idx]

        # Tokenize text
        encoding = self.tokenizer(
            text,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )

        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "labels": torch.tensor(label, dtype=torch.long),
        }


class IntentClassifier(pl.LightningModule):
    """PyTorch Lightning module for intent classification."""

    def __init__(
        self,
        config: TrainingConfig,
        num_labels: int,
        label_to_id: dict[str, int],
        id_to_label: dict[int, str],
    ):
        """Initialize intent classifier.

        Args:
            config: Training configuration
            num_labels: Number of intent classes
            label_to_id: Mapping from label names to IDs
            id_to_label: Mapping from IDs to label names
        """
        super().__init__()
        self.save_hyperparameters(ignore=["label_to_id", "id_to_label"])

        self.config = config
        self.num_labels = num_labels
        self.label_to_id = label_to_id
        self.id_to_label = id_to_label

        # Load pre-trained RoBERTa model
        self.model = RobertaForSequenceClassification.from_pretrained(
            config.model_name, num_labels=num_labels
        )

        # Metrics storage
        self.validation_step_outputs = []
        self.test_step_outputs = []

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        labels: Optional[torch.Tensor] = None,
    ):
        """Forward pass.

        Args:
            input_ids: Input token IDs
            attention_mask: Attention mask
            labels: Ground truth labels (optional)

        Returns:
            Model outputs
        """
        return self.model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)

    def training_step(self, batch: dict[str, torch.Tensor], batch_idx: int):
        """Training step.

        Args:
            batch: Batch of data
            batch_idx: Batch index

        Returns:
            Loss value
        """
        outputs = self(
            input_ids=batch["input_ids"],
            attention_mask=batch["attention_mask"],
            labels=batch["labels"],
        )

        loss = outputs.loss
        self.log("train_loss", loss, prog_bar=True)

        return loss

    def validation_step(self, batch: dict[str, torch.Tensor], batch_idx: int):
        """Validation step.

        Args:
            batch: Batch of data
            batch_idx: Batch index
        """
        outputs = self(
            input_ids=batch["input_ids"],
            attention_mask=batch["attention_mask"],
            labels=batch["labels"],
        )

        loss = outputs.loss
        logits = outputs.logits
        preds = torch.argmax(logits, dim=1)

        self.validation_step_outputs.append(
            {"loss": loss, "preds": preds, "labels": batch["labels"]}
        )

    def on_validation_epoch_end(self):
        """Compute validation metrics at end of epoch."""
        all_preds = torch.cat([x["preds"] for x in self.validation_step_outputs])
        all_labels = torch.cat([x["labels"] for x in self.validation_step_outputs])
        all_losses = torch.stack([x["loss"] for x in self.validation_step_outputs])

        # Compute metrics
        avg_loss = all_losses.mean()
        accuracy = accuracy_score(all_labels.cpu().numpy(), all_preds.cpu().numpy())

        # Log metrics
        self.log("val_loss", avg_loss, prog_bar=True)
        self.log("val_accuracy", accuracy, prog_bar=True)

        # Clear outputs
        self.validation_step_outputs.clear()

    def test_step(self, batch: dict[str, torch.Tensor], batch_idx: int):
        """Test step.

        Args:
            batch: Batch of data
            batch_idx: Batch index
        """
        outputs = self(
            input_ids=batch["input_ids"],
            attention_mask=batch["attention_mask"],
            labels=batch["labels"],
        )

        logits = outputs.logits
        preds = torch.argmax(logits, dim=1)

        self.test_step_outputs.append({"preds": preds, "labels": batch["labels"]})

    def on_test_epoch_end(self):
        """Compute test metrics at end of testing."""
        all_preds = torch.cat([x["preds"] for x in self.test_step_outputs])
        all_labels = torch.cat([x["labels"] for x in self.test_step_outputs])

        # Compute metrics
        accuracy = accuracy_score(all_labels.cpu().numpy(), all_preds.cpu().numpy())

        precision, recall, f1, _ = precision_recall_fscore_support(
            all_labels.cpu().numpy(), all_preds.cpu().numpy(), average="weighted"
        )

        # Log metrics
        self.log("test_accuracy", accuracy)
        self.log("test_precision", precision)
        self.log("test_recall", recall)
        self.log("test_f1", f1)

        print("\nTest Results:")
        print(f"  Accuracy: {accuracy:.4f}")
        print(f"  Precision: {precision:.4f}")
        print(f"  Recall: {recall:.4f}")
        print(f"  F1: {f1:.4f}")

        # Clear outputs
        self.test_step_outputs.clear()

    def configure_optimizers(self):
        """Configure optimizer and learning rate scheduler."""
        # AdamW optimizer
        optimizer = torch.optim.AdamW(
            self.parameters(), lr=self.config.learning_rate, weight_decay=self.config.weight_decay
        )

        # Linear warmup + decay scheduler
        scheduler = get_linear_schedule_with_warmup(
            optimizer,
            num_warmup_steps=self.config.warmup_steps,
            num_training_steps=self.trainer.estimated_stepping_batches,
        )

        return {
            "optimizer": optimizer,
            "lr_scheduler": {"scheduler": scheduler, "interval": "step"},
        }


def load_data(
    data_dir: str,
) -> tuple[list[str], list[str], list[str], list[str], list[str], list[str]]:
    """Load training, validation, and test data.

    Args:
        data_dir: Directory containing data files

    Returns:
        Tuple of (train_texts, train_labels, val_texts, val_labels, test_texts, test_labels)
    """

    def read_file(filepath: str) -> tuple[list[str], list[str]]:
        texts = []
        labels = []
        with open(filepath, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    parts = line.split("\t")
                    if len(parts) == 2:
                        labels.append(parts[0])
                        texts.append(parts[1])
        return texts, labels

    train_texts, train_labels = read_file(os.path.join(data_dir, "train.txt"))
    val_texts, val_labels = read_file(os.path.join(data_dir, "val.txt"))
    test_texts, test_labels = read_file(os.path.join(data_dir, "test.txt"))

    return train_texts, train_labels, val_texts, val_labels, test_texts, test_labels


def create_label_mappings(
    train_labels: list[str], val_labels: list[str], test_labels: list[str]
) -> tuple[dict[str, int], dict[int, str]]:
    """Create label to ID and ID to label mappings.

    Args:
        train_labels: Training labels
        val_labels: Validation labels
        test_labels: Test labels

    Returns:
        Tuple of (label_to_id, id_to_label)
    """
    # Get all unique labels
    all_labels = sorted(set(train_labels + val_labels + test_labels))

    # Create mappings
    label_to_id = {label: idx for idx, label in enumerate(all_labels)}
    id_to_label = {idx: label for label, idx in label_to_id.items()}

    return label_to_id, id_to_label


def train_intent_classifier(config: TrainingConfig = TrainingConfig()):
    """Train intent classification model - PRODUCTION GRADE.

    Args:
        config: Training configuration
    """
    print("=" * 100)
    print("PRODUCTION-GRADE INTENT CLASSIFICATION TRAINING")
    print("Zero Compromise - Maximum Performance")
    print("=" * 100)
    print(f"\nModel: {config.model_name} (355M parameters)")
    print("Target Accuracy: >95% (Current baseline: 83.33%)")
    print("Training Strategy: Extended epochs + Large model + Optimized hyperparameters")
    print("=" * 100)

    # Create output directory
    os.makedirs(config.output_dir, exist_ok=True)

    # Load data
    print("\nLoading data...")
    train_texts, train_labels, val_texts, val_labels, test_texts, test_labels = load_data(
        config.data_dir
    )

    print(f"  Train: {len(train_texts)} examples")
    print(f"  Val: {len(val_texts)} examples")
    print(f"  Test: {len(test_texts)} examples")

    # Create label mappings
    label_to_id, id_to_label = create_label_mappings(train_labels, val_labels, test_labels)
    num_labels = len(label_to_id)
    print(f"  Number of intents: {num_labels}")

    # Save label mappings
    mappings_path = os.path.join(config.output_dir, "label_mappings.yaml")
    with open(mappings_path, "w") as f:
        yaml.dump(
            {"label_to_id": label_to_id, "id_to_label": id_to_label, "num_labels": num_labels}, f
        )
    print(f"  Saved label mappings to {mappings_path}")

    # Convert labels to IDs
    train_label_ids = [label_to_id[label] for label in train_labels]
    val_label_ids = [label_to_id[label] for label in val_labels]
    test_label_ids = [label_to_id[label] for label in test_labels]

    # Load tokenizer
    print(f"\nLoading tokenizer: {config.model_name}")
    tokenizer = RobertaTokenizer.from_pretrained(config.model_name)

    # Save tokenizer
    tokenizer.save_pretrained(config.output_dir)
    print(f"  Saved tokenizer to {config.output_dir}")

    # Create datasets
    print("\nCreating datasets...")
    train_dataset = IntentDataset(train_texts, train_label_ids, tokenizer, config.max_length)
    val_dataset = IntentDataset(val_texts, val_label_ids, tokenizer, config.max_length)
    test_dataset = IntentDataset(test_texts, test_label_ids, tokenizer, config.max_length)

    # Create dataloaders
    train_loader = DataLoader(
        train_dataset,
        batch_size=config.batch_size,
        shuffle=True,
        num_workers=0,  # Windows compatibility
    )
    val_loader = DataLoader(val_dataset, batch_size=config.batch_size, num_workers=0)
    test_loader = DataLoader(test_dataset, batch_size=config.batch_size, num_workers=0)

    # Create model
    print(f"\nInitializing model: {config.model_name}")
    model = IntentClassifier(config, num_labels, label_to_id, id_to_label)

    # Create callbacks
    early_stopping = EarlyStopping(
        monitor="val_accuracy",
        patience=config.patience,
        mode="max",
        min_delta=config.min_delta,
        verbose=True,
    )

    checkpoint_callback = ModelCheckpoint(
        dirpath=config.output_dir,
        filename="intent-classifier-{epoch:02d}-{val_accuracy:.4f}",
        monitor="val_accuracy",
        mode="max",
        save_top_k=1,
        save_last=True,
    )

    # Create logger
    logger = TensorBoardLogger(save_dir=config.output_dir, name="logs")

    # Create trainer
    print("\nInitializing trainer...")
    trainer = pl.Trainer(
        max_epochs=config.num_epochs,
        accelerator=config.accelerator,
        devices=config.devices,
        callbacks=[early_stopping, checkpoint_callback],
        logger=logger,
        log_every_n_steps=10,
        deterministic=True,
    )

    # Train model
    print("\nStarting training...")
    print(f"  Epochs: {config.num_epochs}")
    print(f"  Batch size: {config.batch_size}")
    print(f"  Learning rate: {config.learning_rate}")
    print(f"  Early stopping patience: {config.patience}")
    print()

    trainer.fit(model, train_loader, val_loader)

    # Test model
    print("\nEvaluating on test set...")
    test_results = trainer.test(model, test_loader)

    # Get test accuracy from logged metrics
    test_accuracy = trainer.callback_metrics.get("test_accuracy", 0.0)

    # Save final model
    final_model_path = os.path.join(config.output_dir, "final_model")
    model.model.save_pretrained(final_model_path)
    print(f"\nSaved final model to {final_model_path}")

    # Save training config
    config_path = os.path.join(config.output_dir, "training_config.yaml")
    with open(config_path, "w") as f:
        yaml.dump(
            {
                "model_name": config.model_name,
                "max_length": config.max_length,
                "learning_rate": config.learning_rate,
                "batch_size": config.batch_size,
                "num_epochs": config.num_epochs,
                "warmup_steps": config.warmup_steps,
                "weight_decay": config.weight_decay,
                "patience": config.patience,
                "min_delta": config.min_delta,
                "test_accuracy": float(test_accuracy)
                if isinstance(test_accuracy, torch.Tensor)
                else float(test_accuracy),
            },
            f,
        )
    print(f"Saved training config to {config_path}")

    print("\n" + "=" * 100)
    if test_accuracy >= 0.95:
        print(f"✓ SUCCESS: Test accuracy {test_accuracy*100:.2f}% MEETS >95% requirement!")
        print("  Model is PRODUCTION READY!")
    else:
        improvement = (test_accuracy - 0.8333) * 100
        print(f"  Current accuracy: {test_accuracy*100:.2f}%")
        print(f"  Improvement: +{improvement:.2f}% from baseline (83.33%)")
        print("  Target: 95.00%")
        print(f"  Gap: {(0.95 - test_accuracy)*100:.2f}%")
    print("=" * 100)
    print("Training complete!")
    print("=" * 100)


if __name__ == "__main__":
    # Train with default configuration
    train_intent_classifier()
