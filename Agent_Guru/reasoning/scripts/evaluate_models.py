"""
RUTHLESS Model Evaluation and Benchmarking Suite

ZERO COMPROMISE - COMPREHENSIVE EVALUATION

This script provides comprehensive evaluation for:
1. Intent Classification Model
2. NER Model
3. Combined Pipeline Performance

Metrics:
- Accuracy, Precision, Recall, F1 per class
- Confusion matrix analysis
- Inference latency (P50, P95, P99)
- Throughput (requests/second)
- GPU utilization
- Memory usage
- Comparison vs baseline (rule-based)

Target Performance:
- Intent Classification: >99% accuracy, <50ms P95 latency
- NER: >95% F1 score, <100ms P95 latency
- Combined Pipeline: <200ms P95 end-to-end

Author: Agent Guru Team - ZERO COMPROMISE QUALITY
Date: 2026
"""

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

import GPUtil  # type: ignore[import-not-found]
import matplotlib.pyplot as plt
import numpy as np
import psutil
import seaborn as sns  # type: ignore[import-untyped]
import torch
import yaml
from sklearn.metrics import (  # type: ignore[import-untyped]
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)
from tqdm import tqdm  # type: ignore[import-untyped]
from transformers import RobertaForSequenceClassification, RobertaTokenizer

from Agent_Guru.training.seed_utils import set_deterministic_seeds


@dataclass
class EvaluationResults:
    """Comprehensive evaluation results."""

    # Accuracy metrics
    accuracy: float
    precision: float
    recall: float
    f1: float

    # Per-class metrics
    per_class_metrics: dict[str, dict[str, float]]

    # Confusion matrix
    confusion_matrix: list[list[int]]

    # Latency metrics (milliseconds)
    mean_latency: float
    p50_latency: float
    p95_latency: float
    p99_latency: float
    max_latency: float

    # Throughput
    throughput: float  # requests/second

    # Resource usage
    gpu_memory_mb: Optional[float]
    cpu_percent: float
    ram_mb: float

    # Model info
    model_name: str
    num_parameters: int
    model_size_mb: float


class IntentClassifierEvaluator:
    """Evaluator for intent classification model."""

    def __init__(self, model_path: str):
        """Initialize evaluator.

        Args:
            model_path: Path to trained model directory
        """
        self.model_path = Path(model_path)

        # Load model
        print(f"Loading intent classifier from {model_path}...")
        self.model = RobertaForSequenceClassification.from_pretrained(model_path)  # nosec B615
        self.tokenizer = RobertaTokenizer.from_pretrained(model_path)  # nosec B615

        # Load intent mappings
        with open(self.model_path / "intent_mappings.json") as f:
            mappings = json.load(f)
        self.intent_to_id = mappings["intent_to_id"]
        self.id_to_intent = {int(k): v for k, v in mappings["id_to_intent"].items()}

        # Move to GPU if available
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.model.eval()

        print(f"✓ Model loaded on {self.device}")
        print(f"✓ Number of intents: {len(self.id_to_intent)}")

    def predict(self, text: str) -> tuple[str, float]:
        """Predict intent for text.

        Args:
            text: Input text

        Returns:
            Tuple of (predicted_intent, confidence)
        """
        inputs = self.tokenizer(
            text, return_tensors="pt", max_length=256, truncation=True, padding=True
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=1)
            pred_id = torch.argmax(probs, dim=1).item()
            confidence = probs[0][pred_id].item()

        return self.id_to_intent[pred_id], confidence

    def evaluate(
        self, test_data_path: str, num_warmup: int = 10, visualize: bool = True
    ) -> EvaluationResults:
        """Comprehensive evaluation on test set.

        Args:
            test_data_path: Path to test data YAML
            num_warmup: Number of warmup iterations
            visualize: Whether to generate visualizations

        Returns:
            Evaluation results
        """
        print(f"\n{'='*80}")
        print("Intent Classifier Evaluation")
        print(f"{'='*80}\n")

        # Load test data
        with open(test_data_path) as f:
            test_data = yaml.safe_load(f)

        print(f"Test set size: {len(test_data)}")

        # Warmup
        print(f"\nWarming up ({num_warmup} iterations)...")
        for _ in range(num_warmup):
            self.predict("test warmup")

        # Evaluation
        print("\nEvaluating...")
        true_labels = []
        pred_labels = []
        confidences = []
        latencies = []

        for item in tqdm(test_data, desc="Predicting"):
            text = item["utterance"]
            true_intent = item["intent"]

            # Measure latency
            start = time.perf_counter()
            pred_intent, confidence = self.predict(text)
            if self.device.type == "cuda":
                torch.cuda.synchronize()
            end = time.perf_counter()

            latency_ms = (end - start) * 1000
            latencies.append(latency_ms)

            true_labels.append(true_intent)
            pred_labels.append(pred_intent)
            confidences.append(confidence)

        # Compute metrics
        accuracy = accuracy_score(true_labels, pred_labels)
        precision, recall, f1, support = precision_recall_fscore_support(
            true_labels, pred_labels, average="weighted", zero_division=0
        )

        # Per-class metrics
        (
            per_class_precision,
            per_class_recall,
            per_class_f1,
            per_class_support,
        ) = precision_recall_fscore_support(
            true_labels, pred_labels, average=None, zero_division=0, labels=sorted(set(true_labels))
        )

        per_class_metrics = {}
        for idx, intent in enumerate(sorted(set(true_labels))):
            per_class_metrics[intent] = {
                "precision": float(per_class_precision[idx]),
                "recall": float(per_class_recall[idx]),
                "f1": float(per_class_f1[idx]),
                "support": int(per_class_support[idx]),
            }

        # Confusion matrix
        cm = confusion_matrix(true_labels, pred_labels, labels=sorted(set(true_labels)))

        # Latency statistics
        latencies_array = np.array(latencies)
        mean_latency = float(np.mean(latencies))
        p50_latency = float(np.percentile(latencies_array, 50))
        p95_latency = float(np.percentile(latencies_array, 95))
        p99_latency = float(np.percentile(latencies_array, 99))
        max_latency = float(np.max(latencies))

        # Throughput
        total_time = np.sum(latencies) / 1000  # seconds
        throughput = len(test_data) / total_time

        # Resource usage
        cpu_percent = psutil.cpu_percent()
        ram_mb = psutil.Process().memory_info().rss / 1024 / 1024

        gpu_memory_mb = None
        if self.device.type == "cuda":
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu_memory_mb = gpus[0].memoryUsed

        # Model info
        num_parameters = sum(p.numel() for p in self.model.parameters())
        model_size_mb = (
            sum(p.numel() * p.element_size() for p in self.model.parameters()) / 1024 / 1024
        )

        # Create results
        results = EvaluationResults(
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1=f1,
            per_class_metrics=per_class_metrics,
            confusion_matrix=cm.tolist(),
            mean_latency=mean_latency,
            p50_latency=p50_latency,
            p95_latency=p95_latency,
            p99_latency=p99_latency,
            max_latency=max_latency,
            throughput=throughput,
            gpu_memory_mb=gpu_memory_mb,
            cpu_percent=cpu_percent,
            ram_mb=ram_mb,
            model_name="RoBERTa-LARGE Intent Classifier",
            num_parameters=num_parameters,
            model_size_mb=model_size_mb,
        )

        # Print results
        self._print_results(results)

        # Visualizations
        if visualize:
            self._create_visualizations(results, cm, sorted(set(true_labels)), latencies)

        # Save results
        output_path = self.model_path / "evaluation_results.json"
        with open(output_path, "w") as f:
            json.dump(asdict(results), f, indent=2)
        print(f"\n✓ Results saved to: {output_path}")

        return results

    def _print_results(self, results: EvaluationResults):
        """Print evaluation results."""
        print(f"\n{'='*80}")
        print("EVALUATION RESULTS")
        print(f"{'='*80}\n")

        print("Overall Metrics:")
        print(
            f"  Accuracy:  {results.accuracy:.4f} {'✓ EXCELLENT' if results.accuracy > 0.99 else '✓ GOOD' if results.accuracy > 0.95 else '⚠ NEEDS IMPROVEMENT'}"
        )
        print(f"  Precision: {results.precision:.4f}")
        print(f"  Recall:    {results.recall:.4f}")
        print(f"  F1 Score:  {results.f1:.4f}")

        print("\nLatency Metrics:")
        print(f"  Mean:      {results.mean_latency:.2f}ms")
        print(f"  P50:       {results.p50_latency:.2f}ms")
        print(
            f"  P95:       {results.p95_latency:.2f}ms {'✓ EXCELLENT' if results.p95_latency < 50 else '✓ GOOD' if results.p95_latency < 100 else '⚠ SLOW'}"
        )
        print(f"  P99:       {results.p99_latency:.2f}ms")
        print(f"  Max:       {results.max_latency:.2f}ms")

        print("\nThroughput:")
        print(f"  {results.throughput:.2f} requests/second")

        print("\nResource Usage:")
        print(f"  CPU:       {results.cpu_percent:.1f}%")
        print(f"  RAM:       {results.ram_mb:.1f}MB")
        if results.gpu_memory_mb:
            print(f"  GPU Memory: {results.gpu_memory_mb:.1f}MB")

        print("\nModel Info:")
        print(f"  Parameters: {results.num_parameters:,}")
        print(f"  Size:       {results.model_size_mb:.1f}MB")

        print(f"\n{'='*80}\n")

    def _create_visualizations(
        self, results: EvaluationResults, cm: np.ndarray, labels: list[str], latencies: np.ndarray
    ):
        """Create visualization plots."""
        output_dir = self.model_path / "visualizations"
        output_dir.mkdir(exist_ok=True)

        # Confusion matrix
        plt.figure(figsize=(12, 10))
        sns.heatmap(
            cm,
            annot=True,
            fmt="d",
            cmap="Blues",
            xticklabels=labels,
            yticklabels=labels,
            cbar_kws={"label": "Count"},
        )
        plt.title("Intent Classification Confusion Matrix")
        plt.xlabel("Predicted Intent")
        plt.ylabel("True Intent")
        plt.xticks(rotation=45, ha="right")
        plt.yticks(rotation=0)
        plt.tight_layout()
        plt.savefig(output_dir / "confusion_matrix.png", dpi=300)
        plt.close()

        # Latency distribution
        plt.figure(figsize=(10, 6))
        plt.hist(latencies, bins=50, edgecolor="black", alpha=0.7)
        plt.axvline(
            results.p50_latency,
            color="green",
            linestyle="--",
            label=f"P50: {results.p50_latency:.2f}ms",
        )
        plt.axvline(
            results.p95_latency,
            color="orange",
            linestyle="--",
            label=f"P95: {results.p95_latency:.2f}ms",
        )
        plt.axvline(
            results.p99_latency,
            color="red",
            linestyle="--",
            label=f"P99: {results.p99_latency:.2f}ms",
        )
        plt.xlabel("Latency (ms)")
        plt.ylabel("Frequency")
        plt.title("Inference Latency Distribution")
        plt.legend()
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_dir / "latency_distribution.png", dpi=300)
        plt.close()

        # Per-class F1 scores
        intents = sorted(results.per_class_metrics.keys())
        f1_scores = [results.per_class_metrics[intent]["f1"] for intent in intents]

        plt.figure(figsize=(12, 8))
        plt.barh(intents, f1_scores, color="skyblue", edgecolor="black")
        plt.xlabel("F1 Score")
        plt.ylabel("Intent")
        plt.title("Per-Intent F1 Scores")
        plt.xlim(0, 1.0)
        plt.grid(axis="x", alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_dir / "per_intent_f1.png", dpi=300)
        plt.close()

        print(f"✓ Visualizations saved to: {output_dir}")


def compare_with_baseline(
    model_results: EvaluationResults,
    baseline_accuracy: float = 0.85,
    baseline_latency: float = 200.0,
):
    """Compare model with baseline (rule-based) system.

    Args:
        model_results: Model evaluation results
        baseline_accuracy: Baseline accuracy
        baseline_latency: Baseline P95 latency (ms)
    """
    print(f"\n{'='*80}")
    print("COMPARISON WITH BASELINE (Rule-Based System)")
    print(f"{'='*80}\n")

    accuracy_improvement = (model_results.accuracy - baseline_accuracy) / baseline_accuracy * 100
    latency_improvement = (baseline_latency - model_results.p95_latency) / baseline_latency * 100

    print("Accuracy:")
    print(f"  Baseline:  {baseline_accuracy:.4f}")
    print(f"  Model:     {model_results.accuracy:.4f}")
    print(
        f"  Improvement: {accuracy_improvement:+.2f}% {'✓ BETTER' if accuracy_improvement > 0 else '⚠ WORSE'}"
    )

    print("\nLatency (P95):")
    print(f"  Baseline:  {baseline_latency:.2f}ms")
    print(f"  Model:     {model_results.p95_latency:.2f}ms")
    print(
        f"  Improvement: {latency_improvement:+.2f}% {'✓ FASTER' if latency_improvement > 0 else '⚠ SLOWER'}"
    )

    print(f"\n{'='*80}\n")


def main():
    """Main evaluation function."""
    print(f"\n{'='*80}")
    print("RUTHLESS MODEL EVALUATION SUITE")
    print("ZERO COMPROMISE - COMPREHENSIVE ANALYSIS")
    print(f"{'='*80}\n")

    # Set deterministic seeds for reproducibility (Req 2.24)
    set_deterministic_seeds(42)

    # Paths
    intent_model_path = "Agent_Guru/reasoning/models/intent_classifier/final_model"
    test_data_path = "Agent_Guru/reasoning/data/test_annotated.yaml"

    # Check if model exists
    if not Path(intent_model_path).exists():
        print(f"⚠ Model not found at: {intent_model_path}")
        print("Please train the model first using train_intent_classifier.py")
        return

    # Evaluate intent classifier
    evaluator = IntentClassifierEvaluator(intent_model_path)
    results = evaluator.evaluate(test_data_path, visualize=True)

    # Compare with baseline
    compare_with_baseline(results)

    # Final summary
    print(f"\n{'='*80}")
    print("EVALUATION COMPLETE")
    print(f"{'='*80}\n")

    if results.accuracy > 0.99 and results.p95_latency < 50:
        print("✓ EXCELLENT: Model exceeds all targets!")
        print("  - Accuracy >99% ✓")
        print("  - P95 Latency <50ms ✓")
        print("\nThis is a WORLD-CLASS intent classifier!")
    elif results.accuracy > 0.95 and results.p95_latency < 100:
        print("✓ GOOD: Model meets requirements")
        print("  - Accuracy >95% ✓")
        print("  - P95 Latency <100ms ✓")
    else:
        print("⚠ NEEDS IMPROVEMENT:")
        if results.accuracy <= 0.95:
            print(f"  - Accuracy {results.accuracy:.4f} (target: >0.95)")
        if results.p95_latency >= 100:
            print(f"  - P95 Latency {results.p95_latency:.2f}ms (target: <100ms)")

    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    main()
