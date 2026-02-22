"""
Automated Rollback Monitor for Agent Guru Reasoning Engine

This module monitors production deployments and automatically triggers rollbacks
when health checks fail, error rates spike, or latency degrades beyond thresholds.

Performance Requirements:
- Monitoring interval: 30 seconds
- Rollback decision: <5 seconds
- Rollback execution: <60 seconds

Author: Agent Guru Team
Date: 2026-02-22
"""

import asyncio
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

import aiohttp
import structlog

logger = structlog.get_logger(__name__)


class RollbackReason(Enum):
    """Reasons for triggering automatic rollback."""
    HEALTH_CHECK_FAILURE = "health_check_failure"
    ERROR_RATE_SPIKE = "error_rate_spike"
    LATENCY_DEGRADATION = "latency_degradation"
    MANUAL_TRIGGER = "manual_trigger"


@dataclass
class DeploymentMetrics:
    """Metrics for a deployment."""
    timestamp: datetime
    error_rate: float  # Percentage (0-100)
    p95_latency: float  # Milliseconds
    p99_latency: float  # Milliseconds
    request_count: int
    health_check_status: bool


@dataclass
class RollbackConfig:
    """Configuration for rollback automation."""
    # Health check settings
    health_check_url: str
    health_check_interval: int = 30  # seconds
    health_check_failures_threshold: int = 3  # consecutive failures
    
    # Error rate settings
    error_rate_threshold: float = 5.0  # percentage
    error_rate_window: int = 300  # seconds (5 minutes)
    
    # Latency settings
    latency_baseline_p95: float = 1500.0  # milliseconds
    latency_degradation_multiplier: float = 2.0  # 2x baseline
    latency_window: int = 300  # seconds (5 minutes)
    
    # Kubernetes settings
    namespace: str = "agent-guru-production"
    service_name: str = "agent-guru-reasoning"
    
    # Prometheus settings
    prometheus_url: str = "http://prometheus:9090"
    
    # Notification settings
    slack_webhook_url: Optional[str] = None


class RollbackMonitor:
    """
    Monitors deployment health and triggers automatic rollbacks.
    
    Time Complexity: O(1) per monitoring cycle
    Space Complexity: O(n) where n is metrics history size
    """
    
    def __init__(self, config: RollbackConfig):
        """Initialize rollback monitor.
        
        Args:
            config: Rollback configuration
        """
        self.config = config
        self.metrics_history: List[DeploymentMetrics] = []
        self.consecutive_health_failures = 0
        self.is_monitoring = False
        self.current_color: Optional[str] = None
        
        logger.info(
            "rollback_monitor_initialized",
            namespace=config.namespace,
            service=config.service_name
        )
    
    async def start_monitoring(self) -> None:
        """Start continuous monitoring of deployment."""
        self.is_monitoring = True
        logger.info("rollback_monitoring_started")
        
        try:
            while self.is_monitoring:
                await self._monitoring_cycle()
                await asyncio.sleep(self.config.health_check_interval)
        except Exception as e:
            logger.error("monitoring_error", error=str(e))
            raise
    
    def stop_monitoring(self) -> None:
        """Stop monitoring."""
        self.is_monitoring = False
        logger.info("rollback_monitoring_stopped")
    
    async def _monitoring_cycle(self) -> None:
        """Execute one monitoring cycle."""
        try:
            # Get current deployment color
            self.current_color = await self._get_current_deployment_color()
            
            # Collect metrics
            metrics = await self._collect_metrics()
            self.metrics_history.append(metrics)
            
            # Prune old metrics (keep last hour)
            cutoff_time = datetime.now() - timedelta(hours=1)
            self.metrics_history = [
                m for m in self.metrics_history
                if m.timestamp > cutoff_time
            ]
            
            # Check for rollback conditions
            rollback_reason = await self._check_rollback_conditions(metrics)
            
            if rollback_reason:
                logger.warning(
                    "rollback_triggered",
                    reason=rollback_reason.value,
                    current_color=self.current_color
                )
                await self._execute_rollback(rollback_reason)
            else:
                logger.debug(
                    "monitoring_cycle_complete",
                    error_rate=metrics.error_rate,
                    p95_latency=metrics.p95_latency,
                    health_status=metrics.health_check_status
                )
        
        except Exception as e:
            logger.error("monitoring_cycle_error", error=str(e))
    
    async def _collect_metrics(self) -> DeploymentMetrics:
        """Collect current deployment metrics.
        
        Returns:
            Current deployment metrics
        """
        async with aiohttp.ClientSession() as session:
            # Health check
            health_status = await self._check_health(session)
            
            # Query Prometheus for metrics
            error_rate = await self._query_error_rate(session)
            p95_latency = await self._query_p95_latency(session)
            p99_latency = await self._query_p99_latency(session)
            request_count = await self._query_request_count(session)
        
        return DeploymentMetrics(
            timestamp=datetime.now(),
            error_rate=error_rate,
            p95_latency=p95_latency,
            p99_latency=p99_latency,
            request_count=request_count,
            health_check_status=health_status
        )
    
    async def _check_health(self, session: aiohttp.ClientSession) -> bool:
        """Check health endpoint.
        
        Args:
            session: HTTP session
            
        Returns:
            True if healthy, False otherwise
        """
        try:
            async with session.get(
                self.config.health_check_url,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                return response.status == 200
        except Exception as e:
            logger.warning("health_check_failed", error=str(e))
            return False
    
    async def _query_error_rate(self, session: aiohttp.ClientSession) -> float:
        """Query error rate from Prometheus.
        
        Args:
            session: HTTP session
            
        Returns:
            Error rate percentage
        """
        query = (
            f'sum(rate(reasoning_engine_errors_total{{namespace="{self.config.namespace}"}}[5m])) / '
            f'sum(rate(reasoning_engine_requests_total{{namespace="{self.config.namespace}"}}[5m])) * 100'
        )
        
        try:
            async with session.get(
                f"{self.config.prometheus_url}/api/v1/query",
                params={"query": query},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                data = await response.json()
                if data["status"] == "success" and data["data"]["result"]:
                    return float(data["data"]["result"][0]["value"][1])
                return 0.0
        except Exception as e:
            logger.warning("error_rate_query_failed", error=str(e))
            return 0.0
    
    async def _query_p95_latency(self, session: aiohttp.ClientSession) -> float:
        """Query P95 latency from Prometheus.
        
        Args:
            session: HTTP session
            
        Returns:
            P95 latency in milliseconds
        """
        query = (
            f'histogram_quantile(0.95, sum(rate(reasoning_engine_latency_seconds_bucket{{namespace="{self.config.namespace}"}}[5m])) by (le)) * 1000'
        )
        
        try:
            async with session.get(
                f"{self.config.prometheus_url}/api/v1/query",
                params={"query": query},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                data = await response.json()
                if data["status"] == "success" and data["data"]["result"]:
                    return float(data["data"]["result"][0]["value"][1])
                return 0.0
        except Exception as e:
            logger.warning("p95_latency_query_failed", error=str(e))
            return 0.0
    
    async def _query_p99_latency(self, session: aiohttp.ClientSession) -> float:
        """Query P99 latency from Prometheus.
        
        Args:
            session: HTTP session
            
        Returns:
            P99 latency in milliseconds
        """
        query = (
            f'histogram_quantile(0.99, sum(rate(reasoning_engine_latency_seconds_bucket{{namespace="{self.config.namespace}"}}[5m])) by (le)) * 1000'
        )
        
        try:
            async with session.get(
                f"{self.config.prometheus_url}/api/v1/query",
                params={"query": query},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                data = await response.json()
                if data["status"] == "success" and data["data"]["result"]:
                    return float(data["data"]["result"][0]["value"][1])
                return 0.0
        except Exception as e:
            logger.warning("p99_latency_query_failed", error=str(e))
            return 0.0
    
    async def _query_request_count(self, session: aiohttp.ClientSession) -> int:
        """Query request count from Prometheus.
        
        Args:
            session: HTTP session
            
        Returns:
            Request count in last 5 minutes
        """
        query = (
            f'sum(increase(reasoning_engine_requests_total{{namespace="{self.config.namespace}"}}[5m]))'
        )
        
        try:
            async with session.get(
                f"{self.config.prometheus_url}/api/v1/query",
                params={"query": query},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                data = await response.json()
                if data["status"] == "success" and data["data"]["result"]:
                    return int(float(data["data"]["result"][0]["value"][1]))
                return 0
        except Exception as e:
            logger.warning("request_count_query_failed", error=str(e))
            return 0
    
    async def _check_rollback_conditions(
        self,
        current_metrics: DeploymentMetrics
    ) -> Optional[RollbackReason]:
        """Check if rollback conditions are met.
        
        Args:
            current_metrics: Current deployment metrics
            
        Returns:
            Rollback reason if conditions met, None otherwise
        """
        # Check health failures
        if not current_metrics.health_check_status:
            self.consecutive_health_failures += 1
            if self.consecutive_health_failures >= self.config.health_check_failures_threshold:
                return RollbackReason.HEALTH_CHECK_FAILURE
        else:
            self.consecutive_health_failures = 0
        
        # Check error rate spike
        if current_metrics.error_rate > self.config.error_rate_threshold:
            logger.warning(
                "error_rate_threshold_exceeded",
                current=current_metrics.error_rate,
                threshold=self.config.error_rate_threshold
            )
            return RollbackReason.ERROR_RATE_SPIKE
        
        # Check latency degradation
        latency_threshold = (
            self.config.latency_baseline_p95 *
            self.config.latency_degradation_multiplier
        )
        if current_metrics.p95_latency > latency_threshold:
            logger.warning(
                "latency_threshold_exceeded",
                current=current_metrics.p95_latency,
                threshold=latency_threshold
            )
            return RollbackReason.LATENCY_DEGRADATION
        
        return None
    
    async def _get_current_deployment_color(self) -> str:
        """Get current active deployment color.
        
        Returns:
            Current deployment color (blue or green)
        """
        try:
            result = subprocess.run(
                [
                    "kubectl", "get", "service", self.config.service_name,
                    "-n", self.config.namespace,
                    "-o", "jsonpath={.spec.selector.color}"
                ],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip() or "blue"
        except subprocess.CalledProcessError as e:
            logger.error("failed_to_get_deployment_color", error=str(e))
            return "blue"
    
    async def _execute_rollback(self, reason: RollbackReason) -> None:
        """Execute automatic rollback.
        
        Args:
            reason: Reason for rollback
        """
        start_time = time.time()
        
        logger.critical(
            "executing_automatic_rollback",
            reason=reason.value,
            current_color=self.current_color
        )
        
        # Determine target color (opposite of current)
        target_color = "blue" if self.current_color == "green" else "green"
        
        try:
            # Send notification before rollback
            await self._send_notification(
                f"🚨 AUTOMATIC ROLLBACK INITIATED\n"
                f"Reason: {reason.value}\n"
                f"Rolling back from {self.current_color} to {target_color}"
            )
            
            # Scale up target deployment
            subprocess.run(
                [
                    "kubectl", "scale", f"deployment/agent-guru-reasoning-{target_color}",
                    "-n", self.config.namespace,
                    "--replicas=3"
                ],
                check=True
            )
            
            # Wait for target deployment to be ready
            subprocess.run(
                [
                    "kubectl", "rollout", "status",
                    f"deployment/agent-guru-reasoning-{target_color}",
                    "-n", self.config.namespace,
                    "--timeout=60s"
                ],
                check=True
            )
            
            # Switch service to target color
            subprocess.run(
                [
                    "kubectl", "patch", "service", self.config.service_name,
                    "-n", self.config.namespace,
                    "-p", f'{{"spec":{{"selector":{{"color":"{target_color}"}}}}}}'
                ],
                check=True
            )
            
            # Scale down failed deployment
            subprocess.run(
                [
                    "kubectl", "scale", f"deployment/agent-guru-reasoning-{self.current_color}",
                    "-n", self.config.namespace,
                    "--replicas=0"
                ],
                check=True
            )
            
            elapsed_time = time.time() - start_time
            
            logger.info(
                "rollback_completed",
                reason=reason.value,
                from_color=self.current_color,
                to_color=target_color,
                elapsed_seconds=elapsed_time
            )
            
            # Send success notification
            await self._send_notification(
                f"✅ ROLLBACK COMPLETED\n"
                f"Rolled back from {self.current_color} to {target_color}\n"
                f"Time: {elapsed_time:.1f}s\n"
                f"Reason: {reason.value}"
            )
            
            # Update current color
            self.current_color = target_color
            
            # Reset failure counters
            self.consecutive_health_failures = 0
        
        except subprocess.CalledProcessError as e:
            logger.error("rollback_failed", error=str(e))
            await self._send_notification(
                f"❌ ROLLBACK FAILED\n"
                f"Error: {str(e)}\n"
                f"Manual intervention required!"
            )
            raise
    
    async def _send_notification(self, message: str) -> None:
        """Send notification to Slack.
        
        Args:
            message: Notification message
        """
        if not self.config.slack_webhook_url:
            logger.debug("slack_webhook_not_configured")
            return
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.config.slack_webhook_url,
                    json={"text": message},
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        logger.debug("notification_sent")
                    else:
                        logger.warning(
                            "notification_failed",
                            status=response.status
                        )
        except Exception as e:
            logger.warning("notification_error", error=str(e))
    
    async def manual_rollback(self) -> None:
        """Trigger manual rollback."""
        logger.info("manual_rollback_triggered")
        await self._execute_rollback(RollbackReason.MANUAL_TRIGGER)


async def main():
    """Main entry point for rollback monitor."""
    # Load configuration from environment
    config = RollbackConfig(
        health_check_url=os.getenv(
            "HEALTH_CHECK_URL",
            "https://agent-guru.example.com/health"
        ),
        prometheus_url=os.getenv(
            "PROMETHEUS_URL",
            "http://prometheus:9090"
        ),
        slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL"),
        namespace=os.getenv("KUBERNETES_NAMESPACE", "agent-guru-production"),
        service_name=os.getenv("SERVICE_NAME", "agent-guru-reasoning")
    )
    
    # Create and start monitor
    monitor = RollbackMonitor(config)
    
    try:
        await monitor.start_monitoring()
    except KeyboardInterrupt:
        logger.info("shutting_down")
        monitor.stop_monitoring()


if __name__ == "__main__":
    asyncio.run(main())
