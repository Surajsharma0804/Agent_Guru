"""
GitHub Sync Engine - Queues and syncs agent evolution events to GitHub.

Validates: Requirements 20.1, 20.2, 20.3, 20.4, 20.5
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SyncEvent:
    """An evolution event queued for GitHub sync."""

    event_type: str  # creation, merge, split, retirement
    agent_ids: list[str]
    details: dict[str, Any]
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
        self._queue: list[SyncEvent] = []
        self._processed: list[SyncEvent] = []
        self._failed: list[SyncEvent] = []

    def queue_evolution_event(
        self,
        event_type: str,
        agent_ids: list[str],
        details: dict[str, Any],
    ) -> None:
        """
        Queue an evolution event for GitHub sync.

        Validates: Requirement 20.1
        """
        event = SyncEvent(
            event_type=event_type,
            agent_ids=agent_ids,
            details=details,
            timestamp=datetime.now(tz=timezone.utc),
        )
        self._queue.append(event)
        logger.debug("Queued evolution event: %s for agents %s", event_type, agent_ids)

    async def process_sync_queue(self) -> dict[str, int]:
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
        safe_type = self._sanitize(event.event_type)
        safe_ids = [self._sanitize(a) for a in event.agent_ids]
        agents_str = ", ".join(safe_ids[:3])
        if len(event.agent_ids) > 3:
            agents_str += f" (+{len(event.agent_ids) - 3} more)"
        safe_ts = self._sanitize(event.timestamp.isoformat())
        return f"[agent-evolution] {safe_type}: {agents_str} at {safe_ts}"

    @staticmethod
    def _sanitize(value: str) -> str:
        """
        Escape characters that carry meaning in Markdown/HTML.

        Prevents CWE-20/79/80: untrusted strings injected into Markdown
        must not be able to introduce raw HTML tags, links, or script content.

        Time Complexity: O(n)
        """
        return (
            value
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
            .replace("`", "&#x60;")
            .replace("[", "&#x5B;")
            .replace("]", "&#x5D;")
        )

    def _build_readme_content(self, event: SyncEvent) -> str:
        """Build README.md content summarizing the evolution event. Validates: Req 20.2"""
        safe_event_type = self._sanitize(event.event_type)
        safe_agents = ", ".join(self._sanitize(a) for a in event.agent_ids)
        safe_timestamp = self._sanitize(event.timestamp.isoformat())
        # Represent details as a sanitized key=value list to avoid raw dict repr
        safe_details = ", ".join(
            f"{self._sanitize(str(k))}={self._sanitize(str(v))}"
            for k, v in event.details.items()
        )
        return (
            f"## Agent Evolution Update\n\n"
            f"**Event**: {safe_event_type}\n"
            f"**Agents**: {safe_agents}\n"
            f"**Timestamp**: {safe_timestamp}\n"
            f"**Details**: {safe_details}\n"
        )

    def batch_operations(self, events: list[SyncEvent]) -> list[list[SyncEvent]]:
        """Split events into batches of batch_size."""
        return [events[i : i + self.batch_size] for i in range(0, len(events), self.batch_size)]

    async def update_readme(self, content: str, commit_message: str) -> None:
        """Directly update README.md. Validates: Requirement 20.2"""
        await self.github_client.update_readme(content, commit_message)
