/**
 * Common types and utilities used throughout the avatar system
 */

/**
 * Supported platforms for avatar rendering
 */
export type Platform = 'windows' | 'macos' | 'android' | 'ios' | 'web';

/**
 * Quality levels for rendering and performance optimization
 */
export type QualityLevel = 'low' | 'medium' | 'high' | 'ultra';

/**
 * Gender options for avatar identity
 */
export type Gender = 'male' | 'female' | 'non-binary';

/**
 * Voice style options for avatar personality
 */
export type VoiceStyle = 'calm' | 'friendly' | 'professional' | 'energetic';

/**
 * Personality tone options
 */
export type PersonalityTone = 'co-worker' | 'best-friend' | 'assistant' | 'mentor';

/**
 * Voice personality modes
 */
export type VoicePersonality = 'formal' | 'friendly' | 'casual';

/**
 * Expressiveness levels for emotional responses
 */
export type ExpressivenessLevel = 'low' | 'medium' | 'high';

/**
 * Gesture intensity options
 */
export type GestureIntensity = 'subtle' | 'natural' | 'expressive';

/**
 * 3D vector for positions, rotations, and scales
 */
export interface Vector3 {
  x: number;
  y: number;
  z: number;
}

/**
 * 2D vector for screen coordinates and texture mapping
 */
export interface Vector2 {
  x: number;
  y: number;
}

/**
 * Color value with alpha channel
 */
export interface ColorValue {
  r: number; // 0.0 to 1.0
  g: number; // 0.0 to 1.0
  b: number; // 0.0 to 1.0
  a: number; // 0.0 to 1.0
}

/**
 * Bounding box for 3D objects
 */
export interface BoundingBox {
  min: Vector3;
  max: Vector3;
}

/**
 * Animation curve for smooth transitions
 */
export interface AnimationCurve {
  keyframes: Array<{
    time: number; // 0.0 to 1.0
    value: number;
    inTangent?: number;
    outTangent?: number;
  }>;
  interpolation: 'linear' | 'cubic' | 'bezier';
}

/**
 * Timing data for audio synchronization
 */
export interface TimingData {
  startTime: number; // milliseconds
  duration: number; // milliseconds
  confidence: number; // 0.0 to 1.0
}

/**
 * Performance metrics for monitoring
 */
export interface PerformanceMetrics {
  fps: number;
  frameTime: number; // milliseconds
  memoryUsage: number; // bytes
  cpuUsage: number; // percentage 0.0 to 1.0
  gpuUsage: number; // percentage 0.0 to 1.0
  batteryDrain?: number; // percentage per hour
}

/**
 * Memory statistics for resource monitoring
 */
export interface MemoryStats {
  used: number; // bytes
  allocated: number; // bytes
  peak: number; // bytes
  gcCount: number;
}

/**
 * GPU usage statistics
 */
export interface GPUStats {
  usage: number; // percentage 0.0 to 1.0
  memoryUsed: number; // bytes
  memoryTotal: number; // bytes
  temperature?: number; // celsius
}

/**
 * Digital signature for asset integrity
 */
export interface DigitalSignature {
  algorithm: string;
  signature: string;
  publicKey: string;
  timestamp: number;
}

/**
 * Encryption metadata for secure storage
 */
export interface EncryptionMetadata {
  algorithm: string;
  keyId: string;
  iv: string;
  timestamp: number;
}

/**
 * Error types for avatar system failures
 */
export enum AvatarErrorType {
  RENDERING_FAILURE = 'rendering_failure',
  EMOTION_PROCESSING_FAILURE = 'emotion_processing_failure',
  MOTION_GENERATION_FAILURE = 'motion_generation_failure',
  LIP_SYNC_FAILURE = 'lip_sync_failure',
  ASSET_LOADING_FAILURE = 'asset_loading_failure',
  PERFORMANCE_DEGRADATION = 'performance_degradation',
  PRIVACY_VIOLATION = 'privacy_violation',
  AUTHENTICATION_FAILURE = 'authentication_failure'
}

/**
 * Avatar system error with context
 */
export interface AvatarError {
  type: AvatarErrorType;
  message: string;
  timestamp: number;
  platform: Platform;
  context?: Record<string, unknown>;
  recoverable: boolean;
}

/**
 * Fallback modes for graceful degradation
 */
export enum FallbackMode {
  FULL_SYSTEM = 'full_system',
  REDUCED_QUALITY = 'reduced_quality',
  ESSENTIAL_MODE = 'essential_mode',
  MINIMAL_MODE = 'minimal_mode',
  TEXT_ONLY = 'text_only'
}

/**
 * API response wrapper for avatar system operations
 */
export interface AvatarApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: AvatarError;
  executionTime: number; // milliseconds
  timestamp: number;
}

/**
 * Configuration for cross-platform compatibility
 */
export interface PlatformCapabilities {
  maxTextureSize: number;
  supportedFormats: string[];
  hardwareAcceleration: boolean;
  maxVertexCount: number;
  shaderComplexity: 'basic' | 'advanced' | 'compute';
  memoryLimit: number; // bytes
  supportsFullBody: boolean;
  supportsFaceOnly: boolean;
  supports2D: boolean;
  maxFPS: number;
  batteryOptimized: boolean;
}

/**
 * Audit log entry for privacy and security compliance
 */
export interface AuditLogEntry {
  timestamp: number;
  operation: string;
  dataType: string;
  accessLevel: 'read' | 'write' | 'delete';
  authorized: boolean;
  userId?: string;
  sessionId: string;
  platform: Platform;
}

/**
 * Telemetry data for performance monitoring (privacy-safe)
 */
export interface TelemetryData {
  sessionId: string;
  platform: Platform;
  performance: PerformanceMetrics;
  errors: AvatarError[];
  featureUsage: Record<string, number>;
  timestamp: number;
  anonymized: boolean;
}