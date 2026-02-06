//! Checksum Generator - Cryptographic Integrity Verification
//!
//! This module implements cryptographic checksum generation and verification for the inventory
//! system. It provides SHA-256 checksums with hardware acceleration support and integrity
//! validation capabilities for production-grade file verification.
//!
//! ## Features
//!
//! - SHA-256 cryptographic checksum generation
//! - Hardware acceleration support (when available)
//! - Integrity verification and tamper detection
//! - Batch processing for multiple files
//! - Performance optimization with streaming I/O
//! - Comprehensive error handling and validation
//!
//! ## Performance Requirements
//!
//! - Checksum generation: ≤5ms per file (with hardware acceleration)
//! - Verification: ≤2ms per file
//! - Batch processing: Linear scaling with file count
//! - Memory usage: Constant regardless of file size

use crate::error::{AuditError, AuditResult};
use crate::inventory::types::InventorySystemConfig;
use async_trait::async_trait;
use sha2::{Digest, Sha256};
use std::path::Path;
use tokio::fs::File;
use tokio::io::{AsyncReadExt, BufReader};
use tracing::{debug, warn, error};

/// Trait defining the checksum generator interface
#[async_trait]
pub trait ChecksumGenerator: Send + Sync {
    /// Generate SHA-256 checksum for a file
    async fn generate_checksum(&self, file_path: &Path) -> AuditResult<[u8; 32]>;
    
    /// Verify a file's checksum against expected value
    async fn verify_checksum(&self, file_path: &Path, expected_checksum: &[u8; 32]) -> AuditResult<bool>;
    
    /// Generate checksums for multiple files in batch
    async fn generate_batch_checksums(&self, file_paths: &[&Path]) -> AuditResult<Vec<([u8; 32], std::path::PathBuf)>>;
    
    /// Get checksum algorithm information
    fn get_algorithm_info(&self) -> ChecksumAlgorithmInfo;
}

/// Information about the checksum algorithm
#[derive(Debug, Clone)]
pub struct ChecksumAlgorithmInfo {
    /// Algorithm name (e.g., "SHA-256")
    pub name: String,
    /// Output size in bytes
    pub output_size: usize,
    /// Whether hardware acceleration is available
    pub hardware_accelerated: bool,
    /// Security strength in bits
    pub security_strength: u32,
}

/// Production-grade checksum generator implementation
pub struct ProductionChecksumGenerator {
    /// Configuration for the checksum generator
    config: InventorySystemConfig,
    /// Buffer size for streaming I/O
    buffer_size: usize,
    /// Whether to use hardware acceleration
    use_hardware_acceleration: bool,
}

impl ProductionChecksumGenerator {
    /// Create a new production checksum generator
    pub fn new(config: InventorySystemConfig) -> AuditResult<Self> {
        // Validate checksum algorithm
        if config.checksum_algorithm != "SHA-256" {
            return Err(AuditError::ConfigurationError {
                parameter: "checksum_algorithm".to_string(),
                reason: format!("Unsupported checksum algorithm: {}", config.checksum_algorithm),
                suggested_fix: Some("Use SHA-256 algorithm".to_string()),
            });
        }
        
        Ok(Self {
            config,
            buffer_size: 64 * 1024, // 64KB buffer for optimal I/O performance
            use_hardware_acceleration: Self::detect_hardware_acceleration(),
        })
    }
    
    /// Detect if hardware acceleration is available
    fn detect_hardware_acceleration() -> bool {
        // Check for hardware acceleration support
        // This is a simplified check - in production, you might use CPU feature detection
        cfg!(target_feature = "aes") || cfg!(target_feature = "sha")
    }
    
    /// Generate checksum using streaming I/O for large files
    async fn generate_checksum_streaming(&self, file_path: &Path) -> AuditResult<[u8; 32]> {
        debug!("Generating SHA-256 checksum for: {}", file_path.display());
        
        // Open file for reading
        let file = File::open(file_path).await.map_err(|e| {
            AuditError::FileSystemError {
                operation: "open_file".to_string(),
                path: file_path.display().to_string(),
                reason: e.to_string(),
            }
        })?;
        
        let mut reader = BufReader::with_capacity(self.buffer_size, file);
        let mut hasher = Sha256::new();
        let mut buffer = vec![0u8; self.buffer_size];
        
        // Read file in chunks and update hash
        loop {
            let bytes_read = reader.read(&mut buffer).await.map_err(|e| {
                AuditError::FileSystemError {
                    operation: "read_file".to_string(),
                    path: file_path.display().to_string(),
                    reason: e.to_string(),
                }
            })?;
            
            if bytes_read == 0 {
                break; // End of file
            }
            
            hasher.update(&buffer[..bytes_read]);
        }
        
        // Finalize hash and convert to array
        let hash_result = hasher.finalize();
        let mut checksum = [0u8; 32];
        checksum.copy_from_slice(&hash_result);
        
        debug!("Checksum generated for {}: {}", file_path.display(), hex::encode(checksum));
        
        Ok(checksum)
    }
    
    /// Generate checksum for small files (load entirely into memory)
    async fn generate_checksum_memory(&self, file_path: &Path) -> AuditResult<[u8; 32]> {
        debug!("Generating SHA-256 checksum (memory) for: {}", file_path.display());
        
        // Read entire file into memory
        let content = tokio::fs::read(file_path).await.map_err(|e| {
            AuditError::FileSystemError {
                operation: "read_file".to_string(),
                path: file_path.display().to_string(),
                reason: e.to_string(),
            }
        })?;
        
        // Generate hash
        let mut hasher = Sha256::new();
        hasher.update(&content);
        let hash_result = hasher.finalize();
        
        // Convert to array
        let mut checksum = [0u8; 32];
        checksum.copy_from_slice(&hash_result);
        
        debug!("Checksum generated for {}: {}", file_path.display(), hex::encode(checksum));
        
        Ok(checksum)
    }
    
    /// Choose the appropriate checksum generation method based on file size
    async fn choose_checksum_method(&self, file_path: &Path) -> AuditResult<[u8; 32]> {
        // Get file size
        let metadata = tokio::fs::metadata(file_path).await.map_err(|e| {
            AuditError::FileSystemError {
                operation: "get_metadata".to_string(),
                path: file_path.display().to_string(),
                reason: e.to_string(),
            }
        })?;
        
        let file_size = metadata.len();
        
        // Use memory method for small files, streaming for large files
        const MEMORY_THRESHOLD: u64 = 1024 * 1024; // 1MB
        
        if file_size <= MEMORY_THRESHOLD {
            self.generate_checksum_memory(file_path).await
        } else {
            self.generate_checksum_streaming(file_path).await
        }
    }
    
    /// Validate file accessibility before checksum generation
    async fn validate_file_access(&self, file_path: &Path) -> AuditResult<()> {
        // Check if file exists
        if !file_path.exists() {
            return Err(AuditError::FileSystemError {
                operation: "check_existence".to_string(),
                path: file_path.display().to_string(),
                reason: "File does not exist".to_string(),
            });
        }
        
        // Check if it's a file (not a directory)
        if !file_path.is_file() {
            return Err(AuditError::FileSystemError {
                operation: "check_file_type".to_string(),
                path: file_path.display().to_string(),
                reason: "Path is not a regular file".to_string(),
            });
        }
        
        // Check file size limit
        let metadata = tokio::fs::metadata(file_path).await.map_err(|e| {
            AuditError::FileSystemError {
                operation: "get_metadata".to_string(),
                path: file_path.display().to_string(),
                reason: e.to_string(),
            }
        })?;
        
        let file_size = metadata.len();
        let max_size = (self.config.max_file_size_mb as u64) * 1024 * 1024;
        
        if file_size > max_size {
            return Err(AuditError::ConfigurationError {
                parameter: "file_size".to_string(),
                reason: format!("File size {} exceeds maximum allowed size {}", file_size, max_size),
                suggested_fix: Some("Increase max_file_size_mb or exclude large files".to_string()),
            });
        }
        
        Ok(())
    }
}

#[async_trait]
impl ChecksumGenerator for ProductionChecksumGenerator {
    async fn generate_checksum(&self, file_path: &Path) -> AuditResult<[u8; 32]> {
        // Validate file access
        self.validate_file_access(file_path).await?;
        
        // Generate checksum using appropriate method
        self.choose_checksum_method(file_path).await
    }
    
    async fn verify_checksum(&self, file_path: &Path, expected_checksum: &[u8; 32]) -> AuditResult<bool> {
        debug!("Verifying checksum for: {}", file_path.display());
        
        // Generate current checksum
        let current_checksum = self.generate_checksum(file_path).await?;
        
        // Compare checksums
        let is_valid = current_checksum == *expected_checksum;
        
        if is_valid {
            debug!("Checksum verification passed for: {}", file_path.display());
        } else {
            warn!(
                "Checksum verification failed for: {} (expected: {}, actual: {})",
                file_path.display(),
                hex::encode(expected_checksum),
                hex::encode(current_checksum)
            );
        }
        
        Ok(is_valid)
    }
    
    async fn generate_batch_checksums(&self, file_paths: &[&Path]) -> AuditResult<Vec<([u8; 32], std::path::PathBuf)>> {
        debug!("Generating batch checksums for {} files", file_paths.len());
        
        let mut results = Vec::with_capacity(file_paths.len());
        let mut errors = Vec::new();
        
        // Process files sequentially to avoid overwhelming I/O
        // In a more advanced implementation, you could use controlled parallelism
        for file_path in file_paths {
            match self.generate_checksum(file_path).await {
                Ok(checksum) => {
                    results.push((checksum, file_path.to_path_buf()));
                }
                Err(error) => {
                    warn!("Failed to generate checksum for {}: {}", file_path.display(), error);
                    errors.push((file_path.to_path_buf(), error));
                }
            }
        }
        
        // If there were errors, log them but continue with successful results
        if !errors.is_empty() {
            warn!("Encountered {} errors during batch checksum generation", errors.len());
            for (path, error) in &errors {
                error!("Checksum error for {}: {}", path.display(), error);
            }
        }
        
        debug!("Batch checksum generation completed: {} successful, {} errors", results.len(), errors.len());
        
        Ok(results)
    }
    
    fn get_algorithm_info(&self) -> ChecksumAlgorithmInfo {
        ChecksumAlgorithmInfo {
            name: "SHA-256".to_string(),
            output_size: 32,
            hardware_accelerated: self.use_hardware_acceleration,
            security_strength: 256,
        }
    }
}

/// Utility functions for checksum operations
pub mod utils {
    use super::*;
    
    /// Convert checksum bytes to hexadecimal string
    pub fn checksum_to_hex(checksum: &[u8; 32]) -> String {
        hex::encode(checksum)
    }
    
    /// Parse hexadecimal string to checksum bytes
    pub fn hex_to_checksum(hex_string: &str) -> AuditResult<[u8; 32]> {
        if hex_string.len() != 64 {
            return Err(AuditError::ConfigurationError {
                parameter: "hex_string".to_string(),
                reason: format!("Invalid hex string length: {} (expected 64)", hex_string.len()),
                suggested_fix: Some("Provide a valid 64-character hex string".to_string()),
            });
        }
        
        let bytes = hex::decode(hex_string).map_err(|e| {
            AuditError::ConfigurationError {
                parameter: "hex_string".to_string(),
                reason: format!("Invalid hex string: {}", e),
                suggested_fix: Some("Provide a valid hexadecimal string".to_string()),
            }
        })?;
        
        let mut checksum = [0u8; 32];
        checksum.copy_from_slice(&bytes);
        
        Ok(checksum)
    }
    
    /// Compare two checksums for equality
    pub fn checksums_equal(checksum1: &[u8; 32], checksum2: &[u8; 32]) -> bool {
        checksum1 == checksum2
    }
    
    /// Validate checksum format
    pub fn validate_checksum_format(checksum: &[u8; 32]) -> bool {
        // SHA-256 checksums are always 32 bytes, so any 32-byte array is valid
        checksum.len() == 32
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;
    use tokio::fs;
    
    async fn create_test_file(content: &str) -> (TempDir, std::path::PathBuf) {
        let temp_dir = TempDir::new().unwrap();
        let file_path = temp_dir.path().join("test_file.txt");
        fs::write(&file_path, content).await.unwrap();
        (temp_dir, file_path)
    }
    
    #[tokio::test]
    async fn test_checksum_generation() {
        let content = "Hello, world!";
        let (_temp_dir, file_path) = create_test_file(content).await;
        
        let config = InventorySystemConfig::default();
        let generator = ProductionChecksumGenerator::new(config).unwrap();
        
        let checksum = generator.generate_checksum(&file_path).await.unwrap();
        
        // Verify checksum is 32 bytes
        assert_eq!(checksum.len(), 32);
        
        // Verify checksum is deterministic
        let checksum2 = generator.generate_checksum(&file_path).await.unwrap();
        assert_eq!(checksum, checksum2);
    }
    
    #[tokio::test]
    async fn test_checksum_verification() {
        let content = "Test content for verification";
        let (_temp_dir, file_path) = create_test_file(content).await;
        
        let config = InventorySystemConfig::default();
        let generator = ProductionChecksumGenerator::new(config).unwrap();
        
        // Generate checksum
        let checksum = generator.generate_checksum(&file_path).await.unwrap();
        
        // Verify with correct checksum
        let is_valid = generator.verify_checksum(&file_path, &checksum).await.unwrap();
        assert!(is_valid);
        
        // Verify with incorrect checksum
        let mut wrong_checksum = checksum;
        wrong_checksum[0] = wrong_checksum[0].wrapping_add(1);
        let is_invalid = generator.verify_checksum(&file_path, &wrong_checksum).await.unwrap();
        assert!(!is_invalid);
    }
    
    #[tokio::test]
    async fn test_batch_checksum_generation() {
        let temp_dir = TempDir::new().unwrap();
        
        // Create multiple test files
        let file1_path = temp_dir.path().join("file1.txt");
        let file2_path = temp_dir.path().join("file2.txt");
        let file3_path = temp_dir.path().join("file3.txt");
        
        fs::write(&file1_path, "Content 1").await.unwrap();
        fs::write(&file2_path, "Content 2").await.unwrap();
        fs::write(&file3_path, "Content 3").await.unwrap();
        
        let config = InventorySystemConfig::default();
        let generator = ProductionChecksumGenerator::new(config).unwrap();
        
        // Generate batch checksums
        let file_paths = vec![file1_path.as_path(), file2_path.as_path(), file3_path.as_path()];
        let results = generator.generate_batch_checksums(&file_paths).await.unwrap();
        
        // Verify results
        assert_eq!(results.len(), 3);
        
        // Verify each checksum is unique (different content should produce different checksums)
        let checksums: Vec<_> = results.iter().map(|(checksum, _)| *checksum).collect();
        assert_ne!(checksums[0], checksums[1]);
        assert_ne!(checksums[1], checksums[2]);
        assert_ne!(checksums[0], checksums[2]);
    }
    
    #[tokio::test]
    async fn test_large_file_checksum() {
        let temp_dir = TempDir::new().unwrap();
        let file_path = temp_dir.path().join("large_file.txt");
        
        // Create a large file (2MB)
        let large_content = "A".repeat(2 * 1024 * 1024);
        fs::write(&file_path, &large_content).await.unwrap();
        
        let config = InventorySystemConfig::default();
        let generator = ProductionChecksumGenerator::new(config).unwrap();
        
        // Generate checksum (should use streaming method)
        let checksum = generator.generate_checksum(&file_path).await.unwrap();
        
        // Verify checksum is valid
        assert_eq!(checksum.len(), 32);
        
        // Verify checksum is consistent
        let checksum2 = generator.generate_checksum(&file_path).await.unwrap();
        assert_eq!(checksum, checksum2);
    }
    
    #[tokio::test]
    async fn test_empty_file_checksum() {
        let (_temp_dir, file_path) = create_test_file("").await;
        
        let config = InventorySystemConfig::default();
        let generator = ProductionChecksumGenerator::new(config).unwrap();
        
        let checksum = generator.generate_checksum(&file_path).await.unwrap();
        
        // Empty file should have a specific SHA-256 hash
        let expected_empty_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";
        let actual_hex = hex::encode(checksum);
        assert_eq!(actual_hex, expected_empty_hash);
    }
    
    #[test]
    fn test_algorithm_info() {
        let config = InventorySystemConfig::default();
        let generator = ProductionChecksumGenerator::new(config).unwrap();
        
        let info = generator.get_algorithm_info();
        
        assert_eq!(info.name, "SHA-256");
        assert_eq!(info.output_size, 32);
        assert_eq!(info.security_strength, 256);
    }
    
    #[test]
    fn test_utility_functions() {
        let checksum = [0x12, 0x34, 0x56, 0x78, 0x9a, 0xbc, 0xde, 0xf0,
                       0x12, 0x34, 0x56, 0x78, 0x9a, 0xbc, 0xde, 0xf0,
                       0x12, 0x34, 0x56, 0x78, 0x9a, 0xbc, 0xde, 0xf0,
                       0x12, 0x34, 0x56, 0x78, 0x9a, 0xbc, 0xde, 0xf0];
        
        // Test hex conversion
        let hex_string = utils::checksum_to_hex(&checksum);
        assert_eq!(hex_string.len(), 64);
        
        // Test hex parsing
        let parsed_checksum = utils::hex_to_checksum(&hex_string).unwrap();
        assert_eq!(parsed_checksum, checksum);
        
        // Test checksum comparison
        assert!(utils::checksums_equal(&checksum, &parsed_checksum));
        
        // Test checksum validation
        assert!(utils::validate_checksum_format(&checksum));
    }
    
    #[tokio::test]
    async fn test_file_validation() {
        let config = InventorySystemConfig::default();
        let generator = ProductionChecksumGenerator::new(config).unwrap();
        
        // Test non-existent file
        let non_existent = std::path::Path::new("non_existent_file.txt");
        let result = generator.generate_checksum(non_existent).await;
        assert!(result.is_err());
        
        // Test directory instead of file
        let temp_dir = TempDir::new().unwrap();
        let result = generator.generate_checksum(temp_dir.path()).await;
        assert!(result.is_err());
    }
}