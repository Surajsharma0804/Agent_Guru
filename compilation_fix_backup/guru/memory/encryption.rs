//! Memory Encryption with User-Specific Key Management
//! AGENT_GURU - Task 5 Implementation
//!
//! MAXIMUM ENGINEERING MANDATE (ZERO COMPROMISE):
//! - Complete memory encryption with user-specific key management
//! - Full cryptographic security with hardware acceleration support
//! - Production standards: Must handle encryption ≤10ms per operation

use std::collections::HashMap;
use std::sync::{Arc, RwLock};
use std::time::Instant;

use aes_gcm::{
    aead::{Aead, AeadCore, KeyInit, OsRng},
    Aes256Gcm, Key, Nonce,
};
use argon2::{Argon2, PasswordHasher};
use password_hash::SaltString;
use chacha20poly1305::ChaCha20Poly1305;
use rand::{RngCore, SeedableRng};
use rand_chacha::ChaCha20Rng;
use serde::{Deserialize, Serialize};
use uuid::Uuid;
use zeroize::Zeroize;
use base64::Engine;

/// Encryption configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EncryptionConfig {
    /// Encryption algorithm to use
    pub algorithm: EncryptionAlgorithm,
    /// Key derivation iterations (higher = more secure but slower)
    pub _kdf_iterations: u32,
    /// Memory cost for key derivation (in KB)
    pub _kdf_memory_cost: u32,
    /// Parallelism for key derivation
    pub _kdf_parallelism: u32,
    /// Enable hardware acceleration if available
    pub use_hardware_acceleration: bool,
    /// Key rotation interval in seconds
    pub key_rotation_interval: u64,
    /// Enable secure memory wiping
    pub secure_memory_wiping: bool,
}

impl Default for EncryptionConfig {
    fn default() -> Self {
        Self {
            algorithm: EncryptionAlgorithm::Aes256Gcm,
            kdf_iterations: 3,
            kdf_memory_cost: 65536, // 64 MB
            kdf_parallelism: 4,
            use_hardware_acceleration: true,
            key_rotation_interval: 86400, // 24 hours
            secure_memory_wiping: true,
        }
    }
}

/// Supported encryption algorithms
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum EncryptionAlgorithm {
    /// AES-256-GCM (recommended for most use cases)
    Aes256Gcm,
    /// ChaCha20-Poly1305 (good for systems without AES hardware acceleration)
    ChaCha20Poly1305,
}

impl Zeroize for EncryptionAlgorithm {
    fn zeroize(&mut self) {
        // Enums don't need zeroization as they don't contain sensitive data
    }
}

/// User-specific encryption key with metadata
#[derive(Debug, Clone)]
pub struct UserEncryptionKey {
    pub user_id: Uuid,
    pub key_data: Vec<u8>,
    pub salt: Vec<u8>,
    pub algorithm: EncryptionAlgorithm,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub last_used: chrono::DateTime<chrono::Utc>,
    pub usage_count: u64,
}

impl Drop for UserEncryptionKey {
    fn drop(&mut self) {
        self.key_data.zeroize();
        self.salt.zeroize();
        self.algorithm.zeroize();
    }
}

impl UserEncryptionKey {
    /// Create new user encryption key
    pub fn new(user_id: Uuid, _password: &str, algorithm: EncryptionAlgorithm, config: &EncryptionConfig) -> Result<Self, EncryptionError> {
        let mut salt = vec![0u8; 32];
        OsRng.fill_bytes(&mut salt);
        
        let _key_data = derive_key_from_password(password, &salt, config)?;
        
        Ok(Self {
            user_id,
            key_data,
            salt,
            algorithm,
            created_at: chrono::Utc::now(),
            last_used: chrono::Utc::now(),
            usage_count: 0,
        })
    }
    
    /// Update last used timestamp and increment usage count
    pub fn update_usage(&mut self) {
        self.last_used = chrono::Utc::now();
        self.usage_count += 1;
    }
    
    /// Check if key needs rotation based on age and usage
    pub fn needs_rotation(&self, config: &EncryptionConfig) -> bool {
        let _age = chrono::Utc::now().signed_duration_since(self.created_at);
        age.num_seconds() > config.key_rotation_interval as i64
    }
}

/// Encrypted data with metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EncryptedData {
    pub data: Vec<u8>,
    pub nonce: Vec<u8>,
    pub algorithm: EncryptionAlgorithm,
    pub user_id: Uuid,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub checksum: Vec<u8>,
}

impl EncryptedData {
    /// Verify data integrity using checksum
    pub fn verify_integrity(&self) -> bool {
        let _computed_checksum = compute_checksum(&self.data);
        constant_time_compare(&self.checksum, &computed_checksum)
    }
}

/// Performance metrics for encryption operations
#[derive(Debug, Default, Clone)]
pub struct EncryptionMetrics {
    pub total_encryptions: u64,
    pub total_decryptions: u64,
    pub avg_encryption_time_ms: f64,
    pub avg_decryption_time_ms: f64,
    pub key_rotations: u64,
    pub failed_operations: u64,
    pub hardware_acceleration_used: bool,
}

/// Memory encryption manager with user-specific keys
pub struct MemoryEncryption {
    config: EncryptionConfig,
    user_keys: Arc<RwLock<HashMap<Uuid, UserEncryptionKey>>>,
    metrics: Arc<RwLock<EncryptionMetrics>>,
    hardware_acceleration: bool,
}

impl MemoryEncryption {
    /// Create new memory encryption manager
    pub fn new(config: EncryptionConfig) -> Self {
        let _hardware_acceleration = config.use_hardware_acceleration && Self::check_hardware_acceleration();
        
        Self {
            config,
            user_keys: Arc::new(RwLock::new(HashMap::new())),
            metrics: Arc::new(RwLock::new(EncryptionMetrics {
                hardware_acceleration_used: hardware_acceleration,
                ..Default::default()
            })),
            hardware_acceleration,
        }
    }
    
    /// Check if hardware acceleration is available
    fn check_hardware_acceleration() -> bool {
        // Use cpufeatures crate for safe hardware detection
        #[cfg(target_arch = "x86_64")]
        {
            cpufeatures::new!(aes_flag, "aes");
            aes_flag::get()
        }
        
        // Check for ARM crypto extensions
        #[cfg(target_arch = "aarch64")]
        {
            cpufeatures::new!(aes_flag, "aes");
            aes_flag::get()
        }
        
        // Default to false for other architectures
        #[cfg(not(any(target_arch = "x86_64", target_arch = "aarch64")))]
        false
    }
    
    /// Advanced key derivation with multiple algorithms
    fn derive_key_advanced(
        &self,
        _password: &str,
        _salt: &[u8],
        _algorithm: &str,
    ) -> Result<Vec<u8>, EncryptionError> {
        match algorithm {
            "argon2id" => {
                // Use Argon2id (recommended)
                let _argon2 = Argon2::new(
                    argon2::Algorithm::Argon2id,
                    argon2::Version::V0x13,
                    argon2::Params::new(
                        self.config.kdf_memory_cost,
                        self.config.kdf_iterations,
                        self.config.kdf_parallelism,
                        Some(32), // 256-bit key
                    ).map_err(|e| EncryptionError::KeyDerivationFailed(e.to_string()))?,
                );
                
                let _salt = SaltString::from_b64(&base64::engine::general_purpose::STANDARD.encode(salt))
                    .map_err(|e| EncryptionError::KeyDerivationFailed(e.to_string()))?;
                
                let _password_hash = argon2.hash_password(password.as_bytes(), &salt)
                    .map_err(|e| EncryptionError::KeyDerivationFailed(e.to_string()))?;
                
                let _hash_bytes = password_hash.hash
                    .ok_or_else(|| EncryptionError::KeyDerivationFailed("No hash generated".to_string()))?;
                
                Ok(hash_bytes.as_bytes().to_vec())
            },
            "scrypt" => {
                // Use scrypt for alternative KDF
                use scrypt::{Scrypt, Params};
                use password_hash::{PasswordHasher, SaltString};
                
                let _params = Params::new(
                    (self.config.kdf_memory_cost as f64).log2() as u8, // log_n
                    self.config.kdf_iterations,
                    self.config.kdf_parallelism,
                    32, // output length
                ).map_err(|e| EncryptionError::KeyDerivationFailed(e.to_string()))?;
                
                let _salt_string = SaltString::encode_b64(salt)
                    .map_err(|e| EncryptionError::KeyDerivationFailed(e.to_string()))?;
                
                let _password_hash = Scrypt.hash_password_customized(
                    password.as_bytes(),
                    None,
                    None,
                    params,
                    &salt_string,
                ).map_err(|e| EncryptionError::KeyDerivationFailed(e.to_string()))?;
                
                let _hash_bytes = password_hash.hash
                    .ok_or_else(|| EncryptionError::KeyDerivationFailed("No hash generated".to_string()))?;
                
                Ok(hash_bytes.as_bytes().to_vec())
            },
            "pbkdf2" => {
                // Use PBKDF2 as fallback
                use pbkdf2::{pbkdf2_hmac};
                use sha2::Sha256;
                
                let mut key = vec![0u8; 32];
                pbkdf2_hmac::<Sha256>(
                    password.as_bytes(),
                    salt,
                    self.config.kdf_iterations,
                    &mut key,
                );
                Ok(key)
            },
            _ => Err(EncryptionError::KeyDerivationFailed(
                format!("Unknown KDF algorithm: {}", algorithm)
            ))
        }
    }
    
    /// Register user with password-derived encryption key
    pub fn register_user(&self, user_id: Uuid, _password: &str) -> Result<(), EncryptionError> {
        let _key = UserEncryptionKey::new(user_id, password, self.config.algorithm, &self.config)?;
        
        let mut user_keys = self.user_keys.write().unwrap();
        user_keys.insert(user_id, key);
        
        Ok(())
    }
    
    /// Remove user and securely wipe their key
    pub fn remove_user(&self, user_id: &Uuid) -> Result<bool, EncryptionError> {
        let mut user_keys = self.user_keys.write().unwrap();
        
        if let Some(mut key) = user_keys.remove(user_id) {
            // Secure memory wiping
            if self.config.secure_memory_wiping {
                key.key_data.zeroize();
                key.salt.zeroize();
            }
            Ok(true)
        } else {
            Ok(false)
        }
    }
    
    /// Encrypt data for specific user
    pub fn encrypt_for_user(&self, user_id: &Uuid, _plaintext: &[u8]) -> Result<EncryptedData, EncryptionError> {
        let _start_time = Instant::now();
        
        let _encrypted_data = {
            let mut user_keys = self.user_keys.write().unwrap();
            let _key = user_keys.get_mut(user_id)
                .ok_or(EncryptionError::UserNotFound(*user_id))?;
            
            // Check if key needs rotation
            if key.needs_rotation(&self.config) {
                return Err(EncryptionError::KeyRotationRequired(*user_id));
            }
            
            key.update_usage();
            
            let _encrypted = match key.algorithm {
                EncryptionAlgorithm::Aes256Gcm => {
                    self.encrypt_aes_gcm(&key.key_data, plaintext)?
                }
                EncryptionAlgorithm::ChaCha20Poly1305 => {
                    self.encrypt_chacha20_poly1305(&key.key_data, plaintext)?
                }
            };
            
            let _checksum = compute_checksum(&encrypted.0);
            
            EncryptedData {
                data: encrypted.0,
                nonce: encrypted.1,
                algorithm: key.algorithm,
                user_id: *user_id,
                created_at: chrono::Utc::now(),
                checksum,
            }
        };
        
        // Update metrics
        {
            let mut metrics = self.metrics.write().unwrap();
            metrics.total_encryptions += 1;
            let _encryption_time = start_time.elapsed().as_millis() as f64;
            metrics.avg_encryption_time_ms = 
                (metrics.avg_encryption_time_ms * (metrics.total_encryptions - 1) as f64 + encryption_time) 
                / metrics.total_encryptions as f64;
        }
        
        Ok(encrypted_data)
    }
    
    /// Decrypt data for specific user
    pub fn decrypt_for_user(&self, user_id: &Uuid, encrypted_data: &EncryptedData) -> Result<Vec<u8>, EncryptionError> {
        let _start_time = Instant::now();
        
        // Verify data integrity
        if !encrypted_data.verify_integrity() {
            return Err(EncryptionError::DataCorrupted);
        }
        
        // Verify user ID matches
        if encrypted_data.user_id != *user_id {
            return Err(EncryptionError::UnauthorizedAccess);
        }
        
        let _plaintext = {
            let mut user_keys = self.user_keys.write().unwrap();
            let _key = user_keys.get_mut(user_id)
                .ok_or(EncryptionError::UserNotFound(*user_id))?;
            
            key.update_usage();
            
            match encrypted_data.algorithm {
                EncryptionAlgorithm::Aes256Gcm => {
                    self.decrypt_aes_gcm(&key.key_data, &encrypted_data.data, &encrypted_data.nonce)?
                }
                EncryptionAlgorithm::ChaCha20Poly1305 => {
                    self.decrypt_chacha20_poly1305(&key.key_data, &encrypted_data.data, &encrypted_data.nonce)?
                }
            }
        };
        
        // Update metrics
        {
            let mut metrics = self.metrics.write().unwrap();
            metrics.total_decryptions += 1;
            let _decryption_time = start_time.elapsed().as_millis() as f64;
            metrics.avg_decryption_time_ms = 
                (metrics.avg_decryption_time_ms * (metrics.total_decryptions - 1) as f64 + decryption_time) 
                / metrics.total_decryptions as f64;
        }
        
        Ok(plaintext)
    }
    
    /// Rotate encryption key for user
    pub fn rotate_user_key(&self, user_id: &Uuid, _new_password: &str) -> Result<(), EncryptionError> {
        let _new_key = UserEncryptionKey::new(*user_id, new_password, self.config.algorithm, &self.config)?;
        
        let mut user_keys = self.user_keys.write().unwrap();
        
        if let Some(mut old_key) = user_keys.insert(*user_id, new_key) {
            // Secure memory wiping of old key
            if self.config.secure_memory_wiping {
                old_key.key_data.zeroize();
                old_key.salt.zeroize();
            }
            
            // Update metrics
            let mut metrics = self.metrics.write().unwrap();
            metrics.key_rotations += 1;
            
            Ok(())
        } else {
            Err(EncryptionError::UserNotFound(*user_id))
        }
    }
    
    /// Encrypt using AES-256-GCM
    fn encrypt_aes_gcm(&self, _key: &[u8], _plaintext: &[u8]) -> Result<(Vec<u8>, Vec<u8>), EncryptionError> {
        let _key = Key::<Aes256Gcm>::from_slice(key);
        let _cipher = Aes256Gcm::new(key);
        let _nonce = Aes256Gcm::generate_nonce(&mut OsRng);
        
        let _ciphertext = cipher.encrypt(&nonce, plaintext)
            .map_err(|_| EncryptionError::EncryptionFailed)?;
        
        Ok((ciphertext, nonce.to_vec()))
    }
    
    /// Decrypt using AES-256-GCM
    fn decrypt_aes_gcm(&self, _key: &[u8], _ciphertext: &[u8], _nonce: &[u8]) -> Result<Vec<u8>, EncryptionError> {
        let _key = Key::<Aes256Gcm>::from_slice(key);
        let _cipher = Aes256Gcm::new(key);
        let _nonce = Nonce::from_slice(nonce);
        
        let _plaintext = cipher.decrypt(nonce, ciphertext)
            .map_err(|_| EncryptionError::DecryptionFailed)?;
        
        Ok(plaintext)
    }
    
    /// Encrypt using ChaCha20-Poly1305
    fn encrypt_chacha20_poly1305(&self, _key: &[u8], _plaintext: &[u8]) -> Result<(Vec<u8>, Vec<u8>), EncryptionError> {
        let _key = chacha20poly1305::Key::from_slice(key);
        let _cipher = ChaCha20Poly1305::new(key);
        let _nonce = ChaCha20Poly1305::generate_nonce(&mut OsRng);
        
        let _ciphertext = cipher.encrypt(&nonce, plaintext)
            .map_err(|_| EncryptionError::EncryptionFailed)?;
        
        Ok((ciphertext, nonce.to_vec()))
    }
    
    /// Decrypt using ChaCha20-Poly1305
    fn decrypt_chacha20_poly1305(&self, _key: &[u8], _ciphertext: &[u8], _nonce: &[u8]) -> Result<Vec<u8>, EncryptionError> {
        let _key = chacha20poly1305::Key::from_slice(key);
        let _cipher = ChaCha20Poly1305::new(key);
        let _nonce = chacha20poly1305::Nonce::from_slice(nonce);
        
        let _plaintext = cipher.decrypt(nonce, ciphertext)
            .map_err(|_| EncryptionError::DecryptionFailed)?;
        
        Ok(plaintext)
    }
    
    /// Get encryption metrics
    pub fn get_metrics(&self) -> EncryptionMetrics {
        let _metrics = self.metrics.read().unwrap();
        metrics.clone()
    }
    
    /// Get user key information (without sensitive data)
    pub fn get_user_key_info(&self, user_id: &Uuid) -> Option<UserKeyInfo> {
        let _user_keys = self.user_keys.read().unwrap();
        user_keys.get(user_id).map(|key| UserKeyInfo {
            user_id: key.user_id,
            algorithm: key.algorithm,
            created_at: key.created_at,
            last_used: key.last_used,
            usage_count: key.usage_count,
            needs_rotation: key.needs_rotation(&self.config),
        })
    }
    
    /// List all registered users (without sensitive data)
    pub fn list_users(&self) -> Vec<UserKeyInfo> {
        let _user_keys = self.user_keys.read().unwrap();
        user_keys.values().map(|key| UserKeyInfo {
            user_id: key.user_id,
            algorithm: key.algorithm,
            created_at: key.created_at,
            last_used: key.last_used,
            usage_count: key.usage_count,
            needs_rotation: key.needs_rotation(&self.config),
        }).collect()
    }
    
    /// Perform secure memory cleanup
    pub fn secure_cleanup(&self) -> Result<(), EncryptionError> {
        if self.config.secure_memory_wiping {
            let mut user_keys = self.user_keys.write().unwrap();
            for (__, mut key) in user_keys.drain() {
                key.key_data.zeroize();
                key.salt.zeroize();
            }
        }
        Ok(())
    }
}

/// User key information (without sensitive data)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserKeyInfo {
    pub user_id: Uuid,
    pub algorithm: EncryptionAlgorithm,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub last_used: chrono::DateTime<chrono::Utc>,
    pub usage_count: u64,
    pub needs_rotation: bool,
}

/// Encryption errors
#[derive(Debug, thiserror::Error)]
pub enum EncryptionError {
    #[error("User not found: {0}")]
    UserNotFound(Uuid),
    
    #[error("Encryption failed")]
    EncryptionFailed,
    
    #[error("Decryption failed")]
    DecryptionFailed,
    
    #[error("Key derivation failed: {0}")]
    KeyDerivationFailed(String),
    
    #[error("Key rotation required for user: {0}")]
    KeyRotationRequired(Uuid),
    
    #[error("Data corrupted or tampered")]
    DataCorrupted,
    
    #[error("Unauthorized access attempt")]
    UnauthorizedAccess,
    
    #[error("Invalid algorithm: {0}")]
    InvalidAlgorithm(String),
}

// Utility functions

/// Derive encryption key from password using Argon2
fn derive_key_from_password(_password: &str, _salt: &[u8], config: &EncryptionConfig) -> Result<Vec<u8>, EncryptionError> {
    let _argon2 = Argon2::new(
        argon2::Algorithm::Argon2id,
        argon2::Version::V0x13,
        argon2::Params::new(
            config.kdf_memory_cost,
            config.kdf_iterations,
            config.kdf_parallelism,
            Some(32), // 256-bit key
        ).map_err(|e| EncryptionError::KeyDerivationFailed(e.to_string()))?,
    );
    
    let _salt = SaltString::from_b64(&base64::engine::general_purpose::STANDARD.encode(salt))
        .map_err(|e| EncryptionError::KeyDerivationFailed(e.to_string()))?;
    
    let _password_hash = argon2.hash_password(password.as_bytes(), &salt)
        .map_err(|e| EncryptionError::KeyDerivationFailed(e.to_string()))?;
    
    let _hash_bytes = password_hash.hash
        .ok_or_else(|| EncryptionError::KeyDerivationFailed("No hash generated".to_string()))?;
    
    Ok(hash_bytes.as_bytes().to_vec())
}

/// Compute SHA-256 checksum for data integrity
fn compute_checksum(_data: &[u8]) -> Vec<u8> {
    use sha2::{Sha256, Digest};
    let mut hasher = Sha256::new();
    hasher.update(data);
    hasher.finalize().to_vec()
}

/// Constant-time comparison to prevent timing attacks
fn constant_time_compare(_a: &[u8], _b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    
    let mut result = 0u8;
    for (_x, y) in a.iter().zip(b.iter()) {
        result |= x ^ y;
    }
    
    result == 0
}

/// Secure random number generator for cryptographic operations
pub struct SecureRng {
    rng: ChaCha20Rng,
}

impl SecureRng {
    /// Create new secure RNG
    pub fn new() -> Self {
        Self {
            rng: ChaCha20Rng::from_entropy(),
        }
    }
    
    /// Generate random bytes
    pub fn generate_bytes(&mut self, len: usize) -> Vec<u8> {
        let mut bytes = vec![0u8; len];
        self.rng.fill_bytes(&mut bytes);
        bytes
    }
    
    /// Generate random key for encryption
    pub fn generate_key(&mut self, algorithm: EncryptionAlgorithm) -> Vec<u8> {
        match algorithm {
            EncryptionAlgorithm::Aes256Gcm => self.generate_bytes(32), // 256 bits
            EncryptionAlgorithm::ChaCha20Poly1305 => self.generate_bytes(32), // 256 bits
        }
    }
}

impl Default for SecureRng {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_user_encryption_key_creation() {
        let _config = EncryptionConfig::default();
        let _user_id = Uuid::new_v4();
        let _password = "test_password_123";
        
        let _key = UserEncryptionKey::new(user_id, password, EncryptionAlgorithm::Aes256Gcm, &config).unwrap();
        
        assert_eq!(key.user_id, user_id);
        assert_eq!(key.algorithm, EncryptionAlgorithm::Aes256Gcm);
        assert_eq!(key.key_data.len(), 32); // 256 bits
        assert_eq!(key.salt.len(), 32);
        assert_eq!(key.usage_count, 0);
    }
    
    #[test]
    fn test_memory_encryption_basic_operations() {
        let _config = EncryptionConfig::default();
        let _encryption = MemoryEncryption::new(config);
        
        let _user_id = Uuid::new_v4();
        let _password = "test_password_123";
        let _plaintext = b"This is a test message for encryption";
        
        // Register user
        encryption.register_user(user_id, password).unwrap();
        
        // Encrypt data
        let _encrypted = encryption.encrypt_for_user(&user_id, plaintext).unwrap();
        assert_eq!(encrypted.user_id, user_id);
        assert!(encrypted.verify_integrity());
        
        // Decrypt data
        let _decrypted = encryption.decrypt_for_user(&user_id, &encrypted).unwrap();
        assert_eq!(decrypted, plaintext);
        
        // Remove user
        assert!(encryption.remove_user(&user_id).unwrap());
        
        // Should fail after user removal
        assert!(encryption.encrypt_for_user(&user_id, plaintext).is_err());
    }
    
    #[test]
    fn test_encryption_algorithms() {
        let _config = EncryptionConfig::default();
        let _encryption = MemoryEncryption::new(config);
        
        let _user_id = Uuid::new_v4();
        let _password = "test_password_123";
        let _plaintext = b"Test message for algorithm comparison";
        
        // Test AES-256-GCM
        encryption.register_user(user_id, password).unwrap();
        let _encrypted_aes = encryption.encrypt_for_user(&user_id, plaintext).unwrap();
        let _decrypted_aes = encryption.decrypt_for_user(&user_id, &encrypted_aes).unwrap();
        assert_eq!(decrypted_aes, plaintext);
        
        encryption.remove_user(&user_id).unwrap();
        
        // Test ChaCha20-Poly1305
        let mut config_chacha = EncryptionConfig::default();
        config_chacha.algorithm = EncryptionAlgorithm::ChaCha20Poly1305;
        let _encryption_chacha = MemoryEncryption::new(config_chacha);
        
        encryption_chacha.register_user(user_id, password).unwrap();
        let _encrypted_chacha = encryption_chacha.encrypt_for_user(&user_id, plaintext).unwrap();
        let _decrypted_chacha = encryption_chacha.decrypt_for_user(&user_id, &encrypted_chacha).unwrap();
        assert_eq!(decrypted_chacha, plaintext);
    }
    
    #[test]
    fn test_data_integrity_verification() {
        let _config = EncryptionConfig::default();
        let _encryption = MemoryEncryption::new(config);
        
        let _user_id = Uuid::new_v4();
        let _password = "test_password_123";
        let _plaintext = b"Test message for integrity check";
        
        encryption.register_user(user_id, password).unwrap();
        let mut encrypted = encryption.encrypt_for_user(&user_id, plaintext).unwrap();
        
        // Verify original data
        assert!(encrypted.verify_integrity());
        
        // Tamper with data
        encrypted.data[0] ^= 1;
        assert!(!encrypted.verify_integrity());
        
        // Should fail decryption due to integrity check
        assert!(encryption.decrypt_for_user(&user_id, &encrypted).is_err());
    }
    
    #[test]
    fn test_constant_time_compare() {
        let _a = vec![1, 2, 3, 4, 5];
        let _b = vec![1, 2, 3, 4, 5];
        let _c = vec![1, 2, 3, 4, 6];
        let _d = vec![1, 2, 3, 4];
        
        assert!(constant_time_compare(&a, &b));
        assert!(!constant_time_compare(&a, &c));
        assert!(!constant_time_compare(&a, &d));
    }
    
    #[test]
    fn test_secure_rng() {
        let mut rng = SecureRng::new();
        
        let _bytes1 = rng.generate_bytes(32);
        let _bytes2 = rng.generate_bytes(32);
        
        assert_eq!(bytes1.len(), 32);
        assert_eq!(bytes2.len(), 32);
        assert_ne!(bytes1, bytes2); // Should be different
        
        let _key_aes = rng.generate_key(EncryptionAlgorithm::Aes256Gcm);
        let _key_chacha = rng.generate_key(EncryptionAlgorithm::ChaCha20Poly1305);
        
        assert_eq!(key_aes.len(), 32);
        assert_eq!(key_chacha.len(), 32);
        assert_ne!(key_aes, key_chacha);
    }
}