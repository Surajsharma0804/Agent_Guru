/**
 * Motion and animation frame data structures
 */

import { Vector3, Vector2, AnimationCurve } from './Common';
import { EmotionalState } from './EmotionalState';

/**
 * Complete motion frame containing all movement data
 */
export interface MotionFrame {
  timestamp: number;
  frameId: string;
  
  // Micro-movements (always active)
  breathing: BreathingState;
  blinking: BlinkState;
  eyeTracking: EyePosition;
  postureShift: PostureAdjustment;
  headPosition: HeadOrientation;
  
  // Contextual movements
  gesture?: GestureFrame;
  attention?: AttentionFrame;
  
  // Body parts for compatibility with implementation
  head?: {
    position: Vector3;
    rotation: Vector3;
  };
  torso?: {
    position: Vector3;
    rotation: Vector3;
  };
  leftArm?: {
    position: Vector3;
    rotation: Vector3;
  };
  rightArm?: {
    position: Vector3;
    rotation: Vector3;
  };
  eyes?: {
    direction: Vector3;
    convergence: number;
  };
  posture?: {
    spine: Vector3;
    shoulders: Vector3;
  };
  microMovements?: {
    head: Vector3;
    torso: Vector3;
  };
  
  // Additional compatibility properties
  headPose?: {
    position: Vector3;
    rotation: Vector3;
  };
  eyeGaze?: {
    direction: Vector3;
    confidence: number;
  };
  facialExpression?: {
    happiness: number;
    sadness: number;
    anger: number;
    surprise: number;
    fear: number;
    disgust: number;
  };
  bodyPosture?: {
    spine: Vector3;
    shoulders: Vector3;
  };
  gestureState?: {
    activeGestures: string[];
    intensity: number;
    blendWeights: Record<string, number>;
  };
  attentionState?: {
    target: AttentionTarget | null;
    focus: number;
    engagement: number;
  };
  
  // Metadata
  emotionalInfluence: EmotionalState;
  naturalness: number; // 0.0 to 1.0
  quality: MotionQuality;
}

/**
 * Breathing animation state
 */
export interface BreathingState {
  phase: 'inhale' | 'exhale' | 'pause';
  intensity: number; // 0.0 to 1.0
  rate: number; // breaths per minute
  chestExpansion: number; // 0.0 to 1.0
  shoulderMovement: number; // 0.0 to 1.0
  duration: number; // milliseconds for current phase
  nextPhaseTime: number; // timestamp for next phase
}

/**
 * Blinking animation state
 */
export interface BlinkState {
  isBlinking: boolean;
  blinkProgress: number; // 0.0 to 1.0 (0 = open, 1 = closed)
  blinkDuration: number; // milliseconds
  nextBlinkTime: number; // timestamp for next blink
  blinkType: 'normal' | 'slow' | 'double' | 'wink';
  eyesClosed: {
    left: number; // 0.0 to 1.0
    right: number; // 0.0 to 1.0
  };
  
  // Compatibility properties
  leftEye?: number; // 0.0 to 1.0
  rightEye?: number; // 0.0 to 1.0
  naturalness?: number; // 0.0 to 1.0
}

/**
 * Eye tracking and gaze direction
 */
export interface EyePosition {
  gazeDirection: Vector3; // normalized direction vector
  focusPoint: Vector3; // world space focus point
  convergence: number; // 0.0 to 1.0 (parallel to crossed)
  pupilDilation: number; // 0.0 to 1.0
  eyeMovementSpeed: number; // degrees per second
  saccadeActive: boolean; // rapid eye movement
  trackingTarget?: TrackingTarget;
}

/**
 * Target for eye tracking
 */
export interface TrackingTarget {
  type: 'user' | 'screen_point' | 'audio_source' | 'object';
  position: Vector3;
  confidence: number; // 0.0 to 1.0
  priority: number; // higher values take precedence
}

/**
 * Posture adjustment for natural movement
 */
export interface PostureAdjustment {
  spineRotation: Vector3; // euler angles
  shoulderPosition: Vector3; // offset from neutral
  hipPosition: Vector3; // offset from neutral
  weightShift: Vector2; // left/right, forward/back
  tension: number; // 0.0 to 1.0 (relaxed to tense)
  asymmetry: number; // 0.0 to 1.0 (symmetric to asymmetric)
}

/**
 * Head orientation and movement
 */
export interface HeadOrientation {
  rotation: Vector3; // euler angles (pitch, yaw, roll)
  position: Vector3; // offset from neutral
  tilt: number; // side tilt in degrees
  nod: number; // up/down nod amount
  shake: number; // left/right shake amount
  movementSpeed: number; // degrees per second
  targetOrientation?: Vector3; // target for smooth transitions
}

/**
 * Gesture frame data
 */
export interface GestureFrame {
  gestureId: string;
  type: GestureType;
  phase: 'preparation' | 'stroke' | 'hold' | 'retraction';
  progress: number; // 0.0 to 1.0
  intensity: number; // 0.0 to 1.0
  handPositions: HandPosition[];
  armPositions: ArmPosition[];
  timing: GestureTiming;
  context: GestureContext;
}

/**
 * Types of gestures
 */
export type GestureType = 
  | 'emphasis'
  | 'explanation'
  | 'greeting'
  | 'thinking'
  | 'error'
  | 'success'
  | 'pointing'
  | 'counting'
  | 'size_indication'
  | 'dismissal'
  | 'approval'
  | 'uncertainty'
  | 'waving'
  | 'nodding'
  | 'affirmation'
  | 'negation'
  | 'directional'
  | 'confidence'
  | 'defensive'
  | 'openness'
  | 'curiosity'
  | 'aggressive';

/**
 * Hand position and pose
 */
export interface HandPosition {
  hand: 'left' | 'right';
  position: Vector3; // world space position
  rotation: Vector3; // euler angles
  pose: HandPose;
  fingerPositions: FingerPosition[];
  velocity: Vector3; // movement velocity
}

/**
 * Hand pose types
 */
export type HandPose = 
  | 'open'
  | 'closed'
  | 'pointing'
  | 'thumbs_up'
  | 'ok_sign'
  | 'peace'
  | 'fist'
  | 'relaxed'
  | 'grasping';

/**
 * Individual finger position
 */
export interface FingerPosition {
  finger: 'thumb' | 'index' | 'middle' | 'ring' | 'pinky';
  joints: number[]; // joint angles in degrees
  extension: number; // 0.0 to 1.0 (curled to extended)
}

/**
 * Arm position and movement
 */
export interface ArmPosition {
  arm: 'left' | 'right';
  shoulder: Vector3; // shoulder rotation
  elbow: Vector3; // elbow position
  wrist: Vector3; // wrist position
  extension: number; // 0.0 to 1.0 (close to extended)
  tension: number; // 0.0 to 1.0 (relaxed to tense)
}

/**
 * Gesture timing information
 */
export interface GestureTiming {
  startTime: number; // timestamp
  duration: number; // total gesture duration in milliseconds
  phaseTimings: {
    preparation: number; // milliseconds
    stroke: number; // milliseconds
    hold: number; // milliseconds
    retraction: number; // milliseconds
  };
  synchronization?: SynchronizationPoint[];
}

/**
 * Synchronization points for gesture coordination
 */
export interface SynchronizationPoint {
  type: 'speech_emphasis' | 'word_boundary' | 'sentence_end' | 'pause';
  timestamp: number;
  gesturePhase: 'preparation' | 'stroke' | 'hold' | 'retraction';
  importance: number; // 0.0 to 1.0
}

/**
 * Gesture context information
 */
export interface GestureContext {
  trigger: 'speech' | 'emotion' | 'command' | 'idle' | 'manual';
  emotionalState: EmotionalState;
  speechContext?: SpeechContext;
  repetitionCount: number; // how many times this gesture has been used recently
  appropriateness: number; // 0.0 to 1.0 cultural/contextual appropriateness
  
  // Additional properties for compatibility
  type?: GestureType;
  intensity?: number;
  duration?: number;
  emotionalContext?: string;
  culturalContext?: string;
  targetAudience?: string;
}

/**
 * Speech context for gesture synchronization
 */
export interface SpeechContext {
  text: string;
  emphasisWords: string[];
  sentimentPolarity: number; // -1.0 to 1.0
  speechRate: number; // words per minute
  volume: number; // 0.0 to 1.0
}

/**
 * Attention and focus frame
 */
export interface AttentionFrame {
  focusTarget: AttentionTarget;
  attentionLevel: number; // 0.0 to 1.0
  distractionLevel: number; // 0.0 to 1.0
  engagementType: 'passive' | 'active' | 'interactive';
  bodyOrientation: Vector3; // body facing direction
  headTracking: boolean; // whether head follows target
  eyeTracking: boolean; // whether eyes follow target
}

/**
 * Attention target information
 */
export interface AttentionTarget {
  type: 'user' | 'screen' | 'audio_source' | 'notification' | 'none';
  position: Vector3; // world space position
  screenCoordinates?: Vector2; // screen space coordinates
  confidence: number; // 0.0 to 1.0
  priority: number; // attention priority
  duration: number; // how long to maintain attention
}

/**
 * Motion quality metrics
 */
export interface MotionQuality {
  naturalness: number; // 0.0 to 1.0
  smoothness: number; // 0.0 to 1.0
  responsiveness: number; // 0.0 to 1.0
  consistency: number; // 0.0 to 1.0
  culturalAppropriateness: number; // 0.0 to 1.0
  energyLevel: number; // 0.0 to 1.0
}

/**
 * Motion sequence for complex animations
 */
export interface MotionSequence {
  id: string;
  name: string;
  frames: MotionFrame[];
  duration: number; // milliseconds
  looping: boolean;
  blendable: boolean;
  priority: number;
  tags: string[];
  transitionCurve: AnimationCurve;
}

/**
 * Motion state for different avatar modes
 */
export type MotionState = 'idle' | 'listening' | 'speaking' | 'thinking' | 'error' | 'sleeping';

/**
 * Motion state configuration
 */
export interface MotionStateConfig {
  state: MotionState;
  baseAnimations: string[]; // animation IDs
  allowedGestures: GestureType[];
  attentionBehavior: AttentionBehavior;
  microMovementIntensity: number; // 0.0 to 1.0
  transitionRules: StateTransitionRule[];
}

/**
 * Attention behavior configuration
 */
export interface AttentionBehavior {
  eyeContactFrequency: number; // 0.0 to 1.0
  gazeWandering: number; // 0.0 to 1.0
  headTracking: boolean;
  bodyOrientation: boolean;
  distractionSensitivity: number; // 0.0 to 1.0
}

/**
 * State transition rules
 */
export interface StateTransitionRule {
  fromState: MotionState;
  toState: MotionState;
  trigger: string;
  condition?: string;
  transitionDuration: number; // milliseconds
  blendCurve: AnimationCurve;
}