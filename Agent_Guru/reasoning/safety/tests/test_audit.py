"""Tests for audit logging."""

import json
import time


from Agent_Guru.reasoning.models.action import ActionSensitivity
from Agent_Guru.reasoning.safety.audit import AuditLogEntry, AuditLogger


class TestAuditLogEntry:
    """Tests for AuditLogEntry."""

    def test_entry_creation(self):
        """Test creating audit log entry."""
        entry = AuditLogEntry(
            entry_id=1,
            timestamp=time.time(),
            user_id="user123",
            tool_id="delete_file",
            parameters={"path": "/file.txt"},
            sensitivity="dangerous",
            decision="blocked",
            requires_confirmation=True,
            reason="Dangerous operation",
            validation_time=0.001,
            metadata={"test": "value"},
        )

        assert entry.entry_id == 1  # nosec B101
        assert entry.user_id == "user123"  # nosec B101
        assert entry.tool_id == "delete_file"  # nosec B101
        assert entry.decision == "blocked"  # nosec B101

    def test_entry_to_dict(self):
        """Test converting entry to dictionary."""
        entry = AuditLogEntry(
            entry_id=1,
            timestamp=123.456,
            user_id="user123",
            tool_id="test_tool",
            parameters={"key": "value"},
            sensitivity="safe",
            decision="allowed",
            requires_confirmation=False,
            reason="Safe operation",
            validation_time=0.001,
            metadata={},
        )

        data = entry.to_dict()

        assert data["entry_id"] == 1  # nosec B101
        assert data["timestamp"] == 123.456  # nosec B101
        assert data["user_id"] == "user123"  # nosec B101
        assert data["tool_id"] == "test_tool"  # nosec B101
        assert data["parameters"] == {"key": "value"}  # nosec B101
        assert data["decision"] == "allowed"  # nosec B101


class TestAuditLogger:
    """Tests for AuditLogger."""

    def test_logger_initialization(self):
        """Test logger initialization."""
        logger = AuditLogger()

        assert logger._retention_days == 90  # nosec B101
        assert logger._conn is not None  # nosec B101

        logger.close()

    def test_logger_with_custom_retention(self):
        """Test logger with custom retention period."""
        logger = AuditLogger(retention_days=180)

        assert logger._retention_days == 180  # nosec B101

        logger.close()

    def test_logger_minimum_retention(self):
        """Test logger enforces minimum retention."""
        logger = AuditLogger(retention_days=30)

        # Should be enforced to minimum 90 days
        assert logger._retention_days == 90  # nosec B101

        logger.close()

    def test_logger_with_file_database(self, tmp_path):
        """Test logger with file database."""
        db_path = tmp_path / "audit.db"
        logger = AuditLogger(db_path=str(db_path))

        assert db_path.exists()  # nosec B101

        logger.close()

    def test_log_decision(self):
        """Test logging a decision."""
        logger = AuditLogger()

        entry_id = logger.log_decision(
            user_id="user123",
            tool_id="delete_file",
            parameters={"path": "/file.txt"},
            sensitivity=ActionSensitivity.DANGEROUS,
            decision="blocked",
            requires_confirmation=True,
            reason="Dangerous operation",
            validation_time=0.001,
        )

        assert entry_id > 0  # nosec B101

        logger.close()

    def test_log_decision_with_metadata(self):
        """Test logging decision with metadata."""
        logger = AuditLogger()

        metadata = {"source": "test", "version": "1.0"}
        entry_id = logger.log_decision(
            user_id="user123",
            tool_id="test_tool",
            parameters={},
            sensitivity=ActionSensitivity.SAFE,
            decision="allowed",
            requires_confirmation=False,
            reason="Safe operation",
            validation_time=0.001,
            metadata=metadata,
        )

        assert entry_id > 0  # nosec B101

        logger.close()

    def test_query_logs_all(self):
        """Test querying all logs."""
        logger = AuditLogger()

        # Log multiple decisions
        logger.log_decision(
            user_id="user1",
            tool_id="tool1",
            parameters={},
            sensitivity=ActionSensitivity.SAFE,
            decision="allowed",
            requires_confirmation=False,
            reason="Test 1",
            validation_time=0.001,
        )
        logger.log_decision(
            user_id="user2",
            tool_id="tool2",
            parameters={},
            sensitivity=ActionSensitivity.SENSITIVE,
            decision="confirmed",
            requires_confirmation=True,
            reason="Test 2",
            validation_time=0.002,
        )

        entries = logger.query_logs()

        assert len(entries) == 2  # nosec B101
        assert entries[0].user_id in ["user1", "user2"]  # nosec B101
        assert entries[1].user_id in ["user1", "user2"]  # nosec B101

        logger.close()

    def test_query_logs_by_user(self):
        """Test querying logs by user."""
        logger = AuditLogger()

        # Log decisions for different users
        logger.log_decision(
            user_id="user1",
            tool_id="tool1",
            parameters={},
            sensitivity=ActionSensitivity.SAFE,
            decision="allowed",
            requires_confirmation=False,
            reason="Test 1",
            validation_time=0.001,
        )
        logger.log_decision(
            user_id="user2",
            tool_id="tool2",
            parameters={},
            sensitivity=ActionSensitivity.SAFE,
            decision="allowed",
            requires_confirmation=False,
            reason="Test 2",
            validation_time=0.001,
        )

        entries = logger.query_logs(user_id="user1")

        assert len(entries) == 1  # nosec B101
        assert entries[0].user_id == "user1"  # nosec B101

        logger.close()

    def test_query_logs_by_tool(self):
        """Test querying logs by tool."""
        logger = AuditLogger()

        # Log decisions for different tools
        logger.log_decision(
            user_id="user1",
            tool_id="tool1",
            parameters={},
            sensitivity=ActionSensitivity.SAFE,
            decision="allowed",
            requires_confirmation=False,
            reason="Test 1",
            validation_time=0.001,
        )
        logger.log_decision(
            user_id="user1",
            tool_id="tool2",
            parameters={},
            sensitivity=ActionSensitivity.SAFE,
            decision="allowed",
            requires_confirmation=False,
            reason="Test 2",
            validation_time=0.001,
        )

        entries = logger.query_logs(tool_id="tool1")

        assert len(entries) == 1  # nosec B101
        assert entries[0].tool_id == "tool1"  # nosec B101

        logger.close()

    def test_query_logs_by_decision(self):
        """Test querying logs by decision."""
        logger = AuditLogger()

        # Log different decisions
        logger.log_decision(
            user_id="user1",
            tool_id="tool1",
            parameters={},
            sensitivity=ActionSensitivity.SAFE,
            decision="allowed",
            requires_confirmation=False,
            reason="Test 1",
            validation_time=0.001,
        )
        logger.log_decision(
            user_id="user1",
            tool_id="tool2",
            parameters={},
            sensitivity=ActionSensitivity.DANGEROUS,
            decision="blocked",
            requires_confirmation=False,
            reason="Test 2",
            validation_time=0.001,
        )

        entries = logger.query_logs(decision="blocked")

        assert len(entries) == 1  # nosec B101
        assert entries[0].decision == "blocked"  # nosec B101

        logger.close()

    def test_query_logs_by_time_range(self):
        """Test querying logs by time range."""
        logger = AuditLogger()

        # Log decision at specific time
        start_time = time.time()

        logger.log_decision(
            user_id="user1",
            tool_id="tool1",
            parameters={},
            sensitivity=ActionSensitivity.SAFE,
            decision="allowed",
            requires_confirmation=False,
            reason="Test 1",
            validation_time=0.001,
        )

        time.sleep(0.02)  # Increased sleep time

        mid_time = time.time()

        logger.log_decision(
            user_id="user1",
            tool_id="tool2",
            parameters={},
            sensitivity=ActionSensitivity.SAFE,
            decision="allowed",
            requires_confirmation=False,
            reason="Test 2",
            validation_time=0.001,
        )

        time.time()

        # Query first entry only
        entries = logger.query_logs(start_time=start_time, end_time=mid_time)

        assert len(entries) >= 1  # At least the first entry  # nosec B101
        assert entries[-1].tool_id == "tool1"  # Last entry (oldest) should be tool1  # nosec B101

        logger.close()

    def test_query_logs_with_limit(self):
        """Test querying logs with limit."""
        logger = AuditLogger()

        # Log multiple decisions
        for i in range(10):
            logger.log_decision(
                user_id=f"user{i}",
                tool_id=f"tool{i}",
                parameters={},
                sensitivity=ActionSensitivity.SAFE,
                decision="allowed",
                requires_confirmation=False,
                reason=f"Test {i}",
                validation_time=0.001,
            )

        entries = logger.query_logs(limit=5)

        assert len(entries) == 5  # nosec B101

        logger.close()

    def test_parameters_encrypted(self):
        """Test that parameters are encrypted in database."""
        logger = AuditLogger()

        sensitive_params = {"password": "secret123", "api_key": "key456"}  # nosec B105

        logger.log_decision(
            user_id="user1",
            tool_id="tool1",
            parameters=sensitive_params,
            sensitivity=ActionSensitivity.SAFE,
            decision="allowed",
            requires_confirmation=False,
            reason="Test",
            validation_time=0.001,
        )

        # Query directly from database
        cursor = logger._conn.cursor()
        cursor.execute("SELECT parameters_encrypted FROM audit_log")
        encrypted_data = cursor.fetchone()[0]

        # Should be encrypted (not plain text)
        assert b"secret123" not in encrypted_data  # nosec B101
        assert b"key456" not in encrypted_data  # nosec B101

        # But should decrypt correctly
        entries = logger.query_logs()
        assert entries[0].parameters == sensitive_params  # nosec B101

        logger.close()

    def test_get_statistics(self):
        """Test getting audit statistics."""
        logger = AuditLogger()

        # Log various decisions
        logger.log_decision(
            user_id="user1",
            tool_id="tool1",
            parameters={},
            sensitivity=ActionSensitivity.SAFE,
            decision="allowed",
            requires_confirmation=False,
            reason="Test 1",
            validation_time=0.001,
        )
        logger.log_decision(
            user_id="user1",
            tool_id="tool2",
            parameters={},
            sensitivity=ActionSensitivity.DANGEROUS,
            decision="blocked",
            requires_confirmation=False,
            reason="Test 2",
            validation_time=0.002,
        )
        logger.log_decision(
            user_id="user1",
            tool_id="tool3",
            parameters={},
            sensitivity=ActionSensitivity.SENSITIVE,
            decision="confirmed",
            requires_confirmation=True,
            reason="Test 3",
            validation_time=0.003,
        )

        stats = logger.get_statistics()

        assert stats["total_count"] == 3  # nosec B101
        assert stats["decision_counts"]["allowed"] == 1  # nosec B101
        assert stats["decision_counts"]["blocked"] == 1  # nosec B101
        assert stats["decision_counts"]["confirmed"] == 1  # nosec B101
        assert stats["sensitivity_counts"]["safe"] == 1  # nosec B101
        assert stats["sensitivity_counts"]["dangerous"] == 1  # nosec B101
        assert stats["sensitivity_counts"]["sensitive"] == 1  # nosec B101
        assert stats["average_validation_time"] > 0  # nosec B101

        logger.close()

    def test_get_statistics_by_user(self):
        """Test getting statistics for specific user."""
        logger = AuditLogger()

        # Log decisions for different users
        logger.log_decision(
            user_id="user1",
            tool_id="tool1",
            parameters={},
            sensitivity=ActionSensitivity.SAFE,
            decision="allowed",
            requires_confirmation=False,
            reason="Test 1",
            validation_time=0.001,
        )
        logger.log_decision(
            user_id="user2",
            tool_id="tool2",
            parameters={},
            sensitivity=ActionSensitivity.SAFE,
            decision="allowed",
            requires_confirmation=False,
            reason="Test 2",
            validation_time=0.001,
        )

        stats = logger.get_statistics(user_id="user1")

        assert stats["total_count"] == 1  # nosec B101

        logger.close()

    def test_apply_retention_policy(self):
        """Test applying retention policy."""
        logger = AuditLogger(retention_days=90)

        # Log old decision (manually set timestamp)
        cursor = logger._conn.cursor()
        old_timestamp = time.time() - (100 * 24 * 60 * 60)  # 100 days ago

        cursor.execute("""
            INSERT INTO audit_log 
            (timestamp, user_id, tool_id, parameters_encrypted, sensitivity, 
             decision, requires_confirmation, reason, validation_time, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            old_timestamp,
            "user1",
            "tool1",
            logger._cipher.encrypt(b'{}'),
            "safe",
            "allowed",
            0,
            "Old entry",
            0.001,
            None,
        ))
        logger._conn.commit()

        # Log recent decision
        logger.log_decision(
            user_id="user2",
            tool_id="tool2",
            parameters={},
            sensitivity=ActionSensitivity.SAFE,
            decision="allowed",
            requires_confirmation=False,
            reason="Recent entry",
            validation_time=0.001,
        )

        # Apply retention policy
        deleted_count = logger.apply_retention_policy()

        assert deleted_count == 1  # nosec B101

        # Only recent entry should remain
        entries = logger.query_logs()
        assert len(entries) == 1  # nosec B101
        assert entries[0].user_id == "user2"  # nosec B101

        logger.close()

    def test_export_logs(self, tmp_path):
        """Test exporting logs to JSON."""
        logger = AuditLogger()

        # Log some decisions
        logger.log_decision(
            user_id="user1",
            tool_id="tool1",
            parameters={"key": "value"},
            sensitivity=ActionSensitivity.SAFE,
            decision="allowed",
            requires_confirmation=False,
            reason="Test 1",
            validation_time=0.001,
        )
        logger.log_decision(
            user_id="user2",
            tool_id="tool2",
            parameters={},
            sensitivity=ActionSensitivity.SENSITIVE,
            decision="confirmed",
            requires_confirmation=True,
            reason="Test 2",
            validation_time=0.002,
        )

        # Export logs
        output_path = tmp_path / "audit_export.json"
        count = logger.export_logs(str(output_path))

        assert count == 2  # nosec B101
        assert output_path.exists()  # nosec B101

        # Verify exported data
        with open(output_path) as f:
            data = json.load(f)

        assert len(data) == 2  # nosec B101
        assert data[0]["user_id"] in ["user1", "user2"]  # nosec B101

        logger.close()

    def test_export_logs_filtered(self, tmp_path):
        """Test exporting filtered logs."""
        logger = AuditLogger()

        # Log decisions for different users
        logger.log_decision(
            user_id="user1",
            tool_id="tool1",
            parameters={},
            sensitivity=ActionSensitivity.SAFE,
            decision="allowed",
            requires_confirmation=False,
            reason="Test 1",
            validation_time=0.001,
        )
        logger.log_decision(
            user_id="user2",
            tool_id="tool2",
            parameters={},
            sensitivity=ActionSensitivity.SAFE,
            decision="allowed",
            requires_confirmation=False,
            reason="Test 2",
            validation_time=0.001,
        )

        # Export only user1's logs
        output_path = tmp_path / "audit_export_user1.json"
        count = logger.export_logs(str(output_path), user_id="user1")

        assert count == 1  # nosec B101

        # Verify exported data
        with open(output_path) as f:
            data = json.load(f)

        assert len(data) == 1  # nosec B101
        assert data[0]["user_id"] == "user1"  # nosec B101

        logger.close()

    def test_persistence(self, tmp_path):
        """Test that logs persist across logger instances."""
        db_path = tmp_path / "audit.db"

        # Create first logger and log decision
        logger1 = AuditLogger(db_path=str(db_path))
        logger1.log_decision(
            user_id="user1",
            tool_id="tool1",
            parameters={"test": "data"},
            sensitivity=ActionSensitivity.SAFE,
            decision="allowed",
            requires_confirmation=False,
            reason="Test",
            validation_time=0.001,
        )
        encryption_key = logger1.get_encryption_key()
        logger1.close()

        # Create second logger with same key and verify data
        logger2 = AuditLogger(db_path=str(db_path), encryption_key=encryption_key)
        entries = logger2.query_logs()

        assert len(entries) == 1  # nosec B101
        assert entries[0].user_id == "user1"  # nosec B101
        assert entries[0].parameters == {"test": "data"}  # nosec B101

        logger2.close()

    def test_close(self):
        """Test closing logger."""
        logger = AuditLogger()

        logger.log_decision(
            user_id="user1",
            tool_id="tool1",
            parameters={},
            sensitivity=ActionSensitivity.SAFE,
            decision="allowed",
            requires_confirmation=False,
            reason="Test",
            validation_time=0.001,
        )

        logger.close()

        # Should not raise error
        assert True  # nosec B101
