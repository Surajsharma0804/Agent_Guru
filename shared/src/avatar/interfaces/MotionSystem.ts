/**
 * Motion System Interface
 * 
 * Generates procedural human-like movements, gestures, and micro-animations based on 
 * emotional state and context. Handles natural motion generation, attention tracking,
 * and drift prevention for realistic avatar behavior.
 */

import {
  MotionFrame,
  MotionSequence,
  MotionState,
  GestureType,
  GestureContext,
  AttentionTarget,
  PostureAdjustment,
  BreathingState,
  BlinkState
} from '../types/MotionFrame';
import { EmotionalState } from '../types/EmotionalState';
import { Vector3, Vector2, AvatarApiResponse } from '../types/Common';

/**
 * Core Motion System interface for procedural animation generation
 */
export interface MotionSystem {
  // Motion Generation
  generateMicroMovements(): Promise<AvatarApiResponse<MotionFrame>>;
  generateContextualGesture(context: GestureContext): Promise<AvatarApiResponse<MotionSequence>>;
  generateEmotionalPosture(emotion: EmotionalState): Promise<AvatarApiResponse<PostureAdjustment>>;
  generateBreathingAnimation(rate: number, intensity: number): Promise<AvatarApiResponse<BreathingState>>;
  generateBlinkingPattern(naturalness: number): Promise<AvatarApiResponse<BlinkState>>;
  
  // State Management
  enterListeningMode(): Promise<AvatarApiResponse<void>>;
  enterSpeakingMode(): Promise<AvatarApiResponse<void>>;
  enterThinkingMode(): Promise<AvatarApiResponse<void>>;
  enterIdleMode(): Promise<AvatarApiResponse<void>>;
  getCurrentMotionState(): Promise<AvatarApiResponse<MotionState>>;
  setMotionState(state: MotionState, transitionDuration?: number): Promise<AvatarApiResponse<void>>;
  
  // Attention and Focus
  setAttentionTarget(target: AttentionTarget): Promise<AvatarApiResponse<void>>;
  clearAttentionTarget(): Promise<AvatarApiResponse<void>>;
  trackAudioSource(direction: Vector3, confidence: number): Promise<AvatarApiResponse<void>>;
  setGazeDirection(direction: Vector3, smooth: boolean): Promise<AvatarApiResponse<void>>;
  
  // Gesture Management
  playGesture(gestureId: string, intensity?: number): Promise<AvatarApiResponse<void>>;
  stopGesture(gestureId: string, fadeOut?: boolean): Promise<AvatarApiResponse<void>>;
  blendGestures(gestures: GestureBlendData[]): Promise<AvatarApiResponse<void>>;
  getAvailableGestures(context?: GestureContext): Promise<AvatarApiResponse<GestureInfo[]>>;
  
  // Motion Quality and Naturalism
  preventMotionDrift(): Promise<AvatarApiResponse<void>>;
  randomizeIdleMotions(): Promise<AvatarApiResponse<void>>;
  validateMotionNaturalness(): Promise<AvatarApiResponse<MotionQualityReport>>;
  optimizeMotionQuality(targetQuality: number): Promise<AvatarApiResponse<void>>;
  
  // Advanced Motion Features
  generateProceduralAnimation(parameters: ProceduralAnimationParams): Promise<AvatarApiResponse<MotionSequence>>;
  adaptMotionToEmotion(motion: MotionFrame, emotion: EmotionalState): Promise<AvatarApiResponse<MotionFrame>>;
  synchronizeWithSpeech(speechTiming: SpeechTimingData): Promise<AvatarApiResponse<void>>;
  
  // Configuration and Customization
  setMotionConfiguration(config: MotionSystemConfig): Promise<AvatarApiResponse<void>>;
  getMotionConfiguration(): Promise<AvatarApiResponse<MotionSystemConfig>>;
  calibrateMotionSystem(calibrationData: MotionCalibrationData): Promise<AvatarApiResponse<void>>;
  
  // Performance and Optimization
  optimizePerformance(targetFPS: number): Promise<AvatarApiResponse<void>>;
  getPerformanceMetrics(): Promise<AvatarApiResponse<MotionSystemMetrics>>;
  setQualityLevel(level: 'low' | 'medium' | 'high' | 'ultra'): Promise<AvatarApiResponse<void>>;
  
  // Event Handling
  onMotionStateChanged(callback: MotionStateChangeCallback): void;
  onGestureStarted(callback: GestureEventCallback): void;
  onGestureCompleted(callback: GestureEventCallback): void;
  onAttentionChanged(callback: AttentionChangeCallback): void;
  
  // System Management
  resetMotionSystem(): Promise<AvatarApiResponse<void>>;
  validateMotionConfiguration(): Promise<AvatarApiResponse<ValidationResult>>;
  cleanup(): Promise<AvatarApiResponse<void>>;
}

/**
 * Gesture blend data for combining multiple gestures
 */
export interface GestureBlendData {
  gestureId: string;
  weight: number; // 0.0 to 1.0
  priority: number;
  fadeIn?: number; // milliseconds
  fadeOut?: number; // milliseconds
}

/**
 * Gesture information
 */
export interface GestureInfo {
  id: string;
  name: string;
  type: GestureType;
  duration: number; // milliseconds
  intensity: number; // 0.0 to 1.0
  tags: string[];
  emotionalContext: string[];
  culturalAppropriateness: number; // 0.0 to 1.0
  complexity: 'simple' | 'moderate' | 'complex';
  bodyParts: BodyPart[];
}

/**
 * Body parts involved in motion
 */
export type BodyPart = 
  | 'head'
  | 'eyes'
  | 'eyebrows'
  | 'mouth'
  | 'neck'
  | 'shoulders'
  | 'arms'
  | 'hands'
  | 'fingers'
  | 'torso'
  | 'hips'
  | 'legs'
  | 'feet';

/**
 * Motion quality report
 */
export interface MotionQualityReport {
  overallQuality: number; // 0.0 to 1.0
  naturalness: number; // 0.0 to 1.0
  smoothness: number; // 0.0 to 1.0
  responsiveness: number; // 0.0 to 1.0
  consistency: number; // 0.0 to 1.0
  issues: MotionQualityIssue[];
  recommendations: string[];
}

/**
 * Motion quality issue
 */
export interface MotionQualityIssue {
  type: 'jitter' | 'drift' | 'repetition' | 'unnatural_timing' | 'poor_blending';
  severity: 'low' | 'medium' | 'high';
  description: string;
  affectedBodyParts: BodyPart[];
  suggestedFix: string;
  autoFixable: boolean;
}

/**
 * Procedural animation parameters
 */
export interface ProceduralAnimationParams {
  type: 'idle' | 'gesture' | 'expression' | 'transition';
  duration: number; // milliseconds
  intensity: number; // 0.0 to 1.0
  emotionalContext: EmotionalState;
  bodyParts: BodyPart[];
  constraints: MotionConstraint[];
  randomSeed?: number;
}

/**
 * Motion constraint for procedural generation
 */
export interface MotionConstraint {
  type: 'position' | 'rotation' | 'velocity' | 'acceleration';
  bodyPart: BodyPart;
  min: Vector3;
  max: Vector3;
  weight: number; // 0.0 to 1.0
}

/**
 * Speech timing data for motion synchronization
 */
export interface SpeechTimingData {
  words: WordTiming[];
  sentences: SentenceTiming[];
  emphasis: EmphasisTiming[];
  pauses: PauseTiming[];
  totalDuration: number; // milliseconds
}

/**
 * Word timing information
 */
export interface WordTiming {
  word: string;
  startTime: number; // milliseconds
  duration: number; // milliseconds
  emphasis: number; // 0.0 to 1.0
  phonemes: PhonemeTiming[];
}

/**
 * Sentence timing information
 */
export interface SentenceTiming {
  text: string;
  startTime: number; // milliseconds
  duration: number; // milliseconds
  type: 'statement' | 'question' | 'exclamation';
  sentiment: number; // -1.0 to 1.0
}

/**
 * Emphasis timing information
 */
export interface EmphasisTiming {
  startTime: number; // milliseconds
  duration: number; // milliseconds
  intensity: number; // 0.0 to 1.0
  type: 'stress' | 'pitch' | 'volume';
}

/**
 * Pause timing information
 */
export interface PauseTiming {
  startTime: number; // milliseconds
  duration: number; // milliseconds
  type: 'breath' | 'comma' | 'period' | 'thinking';
}

/**
 * Phoneme timing for detailed lip sync
 */
export interface PhonemeTiming {
  phoneme: string;
  startTime: number; // milliseconds
  duration: number; // milliseconds
  confidence: number; // 0.0 to 1.0
}

/**
 * Motion system configuration
 */
export interface MotionSystemConfig {
  // Quality settings
  qualityLevel: 'low' | 'medium' | 'high' | 'ultra';
  targetFPS: number;
  smoothingFactor: number; // 0.0 to 1.0
  
  // Behavior settings
  naturalness: number; // 0.0 to 1.0
  responsiveness: number; // 0.0 to 1.0
  gestureFrequency: number; // gestures per minute
  microMovementIntensity: number; // 0.0 to 1.0
  
  // Drift prevention
  driftPreventionEnabled: boolean;
  driftCheckInterval: number; // milliseconds
  maxDriftThreshold: number; // 0.0 to 1.0
  
  // Cultural settings
  culturalStyle: string;
  gestureAppropriateness: number; // 0.0 to 1.0
  eyeContactLevel: number; // 0.0 to 1.0
  personalSpaceRespect: number; // 0.0 to 1.0
  
  // Performance settings
  optimizeForBattery: boolean;
  backgroundProcessing: boolean;
  cacheSize: number; // bytes
  
  // Platform-specific settings
  platformOptimizations: Record<string, unknown>;
}

/**
 * Motion calibration data
 */
export interface MotionCalibrationData {
  userPreferences: UserMotionPreferences;
  culturalContext: CulturalMotionContext;
  physicalConstraints: PhysicalConstraints;
  performanceTargets: PerformanceTargets;
}

/**
 * User motion preferences
 */
export interface UserMotionPreferences {
  gestureIntensity: number; // 0.0 to 1.0
  eyeContactComfort: number; // 0.0 to 1.0
  personalSpacePreference: number; // 0.0 to 1.0
  motionSensitivity: number; // 0.0 to 1.0
  preferredGestureTypes: GestureType[];
  dislikedGestureTypes: GestureType[];
}

/**
 * Cultural motion context
 */
export interface CulturalMotionContext {
  region: string;
  gestureNorms: GestureNorm[];
  eyeContactNorms: EyeContactNorm;
  proximityNorms: ProximityNorm;
  formalityLevel: number; // 0.0 to 1.0
}

/**
 * Gesture norm for cultural appropriateness
 */
export interface GestureNorm {
  gestureType: GestureType;
  appropriateness: number; // 0.0 to 1.0
  context: string[];
  alternatives: string[];
}

/**
 * Eye contact norm
 */
export interface EyeContactNorm {
  directContactLevel: number; // 0.0 to 1.0
  gazeAversionFrequency: number; // 0.0 to 1.0
  contextualVariations: Record<string, number>;
}

/**
 * Proximity norm
 */
export interface ProximityNorm {
  personalDistance: number; // meters
  socialDistance: number; // meters
  publicDistance: number; // meters
  intimateDistance: number; // meters
}

/**
 * Physical constraints for motion generation
 */
export interface PhysicalConstraints {
  jointLimits: Record<string, JointLimit>;
  reachLimits: ReachLimit[];
  balanceConstraints: BalanceConstraint[];
  collisionAvoidance: CollisionAvoidanceRule[];
}

/**
 * Joint limit constraint
 */
export interface JointLimit {
  minRotation: Vector3;
  maxRotation: Vector3;
  stiffness: number; // 0.0 to 1.0
  damping: number; // 0.0 to 1.0
}

/**
 * Reach limit constraint
 */
export interface ReachLimit {
  bodyPart: BodyPart;
  maxReach: number; // meters
  comfortableReach: number; // meters
  preferredZone: BoundingVolume;
}

/**
 * Bounding volume for spatial constraints
 */
export interface BoundingVolume {
  type: 'sphere' | 'box' | 'cylinder' | 'capsule';
  center: Vector3;
  dimensions: Vector3;
}

/**
 * Balance constraint
 */
export interface BalanceConstraint {
  centerOfMass: Vector3;
  supportBase: Vector2[];
  stabilityMargin: number; // meters
  recoveryTime: number; // milliseconds
}

/**
 * Collision avoidance rule
 */
export interface CollisionAvoidanceRule {
  bodyPartA: BodyPart;
  bodyPartB: BodyPart;
  minDistance: number; // meters
  avoidanceStrength: number; // 0.0 to 1.0
}

/**
 * Performance targets for motion system
 */
export interface PerformanceTargets {
  targetFPS: number;
  maxCPUUsage: number; // percentage
  maxMemoryUsage: number; // bytes
  maxLatency: number; // milliseconds
  batteryEfficiency: number; // 0.0 to 1.0
}

/**
 * Motion system performance metrics
 */
export interface MotionSystemMetrics {
  performance: MotionPerformanceMetrics;
  quality: MotionQualityMetrics;
  usage: MotionUsageMetrics;
  errors: MotionErrorMetrics;
}

/**
 * Motion performance metrics
 */
export interface MotionPerformanceMetrics {
  averageFPS: number;
  frameDrops: number;
  processingTime: number; // milliseconds
  memoryUsage: number; // bytes
  cpuUsage: number; // percentage
  gpuUsage: number; // percentage
}

/**
 * Motion quality metrics
 */
export interface MotionQualityMetrics {
  naturalness: number; // 0.0 to 1.0
  smoothness: number; // 0.0 to 1.0
  responsiveness: number; // 0.0 to 1.0
  consistency: number; // 0.0 to 1.0
  gestureVariety: number; // 0.0 to 1.0
  driftOccurrences: number;
}

/**
 * Motion usage metrics
 */
export interface MotionUsageMetrics {
  gesturesGenerated: number;
  microMovementsGenerated: number;
  stateTransitions: number;
  attentionChanges: number;
  averageSessionDuration: number; // milliseconds
}

/**
 * Motion error metrics
 */
export interface MotionErrorMetrics {
  generationFailures: number;
  qualityIssues: number;
  performanceViolations: number;
  constraintViolations: number;
  recoveryTime: number; // milliseconds
}

/**
 * Validation result for motion configuration
 */
export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
  performance: PerformanceImpact;
}

/**
 * Validation error
 */
export interface ValidationError {
  field: string;
  message: string;
  severity: 'error' | 'warning';
  suggestedFix?: string;
}

/**
 * Validation warning
 */
export interface ValidationWarning {
  field: string;
  message: string;
  impact: 'performance' | 'quality' | 'compatibility';
  recommendation?: string;
}

/**
 * Performance impact assessment
 */
export interface PerformanceImpact {
  cpuIncrease: number; // percentage
  memoryIncrease: number; // bytes
  fpsDecrease: number;
  batteryImpact: number; // percentage per hour
}

/**
 * Motion state change callback
 */
export type MotionStateChangeCallback = (
  oldState: MotionState,
  newState: MotionState,
  transitionDuration: number
) => void;

/**
 * Gesture event callback
 */
export type GestureEventCallback = (
  gestureId: string,
  gestureType: GestureType,
  context: GestureContext
) => void;

/**
 * Attention change callback
 */
export type AttentionChangeCallback = (
  oldTarget: AttentionTarget | null,
  newTarget: AttentionTarget | null,
  transitionTime: number
) => void;

/**
 * Motion System factory for creating platform-specific implementations
 */
export interface MotionSystemFactory {
  createMotionSystem(config: MotionSystemConfig): Promise<MotionSystem>;
  getDefaultConfig(): MotionSystemConfig;
  validateConfig(config: MotionSystemConfig): ValidationResult;
  getSupportedFeatures(): MotionSystemFeature[];
}

/**
 * Motion system features
 */
export type MotionSystemFeature = 
  | 'full_body_motion'
  | 'facial_motion'
  | 'hand_tracking'
  | 'eye_tracking'
  | 'procedural_generation'
  | 'emotion_adaptation'
  | 'speech_synchronization'
  | 'attention_tracking'
  | 'gesture_recognition'
  | 'drift_prevention';