"""GitHub Sync Engine for LLM Runtime performance data.

CRITICAL: Only updates README.md files. Never creates other markdown files.

Queues performance metrics and syncs them to GitHub in batches
with exponential backoff retry.

Author: Agent Guru Team
Date: 2026-03-18
Version: 1.0.0
"""

from __future__ import annotations

import asyncio
import base64
import logging
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SyncOperation:
    """A pending GitHub sync operation."""

    operation_id: str
    content: str  # Base64-encoded README content
    commit_message: str
    timestamp: datetime
    retry_count: int = 0
    status: str = "pending"  # pending | in_progress | completed | failed


class GitHubSyncEngine:
    """Syncs LLM Runtime performance data to GitHub README.md.

    CRITICAL: Only updates README.md files, never creates other .md files.

    Features:
    - Batched updates (5-second window)
    - Exponential backoff retry (up to 5 attempts)
    - Persistent queue for GitHub unavailability
    - Background sync loop

    Example:
        >>> engine = GitHubSyncEngine(
        ...     repo_url="https://api.github.com/repos/owner/repo",
        ...     branch="main",
        ...     auth_token="ghp_...",
        ... )
        >>> op_id = await engine.queue_performance_update(metrics)

    """

    def __init__(
        self,
        repo_url: str,
        branch: str,
        auth_token: str,
        max_retries: int = 5,
        batch_window_s: float = 5.0,
    ) -> None:
        self.repo_url = repo_url
        self.branch = branch
        self.auth_token = auth_token
        self.max_retries = max_retries
        self.batch_window_s = batch_window_s

        self.pending_operations: deque[SyncOperation] = deque()
        self._client: Any | None = None
        self._sync_task: asyncio.Task | None = None  # type: ignore[type-arg]

    def start(self) -> None:
        """Start the background sync loop."""
        if self._sync_task is None or self._sync_task.done():
            self._sync_task = asyncio.create_task(self._sync_loop())

    def stop(self) -> None:
        """Stop the background sync loop."""
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()

    def _get_client(self) -> Any:
        """Lazy-initialize the httpx async client."""
        if self._client is None:
            import httpx  # type: ignore[import]

            self._client = httpx.AsyncClient(
                headers={
                    "Authorization": f"token {self.auth_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                verify=True,  # Enforce TLS certificate validation
            )
        return self._client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def queue_performance_update(self, metrics: dict[str, Any]) -> str:
        """Queue a performance metrics update for GitHub sync.

        Args:
            metrics: Performance metrics dict from PerformanceMonitor.

        Returns:
            Operation ID for tracking.

        """
        content = self._format_metrics_for_readme(metrics)
        encoded = base64.b64encode(content.encode()).decode()

        operation = SyncOperation(
            operation_id=self._generate_operation_id(),
            content=encoded,
            commit_message=self._generate_commit_message(metrics),
            timestamp=datetime.now(tz=UTC),
        )

        self.pending_operations.append(operation)
        logger.debug("Queued GitHub sync operation %s", operation.operation_id)

        return operation.operation_id

    # ------------------------------------------------------------------
    # Background sync
    # ------------------------------------------------------------------

    async def _sync_loop(self) -> None:
        """Background loop that processes pending operations."""
        while True:
            try:
                await asyncio.sleep(self.batch_window_s)
                if self.pending_operations:
                    await self._process_pending_operations()
            except asyncio.CancelledError:
                break
                logger.exception("Error in GitHub sync loop")

    async def _process_pending_operations(self) -> None:
        """Process (and batch) pending sync operations."""
        if not self.pending_operations:
            return

        # Batch multiple pending operations into one
        if len(self.pending_operations) > 1:
            batched = self._batch_operations(list(self.pending_operations))
            self.pending_operations = deque([batched])

        operation = self.pending_operations[0]
        operation.status = "in_progress"

        try:
            await self._update_readme(operation.content, operation.commit_message)
            operation.status = "completed"
            self.pending_operations.popleft()
            logger.info("GitHub sync completed: %s", operation.operation_id)

        except Exception as exc:
            operation.retry_count += 1
            operation.status = "pending"
            if operation.retry_count >= self.max_retries:
                operation.status = "failed"
                self.pending_operations.popleft()
                logger.exception(
                    "GitHub sync failed after %d retries: %s — %s",
                    self.max_retries,
                    operation.operation_id,
                    exc,
                )
            else:
                # Exponential backoff
                wait_s = 2**operation.retry_count
                logger.exception(
                    "GitHub sync retry %d/%d in %ds: %s",
                    operation.retry_count,
                    self.max_retries,
                    wait_s,
                    exc,
                )
                await asyncio.sleep(wait_s)

    async def _update_readme(self, encoded_content: str, commit_message: str) -> None:
        """Update README.md in the repository.

        CRITICAL: Only updates README.md, never creates other files.
        """
        client = self._get_client()
        readme_path = "README.md"
        api_url = f"{self.repo_url}/contents/{readme_path}"

        # Get current file SHA
        response = await client.get(api_url, params={"ref": self.branch})
        response.raise_for_status()
        current_sha = response.json()["sha"]

        # Update file
        update_response = await client.put(
            api_url,
            json={
                "message": commit_message,
                "content": encoded_content,
                "sha": current_sha,
                "branch": self.branch,
            },
        )
        update_response.raise_for_status()

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_metrics_for_readme(metrics: dict[str, Any]) -> str:
        """Format performance metrics as a Markdown table for README.md."""
        lines = [
            "# LLM Runtime Performance Metrics",
            "",
            f"Last Updated: {datetime.now(tz=UTC).isoformat()}",
            "",
            "| Model | Provider | Success Rate | Avg Latency (ms) | Total Cost |",
            "|-------|----------|--------------|------------------|------------|",
        ]

        for key, m in metrics.items():
            # Support both dict and PerformanceMetrics dataclass
            if isinstance(m, dict):
                model = m.get("model", key)
                provider = m.get("provider", "?")
                success_rate = m.get("success_rate", 0)
                avg_latency = m.get("average_latency_ms", 0)
                total_cost = m.get("total_cost", 0)
            else:
                # PerformanceMetrics dataclass
                model = getattr(m, "model", key)
                provider = getattr(
                    getattr(m, "provider", None),
                    "value",
                    str(getattr(m, "provider", "?")),
                )
                success_rate = getattr(m, "success_rate", 0)
                avg_latency = getattr(m, "average_latency_ms", 0)
                total_cost = getattr(m, "total_cost", 0)

            lines.append(
                f"| {model} | {provider} | "
                f"{success_rate:.2%} | "
                f"{avg_latency:.1f} | "
                f"${total_cost:.4f} |",
            )

        return "\n".join(lines)

    @staticmethod
    def _generate_commit_message(metrics: dict[str, Any]) -> str:
        """Generate a meaningful commit message."""
        total_requests = 0
        for m in metrics.values():
            if isinstance(m, dict):
                total_requests += m.get("total_requests", 0)
            else:
                total_requests += getattr(m, "total_requests", 0)
        return f"[LLM Runtime] Performance update — {total_requests} requests processed"

    @staticmethod
    def _generate_operation_id() -> str:
        """Generate a unique operation ID."""
        return str(uuid.uuid4())

    def _batch_operations(self, operations: list[SyncOperation]) -> SyncOperation:
        """Combine multiple operations into a single batched operation."""
        # Use the latest content (most up-to-date metrics)
        latest = operations[-1]
        return SyncOperation(
            operation_id=self._generate_operation_id(),
            content=latest.content,
            commit_message=f"[LLM Runtime] Batched update — {len(operations)} changes",
            timestamp=datetime.now(tz=UTC),
        )
