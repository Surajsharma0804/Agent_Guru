"""
External System Integrations - Interfaces for Goal Manager, Model Router,
Verifier System, Memory System, and Self-Improvement Engine.

Validates: Requirements 15.x, 16.x, 17.x, 18.x, 19.x
"""

from typing import Dict, Any, Optional, List, TYPE_CHECKING
from dataclasses import dataclass
import logging

if TYPE_CHECKING:
    from .orchestration_system import OrchestrationSystem
    from .performance_tracker import PerformanceMetrics
    from .task_decomposer import Task
    from .orchestration_system import TaskResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data transfer objects
# ---------------------------------------------------------------------------


@dataclass
class ModelSelection:
    """Model selection result from Model Router."""

    model_id: str
    configuration: Dict[str, Any]


@dataclass
class VerificationResult:
    """Verification result from Verifier System."""

    passed: bool
    feedback: str


@dataclass
class AgentContext:
    """Context retrieved from Memory System."""

    agent_id: str
    task_type: str
    experiences: List[Dict[str, Any]]
    knowledge: Dict[str, Any]


# ---------------------------------------------------------------------------
# Goal Manager Integration
# ---------------------------------------------------------------------------


class GoalManagerIntegration:
    """
    Interface for receiving tasks from and returning results to the Goal Manager.

    Validates: Requirements 15.1, 15.2, 15.3, 15.4, 15.5
    """

    def __init__(self, system: "OrchestrationSystem") -> None:
        self.system = system

    async def receive_task(self, task: "Task") -> "TaskResult":
        """Receive task from Goal Manager and orchestrate execution."""
        return await self.system.receive_task(task)

    async def return_result(self, result: "TaskResult") -> None:
        """Return task result to Goal Manager (stub — implement with actual client)."""
        logger.info("Returning result for task %s: success=%s", result.task_id, result.success)


# ---------------------------------------------------------------------------
# Model Router Integration
# ---------------------------------------------------------------------------


class ModelRouterIntegration:
    """
    Interface for requesting model selection from the Model Router.

    Caches model selections per agent per task type.

    Validates: Requirements 16.1, 16.2, 16.3, 16.4, 16.5
    """

    def __init__(self, model_router_client: Any = None) -> None:
        self._client = model_router_client
        self._cache: Dict[str, ModelSelection] = {}

    async def request_model_selection(
        self,
        agent_id: str,
        task_type: str,
        specialization: Dict[str, float],
    ) -> ModelSelection:
        """Request model selection, using cache when available."""
        cache_key = f"{agent_id}:{task_type}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        if self._client:
            try:
                selection = await self._client.select_model(agent_id, task_type, specialization)
                self._cache[cache_key] = selection
                return selection
            except Exception as exc:
                logger.warning("Model Router unavailable: %s. Using default.", exc)

        # Fallback: default model
        default = ModelSelection(model_id="default", configuration={})
        self._cache[cache_key] = default
        return default


# ---------------------------------------------------------------------------
# Verifier System Integration
# ---------------------------------------------------------------------------


class VerifierSystemIntegration:
    """
    Interface for verifying agent outputs.

    Validates: Requirements 17.1, 17.2, 17.3, 17.4, 17.5
    """

    def __init__(self, verifier_client: Any = None, max_retries: int = 2) -> None:
        self._client = verifier_client
        self.max_retries = max_retries

    async def verify_agent_output(
        self, agent_id: str, task_id: str, output: Any
    ) -> VerificationResult:
        """Verify agent output, retrying on failure."""
        for attempt in range(self.max_retries + 1):
            if self._client:
                try:
                    result = await self._client.verify(agent_id, task_id, output)
                    return result
                except Exception as exc:
                    logger.warning("Verifier attempt %d failed: %s", attempt + 1, exc)
            else:
                # No verifier — pass by default
                return VerificationResult(passed=True, feedback="No verifier configured")

        return VerificationResult(passed=False, feedback="Verification failed after retries")


# ---------------------------------------------------------------------------
# Memory System Integration
# ---------------------------------------------------------------------------


class MemorySystemIntegration:
    """
    Interface for storing and retrieving agent knowledge.

    Validates: Requirements 18.1, 18.2, 18.3, 18.4, 18.5
    """

    def __init__(self, memory_client: Any = None) -> None:
        self._client = memory_client

    async def store_agent_knowledge(
        self, agent_id: str, knowledge: Dict[str, Any]
    ) -> None:
        """Store agent knowledge in Memory System."""
        if self._client:
            try:
                await self._client.store(agent_id, knowledge)
            except Exception as exc:
                logger.warning("Memory System store failed: %s", exc)

    async def retrieve_agent_context(
        self, agent_id: str, task_type: str
    ) -> AgentContext:
        """Retrieve relevant context for agent from Memory System."""
        if self._client:
            try:
                data = await self._client.retrieve(agent_id, task_type)
                return AgentContext(
                    agent_id=agent_id,
                    task_type=task_type,
                    experiences=data.get("experiences", []),
                    knowledge=data.get("knowledge", {}),
                )
            except Exception as exc:
                logger.warning("Memory System retrieve failed: %s", exc)

        return AgentContext(agent_id=agent_id, task_type=task_type, experiences=[], knowledge={})


# ---------------------------------------------------------------------------
# Self-Improvement Engine Integration
# ---------------------------------------------------------------------------


class SelfImprovementIntegration:
    """
    Interface for reporting metrics and evolution events to the Self-Improvement Engine.

    Validates: Requirements 19.1, 19.2, 19.3, 19.4, 19.5
    """

    def __init__(self, sie_client: Any = None) -> None:
        self._client = sie_client

    async def report_performance_metrics(self, metrics: "PerformanceMetrics") -> None:
        """Report performance metrics to Self-Improvement Engine."""
        if self._client:
            try:
                await self._client.report_metrics(metrics)
            except Exception as exc:
                logger.warning("SIE metrics report failed: %s", exc)

    async def report_evolution_event(self, event: Dict[str, Any]) -> None:
        """Report agent evolution event to Self-Improvement Engine."""
        if self._client:
            try:
                await self._client.report_evolution(event)
            except Exception as exc:
                logger.warning("SIE evolution report failed: %s", exc)
