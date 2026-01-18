/**
 * Avatar System Types
 * 
 * Core type definitions for the GURU Humanized Avatar System.
 * These types define the data structures used throughout the avatar system.
 */

// Identity and Configuration Types
export type {
  AvatarIdentity,
  AvatarIdentityConfig,
  AvatarAppearance,
  AvatarPersonality,
  FacialFeatureSet,
  EmotionalRange,
  GestureProfile,
  UserPreferences,
  AccessibilityOptions,
  CulturalPreferences
} from './AvatarIdentity';

// Common Utility Types
export type {
  Platform,
  QualityLevel,
  Gender,
  VoiceStyle,
  PersonalityTone,
  VoicePersonality,
  ExpressivenessLevel,
  GestureIntensity,
  Vector3,
  Vector2,
  ColorValue,
  BoundingBox,
  AnimationCurve,
  TimingData,
  PerformanceMetrics,
  MemoryStats,
  GPUStats,
  DigitalSignature,
  EncryptionMetadata,
  AvatarError,
  AvatarErrorType,
  FallbackMode,
  AvatarApiResponse,
  PlatformCapabilities,
  AuditLogEntry,
  TelemetryData
} from './Common';

// Emotional State Types
export type {
  EmotionalState,
  PrimaryEmotion,
  EmotionalContext,
  EmotionalTrigger,
  EmotionalTransition,
  TransitionCondition,
  EmotionalStateGraph,
  AudioFeatures,
  SentimentAnalysis,
  EmotionScores,
  CommandResult,
  EmotionalResponsiveness,
  EmotionalNormalization,
  DriftPrevention,
  EmotionalHistory,
  EmotionalPattern,
  EmotionalStatistics,
  EmotionModifier
} from './EmotionalState';

// Motion and Animation Types
export type {
  MotionFrame,
  BreathingState,
  BlinkState,
  EyePosition,
  TrackingTarget,
  PostureAdjustment,
  HeadOrientation,
  GestureFrame,
  GestureType,
  HandPosition,
  HandPose,
  FingerPosition,
  ArmPosition,
  GestureTiming,
  SynchronizationPoint,
  GestureContext,
  SpeechContext,
  AttentionFrame,
  AttentionTarget,
  MotionQuality,
  MotionSequence,
  MotionState,
  MotionStateConfig,
  AttentionBehavior,
  StateTransitionRule
} from './MotionFrame';

// Animation Frame Types
export type {
  AnimationFrame,
  FacialAnimation,
  VisemeFrame,
  EyeAnimation,
  BlinkFrame,
  BodyAnimation,
  QualityMetrics,
  RenderingHints
} from './AnimationFrame';

// Asset Management Types
export type {
  AvatarAssets,
  LoadingStrategy,
  CachePolicy
} from './AvatarAssets';

// Platform-Specific Types
export type {
  PlatformRenderingConfig,
  RenderingAPI,
  AvatarType,
  PlatformFeatures,
  PlatformPerformanceTargets
} from './Platform';