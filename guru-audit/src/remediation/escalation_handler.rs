//! Manual Intervention Coordination and Escalation Handler
//!
//! This module provides comprehensive escalation capabilities for issues that
//! cannot be automatically remediated or require manual review. The escalation
//! handler coordinates with human operators, provides detailed context, and
//! tracks the resolution of escalated issues.
//!
//! ## Escalation Capabilities
//!
//! - Intelligent escalation routing based on issue type and severity
//! - Comprehensive context provision for manual intervention
//! - Priority-based escalation queuing
//! - Resolution tracking and feedback collection
//! - Automated notification and alerting
//!
//! ## Escalation Criteria
//!
//! - Security vulnerabilities requiring expert review
//! - High-risk modifications with potential system impact
//! - Complex issues without known remediation patterns
//! - Verification failures requiring investigation
//! - Policy violations requiring approval

use crate::error::AuditError;
use crate::remediation::types::{DetectedIssue, EscalationRequest, IssueSeverity};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;

/// Comprehensive escalation and manual intervention handler
pub struct EscalationHandler {
    escalation_queue: Arc<RwLock<Vec<EscalationRequest>>>,
    escalation_history: Arc<RwLock<Vec<EscalationRecord>>>,
    notification_config: NotificationConfig,
    statistics: Arc<RwLock<EscalationStatistics>>,
}

/// Configuration for escalation notifications
#[derive(Debug, Clone)]
pub struct NotificationConfig {
    pub enable_email_notifications: bool,
    pub enable_slack_notifications: bool,
    pub enable_webhook_notifications: bool,
    pub critical_issue_immediate_notification: bool,
    pub notification_batch_interval_seconds: u64,
}

impl Default for NotificationConfig {
    fn default() -> Self {
        Self {
            enable_email_notifications: true,
            enable_slack_notifications: false,
            enable_webhook_notifications: false,
            critical_issue_immediate_notification: true,
            notification_batch_interval_seconds: 300,
        }
    }
}

/// Record of an escalation operation
#[derive(Debug, Clone)]
pub struct EscalationRecord {
    pub escalation_id: String,
    pub issue_id: String,
    pub escalation_reason: EscalationReason,
    pub priority: EscalationPriority,
    pub status: EscalationStatus,
    pub assigned_to: Option<String>,
    pub resolution: Option<String>,
    pub created_at: std::time::SystemTime,
    pub resolved_at: Option<std::time::SystemTime>,
}

/// Reason for escalation
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum EscalationReason {
    SecurityVulnerability,
    HighRiskModification,
    ComplexIssue,
    VerificationFailure,
    PolicyViolation,
    UnknownIssueType,
    ManualReviewRequired,
}

/// Priority level for escalation
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub enum EscalationPriority {
    Critical,
    High,
    Medium,
    Low,
}

/// Status of escalation
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum EscalationStatus {
    Pending,
    InProgress,
    Resolved,
    Cancelled,
}

/// Statistics for escalation operations
#[derive(Debug, Clone, Default)]
pub struct EscalationStatistics {
    pub total_escalations: u64,
    pub pending_escalations: u64,
    pub resolved_escalations: u64,
    pub cancelled_escalations: u64,
    pub average_resolution_time_hours: f64,
    pub escalations_by_reason: HashMap<String, u64>,
    pub escalations_by_priority: HashMap<String, u64>,
}

impl EscalationHandler {
    /// Create a new escalation handler with the specified configuration
    pub fn new(notification_config: NotificationConfig) -> Self {
        Self {
            escalation_queue: Arc::new(RwLock::new(Vec::new())),
            escalation_history: Arc::new(RwLock::new(Vec::new())),
            notification_config,
            statistics: Arc::new(RwLock::new(EscalationStatistics::default())),
        }
    }

    /// Escalate an issue for manual intervention
    pub async fn escalate_issue(
        &self,
        issue: &DetectedIssue,
        reason: EscalationReason,
        context: String,
    ) -> Result<EscalationRequest, AuditError> {
        let escalation_id = format!("ESC_{}", uuid::Uuid::new_v4());
        let priority = self.determine_priority(issue, &reason);

        let request = EscalationRequest {
            escalation_id: escalation_id.clone(),
            issue_id: issue.issue_id.clone(),
            issue_type: issue.issue_type.clone(),
            severity: issue.severity.clone(),
            escalation_reason: reason.clone(),
            priority: priority.clone(),
            context,
            file_path: issue.file_path.clone(),
            line_number: issue.line_number,
            suggested_actions: self.generate_suggested_actions(issue, &reason),
            created_at: std::time::SystemTime::now(),
        };

        // Add to escalation queue
        {
            let mut queue = self.escalation_queue.write().await;
            queue.push(request.clone());
            // Sort by priority
            queue.sort_by(|a, b| a.priority.cmp(&b.priority));
        }

        // Create escalation record
        let record = EscalationRecord {
            escalation_id: escalation_id.clone(),
            issue_id: issue.issue_id.clone(),
            escalation_reason: reason.clone(),
            priority: priority.clone(),
            status: EscalationStatus::Pending,
            assigned_to: None,
            resolution: None,
            created_at: std::time::SystemTime::now(),
            resolved_at: None,
        };

        {
            let mut history = self.escalation_history.write().await;
            history.push(record);
        }

        // Update statistics
        {
            let mut stats = self.statistics.write().await;
            stats.total_escalations += 1;
            stats.pending_escalations += 1;
            *stats.escalations_by_reason.entry(format!("{:?}", reason)).or_insert(0) += 1;
            *stats.escalations_by_priority.entry(format!("{:?}", priority)).or_insert(0) += 1;
        }

        // Send notifications if configured
        if self.should_send_immediate_notification(&priority) {
            self.send_notification(&request).await?;
        }

        Ok(request)
    }

    /// Determine escalation priority based on issue and reason
    fn determine_priority(&self, issue: &DetectedIssue, reason: &EscalationReason) -> EscalationPriority {
        match reason {
            EscalationReason::SecurityVulnerability => EscalationPriority::Critical,
            EscalationReason::HighRiskModification => EscalationPriority::High,
            EscalationReason::PolicyViolation => EscalationPriority::High,
            _ => match issue.severity {
                IssueSeverity::Critical => EscalationPriority::Critical,
                IssueSeverity::High => EscalationPriority::High,
                IssueSeverity::Medium => EscalationPriority::Medium,
                IssueSeverity::Low => EscalationPriority::Low,
            },
        }
    }

    /// Generate suggested actions for manual intervention
    fn generate_suggested_actions(&self, issue: &DetectedIssue, reason: &EscalationReason) -> Vec<String> {
        let mut actions = Vec::new();

        match reason {
            EscalationReason::SecurityVulnerability => {
                actions.push("Review security implications with security team".to_string());
                actions.push("Check for known CVEs and patches".to_string());
                actions.push("Assess impact on system security posture".to_string());
            }
            EscalationReason::HighRiskModification => {
                actions.push("Review proposed changes carefully".to_string());
                actions.push("Run comprehensive test suite".to_string());
                actions.push("Create backup before applying changes".to_string());
            }
            EscalationReason::VerificationFailure => {
                actions.push("Investigate verification failure root cause".to_string());
                actions.push("Review test results and logs".to_string());
                actions.push("Consider alternative remediation approach".to_string());
            }
            _ => {
                actions.push("Review issue details and context".to_string());
                actions.push("Determine appropriate remediation strategy".to_string());
                actions.push("Document resolution for future reference".to_string());
            }
        }

        if let Some(suggested_fix) = &issue.suggested_fix {
            actions.push(format!("Consider suggested fix: {}", suggested_fix));
        }

        actions
    }

    /// Check if immediate notification should be sent
    fn should_send_immediate_notification(&self, priority: &EscalationPriority) -> bool {
        self.notification_config.critical_issue_immediate_notification 
            && matches!(priority, EscalationPriority::Critical)
    }

    /// Send notification for escalation
    async fn send_notification(&self, request: &EscalationRequest) -> Result<(), AuditError> {
        // In production, this would send actual notifications via configured channels
        // For now, we'll just log the notification
        println!("ESCALATION NOTIFICATION: {:?}", request.escalation_id);
        Ok(())
    }

    /// Get next escalation from queue
    pub async fn get_next_escalation(&self) -> Option<EscalationRequest> {
        let mut queue = self.escalation_queue.write().await;
        queue.pop()
    }

    /// Resolve an escalation
    pub async fn resolve_escalation(
        &self,
        escalation_id: &str,
        resolution: String,
        assigned_to: Option<String>,
    ) -> Result<(), AuditError> {
        // Update escalation record
        {
            let mut history = self.escalation_history.write().await;
            if let Some(record) = history.iter_mut().find(|r| r.escalation_id == escalation_id) {
                record.status = EscalationStatus::Resolved;
                record.resolution = Some(resolution);
                record.assigned_to = assigned_to;
                record.resolved_at = Some(std::time::SystemTime::now());
            } else {
                return Err(AuditError::NotFound(format!("Escalation not found: {}", escalation_id)));
            }
        }

        // Update statistics
        {
            let mut stats = self.statistics.write().await;
            stats.pending_escalations = stats.pending_escalations.saturating_sub(1);
            stats.resolved_escalations += 1;
        }

        Ok(())
    }

    /// Cancel an escalation
    pub async fn cancel_escalation(&self, escalation_id: &str, reason: String) -> Result<(), AuditError> {
        // Update escalation record
        {
            let mut history = self.escalation_history.write().await;
            if let Some(record) = history.iter_mut().find(|r| r.escalation_id == escalation_id) {
                record.status = EscalationStatus::Cancelled;
                record.resolution = Some(reason);
                record.resolved_at = Some(std::time::SystemTime::now());
            } else {
                return Err(AuditError::NotFound(format!("Escalation not found: {}", escalation_id)));
            }
        }

        // Update statistics
        {
            let mut stats = self.statistics.write().await;
            stats.pending_escalations = stats.pending_escalations.saturating_sub(1);
            stats.cancelled_escalations += 1;
        }

        Ok(())
    }

    /// Get all pending escalations
    pub async fn get_pending_escalations(&self) -> Vec<EscalationRequest> {
        self.escalation_queue.read().await.clone()
    }

    /// Get escalation history
    pub async fn get_history(&self) -> Vec<EscalationRecord> {
        self.escalation_history.read().await.clone()
    }

    /// Get escalation statistics
    pub async fn get_statistics(&self) -> EscalationStatistics {
        self.statistics.read().await.clone()
    }

    /// Get escalations by priority
    pub async fn get_escalations_by_priority(&self, priority: EscalationPriority) -> Vec<EscalationRequest> {
        let queue = self.escalation_queue.read().await;
        queue.iter()
            .filter(|req| req.priority == priority)
            .cloned()
            .collect()
    }

    /// Get escalations by reason
    pub async fn get_escalations_by_reason(&self, reason: EscalationReason) -> Vec<EscalationRequest> {
        let queue = self.escalation_queue.read().await;
        queue.iter()
            .filter(|req| req.escalation_reason == reason)
            .cloned()
            .collect()
    }
}

impl Default for EscalationHandler {
    fn default() -> Self {
        Self::new(NotificationConfig::default())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::remediation::types::IssueType;
    use std::path::PathBuf;

    #[tokio::test]
    async fn test_escalation_handler_creation() {
        let handler = EscalationHandler::default();
        let stats = handler.get_statistics().await;
        assert_eq!(stats.total_escalations, 0);
    }

    #[tokio::test]
    async fn test_escalation_priority_determination() {
        let handler = EscalationHandler::default();
        let issue = DetectedIssue {
            issue_id: "TEST_001".to_string(),
            issue_type: IssueType::SecurityVulnerability,
            severity: IssueSeverity::Critical,
            file_path: PathBuf::from("test.rs"),
            line_number: Some(42),
            column_number: None,
            description: "Test issue".to_string(),
            auto_fixable: false,
            suggested_fix: None,
            detected_at: std::time::SystemTime::now(),
        };

        let priority = handler.determine_priority(&issue, &EscalationReason::SecurityVulnerability);
        assert_eq!(priority, EscalationPriority::Critical);
    }

    #[tokio::test]
    async fn test_escalation_queue_ordering() {
        let handler = EscalationHandler::default();
        
        let low_issue = DetectedIssue {
            issue_id: "LOW_001".to_string(),
            issue_type: IssueType::FormattingIssue,
            severity: IssueSeverity::Low,
            file_path: PathBuf::from("test.rs"),
            line_number: Some(1),
            column_number: None,
            description: "Low priority issue".to_string(),
            auto_fixable: true,
            suggested_fix: None,
            detected_at: std::time::SystemTime::now(),
        };

        let critical_issue = DetectedIssue {
            issue_id: "CRIT_001".to_string(),
            issue_type: IssueType::SecurityVulnerability,
            severity: IssueSeverity::Critical,
            file_path: PathBuf::from("test.rs"),
            line_number: Some(42),
            column_number: None,
            description: "Critical issue".to_string(),
            auto_fixable: false,
            suggested_fix: None,
            detected_at: std::time::SystemTime::now(),
        };

        handler.escalate_issue(&low_issue, EscalationReason::ComplexIssue, "Test".to_string()).await.unwrap();
        handler.escalate_issue(&critical_issue, EscalationReason::SecurityVulnerability, "Test".to_string()).await.unwrap();

        let next = handler.get_next_escalation().await.unwrap();
        assert_eq!(next.priority, EscalationPriority::Critical);
    }
}
