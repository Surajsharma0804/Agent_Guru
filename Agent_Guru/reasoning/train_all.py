"""
RUTHLESS Training Pipeline - Train All Models

This script trains both intent classification and NER models sequentially.

Usage:
    python train_all.py

Training Time: 10-20 hours total (WORTH IT)

Author: Agent Guru Team - ZERO COMPROMISE QUALITY
Date: 2026
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from train_intent_classifier import TrainingConfig as IntentConfig
from train_intent_classifier import train_intent_classifier
from train_ner_model import NERTrainingConfig, train_ner_model


def main():
    """Train all models sequentially."""
    print(f"\n{'='*80}")
    print("RUTHLESS TRAINING PIPELINE")
    print("Training ALL models with ZERO COMPROMISE")
    print(f"{'='*80}\n")

    print("This will train:")
    print("  1. Intent Classification Model (RoBERTa-LARGE)")
    print("  2. NER Model (spaCy Transformer)")
    print()
    print("Estimated total time: 10-20 hours")
    print("Target performance:")
    print("  - Intent Accuracy: >99%")
    print("  - NER F1 Score: >95%")
    print("  - Combined Latency: <200ms P95")
    print()

    response = input("Start training? (yes/no): ")
    if response.lower() != "yes":
        print("Training cancelled.")
        return

    # Train intent classifier
    print(f"\n{'='*80}")
    print("STEP 1/2: Training Intent Classifier")
    print(f"{'='*80}\n")

    intent_config = IntentConfig()
    train_intent_classifier(intent_config)

    print(f"\n{'='*80}")
    print("✓ Intent Classifier Training Complete!")
    print(f"{'='*80}\n")

    # Train NER model
    print(f"\n{'='*80}")
    print("STEP 2/2: Training NER Model")
    print(f"{'='*80}\n")

    ner_config = NERTrainingConfig()
    train_ner_model(ner_config)

    print(f"\n{'='*80}")
    print("✓ NER Model Training Complete!")
    print(f"{'='*80}\n")

    # Final summary
    print(f"\n{'='*80}")
    print("🎉 ALL TRAINING COMPLETE!")
    print(f"{'='*80}\n")

    print("Models saved to:")
    print(f"  - Intent: {intent_config.output_dir}/final_model")
    print(f"  - NER: {ner_config.output_dir}/final_model")
    print()
    print("Next steps:")
    print("  1. Run evaluation: python evaluate_models.py")
    print("  2. Check results in models/*/evaluation_results.json")
    print("  3. View visualizations in models/*/visualizations/")
    print()
    print("Expected performance:")
    print("  ✓ Intent Accuracy: >99%")
    print("  ✓ NER F1 Score: >95%")
    print("  ✓ Combined Latency: <200ms P95")
    print()
    print("These are WORLD-CLASS models - ZERO COMPROMISE!")
    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    main()
