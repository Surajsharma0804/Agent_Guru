/**
 * Emotional state management and transition types
 */

import { AnimationCurve } from './Common';

/**
 * Primary emotional states supported by the avatar system
 */
export type PrimaryEmotion = 
  | 'neutral'
  | 'happy'
  | 'focused'
  | 'curious'
  | 'concerned'
  | 'confident'
  | 'apologetic'
  | 'excited';

/**
 * Complete emotional state representation
 */
export interface EmotionalState {
  primary: PrimaryEmotion;
  intensity: number; // 0.0 to 1.0
  secondary?: EmotionalState;
  timestamp: number;
  transitionSpeed: number; // 0.0 to 1.0
  duration?: number; // milliseconds, undefined for indefinite
  context?: EmotionalContext;
}

/**
 * Context information for emotional state
 */
export interface EmotionalContext {
  trigger: EmotionalTrigger;
  confidence: number; // 0.0 to 1.0
  source: 'voice' | 'text' | 'command' | 'system' | 'user';
  metadata?: Record<string, unknown>;
}

/**
 * Types of emotional triggers
 */
export type EmotionalTrigger = 
  | 'voice_tone_change'
  | 'positive_sentiment'
  | 'negative_sentiment'
  | 'command_success'
  | 'command_failure'
  | 'user_interaction'
  | 'system_event'
  | 'timeout'
  | 'manual_override';

/**
 * Emotional transition configuration
 */
export interface EmotionalTransition {
  from: PrimaryEmotion;
  to: PrimaryEmotion;
  duration: number; // milliseconds
  curve: AnimationCurve;
  conditions?: TransitionCondition[];
  priority: number; // higher priority transitions override lower ones
}

/**
 * Conditions for emotional transitions
 */
export interface TransitionCondition {
  type: 'intensity_threshold' | 'time_elapsed' | 'trigger_type' | 'user_override';
  value: number | string | boolean;
  operator: 'gt' | 'lt' | 'eq' | 'ne' | 'gte' | 'lte';
}

/**
 * Emotional state graph for valid transitions
 */
export interface EmotionalStateGraph {
  states: PrimaryEmotion[];
  transitions: EmotionalTransition[];
  defaultState: PrimaryEmotion;
  maxIntensity: number;
  decayRate: number; // intensity decay per second
}

/**
 * Audio features for voice tone analysis
 */
export interface AudioFeatures {
  pitch: number; // Hz
  energy: number; // 0.0 to 1.0
  spectralCentroid: number; // Hz
  zeroCrossingRate: number; // 0.0 to 1.0
  mfcc: number[]; // Mel-frequency cepstral coefficients
  tempo?: number; // BPM
  confidence: number; // 0.0 to 1.0
}

/**
 * Sentiment analysis result
 */
export interface SentimentAnalysis {
  polarity: number; // -1.0 to 1.0 (negative to positive)
  subjectivity: number; // 0.0 to 1.0 (objective to subjective)
  emotions: EmotionScores;
  confidence: number; // 0.0 to 1.0
  language?: string;
}

/**
 * Emotion scores from sentiment analysis
 */
export interface EmotionScores {
  joy: number; // 0.0 to 1.0
  sadness: number; // 0.0 to 1.0
  anger: number; // 0.0 to 1.0
  fear: number; // 0.0 to 1.0
  surprise: number; // 0.0 to 1.0
  disgust: number; // 0.0 to 1.0
  trust: number; // 0.0 to 1.0
  anticipation: number; // 0.0 to 1.0
}

/**
 * Command result context for emotional response
 */
export interface CommandResult {
  success: boolean;
  command: string;
  executionTime: number; // milliseconds
  errorType?: string;
  userFeedback?: 'positive' | 'negative' | 'neutral';
  context?: Record<string, unknown>;
}

/**
 * Emotional responsiveness configuration
 */
export interface EmotionalResponsiveness {
  level: 'low' | 'medium' | 'high';
  voiceSensitivity: number; // 0.0 to 1.0
  textSensitivity: number; // 0.0 to 1.0
  commandSensitivity: number; // 0.0 to 1.0
  adaptationRate: number; // how quickly to adapt to user patterns
  userOverrideEnabled: boolean;
}

/**
 * Emotional state normalization settings
 */
export interface EmotionalNormalization {
  enabled: boolean;
  interval: number; // milliseconds between normalizations
  targetState: PrimaryEmotion;
  decayRate: number; // intensity reduction per normalization
  preservePositive: boolean; // whether to preserve positive emotions longer
}

/**
 * Emotional drift prevention configuration
 */
export interface DriftPrevention {
  enabled: boolean;
  maxDuration: number; // maximum time in any non-neutral state (milliseconds)
  intensityThreshold: number; // maximum sustained intensity
  resetInterval: number; // forced reset interval (milliseconds)
  gradualReturn: boolean; // whether to gradually return to neutral
}

/**
 * Emotional state history for pattern analysis
 */
export interface EmotionalHistory {
  states: Array<{
    state: EmotionalState;
    timestamp: number;
    duration: number;
  }>;
  patterns: EmotionalPattern[];
  statistics: EmotionalStatistics;
}

/**
 * Detected emotional patterns
 */
export interface EmotionalPattern {
  type: 'cycle' | 'trend' | 'spike' | 'plateau';
  states: PrimaryEmotion[];
  frequency: number; // occurrences per hour
  confidence: number; // 0.0 to 1.0
  triggers: EmotionalTrigger[];
}

/**
 * Statistical analysis of emotional behavior
 */
export interface EmotionalStatistics {
  averageIntensity: number;
  mostCommonState: PrimaryEmotion;
  transitionFrequency: Record<string, number>;
  timeInStates: Record<PrimaryEmotion, number>; // milliseconds
  responsiveness: number; // how quickly emotions change
}

/**
 * Emotional modulation for other systems
 */
export interface EmotionModifier {
  facialExpression: number; // 0.0 to 1.0 multiplier
  gestureIntensity: number; // 0.0 to 1.0 multiplier
  voiceTone: number; // -1.0 to 1.0 (lower to higher pitch)
  movementSpeed: number; // 0.0 to 2.0 multiplier
  eyeContact: number; // 0.0 to 1.0 (avoidance to direct)
  posture: number; // -1.0 to 1.0 (closed to open)
}