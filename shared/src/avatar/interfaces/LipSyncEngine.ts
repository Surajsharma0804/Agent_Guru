/**
 * Lip Sync Engine Interface
 * 
 * Provides real-time phoneme-to-viseme mapping with emotion-aware mouth movement generation.
 * Handles audio processing, timing synchronization, and breathing animation integration.
 */

import { 
  VisemeFrame, 
  Viseme, 
  MouthShape, 
  EmotionModifier, 
  EmphasisMarker 
} from '../types/AnimationFrame';
import { EmotionalState } from '../types/EmotionalState';
import { AvatarApiResponse, TimingData } from '../types/Common';

/**
 * Core Lip Sync Engine interface for phoneme-based lip synchronization
 */
export interface LipSyncEngine {
  // Phoneme Processing
  processPhonemeStream(phonemes: PhonemeSequence): Promise<AvatarApiResponse<VisemeSequence>>;
  syncWithAudio(audioBuffer: AudioBuffer, phonemes: PhonemeSequence): Promise<AvatarApiResponse<SyncedAnimation>>;
  processRealTimeAudio(audioStream: AudioStream): Promise<AvatarApiResponse<VisemeFrame>>;
  
  // Emotion Integration
  applyEmotionalModulation(visemes: VisemeSequence, emotion: EmotionalState): Promise<AvatarApiResponse<VisemeSequence>>;
  generateEmotionModifier(emotion: EmotionalState): Promise<AvatarApiResponse<EmotionModifier>>;
  blendEmotionalStates(primary: EmotionalState, secondary: EmotionalState, blendFactor: number): Promise<AvatarApiResponse<EmotionModifier>>;
  
  // Timing and Quality
  validateSyncAccuracy(audio: AudioBuffer, animation: VisemeSequence): Promise<AvatarApiResponse<SyncQuality>>;
  adjustLatencyCompensation(latency: number): Promise<AvatarApiResponse<void>>;
  optimizeTiming(targetAccuracy: number): Promise<AvatarApiResponse<void>>;
  
  // Breathing and Pauses
  generateBreathingPauses(sentences: SentenceBreak[]): Promise<AvatarApiResponse<BreathingAnimation>>;
  insertEmphasisNods(emphasisWords: WordTiming[]): Promise<AvatarApiResponse<HeadNodSequence>>;
  synchronizeBreathing(breathingPattern: BreathingPattern): Promise<AvatarApiResponse<void>>;
  
  // Advanced Features
  generateProceduralVisemes(text: string, voiceProfile: VoiceProfile): Promise<AvatarApiResponse<VisemeSequence>>;
  adaptToSpeakingStyle(style: SpeakingStyle): Promise<AvatarApiResponse<void>>;
  calibrateForVoice(voiceSamples: VoiceSample[]): Promise<AvatarApiResponse<VoiceCalibration>>;
  
  // Configuration and Control
  setLipSyncConfiguration(config: LipSyncConfig): Promise<AvatarApiResponse<void>>;
  getLipSyncConfiguration(): Promise<AvatarApiResponse<LipSyncConfig>>;
  setQualityLevel(level: 'low' | 'medium' | 'high' | 'ultra'): Promise<AvatarApiResponse<void>>;
  
  // Performance and Optimization
  optimizePerformance(targetLatency: number): Promise<AvatarApiResponse<void>>;
  getPerformanceMetrics(): Promise<AvatarApiResponse<LipSyncMetrics>>;
  preloadPhonemeData(phonemes: string[]): Promise<AvatarApiResponse<void>>;
  
  // Event Handling
  onSyncStarted(callback: SyncEventCallback): void;
  onSyncCompleted(callback: SyncEventCallback): void;
  onSyncError(callback: SyncErrorCallback): void;
  onQualityChanged(callback: QualityChangeCallback): void;
  
  // System Management
  resetLipSyncEngine(): Promise<AvatarApiResponse<void>>;
  validateConfiguration(): Promise<AvatarApiResponse<ValidationResult>>;
  cleanup(): Promise<AvatarApiResponse<void>>;
}

/**
 * Phoneme sequence with timing and emphasis data
 */
export interface PhonemeSequence {
  phonemes: Phoneme[];
  timing: TimingData[];
  emphasis: EmphasisMarker[];
  totalDuration: number; // milliseconds
  sampleRate: number; // Hz
  confidence: number; // 0.0 to 1.0
  language?: string;
  dialect?: string;
}

/**
 * Individual phoneme with properties
 */
export interface Phoneme {
  symbol: string; // IPA or ARPABET symbol
  startTime: number; // milliseconds
  duration: number; // milliseconds
  intensity: number; // 0.0 to 1.0
  pitch: number; // Hz
  confidence: number; // 0.0 to 1.0
  context: PhonemeContext;
}

/**
 * Phoneme context information
 */
export interface PhonemeContext {
  precedingPhoneme?: string;
  followingPhoneme?: string;
  wordPosition: 'initial' | 'medial' | 'final';
  syllableStress: 'primary' | 'secondary' | 'unstressed';
  wordBoundary: boolean;
}

/**
 * Viseme sequence with transitions and modulation
 */
export interface VisemeSequence {
  visemes: Viseme[];
  transitions: TransitionCurve[];
  emotionalModulation: EmotionModifier[];
  breathingPauses: BreathingMarker[];
  totalDuration: number; // milliseconds
  quality: VisemeQuality;
}

/**
 * Transition curve for smooth viseme changes
 */
export interface TransitionCurve {
  fromViseme: string;
  toViseme: string;
  startTime: number; // milliseconds
  duration: number; // milliseconds
  curve: import('../types/Common').AnimationCurve;
  blendMode: 'linear' | 'ease_in' | 'ease_out' | 'ease_in_out' | 'custom';
}

/**
 * Breathing marker for natural pauses
 */
export interface BreathingMarker {
  timestamp: number; // milliseconds
  duration: number; // milliseconds
  intensity: number; // 0.0 to 1.0
  type: 'inhale' | 'exhale' | 'pause';
  mouthMovement: MouthShape;
}

/**
 * Viseme quality metrics
 */
export interface VisemeQuality {
  accuracy: number; // 0.0 to 1.0
  smoothness: number; // 0.0 to 1.0
  naturalness: number; // 0.0 to 1.0
  emotionalConsistency: number; // 0.0 to 1.0
  timingPrecision: number; // 0.0 to 1.0
}

/**
 * Synchronized animation result
 */
export interface SyncedAnimation {
  visemeSequence: VisemeSequence;
  audioAlignment: AudioAlignment;
  headMovements: HeadMovementSequence;
  breathingAnimation: BreathingAnimation;
  qualityMetrics: SyncQuality;
}

/**
 * Audio alignment information
 */
export interface AudioAlignment {
  offsetCorrection: number; // milliseconds
  stretchFactor: number; // 0.5 to 2.0
  confidenceScore: number; // 0.0 to 1.0
  alignmentPoints: AlignmentPoint[];
}

/**
 * Alignment point for audio-visual sync
 */
export interface AlignmentPoint {
  audioTime: number; // milliseconds
  visualTime: number; // milliseconds
  phoneme: string;
  confidence: number; // 0.0 to 1.0
}

/**
 * Head movement sequence for emphasis and breathing
 */
export interface HeadMovementSequence {
  movements: HeadMovement[];
  breathingSync: boolean;
  emphasisSync: boolean;
  totalDuration: number; // milliseconds
}

/**
 * Individual head movement
 */
export interface HeadMovement {
  type: 'nod' | 'shake' | 'tilt' | 'turn';
  startTime: number; // milliseconds
  duration: number; // milliseconds
  intensity: number; // 0.0 to 1.0
  direction: import('../types/Common').Vector3;
  synchronizedWith: 'word' | 'emphasis' | 'breath' | 'pause';
}

/**
 * Breathing animation for natural speech
 */
export interface BreathingAnimation {
  breathCycles: BreathCycle[];
  chestMovement: ChestMovement[];
  shoulderMovement: ShoulderMovement[];
  diaphragmMovement: DiaphragmMovement[];
}

/**
 * Breath cycle information
 */
export interface BreathCycle {
  startTime: number; // milliseconds
  duration: number; // milliseconds
  phase: 'inhale' | 'exhale' | 'pause';
  intensity: number; // 0.0 to 1.0
  naturalness: number; // 0.0 to 1.0
}

/**
 * Chest movement for breathing
 */
export interface ChestMovement {
  timestamp: number; // milliseconds
  expansion: number; // 0.0 to 1.0
  velocity: number; // expansion rate
  naturalVariation: number; // 0.0 to 1.0
}

/**
 * Shoulder movement for breathing
 */
export interface ShoulderMovement {
  timestamp: number; // milliseconds
  elevation: number; // 0.0 to 1.0
  asymmetry: number; // 0.0 to 1.0 (left-right difference)
  tension: number; // 0.0 to 1.0
}

/**
 * Diaphragm movement for breathing
 */
export interface DiaphragmMovement {
  timestamp: number; // milliseconds
  contraction: number; // 0.0 to 1.0
  support: number; // breath support strength
  efficiency: number; // 0.0 to 1.0
}

/**
 * Head nod sequence for emphasis
 */
export interface HeadNodSequence {
  nods: HeadNod[];
  synchronization: NodSynchronization[];
  naturalness: number; // 0.0 to 1.0
}

/**
 * Individual head nod
 */
export interface HeadNod {
  startTime: number; // milliseconds
  duration: number; // milliseconds
  intensity: number; // 0.0 to 1.0
  type: 'single' | 'double' | 'continuous';
  direction: 'up_down' | 'left_right' | 'diagonal';
  emphasis: EmphasisLevel;
}

/**
 * Emphasis level for head nods
 */
export type EmphasisLevel = 'subtle' | 'moderate' | 'strong' | 'dramatic';

/**
 * Nod synchronization with speech
 */
export interface NodSynchronization {
  nodId: string;
  wordIndex: number;
  syllableIndex?: number;
  synchronizationType: 'onset' | 'peak' | 'offset';
  timingOffset: number; // milliseconds
}

/**
 * Audio stream for real-time processing
 */
export interface AudioStream {
  sampleRate: number; // Hz
  channels: number;
  bitDepth: number;
  bufferSize: number; // samples
  format: 'pcm' | 'float32' | 'int16';
  latency: number; // milliseconds
}

/**
 * Sync quality assessment
 */
export interface SyncQuality {
  overallScore: number; // 0.0 to 1.0
  timingAccuracy: number; // 0.0 to 1.0
  visualFidelity: number; // 0.0 to 1.0
  emotionalConsistency: number; // 0.0 to 1.0
  naturalness: number; // 0.0 to 1.0
  issues: SyncIssue[];
  recommendations: string[];
}

/**
 * Sync quality issue
 */
export interface SyncIssue {
  type: 'timing_drift' | 'visual_artifact' | 'emotional_mismatch' | 'unnatural_transition';
  severity: 'low' | 'medium' | 'high' | 'critical';
  timestamp: number; // milliseconds
  description: string;
  suggestedFix: string;
}

/**
 * Sentence break information
 */
export interface SentenceBreak {
  position: number; // character position in text
  timestamp: number; // milliseconds in audio
  type: 'period' | 'comma' | 'semicolon' | 'question' | 'exclamation';
  pauseDuration: number; // milliseconds
  breathingRequired: boolean;
}

/**
 * Word timing for emphasis synchronization
 */
export interface WordTiming {
  word: string;
  startTime: number; // milliseconds
  duration: number; // milliseconds
  emphasis: number; // 0.0 to 1.0
  syllables: SyllableTiming[];
  partOfSpeech?: string;
}

/**
 * Syllable timing information
 */
export interface SyllableTiming {
  syllable: string;
  startTime: number; // milliseconds
  duration: number; // milliseconds
  stress: 'primary' | 'secondary' | 'unstressed';
  phonemes: Phoneme[];
}

/**
 * Breathing pattern for synchronization
 */
export interface BreathingPattern {
  rate: number; // breaths per minute
  depth: number; // 0.0 to 1.0
  rhythm: 'regular' | 'irregular' | 'speech_adapted';
  pauseLocations: number[]; // timestamps in milliseconds
  naturalVariation: number; // 0.0 to 1.0
}

/**
 * Voice profile for personalized lip sync
 */
export interface VoiceProfile {
  gender: 'male' | 'female' | 'non-binary';
  age: number; // years
  accent: string;
  speakingRate: number; // words per minute
  pitchRange: [number, number]; // Hz min/max
  articulationClarity: number; // 0.0 to 1.0
  emotionalExpressiveness: number; // 0.0 to 1.0
  breathingPattern: BreathingPattern;
}

/**
 * Speaking style configuration
 */
export interface SpeakingStyle {
  formality: 'casual' | 'conversational' | 'formal' | 'presentation';
  energy: number; // 0.0 to 1.0
  articulation: number; // 0.0 to 1.0
  gestureFrequency: number; // 0.0 to 1.0
  eyeContact: number; // 0.0 to 1.0
  pauseFrequency: number; // 0.0 to 1.0
}

/**
 * Voice sample for calibration
 */
export interface VoiceSample {
  audioData: AudioBuffer;
  transcript: string;
  phonemes: PhonemeSequence;
  emotion: EmotionalState;
  quality: number; // 0.0 to 1.0
}

/**
 * Voice calibration result
 */
export interface VoiceCalibration {
  profile: VoiceProfile;
  phonemeMapping: Record<string, string>; // phoneme -> viseme
  timingAdjustments: TimingAdjustment[];
  emotionalModifiers: Record<string, EmotionModifier>;
  accuracy: number; // 0.0 to 1.0
}

/**
 * Timing adjustment for calibration
 */
export interface TimingAdjustment {
  phoneme: string;
  offsetCorrection: number; // milliseconds
  durationMultiplier: number; // 0.5 to 2.0
  confidence: number; // 0.0 to 1.0
}

/**
 * Lip sync configuration
 */
export interface LipSyncConfig {
  // Quality settings
  qualityLevel: 'low' | 'medium' | 'high' | 'ultra';
  targetAccuracy: number; // 0.0 to 1.0
  smoothingFactor: number; // 0.0 to 1.0
  
  // Timing settings
  latencyCompensation: number; // milliseconds
  bufferSize: number; // milliseconds
  lookaheadTime: number; // milliseconds
  
  // Emotional settings
  emotionalModulationEnabled: boolean;
  emotionalIntensity: number; // 0.0 to 1.0
  emotionalBlending: boolean;
  
  // Breathing settings
  breathingAnimationEnabled: boolean;
  breathingIntensity: number; // 0.0 to 1.0
  automaticBreathingPauses: boolean;
  
  // Performance settings
  realTimeProcessing: boolean;
  optimizeForBattery: boolean;
  cacheSize: number; // bytes
  
  // Platform-specific settings
  platformOptimizations: Record<string, unknown>;
}

/**
 * Lip sync performance metrics
 */
export interface LipSyncMetrics {
  performance: LipSyncPerformanceMetrics;
  quality: LipSyncQualityMetrics;
  accuracy: LipSyncAccuracyMetrics;
  usage: LipSyncUsageMetrics;
}

/**
 * Lip sync performance metrics
 */
export interface LipSyncPerformanceMetrics {
  processingLatency: number; // milliseconds
  throughput: number; // phonemes per second
  memoryUsage: number; // bytes
  cpuUsage: number; // percentage
  cacheHitRate: number; // 0.0 to 1.0
}

/**
 * Lip sync quality metrics
 */
export interface LipSyncQualityMetrics {
  overallQuality: number; // 0.0 to 1.0
  timingAccuracy: number; // 0.0 to 1.0
  visualFidelity: number; // 0.0 to 1.0
  emotionalConsistency: number; // 0.0 to 1.0
  naturalness: number; // 0.0 to 1.0
}

/**
 * Lip sync accuracy metrics
 */
export interface LipSyncAccuracyMetrics {
  phonemeAccuracy: number; // 0.0 to 1.0
  timingPrecision: number; // milliseconds RMS error
  visemeMapping: number; // 0.0 to 1.0
  emotionalAlignment: number; // 0.0 to 1.0
}

/**
 * Lip sync usage metrics
 */
export interface LipSyncUsageMetrics {
  phonemesProcessed: number;
  visemesGenerated: number;
  emotionalModulations: number;
  breathingAnimations: number;
  averageSessionDuration: number; // milliseconds
}

/**
 * Validation result for lip sync configuration
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
  latencyIncrease: number; // milliseconds
  memoryIncrease: number; // bytes
  cpuIncrease: number; // percentage
  batteryImpact: number; // percentage per hour
}

/**
 * Sync event callback
 */
export type SyncEventCallback = (
  eventType: 'started' | 'completed',
  duration: number,
  quality: SyncQuality
) => void;

/**
 * Sync error callback
 */
export type SyncErrorCallback = (
  error: SyncError,
  context: Record<string, unknown>
) => void;

/**
 * Sync error information
 */
export interface SyncError {
  type: 'processing_error' | 'timing_error' | 'quality_error' | 'resource_error';
  message: string;
  timestamp: number;
  recoverable: boolean;
  suggestedAction: string;
}

/**
 * Quality change callback
 */
export type QualityChangeCallback = (
  oldQuality: number,
  newQuality: number,
  reason: string
) => void;

/**
 * Lip Sync Engine factory for creating platform-specific implementations
 */
export interface LipSyncEngineFactory {
  createLipSyncEngine(config: LipSyncConfig): Promise<LipSyncEngine>;
  getDefaultConfig(): LipSyncConfig;
  validateConfig(config: LipSyncConfig): ValidationResult;
  getSupportedLanguages(): string[];
  getSupportedVoiceProfiles(): VoiceProfile[];
}

/**
 * Phoneme-to-viseme mapping configuration
 */
export interface PhonemeVisemeMapping {
  language: string;
  dialect?: string;
  mappings: Record<string, VisemeMapping>;
  customMappings?: Record<string, VisemeMapping>;
}

/**
 * Viseme mapping information
 */
export interface VisemeMapping {
  visemeId: string;
  mouthShape: MouthShape;
  transitionRules: TransitionRule[];
  emotionalVariations: Record<string, MouthShape>;
  contextualAdjustments: ContextualAdjustment[];
}

/**
 * Transition rule for viseme changes
 */
export interface TransitionRule {
  fromPhoneme?: string;
  toPhoneme?: string;
  duration: number; // milliseconds
  curve: import('../types/Common').AnimationCurve;
  conditions: string[];
}

/**
 * Contextual adjustment for visemes
 */
export interface ContextualAdjustment {
  context: 'word_initial' | 'word_final' | 'stressed' | 'unstressed' | 'fast_speech' | 'slow_speech';
  adjustment: Partial<MouthShape>;
  weight: number; // 0.0 to 1.0
}