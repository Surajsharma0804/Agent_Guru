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

/**
 * CONSOLIDATED VALIDATION TYPES
 * Previously duplicated across 5 subsystems - now centralized for consistency
 */

/**
 * Validation error severity levels
 */
export type ValidationSeverity = 'error' | 'warning' | 'info';

/**
 * Validation error codes for categorization
 */
export type ValidationErrorCode = 
  | 'REQUIRED_FIELD'
  | 'INVALID_ENUM_VALUE'
  | 'INVALID_FORMAT'
  | 'INVALID_RANGE'
  | 'MINIMAL_MODE_CONFLICT'
  | 'BUSINESS_RULE_VIOLATION'
  | 'SECURITY_CONSTRAINT_VIOLATION'
  | 'PLATFORM_INCOMPATIBILITY'
  | 'PERFORMANCE_CONSTRAINT_VIOLATION';

/**
 * Standardized validation error structure
 */
export interface ValidationError {
  field: string;
  message: string;
  code: ValidationErrorCode;
  severity: ValidationSeverity;
  context?: Record<string, unknown>;
}

/**
 * Standardized validation warning structure
 */
export interface ValidationWarning {
  field: string;
  message: string;
  code: ValidationErrorCode;
  severity: ValidationSeverity;
  suggestion?: string;
  context?: Record<string, unknown>;
}

/**
 * Configuration suggestion for optimization
 */
export interface ConfigurationSuggestion {
  field: string;
  currentValue: unknown;
  suggestedValue: unknown;
  reason: string;
  impact: 'performance' | 'quality' | 'compatibility' | 'security';
  priority: 'low' | 'medium' | 'high' | 'critical';
}

/**
 * Comprehensive validation result
 */
export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
  suggestions: ConfigurationSuggestion[];
  validationTime?: number;
  rulesApplied?: string[];
}

/**
 * Performance impact assessment
 */
export interface PerformanceImpact {
  cpuUsage: number; // percentage increase
  memoryUsage: number; // bytes increase
  batteryDrain: number; // percentage increase per hour
  renderingLoad: number; // percentage increase
  networkUsage: number; // bytes per minute
  storageUsage: number; // bytes
}

/**
 * Security constraint validation
 */
export interface SecurityConstraint {
  name: string;
  description: string;
  enforced: boolean;
  severity: 'low' | 'medium' | 'high' | 'critical';
  violationAction: 'warn' | 'block' | 'audit';
}

/**
 * Business rule definition
 */
export interface BusinessRule {
  id: string;
  name: string;
  description: string;
  condition: string; // JavaScript expression
  action: 'validate' | 'transform' | 'reject';
  priority: number;
  enabled: boolean;
}

/**
 * LIP SYNC SYSTEM TYPES
 * Production-grade types for real-time audio-to-viseme conversion
 */

/**
 * Lip sync configuration for audio processing
 */
export interface LipSyncConfig {
  fftSize?: number;
  smoothingTimeConstant?: number;
  visemeCount: number;
  transitionDuration?: number;
  smoothingFactor?: number;
  breathingRate?: number;
  breathingIntensity?: number;
  targetFrameRate?: number;
}

/**
 * Individual viseme with timing and weight
 */
export interface Viseme {
  name: string;
  weight: number; // 0.0 to 1.0
  duration: number; // milliseconds
  timestamp: number;
}

/**
 * Viseme weights for all mouth shapes
 */
export interface VisemeWeights {
  sil: number; // silence
  a: number;   // 'a' sound
  e: number;   // 'e' sound
  i: number;   // 'i' sound
  o: number;   // 'o' sound
  u: number;   // 'u' sound
  m: number;   // 'm', 'n' sounds
  p: number;   // 'p', 'b', 'f', 'v' sounds
}

/**
 * Individual phoneme with confidence and timing
 */
export interface Phoneme {
  symbol: string;
  duration: number; // milliseconds
  confidence: number; // 0.0 to 1.0
  visemeIndex?: number;
}

/**
 * Phoneme analysis result from audio processing
 */
export interface PhonemeAnalysis {
  phonemes: Phoneme[];
  confidence: number; // 0.0 to 1.0
  timing: number[];
  quality: QualityLevel;
}

/**
 * Spectral analysis data for phoneme detection
 */
export interface SpectralAnalysis {
  spectrum: number[];
  spectralCentroid: number;
  spectralRolloff: number;
  spectralFlux: number;
}

/**
 * Lip sync processing metrics
 */
export interface LipSyncMetrics {
  totalProcessingTime: number;
  frameCount: number;
  averageProcessingTime: number;
  phonemeAccuracy: number;
  visemeAccuracy: number;
  syncAccuracy: number;
}

/**
 * Viseme transition state for smooth animations
 */
export interface VisemeTransitionState {
  currentViseme: number;
  targetViseme: number;
  transitionProgress: number; // 0.0 to 1.0
  transitionDuration: number; // milliseconds
}

/**
 * Breathing modulation for natural lip movement
 */
export interface BreathingModulation {
  intensity: number; // 0.0 to 1.0
  phase: number; // radians
  rate: number; // Hz
}

/**
 * Emotional modulation for expressive lip sync
 */
export interface EmotionalModulation {
  state: string;
  intensity: number; // 0.0 to 1.0
  transition: number; // 0.0 to 1.0
  modulation: number[]; // per-viseme modulation factors
}

/**
 * Performance optimization parameters
 */
export interface OptimizationParams {
  level: number; // 0.0 to 1.0
  quality: QualityLevel;
  adaptiveEnabled: boolean;
}

/**
 * Synchronization validation result
 */
export interface SyncValidation {
  accuracy: number; // 0.0 to 1.0
  timeDelta: number; // milliseconds
  isInSync: boolean;
  frameDropped: boolean;
}

/**
 * Complete lip sync processing result
 */
export interface LipSyncResult {
  visemes: Viseme[];
  confidence: number; // 0.0 to 1.0
  timing: number[];
  metadata: {
    processingTime: number;
    quality: QualityLevel;
    breathingIntensity?: number;
    emotionalState?: string;
    optimizationLevel?: number;
    syncAccuracy?: number;
  };
  warnings: string[];
  suggestions: string[];
}

/**
 * PLATFORM RENDERER TYPES
 * Production-grade types for cross-platform avatar rendering
 */

/**
 * Render configuration for platform-specific rendering
 */
export interface RenderConfig {
  platform: Platform;
  quality: QualityLevel;
  width: number;
  height: number;
  targetFPS: number;
  enableHardwareAcceleration: boolean;
  enableShadows: boolean;
  enablePostProcessing: boolean;
  enableAntiAliasing: boolean;
  maxFPS?: number;
  enableVSync?: boolean;
  antiAliasing?: number;
  shadowQuality?: QualityLevel;
  textureQuality?: QualityLevel;
  enableBloom?: boolean;
  enableSSAO?: boolean;
  enableMotionBlur?: boolean;
  renderScale?: number;
  maxLights?: number;
  maxBones?: number;
  enableInstancing?: boolean;
  enableFrustumCulling?: boolean;
  enableOcclusionCulling?: boolean;
  memoryBudget?: number;
  enableDebugMode?: boolean;
}

/**
 * Current rendering state
 */
export interface RenderState {
  isInitialized: boolean;
  isRendering: boolean;
  currentFrame: number;
  renderTime: number;
  quality: number;
  errors: string[];
}

/**
 * Avatar state for rendering
 */
export interface AvatarState {
  transform?: Float32Array;
  boneTransforms?: Float32Array;
  blendShapes?: Record<string, number>;
  [key: string]: unknown;
}