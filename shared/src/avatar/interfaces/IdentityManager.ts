/**
 * Identity Manager Interface
 * 
 * Manages user avatar customization, identity persistence, and cross-platform synchronization.
 * Handles encrypted storage, asset management, and version migration for avatar identities.
 */

import { 
  AvatarIdentity, 
  AvatarIdentityConfig
} from '../types/AvatarIdentity';

// Re-export types for external use
export type { AvatarIdentity, AvatarIdentityConfig } from '../types/AvatarIdentity';
import { 
  Platform, 
  AvatarApiResponse,
  DigitalSignature,
  EncryptionMetadata
} from '../types/Common';
import { AvatarAssets } from '../types/AvatarAssets';

/**
 * Core Identity Manager interface for avatar customization and persistence
 */
export interface IdentityManager {
  // Identity Configuration Management
  createIdentity(config: AvatarIdentityConfig): Promise<AvatarApiResponse<AvatarIdentity>>;
  updateIdentity(identity: AvatarIdentity, updates: Partial<AvatarIdentityConfig>): Promise<AvatarApiResponse<void>>;
  deleteIdentity(identityId: string): Promise<AvatarApiResponse<void>>;
  getActiveIdentity(): Promise<AvatarApiResponse<AvatarIdentity>>;
  getAllIdentities(): Promise<AvatarApiResponse<AvatarIdentity[]>>;
  setActiveIdentity(identityId: string): Promise<AvatarApiResponse<void>>;
  
  // Cross-platform Synchronization
  syncIdentityAcrossDevices(identity: AvatarIdentity): Promise<AvatarApiResponse<void>>;
  validateIdentityCompatibility(identity: AvatarIdentity, platform: Platform): Promise<AvatarApiResponse<boolean>>;
  migrateIdentityToPlatform(identity: AvatarIdentity, targetPlatform: Platform): Promise<AvatarApiResponse<AvatarIdentity>>;
  
  // Asset Management
  loadIdentityAssets(identity: AvatarIdentity, platform: Platform): Promise<AvatarApiResponse<AvatarAssets>>;
  preloadAssets(identity: AvatarIdentity, platform: Platform): Promise<AvatarApiResponse<void>>;
  validateAssetIntegrity(assets: AvatarAssets): Promise<AvatarApiResponse<boolean>>;
  
  // Version Management and Migration
  migrateIdentityVersion(identityId: string, fromVersion: string, toVersion: string): Promise<AvatarApiResponse<AvatarIdentity>>;
  getVersionHistory(identityId: string): Promise<AvatarApiResponse<VersionHistoryEntry[]>>;
  rollbackToVersion(identityId: string, version: string): Promise<AvatarApiResponse<AvatarIdentity>>;
  
  // Security and Privacy
  encryptIdentityData(identity: AvatarIdentity): Promise<AvatarApiResponse<EncryptedIdentityData>>;
  decryptIdentityData(encryptedData: EncryptedIdentityData): Promise<AvatarApiResponse<AvatarIdentity>>;
  validateIdentitySignature(identity: AvatarIdentity): Promise<AvatarApiResponse<boolean>>;
  
  // Configuration and Preferences
  getDefaultConfiguration(platform: Platform): Promise<AvatarApiResponse<AvatarIdentityConfig>>;
  validateConfiguration(config: AvatarIdentityConfig): Promise<AvatarApiResponse<ValidationResult>>;
  getConfigurationPresets(): Promise<AvatarApiResponse<ConfigurationPreset[]>>;
  
  // Event Handling
  onIdentityChanged(callback: IdentityChangeCallback): void;
  onSyncCompleted(callback: SyncCompletedCallback): void;
  onAssetLoadingProgress(callback: AssetLoadingProgressCallback): void;
  
  // Cleanup and Maintenance
  cleanup(): Promise<AvatarApiResponse<void>>;
  optimizeStorage(): Promise<AvatarApiResponse<StorageOptimizationResult>>;
  validateSystemIntegrity(): Promise<AvatarApiResponse<IntegrityCheckResult>>;
}

/**
 * Version history entry for identity tracking
 */
export interface VersionHistoryEntry {
  version: string;
  timestamp: Date;
  changes: IdentityChange[];
  platform: Platform;
  size: number; // bytes
  checksum: string;
}

/**
 * Identity change record
 */
export interface IdentityChange {
  field: string;
  oldValue: unknown;
  newValue: unknown;
  changeType: 'create' | 'update' | 'delete';
  timestamp: Date;
}

/**
 * Encrypted identity data for secure storage
 */
export interface EncryptedIdentityData {
  encryptedData: string; // base64 encoded encrypted data
  encryptionMetadata: EncryptionMetadata;
  signature: DigitalSignature;
  version: string;
}

/**
 * Configuration validation result
 */
export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
  suggestions: ConfigurationSuggestion[];
}

/**
 * Validation error
 */
export interface ValidationError {
  field: string;
  message: string;
  code: string;
  severity: 'error' | 'warning' | 'info';
}

/**
 * Validation warning
 */
export interface ValidationWarning {
  field: string;
  message: string;
  code: string;
  impact: 'performance' | 'compatibility' | 'user_experience';
}

/**
 * Configuration suggestion
 */
export interface ConfigurationSuggestion {
  field: string;
  suggestion: string;
  reason: string;
  benefit: string;
}

/**
 * Configuration preset for quick setup
 */
export interface ConfigurationPreset {
  id: string;
  name: string;
  description: string;
  config: AvatarIdentityConfig;
  tags: string[];
  popularity: number; // 0.0 to 1.0
  platform?: Platform; // platform-specific preset
}

/**
 * Storage optimization result
 */
export interface StorageOptimizationResult {
  bytesFreed: number;
  assetsRemoved: number;
  duplicatesRemoved: number;
  compressionSavings: number;
  optimizationTime: number; // milliseconds
}

/**
 * System integrity check result
 */
export interface IntegrityCheckResult {
  passed: boolean;
  checksPerformed: number;
  issuesFound: IntegrityIssue[];
  recommendedActions: string[];
  checkDuration: number; // milliseconds
}

/**
 * Integrity issue
 */
export interface IntegrityIssue {
  type: 'corruption' | 'missing_asset' | 'signature_mismatch' | 'version_conflict';
  severity: 'critical' | 'high' | 'medium' | 'low';
  description: string;
  affectedAssets: string[];
  autoFixable: boolean;
}

/**
 * Identity change callback
 */
export type IdentityChangeCallback = (
  identityId: string,
  changes: IdentityChange[],
  newIdentity: AvatarIdentity
) => void;

/**
 * Sync completed callback
 */
export type SyncCompletedCallback = (
  identityId: string,
  success: boolean,
  syncedPlatforms: Platform[],
  errors?: string[]
) => void;

/**
 * Asset loading progress callback
 */
export type AssetLoadingProgressCallback = (
  identityId: string,
  platform: Platform,
  progress: AssetLoadingProgress
) => void;

/**
 * Asset loading progress information
 */
export interface AssetLoadingProgress {
  totalAssets: number;
  loadedAssets: number;
  failedAssets: number;
  currentAsset?: string;
  bytesLoaded: number;
  totalBytes: number;
  estimatedTimeRemaining: number; // milliseconds
  loadingSpeed: number; // bytes per second
}

/**
 * Identity Manager factory for creating platform-specific implementations
 */
export interface IdentityManagerFactory {
  createIdentityManager(platform: Platform, config: IdentityManagerConfig): Promise<IdentityManager>;
  getSupportedPlatforms(): Platform[];
  getDefaultConfig(platform: Platform): IdentityManagerConfig;
}

/**
 * Identity Manager configuration
 */
export interface IdentityManagerConfig {
  // Storage configuration
  storageProvider: 'local' | 'cloud' | 'hybrid';
  encryptionEnabled: boolean;
  compressionEnabled: boolean;
  
  // Synchronization settings
  autoSync: boolean;
  syncInterval: number; // milliseconds
  conflictResolution: 'local_wins' | 'remote_wins' | 'merge' | 'manual';
  
  // Performance settings
  cacheSize: number; // bytes
  preloadAssets: boolean;
  backgroundSync: boolean;
  
  // Security settings
  signatureValidation: boolean;
  integrityChecks: boolean;
  secureDelete: boolean;
  
  // Platform-specific settings
  platformOptimizations: Record<Platform, PlatformOptimization>;
}

/**
 * Platform-specific optimization settings
 */
export interface PlatformOptimization {
  assetCompression: boolean;
  lodOptimization: boolean;
  textureCompression: string;
  meshOptimization: boolean;
  shaderOptimization: boolean;
  memoryOptimization: boolean;
}