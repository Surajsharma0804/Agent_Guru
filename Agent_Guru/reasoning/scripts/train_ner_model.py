"""STATE-OF-THE-ART NER Training - GLiNER.

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
from sklearn.metrics import precision_recall_fscore_support  # type: ignore[import-untyped]
from tqdm import tqdm  # type: ignore[import-untyped]

from Agent_Guru.security.path_utils import safe_path

try:
    from gliner import GLiNER  # type: ignore[import-untyped]
except ImportError as _gliner_err:
    msg = "GLiNER is required for NER training. Install with: pip install gliner"
    raise ImportError(
        msg,
    ) from _gliner_err


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
    with open(data_path) as f:  # nosec - path validated by caller via safe_path
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
                },
            )

        training_data.append(
            {"tokenized_text": text.split(), "ner": ner_entities},  # Simple tokenization
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
        tokens = example["tokenized_text"]

        # Predict
        pred_entities = model.predict_entities(text, entity_types, threshold=0.5)

        # Build token-level label sequences using character offsets
        true_labels = ["O"] * len(tokens)
        pred_labels = ["O"] * len(tokens)

        # Map true entities to token indices using simple word-boundary matching
        token_starts: list[int] = []
        pos = 0
        for tok in tokens:
            token_starts.append(pos)
            pos += len(tok) + 1  # +1 for space

        def _char_to_token(
            char_start: int,
            char_end: int,
            token_starts: list[int] = token_starts,
            tokens: list[str] = tokens,
        ) -> tuple[int, int]:
            """Return (first_token_idx, last_token_idx) for a char span."""
            t_start = -1
            t_end = -1
            for ti, ts in enumerate(token_starts):
                te = ts + len(tokens[ti])
                if t_start == -1 and ts <= char_start < te:
                    t_start = ti
                if ts < char_end <= te:
                    t_end = ti
                    break
            if t_start == -1:
                t_start = 0
            if t_end == -1:
                t_end = t_start
            return t_start, t_end

        # Fill true labels (B-/I- scheme)
        for ent in true_entities:
            label = ent["label"]
            t0, t1 = _char_to_token(ent.get("start", 0), ent.get("end", len(text)))
            true_labels[t0] = f"B-{label}"
            for ti in range(t0 + 1, t1 + 1):
                true_labels[ti] = f"I-{label}"

        # Fill pred labels (B-/I- scheme)
        for ent in pred_entities:
            label = ent["label"]
            ent_text: str = ent.get("text", "")
            # Find token span by matching text
            ent_tokens = ent_text.split()
            for ti in range(len(tokens) - len(ent_tokens) + 1):
                if tokens[ti : ti + len(ent_tokens)] == ent_tokens:
                    pred_labels[ti] = f"B-{label}"
                    for tj in range(ti + 1, ti + len(ent_tokens)):
                        pred_labels[tj] = f"I-{label}"
                    break

        all_true.extend(true_labels)
        all_pred.extend(pred_labels)

    # Compute metrics
    precision, recall, f1, _ = precision_recall_fscore_support(
        all_true,
        all_pred,
        average="weighted",
        zero_division=0,
    )

    return {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
    }


def train_ner_model(config: NERTrainingConfig) -> None:
    """Train GLiNER model (SOTA NER).

    Args:
        config: Training configuration

    Target Performance:
    - F1 Score: >95% on test set
    - Inference: <100ms per batch with GPU

    Training Time: 4-6 hours with GPU

    """
    # Check GPU
    if config.use_gpu:
        if torch.cuda.is_available():
            pass
        else:
            response = input("Continue on CPU? (yes/no): ")
            if response.lower() != "yes":
                return

    # Load data
    _data_base = Path(config.data_dir).resolve()
    train_data = load_ner_data(safe_path("train_annotated.yaml", _data_base))  # nosec
    val_data = load_ner_data(safe_path("val_annotated.yaml", _data_base))  # nosec
    test_data = load_ner_data(safe_path("test_annotated.yaml", _data_base))  # nosec

    # Apply augmentation
    if config.use_augmentation:
        train_data = augment_ner_data(train_data, config.augmentation_factor)

    # Get entity types
    entity_types = set()
    for example in train_data:
        for ent in example["ner"]:
            entity_types.add(ent["label"])
    entity_types = sorted(entity_types)

    # Load GLiNER model
    model = GLiNER.from_pretrained(config.base_model)

    if config.use_gpu and torch.cuda.is_available():
        model = model.to("cuda")

    # Training with GLiNER's built-in trainer

    # Calculate total steps
    steps_per_epoch = len(train_data) // config.batch_size
    max_steps = steps_per_epoch * config.num_epochs
    eval_steps = steps_per_epoch  # Evaluate once per epoch

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
    trainer.save_model()

    # Load best model for final evaluation

    # GLiNER trainer saves best model to output_dir
    model = GLiNER.from_pretrained(config.output_dir)

    if config.use_gpu and torch.cuda.is_available():
        model = model.to("cuda")

    # Test evaluation
    test_scores = evaluate_ner(model, test_data, entity_types)

    # Save final model
    _output_base = Path(config.output_dir).resolve()
    final_model_path = safe_path("final_model", _output_base)  # nosec
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

    with open(final_model_path / "test_results.json", "w") as f:  # nosec - path validated by safe_path
        json.dump(results, f, indent=2)

    with open(final_model_path / "training_config.json", "w") as f:  # nosec - path validated by safe_path
        json.dump(vars(config), f, indent=2)


if __name__ == "__main__":
    config = NERTrainingConfig()
    train_ner_model(config)
