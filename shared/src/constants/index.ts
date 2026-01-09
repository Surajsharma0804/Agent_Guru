/**
 * @fileoverview System constants for the Guru Personal Assistant
 */

// Cryptographic constants
export const CRYPTO_CONSTANTS = {
  KEY_SIZE: 32,
  SIGNATURE_SIZE: 64,
  NONCE_SIZE: 24,
  SALT_SIZE: 16,
  HASH_SIZE: 32,
} as const;

// Network constants
export const NETWORK_CONSTANTS = {
  DEFAULT_PORT: 8443,
  MAX_MESSAGE_SIZE: 1024 * 1024, // 1MB
  CONNECTION_TIMEOUT: 30000, // 30 seconds
  HEARTBEAT_INTERVAL: 60000, // 1 minute
} as const;

// Authentication constants
export const AUTH_CONSTANTS = {
  MAX_REQUEST_AGE: 300000, // 5 minutes
  SESSION_TIMEOUT: 3600000, // 1 hour
  MAX_RETRY_ATTEMPTS: 3,
  LOCKOUT_DURATION: 900000, // 15 minutes
} as const;

// Device constants
export const DEVICE_CONSTANTS = {
  MAX_PAIRED_DEVICES: 10,
  PAIRING_CODE_LENGTH: 6,
  PAIRING_TIMEOUT: 300000, // 5 minutes
} as const;

// Protocol version
export const PROTOCOL_VERSION = '1.0.0' as const;

// Error codes
export const ERROR_CODES = {
  // Authentication errors
  INVALID_SIGNATURE: 'AUTH_001',
  EXPIRED_REQUEST: 'AUTH_002',
  DEVICE_NOT_PAIRED: 'AUTH_003',
  BIOMETRIC_FAILED: 'AUTH_004',
  
  // Cryptographic errors
  KEY_GENERATION_FAILED: 'CRYPTO_001',
  ENCRYPTION_FAILED: 'CRYPTO_002',
  DECRYPTION_FAILED: 'CRYPTO_003',
  SIGNATURE_FAILED: 'CRYPTO_004',
  
  // Network errors
  CONNECTION_FAILED: 'NET_001',
  MESSAGE_TOO_LARGE: 'NET_002',
  PROTOCOL_ERROR: 'NET_003',
  TIMEOUT: 'NET_004',
  
  // Device errors
  DEVICE_NOT_FOUND: 'DEV_001',
  PAIRING_FAILED: 'DEV_002',
  CAPABILITY_NOT_SUPPORTED: 'DEV_003',
  DEVICE_LOCKED: 'DEV_004',
} as const;