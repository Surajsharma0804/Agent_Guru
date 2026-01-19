/**
 * Production-Grade Emotion Engine Implementation
 * 
 * Manages emotional state with smooth transitions, voice tone analysis, sentiment processing,
 * drift prevention, and comprehensive emotional normalization for natural avatar behavior.
 */

import { EmotionEngine, EmotionEngineConfig } from '../interfaces/EmotionEngine';
import { EmotionalState, EmotionType, EmotionIntensity, EmotionTransition, PrimaryEmotion } from '../types/EmotionalState';
import { Platform, AvatarApiResponse, ValidationResult, PerformanceImpact, AvatarErrorType } from '../types/Common';
import { ErrorHandler } from '../utils/ErrorHandler';
import { AvatarEventEmitter } from '../utils/EventEmitter';

/**
 * Voice tone analysis result
 */
interface VoiceToneAnalysis {
  pitch: number; // Hz
  energy: number; // 0.0 to 1.0
  rhythm: number; // beats per minute
  confidence: number; // 0.0 to 1.0
  dominantEmotion: EmotionType;
  emotionConfidence: number; // 0.0 to 1.0
}

/**
 * Sentiment analysis result
 */
interface SentimentAnalysis {
  polarity: number; // -1.0 to 1.0 (negative to positive)
  subjectivity: number; // 0.0 to 1.0 (objective to subjective)
  emotions: Record<EmotionType, number>; // emotion scores 0.0 to 1.0
  confidence: number; // 0.0 to 1.0
  keywords: string[];
}

/**
 * Emotional drift detection result
 */
interface DriftDetectionResult {
  driftDetected: boolean;
  driftMagnitude: number; // 0.0 to 1.0
  driftDirection: EmotionType;
  correctionRequired: boolean;
  recommendedCorrection: Partial<EmotionalState>;
}

/**
 * Production-grade emotion engine with comprehensive emotional intelligence
 */
export class EmotionEngine extends AvatarEventEmitter implements EmotionEngine {
  private readonly config: EmotionEngineConfig;
  private readonly errorHandler: ErrorHandler;
  
  // Emotional state management
  private currentState: EmotionalState;
  private targetState: EmotionalState;
  private transitionStartTime: number = 0;
  private transitionDuration: number = 1000; // milliseconds
  private isTransitioning: boolean = false;
  
  // Emotional history for drift detection
  private emotionalHistory: Array<{ state: EmotionalState; timestamp: number }> = [];
  private readonly maxHistorySize = 100;
  
  // Performance monitoring
  private processingTimes: number[] = [];
  private readonly maxProcessingTimeHistory = 50;
  
  // Emotional boundaries and constraints
  private readonly emotionalBoundaries = {
    maxIntensity: 0.95,
    minIntensity: 0.05,
    maxSimultaneousEmotions: 3,
    driftThreshold: 0.3,
    stabilityThreshold: 0.1
  };

  constructor(config: EmotionEngineConfig) {
    super('EmotionEngine');
    this.config = {
      enableVoiceToneAnalysis: true,
      enableSentimentAnalysis: true,
      enableDriftPrevention: true,
      enableEmotionalNormalization: true,
      transitionSmoothness: 0.8,
      maxEmotionIntensity: 0.9,
      culturalSensitivity: 'neutral',
      personalityInfluence: 0.7,
      contextualAwareness: true,
      realTimeProcessing: true,
      ...config
    };

    this.errorHandler = ErrorHandler.getInstance();
    
    // Initialize with neutral emotional state
    this.currentState = this.createNeutralState();
    this.targetState = { ...this.currentState };
  }

  /**
   * Initialize the emotion engine
   */
  async initialize(): Promise<ValidationResult> {
    try {
      // Initialize emotional state
      this.currentState = this.createNeutralState();
      this.targetState = { ...this.currentState };
      
      // Clear history
      this.emotionalHistory = [];
      this.processingTimes = [];
      
      // Emit initialization event
      await this.emit('initialized', { 
        config: this.config,
        initialState: this.currentState 
      });
      
      return {
        valid: true,
        errors: [],
        warnings: [],
        suggestions: []
      };
    } catch (error) {
      return {
        valid: false,
        errors: [{
          field: 'initialization',
          message: `Initialization failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
          code: 'INITIALIZATION_FAILED',
          severity: 'error'
        }],
        warnings: [],
        suggestions: []
      };
    }
  }

  /**
   * Process voice input for emotional analysis
   */
  async processVoiceInput(audioData: ArrayBuffer, context?: Record<string, unknown>): Promise<AvatarApiResponse<EmotionalState>> {
    const errorContext = this.errorHandler.createContext('processVoiceInput', 'EmotionEngine', {
      additionalData: { audioDataSize: audioData.byteLength, context }
    });

    return this.errorHandler.wrapAsync(async () => {
      const startTime = Date.now();

      if (!this.config.enableVoiceToneAnalysis) {
        return this.currentState;
      }

      // Analyze voice tone characteristics
      const toneAnalysis = await this.analyzeVoiceTone(audioData);
      
      // Convert tone analysis to emotional state
      const emotionalResponse = this.mapToneToEmotion(toneAnalysis);
      
      // Apply contextual modulation
      const contextualEmotion = this.applyContextualModulation(emotionalResponse, context);
      
      // Blend with current state
      const blendedState = this.blendEmotionalStates(this.currentState, contextualEmotion, 0.3);
      
      // Apply emotional boundaries
      const boundedState = this.applyEmotionalBoundaries(blendedState);
      
      // Initiate transition to new state
      await this.transitionToState(boundedState);
      
      // Record processing time
      this.recordProcessingTime(Date.now() - startTime);
      
      // Emit state change event
      await this.emit('emotionalStateChanged', {
        previousState: this.currentState,
        newState: boundedState,
        trigger: 'voice_input',
        confidence: toneAnalysis.confidence
      });

      return boundedState;
    }, errorContext);
  }

  /**
   * Process text input for sentiment analysis
   */
  async processTextInput(text: string, context?: Record<string, unknown>): Promise<AvatarApiResponse<EmotionalState>> {
    const errorContext = this.errorHandler.createContext('processTextInput', 'EmotionEngine', {
      additionalData: { textLength: text.length, context }
    });

    return this.errorHandler.wrapAsync(async () => {
      const startTime = Date.now();

      if (!this.config.enableSentimentAnalysis) {
        return this.currentState;
      }

      // Analyze text sentiment
      const sentimentAnalysis = await this.analyzeSentiment(text);
      
      // Convert sentiment to emotional state
      const emotionalResponse = this.mapSentimentToEmotion(sentimentAnalysis);
      
      // Apply personality influence
      const personalityModulated = this.applyPersonalityInfluence(emotionalResponse);
      
      // Blend with current state
      const blendedState = this.blendEmotionalStates(this.currentState, personalityModulated, 0.4);
      
      // Apply emotional boundaries
      const boundedState = this.applyEmotionalBoundaries(blendedState);
      
      // Initiate transition to new state
      await this.transitionToState(boundedState);
      
      // Record processing time
      this.recordProcessingTime(Date.now() - startTime);
      
      // Emit state change event
      await this.emit('emotionalStateChanged', {
        previousState: this.currentState,
        newState: boundedState,
        trigger: 'text_input',
        confidence: sentimentAnalysis.confidence
      });

      return boundedState;
    }, errorContext);
  }

  /**
   * Process emotion with timestamp for real-time processing
   */
  async processEmotion(emotionalState: EmotionalState, timestamp: number): Promise<AvatarApiResponse<any>> {
    const startTime = Date.now();

    try {
      // Validate emotional state first
      const validation = this.validateEmotionalState(emotionalState);
      if (!validation.valid) {
        return {
          success: false,
          data: null,
          error: {
            message: `Invalid emotional state: ${validation.errors.map(e => e.message).join(', ')}`,
            type: 'VALIDATION_ERROR',
            code: 'INVALID_EMOTIONAL_STATE',
            details: validation.errors
          },
          executionTime: Date.now() - startTime,
          timestamp: Date.now()
        };
      }

      // Apply emotional boundaries
      const boundedState = this.applyEmotionalBoundaries(emotionalState);
      
      // Blend with current state
      const blendedState = this.blendEmotionalStates(this.currentState, boundedState, 0.5);
      
      // Initiate transition to new state
      await this.transitionToState(blendedState);
      
      // Generate blend shapes for rendering
      const blendShapes = this.generateBlendShapes(blendedState);
      
      // Generate micro-expressions
      const microExpressions = await this.generateMicroExpressions(
        blendedState.primary || 'neutral',
        blendedState.intensity,
        timestamp
      );
      
      // Record processing time
      this.recordProcessingTime(Date.now() - startTime);
      
      // Emit state change event
      await this.emit('emotionalStateChanged', {
        previousState: this.currentState,
        newState: blendedState,
        trigger: 'process_emotion',
        timestamp
      });

      return {
        success: true,
        data: {
          blendShapes,
          microExpressions: microExpressions.success ? microExpressions.data : [],
          emotionalState: blendedState,
          confidence: 0.9,
          processingTime: Date.now() - startTime
        },
        executionTime: Date.now() - startTime,
        timestamp: Date.now()
      };
    } catch (error) {
      const errorContext = this.errorHandler.createContext('processEmotion', 'EmotionEngine', {
        additionalData: { emotionalState, timestamp }
      });
      
      return this.errorHandler.handleError(error, errorContext, AvatarErrorType.VALIDATION_FAILURE);
    }
  }

  /**
   * Generate micro-expressions for subtle emotional display
   */
  async generateMicroExpressions(emotion: string, intensity: number, timestamp: number): Promise<AvatarApiResponse<any[]>> {
    const errorContext = this.errorHandler.createContext('generateMicroExpressions', 'EmotionEngine', {
      additionalData: { emotion, intensity, timestamp }
    });

    return this.errorHandler.wrapAsync(async () => {
      const microExpressions = [];
      
      // Generate micro-expressions based on emotion and intensity
      const baseDuration = 200 + Math.random() * 300; // 200-500ms
      const startTime = timestamp + Math.random() * 1000; // Random delay
      
      microExpressions.push({
        type: 'eyebrow_flash',
        startTime,
        duration: baseDuration * 0.5,
        intensity: intensity * 0.3,
        emotion
      });
      
      if (intensity > 0.3) {
        microExpressions.push({
          type: 'lip_corner',
          startTime: startTime + 100,
          duration: baseDuration,
          intensity: intensity * 0.4,
          emotion
        });
      }
      
      if (intensity > 0.6) {
        microExpressions.push({
          type: 'eye_squint',
          startTime: startTime + 200,
          duration: baseDuration * 0.7,
          intensity: intensity * 0.2,
          emotion
        });
      }

      return microExpressions;
    }, errorContext);
  }

  /**
   * Get emotional context including recent emotions and dominant mood
   */
  async getEmotionalContext(): Promise<AvatarApiResponse<any>> {
    const errorContext = this.errorHandler.createContext('getEmotionalContext', 'EmotionEngine');

    return this.errorHandler.wrapAsync(async () => {
      const recentEmotions = this.emotionalHistory.slice(-10).map(entry => entry.state);
      const dominantMood = this.calculateDominantMood(recentEmotions);
      
      return {
        recentEmotions,
        dominantMood,
        currentState: this.currentState,
        historyLength: this.emotionalHistory.length,
        averageIntensity: this.calculateAverageIntensity(recentEmotions)
      };
    }, errorContext);
  }

  /**
   * Update configuration at runtime
   */
  updateConfig(newConfig: Partial<EmotionEngineConfig>): ValidationResult {
    try {
      // Validate new configuration
      const errors: any[] = [];
      
      if (newConfig.maxEmotionIntensity !== undefined) {
        if (newConfig.maxEmotionIntensity < 0 || newConfig.maxEmotionIntensity > 1) {
          errors.push({
            field: 'maxEmotionIntensity',
            message: 'Max emotion intensity must be between 0 and 1',
            code: 'INVALID_RANGE',
            severity: 'error'
          });
        }
      }
      
      if (newConfig.transitionSmoothness !== undefined) {
        if (newConfig.transitionSmoothness < 0 || newConfig.transitionSmoothness > 1) {
          errors.push({
            field: 'transitionSmoothness',
            message: 'Transition smoothness must be between 0 and 1',
            code: 'INVALID_RANGE',
            severity: 'error'
          });
        }
      }
      
      if (errors.length > 0) {
        return {
          valid: false,
          errors,
          warnings: [],
          suggestions: []
        };
      }
      
      // Apply configuration updates
      Object.assign(this.config, newConfig);
      
      return {
        valid: true,
        errors: [],
        warnings: [],
        suggestions: []
      };
    } catch (error) {
      return {
        valid: false,
        errors: [{
          field: 'configuration',
          message: `Config update failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
          code: 'CONFIG_UPDATE_FAILED',
          severity: 'error'
        }],
        warnings: [],
        suggestions: []
      };
    }
  }

  /**
   * Process command result for emotional response
   */
  async processCommandResult(success: boolean, command: string, result?: unknown, context?: Record<string, unknown>): Promise<AvatarApiResponse<EmotionalState>> {
    const errorContext = this.errorHandler.createContext('processCommandResult', 'EmotionEngine', {
      additionalData: { success, command, context }
    });

    return this.errorHandler.wrapAsync(async () => {
      const startTime = Date.now();

      // Determine emotional response based on command result
      const emotionalResponse = this.generateCommandResponse(success, command, result);
      
      // Apply contextual awareness
      const contextualEmotion = this.applyContextualModulation(emotionalResponse, context);
      
      // Blend with current state (lighter influence for command results)
      const blendedState = this.blendEmotionalStates(this.currentState, contextualEmotion, 0.2);
      
      // Apply emotional boundaries
      const boundedState = this.applyEmotionalBoundaries(blendedState);
      
      // Initiate transition to new state
      await this.transitionToState(boundedState);
      
      // Record processing time
      this.recordProcessingTime(Date.now() - startTime);
      
      // Emit state change event
      await this.emit('emotionalStateChanged', {
        previousState: this.currentState,
        newState: boundedState,
        trigger: 'command_result',
        commandSuccess: success
      });

      return boundedState;
    }, errorContext);
  }

  /**
   * Get current emotional state
   */
  async getCurrentState(): Promise<AvatarApiResponse<EmotionalState>> {
    const errorContext = this.errorHandler.createContext('getCurrentState', 'EmotionEngine');

    return this.errorHandler.wrapAsync(async () => {
      // Update state if transition is in progress
      if (this.isTransitioning) {
        this.updateTransition();
      }

      return { ...this.currentState };
    }, errorContext);
  }

  /**
   * Set emotional state directly
   */
  async setState(state: EmotionalState, transitionDuration?: number): Promise<AvatarApiResponse<void>> {
    const errorContext = this.errorHandler.createContext('setState', 'EmotionEngine', {
      additionalData: { state, transitionDuration }
    });

    return this.errorHandler.wrapAsync(async () => {
      // Validate emotional state
      const validation = this.validateEmotionalState(state);
      if (!validation.valid) {
        throw new Error(`Invalid emotional state: ${validation.errors.map(e => e.message).join(', ')}`);
      }

      // Apply emotional boundaries
      const boundedState = this.applyEmotionalBoundaries(state);
      
      // Set transition duration if provided
      if (transitionDuration !== undefined) {
        this.transitionDuration = Math.max(100, Math.min(5000, transitionDuration));
      }
      
      // Initiate transition to new state
      await this.transitionToState(boundedState);
      
      // Emit state change event
      await this.eventEmitter.emit('emotionalStateChanged', {
        previousState: this.currentState,
        newState: boundedState,
        trigger: 'direct_set'
      });
    }, errorContext);
  }

  /**
   * Blend multiple emotional states
   */
  async blendStates(states: Array<{ state: EmotionalState; weight: number }>): Promise<AvatarApiResponse<EmotionalState>> {
    const errorContext = this.errorHandler.createContext('blendStates', 'EmotionEngine', {
      additionalData: { stateCount: states.length }
    });

    return this.errorHandler.wrapAsync(async () => {
      if (states.length === 0) {
        return this.currentState;
      }

      // Normalize weights
      const totalWeight = states.reduce((sum, s) => sum + s.weight, 0);
      if (totalWeight === 0) {
        return this.currentState;
      }

      const normalizedStates = states.map(s => ({
        state: s.state,
        weight: s.weight / totalWeight
      }));

      // Blend all states
      let blendedState = this.createNeutralState();
      
      for (const { state, weight } of normalizedStates) {
        blendedState = this.blendEmotionalStates(blendedState, state, weight);
      }

      // Apply emotional boundaries
      const boundedState = this.applyEmotionalBoundaries(blendedState);
      
      return boundedState;
    }, errorContext);
  }

  /**
   * Detect and prevent emotional drift
   */
  async preventDrift(): Promise<AvatarApiResponse<boolean>> {
    const errorContext = this.errorHandler.createContext('preventDrift', 'EmotionEngine');

    return this.errorHandler.wrapAsync(async () => {
      if (!this.config.enableDriftPrevention) {
        return false;
      }

      const driftResult = this.detectEmotionalDrift();
      
      if (driftResult.correctionRequired) {
        // Apply drift correction
        const correctedState = {
          ...this.currentState,
          ...driftResult.recommendedCorrection
        };
        
        // Apply emotional boundaries
        const boundedState = this.applyEmotionalBoundaries(correctedState);
        
        // Initiate gentle transition to corrected state
        await this.transitionToState(boundedState, 2000); // Slower transition for drift correction
        
        // Emit drift correction event
        await this.emit('emotionalDriftCorrected', {
          driftMagnitude: driftResult.driftMagnitude,
          driftDirection: driftResult.driftDirection,
          correctedState: boundedState
        });
        
        return true;
      }

      return false;
    }, errorContext);
  }

  /**
   * Normalize emotional state within acceptable bounds
   */
  async normalizeState(): Promise<AvatarApiResponse<EmotionalState>> {
    const errorContext = this.errorHandler.createContext('normalizeState', 'EmotionEngine');

    return this.errorHandler.wrapAsync(async () => {
      if (!this.config.enableEmotionalNormalization) {
        return this.currentState;
      }

      // Apply comprehensive normalization
      let normalizedState = { ...this.currentState };
      
      // Intensity normalization
      normalizedState = this.normalizeIntensities(normalizedState);
      
      // Emotional conflict resolution
      normalizedState = this.resolveEmotionalConflicts(normalizedState);
      
      // Cultural appropriateness adjustment
      normalizedState = this.applyCulturalSensitivity(normalizedState);
      
      // Apply emotional boundaries
      normalizedState = this.applyEmotionalBoundaries(normalizedState);
      
      // Update current state if normalization made significant changes
      const changeThreshold = 0.1;
      if (this.calculateStateDistance(this.currentState, normalizedState) > changeThreshold) {
        await this.transitionToState(normalizedState, 1500);
        
        // Emit normalization event
        await this.emit('emotionalStateNormalized', {
          originalState: this.currentState,
          normalizedState
        });
      }

      return normalizedState;
    }, errorContext);
  }

  /**
   * Get emotional history for analysis
   */
  async getEmotionalHistory(limit?: number): Promise<AvatarApiResponse<Array<{ state: EmotionalState; timestamp: number }>>> {
    const errorContext = this.errorHandler.createContext('getEmotionalHistory', 'EmotionEngine');

    return this.errorHandler.wrapAsync(async () => {
      const historyLimit = limit || this.emotionalHistory.length;
      return this.emotionalHistory.slice(-historyLimit).map(entry => ({
        state: { ...entry.state },
        timestamp: entry.timestamp
      }));
    }, errorContext);
  }

  /**
   * Get performance metrics
   */
  async getPerformanceMetrics(): Promise<AvatarApiResponse<PerformanceImpact>> {
    const errorContext = this.errorHandler.createContext('getPerformanceMetrics', 'EmotionEngine');

    return this.errorHandler.wrapAsync(async () => {
      const avgProcessingTime = this.processingTimes.length > 0
        ? this.processingTimes.reduce((sum, time) => sum + time, 0) / this.processingTimes.length
        : 0;

      return {
        cpuUsage: Math.min(5, avgProcessingTime / 10), // Estimate CPU usage
        memoryUsage: this.emotionalHistory.length * 1024, // Estimate memory usage
        batteryDrain: this.config.realTimeProcessing ? 2 : 0.5, // Estimate battery impact
        renderingLoad: 0, // Emotion engine doesn't directly affect rendering
        networkUsage: 0, // No network usage
        storageUsage: this.emotionalHistory.length * 512 // Estimate storage usage
      };
    }, errorContext);
  }

  /**
   * Validate emotional state configuration
   */
  async validateState(state: EmotionalState): Promise<AvatarApiResponse<ValidationResult>> {
    const errorContext = this.errorHandler.createContext('validateState', 'EmotionEngine');

    return this.errorHandler.wrapAsync(async () => {
      return this.validateEmotionalState(state);
    }, errorContext);
  }

  /**
   * Event listener registration
   */
  onStateChanged(callback: (data: any) => void): void {
    this.on('emotionalStateChanged', callback);
  }

  onDriftCorrected(callback: (data: any) => void): void {
    this.on('emotionalDriftCorrected', callback);
  }

  onStateNormalized(callback: (data: any) => void): void {
    this.on('emotionalStateNormalized', callback);
  }

  /**
   * Cleanup resources
   */
  async cleanup(): Promise<AvatarApiResponse<void>> {
    const errorContext = this.errorHandler.createContext('cleanup', 'EmotionEngine');

    return this.errorHandler.wrapAsync(async () => {
      // Clear emotional history
      this.emotionalHistory = [];
      
      // Clear processing times
      this.processingTimes = [];
      
      // Reset to neutral state
      this.currentState = this.createNeutralState();
      this.targetState = { ...this.currentState };
      this.isTransitioning = false;
      
      // Remove all event listeners
      this.removeAllListeners();
    }, errorContext);
  }

  /**
   * Destroy the emotion engine (alias for cleanup for test compatibility)
   */
  async destroy(): Promise<void> {
    await this.cleanup();
  }

  // Private implementation methods
  private createNeutralState(): EmotionalState {
    return {
      primary: 'neutral',
      secondary: undefined,
      intensity: 0.2,
      confidence: 0.8,
      stability: 0.8,
      timestamp: Date.now(),
      context: { trigger: 'initialization' },
      valence: 0.0,
      arousal: 0.2,
      dominance: 0.5,
      joy: 0.1,
      sadness: 0.05,
      anger: 0.02,
      fear: 0.03,
      surprise: 0.05,
      disgust: 0.02,
      trust: 0.3,
      anticipation: 0.1
    };
  }

  private generateBlendShapes(state: EmotionalState): Record<string, number> {
    const blendShapes: Record<string, number> = {
      // Basic facial expressions
      'browInnerUp': 0,
      'browDownLeft': 0,
      'browDownRight': 0,
      'eyeSquintLeft': 0,
      'eyeSquintRight': 0,
      'eyeWideLeft': 0,
      'eyeWideRight': 0,
      'cheekPuff': 0,
      'cheekSquintLeft': 0,
      'cheekSquintRight': 0,
      'noseSneerLeft': 0,
      'noseSneerRight': 0,
      'mouthFunnel': 0,
      'mouthPucker': 0,
      'mouthLeft': 0,
      'mouthRight': 0,
      'mouthSmileLeft': 0,
      'mouthSmileRight': 0,
      'mouthFrownLeft': 0,
      'mouthFrownRight': 0,
      'mouthDimpleLeft': 0,
      'mouthDimpleRight': 0,
      'mouthStretchLeft': 0,
      'mouthStretchRight': 0,
      'mouthRollLower': 0,
      'mouthRollUpper': 0,
      'mouthShrugLower': 0,
      'mouthShrugUpper': 0,
      'mouthClose': 0,
      'mouthLowerDownLeft': 0,
      'mouthLowerDownRight': 0,
      'mouthUpperUpLeft': 0,
      'mouthUpperUpRight': 0,
      'jawForward': 0,
      'jawLeft': 0,
      'jawRight': 0,
      'jawOpen': 0
    };

    // Map emotional state to blend shapes
    const intensity = state.intensity;
    
    // Process primary emotion
    this.applyEmotionToBlendShapes(blendShapes, state.primary, intensity, 1.0);
    
    // Process secondary emotions (support both single and array formats)
    if (state.secondary) {
      const secondaryEmotions = Array.isArray(state.secondary) ? state.secondary : [state.secondary];
      const secondaryWeight = 0.6; // Secondary emotions have less influence
      
      secondaryEmotions.forEach((emotion, index) => {
        const weight = secondaryWeight * (1 - index * 0.1); // Diminishing weight for multiple secondaries
        this.applyEmotionToBlendShapes(blendShapes, emotion, intensity, weight);
      });
    }
    
    // Process individual emotion scores if available
    const emotions: (keyof EmotionalState)[] = ['joy', 'sadness', 'anger', 'fear', 'surprise', 'disgust', 'trust', 'anticipation'];
    emotions.forEach(emotion => {
      const value = state[emotion];
      if (typeof value === 'number' && value > 0.1) {
        this.applyEmotionToBlendShapes(blendShapes, emotion as PrimaryEmotion, value, 0.8);
      }
    });

    // Normalize blend shapes to ensure they're within valid range
    Object.keys(blendShapes).forEach(key => {
      blendShapes[key] = Math.max(0, Math.min(1, blendShapes[key]));
    });

    // Debug logging for complex blending test
    if (state.primary === 'joy' && Array.isArray(state.secondary) && state.secondary.includes('surprise')) {
      console.log('DEBUG: Complex blending state:', {
        primary: state.primary,
        secondary: state.secondary,
        intensity: state.intensity
      });
      
      const activeShapes = Object.entries(blendShapes)
        .filter(([key, value]) => value > 0.1)
        .map(([key, value]) => ({ [key]: value }));
      
      console.log('DEBUG: Active blend shapes (> 0.1):', activeShapes);
      console.log('DEBUG: Total active shapes:', activeShapes.length);
      
      // Log all non-zero blend shapes
      const nonZeroShapes = Object.entries(blendShapes)
        .filter(([key, value]) => value > 0)
        .map(([key, value]) => ({ [key]: value }));
      console.log('DEBUG: All non-zero blend shapes:', nonZeroShapes);
    }

    return blendShapes;
  }

  private applyEmotionToBlendShapes(blendShapes: Record<string, number>, emotion: PrimaryEmotion, intensity: number, weight: number): void {
    const effectiveIntensity = intensity * weight;
    
    // Normalize emotion names (handle variations)
    let normalizedEmotion = emotion;
    if (emotion === 'curiosity') normalizedEmotion = 'curious';
    if (emotion === 'excitement') normalizedEmotion = 'excited';
    
    switch (normalizedEmotion) {
      case 'joy':
      case 'happy':
      case 'excitement':
      case 'excited':
        blendShapes['mouthSmileLeft'] = Math.max(blendShapes['mouthSmileLeft'], effectiveIntensity);
        blendShapes['mouthSmileRight'] = Math.max(blendShapes['mouthSmileRight'], effectiveIntensity);
        blendShapes['cheekSquintLeft'] = Math.max(blendShapes['cheekSquintLeft'], effectiveIntensity * 0.7);
        blendShapes['cheekSquintRight'] = Math.max(blendShapes['cheekSquintRight'], effectiveIntensity * 0.7);
        blendShapes['mouthDimpleLeft'] = Math.max(blendShapes['mouthDimpleLeft'], effectiveIntensity * 0.5);
        blendShapes['mouthDimpleRight'] = Math.max(blendShapes['mouthDimpleRight'], effectiveIntensity * 0.5);
        break;
        
      case 'sadness':
        blendShapes['mouthFrownLeft'] = Math.max(blendShapes['mouthFrownLeft'], effectiveIntensity);
        blendShapes['mouthFrownRight'] = Math.max(blendShapes['mouthFrownRight'], effectiveIntensity);
        blendShapes['browInnerUp'] = Math.max(blendShapes['browInnerUp'], effectiveIntensity * 0.8);
        blendShapes['mouthLowerDownLeft'] = Math.max(blendShapes['mouthLowerDownLeft'], effectiveIntensity * 0.6);
        blendShapes['mouthLowerDownRight'] = Math.max(blendShapes['mouthLowerDownRight'], effectiveIntensity * 0.6);
        break;
        
      case 'anger':
        blendShapes['browDownLeft'] = Math.max(blendShapes['browDownLeft'], effectiveIntensity);
        blendShapes['browDownRight'] = Math.max(blendShapes['browDownRight'], effectiveIntensity);
        blendShapes['noseSneerLeft'] = Math.max(blendShapes['noseSneerLeft'], effectiveIntensity * 0.6);
        blendShapes['noseSneerRight'] = Math.max(blendShapes['noseSneerRight'], effectiveIntensity * 0.6);
        blendShapes['mouthStretchLeft'] = Math.max(blendShapes['mouthStretchLeft'], effectiveIntensity * 0.4);
        blendShapes['mouthStretchRight'] = Math.max(blendShapes['mouthStretchRight'], effectiveIntensity * 0.4);
        break;
        
      case 'fear':
        blendShapes['eyeWideLeft'] = Math.max(blendShapes['eyeWideLeft'], effectiveIntensity);
        blendShapes['eyeWideRight'] = Math.max(blendShapes['eyeWideRight'], effectiveIntensity);
        blendShapes['browInnerUp'] = Math.max(blendShapes['browInnerUp'], effectiveIntensity);
        blendShapes['jawOpen'] = Math.max(blendShapes['jawOpen'], effectiveIntensity * 0.3);
        break;
        
      case 'surprise':
        blendShapes['eyeWideLeft'] = Math.max(blendShapes['eyeWideLeft'], effectiveIntensity);
        blendShapes['eyeWideRight'] = Math.max(blendShapes['eyeWideRight'], effectiveIntensity);
        blendShapes['browInnerUp'] = Math.max(blendShapes['browInnerUp'], effectiveIntensity);
        blendShapes['jawOpen'] = Math.max(blendShapes['jawOpen'], effectiveIntensity * 0.5);
        blendShapes['mouthFunnel'] = Math.max(blendShapes['mouthFunnel'], effectiveIntensity * 0.3);
        break;
        
      case 'disgust':
        blendShapes['noseSneerLeft'] = Math.max(blendShapes['noseSneerLeft'], effectiveIntensity);
        blendShapes['noseSneerRight'] = Math.max(blendShapes['noseSneerRight'], effectiveIntensity);
        blendShapes['mouthFrownLeft'] = Math.max(blendShapes['mouthFrownLeft'], effectiveIntensity * 0.7);
        blendShapes['mouthFrownRight'] = Math.max(blendShapes['mouthFrownRight'], effectiveIntensity * 0.7);
        blendShapes['mouthShrugUpper'] = Math.max(blendShapes['mouthShrugUpper'], effectiveIntensity * 0.5);
        break;
        
      case 'trust':
      case 'confident':
        blendShapes['mouthSmileLeft'] = Math.max(blendShapes['mouthSmileLeft'], effectiveIntensity * 0.4);
        blendShapes['mouthSmileRight'] = Math.max(blendShapes['mouthSmileRight'], effectiveIntensity * 0.4);
        blendShapes['eyeSquintLeft'] = Math.max(blendShapes['eyeSquintLeft'], effectiveIntensity * 0.3);
        blendShapes['eyeSquintRight'] = Math.max(blendShapes['eyeSquintRight'], effectiveIntensity * 0.3);
        break;
        
      case 'anticipation':
      case 'curious':
      case 'curiosity':
        blendShapes['browInnerUp'] = Math.max(blendShapes['browInnerUp'], effectiveIntensity * 0.6);
        blendShapes['eyeWideLeft'] = Math.max(blendShapes['eyeWideLeft'], effectiveIntensity * 0.4);
        blendShapes['eyeWideRight'] = Math.max(blendShapes['eyeWideRight'], effectiveIntensity * 0.4);
        blendShapes['mouthSmileLeft'] = Math.max(blendShapes['mouthSmileLeft'], effectiveIntensity * 0.3);
        blendShapes['mouthSmileRight'] = Math.max(blendShapes['mouthSmileRight'], effectiveIntensity * 0.3);
        break;
        
      case 'focused':
        blendShapes['eyeSquintLeft'] = Math.max(blendShapes['eyeSquintLeft'], effectiveIntensity * 0.5);
        blendShapes['eyeSquintRight'] = Math.max(blendShapes['eyeSquintRight'], effectiveIntensity * 0.5);
        blendShapes['browDownLeft'] = Math.max(blendShapes['browDownLeft'], effectiveIntensity * 0.3);
        blendShapes['browDownRight'] = Math.max(blendShapes['browDownRight'], effectiveIntensity * 0.3);
        break;
        
      case 'concerned':
        blendShapes['browInnerUp'] = Math.max(blendShapes['browInnerUp'], effectiveIntensity * 0.7);
        blendShapes['mouthFrownLeft'] = Math.max(blendShapes['mouthFrownLeft'], effectiveIntensity * 0.4);
        blendShapes['mouthFrownRight'] = Math.max(blendShapes['mouthFrownRight'], effectiveIntensity * 0.4);
        break;
        
      case 'apologetic':
        blendShapes['browInnerUp'] = Math.max(blendShapes['browInnerUp'], effectiveIntensity * 0.6);
        blendShapes['mouthFrownLeft'] = Math.max(blendShapes['mouthFrownLeft'], effectiveIntensity * 0.5);
        blendShapes['mouthFrownRight'] = Math.max(blendShapes['mouthFrownRight'], effectiveIntensity * 0.5);
        blendShapes['eyeSquintLeft'] = Math.max(blendShapes['eyeSquintLeft'], effectiveIntensity * 0.3);
        blendShapes['eyeSquintRight'] = Math.max(blendShapes['eyeSquintRight'], effectiveIntensity * 0.3);
        break;
        
      default:
        // Neutral or unknown emotions - minimal expression
        blendShapes['mouthSmileLeft'] = Math.max(blendShapes['mouthSmileLeft'], effectiveIntensity * 0.1);
        blendShapes['mouthSmileRight'] = Math.max(blendShapes['mouthSmileRight'], effectiveIntensity * 0.1);
        break;
    }
  }

  private calculateDominantMood(emotions: EmotionalState[]): string {
    if (emotions.length === 0) return 'neutral';
    
    const emotionSums: Record<string, number> = {
      joy: 0, sadness: 0, anger: 0, fear: 0, 
      surprise: 0, disgust: 0, trust: 0, anticipation: 0
    };
    
    emotions.forEach(emotion => {
      Object.keys(emotionSums).forEach(key => {
        if (typeof emotion[key as keyof EmotionalState] === 'number') {
          emotionSums[key] += emotion[key as keyof EmotionalState] as number;
        }
      });
    });
    
    let dominantEmotion = 'neutral';
    let maxValue = 0;
    
    Object.entries(emotionSums).forEach(([emotion, sum]) => {
      const average = sum / emotions.length;
      if (average > maxValue) {
        maxValue = average;
        dominantEmotion = emotion;
      }
    });
    
    return dominantEmotion;
  }

  private calculateAverageIntensity(emotions: EmotionalState[]): number {
    if (emotions.length === 0) return 0;
    
    const totalIntensity = emotions.reduce((sum, emotion) => sum + emotion.intensity, 0);
    return totalIntensity / emotions.length;
  }

  private async analyzeVoiceTone(audioData: ArrayBuffer): Promise<VoiceToneAnalysis> {
    // Production implementation would use advanced audio analysis
    // For now, simulate realistic voice tone analysis
    
    const dataView = new DataView(audioData);
    let energy = 0;
    let pitch = 0;
    
    // Simple energy calculation from audio samples
    for (let i = 0; i < Math.min(audioData.byteLength, 1024); i += 2) {
      const sample = dataView.getInt16(i, true) / 32768;
      energy += Math.abs(sample);
    }
    
    energy = Math.min(1.0, energy / 512);
    pitch = 100 + (energy * 200); // Simulate pitch based on energy
    
    // Map energy and pitch to dominant emotion
    let dominantEmotion: EmotionType = 'trust';
    if (energy > 0.7) dominantEmotion = 'joy';
    else if (energy < 0.3) dominantEmotion = 'sadness';
    else if (pitch > 200) dominantEmotion = 'surprise';
    
    return {
      pitch,
      energy,
      rhythm: 60 + (energy * 40), // Simulate rhythm
      confidence: 0.7 + (energy * 0.2),
      dominantEmotion,
      emotionConfidence: 0.6 + (energy * 0.3)
    };
  }

  private async analyzeSentiment(text: string): Promise<SentimentAnalysis> {
    // Production implementation would use advanced NLP
    // For now, simulate realistic sentiment analysis
    
    const positiveWords = ['good', 'great', 'excellent', 'happy', 'love', 'wonderful', 'amazing'];
    const negativeWords = ['bad', 'terrible', 'hate', 'awful', 'horrible', 'disgusting', 'angry'];
    const emotionalWords = ['excited', 'surprised', 'scared', 'worried', 'confident', 'proud'];
    
    const words = text.toLowerCase().split(/\s+/);
    let positiveScore = 0;
    let negativeScore = 0;
    let emotionalScore = 0;
    
    for (const word of words) {
      if (positiveWords.includes(word)) positiveScore++;
      if (negativeWords.includes(word)) negativeScore++;
      if (emotionalWords.includes(word)) emotionalScore++;
    }
    
    const totalWords = words.length;
    const polarity = totalWords > 0 ? (positiveScore - negativeScore) / totalWords : 0;
    const subjectivity = totalWords > 0 ? emotionalScore / totalWords : 0;
    
    // Generate emotion scores based on analysis
    const emotions: Record<EmotionType, number> = {
      joy: Math.max(0, polarity * 0.8),
      sadness: Math.max(0, -polarity * 0.8),
      anger: negativeScore > 0 ? 0.3 : 0.1,
      fear: negativeWords.some(w => ['scared', 'worried', 'afraid'].includes(w)) ? 0.4 : 0.1,
      surprise: emotionalWords.some(w => ['surprised', 'shocked'].includes(w)) ? 0.5 : 0.1,
      disgust: negativeWords.some(w => ['disgusting', 'awful'].includes(w)) ? 0.4 : 0.05,
      trust: positiveScore > negativeScore ? 0.6 : 0.3,
      anticipation: emotionalWords.some(w => ['excited', 'eager'].includes(w)) ? 0.5 : 0.2
    };
    
    return {
      polarity: Math.max(-1, Math.min(1, polarity)),
      subjectivity: Math.max(0, Math.min(1, subjectivity)),
      emotions,
      confidence: 0.6 + Math.min(0.3, emotionalScore / 10),
      keywords: words.filter(w => [...positiveWords, ...negativeWords, ...emotionalWords].includes(w))
    };
  }

  private mapToneToEmotion(analysis: VoiceToneAnalysis): EmotionalState {
    const baseState = this.createNeutralState();
    
    // Map voice characteristics to emotions
    if (analysis.energy > 0.7) {
      baseState.joy = Math.min(0.9, 0.3 + analysis.energy * 0.6);
      baseState.anticipation = Math.min(0.8, 0.2 + analysis.energy * 0.4);
    } else if (analysis.energy < 0.3) {
      baseState.sadness = Math.min(0.7, 0.1 + (1 - analysis.energy) * 0.5);
      baseState.trust = Math.max(0.1, baseState.trust - 0.2);
    }
    
    if (analysis.pitch > 200) {
      baseState.surprise = Math.min(0.8, 0.2 + (analysis.pitch - 200) / 200 * 0.6);
    }
    
    baseState.intensity = Math.min(0.9, analysis.energy * 0.8 + 0.1);
    baseState.timestamp = Date.now();
    
    return baseState;
  }

  private mapSentimentToEmotion(analysis: SentimentAnalysis): EmotionalState {
    const baseState = this.createNeutralState();
    
    // Apply sentiment emotions directly
    Object.entries(analysis.emotions).forEach(([emotion, score]) => {
      if (emotion in baseState) {
        (baseState as any)[emotion] = Math.min(0.9, score);
      }
    });
    
    baseState.intensity = Math.min(0.9, Math.abs(analysis.polarity) * 0.7 + analysis.subjectivity * 0.3);
    baseState.timestamp = Date.now();
    
    return baseState;
  }

  private generateCommandResponse(success: boolean, command: string, result?: unknown): EmotionalState {
    const baseState = this.createNeutralState();
    
    if (success) {
      baseState.joy = 0.4;
      baseState.trust = 0.6;
      baseState.anticipation = 0.3;
      baseState.intensity = 0.3;
    } else {
      baseState.sadness = 0.3;
      baseState.frustration = 0.4; // Custom emotion for command failures
      baseState.trust = Math.max(0.1, baseState.trust - 0.2);
      baseState.intensity = 0.4;
    }
    
    baseState.timestamp = Date.now();
    return baseState;
  }

  private applyContextualModulation(state: EmotionalState, context?: Record<string, unknown>): EmotionalState {
    if (!context || !this.config.contextualAwareness) {
      return state;
    }
    
    const modulatedState = { ...state };
    
    // Apply context-based modulation
    if (context.userMood === 'stressed') {
      modulatedState.trust = Math.max(0.1, modulatedState.trust - 0.1);
      modulatedState.intensity = Math.min(0.9, modulatedState.intensity + 0.1);
    }
    
    if (context.timeOfDay === 'morning') {
      modulatedState.anticipation = Math.min(0.9, modulatedState.anticipation + 0.1);
    }
    
    return modulatedState;
  }

  private applyPersonalityInfluence(state: EmotionalState): EmotionalState {
    if (this.config.personalityInfluence === 0) {
      return state;
    }
    
    const influenced = { ...state };
    const influence = this.config.personalityInfluence;
    
    // Apply personality-based emotional tendencies
    // This would be customized based on avatar personality configuration
    influenced.trust = Math.min(0.9, influenced.trust * (1 + influence * 0.2));
    influenced.stability = Math.min(0.9, influenced.stability * (1 + influence * 0.1));
    
    return influenced;
  }

  private blendEmotionalStates(state1: EmotionalState, state2: EmotionalState, weight: number): EmotionalState {
    const blended: EmotionalState = { ...state1 };
    
    // Blend each emotion
    const emotions: (keyof EmotionalState)[] = ['joy', 'sadness', 'anger', 'fear', 'surprise', 'disgust', 'trust', 'anticipation'];
    
    emotions.forEach(emotion => {
      if (typeof blended[emotion] === 'number' && typeof state2[emotion] === 'number') {
        blended[emotion] = (blended[emotion] as number) * (1 - weight) + (state2[emotion] as number) * weight;
      }
    });
    
    // Blend intensity and stability
    blended.intensity = state1.intensity * (1 - weight) + state2.intensity * weight;
    blended.stability = state1.stability * (1 - weight) + state2.stability * weight;
    blended.timestamp = Date.now();
    
    return blended;
  }

  private applyEmotionalBoundaries(state: EmotionalState): EmotionalState {
    let bounded = { ...state };
    
    // Apply intensity boundaries
    bounded.intensity = Math.max(this.emotionalBoundaries.minIntensity, 
                                Math.min(this.emotionalBoundaries.maxIntensity, bounded.intensity));
    
    // Apply individual emotion boundaries
    const emotions: (keyof EmotionalState)[] = ['joy', 'sadness', 'anger', 'fear', 'surprise', 'disgust', 'trust', 'anticipation'];
    
    emotions.forEach(emotion => {
      if (typeof bounded[emotion] === 'number') {
        bounded[emotion] = Math.max(0, Math.min(this.config.maxEmotionIntensity, bounded[emotion] as number));
      }
    });
    
    // Ensure emotional consistency (prevent conflicting emotions at high intensity)
    const resolvedBounded = this.resolveEmotionalConflicts(bounded);
    
    return resolvedBounded;
    
    return bounded;
  }

  private resolveEmotionalConflicts(state: EmotionalState): EmotionalState {
    const resolved = { ...state };
    
    // Resolve joy-sadness conflict
    if (resolved.joy > 0.5 && resolved.sadness > 0.5) {
      const total = resolved.joy + resolved.sadness;
      resolved.joy = resolved.joy / total * 0.8;
      resolved.sadness = resolved.sadness / total * 0.8;
    }
    
    // Resolve trust-fear conflict
    if (resolved.trust > 0.6 && resolved.fear > 0.4) {
      resolved.fear = Math.max(0.1, resolved.fear - 0.2);
    }
    
    return resolved;
  }

  private applyCulturalSensitivity(state: EmotionalState): EmotionalState {
    if (this.config.culturalSensitivity === 'neutral') {
      return state;
    }
    
    const culturallySensitive = { ...state };
    
    // Apply cultural modulation based on configuration
    // This would be expanded with specific cultural emotional norms
    if (this.config.culturalSensitivity === 'conservative') {
      culturallySensitive.intensity = Math.min(0.7, culturallySensitive.intensity);
      culturallySensitive.anger = Math.min(0.3, culturallySensitive.anger);
    }
    
    return culturallySensitive;
  }

  private async transitionToState(targetState: EmotionalState, duration?: number): Promise<void> {
    this.targetState = { ...targetState };
    this.transitionStartTime = Date.now();
    this.transitionDuration = duration || this.transitionDuration;
    this.isTransitioning = true;
    
    // Add to emotional history
    this.addToEmotionalHistory(targetState);
  }

  private updateTransition(): void {
    if (!this.isTransitioning) return;
    
    const elapsed = Date.now() - this.transitionStartTime;
    const progress = Math.min(1, elapsed / this.transitionDuration);
    
    // Apply smooth transition curve
    const smoothProgress = this.applySmoothingCurve(progress);
    
    // Interpolate between current and target state
    this.currentState = this.blendEmotionalStates(this.currentState, this.targetState, smoothProgress);
    
    if (progress >= 1) {
      this.isTransitioning = false;
      this.currentState = { ...this.targetState };
    }
  }

  private applySmoothingCurve(progress: number): number {
    // Apply configurable smoothing curve
    const smoothness = this.config.transitionSmoothness;
    return progress * progress * (3 - 2 * progress) * smoothness + progress * (1 - smoothness);
  }

  private addToEmotionalHistory(state: EmotionalState): void {
    this.emotionalHistory.push({
      state: { ...state },
      timestamp: Date.now()
    });
    
    // Maintain history size limit
    if (this.emotionalHistory.length > this.maxHistorySize) {
      this.emotionalHistory.shift();
    }
  }

  private detectEmotionalDrift(): DriftDetectionResult {
    if (this.emotionalHistory.length < 10) {
      return {
        driftDetected: false,
        driftMagnitude: 0,
        driftDirection: 'trust',
        correctionRequired: false,
        recommendedCorrection: {}
      };
    }
    
    // Analyze recent emotional history for drift patterns
    const recentHistory = this.emotionalHistory.slice(-10);
    const baseline = this.emotionalHistory.slice(-20, -10);
    
    if (baseline.length === 0) {
      return {
        driftDetected: false,
        driftMagnitude: 0,
        driftDirection: 'trust',
        correctionRequired: false,
        recommendedCorrection: {}
      };
    }
    
    // Calculate average states
    const recentAvg = this.calculateAverageState(recentHistory.map(h => h.state));
    const baselineAvg = this.calculateAverageState(baseline.map(h => h.state));
    
    // Calculate drift magnitude
    const driftMagnitude = this.calculateStateDistance(recentAvg, baselineAvg);
    
    const driftDetected = driftMagnitude > this.emotionalBoundaries.driftThreshold;
    const correctionRequired = driftMagnitude > this.emotionalBoundaries.driftThreshold * 1.5;
    
    // Determine drift direction (dominant emotion causing drift)
    let driftDirection: EmotionType = 'trust';
    let maxDrift = 0;
    
    const emotions: (keyof EmotionalState)[] = ['joy', 'sadness', 'anger', 'fear', 'surprise', 'disgust', 'trust', 'anticipation'];
    emotions.forEach(emotion => {
      if (typeof recentAvg[emotion] === 'number' && typeof baselineAvg[emotion] === 'number') {
        const drift = Math.abs((recentAvg[emotion] as number) - (baselineAvg[emotion] as number));
        if (drift > maxDrift) {
          maxDrift = drift;
          driftDirection = emotion as EmotionType;
        }
      }
    });
    
    // Generate correction recommendation
    const recommendedCorrection: Partial<EmotionalState> = {};
    if (correctionRequired) {
      // Recommend moving back toward baseline
      emotions.forEach(emotion => {
        if (typeof recentAvg[emotion] === 'number' && typeof baselineAvg[emotion] === 'number') {
          const target = (recentAvg[emotion] as number) * 0.7 + (baselineAvg[emotion] as number) * 0.3;
          recommendedCorrection[emotion] = target;
        }
      });
    }
    
    return {
      driftDetected,
      driftMagnitude,
      driftDirection,
      correctionRequired,
      recommendedCorrection
    };
  }

  private calculateAverageState(states: EmotionalState[]): EmotionalState {
    if (states.length === 0) {
      return this.createNeutralState();
    }
    
    const average = this.createNeutralState();
    const emotions: (keyof EmotionalState)[] = ['joy', 'sadness', 'anger', 'fear', 'surprise', 'disgust', 'trust', 'anticipation'];
    
    emotions.forEach(emotion => {
      const sum = states.reduce((acc, state) => {
        return acc + (typeof state[emotion] === 'number' ? state[emotion] as number : 0);
      }, 0);
      (average as any)[emotion] = sum / states.length;
    });
    
    average.intensity = states.reduce((acc, state) => acc + state.intensity, 0) / states.length;
    average.stability = states.reduce((acc, state) => acc + state.stability, 0) / states.length;
    
    return average;
  }

  private calculateStateDistance(state1: EmotionalState, state2: EmotionalState): number {
    const emotions: (keyof EmotionalState)[] = ['joy', 'sadness', 'anger', 'fear', 'surprise', 'disgust', 'trust', 'anticipation'];
    
    let distance = 0;
    emotions.forEach(emotion => {
      if (typeof state1[emotion] === 'number' && typeof state2[emotion] === 'number') {
        distance += Math.pow((state1[emotion] as number) - (state2[emotion] as number), 2);
      }
    });
    
    distance += Math.pow(state1.intensity - state2.intensity, 2);
    distance += Math.pow(state1.stability - state2.stability, 2);
    
    return Math.sqrt(distance);
  }

  private normalizeIntensities(state: EmotionalState): EmotionalState {
    const normalized = { ...state };
    
    // Calculate total emotional intensity
    const emotions: (keyof EmotionalState)[] = ['joy', 'sadness', 'anger', 'fear', 'surprise', 'disgust', 'trust', 'anticipation'];
    const totalIntensity = emotions.reduce((sum, emotion) => {
      return sum + (typeof normalized[emotion] === 'number' ? normalized[emotion] as number : 0);
    }, 0);
    
    // Normalize if total intensity exceeds reasonable bounds
    if (totalIntensity > 2.0) {
      const normalizationFactor = 2.0 / totalIntensity;
      emotions.forEach(emotion => {
        if (typeof normalized[emotion] === 'number') {
          normalized[emotion] = (normalized[emotion] as number) * normalizationFactor;
        }
      });
    }
    
    return normalized;
  }

  private validateEmotionalState(state: EmotionalState): ValidationResult {
    const errors: any[] = [];
    const warnings: any[] = [];
    const suggestions: any[] = [];
    
    // Validate required fields
    if (!state) {
      errors.push({
        field: 'state',
        message: 'Emotional state is required',
        code: 'REQUIRED_FIELD_MISSING',
        severity: 'error'
      });
      return { valid: false, errors, warnings, suggestions };
    }
    
    if (!state.primary || typeof state.primary !== 'string') {
      errors.push({
        field: 'primary',
        message: 'Primary emotion is required and must be a valid string',
        code: 'REQUIRED_FIELD_MISSING',
        severity: 'error'
      });
    }
    
    if (typeof state.intensity !== 'number') {
      errors.push({
        field: 'intensity',
        message: 'Intensity is required and must be a number',
        code: 'REQUIRED_FIELD_MISSING',
        severity: 'error'
      });
    }
    
    // Validate emotion values are within bounds
    const emotions: (keyof EmotionalState)[] = ['joy', 'sadness', 'anger', 'fear', 'surprise', 'disgust', 'trust', 'anticipation'];
    
    emotions.forEach(emotion => {
      const value = state[emotion];
      if (typeof value === 'number') {
        if (value < 0 || value > 1) {
          errors.push({
            field: emotion,
            message: `${emotion} must be between 0 and 1`,
            code: 'INVALID_RANGE',
            severity: 'error'
          });
        }
      }
    });
    
    // Validate intensity and stability
    if (typeof state.intensity === 'number' && (state.intensity < 0 || state.intensity > 1)) {
      errors.push({
        field: 'intensity',
        message: 'Intensity must be between 0 and 1',
        code: 'INVALID_RANGE',
        severity: 'error'
      });
    }
    
    if (typeof state.stability === 'number' && (state.stability < 0 || state.stability > 1)) {
      errors.push({
        field: 'stability',
        message: 'Stability must be between 0 and 1',
        code: 'INVALID_RANGE',
        severity: 'error'
      });
    }
    
    // Validate valence, arousal, dominance if present
    if (typeof state.valence === 'number' && (state.valence < -1 || state.valence > 1)) {
      errors.push({
        field: 'valence',
        message: 'Valence must be between -1 and 1',
        code: 'INVALID_RANGE',
        severity: 'error'
      });
    }
    
    if (typeof state.arousal === 'number' && (state.arousal < 0 || state.arousal > 1)) {
      errors.push({
        field: 'arousal',
        message: 'Arousal must be between 0 and 1',
        code: 'INVALID_RANGE',
        severity: 'error'
      });
    }
    
    if (typeof state.dominance === 'number' && (state.dominance < 0 || state.dominance > 1)) {
      errors.push({
        field: 'dominance',
        message: 'Dominance must be between 0 and 1',
        code: 'INVALID_RANGE',
        severity: 'error'
      });
    }
    
    // Validate confidence if present
    if (typeof state.confidence === 'number' && (state.confidence < 0 || state.confidence > 1)) {
      errors.push({
        field: 'confidence',
        message: 'Confidence must be between 0 and 1',
        code: 'INVALID_RANGE',
        severity: 'error'
      });
    }
    
    // Check for emotional conflicts
    if (typeof state.joy === 'number' && typeof state.sadness === 'number' && 
        state.joy > 0.7 && state.sadness > 0.7) {
      warnings.push({
        field: 'emotional_conflict',
        message: 'High joy and sadness simultaneously may appear unnatural',
        code: 'BUSINESS_RULE_VIOLATION',
        severity: 'warning'
      });
    }
    
    // Validate secondary emotions format
    if (state.secondary !== undefined) {
      if (Array.isArray(state.secondary)) {
        state.secondary.forEach((emotion, index) => {
          if (typeof emotion !== 'string') {
            errors.push({
              field: `secondary[${index}]`,
              message: 'Secondary emotions must be valid emotion strings',
              code: 'INVALID_TYPE',
              severity: 'error'
            });
          }
        });
      } else if (typeof state.secondary !== 'string') {
        errors.push({
          field: 'secondary',
          message: 'Secondary emotion must be a string or array of strings',
          code: 'INVALID_TYPE',
          severity: 'error'
        });
      }
    }
    
    return {
      valid: errors.length === 0,
      errors,
      warnings,
      suggestions
    };
  }

  private recordProcessingTime(time: number): void {
    this.processingTimes.push(time);
    
    if (this.processingTimes.length > this.maxProcessingTimeHistory) {
      this.processingTimes.shift();
    }
  }
}