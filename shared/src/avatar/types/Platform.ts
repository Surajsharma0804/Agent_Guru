/**
 * Platform-specific types and configurations for avatar rendering
 */

import { Platform, QualityLevel, PlatformCapabilities } from './Common';

/**
 * Platform-specific rendering configuration
 */
export interface PlatformRenderingConfig {
  platform: Platform;
  quality: QualityLevel;
  targetFPS: number;
  memoryLimit: number; // bytes
  renderingAPI: RenderingAPI;
  avatarType: AvatarType;
  features: PlatformFeatures;
}

/**
 * Supported rendering APIs by platform
 */
export type RenderingAPI = 
  | 'directx12' 
  | 'vulkan' 
  | 'metal' 
  | 'opengl_es' 
  | 'webgl' 
  | 'webgpu';

/**
 * Avatar rendering types based on platform capabilities
 */
export type AvatarType = 'full_body_3d' | 'face_only_3d' | 'upper_body_2_5d' | 'static_2d';

/**
 * Platform-specific feature support
 */
export interface PlatformFeatures {
  dynamicLighting: boolean;
  realTimeShadows: boolean;
  textureCompression: boolean;
  morphTargets: boolean;
  proceduralAnimation: boolean;
  audioProcessing: boolean;
  cameraAccess: boolean;
  backgroundProcessing: boolean;
  pushNotifications: boolean;
  fileSystemAccess: boolean;
}

/**
 * Platform detection result
 */
export interface PlatformDetectionResult {
  platform: Platform;
  version: string;
  capabilities: PlatformCapabilities;
  recommendedConfig: PlatformRenderingConfig;
  limitations: string[];
  warnings: string[];
}

/**
 * Platform-specific asset requirements
 */
export interface PlatformAssetRequirements {
  platform: Platform;
  maxTextureResolution: number;
  supportedTextureFormats: string[];
  maxMeshComplexity: number;
  compressionRequired: boolean;
  lodLevelsRequired: number;
  shaderVersions: string[];
}

/**
 * Cross-platform consistency validation
 */
export interface ConsistencyValidation {
  behaviorVariance: number; // percentage difference allowed
  timingTolerance: number; // milliseconds
  visualFidelityThreshold: number; // 0.0 to 1.0
  performanceVariance: number; // percentage difference allowed
}

/**
 * Platform optimization strategy
 */
export interface OptimizationStrategy {
  platform: Platform;
  batteryOptimization: boolean;
  memoryOptimization: boolean;
  thermalOptimization: boolean;
  networkOptimization: boolean;
  adaptiveQuality: boolean;
  backgroundBehavior: 'suspend' | 'reduce' | 'maintain';
}

/**
 * Platform-specific performance targets
 */
export interface PlatformPerformanceTargets {
  platform: Platform;
  minFPS: number;
  maxMemoryUsage: number; // bytes
  maxCPUUsage: number; // percentage
  maxGPUUsage: number; // percentage
  maxStartupTime: number; // milliseconds
  maxBatteryDrain?: number; // percentage per hour
  maxThermalImpact?: number; // celsius increase
}

/**
 * Platform migration data for cross-device synchronization
 */
export interface PlatformMigrationData {
  sourceplatform: Platform;
  targetPlatform: Platform;
  identityData: unknown; // Encrypted identity configuration
  assetMappings: Record<string, string>;
  featureMappings: Record<string, string>;
  performanceAdjustments: Record<string, number>;
  migrationTimestamp: number;
}