"""
Example: Resource Monitor Alert System Usage

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
from datetime import datetime, timedelta

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
    """
    Custom alert handler that logs alerts to console.

    In production, this could:
    - Send notifications to administrators
    - Trigger automatic remediation actions
    - Log to external monitoring systems
    - Update dashboards
    """
    print(f"\n🚨 ALERT: {alert.severity.value.upper()}")
    print(f"   Resource: {alert.resource_type.value}")
    print(f"   Message: {alert.message}")
    print(f"   Current: {alert.current_value:.1f}")
    print(f"   Threshold: {alert.threshold_value:.1f}")
    print(f"   Action: {alert.recommended_action}")
    print(f"   Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")


def main():
    """Demonstrate alert system usage."""

    print("=" * 70)
    print("Resource Monitor Alert System Example")
    print("=" * 70)

    # 1. Configure custom thresholds
    print("\n1. Configuring custom alert thresholds...")
    custom_limits = ResourceLimits(
        max_cpu_percent=70.0,      # Alert when CPU > 70%
        max_memory_percent=85.0,   # Alert when memory > 85%
        min_disk_free_bytes=2 * 1024 * 1024 * 1024,  # Alert when < 2GB free
        max_gpu_memory_percent=90.0  # Alert when GPU memory > 90%
    )

    config = ResourceMonitorConfig(
        sampling_interval=2.0,  # Sample every 2 seconds
        history_size=100,       # Keep last 100 snapshots
        limits=custom_limits
    )

    monitor = ResourceMonitor(config)
    print(f"   ✓ CPU threshold: {custom_limits.max_cpu_percent}%")
    print(f"   ✓ Memory threshold: {custom_limits.max_memory_percent}%")
    print(f"   ✓ Disk free minimum: {custom_limits.min_disk_free_bytes / (1024**3):.1f} GB")

    # 2. Register alert callbacks
    print("\n2. Registering alert callbacks...")

    # Register custom handler
    monitor.register_alert_callback(custom_alert_handler)
    print("   ✓ Custom alert handler registered")

    # Register Self-Improvement Engine integration
    integration = SelfImprovementIntegration(enable_logging=True)
    monitor.register_alert_callback(integration.on_alert)
    print("   ✓ Self-Improvement Engine integration registered")

    # 3. Start monitoring
    print("\n3. Starting resource monitoring...")
    monitor.start_monitoring()
    print("   ✓ Monitoring started (sampling every 2 seconds)")

    # 4. Monitor for 10 seconds
    print("\n4. Monitoring resources for 10 seconds...")
    print("   (Alerts will be triggered if thresholds are exceeded)")

    for i in range(5):
        time.sleep(2)

        # Get current usage
        snapshot = monitor.get_current_usage()
        print(f"\n   Snapshot {i+1}:")
        print(f"      CPU: {snapshot.cpu_percent:.1f}%")
        print(f"      Memory: {snapshot.memory_percent:.1f}%")
        print(f"      Processes: {snapshot.process_count}")

        # Check for active alerts
        active_alerts = monitor.get_active_alerts()
        if active_alerts:
            print(f"      Active alerts: {len(active_alerts)}")

    # 5. Query alert history
    print("\n5. Querying alert history...")

    # Get all alerts
    all_alerts = monitor.get_alert_history()
    print(f"   Total alerts: {len(all_alerts)}")

    # Get alerts by severity
    critical_alerts = monitor.get_alert_history(severity=AlertSeverity.CRITICAL)
    high_alerts = monitor.get_alert_history(severity=AlertSeverity.HIGH)
    print(f"   Critical alerts: {len(critical_alerts)}")
    print(f"   High alerts: {len(high_alerts)}")

    # Get alerts by resource type
    cpu_alerts = monitor.get_alert_history(resource_type=ResourceType.CPU)
    memory_alerts = monitor.get_alert_history(resource_type=ResourceType.MEMORY)
    print(f"   CPU alerts: {len(cpu_alerts)}")
    print(f"   Memory alerts: {len(memory_alerts)}")

    # Get recent alerts (last 5 seconds)
    recent_start = datetime.now() - timedelta(seconds=5)
    recent_alerts = monitor.get_alert_history(start_time=recent_start)
    print(f"   Recent alerts (last 5s): {len(recent_alerts)}")

    # 6. Manage active alerts
    print("\n6. Managing active alerts...")
    active_alerts = monitor.get_active_alerts()
    print(f"   Active alerts: {len(active_alerts)}")

    if active_alerts:
        # Clear first alert
        first_alert = active_alerts[0]
        print(f"   Clearing alert: {first_alert.alert_id}")
        monitor.clear_alert(first_alert.alert_id)

        remaining = monitor.get_active_alerts()
        print(f"   Remaining active alerts: {len(remaining)}")

    # 7. Self-Improvement Engine statistics
    print("\n7. Self-Improvement Engine integration statistics...")
    stats = integration.get_stats()
    print(f"   Notifications sent: {stats['notifications_sent']}")
    print(f"   Errors: {stats['errors']}")

    # 8. Update thresholds dynamically
    print("\n8. Updating thresholds dynamically...")
    new_limits = ResourceLimits(
        max_cpu_percent=90.0,  # More lenient
        max_memory_percent=95.0
    )
    monitor.set_alert_thresholds(new_limits)
    print(f"   ✓ CPU threshold updated to {new_limits.max_cpu_percent}%")
    print(f"   ✓ Memory threshold updated to {new_limits.max_memory_percent}%")

    # 9. Stop monitoring
    print("\n9. Stopping monitoring...")
    monitor.stop_monitoring()
    print("   ✓ Monitoring stopped")

    # 10. Final summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)

    final_history = monitor.get_alert_history()
    print(f"Total alerts triggered: {len(final_history)}")

    if final_history:
        print("\nAlert breakdown by severity:")
        for severity in AlertSeverity:
            count = len([a for a in final_history if a.severity == severity])
            if count > 0:
                print(f"  {severity.value.upper()}: {count}")

        print("\nAlert breakdown by resource:")
        for resource_type in ResourceType:
            count = len([a for a in final_history if a.resource_type == resource_type])
            if count > 0:
                print(f"  {resource_type.value.upper()}: {count}")

    print("\n✅ Example completed successfully!")


if __name__ == "__main__":
    main()
