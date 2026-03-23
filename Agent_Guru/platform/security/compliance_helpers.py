"""
Module: agent_guru.platform.security.compliance_helpers
Purpose: Helper methods for compliance reporting

This module contains helper methods for:
- SIEM-specific export formats
- Data analysis for compliance reports
- Report serialization

Author: Agent Guru Team
Date: 2026-02-25
Version: 1.0.0
"""

import socket
from datetime import datetime
from typing import Any

import structlog

from Agent_Guru.platform.security.auditor import AuditLogEntry

logger = structlog.get_logger(__name__)


def export_to_splunk(
    entries: list[AuditLogEntry],
    endpoint_url: str,
    auth_token: str,
    batch_size: int = 1000,
) -> dict[str, Any]:
    """
    Export to Splunk HTTP Event Collector (HEC).

    Args:
        entries: Audit log entries to export
        endpoint_url: Splunk HEC endpoint URL
        auth_token: Splunk HEC token
        batch_size: Number of entries per batch

    Returns:
        Export statistics
    """
    import requests

    exported_count = 0
    failed_count = 0

    # Prepare headers
    headers = {
        "Authorization": f"Splunk {auth_token}",
        "Content-Type": "application/json",
    }

    # Export in batches
    for i in range(0, len(entries), batch_size):
        batch = entries[i : i + batch_size]

        # Format for Splunk HEC
        events = []
        for entry in batch:
            event = {
                "time": datetime.fromisoformat(entry.timestamp.replace("Z", "")).timestamp(),
                "host": socket.gethostname(),
                "source": "agent_guru_audit",
                "sourcetype": "agent_guru:audit",
                "event": {
                    "entry_id": entry.entry_id,
                    "operation_type": entry.operation_type.value,
                    "user_id": entry.user_id,
                    "result_status": entry.result_status.value,
                    "execution_time": entry.execution_time,
                    "parameters": entry.parameters,
                    "error_message": entry.error_message,
                },
            }
            events.append(event)

        # Send batch to Splunk
        try:
            response = requests.post(
                endpoint_url,
                headers=headers,
                json=events,
                timeout=30,
            )
            response.raise_for_status()
            exported_count += len(batch)
        except Exception as e:
            logger.error("splunk_export_failed", error=str(e), batch_size=len(batch))
            failed_count += len(batch)

    return {
        "entries_exported": exported_count,
        "entries_failed": failed_count,
        "total_entries": len(entries),
    }
