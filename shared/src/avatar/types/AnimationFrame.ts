/**
 * Complete animation frame data for avatar rendering
 */

import { Platform, QualityLevel } from './Common';
import { EmotionalState } from './EmotionalState';
import { MotionFrame } from './MotionFrame';

/**
 * Complete animation frame containing all rendering data
 */
export interface AnimationFrame {
  timestamp: number;
  frameId: string;
  sequenceNumber: number;
  
  // Core Animation Data
  facial: FacialAnimation;
  lipSync: VisemeFrame;
  eyeMovement: EyeAnimation;
  blinking: BlinkFrame;
  
  // Body Animation (platform dependent)
  body?: BodyAnimation;
  
  // Metadata
  emotionalState: EmotionalState;
  motionData: MotionFrame;
  quality: QualityMetrics;
  platform: Platform;
  renderingHints: RenderingHints;
}

/**
 * Facial expression animation data
 */
export interface FacialAnimation {
  expression: FacialExpression;
  morphTargets: MorphTargetWeights;
  blendShapes: BlendShapeWeights;
  intensity: number; // 0.0 to 1.0
  transitionCurve: import('./Common').AnimationCurve;
  duration: number; // milliseconds
  asymmetry?: FacialAsymmetry;
}

/**
 * Facial expression configuration
 */
export interface FacialExpression {
  primary: ExpressionType;
  secondary?: ExpressionType;
  intensity: number; // 0.0 to 1.0
  regions: FacialRegionWeights;
  microExpressions: MicroExpression[];
}

/**
 * Types of facial expressions
 */
export type ExpressionType = 
  | 'neutral'
  | 'smile'
  | 'frown'
  | 'surprise'
  | 'concern'
  | 'focus'
  | 'confusion'
  | 'approval'
  | 'disapproval'
  | 'thinking'
  | 'listening'
  | 'speaking';

/**
 * Facial region weight distribution
 */
export interface FacialRegionWeights {
  forehead: number; // 0.0 to 1.0
  eyebrows: number; // 0.0 to 1.0
  eyes: number; // 0.0 to 1.0
  cheeks: number; // 0.0 to 1.0
  nose: number; // 0.0 to 1.0
  mouth: number; // 0.0 to 1.0
  jaw: number; // 0.0 to 1.0
  chin: number; // 0.0 to 1.0
}

/**
 * Micro-expression for subtle facial changes
 */
export interface MicroExpression {
  type: 'eyebrow_flash' | 'lip_twitch' | 'nostril_flare' | 'eye_squint' | 'cheek_raise';
  intensity: number; // 0.0 to 1.0
  duration: number; // milliseconds
  delay: number; // milliseconds from frame start
  region: keyof FacialRegionWeights;
}

/**
 * Morph target weights for facial deformation
 */
export interface MorphTargetWeights {
  [targetName: string]: number; // 0.0 to 1.0
}

/**
 * Blend shape weights for facial animation
 */
export interface BlendShapeWeights {
  // Basic expressions
  smile: number;
  frown: number;
  browUp: number;
  browDown: number;
  eyeWide: number;
  eyeSquint: number;
  cheekPuff: number;
  jawOpen: number;
  
  // Visemes (for lip sync)
  viseme_sil: number; // silence
  viseme_PP: number; // p, b, m
  viseme_FF: number; // f, v
  viseme_TH: number; // th
  viseme_DD: number; // t, d, n, l
  viseme_kk: number; // k, g
  viseme_CH: number; // ch, sh, j
  viseme_SS: number; // s, z
  viseme_nn: number; // n, ng
  viseme_RR: number; // r
  viseme_aa: number; // a
  viseme_E: number; // e
  viseme_ih: number; // i
  viseme_oh: number; // o
  viseme_ou: number; // u
  
  // Custom blend shapes
  [customShape: string]: number;
}

/**
 * Facial asymmetry for natural variation
 */
export interface FacialAsymmetry {
  enabled: boolean;
  leftSideIntensity: number; // 0.0 to 1.0
  rightSideIntensity: number; // 0.0 to 1.0
  asymmetryType: 'smile' | 'eyebrow' | 'eye' | 'general';
  naturalness: number; // 0.0 to 1.0
}

/**
 * Lip sync viseme frame
 */
export interface VisemeFrame {
  currentViseme: Viseme;
  nextViseme?: Viseme;
  transitionProgress: number; // 0.0 to 1.0
  emotionalModulation: EmotionModifier;
  breathingInfluence: BreathingInfluence;
  emphasis: EmphasisMarker[];
}

/**
 * Viseme representation
 */
export interface Viseme {
  phoneme: string;
  visemeId: string;
  mouthShape: MouthShape;
  duration: number; // milliseconds
  intensity: number; // 0.0 to 1.0
  confidence: number; // 0.0 to 1.0
}

/**
 * Mouth shape configuration
 */
export interface MouthShape {
  openness: number; // 0.0 to 1.0
  width: number; // 0.0 to 1.0
  lipRounding: number; // 0.0 to 1.0
  tonguePosition: import('./Common').Vector3;
  teethVisibility: number; // 0.0 to 1.0
  lipTension: number; // 0.0 to 1.0
}

/**
 * Emotional modulation for lip sync
 */
export interface EmotionModifier {
  mouthCurvature: number; // -1.0 to 1.0 (frown to smile)
  lipTightness: number; // 0.0 to 1.0
  jawTension: number; // 0.0 to 1.0
  articulationClarity: number; // 0.0 to 1.0
  speedModulation: number; // 0.5 to 2.0 (slower to faster)
}

/**
 * Breathing influence on speech
 */
export interface BreathingInfluence {
  breathSupport: number; // 0.0 to 1.0
  pauseForBreath: boolean;
  breathingPhase: 'inhale' | 'exhale' | 'pause';
  chestMovement: number; // 0.0 to 1.0
}

/**
 * Speech emphasis markers
 */
export interface EmphasisMarker {
  type: 'stress' | 'pitch_rise' | 'volume_increase' | 'pause';
  timestamp: number; // relative to frame
  intensity: number; // 0.0 to 1.0
  duration: number; // milliseconds
  associatedGesture?: string; // gesture ID
}

/**
 * Eye animation data
 */
export interface EyeAnimation {
  leftEye: EyeState;
  rightEye: EyeState;
  gazeDirection: import('./Common').Vector3;
  convergence: number; // 0.0 to 1.0
  focusDistance: number; // meters
  saccadeActive: boolean;
  trackingTarget?: TrackingTarget;
}

/**
 * Individual eye state
 */
export interface EyeState {
  rotation: import('./Common').Vector3; // euler angles
  pupilDilation: number; // 0.0 to 1.0
  eyelidPosition: number; // 0.0 to 1.0 (closed to open)
  moistness: number; // 0.0 to 1.0 (dry to moist)
  bloodshot: number; // 0.0 to 1.0 (clear to bloodshot)
  focus: number; // 0.0 to 1.0 (unfocused to sharp focus)
}

/**
 * Eye tracking target
 */
export interface TrackingTarget {
  position: import('./Common').Vector3;
  type: 'user' | 'screen_point' | 'object' | 'audio_source';
  confidence: number; // 0.0 to 1.0
  priority: number;
  smoothing: number; // 0.0 to 1.0
}

/**
 * Blinking animation frame
 */
export interface BlinkFrame {
  leftEyelid: EyelidState;
  rightEyelid: EyelidState;
  blinkType: BlinkType;
  synchronization: number; // 0.0 to 1.0 (async to sync)
  naturalness: number; // 0.0 to 1.0
}

/**
 * Eyelid animation state
 */
export interface EyelidState {
  upperLid: number; // 0.0 to 1.0 (open to closed)
  lowerLid: number; // 0.0 to 1.0 (relaxed to raised)
  velocity: number; // closing/opening speed
  acceleration: number; // speed change rate
}

/**
 * Types of blinks
 */
export type BlinkType = 'normal' | 'slow' | 'rapid' | 'wink_left' | 'wink_right' | 'double' | 'flutter';

/**
 * Body animation data (for full-body platforms)
 */
export interface BodyAnimation {
  posture: PostureFrame;
  gestures: GestureFrame[];
  breathing: BreathingFrame;
  headOrientation: HeadFrame;
  armMovements?: ArmFrame[];
  handPositions?: HandFrame[];
  torsoMovement?: TorsoFrame;
}

/**
 * Posture animation frame
 */
export interface PostureFrame {
  spineAlignment: import('./Common').Vector3;
  shoulderPosition: import('./Common').Vector3;
  hipAlignment: import('./Common').Vector3;
  weightDistribution: WeightDistribution;
  tension: number; // 0.0 to 1.0
  confidence: number; // 0.0 to 1.0 (affects posture openness)
}

/**
 * Weight distribution for natural posture
 */
export interface WeightDistribution {
  leftRight: number; // -1.0 to 1.0 (left to right)
  frontBack: number; // -1.0 to 1.0 (back to front)
  stability: number; // 0.0 to 1.0
}

/**
 * Gesture animation frame
 */
export interface GestureFrame {
  gestureId: string;
  phase: 'preparation' | 'stroke' | 'hold' | 'retraction';
  progress: number; // 0.0 to 1.0
  intensity: number; // 0.0 to 1.0
  handPositions: HandFrame[];
  armPositions: ArmFrame[];
  synchronization: SynchronizationData;
}

/**
 * Breathing animation frame
 */
export interface BreathingFrame {
  phase: 'inhale' | 'exhale' | 'pause';
  intensity: number; // 0.0 to 1.0
  chestExpansion: number; // 0.0 to 1.0
  shoulderMovement: number; // 0.0 to 1.0
  diaphragmMovement: number; // 0.0 to 1.0
  rate: number; // breaths per minute
}

/**
 * Head orientation frame
 */
export interface HeadFrame {
  rotation: import('./Common').Vector3; // pitch, yaw, roll
  position: import('./Common').Vector3; // offset from neutral
  tilt: number; // side tilt
  nod: number; // up/down movement
  shake: number; // left/right movement
  trackingActive: boolean;
}

/**
 * Arm animation frame
 */
export interface ArmFrame {
  arm: 'left' | 'right';
  shoulder: import('./Common').Vector3;
  elbow: import('./Common').Vector3;
  wrist: import('./Common').Vector3;
  extension: number; // 0.0 to 1.0
  tension: number; // 0.0 to 1.0
}

/**
 * Hand animation frame
 */
export interface HandFrame {
  hand: 'left' | 'right';
  position: import('./Common').Vector3;
  rotation: import('./Common').Vector3;
  pose: HandPose;
  fingerPositions: FingerFrame[];
}

/**
 * Hand pose types
 */
export type HandPose = 'open' | 'closed' | 'pointing' | 'thumbs_up' | 'ok_sign' | 'relaxed' | 'grasping';

/**
 * Individual finger frame
 */
export interface FingerFrame {
  finger: 'thumb' | 'index' | 'middle' | 'ring' | 'pinky';
  joints: number[]; // joint angles
  extension: number; // 0.0 to 1.0
  curl: number; // 0.0 to 1.0
}

/**
 * Torso animation frame
 */
export interface TorsoFrame {
  rotation: import('./Common').Vector3;
  lean: import('./Common').Vector2; // forward/back, left/right
  twist: number; // spinal rotation
  expansion: number; // chest expansion for breathing
}

/**
 * Synchronization data for coordinated animation
 */
export interface SynchronizationData {
  speechSync: boolean;
  emotionSync: boolean;
  breathingSync: boolean;
  gestureSync: boolean;
  timingOffset: number; // milliseconds
}

/**
 * Quality metrics for animation frame
 */
export interface QualityMetrics {
  frameRate: number; // actual FPS
  renderTime: number; // milliseconds to render
  smoothness: number; // 0.0 to 1.0
  naturalness: number; // 0.0 to 1.0
  synchronization: number; // 0.0 to 1.0
  memoryUsage: number; // bytes
  cpuUsage: number; // percentage
  gpuUsage: number; // percentage
}

/**
 * Rendering hints for platform optimization
 */
export interface RenderingHints {
  quality: QualityLevel;
  lodLevel: number; // 0 = highest quality
  cullingEnabled: boolean;
  shadowsEnabled: boolean;
  lightingComplexity: 'basic' | 'standard' | 'advanced';
  textureResolution: number;
  animationComplexity: 'minimal' | 'standard' | 'full';
  optimizationFlags: OptimizationFlag[];
}

/**
 * Optimization flags for performance tuning
 */
export type OptimizationFlag = 
  | 'reduce_geometry'
  | 'simplify_shaders'
  | 'disable_shadows'
  | 'lower_texture_quality'
  | 'reduce_animation_fidelity'
  | 'enable_culling'
  | 'use_instancing'
  | 'compress_textures';