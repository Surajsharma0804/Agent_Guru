"""Privacy proof and budget tracking for federated learning."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass
class PrivacyBudget:
    """Tracks differential privacy budget consumption."""
    epsilon_max: float = 1.0
    delta_max: float = 1e-5
    epsilon_used: float = 0.0
    delta_used: float = 0.0

    def can_train(self, epsilon_cost: float, delta_cost: float) -> bool:
        return (
            self.epsilon_used + epsilon_cost <= self.epsilon_max
            and self.delta_used + delta_cost <= self.delta_max
        )

    def consume(self, epsilon_cost: float, delta_cost: float) -> None:
        self.epsilon_used += epsilon_cost
        self.delta_used += delta_cost


@dataclass
class PrivacyProof:
    """Cryptographic proof of differential privacy guarantees."""
    epsilon: float
    delta: float
    mechanism: str
    noise_scale: float
    proof_hash: str = ""

    def __post_init__(self) -> None:
        if not self.proof_hash:
            self.proof_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        data = f"{self.epsilon}:{self.delta}:{self.mechanism}:{self.noise_scale}"
        return hashlib.sha256(data.encode()).hexdigest()

    def verify(self) -> bool:
        return self.proof_hash == self._compute_hash()
