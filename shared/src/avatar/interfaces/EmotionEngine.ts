/**
 * Emotion Engine Interface
 * 
 * Processes emotional context from multiple inputs and manages smooth emotional state transitions.
 * Handles voice tone analysis, sentiment processing, command result evaluation, and emotional normalization.
 */

import {
  EmotionalState,
  PrimaryEmotion,
  AudioFeatures,
  SentimentAnalysis,
  CommandResult,
  EmotionalResponsiveness,
  EmotionalNormalization,
  DriftPrevention,
  EmotionalHistory,
  EmotionalTransition,
  EmotionalStateGraph,
  EmotionModifier
} from '../types/EmotionalState';
import { AvatarApiResponse } from '../types/Common';

/**
 * Core Emotion Engine interface for emotional state management
 */
export interface EmotionEngine {
  // State Management
  getCurrentEmotionalState(): Promise<AvatarApiResponse<EmotionalState>>;
  setEmotionalState(state: EmotionalState, transitionDuration?: number): Promise<AvatarApiResponse<void>>;
  transitionToEmotion(emotion: PrimaryEmotion, intensity: number, duration?: number): Promise<AvatarApiResponse<void>>;
  blendEmotionalStates(primary: EmotionalState, secondary: EmotionalState, blendFactor: number): Promise<AvatarApiResponse<EmotionalState>>;
  
  // Input Processing
  processVoiceTone(audioFeatures: AudioFeatures): Promise<AvatarApiResponse<EmotionalState>>;
  processSentiment(text: string, sentiment: SentimentAnalysis): Promise<AvatarApiResponse<EmotionalState>>;
  processCommandResult(result: CommandResult): Promise<AvatarApiResponse<EmotionalState>>;
  processUserInteraction(interactionType: UserInteractionType, context?: Record<string, unknown>): Promise<AvatarApiResponse<EmotionalState>>;
  
  // Normalization and Safety
  normalizeEmotionalState(): Promise<AvatarApiResponse<void>>;
  resetEmotionalDrift(): Promise<AvatarApiResponse<void>>;
  preventEmotionalOverload(maxIntensity: number): Promise<AvatarApiResponse<void>>;
  enforceEmotionalBoundaries(boundaries: EmotionalBoundaries): Promise<AvatarApiResponse<void>>;
  
  // Configuration and Control
  setEmotionalResponsiveness(responsiveness: EmotionalResponsiveness): Promise<AvatarApiResponse<void>>;
  getEmotionalResponsiveness(): Promise<AvatarApiResponse<EmotionalResponsiveness>>;
  enableUserOverride(enabled: boolean): Promise<AvatarApiResponse<void>>;
  setEmotionalStateGraph(graph: EmotionalStateGraph): Promise<AvatarApiResponse<void>>;
  
  // Advanced Features
  predictEmotionalTransition(currentState: EmotionalState, inputs: EmotionalInput[]): Promise<AvatarApiResponse<EmotionalPrediction>>;
  analyzeEmotionalPattern(history: EmotionalHistory): Promise<AvatarApiResponse<EmotionalPatternAnalysis>>;
  generateEmotionModifier(state: EmotionalState): Promise<AvatarApiResponse<EmotionModifier>>;
  
  // Drift Prevention and Stability
  configureDriftPrevention(config: DriftPrevention): Promise<AvatarApiResponse<void>>;
  configureNormalization(config: EmotionalNormalization): Promise<AvatarApiResponse<void>>;
  checkEmotionalStability(): Promise<AvatarApiResponse<EmotionalStabilityReport>>;
  
  // History and Analytics
  getEmotionalHistory(timeRange?: TimeRange): Promise<AvatarApiResponse<EmotionalHistory>>;
  clearEmotionalHistory(): Promise<AvatarApiResponse<void>>;
  exportEmotionalData(format: 'json' | 'csv'): Promise<AvatarApiResponse<string>>;
  
  // Event Handling
  onEmotionalStateChanged(callback: EmotionalStateChangeCallback): void;
  onEmotionalTransition(callback: EmotionalTransitionCallback): void;
  onEmotionalOverload(callback: EmotionalOverloadCallback): void;
  
  // System Management
  calibrateEmotionalSystem(calibrationData: EmotionalCalibrationData): Promise<AvatarApiResponse<void>>;
  validateEmotionalConfiguration(): Promise<AvatarApiResponse<ValidationResult>>;
  resetToDefaults(): Promise<AvatarApiResponse<void>>;
  
  // Performance and Optimization
  optimizePerformance(): Promise<AvatarApiResponse<void>>;
  getPerformanceMetrics(): Promise<AvatarApiResponse<EmotionEngineMetrics>>;
  cleanup(): Promise<AvatarApiResponse<void>>;
}

/**
 * Types of user interactions that can trigger emotional responses
 */
export type UserInteractionType = 
  | 'voice_command'
  | 'text_input'
  | 'gesture'
  | 'touch'
  | 'gaze'
  | 'proximity'
  | 'system_notification'
  | 'error_occurrence'
  | 'success_feedback'
  | 'timeout'
  | 'interruption';

/**
 * Emotional boundaries for safety and appropriateness
 */
export interface EmotionalBoundaries {
  maxIntensity: number; // 0.0 to 1.0
  allowedEmotions: PrimaryEmotion[];
  forbiddenEmotions: PrimaryEmotion[];
  maxTransitionSpeed: number; // 0.0 to 1.0
  culturalConstraints: CulturalConstraints;
  contextualLimits: ContextualLimits;
}

/**
 * Cultural constraints for appropriate emotional expression
 */
export interface CulturalConstraints {
  region: string;
  emotionalExpressiveness: number; // 0.0 to 1.0
  gestureAppropriateness: string[];
  eyeContactNorms: number; // 0.0 to 1.0
  personalSpacePreference: number; // 0.0 to 1.0
}

/**
 * Contextual limits based on situation
 */
export interface ContextualLimits {
  professionalMode: boolean;
  publicSetting: boolean;
  formalInteraction: boolean;
  emergencyMode: boolean;
  privacyMode: boolean;
}

/**
 * Emotional input for processing
 */
export interface EmotionalInput {
  type: 'voice' | 'text' | 'command' | 'system' | 'user';
  data: AudioFeatures | SentimentAnalysis | CommandResult | Record<string, unknown>;
  timestamp: number;
  confidence: number; // 0.0 to 1.0
  priority: number; // 0.0 to 1.0
  context?: Record<string, unknown>;
}

/**
 * Emotional prediction result
 */
export interface EmotionalPrediction {
  predictedState: EmotionalState;
  confidence: number; // 0.0 to 1.0
  transitionPath: EmotionalTransition[];
  estimatedDuration: number; // milliseconds
  factors: PredictionFactor[];
}

/**
 * Factors influencing emotional prediction
 */
export interface PredictionFactor {
  type: 'voice_tone' | 'sentiment' | 'command_result' | 'history' | 'context';
  influence: number; // -1.0 to 1.0
  confidence: number; // 0.0 to 1.0
  description: string;
}

/**
 * Emotional pattern analysis result
 */
export interface EmotionalPatternAnalysis {
  dominantEmotions: PrimaryEmotion[];
  averageIntensity: number;
  transitionFrequency: number; // transitions per hour
  stabilityScore: number; // 0.0 to 1.0
  responsiveness: number; // 0.0 to 1.0
  patterns: DetectedPattern[];
  recommendations: PatternRecommendation[];
}

/**
 * Detected emotional pattern
 */
export interface DetectedPattern {
  type: 'cycle' | 'trend' | 'spike' | 'plateau' | 'oscillation';
  emotions: PrimaryEmotion[];
  frequency: number; // occurrences per hour
  duration: number; // average duration in milliseconds
  triggers: string[];
  confidence: number; // 0.0 to 1.0
}

/**
 * Pattern-based recommendation
 */
export interface PatternRecommendation {
  type: 'configuration' | 'behavior' | 'optimization';
  description: string;
  expectedBenefit: string;
  implementation: string;
  priority: 'low' | 'medium' | 'high';
}

/**
 * Emotional stability report
 */
export interface EmotionalStabilityReport {
  stable: boolean;
  stabilityScore: number; // 0.0 to 1.0
  driftDetected: boolean;
  overloadRisk: number; // 0.0 to 1.0
  issues: StabilityIssue[];
  recommendations: string[];
  lastNormalization: Date;
}

/**
 * Stability issue
 */
export interface StabilityIssue {
  type: 'drift' | 'overload' | 'inconsistency' | 'performance';
  severity: 'low' | 'medium' | 'high' | 'critical';
  description: string;
  affectedEmotions: PrimaryEmotion[];
  suggestedFix: string;
}

/**
 * Time range for historical queries
 */
export interface TimeRange {
  start: Date;
  end: Date;
  granularity: 'second' | 'minute' | 'hour' | 'day';
}

/**
 * Emotional calibration data for system tuning
 */
export interface EmotionalCalibrationData {
  userBaseline: EmotionalState;
  voiceSamples: AudioFeatures[];
  textSamples: Array<{ text: string; expectedEmotion: PrimaryEmotion }>;
  culturalPreferences: CulturalConstraints;
  personalityProfile: PersonalityProfile;
}

/**
 * Personality profile for emotional calibration
 */
export interface PersonalityProfile {
  openness: number; // 0.0 to 1.0
  conscientiousness: number; // 0.0 to 1.0
  extraversion: number; // 0.0 to 1.0
  agreeableness: number; // 0.0 to 1.0
  neuroticism: number; // 0.0 to 1.0
  emotionalIntelligence: number; // 0.0 to 1.0
}

/**
 * Validation result for emotional configuration
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
  impact: 'performance' | 'accuracy' | 'user_experience';
  recommendation?: string;
}

/**
 * Performance impact assessment
 */
export interface PerformanceImpact {
  cpuUsage: number; // percentage increase
  memoryUsage: number; // bytes increase
  responseTime: number; // milliseconds increase
  batteryImpact: number; // percentage increase per hour
}

/**
 * Emotion Engine performance metrics
 */
export interface EmotionEngineMetrics {
  processingTime: ProcessingTimeMetrics;
  accuracy: AccuracyMetrics;
  stability: StabilityMetrics;
  resourceUsage: ResourceUsageMetrics;
  userSatisfaction: UserSatisfactionMetrics;
}

/**
 * Processing time metrics
 */
export interface ProcessingTimeMetrics {
  averageResponseTime: number; // milliseconds
  maxResponseTime: number; // milliseconds
  minResponseTime: number; // milliseconds
  timeoutRate: number; // percentage
  throughput: number; // operations per second
}

/**
 * Accuracy metrics
 */
export interface AccuracyMetrics {
  emotionRecognitionAccuracy: number; // 0.0 to 1.0
  transitionSmoothness: number; // 0.0 to 1.0
  contextualAppropriateness: number; // 0.0 to 1.0
  userAlignment: number; // 0.0 to 1.0
}

/**
 * Stability metrics
 */
export interface StabilityMetrics {
  driftRate: number; // drift events per hour
  overloadEvents: number; // overload events per hour
  recoveryTime: number; // average recovery time in milliseconds
  consistencyScore: number; // 0.0 to 1.0
}

/**
 * Resource usage metrics
 */
export interface ResourceUsageMetrics {
  cpuUsage: number; // percentage
  memoryUsage: number; // bytes
  networkUsage: number; // bytes per hour
  storageUsage: number; // bytes
  batteryDrain: number; // percentage per hour
}

/**
 * User satisfaction metrics
 */
export interface UserSatisfactionMetrics {
  overrideRate: number; // percentage of manual overrides
  feedbackScore: number; // 0.0 to 1.0
  engagementLevel: number; // 0.0 to 1.0
  naturalness: number; // 0.0 to 1.0
}

/**
 * Emotional state change callback
 */
export type EmotionalStateChangeCallback = (
  oldState: EmotionalState,
  newState: EmotionalState,
  trigger: string
) => void;

/**
 * Emotional transition callback
 */
export type EmotionalTransitionCallback = (
  transition: EmotionalTransition,
  progress: number
) => void;

/**
 * Emotional overload callback
 */
export type EmotionalOverloadCallback = (
  overloadType: 'intensity' | 'frequency' | 'duration',
  severity: number,
  recommendedAction: string
) => void;

/**
 * Emotion Engine factory for creating platform-specific implementations
 */
export interface EmotionEngineFactory {
  createEmotionEngine(config: EmotionEngineConfig): Promise<EmotionEngine>;
  getDefaultConfig(): EmotionEngineConfig;
  validateConfig(config: EmotionEngineConfig): ValidationResult;
}

/**
 * Emotion Engine configuration
 */
export interface EmotionEngineConfig {
  // Processing settings
  processingMode: 'real_time' | 'batch' | 'hybrid';
  maxProcessingTime: number; // milliseconds
  queueSize: number;
  
  // Emotional settings
  defaultState: PrimaryEmotion;
  responsiveness: EmotionalResponsiveness;
  boundaries: EmotionalBoundaries;
  
  // Stability settings
  driftPrevention: DriftPrevention;
  normalization: EmotionalNormalization;
  
  // Performance settings
  optimizeForBattery: boolean;
  cacheSize: number; // bytes
  backgroundProcessing: boolean;
  
  // Privacy settings
  localProcessingOnly: boolean;
  dataRetention: number; // milliseconds
  anonymizeData: boolean;
}