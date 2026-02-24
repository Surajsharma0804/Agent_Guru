"""
STATE-OF-THE-ART NER Training - GLiNER

Based on latest research (2024-2025):
- GLiNER: Generalist NER model using bidirectional transformer
- Zero-shot capable, outperforms ChatGPT and fine-tuned LLMs
- 130x faster than uni-encoder approaches
- State-of-the-art on CrossNER benchmark (61.5% F1 zero-shot)

Research: https://arxiv.org/abs/2311.08526
Model: urchade/gliner_large-v2.1 or knowledgator/gliner-bi-large-v1.0

Performance Targets:
- F1 Score: >95% on test set
- Inference: <100ms P95 with GPU
- Training: 4-6 hours with GPU

GPU Requirements:
- NVIDIA GPU with 12GB+ VRAM
- CUDA 11.8+ or 12.1+

Author: Agent Guru Team
Date: 2026
"""

import json
from dataclasses import dataclass
from pathlib import Path

import torch
import yaml
from gliner import gliner  # type: ignore[import-untyped]
from sklearn.metrics import precision_recall_fscore_support  # type: ignore[import-untyped]
from tqdm import tqdm  # type: ignore[import-untyped]


@dataclass
class NERTrainingConfig:
    """Training configuration for GLiNER (research-backed)."""

    # Model - SOTA for NER
    base_model: str = "urchade/gliner_large-v2.1"  # SOTA GLiNER

    # Training hyperparameters (from GLiNER paper)
    num_epochs: int = 10  # GLiNER converges fast
    batch_size: int = 8  # Optimal for GLiNER
    learning_rate: float = 5e-6  # Lower LR for fine-tuning
    warmup_ratio: float = 0.1
    weight_decay: float = 0.01

    # GPU optimization
    use_gpu: bool = True
    mixed_precision: bool = True

    # Data augmentation
    use_augmentation: bool = True
    augmentation_factor: int = 2

    # Early stopping
    patience: int = 3  # GLiNER converges fast
    min_improvement: float = 0.001

    # Paths
    data_dir: str = "Agent_Guru/reasoning/data"
    output_dir: str = "Agent_Guru/reasoning/models/ner_model"

    # Evaluation
    eval_frequency: int = 100


def load_ner_data(data_path: str) -> list[dict]:
    """Load NER training data from annotated YAML.

    Args:
        data_path: Path to annotated YAML file

    Returns:
        List of examples in GLiNER format
    """
    with open(data_path) as f:
        data = yaml.safe_load(f)

    training_data = []

    for item in data:
        text = item["utterance"]
        entities = item.get("entities", [])

        # Convert to GLiNER format
        ner_entities = []
        for entity in entities:
            ner_entities.append(
                {
                    "start": entity["start"],
                    "end": entity["end"],
                    "text": entity["text"],
                    "label": entity["type"],
                }
            )

        training_data.append(
            {"tokenized_text": text.split(), "ner": ner_entities}  # Simple tokenization
        )

    return training_data


def augment_ner_data(training_data: list[dict], augmentation_factor: int = 2) -> list[dict]:
    """Augment NER training data.

    Args:
        training_data: Original training data
        augmentation_factor: How many augmented versions per example

    Returns:
        Augmented training data
    """
    augmented_data = list(training_data)

    # Simple augmentation: duplicate for now
    # TODO: Add more sophisticated augmentation
    for _ in range(augmentation_factor - 1):
        augmented_data.extend(training_data)

    return augmented_data


def evaluate_ner(model: GLiNER, test_data: list[dict], entity_types: list[str]) -> dict[str, float]:
    """Evaluate GLiNER model.

    Args:
        model: GLiNER model
        test_data: Test examples
        entity_types: List of entity types

    Returns:
        Dictionary with precision, recall, F1 scores
    """
    all_true = []
    all_pred = []

    for example in tqdm(test_data, desc="Evaluating"):
        text = " ".join(example["tokenized_text"])
        true_entities = example["ner"]

        # Predict
        pred_entities = model.predict_entities(text, entity_types, threshold=0.5)

        # Convert to label sequences for evaluation
        tokens = example["tokenized_text"]
        true_labels = ["O"] * len(tokens)
        pred_labels = ["O"] * len(tokens)

        # Fill true labels
        for ent in true_entities:
            # Simple token-level labeling
            label = ent["label"]
            # Mark first token as B-, rest as I-
            true_labels[0] = f"B-{label}"
            for i in range(1, len(tokens)):
                if true_labels[i] == "O":
                    true_labels[i] = f"I-{label}"

        # Fill pred labels
        for ent in pred_entities:
            label = ent["label"]
            pred_labels[0] = f"B-{label}"
            for i in range(1, len(tokens)):
                if pred_labels[i] == "O":
                    pred_labels[i] = f"I-{label}"

        all_true.extend(true_labels)
        all_pred.extend(pred_labels)

    # Compute metrics
    precision, recall, f1, _ = precision_recall_fscore_support(
        all_true, all_pred, average="weighted", zero_division=0
    )

    return {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
    }


def train_ner_model(config: NERTrainingConfig):
    """Train GLiNER model (SOTA NER).

    Args:
        config: Training configuration

    Target Performance:
    - F1 Score: >95% on test set
    - Inference: <100ms per batch with GPU

    Training Time: 4-6 hours with GPU
    """
    print(f"\n{'='*80}")
    print("STATE-OF-THE-ART NER Training - GLiNER")
    print("Generalist NER with Bidirectional Transformer")
    print(f"{'='*80}\n")

    # Check GPU
    if config.use_gpu:
        if torch.cuda.is_available():
            print(f"✓ GPU enabled: {torch.cuda.get_device_name(0)}")
            print(f"✓ CUDA version: {torch.version.cuda}")
            print(
                f"✓ GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB\n"
            )
        else:
            print("⚠ WARNING: GPU not available!")
            response = input("Continue on CPU? (yes/no): ")
            if response.lower() != "yes":
                return

    print(f"✓ Model: {config.base_model}")
    print(f"✓ Max epochs: {config.num_epochs}")
    print(f"✓ Batch size: {config.batch_size}")
    print(f"✓ Learning rate: {config.learning_rate}")
    print(f"✓ Data augmentation: {config.use_augmentation}\n")

    # Load data
    print("Loading training data...")
    train_data = load_ner_data(Path(config.data_dir) / "train_annotated.yaml")
    val_data = load_ner_data(Path(config.data_dir) / "val_annotated.yaml")
    test_data = load_ner_data(Path(config.data_dir) / "test_annotated.yaml")

    print("Original dataset sizes:")
    print(f"  Train: {len(train_data)}")
    print(f"  Validation: {len(val_data)}")
    print(f"  Test: {len(test_data)}\n")

    # Apply augmentation
    if config.use_augmentation:
        print("Applying data augmentation...")
        train_data = augment_ner_data(train_data, config.augmentation_factor)
        print(f"Augmented train size: {len(train_data)}\n")

    # Get entity types
    entity_types = set()
    for example in train_data:
        for ent in example["ner"]:
            entity_types.add(ent["label"])
    entity_types = sorted(list(entity_types))

    print(f"Entity types ({len(entity_types)}): {entity_types}\n")

    # Load GLiNER model
    print("Loading GLiNER model...")
    model = GLiNER.from_pretrained(config.base_model)

    if config.use_gpu and torch.cuda.is_available():
        model = model.to("cuda")

    print("✓ Model loaded\n")

    # Training with GLiNER's built-in trainer
    print(f"{'='*80}")
    print("Starting training with GLiNER trainer...")
    print(f"{'='*80}\n")

    # Calculate total steps
    steps_per_epoch = len(train_data) // config.batch_size
    max_steps = steps_per_epoch * config.num_epochs
    eval_steps = steps_per_epoch  # Evaluate once per epoch

    print(f"Steps per epoch: {steps_per_epoch}")
    print(f"Total steps: {max_steps}")
    print(f"Eval frequency: {eval_steps} steps\n")

    # Train using GLiNER's train_model method
    trainer = model.train_model(
        train_dataset=train_data,
        eval_dataset=val_data,
        output_dir=config.output_dir,
        # Training schedule
        max_steps=max_steps,
        lr_scheduler_type="cosine",
        warmup_ratio=config.warmup_ratio,
        # Batch & optimization
        per_device_train_batch_size=config.batch_size,
        per_device_eval_batch_size=config.batch_size,
        learning_rate=config.learning_rate,
        weight_decay=config.weight_decay,
        max_grad_norm=1.0,
        # Logging & saving
        save_steps=eval_steps,
        logging_steps=100,
        save_total_limit=3,
        # Evaluation
        evaluation_strategy="steps",
        eval_steps=eval_steps,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
    )

    # Save best model
    print(f"\n{'='*80}")
    print("Saving best model...")
    print(f"{'='*80}\n")
    trainer.save_model()

    # Load best model for final evaluation
    print(f"\n{'='*80}")
    print("Loading best model for final evaluation...")
    print(f"{'='*80}\n")

    # GLiNER trainer saves best model to output_dir
    model = GLiNER.from_pretrained(config.output_dir)

    if config.use_gpu and torch.cuda.is_available():
        model = model.to("cuda")

    # Test evaluation
    print("Running test evaluation...")
    test_scores = evaluate_ner(model, test_data, entity_types)

    print(f"\n{'='*80}")
    print("Test Results:")
    print(f"{'='*80}")
    print(f"Test Precision: {test_scores['precision']:.4f}")
    print(f"Test Recall: {test_scores['recall']:.4f}")
    print(f"Test F1: {test_scores['f1']:.4f}")
    print(f"{'='*80}\n")

    # Save final model
    final_model_path = Path(config.output_dir) / "final_model"
    final_model_path.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(final_model_path))

    # Save results
    results = {
        "test_precision": test_scores["precision"],
        "test_recall": test_scores["recall"],
        "test_f1": test_scores["f1"],
        "entity_types": entity_types,
        "num_entity_types": len(entity_types),
    }

    with open(final_model_path / "test_results.json", "w") as f:
        json.dump(results, f, indent=2)

    with open(final_model_path / "training_config.json", "w") as f:
        json.dump(vars(config), f, indent=2)

    print(f"{'='*80}")
    print(f"✓ Final model saved to: {final_model_path}")
    print(f"✓ Test F1 score: {test_scores['f1']:.4f}")
    print("✓ Training complete!")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    config = NERTrainingConfig()
    train_ner_model(config)
