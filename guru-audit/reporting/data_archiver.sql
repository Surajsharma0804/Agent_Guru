-- Data Archiver - Historical Data Management
--
-- Production-grade data archiving system with searchable archives,
-- historical comparison capabilities, and comprehensive data retention.
-- Designed for 20+ year operational lifetime with zero tolerance for data loss.
--
-- MAXIMUM ENGINEERING MANDATE:
-- - Complete data archiving with cryptographic verification
-- - Searchable archives with efficient indexing
-- - Historical comparison with trend analysis
-- - Data retention policies with automated cleanup
-- - Performance requirement: ≤10 seconds per data archive operation

-- ============================================================================
-- AUDIT RESULTS ARCHIVE
-- ============================================================================

CREATE TABLE IF NOT EXISTS audit_results (
    audit_id TEXT PRIMARY KEY,
    audit_timestamp TIMESTAMP NOT NULL,
    repository_name TEXT NOT NULL,
    repository_url TEXT,
    branch TEXT NOT NULL,
    commit_hash TEXT NOT NULL,
    overall_status TEXT NOT NULL CHECK (overall_status IN ('PASSED', 'FAILED', 'PARTIAL')),
    quality_score REAL NOT NULL CHECK (quality_score >= 0 AND quality_score <= 100),
    execution_duration_ms INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_hash TEXT NOT NULL,
    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_results(audit_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_repository_name ON audit_results(repository_name);
CREATE INDEX IF NOT EXISTS idx_overall_status ON audit_results(overall_status);
CREATE INDEX IF NOT EXISTS idx_quality_score ON audit_results(quality_score DESC);

-- ============================================================================
-- PHASE RESULTS ARCHIVE
-- ============================================================================

CREATE TABLE IF NOT EXISTS phase_results (
    phase_result_id TEXT PRIMARY KEY,
    audit_id TEXT NOT NULL,
    phase_id TEXT NOT NULL,
    phase_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('NOT_STARTED', 'IN_PROGRESS', 'COMPLETED', 'FAILED')),
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    execution_duration_ms INTEGER,
    files_processed INTEGER DEFAULT 0,
    errors_encountered INTEGER DEFAULT 0,
    warnings_generated INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (audit_id) REFERENCES audit_results(audit_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_phase_audit_id ON phase_results(audit_id);
CREATE INDEX IF NOT EXISTS idx_phase_status ON phase_results(status);
CREATE INDEX IF NOT EXISTS idx_phase_name ON phase_results(phase_name);

-- ============================================================================
-- QUALITY METRICS ARCHIVE
-- ============================================================================

CREATE TABLE IF NOT EXISTS quality_metrics (
    metric_id TEXT PRIMARY KEY,
    audit_id TEXT NOT NULL,
    compiler_warnings INTEGER NOT NULL DEFAULT 0,
    runtime_errors INTEGER NOT NULL DEFAULT 0,
    unused_files INTEGER NOT NULL DEFAULT 0,
    ambiguous_names INTEGER NOT NULL DEFAULT 0,
    test_pass_rate REAL NOT NULL CHECK (test_pass_rate >= 0 AND test_pass_rate <= 100),
    code_coverage REAL NOT NULL CHECK (code_coverage >= 0 AND code_coverage <= 100),
    property_test_iterations INTEGER NOT NULL DEFAULT 0,
    formal_verification_proofs INTEGER NOT NULL DEFAULT 0,
    security_vulnerabilities INTEGER NOT NULL DEFAULT 0,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (audit_id) REFERENCES audit_results(audit_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_quality_audit_id ON quality_metrics(audit_id);
CREATE INDEX IF NOT EXISTS idx_quality_recorded_at ON quality_metrics(recorded_at DESC);

-- ============================================================================
-- PERFORMANCE METRICS ARCHIVE
-- ============================================================================

CREATE TABLE IF NOT EXISTS performance_metrics (
    metric_id TEXT PRIMARY KEY,
    audit_id TEXT NOT NULL,
    phase_transition_latency_ms REAL,
    dependency_validation_ms REAL,
    audit_trail_generation_ms REAL,
    peak_memory_usage_bytes INTEGER,
    average_memory_usage_bytes INTEGER,
    peak_cpu_utilization REAL CHECK (peak_cpu_utilization >= 0 AND peak_cpu_utilization <= 100),
    average_cpu_utilization REAL CHECK (average_cpu_utilization >= 0 AND average_cpu_utilization <= 100),
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (audit_id) REFERENCES audit_results(audit_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_performance_audit_id ON performance_metrics(audit_id);
CREATE INDEX IF NOT EXISTS idx_performance_recorded_at ON performance_metrics(recorded_at DESC);

-- ============================================================================
-- SECURITY METRICS ARCHIVE
-- ============================================================================

CREATE TABLE IF NOT EXISTS security_metrics (
    metric_id TEXT PRIMARY KEY,
    audit_id TEXT NOT NULL,
    cryptographic_operations INTEGER NOT NULL DEFAULT 0,
    signature_verifications INTEGER NOT NULL DEFAULT 0,
    checksum_validations INTEGER NOT NULL DEFAULT 0,
    security_violations INTEGER NOT NULL DEFAULT 0,
    capability_checks INTEGER NOT NULL DEFAULT 0,
    integrity_attestations INTEGER NOT NULL DEFAULT 0,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (audit_id) REFERENCES audit_results(audit_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_security_audit_id ON security_metrics(audit_id);
CREATE INDEX IF NOT EXISTS idx_security_recorded_at ON security_metrics(recorded_at DESC);

-- ============================================================================
-- COMPLIANCE STATUS ARCHIVE
-- ============================================================================

CREATE TABLE IF NOT EXISTS compliance_status (
    compliance_id TEXT PRIMARY KEY,
    audit_id TEXT NOT NULL,
    clean_room_compliance BOOLEAN NOT NULL DEFAULT FALSE,
    intellectual_property_compliance BOOLEAN NOT NULL DEFAULT FALSE,
    license_compliance BOOLEAN NOT NULL DEFAULT FALSE,
    supply_chain_compliance BOOLEAN NOT NULL DEFAULT FALSE,
    security_compliance BOOLEAN NOT NULL DEFAULT FALSE,
    performance_compliance BOOLEAN NOT NULL DEFAULT FALSE,
    overall_compliance BOOLEAN NOT NULL DEFAULT FALSE,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (audit_id) REFERENCES audit_results(audit_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_compliance_audit_id ON compliance_status(audit_id);
CREATE INDEX IF NOT EXISTS idx_compliance_overall ON compliance_status(overall_compliance);

-- ============================================================================
-- TREND ANALYSIS CACHE
-- ============================================================================

CREATE TABLE IF NOT EXISTS trend_analysis_cache (
    cache_id TEXT PRIMARY KEY,
    metric_name TEXT NOT NULL,
    metric_category TEXT NOT NULL CHECK (metric_category IN ('QUALITY', 'PERFORMANCE', 'SECURITY', 'COMPLIANCE')),
    trend_direction TEXT NOT NULL CHECK (trend_direction IN ('IMPROVING', 'STABLE', 'DECLINING')),
    trend_strength REAL NOT NULL CHECK (trend_strength >= 0 AND trend_strength <= 1),
    current_value REAL NOT NULL,
    historical_average REAL NOT NULL,
    historical_std_dev REAL NOT NULL,
    prediction_next_period REAL,
    confidence_interval_lower REAL,
    confidence_interval_upper REAL,
    statistical_significance REAL,
    data_points_analyzed INTEGER NOT NULL,
    analysis_timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trend_metric_name ON trend_analysis_cache(metric_name);
CREATE INDEX IF NOT EXISTS idx_trend_category ON trend_analysis_cache(metric_category);
CREATE INDEX IF NOT EXISTS idx_trend_analysis_timestamp ON trend_analysis_cache(analysis_timestamp DESC);

-- ============================================================================
-- AUDIT ARTIFACTS ARCHIVE
-- ============================================================================

CREATE TABLE IF NOT EXISTS audit_artifacts (
    artifact_id TEXT PRIMARY KEY,
    audit_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    artifact_name TEXT NOT NULL,
    artifact_path TEXT,
    artifact_size_bytes INTEGER,
    artifact_checksum TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (audit_id) REFERENCES audit_results(audit_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_artifact_audit_id ON audit_artifacts(audit_id);
CREATE INDEX IF NOT EXISTS idx_artifact_type ON audit_artifacts(artifact_type);

-- ============================================================================
-- DATA RETENTION POLICIES
-- ============================================================================

CREATE TABLE IF NOT EXISTS data_retention_policies (
    policy_id TEXT PRIMARY KEY,
    table_name TEXT NOT NULL,
    retention_days INTEGER NOT NULL,
    archive_before_delete BOOLEAN NOT NULL DEFAULT TRUE,
    archive_location TEXT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Default retention policies
INSERT OR IGNORE INTO data_retention_policies (policy_id, table_name, retention_days, archive_before_delete, enabled)
VALUES
    ('policy_audit_results', 'audit_results', 730, TRUE, TRUE),  -- 2 years
    ('policy_phase_results', 'phase_results', 730, TRUE, TRUE),
    ('policy_quality_metrics', 'quality_metrics', 730, TRUE, TRUE),
    ('policy_performance_metrics', 'performance_metrics', 730, TRUE, TRUE),
    ('policy_security_metrics', 'security_metrics', 730, TRUE, TRUE),
    ('policy_compliance_status', 'compliance_status', 730, TRUE, TRUE),
    ('policy_trend_cache', 'trend_analysis_cache', 90, FALSE, TRUE),  -- 90 days for cache
    ('policy_artifacts', 'audit_artifacts', 365, TRUE, TRUE);  -- 1 year

-- ============================================================================
-- VIEWS FOR REPORTING
-- ============================================================================

-- Comprehensive audit summary view
CREATE VIEW IF NOT EXISTS v_audit_summary AS
SELECT
    ar.audit_id,
    ar.audit_timestamp,
    ar.repository_name,
    ar.branch,
    ar.commit_hash,
    ar.overall_status,
    ar.quality_score,
    ar.execution_duration_ms,
    qm.compiler_warnings,
    qm.runtime_errors,
    qm.test_pass_rate,
    qm.code_coverage,
    qm.security_vulnerabilities,
    pm.peak_memory_usage_bytes,
    pm.average_cpu_utilization,
    cs.overall_compliance
FROM audit_results ar
LEFT JOIN quality_metrics qm ON ar.audit_id = qm.audit_id
LEFT JOIN performance_metrics pm ON ar.audit_id = pm.audit_id
LEFT JOIN compliance_status cs ON ar.audit_id = cs.audit_id;

-- Quality trend view
CREATE VIEW IF NOT EXISTS v_quality_trend AS
SELECT
    ar.audit_timestamp,
    ar.repository_name,
    qm.compiler_warnings,
    qm.runtime_errors,
    qm.test_pass_rate,
    qm.code_coverage,
    qm.security_vulnerabilities,
    AVG(qm.test_pass_rate) OVER (
        PARTITION BY ar.repository_name
        ORDER BY ar.audit_timestamp
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS test_pass_rate_7day_avg,
    AVG(qm.code_coverage) OVER (
        PARTITION BY ar.repository_name
        ORDER BY ar.audit_timestamp
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS code_coverage_7day_avg
FROM audit_results ar
JOIN quality_metrics qm ON ar.audit_id = qm.audit_id
ORDER BY ar.audit_timestamp DESC;

-- Performance trend view
CREATE VIEW IF NOT EXISTS v_performance_trend AS
SELECT
    ar.audit_timestamp,
    ar.repository_name,
    ar.execution_duration_ms,
    pm.peak_memory_usage_bytes,
    pm.average_cpu_utilization,
    AVG(ar.execution_duration_ms) OVER (
        PARTITION BY ar.repository_name
        ORDER BY ar.audit_timestamp
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS execution_duration_7day_avg,
    AVG(pm.peak_memory_usage_bytes) OVER (
        PARTITION BY ar.repository_name
        ORDER BY ar.audit_timestamp
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS memory_usage_7day_avg
FROM audit_results ar
JOIN performance_metrics pm ON ar.audit_id = pm.audit_id
ORDER BY ar.audit_timestamp DESC;

-- ============================================================================
-- STORED PROCEDURES (SQLite Functions)
-- ============================================================================

-- Note: SQLite doesn't support stored procedures, but we can create triggers
-- for automated data management

-- Trigger to update updated_at timestamp
CREATE TRIGGER IF NOT EXISTS update_audit_results_timestamp
AFTER UPDATE ON audit_results
FOR EACH ROW
BEGIN
    UPDATE audit_results SET updated_at = CURRENT_TIMESTAMP WHERE audit_id = NEW.audit_id;
END;

-- Trigger to update retention policy timestamp
CREATE TRIGGER IF NOT EXISTS update_retention_policy_timestamp
AFTER UPDATE ON data_retention_policies
FOR EACH ROW
BEGIN
    UPDATE data_retention_policies SET updated_at = CURRENT_TIMESTAMP WHERE policy_id = NEW.policy_id;
END;

-- ============================================================================
-- UTILITY QUERIES
-- ============================================================================

-- Query to find audits older than retention period
-- (To be used by cleanup scripts)
CREATE VIEW IF NOT EXISTS v_audits_for_cleanup AS
SELECT
    ar.audit_id,
    ar.audit_timestamp,
    ar.repository_name,
    drp.retention_days,
    drp.archive_before_delete,
    julianday('now') - julianday(ar.audit_timestamp) AS days_old
FROM audit_results ar
CROSS JOIN data_retention_policies drp
WHERE drp.table_name = 'audit_results'
    AND drp.enabled = TRUE
    AND julianday('now') - julianday(ar.audit_timestamp) > drp.retention_days;

-- Query for historical comparison
CREATE VIEW IF NOT EXISTS v_historical_comparison AS
SELECT
    ar.repository_name,
    COUNT(*) AS total_audits,
    AVG(ar.quality_score) AS avg_quality_score,
    AVG(qm.test_pass_rate) AS avg_test_pass_rate,
    AVG(qm.code_coverage) AS avg_code_coverage,
    SUM(CASE WHEN ar.overall_status = 'PASSED' THEN 1 ELSE 0 END) AS passed_audits,
    SUM(CASE WHEN ar.overall_status = 'FAILED' THEN 1 ELSE 0 END) AS failed_audits,
    MIN(ar.audit_timestamp) AS first_audit,
    MAX(ar.audit_timestamp) AS last_audit
FROM audit_results ar
LEFT JOIN quality_metrics qm ON ar.audit_id = qm.audit_id
GROUP BY ar.repository_name;

-- ============================================================================
-- COMMENTS AND DOCUMENTATION
-- ============================================================================

-- This schema provides comprehensive data archiving for the GURU Production Audit System
-- with the following capabilities:
--
-- 1. Complete audit result storage with cryptographic verification
-- 2. Searchable archives with efficient indexing
-- 3. Historical comparison with trend analysis
-- 4. Data retention policies with automated cleanup
-- 5. Performance-optimized queries for reporting
--
-- Performance Requirements:
-- - Archive operation: ≤10 seconds per operation
-- - Query performance: ≤1 second for most queries
-- - Index maintenance: Automatic with SQLite
--
-- Data Integrity:
-- - Foreign key constraints for referential integrity
-- - Check constraints for data validation
-- - Cryptographic checksums for tamper detection
-- - Timestamps for audit trail
--
-- Scalability:
-- - Designed for millions of audit records
-- - Efficient indexing for fast queries
-- - Partitioning support through retention policies
-- - Archive and purge capabilities for long-term management
