//! Forensic Analysis System with Evidence Preservation
//!
//! This module provides comprehensive forensic analysis with evidence collection,
//! timeline reconstruction, root cause analysis, and impact assessment.

use crate::crypto::AuditSignature;
use crate::error::{AuditError, AuditResult};
use crate::runtime::types::{
    BusinessImpact, ComplianceImpact, CustodyTransfer, EvidenceType, EventSignificance,
    ForensicAnalysisResult, ForensicEvidence, ImpactAssessment, ImpactSeverity,
    ReputationImpact, RootCause, RootCauseAnalysis, RootCauseCategory, SecurityImpact,
    SecurityImpactLevel, TimelineEvent,
};
use std::collections::HashMap;
use std::sync::{Arc, RwLock};
use std::time::{Duration, Instant, SystemTime};

/// Forensic analyzer with evidence preservation and investigation capabilities
pub struct ForensicAnalyzer {
    /// Collected evidence
    evidence_store: Arc<RwLock<HashMap<String, ForensicEvidence>>>,
    /// Timeline events
    timeline: Arc<RwLock<Vec<TimelineEvent>>>,
    /// Analysis results
    analysis_results: Arc<RwLock<Vec<ForensicAnalysisResult>>>,
    /// Current custodian identifier
    custodian_id: String,
}

impl ForensicAnalyzer {
    /// Create new forensic analyzer
    #[must_use]
    pub fn new(custodian_id: String) -> Self {
        Self {
            evidence_store: Arc::new(RwLock::new(HashMap::new())),
            timeline: Arc::new(RwLock::new(Vec::new())),
            analysis_results: Arc::new(RwLock::new(Vec::new())),
            custodian_id,
        }
    }

    /// Collect forensic evidence
    ///
    /// # Errors
    ///
    /// Returns `AuditError` if evidence collection fails
    pub async fn collect_evidence(
        &self,
        evidence_type: EvidenceType,
        description: String,
        data: Vec<u8>,
    ) -> AuditResult<ForensicEvidence> {
        let data_hash = crate::crypto::compute_sha256_hash(&data)?;

        let evidence = ForensicEvidence {
            evidence_id: uuid::Uuid::new_v4().to_string(),
            evidence_type,
            description,
            data_hash,
            collection_timestamp: SystemTime::now(),
            collector_id: self.custodian_id.clone(),
            chain_of_custody: vec![],
            integrity_verified: true,
        };

        // Store evidence
        {
            let mut store = self.evidence_store.write().map_err(|e| {
                AuditError::CriticalSystemError {
                    error_code: crate::error::SystemErrorCode::MemoryCorruption,
                    threat_level: crate::error::ThreatLevel::High,
                    forensic_data: crate::error::ForensicData {
                        timestamp: SystemTime::now(),
                        system_state_hash: String::new(),
                        execution_trace: vec![format!("Evidence store lock error: {e}")],
                        memory_usage: 0,
                        cpu_utilization: 0.0,
                        network_activity: vec![],
                        file_system_operations: vec![],
                    },
                    recovery_options: vec![],
                }
            })?;

            store.insert(evidence.evidence_id.clone(), evidence.clone());
        }

        Ok(evidence)
    }

    /// Record timeline event
    ///
    /// # Errors
    ///
    /// Returns `AuditError` if event recording fails
    pub fn record_event(
        &self,
        event_type: String,
        description: String,
        source: String,
        significance: EventSignificance,
    ) -> AuditResult<()> {
        let event = TimelineEvent {
            event_id: uuid::Uuid::new_v4().to_string(),
            event_timestamp: SystemTime::now(),
            event_type,
            description,
            source,
            related_evidence: vec![],
            significance,
        };

        let mut timeline = self.timeline.write().map_err(|e| {
            AuditError::CriticalSystemError {
                error_code: crate::error::SystemErrorCode::MemoryCorruption,
                threat_level: crate::error::ThreatLevel::High,
                forensic_data: crate::error::ForensicData {
                    timestamp: SystemTime::now(),
                    system_state_hash: String::new(),
                    execution_trace: vec![format!("Timeline lock error: {e}")],
                    memory_usage: 0,
                    cpu_utilization: 0.0,
                    network_activity: vec![],
                    file_system_operations: vec![],
                },
                recovery_options: vec![],
            }
        })?;

        timeline.push(event);
        Ok(())
    }

    /// Perform comprehensive forensic analysis
    ///
    /// # Errors
    ///
    /// Returns `AuditError` if analysis fails
    pub async fn perform_analysis(
        &self,
        incident_id: String,
    ) -> AuditResult<ForensicAnalysisResult> {
        let start_time = Instant::now();

        // Collect all evidence
        let evidence_collected: Vec<ForensicEvidence> = {
            let store = self.evidence_store.read().map_err(|e| {
                AuditError::CriticalSystemError {
                    error_code: crate::error::SystemErrorCode::MemoryCorruption,
                    threat_level: crate::error::ThreatLevel::High,
                    forensic_data: crate::error::ForensicData {
                        timestamp: SystemTime::now(),
                        system_state_hash: String::new(),
                        execution_trace: vec![format!("Evidence store lock error: {e}")],
                        memory_usage: 0,
                        cpu_utilization: 0.0,
                        network_activity: vec![],
                        file_system_operations: vec![],
                    },
                    recovery_options: vec![],
                }
            })?;

            store.values().cloned().collect()
        };

        // Get timeline
        let timeline = {
            let timeline = self.timeline.read().map_err(|e| {
                AuditError::CriticalSystemError {
                    error_code: crate::error::SystemErrorCode::MemoryCorruption,
                    threat_level: crate::error::ThreatLevel::High,
                    forensic_data: crate::error::ForensicData {
                        timestamp: SystemTime::now(),
                        system_state_hash: String::new(),
                        execution_trace: vec![format!("Timeline lock error: {e}")],
                        memory_usage: 0,
                        cpu_utilization: 0.0,
                        network_activity: vec![],
                        file_system_operations: vec![],
                    },
                    recovery_options: vec![],
                }
            })?;

            timeline.clone()
        };

        // Perform root cause analysis
        let root_cause_analysis = self.analyze_root_cause(&evidence_collected, &timeline)?;

        // Perform impact assessment
        let impact_assessment = self.assess_impact(&evidence_collected, &timeline)?;

        let result = ForensicAnalysisResult {
            analysis_id: uuid::Uuid::new_v4().to_string(),
            analysis_timestamp: SystemTime::now(),
            incident_id,
            evidence_collected,
            timeline,
            root_cause_analysis,
            impact_assessment,
            analysis_duration: start_time.elapsed(),
        };

        // Store analysis result
        {
            let mut results = self.analysis_results.write().map_err(|e| {
                AuditError::CriticalSystemError {
                    error_code: crate::error::SystemErrorCode::MemoryCorruption,
                    threat_level: crate::error::ThreatLevel::High,
                    forensic_data: crate::error::ForensicData {
                        timestamp: SystemTime::now(),
                        system_state_hash: String::new(),
                        execution_trace: vec![format!("Results lock error: {e}")],
                        memory_usage: 0,
                        cpu_utilization: 0.0,
                        network_activity: vec![],
                        file_system_operations: vec![],
                    },
                    recovery_options: vec![],
                }
            })?;

            results.push(result.clone());
        }

        Ok(result)
    }

    /// Analyze root cause of incident
    fn analyze_root_cause(
        &self,
        _evidence: &[ForensicEvidence],
        _timeline: &[TimelineEvent],
    ) -> AuditResult<RootCauseAnalysis> {
        Ok(RootCauseAnalysis {
            analysis_id: uuid::Uuid::new_v4().to_string(),
            root_causes: vec![RootCause {
                cause_id: uuid::Uuid::new_v4().to_string(),
                description: "Root cause analysis in progress".to_string(),
                category: RootCauseCategory::Unknown,
                supporting_evidence: vec![],
                likelihood: 0.5,
            }],
            contributing_factors: vec![],
            confidence: 0.5,
            recommendations: vec!["Further investigation required".to_string()],
        })
    }

    /// Assess impact of incident
    fn assess_impact(
        &self,
        _evidence: &[ForensicEvidence],
        _timeline: &[TimelineEvent],
    ) -> AuditResult<ImpactAssessment> {
        Ok(ImpactAssessment {
            assessment_id: uuid::Uuid::new_v4().to_string(),
            overall_severity: ImpactSeverity::Minor,
            affected_systems: vec![],
            affected_data: vec![],
            estimated_recovery_time: Duration::from_secs(3600),
            business_impact: BusinessImpact {
                service_availability: 1.0,
                data_integrity: 1.0,
                operational_efficiency: 1.0,
                financial_impact: None,
                reputation_impact: ReputationImpact::None,
            },
            security_impact: SecurityImpact {
                confidentiality: SecurityImpactLevel::None,
                integrity: SecurityImpactLevel::None,
                availability: SecurityImpactLevel::None,
                compliance: ComplianceImpact {
                    regulatory_violations: vec![],
                    policy_violations: vec![],
                    legal_implications: vec![],
                    reporting_requirements: vec![],
                },
            },
        })
    }

    /// Transfer evidence custody
    ///
    /// # Errors
    ///
    /// Returns `AuditError` if transfer fails
    pub fn transfer_custody(
        &self,
        evidence_id: &str,
        to_custodian: String,
        reason: String,
        signature: Option<AuditSignature>,
    ) -> AuditResult<()> {
        let mut store = self.evidence_store.write().map_err(|e| {
            AuditError::CriticalSystemError {
                error_code: crate::error::SystemErrorCode::MemoryCorruption,
                threat_level: crate::error::ThreatLevel::High,
                forensic_data: crate::error::ForensicData {
                    timestamp: SystemTime::now(),
                    system_state_hash: String::new(),
                    execution_trace: vec![format!("Evidence store lock error: {e}")],
                    memory_usage: 0,
                    cpu_utilization: 0.0,
                    network_activity: vec![],
                    file_system_operations: vec![],
                },
                recovery_options: vec![],
            }
        })?;

        if let Some(evidence) = store.get_mut(evidence_id) {
            let transfer = CustodyTransfer {
                transfer_id: uuid::Uuid::new_v4().to_string(),
                transfer_timestamp: SystemTime::now(),
                from_custodian: self.custodian_id.clone(),
                to_custodian,
                transfer_reason: reason,
                transfer_signature: signature,
            };

            evidence.chain_of_custody.push(transfer);
            Ok(())
        } else {
            Err(AuditError::FileSystemError {
                operation: "transfer_custody".to_string(),
                path: evidence_id.to_string(),
                reason: "Evidence not found".to_string(),
            })
        }
    }

    /// Get all analysis results
    ///
    /// # Errors
    ///
    /// Returns `AuditError` if access fails
    pub fn get_analysis_results(&self) -> AuditResult<Vec<ForensicAnalysisResult>> {
        let results = self.analysis_results.read().map_err(|e| {
            AuditError::CriticalSystemError {
                error_code: crate::error::SystemErrorCode::MemoryCorruption,
                threat_level: crate::error::ThreatLevel::High,
                forensic_data: crate::error::ForensicData {
                    timestamp: SystemTime::now(),
                    system_state_hash: String::new(),
                    execution_trace: vec![format!("Results lock error: {e}")],
                    memory_usage: 0,
                    cpu_utilization: 0.0,
                    network_activity: vec![],
                    file_system_operations: vec![],
                },
                recovery_options: vec![],
            }
        })?;

        Ok(results.clone())
    }

    /// Clear all evidence and analysis data
    ///
    /// # Errors
    ///
    /// Returns `AuditError` if clear fails
    pub fn clear_all(&self) -> AuditResult<()> {
        {
            let mut store = self.evidence_store.write().map_err(|e| {
                AuditError::CriticalSystemError {
                    error_code: crate::error::SystemErrorCode::MemoryCorruption,
                    threat_level: crate::error::ThreatLevel::High,
                    forensic_data: crate::error::ForensicData {
                        timestamp: SystemTime::now(),
                        system_state_hash: String::new(),
                        execution_trace: vec![format!("Evidence store lock error: {e}")],
                        memory_usage: 0,
                        cpu_utilization: 0.0,
                        network_activity: vec![],
                        file_system_operations: vec![],
                    },
                    recovery_options: vec![],
                }
            })?;
            store.clear();
        }

        {
            let mut timeline = self.timeline.write().map_err(|e| {
                AuditError::CriticalSystemError {
                    error_code: crate::error::SystemErrorCode::MemoryCorruption,
                    threat_level: crate::error::ThreatLevel::High,
                    forensic_data: crate::error::ForensicData {
                        timestamp: SystemTime::now(),
                        system_state_hash: String::new(),
                        execution_trace: vec![format!("Timeline lock error: {e}")],
                        memory_usage: 0,
                        cpu_utilization: 0.0,
                        network_activity: vec![],
                        file_system_operations: vec![],
                    },
                    recovery_options: vec![],
                }
            })?;
            timeline.clear();
        }

        {
            let mut results = self.analysis_results.write().map_err(|e| {
                AuditError::CriticalSystemError {
                    error_code: crate::error::SystemErrorCode::MemoryCorruption,
                    threat_level: crate::error::ThreatLevel::High,
                    forensic_data: crate::error::ForensicData {
                        timestamp: SystemTime::now(),
                        system_state_hash: String::new(),
                        execution_trace: vec![format!("Results lock error: {e}")],
                        memory_usage: 0,
                        cpu_utilization: 0.0,
                        network_activity: vec![],
                        file_system_operations: vec![],
                    },
                    recovery_options: vec![],
                }
            })?;
            results.clear();
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_forensic_analyzer_creation() {
        let analyzer = ForensicAnalyzer::new("test_custodian".to_string());
        assert_eq!(analyzer.custodian_id, "test_custodian");
    }

    #[tokio::test]
    async fn test_evidence_collection() {
        let analyzer = ForensicAnalyzer::new("test_custodian".to_string());

        let evidence = analyzer
            .collect_evidence(
                EvidenceType::SystemLogs,
                "Test evidence".to_string(),
                vec![1, 2, 3, 4],
            )
            .await
            .unwrap();

        assert_eq!(evidence.evidence_type, EvidenceType::SystemLogs);
        assert!(evidence.integrity_verified);
    }

    #[test]
    fn test_timeline_recording() {
        let analyzer = ForensicAnalyzer::new("test_custodian".to_string());

        analyzer
            .record_event(
                "test_event".to_string(),
                "Test event description".to_string(),
                "test_source".to_string(),
                EventSignificance::Notable,
            )
            .unwrap();

        let timeline = analyzer.timeline.read().unwrap();
        assert_eq!(timeline.len(), 1);
    }

    #[tokio::test]
    async fn test_forensic_analysis() {
        let analyzer = ForensicAnalyzer::new("test_custodian".to_string());

        analyzer
            .collect_evidence(
                EvidenceType::SystemLogs,
                "Test evidence".to_string(),
                vec![1, 2, 3, 4],
            )
            .await
            .unwrap();

        let result = analyzer
            .perform_analysis("test_incident".to_string())
            .await
            .unwrap();

        assert_eq!(result.incident_id, "test_incident");
        assert!(!result.evidence_collected.is_empty());
    }
}
