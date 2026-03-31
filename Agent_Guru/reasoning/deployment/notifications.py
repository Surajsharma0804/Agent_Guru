"""
Deployment Notification System for Agent Guru

Sends notifications to Slack and other channels about deployment events.

Author: Agent Guru Team
Date: 2026-02-22
"""

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import aiohttp
import structlog

logger = structlog.get_logger(__name__)


class DeploymentStatus(Enum):
    """Deployment status types."""
    STARTED = "started"
    SUCCESS = "success"
    FAILURE = "failure"
    ROLLBACK = "rollback"


@dataclass
class DeploymentInfo:
    """Deployment information."""
    environment: str  # staging or production
    version: str
    commit_sha: str
    commit_message: str
    deployer: str
    timestamp: datetime
    status: DeploymentStatus
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None
    logs_url: Optional[str] = None
    metrics_url: Optional[str] = None
    grafana_url: Optional[str] = None


class NotificationService:
    """
    Service for sending deployment notifications.

    Supports multiple notification channels:
    - Slack
    - Email (future)
    - PagerDuty (future)
    """

    def __init__(
        self,
        slack_webhook_url: Optional[str] = None,
        slack_channel: Optional[str] = None
    ):
        """Initialize notification service.

        Args:
            slack_webhook_url: Slack webhook URL
            slack_channel: Slack channel name (optional override)
        """
        self.slack_webhook_url = slack_webhook_url
        self.slack_channel = slack_channel

        logger.info(
            "notification_service_initialized",
            slack_enabled=bool(slack_webhook_url)
        )

    async def send_deployment_notification(
        self,
        deployment: DeploymentInfo
    ) -> None:
        """Send deployment notification to all configured channels.

        Args:
            deployment: Deployment information
        """
        logger.info(
            "sending_deployment_notification",
            environment=deployment.environment,
            status=deployment.status.value,
            version=deployment.version
        )

        # Send to Slack
        if self.slack_webhook_url:
            await self._send_slack_notification(deployment)

        # Future: Send to email, PagerDuty, etc.

    async def _send_slack_notification(
        self,
        deployment: DeploymentInfo
    ) -> None:
        """Send notification to Slack.

        Args:
            deployment: Deployment information
        """
        try:
            message = self._format_slack_message(deployment)

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.slack_webhook_url,
                    json=message,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        logger.info("slack_notification_sent")
                    else:
                        logger.warning(
                            "slack_notification_failed",
                            status=response.status,
                            response=await response.text()
                        )
        except Exception as e:
            logger.error("slack_notification_error", error=str(e))

    def _format_slack_message(
        self,
        deployment: DeploymentInfo
    ) -> dict:
        """Format Slack message with rich formatting.

        Args:
            deployment: Deployment information

        Returns:
            Slack message payload
        """
        # Determine emoji and color based on status
        if deployment.status == DeploymentStatus.STARTED:
            emoji = "🚀"
            color = "#0066cc"  # Blue
            title = "Deployment Started"
        elif deployment.status == DeploymentStatus.SUCCESS:
            emoji = "✅"
            color = "#00cc00"  # Green
            title = "Deployment Successful"
        elif deployment.status == DeploymentStatus.FAILURE:
            emoji = "❌"
            color = "#cc0000"  # Red
            title = "Deployment Failed"
        elif deployment.status == DeploymentStatus.ROLLBACK:
            emoji = "⚠️"
            color = "#ff9900"  # Orange
            title = "Deployment Rolled Back"
        else:
            emoji = "ℹ️"
            color = "#666666"  # Gray
            title = "Deployment Update"

        # Build fields
        fields = [
            {
                "title": "Environment",
                "value": deployment.environment.upper(),
                "short": True
            },
            {
                "title": "Version",
                "value": deployment.version,
                "short": True
            },
            {
                "title": "Commit",
                "value": f"`{deployment.commit_sha[:8]}`",
                "short": True
            },
            {
                "title": "Deployer",
                "value": deployment.deployer,
                "short": True
            },
            {
                "title": "Time",
                "value": deployment.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "short": True
            }
        ]

        # Add duration if available
        if deployment.duration_seconds is not None:
            fields.append({
                "title": "Duration",
                "value": f"{deployment.duration_seconds:.1f}s",
                "short": True
            })

        # Add commit message
        if deployment.commit_message:
            fields.append({
                "title": "Changes",
                "value": deployment.commit_message[:500],  # Truncate long messages
                "short": False
            })

        # Add error message if failure
        if deployment.error_message:
            fields.append({
                "title": "Error",
                "value": f"```{deployment.error_message[:1000]}```",
                "short": False
            })

        # Build actions (links)
        actions = []

        if deployment.logs_url:
            actions.append({
                "type": "button",
                "text": "View Logs",
                "url": deployment.logs_url
            })

        if deployment.metrics_url:
            actions.append({
                "type": "button",
                "text": "View Metrics",
                "url": deployment.metrics_url
            })

        if deployment.grafana_url:
            actions.append({
                "type": "button",
                "text": "Grafana Dashboard",
                "url": deployment.grafana_url
            })

        # Build attachment
        attachment = {
            "fallback": f"{emoji} {title}: {deployment.environment} - {deployment.version}",
            "color": color,
            "title": f"{emoji} {title}",
            "fields": fields,
            "footer": "Agent Guru Deployment System",
            "footer_icon": "https://agent-guru.example.com/icon.png",
            "ts": int(deployment.timestamp.timestamp())
        }

        # Add actions if any
        if actions:
            attachment["actions"] = actions

        # Build message
        message = {
            "username": "Agent Guru Deploy Bot",
            "icon_emoji": ":robot_face:",
            "attachments": [attachment]
        }

        # Add channel override if specified
        if self.slack_channel:
            message["channel"] = self.slack_channel

        return message


async def send_deployment_started(
    environment: str,
    version: str,
    commit_sha: str,
    commit_message: str,
    deployer: str
) -> None:
    """Send deployment started notification.

    Args:
        environment: Deployment environment
        version: Version being deployed
        commit_sha: Git commit SHA
        commit_message: Git commit message
        deployer: Person/system deploying
    """
    service = NotificationService(
        slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL")
    )

    deployment = DeploymentInfo(
        environment=environment,
        version=version,
        commit_sha=commit_sha,
        commit_message=commit_message,
        deployer=deployer,
        timestamp=datetime.now(tz=timezone.utc),
        status=DeploymentStatus.STARTED,
        logs_url="https://github.com/agent-guru/agent-guru/actions",
        metrics_url="https://prometheus.agent-guru.example.com",
        grafana_url=f"https://grafana.agent-guru.example.com/d/deployment-{environment}"
    )

    await service.send_deployment_notification(deployment)


async def send_deployment_success(
    environment: str,
    version: str,
    commit_sha: str,
    commit_message: str,
    deployer: str,
    duration_seconds: float
) -> None:
    """Send deployment success notification.

    Args:
        environment: Deployment environment
        version: Version deployed
        commit_sha: Git commit SHA
        commit_message: Git commit message
        deployer: Person/system who deployed
        duration_seconds: Deployment duration
    """
    service = NotificationService(
        slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL")
    )

    deployment = DeploymentInfo(
        environment=environment,
        version=version,
        commit_sha=commit_sha,
        commit_message=commit_message,
        deployer=deployer,
        timestamp=datetime.now(tz=timezone.utc),
        status=DeploymentStatus.SUCCESS,
        duration_seconds=duration_seconds,
        logs_url="https://github.com/agent-guru/agent-guru/actions",
        metrics_url="https://prometheus.agent-guru.example.com",
        grafana_url=f"https://grafana.agent-guru.example.com/d/deployment-{environment}"
    )

    await service.send_deployment_notification(deployment)


async def send_deployment_failure(
    environment: str,
    version: str,
    commit_sha: str,
    commit_message: str,
    deployer: str,
    duration_seconds: float,
    error_message: str
) -> None:
    """Send deployment failure notification.

    Args:
        environment: Deployment environment
        version: Version attempted
        commit_sha: Git commit SHA
        commit_message: Git commit message
        deployer: Person/system who attempted deployment
        duration_seconds: Time until failure
        error_message: Error details
    """
    service = NotificationService(
        slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL")
    )

    deployment = DeploymentInfo(
        environment=environment,
        version=version,
        commit_sha=commit_sha,
        commit_message=commit_message,
        deployer=deployer,
        timestamp=datetime.now(tz=timezone.utc),
        status=DeploymentStatus.FAILURE,
        duration_seconds=duration_seconds,
        error_message=error_message,
        logs_url="https://github.com/agent-guru/agent-guru/actions",
        metrics_url="https://prometheus.agent-guru.example.com",
        grafana_url=f"https://grafana.agent-guru.example.com/d/deployment-{environment}"
    )

    await service.send_deployment_notification(deployment)


async def send_deployment_rollback(
    environment: str,
    version: str,
    commit_sha: str,
    reason: str
) -> None:
    """Send deployment rollback notification.

    Args:
        environment: Deployment environment
        version: Version rolled back
        commit_sha: Git commit SHA
        reason: Rollback reason
    """
    service = NotificationService(
        slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL")
    )

    deployment = DeploymentInfo(
        environment=environment,
        version=version,
        commit_sha=commit_sha,
        commit_message=f"Rollback reason: {reason}",
        deployer="Automatic Rollback System",
        timestamp=datetime.now(tz=timezone.utc),
        status=DeploymentStatus.ROLLBACK,
        error_message=reason,
        logs_url="https://github.com/agent-guru/agent-guru/actions",
        metrics_url="https://prometheus.agent-guru.example.com",
        grafana_url=f"https://grafana.agent-guru.example.com/d/deployment-{environment}"
    )

    await service.send_deployment_notification(deployment)
