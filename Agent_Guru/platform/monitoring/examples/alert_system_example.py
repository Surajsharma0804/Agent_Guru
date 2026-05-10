"""Example: Resource Monitor Alert System Usage.

This example demonstrates how to use the Resource Monitor's alert system
with Self-Improvement Engine integration.

Features demonstrated:
- Configuring custom alert thresholds
- Registering alert callbacks
- Tracking alert history
- Managing active alerts
- Integrating with Self-Improvement Engine

Author: Agent Guru Team
Date: 2026-02-25
"""

import time
from datetime import UTC, datetime, timedelta

from Agent_Guru.platform.monitoring import (
    AlertSeverity,
    ResourceAlert,
    ResourceLimits,
    ResourceMonitor,
    ResourceMonitorConfig,
    ResourceType,
    SelfImprovementIntegration,
)


def custom_alert_handler(alert: ResourceAlert) -> None:
    """Custom alert handler that logs alerts to console.

    In production, this could:
    - Send notifications to administrators
    - Trigger automatic remediation actions
    - Log to external monitoring systems
    - Update dashboards
    """


def main() -> None:
    """Demonstrate alert system usage."""
    # 1. Configure custom thresholds
    custom_limits = ResourceLimits(
        max_cpu_percent=70.0,  # Alert when CPU > 70%
        max_memory_percent=85.0,  # Alert when memory > 85%
        min_disk_free_bytes=2 * 1024 * 1024 * 1024,  # Alert when < 2GB free
        max_gpu_memory_percent=90.0,  # Alert when GPU memory > 90%
    )

    config = ResourceMonitorConfig(
        sampling_interval=2.0,  # Sample every 2 seconds
        history_size=100,  # Keep last 100 snapshots
        limits=custom_limits,
    )

    monitor = ResourceMonitor(config)

    # 2. Register alert callbacks

    # Register custom handler
    monitor.register_alert_callback(custom_alert_handler)

    # Register Self-Improvement Engine integration
    integration = SelfImprovementIntegration(enable_logging=True)
    monitor.register_alert_callback(integration.on_alert)

    # 3. Start monitoring
    monitor.start_monitoring()

    # 4. Monitor for 10 seconds

    for _i in range(5):
        time.sleep(2)

        # Get current usage
        monitor.get_current_usage()

        # Check for active alerts
        active_alerts = monitor.get_active_alerts()
        if active_alerts:
            pass

    # 5. Query alert history

    # Get all alerts
    monitor.get_alert_history()

    # Get alerts by severity
    monitor.get_alert_history(severity=AlertSeverity.CRITICAL)
    monitor.get_alert_history(severity=AlertSeverity.HIGH)

    # Get alerts by resource type
    monitor.get_alert_history(resource_type=ResourceType.CPU)
    monitor.get_alert_history(resource_type=ResourceType.MEMORY)

    # Get recent alerts (last 5 seconds)
    recent_start = datetime.now(tz=UTC) - timedelta(seconds=5)
    monitor.get_alert_history(start_time=recent_start)

    # 6. Manage active alerts
    active_alerts = monitor.get_active_alerts()

    if active_alerts:
        # Clear first alert
        first_alert = active_alerts[0]
        monitor.clear_alert(first_alert.alert_id)

        monitor.get_active_alerts()

    # 7. Self-Improvement Engine statistics
    integration.get_stats()

    # 8. Update thresholds dynamically
    new_limits = ResourceLimits(
        max_cpu_percent=90.0,  # More lenient
        max_memory_percent=95.0,
    )
    monitor.set_alert_thresholds(new_limits)

    # 9. Stop monitoring
    monitor.stop_monitoring()

    # 10. Final summary

    final_history = monitor.get_alert_history()

    if final_history:
        for severity in AlertSeverity:
            count = len([a for a in final_history if a.severity == severity])
            if count > 0:
                pass

        for resource_type in ResourceType:
            count = len([a for a in final_history if a.resource_type == resource_type])
            if count > 0:
                pass


if __name__ == "__main__":
    main()
