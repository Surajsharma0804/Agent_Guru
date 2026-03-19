"""
GitHub Sync Engine - Queues and syncs agent evolution events to GitHub.

Validates: Requirements 20.1, 20.2, 20.3, 20.4, 20.5
"""

from typing import Dict, List, Any
from dataclasses import dataclass
from datetime import datetime
import asyncio
import logging

logger = logging.getLogger(__name__)


@dataclass
class SyncEvent:
    """An evolution event queued for GitHub sync."""

    event_type: str  # creation, merge, split, retirement
    agent_ids: List[str]
    details: Dict[str, Any]
    timestamp: datetime
    attempts: int = 0


class GitHubSyncEngine:
    """
    Queues agent evolution events and syncs them to GitHub.

    Uses exponential backoff for retries on network failures.
    Only updates README.md — never creates other markdown files.

    Time Complexity: O(1) for queue operations
    Space Complexity: O(q) where q = queue size

    Example:
        >>> engine = GitHubSyncEngine(github_client, max_retries=3)
        >>> engine.queue_evolution_event("creation", ["agent-1"], {})
        >>> await engine.process_sync_queue()

    Validates: Requirements 20.1, 20.2, 20.3, 20.4, 20.5
    """

    def __init__(
        self,
        github_client: Any,
        max_retries: int = 3,
        batch_size: int = 10,
        base_backoff_seconds: float = 1.0,
    ) -> None:
        self.github_client = github_client
        self.max_retries = max_retries
        self.batch_size = batch_size
        self.base_backoff_seconds = base_backoff_seconds
        self._queue: List[SyncEvent] = []
        self._processed: List[SyncEvent] = []
        self._failed: List[SyncEvent] = []

    def queue_evolution_event(
        self,
        event_type: str,
        agent_ids: List[str],
        details: Dict[str, Any],
    ) -> None:
        """
        Queue an evolution event for GitHub sync.

        Validates: Requirement 20.1
        """
        event = SyncEvent(
            event_type=event_type,
            agent_ids=agent_ids,
            details=details,
            timestamp=datetime.now(),
        )
        self._queue.append(event)
        logger.debug("Queued evolution event: %s for agents %s", event_type, agent_ids)

    async def process_sync_queue(self) -> Dict[str, int]:
        """
        Process all queued events in batches with retry logic.

        Returns:
            Dict with 'processed' and 'failed' counts

        Validates: Requirements 20.1, 20.3, 20.4
        """
        processed = 0
        failed = 0

        # Process in batches
        while self._queue:
            batch = self._queue[: self.batch_size]
            self._queue = self._queue[self.batch_size :]

            for event in batch:
                success = await self._sync_with_retry(event)
                if success:
                    self._processed.append(event)
                    processed += 1
                else:
                    self._failed.append(event)
                    failed += 1

        return {"processed": processed, "failed": failed}

    async def _sync_with_retry(self, event: SyncEvent) -> bool:
        """
        Attempt to sync event with exponential backoff.

        Validates: Requirement 20.4
        """
        for attempt in range(self.max_retries):
            try:
                await self._push_event(event)
                return True
            except Exception as exc:
                event.attempts += 1
                wait = self.base_backoff_seconds * (2 ** attempt)
                logger.warning(
                    "GitHub sync attempt %d/%d failed: %s. Retrying in %.1fs",
                    attempt + 1,
                    self.max_retries,
                    exc,
                    wait,
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(wait)

        logger.error("GitHub sync failed after %d attempts for event %s", self.max_retries, event.event_type)
        return False

    async def _push_event(self, event: SyncEvent) -> None:
        """Push a single event to GitHub via the client."""
        commit_message = self._build_commit_message(event)
        readme_content = self._build_readme_content(event)
        # Only update README.md — never create other markdown files (Req 20.2, 20.5)
        await self.github_client.update_readme(readme_content, commit_message)

    def _build_commit_message(self, event: SyncEvent) -> str:
        """Build a meaningful commit message for the evolution event. Validates: Req 20.3"""
        agents_str = ", ".join(event.agent_ids[:3])
        if len(event.agent_ids) > 3:
            agents_str += f" (+{len(event.agent_ids) - 3} more)"
        return f"[agent-evolution] {event.event_type}: {agents_str} at {event.timestamp.isoformat()}"

    def _build_readme_content(self, event: SyncEvent) -> str:
        """Build README.md content summarizing the evolution event. Validates: Req 20.2"""
        return (
            f"## Agent Evolution Update\n\n"
            f"**Event**: {event.event_type}\n"
            f"**Agents**: {', '.join(event.agent_ids)}\n"
            f"**Timestamp**: {event.timestamp.isoformat()}\n"
            f"**Details**: {event.details}\n"
        )

    def batch_operations(self, events: List[SyncEvent]) -> List[List[SyncEvent]]:
        """Split events into batches of batch_size."""
        return [events[i : i + self.batch_size] for i in range(0, len(events), self.batch_size)]

    async def update_readme(self, content: str, commit_message: str) -> None:
        """Directly update README.md. Validates: Requirement 20.2"""
        await self.github_client.update_readme(content, commit_message)
