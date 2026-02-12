//! # Biometric Authentication Module
//!
//! Production-grade multi-modal biometric authentication system supporting
//! face recognition, voice authentication, and fingerprint verification.
//!
//! ## Security Features
//!
//! - Multi-modal biometric fusion
//! - Liveness detection and anti-spoofing
//! - Homomorphic encryption for templates
//! - Zero biometric data transmission
//! - Formal verification of authentication logic

pub mod face;
pub mod voice;
pub mod fingerprint;

use std::collections::HashMap;
use std::time::SystemTime;

use serde::{Deserialize, Serialize};
use thiserror::Error;
use uuid::Uuid;

/// Biometric authentication errors
#[derive(Error, Debug, Clone, PartialEq, Eq)]
pub enum BiometricError {
    /// Enrollment failed
    #[error("Enrollment failed: {reason}")]
    EnrollmentFailed { reason: String },
    
    /// Authentication failed
    #[error("Authentication failed: {reason}")]
    AuthenticationFailed { reason: String },
    
    /// Liveness detection failed
    #[error("Liveness detection failed: {reason}")]
    LivenessDetectionFailed { reason: String },
    
    /// Spoofing attempt detected
    #[error("Spoofing attempt detected: {reason}")]
    SpoofingDetected { reason: String },
    
    /// Invalid biometric data
    #[error("Invalid biometric data: {reason}")]
    InvalidData { reason: String },
    
    /// Template storage error
    #[error("Template storage error: {reason}")]
    StorageError { reason: String },
    
    /// Encryption error
    #[error("Encryption error: {reason}")]
    EncryptionError { reason: String },
}

/// Biometric modality types
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum BiometricType {
    /// Facial recognition
    Face,
    /// Voice authentication
    Voice,
    /// Fingerprint recognition
    Fingerprint,
}

/// Encrypted biometric template
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BiometricTemplate {
    /// Template identifier
    pub template_id: Uuid,
    /// Biometric modality type
    pub biometric_type: BiometricType,
    /// Encrypted template data
    pub encrypted_data: Vec<u8>,
    /// Encryption key identifier
    pub encryption_key_id: Uuid,
    /// Template quality score (0.0 to 1.0)
    pub quality_score: f32,
    /// Creation timestamp
    pub created_at: SystemTime,
    /// Template metadata
    pub metadata: HashMap<String, String>,
}

impl BiometricTemplate {
    /// Create a new biometric template
    pub fn new(
        biometric_type: BiometricType,
        encrypted_data: Vec<u8>,
        encryption_key_id: Uuid,
        quality_score: f32,
    ) -> Self {
        Self {
            template_id: Uuid::new_v4(),
            biometric_type,
            encrypted_data,
            encryption_key_id,
            quality_score,
            created_at: SystemTime::now(),
            metadata: HashMap::new(),
        }
    }
    
    /// Add metadata to the template
    pub fn with_metadata(mut self, key: String, value: String) -> Self {
        self.metadata.insert(key, value);
        self
    }
}

/// Biometric authentication result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthenticationResult {
    /// Whether authentication succeeded
    pub success: bool,
    /// User ID if authentication succeeded
    pub user_id: Option<Uuid>,
    /// Confidence score (0.0 to 1.0)
    pub confidence: f32,
    /// Biometric modalities used
    pub modalities_used: Vec<BiometricType>,
    /// Authentication timestamp
    pub timestamp: SystemTime,
    /// Additional metadata
    pub metadata: HashMap<String, String>,
}

impl AuthenticationResult {
    /// Create a successful authentication result
    pub fn success(user_id: Uuid, confidence: f32, modalities: Vec<BiometricType>) -> Self {
        Self {
            success: true,
            user_id: Some(user_id),
            confidence,
            modalities_used: modalities,
            timestamp: SystemTime::now(),
            metadata: HashMap::new(),
        }
    }
    
    /// Create a failed authentication result
    pub fn failure(modalities: Vec<BiometricType>) -> Self {
        Self {
            success: false,
            user_id: None,
            confidence: 0.0,
            modalities_used: modalities,
            timestamp: SystemTime::now(),
            metadata: HashMap::new(),
        }
    }
}

/// Biometric enrollment result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EnrollmentResult {
    /// Whether enrollment succeeded
    pub success: bool,
    /// Template ID if enrollment succeeded
    pub template_id: Option<Uuid>,
    /// Quality score of enrolled template
    pub quality_score: f32,
    /// Enrollment timestamp
    pub timestamp: SystemTime,
    /// Additional metadata
    pub metadata: HashMap<String, String>,
}

impl EnrollmentResult {
    /// Create a successful enrollment result
    pub fn success(template_id: Uuid, quality_score: f32) -> Self {
        Self {
            success: true,
            template_id: Some(template_id),
            quality_score,
            timestamp: SystemTime::now(),
            metadata: HashMap::new(),
        }
    }
    
    /// Create a failed enrollment result
    pub fn failure() -> Self {
        Self {
            success: false,
            template_id: None,
            quality_score: 0.0,
            timestamp: SystemTime::now(),
            metadata: HashMap::new(),
        }
    }
}

/// Raw biometric data for processing
#[derive(Debug, Clone)]
pub struct BiometricData {
    /// Face image data (if available)
    pub face_image: Option<Vec<u8>>,
    /// Voice audio data (if available)
    pub voice_sample: Option<Vec<f32>>,
    /// Fingerprint image data (if available)
    pub fingerprint_image: Option<Vec<u8>>,
    /// Capture timestamp
    pub timestamp: SystemTime,
    /// Data quality indicators
    pub quality_indicators: HashMap<BiometricType, f32>,
}

impl BiometricData {
    /// Create new biometric data
    pub fn new() -> Self {
        Self {
            face_image: None,
            voice_sample: None,
            fingerprint_image: None,
            timestamp: SystemTime::now(),
            quality_indicators: HashMap::new(),
        }
    }
    
    /// Add face image data
    pub fn with_face_image(mut self, image_data: Vec<u8>, quality: f32) -> Self {
        self.face_image = Some(image_data);
        self.quality_indicators.insert(BiometricType::Face, quality);
        self
    }
    
    /// Add voice sample data
    pub fn with_voice_sample(mut self, audio_data: Vec<f32>, quality: f32) -> Self {
        self.voice_sample = Some(audio_data);
        self.quality_indicators.insert(BiometricType::Voice, quality);
        self
    }
    
    /// Add fingerprint image data
    pub fn with_fingerprint_image(mut self, image_data: Vec<u8>, quality: f32) -> Self {
        self.fingerprint_image = Some(image_data);
        self.quality_indicators.insert(BiometricType::Fingerprint, quality);
        self
    }
}

impl Default for BiometricData {
    fn default() -> Self {
        Self::new()
    }
}

/// Biometric authenticator trait
pub trait BiometricAuthenticator {
    /// Enroll a user with biometric data
    fn enroll_user(
        &mut self,
        user_id: &str,
        biometric_data: &BiometricData,
    ) -> Result<EnrollmentResult, BiometricError>;
    
    /// Authenticate using biometric data
    fn authenticate(
        &self,
        biometric_data: &BiometricData,
    ) -> Result<AuthenticationResult, BiometricError>;
    
    /// Verify liveness of biometric data
    fn verify_liveness(
        &self,
        biometric_data: &BiometricData,
    ) -> Result<bool, BiometricError>;
    
    /// Get list of enrolled users
    fn get_enrolled_users(&self) -> Vec<String>;
    
    /// Remove a user's biometric templates
    fn remove_user(&mut self, user_id: &str) -> Result<(), BiometricError>;
    
    /// Get authentication metrics
    fn get_metrics(&self) -> BiometricMetrics;
}

/// Biometric system performance metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BiometricMetrics {
    /// Total enrollments
    pub total_enrollments: usize,
    /// Total authentication attempts
    pub total_authentications: usize,
    /// Successful authentications
    pub successful_authentications: usize,
    /// Failed authentications
    pub failed_authentications: usize,
    /// Spoofing attempts detected
    pub spoofing_attempts: usize,
    /// Average authentication time (milliseconds)
    pub avg_auth_time_ms: f64,
    /// Per-modality metrics
    pub modality_metrics: HashMap<BiometricType, ModalityMetrics>,
}

/// Per-modality performance metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModalityMetrics {
    /// Enrollments for this modality
    pub enrollments: usize,
    /// Authentication attempts
    pub auth_attempts: usize,
    /// Successful authentications
    pub successful_auths: usize,
    /// Average quality score
    pub avg_quality: f32,
    /// Average processing time (milliseconds)
    pub avg_processing_time_ms: f64,
}

impl Default for BiometricMetrics {
    fn default() -> Self {
        Self {
            total_enrollments: 0,
            total_authentications: 0,
            successful_authentications: 0,
            failed_authentications: 0,
            spoofing_attempts: 0,
            avg_auth_time_ms: 0.0,
            modality_metrics: HashMap::new(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_biometric_template_creation() {
        let template = BiometricTemplate::new(
            BiometricType::Face,
            vec![1, 2, 3, 4],
            Uuid::new_v4(),
            0.95,
        );
        
        assert_eq!(template.biometric_type, BiometricType::Face);
        assert_eq!(template.encrypted_data, vec![1, 2, 3, 4]);
        assert_eq!(template.quality_score, 0.95);
        assert!(template.created_at <= SystemTime::now());
    }
    
    #[test]
    fn test_authentication_result() {
        let user_id = Uuid::new_v4();
        let modalities = vec![BiometricType::Face, BiometricType::Voice];
        
        let success_result = AuthenticationResult::success(user_id, 0.95, modalities.clone());
        assert!(success_result.success);
        assert_eq!(success_result.user_id, Some(user_id));
        assert_eq!(success_result.confidence, 0.95);
        
        let failure_result = AuthenticationResult::failure(modalities);
        assert!(!failure_result.success);
        assert_eq!(failure_result.user_id, None);
        assert_eq!(failure_result.confidence, 0.0);
    }
    
    #[test]
    fn test_biometric_data_builder() {
        let data = BiometricData::new()
            .with_face_image(vec![1, 2, 3], 0.9)
            .with_voice_sample(vec![0.1, 0.2, 0.3], 0.8)
            .with_fingerprint_image(vec![4, 5, 6], 0.95);
        
        assert!(data.face_image.is_some());
        assert!(data.voice_sample.is_some());
        assert!(data.fingerprint_image.is_some());
        assert_eq!(data.quality_indicators.get(&BiometricType::Face), Some(&0.9));
        assert_eq!(data.quality_indicators.get(&BiometricType::Voice), Some(&0.8));
        assert_eq!(data.quality_indicators.get(&BiometricType::Fingerprint), Some(&0.95));
    }
}