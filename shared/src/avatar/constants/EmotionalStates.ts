/**
 * Emotional states constants and configuration
 */

import { PrimaryEmotion, EmotionalStateGraph } from '../types/EmotionalState';

/**
 * All supported primary emotional states
 */
export const PRIMARY_EMOTIONS: readonly PrimaryEmotion[] = [
  'neutral',
  'happy',
  'focused',
  'curious',
  'concerned',
  'confident',
  'apologetic',
  'excited'
] as const;

/**
 * Default emotional state
 */
export const DEFAULT_EMOTIONAL_STATE: PrimaryEmotion = 'neutral';

/**
 * Maximum emotional intensity
 */
export const MAX_EMOTIONAL_INTENSITY = 1.0;

/**
 * Minimum emotional intensity
 */
export const MIN_EMOTIONAL_INTENSITY = 0.0;

/**
 * Default emotional intensity
 */
export const DEFAULT_EMOTIONAL_INTENSITY = 0.5;

/**
 * Maximum transition speed (instantaneous)
 */
export const MAX_TRANSITION_SPEED = 1.0;

/**
 * Minimum transition speed (very slow)
 */
export const MIN_TRANSITION_SPEED = 0.01;

/**
 * Default transition speed
 */
export const DEFAULT_TRANSITION_SPEED = 0.3;

/**
 * Default emotional decay rate (intensity reduction per second)
 */
export const DEFAULT_DECAY_RATE = 0.1;

/**
 * Emotional drift prevention interval (milliseconds)
 */
export const DRIFT_PREVENTION_INTERVAL = 60000; // 1 minute

/**
 * Emotional normalization interval (milliseconds)
 */
export const NORMALIZATION_INTERVAL = 3600000; // 1 hour

/**
 * Maximum time in any non-neutral state (milliseconds)
 */
export const MAX_NON_NEUTRAL_DURATION = 1800000; // 30 minutes

/**
 * Default emotional state graph with valid transitions
 */
export const DEFAULT_EMOTIONAL_STATE_GRAPH: EmotionalStateGraph = {
  states: [...PRIMARY_EMOTIONS],
  transitions: [
    // From Neutral
    {
      from: 'neutral',
      to: 'happy',
      duration: 1000,
      curve: {
        keyframes: [
          { time: 0.0, value: 0.0 },
          { time: 0.3, value: 0.7 },
          { time: 1.0, value: 1.0 }
        ],
        interpolation: 'cubic'
      },
      priority: 1
    },
    {
      from: 'neutral',
      to: 'focused',
      duration: 800,
      curve: {
        keyframes: [
          { time: 0.0, value: 0.0 },
          { time: 0.5, value: 0.8 },
          { time: 1.0, value: 1.0 }
        ],
        interpolation: 'linear'
      },
      priority: 1
    },
    {
      from: 'neutral',
      to: 'curious',
      duration: 600,
      curve: {
        keyframes: [
          { time: 0.0, value: 0.0 },
          { time: 0.2, value: 0.6 },
          { time: 1.0, value: 1.0 }
        ],
        interpolation: 'cubic'
      },
      priority: 1
    },
    {
      from: 'neutral',
      to: 'concerned',
      duration: 500,
      curve: {
        keyframes: [
          { time: 0.0, value: 0.0 },
          { time: 0.1, value: 0.5 },
          { time: 1.0, value: 1.0 }
        ],
        interpolation: 'linear'
      },
      priority: 2
    },

    // From Happy
    {
      from: 'happy',
      to: 'excited',
      duration: 800,
      curve: {
        keyframes: [
          { time: 0.0, value: 0.0 },
          { time: 0.4, value: 0.9 },
          { time: 1.0, value: 1.0 }
        ],
        interpolation: 'cubic'
      },
      priority: 1
    },
    {
      from: 'happy',
      to: 'confident',
      duration: 1200,
      curve: {
        keyframes: [
          { time: 0.0, value: 0.0 },
          { time: 0.6, value: 0.8 },
          { time: 1.0, value: 1.0 }
        ],
        interpolation: 'cubic'
      },
      priority: 1
    },
    {
      from: 'happy',
      to: 'neutral',
      duration: 2000,
      curve: {
        keyframes: [
          { time: 0.0, value: 1.0 },
          { time: 0.7, value: 0.3 },
          { time: 1.0, value: 0.0 }
        ],
        interpolation: 'cubic'
      },
      priority: 0
    },

    // From Focused
    {
      from: 'focused',
      to: 'confident',
      duration: 1000,
      curve: {
        keyframes: [
          { time: 0.0, value: 0.0 },
          { time: 0.5, value: 0.7 },
          { time: 1.0, value: 1.0 }
        ],
        interpolation: 'cubic'
      },
      priority: 1
    },
    {
      from: 'focused',
      to: 'concerned',
      duration: 600,
      curve: {
        keyframes: [
          { time: 0.0, value: 0.0 },
          { time: 0.3, value: 0.8 },
          { time: 1.0, value: 1.0 }
        ],
        interpolation: 'linear'
      },
      priority: 2
    },
    {
      from: 'focused',
      to: 'neutral',
      duration: 1500,
      curve: {
        keyframes: [
          { time: 0.0, value: 1.0 },
          { time: 0.8, value: 0.2 },
          { time: 1.0, value: 0.0 }
        ],
        interpolation: 'cubic'
      },
      priority: 0
    },

    // From Curious
    {
      from: 'curious',
      to: 'happy',
      duration: 800,
      curve: {
        keyframes: [
          { time: 0.0, value: 0.0 },
          { time: 0.3, value: 0.8 },
          { time: 1.0, value: 1.0 }
        ],
        interpolation: 'cubic'
      },
      priority: 1
    },
    {
      from: 'curious',
      to: 'focused',
      duration: 700,
      curve: {
        keyframes: [
          { time: 0.0, value: 0.0 },
          { time: 0.4, value: 0.9 },
          { time: 1.0, value: 1.0 }
        ],
        interpolation: 'linear'
      },
      priority: 1
    },
    {
      from: 'curious',
      to: 'neutral',
      duration: 1200,
      curve: {
        keyframes: [
          { time: 0.0, value: 1.0 },
          { time: 0.6, value: 0.4 },
          { time: 1.0, value: 0.0 }
        ],
        interpolation: 'cubic'
      },
      priority: 0
    },

    // From Concerned
    {
      from: 'concerned',
      to: 'apologetic',
      duration: 600,
      curve: {
        keyframes: [
          { time: 0.0, value: 0.0 },
          { time: 0.2, value: 0.7 },
          { time: 1.0, value: 1.0 }
        ],
        interpolation: 'linear'
      },
      priority: 1
    },
    {
      from: 'concerned',
      to: 'focused',
      duration: 800,
      curve: {
        keyframes: [
          { time: 0.0, value: 0.0 },
          { time: 0.5, value: 0.8 },
          { time: 1.0, value: 1.0 }
        ],
        interpolation: 'cubic'
      },
      priority: 1
    },
    {
      from: 'concerned',
      to: 'neutral',
      duration: 1800,
      curve: {
        keyframes: [
          { time: 0.0, value: 1.0 },
          { time: 0.7, value: 0.3 },
          { time: 1.0, value: 0.0 }
        ],
        interpolation: 'cubic'
      },
      priority: 0
    },

    // From Confident
    {
      from: 'confident',
      to: 'happy',
      duration: 1000,
      curve: {
        keyframes: [
          { time: 0.0, value: 0.0 },
          { time: 0.4, value: 0.8 },
          { time: 1.0, value: 1.0 }
        ],
        interpolation: 'cubic'
      },
      priority: 1
    },
    {
      from: 'confident',
      to: 'neutral',
      duration: 2500,
      curve: {
        keyframes: [
          { time: 0.0, value: 1.0 },
          { time: 0.8, value: 0.2 },
          { time: 1.0, value: 0.0 }
        ],
        interpolation: 'cubic'
      },
      priority: 0
    },

    // From Apologetic
    {
      from: 'apologetic',
      to: 'concerned',
      duration: 500,
      curve: {
        keyframes: [
          { time: 0.0, value: 0.0 },
          { time: 0.3, value: 0.9 },
          { time: 1.0, value: 1.0 }
        ],
        interpolation: 'linear'
      },
      priority: 1
    },
    {
      from: 'apologetic',
      to: 'neutral',
      duration: 1500,
      curve: {
        keyframes: [
          { time: 0.0, value: 1.0 },
          { time: 0.6, value: 0.4 },
          { time: 1.0, value: 0.0 }
        ],
        interpolation: 'cubic'
      },
      priority: 0
    },

    // From Excited
    {
      from: 'excited',
      to: 'happy',
      duration: 1200,
      curve: {
        keyframes: [
          { time: 0.0, value: 1.0 },
          { time: 0.5, value: 0.7 },
          { time: 1.0, value: 0.0 }
        ],
        interpolation: 'cubic'
      },
      priority: 1
    },
    {
      from: 'excited',
      to: 'neutral',
      duration: 3000,
      curve: {
        keyframes: [
          { time: 0.0, value: 1.0 },
          { time: 0.3, value: 0.8 },
          { time: 0.7, value: 0.3 },
          { time: 1.0, value: 0.0 }
        ],
        interpolation: 'cubic'
      },
      priority: 0
    }
  ],
  defaultState: DEFAULT_EMOTIONAL_STATE,
  maxIntensity: MAX_EMOTIONAL_INTENSITY,
  decayRate: DEFAULT_DECAY_RATE
};

/**
 * Emotional state priorities (higher number = higher priority)
 */
export const EMOTIONAL_STATE_PRIORITIES: Record<PrimaryEmotion, number> = {
  'neutral': 0,
  'happy': 1,
  'focused': 2,
  'curious': 1,
  'concerned': 3,
  'confident': 1,
  'apologetic': 2,
  'excited': 1
};

/**
 * Emotional state durations (default duration in milliseconds)
 */
export const EMOTIONAL_STATE_DURATIONS: Record<PrimaryEmotion, number> = {
  'neutral': -1, // indefinite
  'happy': 30000, // 30 seconds
  'focused': 120000, // 2 minutes
  'curious': 15000, // 15 seconds
  'concerned': 60000, // 1 minute
  'confident': 45000, // 45 seconds
  'apologetic': 20000, // 20 seconds
  'excited': 10000 // 10 seconds
};

/**
 * Emotional compatibility matrix (which emotions can blend well)
 */
export const EMOTIONAL_COMPATIBILITY: Record<PrimaryEmotion, PrimaryEmotion[]> = {
  'neutral': ['happy', 'focused', 'curious', 'concerned', 'confident', 'apologetic', 'excited'],
  'happy': ['neutral', 'confident', 'excited', 'curious'],
  'focused': ['neutral', 'confident', 'curious', 'concerned'],
  'curious': ['neutral', 'happy', 'focused', 'excited'],
  'concerned': ['neutral', 'focused', 'apologetic'],
  'confident': ['neutral', 'happy', 'focused'],
  'apologetic': ['neutral', 'concerned'],
  'excited': ['neutral', 'happy', 'curious']
};

/**
 * Emotional intensity thresholds for different behaviors
 */
export const INTENSITY_THRESHOLDS = {
  SUBTLE: 0.2,
  MODERATE: 0.5,
  STRONG: 0.8,
  DRAMATIC: 1.0
} as const;

/**
 * Emotional response sensitivity levels
 */
export const SENSITIVITY_LEVELS = {
  LOW: 0.3,
  MEDIUM: 0.6,
  HIGH: 0.9
} as const;

/**
 * Default emotional responsiveness configuration
 */
export const DEFAULT_EMOTIONAL_RESPONSIVENESS = {
  level: 'medium' as const,
  voiceSensitivity: SENSITIVITY_LEVELS.MEDIUM,
  textSensitivity: SENSITIVITY_LEVELS.MEDIUM,
  commandSensitivity: SENSITIVITY_LEVELS.MEDIUM,
  adaptationRate: 0.1,
  userOverrideEnabled: true
};

/**
 * Default drift prevention configuration
 */
export const DEFAULT_DRIFT_PREVENTION = {
  enabled: true,
  maxDuration: MAX_NON_NEUTRAL_DURATION,
  intensityThreshold: 0.8,
  resetInterval: DRIFT_PREVENTION_INTERVAL,
  gradualReturn: true
};

/**
 * Default normalization configuration
 */
export const DEFAULT_NORMALIZATION = {
  enabled: true,
  interval: NORMALIZATION_INTERVAL,
  targetState: DEFAULT_EMOTIONAL_STATE,
  decayRate: DEFAULT_DECAY_RATE,
  preservePositive: true
};