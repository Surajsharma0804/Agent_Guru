"""Federated Learning with Differential Privacy."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from Agent_Guru.learning.privacy import PrivacyBudget, PrivacyProof

logger = logging.getLogger(__name__)

try:
    import opacus  # type: ignore[import]  # noqa: F401

    _OPACUS_AVAILABLE = True
except ImportError:
    _OPACUS_AVAILABLE = False

# DP defaults
DEFAULT_EPSILON = 1.0
DEFAULT_DELTA = 1e-5
DEFAULT_MAX_GRAD_NORM = 1.0
DEFAULT_NOISE_MULTIPLIER = 1.1


@dataclass
class FederatedUpdate:
    """A differentially-private gradient update."""

    round_id: int
    gradient_delta: list[float]
    epsilon_cost: float
    delta_cost: float
    proof: PrivacyProof | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class FederatedLearner:
    """Federated learning with differential privacy guarantees."""

    def __init__(
        self,
        data_dir: str = "~/.agent_guru/federated",
        epsilon_max: float = DEFAULT_EPSILON,
        delta_max: float = DEFAULT_DELTA,
        max_grad_norm: float = DEFAULT_MAX_GRAD_NORM,
        noise_multiplier: float = DEFAULT_NOISE_MULTIPLIER,
    ) -> None:
        self.data_dir = Path(data_dir).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.budget = PrivacyBudget(epsilon_max=epsilon_max, delta_max=delta_max)
        self.max_grad_norm = max_grad_norm
        self.noise_multiplier = noise_multiplier
        self._opted_out = False
        self._round = 0

    def verify_privacy_budget(self, epsilon_cost: float, delta_cost: float) -> bool:
        """Check if budget allows another training round."""
        return self.budget.can_train(epsilon_cost, delta_cost)

    def train_round(
        self,
        local_data: list[Any],
        epsilon_cost: float = 0.1,
        delta_cost: float = 1e-6,
    ) -> FederatedUpdate | None:
        """Train one round with DP guarantees. Returns None if budget exceeded."""
        if self._opted_out:
            logger.info("Opted out; skipping training round")
            return None
        if not self.verify_privacy_budget(epsilon_cost, delta_cost):
            logger.warning("Privacy budget exceeded; skipping round")
            return None

        self.budget.consume(epsilon_cost, delta_cost)
        self._round += 1

        # Compute gradient delta (stub: in production uses opacus)
        gradient_delta = self._compute_dp_gradient(local_data)

        proof = PrivacyProof(
            epsilon=epsilon_cost,
            delta=delta_cost,
            mechanism="gaussian",
            noise_scale=self.noise_multiplier,
        )

        return FederatedUpdate(
            round_id=self._round,
            gradient_delta=gradient_delta,
            epsilon_cost=epsilon_cost,
            delta_cost=delta_cost,
            proof=proof,
        )

    def _compute_dp_gradient(self, local_data: list[Any]) -> list[float]:
        """Compute differentially-private gradient (stub)."""
        import random

        # Stub: return noisy zero gradient
        n = min(len(local_data), 10)
        noise = self.noise_multiplier * self.max_grad_norm
        return [random.gauss(0, noise) for _ in range(n)]

    def transmit(self, update: FederatedUpdate) -> dict[str, Any]:
        """Transmit only the DP gradient delta, never raw data."""
        return {
            "round_id": update.round_id,
            "gradient_delta": update.gradient_delta,
            "epsilon_cost": update.epsilon_cost,
            "delta_cost": update.delta_cost,
            "proof_hash": update.proof.proof_hash if update.proof else None,
        }

    def opt_out(self) -> None:
        """Opt out of federated learning and delete local data."""
        self._opted_out = True
        if self.data_dir.exists():
            shutil.rmtree(str(self.data_dir))
            logger.info("Deleted federated learning data at %s", self.data_dir)

    def is_opted_out(self) -> bool:
        return self._opted_out
