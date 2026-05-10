"""Dataset generation and augmentation pipeline for intent detection."""

import random
import re
from pathlib import Path
from typing import Any

import yaml


class DatasetGenerator:
    """Generate and augment training dataset for intent detection."""

    def __init__(self, intents_file: str = "Agent_Guru/reasoning/data/intents.yaml") -> None:
        """Initialize dataset generator.

        Args:
            intents_file: Path to intents YAML file

        """
        self.intents_file = Path(intents_file)
        self.intents_data = self._load_intents()

        # Augmentation patterns for paraphrasing
        self.paraphrase_patterns = {
            "can you": ["could you", "would you", "please"],
            "I need": ["I want", "I'd like", "give me"],
            "set a": ["create a", "make a", "start a"],
            "turn on": ["switch on", "enable", "activate"],
            "turn off": ["switch off", "disable", "deactivate"],
        }

        # Noise words to add variation
        self.noise_words = ["please", "now", "right now", "quickly", "for me"]

    def _load_intents(self) -> dict[Any, Any]:
        """Load intents from YAML file."""
        with open(self.intents_file, encoding="utf-8") as f:  # noqa: PTH123
            data: dict[Any, Any] = yaml.safe_load(f)
            return data

    def augment_utterance(self, utterance: str) -> list[str]:
        """Generate augmented variations of an utterance.

        Args:
            utterance: Original utterance

        Returns:
            List of augmented utterances

        """
        variations = [utterance]

        # Paraphrase substitution
        for original, replacements in self.paraphrase_patterns.items():
            if original in utterance.lower():
                for replacement in replacements:
                    new_utterance = re.sub(original, replacement, utterance, flags=re.IGNORECASE)
                    variations.append(new_utterance)

        # Add noise words
        for noise in self.noise_words:
            # Add at beginning
            variations.append(f"{noise} {utterance}")
            # Add at end
            variations.append(f"{utterance} {noise}")

        # Case variations
        variations.append(utterance.lower())
        variations.append(utterance.upper())
        variations.append(utterance.capitalize())

        # Remove duplicates while preserving order
        seen = set()
        unique_variations = []
        for v in variations:
            if v.lower() not in seen:
                seen.add(v.lower())
                unique_variations.append(v)

        return unique_variations

    def generate_dataset(
        self,
        augmentation_factor: int = 3,
        train_split: float = 0.8,
        val_split: float = 0.1,
        test_split: float = 0.1,
        random_seed: int = 42,
    ) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]]]:
        """Generate augmented dataset with train/val/test splits.

        Args:
            augmentation_factor: Number of augmented examples per original
            train_split: Fraction for training set
            val_split: Fraction for validation set
            test_split: Fraction for test set
            random_seed: Random seed for reproducibility

        Returns:
            Tuple of (train_data, val_data, test_data)

        """
        random.seed(random_seed)

        all_examples = []

        # Generate examples for each intent
        for intent_name, intent_data in self.intents_data["intents"].items():
            examples = intent_data.get("examples", [])

            for example in examples:
                # Add original example
                all_examples.append((example, intent_name))

                # Generate augmented examples
                augmented = self.augment_utterance(example)
                # Sample augmentation_factor examples
                sampled = random.sample(
                    augmented[1:],  # Exclude original
                    min(augmentation_factor, len(augmented) - 1),
                )
                for aug_example in sampled:
                    all_examples.append((aug_example, intent_name))

        # Shuffle dataset
        random.shuffle(all_examples)

        # Split dataset
        total = len(all_examples)
        train_end = int(total * train_split)
        val_end = train_end + int(total * val_split)

        train_data = all_examples[:train_end]
        val_data = all_examples[train_end:val_end]
        test_data = all_examples[val_end:]

        return train_data, val_data, test_data

    def save_dataset(
        self,
        train_data: list[tuple[str, str]],
        val_data: list[tuple[str, str]],
        test_data: list[tuple[str, str]],
        output_dir: str = "Agent_Guru/reasoning/data",
    ) -> None:
        """Save dataset splits to files.

        Args:
            train_data: Training examples
            val_data: Validation examples
            test_data: Test examples
            output_dir: Output directory

        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Save train set
        with open(output_path / "train.txt", "w", encoding="utf-8") as f:  # noqa: PTH123
            f.writelines(f"{intent}\t{utterance}\n" for utterance, intent in train_data)

        # Save validation set
        with open(output_path / "val.txt", "w", encoding="utf-8") as f:  # noqa: PTH123
            f.writelines(f"{intent}\t{utterance}\n" for utterance, intent in val_data)

        # Save test set
        with open(output_path / "test.txt", "w", encoding="utf-8") as f:  # noqa: PTH123
            f.writelines(f"{intent}\t{utterance}\n" for utterance, intent in test_data)

        # Save statistics
        stats = {
            "train_size": len(train_data),
            "val_size": len(val_data),
            "test_size": len(test_data),
            "total_size": len(train_data) + len(val_data) + len(test_data),
            "num_intents": len(self.intents_data["intents"]),
        }

        with open(output_path / "dataset_stats.yaml", "w", encoding="utf-8") as f:  # noqa: PTH123
            yaml.dump(stats, f, default_flow_style=False)

    def get_intent_distribution(self, data: list[tuple[str, str]]) -> dict[str, int]:
        """Get distribution of intents in dataset.

        Args:
            data: Dataset examples

        Returns:
            Dictionary mapping intent to count

        """
        distribution: dict[str, int] = {}
        for _, intent in data:
            distribution[intent] = distribution.get(intent, 0) + 1
        return distribution


def main() -> None:
    """Generate and save the dataset."""
    generator = DatasetGenerator()

    # Generate dataset with augmentation
    train_data, val_data, test_data = generator.generate_dataset(
        augmentation_factor=3,
        train_split=0.8,
        val_split=0.1,
        test_split=0.1,
        random_seed=42,
    )

    # Save dataset
    generator.save_dataset(train_data, val_data, test_data)

    # Print intent distribution
    train_dist = generator.get_intent_distribution(train_data)
    for _intent, _count in sorted(train_dist.items(), key=lambda x: x[1], reverse=True)[:10]:
        pass


if __name__ == "__main__":
    main()
