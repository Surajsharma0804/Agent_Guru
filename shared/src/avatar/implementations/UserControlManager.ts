/**
 * User Control Manager for Avatar Safety Boundaries
 * 
 * Provides comprehensive user control over avatar behavior including expressiveness,
 * gesture intensity, voice personality, and minimal mode with safety boundaries.
 */

import {
  UserPreferences,
  AccessibilityOptions,
  CulturalPreferences,
  EmotionalRange,
  GestureProfile
} from '../types/AvatarIdentity';

import {
  ExpressivenessLevel,
  GestureIntensity,
  VoicePersonality,
  AvatarApiResponse,
  AvatarErrorType,
  Platform
} from '../types/Common';

/**
 * User control settings for avatar behavior
 */
export interface UserControlSettings {
  // Expressiveness Controls (Low/Medium/High emotion settings)
  expressiveness: ExpressivenessLevel;
  emotionalResponsiveness: number; // 0.0 to 1.0
  emotionalStability: number; // 0.0 to 1.0
  
  // Gesture Intensity Controls (Subtle/Natural/Expressive options)
  gestureIntensity: GestureIntensity;
  gestureFrequency: number; // gestures per minute
  gestureVariety: number; // 0.0 to 1.0
  
  // Voice Personality Toggles (Formal/Friendly/Casual modes)
  voicePersonality: VoicePersonality;
  voiceTone: 'professional' | 'conversational' | 'casual';
  voiceSpeed: number; // 0.5 to 2.0 (relative speed)
  
  // Minimal Mode
  minimalMode: boolean;
  reducedAnimations: boolean;
  staticMode: boolean;
  
  // Safety Boundaries
  userOverrideEnabled: boolean;
  safetyLimitsEnabled: boolean;
  parentalControlsEnabled: boolean;
  
  // Accessibility
  accessibilityMode: boolean;
  reducedMotion: boolean;
  highContrast: boolean;
  
  // Cultural Sensitivity
  culturalAdaptation: boolean;
  gestureStyle: 'western' | 'eastern' | 'neutral';
  eyeContactLevel: number; // 0.0 to 1.0
  personalSpacePreference: number; // 0.0 to 1.0
}

/**
 * Control override result
 */
export interface ControlOverrideResult {
  applied: boolean;
  originalValue: unknown;
  newValue: unknown;
  reason: string;
  safetyBoundaryTriggered: boolean;
}

/**
 * Safety boundary violation
 */
export interface SafetyBoundaryViolation {
  type: 'expressiveness_limit' | 'gesture_limit' | 'voice_limit' | 'accessibility_requirement';
  severity: 'warning' | 'error' | 'critical';
  description: string;
  suggestedAction: string;
  autoCorrect: boolean;
}

/**
 * User Control Manager interface
 */
export interface UserControlManager {
  // Control Settings Management
  getUserControlSettings(identityId: string): Promise<AvatarApiResponse<UserControlSettings>>;
  updateUserControlSettings(identityId: string, settings: Partial<UserControlSettings>): Promise<AvatarApiResponse<void>>;
  resetToDefaults(identityId: string): Promise<AvatarApiResponse<UserControlSettings>>;
  
  // Expressiveness Controls
  setExpressiveness(identityId: string, level: ExpressivenessLevel): Promise<AvatarApiResponse<ControlOverrideResult>>;
  setEmotionalResponsiveness(identityId: string, level: number): Promise<AvatarApiResponse<ControlOverrideResult>>;
  setEmotionalStability(identityId: string, level: number): Promise<AvatarApiResponse<ControlOverrideResult>>;
  
  // Gesture Controls
  setGestureIntensity(identityId: string, intensity: GestureIntensity): Promise<AvatarApiResponse<ControlOverrideResult>>;
  setGestureFrequency(identityId: string, frequency: number): Promise<AvatarApiResponse<ControlOverrideResult>>;
  setGestureVariety(identityId: string, variety: number): Promise<AvatarApiResponse<ControlOverrideResult>>;
  
  // Voice Controls
  setVoicePersonality(identityId: string, personality: VoicePersonality): Promise<AvatarApiResponse<ControlOverrideResult>>;
  setVoiceTone(identityId: string, tone: 'professional' | 'conversational' | 'casual'): Promise<AvatarApiResponse<ControlOverrideResult>>;
  setVoiceSpeed(identityId: string, speed: number): Promise<AvatarApiResponse<ControlOverrideResult>>;
  
  // Mode Controls
  setMinimalMode(identityId: string, enabled: boolean): Promise<AvatarApiResponse<ControlOverrideResult>>;
  setReducedAnimations(identityId: string, enabled: boolean): Promise<AvatarApiResponse<ControlOverrideResult>>;
  setStaticMode(identityId: string, enabled: boolean): Promise<AvatarApiResponse<ControlOverrideResult>>;
  
  // Safety Boundaries
  enableUserOverride(identityId: string, enabled: boolean): Promise<AvatarApiResponse<void>>;
  enableSafetyLimits(identityId: string, enabled: boolean): Promise<AvatarApiResponse<void>>;
  enableParentalControls(identityId: string, enabled: boolean): Promise<AvatarApiResponse<void>>;
  
  // Accessibility Controls
  setAccessibilityMode(identityId: string, enabled: boolean): Promise<AvatarApiResponse<ControlOverrideResult>>;
  setReducedMotion(identityId: string, enabled: boolean): Promise<AvatarApiResponse<ControlOverrideResult>>;
  setHighContrast(identityId: string, enabled: boolean): Promise<AvatarApiResponse<ControlOverrideResult>>;
  
  // Cultural Controls
  setCulturalAdaptation(identityId: string, enabled: boolean): Promise<AvatarApiResponse<ControlOverrideResult>>;
  setGestureStyle(identityId: string, style: 'western' | 'eastern' | 'neutral'): Promise<AvatarApiResponse<ControlOverrideResult>>;
  setEyeContactLevel(identityId: string, level: number): Promise<AvatarApiResponse<ControlOverrideResult>>;
  setPersonalSpacePreference(identityId: string, preference: number): Promise<AvatarApiResponse<ControlOverrideResult>>;
  
  // Validation and Safety
  validateControlSettings(settings: UserControlSettings): Promise<AvatarApiResponse<SafetyBoundaryViolation[]>>;
  applySafetyBoundaries(settings: UserControlSettings): Promise<AvatarApiResponse<UserControlSettings>>;
  checkCompatibility(settings: UserControlSettings, platform: Platform): Promise<AvatarApiResponse<boolean>>;
  
  // Presets
  getControlPresets(): Promise<AvatarApiResponse<UserControlPreset[]>>;
  applyControlPreset(identityId: string, presetId: string): Promise<AvatarApiResponse<ControlOverrideResult[]>>;
  
  // Event Handling
  onControlChanged(callback: ControlChangeCallback): void;
  onSafetyBoundaryTriggered(callback: SafetyBoundaryCallback): void;
  
  // Cleanup
  cleanup(): Promise<AvatarApiResponse<void>>;
}

/**
 * User control preset for quick configuration
 */
export interface UserControlPreset {
  id: string;
  name: string;
  description: string;
  settings: UserControlSettings;
  category: 'accessibility' | 'performance' | 'professional' | 'personal' | 'minimal';
  recommended: boolean;
}

/**
 * Control change callback
 */
export type ControlChangeCallback = (
  identityId: string,
  controlType: string,
  oldValue: unknown,
  newValue: unknown,
  overrideResult: ControlOverrideResult
) => void;

/**
 * Safety boundary callback
 */
export type SafetyBoundaryCallback = (
  identityId: string,
  violation: SafetyBoundaryViolation,
  correctedSettings: UserControlSettings
) => void;

/**
 * Production implementation of User Control Manager
 */
export class UserControlManagerImpl implements UserControlManager {
  private readonly controlSettings: Map<string, UserControlSettings> = new Map();
  private readonly controlChangeCallbacks: ControlChangeCallback[] = [];
  private readonly safetyBoundaryCallbacks: SafetyBoundaryCallback[] = [];

  // Default safety boundaries
  private readonly SAFETY_LIMITS = {
    maxExpressiveness: 'high' as ExpressivenessLevel,
    maxGestureIntensity: 'expressive' as GestureIntensity,
    maxEmotionalResponsiveness: 1.0,
    minEmotionalStability: 0.1,
    maxGestureFrequency: 10, // gestures per minute
    maxVoiceSpeed: 2.0,
    minVoiceSpeed: 0.5
  };

  async getUserControlSettings(identityId: string): Promise<AvatarApiResponse<UserControlSettings>> {
    const startTime = Date.now();
    
    try {
      let settings = this.controlSettings.get(identityId);
      
      if (!settings) {
        // Create default settings
        settings = this.createDefaultSettings();
        this.controlSettings.set(identityId, settings);
      }

      return {
        success: true,
        data: { ...settings }, // Return copy to prevent mutation
        executionTime: Date.now() - startTime,
        timestamp: Date.now()
      };
    } catch (error) {
      return {
        success: false,
        error: {
          type: AvatarErrorType.AUTHENTICATION_FAILURE,
          message: `Failed to get user control settings: ${error instanceof Error ? error.message : 'Unknown error'}`,
          timestamp: Date.now(),
          platform: this.getCurrentPlatform(),
          recoverable: true
        },
        executionTime: Date.now() - startTime,
        timestamp: Date.now()
      };
    }
  }
  async updateUserControlSettings(identityId: string, settings: Partial<UserControlSettings>): Promise<AvatarApiResponse<void>> {
    const startTime = Date.now();
    
    try {
      const currentSettings = await this.getUserControlSettings(identityId);
      if (!currentSettings.success || !currentSettings.data) {
        return {
          success: false,
          error: {
            type: AvatarErrorType.AUTHENTICATION_FAILURE,
            message: 'Failed to get current settings',
            timestamp: Date.now(),
            platform: this.getCurrentPlatform(),
            recoverable: true
          },
          executionTime: Date.now() - startTime,
          timestamp: Date.now()
        };
      }

      // Merge settings
      const updatedSettings: UserControlSettings = {
        ...currentSettings.data,
        ...settings
      };

      // Apply safety boundaries
      const safetyResult = await this.applySafetyBoundaries(updatedSettings);
      if (!safetyResult.success || !safetyResult.data) {
        return {
          success: false,
          error: safetyResult.error,
          executionTime: Date.now() - startTime,
          timestamp: Date.now()
        };
      }

      // Store updated settings
      this.controlSettings.set(identityId, safetyResult.data);

      return {
        success: true,
        executionTime: Date.now() - startTime,
        timestamp: Date.now()
      };
    } catch (error) {
      return {
        success: false,
        error: {
          type: AvatarErrorType.AUTHENTICATION_FAILURE,
          message: `Failed to update user control settings: ${error instanceof Error ? error.message : 'Unknown error'}`,
          timestamp: Date.now(),
          platform: this.getCurrentPlatform(),
          recoverable: true
        },
        executionTime: Date.now() - startTime,
        timestamp: Date.now()
      };
    }
  }

  async resetToDefaults(identityId: string): Promise<AvatarApiResponse<UserControlSettings>> {
    const startTime = Date.now();
    
    try {
      const defaultSettings = this.createDefaultSettings();
      this.controlSettings.set(identityId, defaultSettings);

      return {
        success: true,
        data: { ...defaultSettings },
        executionTime: Date.now() - startTime,
        timestamp: Date.now()
      };
    } catch (error) {
      return {
        success: false,
        error: {
          type: AvatarErrorType.AUTHENTICATION_FAILURE,
          message: `Failed to reset to defaults: ${error instanceof Error ? error.message : 'Unknown error'}`,
          timestamp: Date.now(),
          platform: this.getCurrentPlatform(),
          recoverable: true
        },
        executionTime: Date.now() - startTime,
        timestamp: Date.now()
      };
    }
  }

  // Expressiveness Controls
  async setExpressiveness(identityId: string, level: ExpressivenessLevel): Promise<AvatarApiResponse<ControlOverrideResult>> {
    return this.updateControlWithOverride(identityId, 'expressiveness', level, (settings, value) => {
      const originalValue = settings.expressiveness;
      
      // Apply safety boundaries
      if (settings.safetyLimitsEnabled && !this.isExpressivenessWithinLimits(value)) {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'Expressiveness level exceeds safety limits',
          safetyBoundaryTriggered: true
        };
      }

      // Apply minimal mode constraints
      if (settings.minimalMode && value !== 'low') {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'Minimal mode requires low expressiveness',
          safetyBoundaryTriggered: true
        };
      }

      settings.expressiveness = value;
      return {
        applied: true,
        originalValue,
        newValue: value,
        reason: 'Expressiveness updated successfully',
        safetyBoundaryTriggered: false
      };
    });
  }

  async setEmotionalResponsiveness(identityId: string, level: number): Promise<AvatarApiResponse<ControlOverrideResult>> {
    return this.updateControlWithOverride(identityId, 'emotionalResponsiveness', level, (settings, value) => {
      const originalValue = settings.emotionalResponsiveness;
      
      // Validate range
      if (value < 0.0 || value > 1.0) {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'Emotional responsiveness must be between 0.0 and 1.0',
          safetyBoundaryTriggered: true
        };
      }

      // Apply safety boundaries
      if (settings.safetyLimitsEnabled && value > this.SAFETY_LIMITS.maxEmotionalResponsiveness) {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'Emotional responsiveness exceeds safety limits',
          safetyBoundaryTriggered: true
        };
      }

      settings.emotionalResponsiveness = value;
      return {
        applied: true,
        originalValue,
        newValue: value,
        reason: 'Emotional responsiveness updated successfully',
        safetyBoundaryTriggered: false
      };
    });
  }

  async setEmotionalStability(identityId: string, level: number): Promise<AvatarApiResponse<ControlOverrideResult>> {
    return this.updateControlWithOverride(identityId, 'emotionalStability', level, (settings, value) => {
      const originalValue = settings.emotionalStability;
      
      // Validate range
      if (value < 0.0 || value > 1.0) {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'Emotional stability must be between 0.0 and 1.0',
          safetyBoundaryTriggered: true
        };
      }

      // Apply safety boundaries
      if (settings.safetyLimitsEnabled && value < this.SAFETY_LIMITS.minEmotionalStability) {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'Emotional stability below safety limits',
          safetyBoundaryTriggered: true
        };
      }

      settings.emotionalStability = value;
      return {
        applied: true,
        originalValue,
        newValue: value,
        reason: 'Emotional stability updated successfully',
        safetyBoundaryTriggered: false
      };
    });
  }

  // Gesture Controls
  async setGestureIntensity(identityId: string, intensity: GestureIntensity): Promise<AvatarApiResponse<ControlOverrideResult>> {
    return this.updateControlWithOverride(identityId, 'gestureIntensity', intensity, (settings, value) => {
      const originalValue = settings.gestureIntensity;
      
      // Apply safety boundaries
      if (settings.safetyLimitsEnabled && !this.isGestureIntensityWithinLimits(value)) {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'Gesture intensity exceeds safety limits',
          safetyBoundaryTriggered: true
        };
      }

      // Apply minimal mode constraints
      if (settings.minimalMode && value !== 'subtle') {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'Minimal mode requires subtle gesture intensity',
          safetyBoundaryTriggered: true
        };
      }

      // Apply accessibility constraints
      if (settings.reducedMotion && value === 'expressive') {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'Reduced motion mode incompatible with expressive gestures',
          safetyBoundaryTriggered: true
        };
      }

      settings.gestureIntensity = value;
      return {
        applied: true,
        originalValue,
        newValue: value,
        reason: 'Gesture intensity updated successfully',
        safetyBoundaryTriggered: false
      };
    });
  }

  async setGestureFrequency(identityId: string, frequency: number): Promise<AvatarApiResponse<ControlOverrideResult>> {
    return this.updateControlWithOverride(identityId, 'gestureFrequency', frequency, (settings, value) => {
      const originalValue = settings.gestureFrequency;
      
      // Validate range
      if (value < 0 || value > this.SAFETY_LIMITS.maxGestureFrequency) {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: `Gesture frequency must be between 0 and ${this.SAFETY_LIMITS.maxGestureFrequency}`,
          safetyBoundaryTriggered: true
        };
      }

      // Apply minimal mode constraints
      if (settings.minimalMode && value > 2) {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'Minimal mode limits gesture frequency to 2 per minute',
          safetyBoundaryTriggered: true
        };
      }

      settings.gestureFrequency = value;
      return {
        applied: true,
        originalValue,
        newValue: value,
        reason: 'Gesture frequency updated successfully',
        safetyBoundaryTriggered: false
      };
    });
  }

  async setGestureVariety(identityId: string, variety: number): Promise<AvatarApiResponse<ControlOverrideResult>> {
    return this.updateControlWithOverride(identityId, 'gestureVariety', variety, (settings, value) => {
      const originalValue = settings.gestureVariety;
      
      // Validate range
      if (value < 0.0 || value > 1.0) {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'Gesture variety must be between 0.0 and 1.0',
          safetyBoundaryTriggered: true
        };
      }

      settings.gestureVariety = value;
      return {
        applied: true,
        originalValue,
        newValue: value,
        reason: 'Gesture variety updated successfully',
        safetyBoundaryTriggered: false
      };
    });
  }
  // Voice Controls
  async setVoicePersonality(identityId: string, personality: VoicePersonality): Promise<AvatarApiResponse<ControlOverrideResult>> {
    return this.updateControlWithOverride(identityId, 'voicePersonality', personality, (settings, value) => {
      const originalValue = settings.voicePersonality;
      
      // Check if user overrides are enabled
      if (!settings.userOverrideEnabled) {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'User overrides are disabled',
          safetyBoundaryTriggered: false
        };
      }
      
      // Apply parental controls
      if (settings.parentalControlsEnabled && value === 'casual') {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'Parental controls restrict casual voice personality',
          safetyBoundaryTriggered: true
        };
      }

      settings.voicePersonality = value;
      return {
        applied: true,
        originalValue,
        newValue: value,
        reason: 'Voice personality updated successfully',
        safetyBoundaryTriggered: false
      };
    });
  }

  async setVoiceTone(identityId: string, tone: 'professional' | 'conversational' | 'casual'): Promise<AvatarApiResponse<ControlOverrideResult>> {
    return this.updateControlWithOverride(identityId, 'voiceTone', tone, (settings, value) => {
      const originalValue = settings.voiceTone;
      
      // Apply parental controls
      if (settings.parentalControlsEnabled && value === 'casual') {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'Parental controls restrict casual voice tone',
          safetyBoundaryTriggered: true
        };
      }

      settings.voiceTone = value;
      return {
        applied: true,
        originalValue,
        newValue: value,
        reason: 'Voice tone updated successfully',
        safetyBoundaryTriggered: false
      };
    });
  }

  async setVoiceSpeed(identityId: string, speed: number): Promise<AvatarApiResponse<ControlOverrideResult>> {
    return this.updateControlWithOverride(identityId, 'voiceSpeed', speed, (settings, value) => {
      const originalValue = settings.voiceSpeed;
      
      // Validate range
      if (value < this.SAFETY_LIMITS.minVoiceSpeed || value > this.SAFETY_LIMITS.maxVoiceSpeed) {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: `Voice speed must be between ${this.SAFETY_LIMITS.minVoiceSpeed} and ${this.SAFETY_LIMITS.maxVoiceSpeed}`,
          safetyBoundaryTriggered: true
        };
      }

      settings.voiceSpeed = value;
      return {
        applied: true,
        originalValue,
        newValue: value,
        reason: 'Voice speed updated successfully',
        safetyBoundaryTriggered: false
      };
    });
  }

  // Mode Controls
  async setMinimalMode(identityId: string, enabled: boolean): Promise<AvatarApiResponse<ControlOverrideResult>> {
    return this.updateControlWithOverride(identityId, 'minimalMode', enabled, (settings, value) => {
      const originalValue = settings.minimalMode;
      
      settings.minimalMode = value;
      
      // If enabling minimal mode, adjust other settings
      if (value) {
        settings.expressiveness = 'low';
        settings.gestureIntensity = 'subtle';
        settings.gestureFrequency = Math.min(settings.gestureFrequency, 2);
        settings.reducedAnimations = true;
      }

      return {
        applied: true,
        originalValue,
        newValue: value,
        reason: value ? 'Minimal mode enabled with adjusted settings' : 'Minimal mode disabled',
        safetyBoundaryTriggered: false
      };
    });
  }

  async setReducedAnimations(identityId: string, enabled: boolean): Promise<AvatarApiResponse<ControlOverrideResult>> {
    return this.updateControlWithOverride(identityId, 'reducedAnimations', enabled, (settings, value) => {
      const originalValue = settings.reducedAnimations;
      
      settings.reducedAnimations = value;
      
      // If enabling reduced animations, adjust gesture settings
      if (value && settings.gestureIntensity === 'expressive') {
        settings.gestureIntensity = 'natural';
      }

      return {
        applied: true,
        originalValue,
        newValue: value,
        reason: 'Reduced animations setting updated',
        safetyBoundaryTriggered: false
      };
    });
  }

  async setStaticMode(identityId: string, enabled: boolean): Promise<AvatarApiResponse<ControlOverrideResult>> {
    return this.updateControlWithOverride(identityId, 'staticMode', enabled, (settings, value) => {
      const originalValue = settings.staticMode;
      
      settings.staticMode = value;
      
      // If enabling static mode, disable all animations
      if (value) {
        settings.minimalMode = true;
        settings.reducedAnimations = true;
        settings.expressiveness = 'low';
        settings.gestureIntensity = 'subtle';
        settings.gestureFrequency = 0;
      }

      return {
        applied: true,
        originalValue,
        newValue: value,
        reason: value ? 'Static mode enabled - all animations disabled' : 'Static mode disabled',
        safetyBoundaryTriggered: false
      };
    });
  }

  // Safety Boundaries
  async enableUserOverride(identityId: string, enabled: boolean): Promise<AvatarApiResponse<void>> {
    const startTime = Date.now();
    
    try {
      const settings = await this.getUserControlSettings(identityId);
      if (!settings.success || !settings.data) {
        return {
          success: false,
          error: settings.error,
          executionTime: Date.now() - startTime,
          timestamp: Date.now()
        };
      }

      settings.data.userOverrideEnabled = enabled;
      this.controlSettings.set(identityId, settings.data);

      return {
        success: true,
        executionTime: Date.now() - startTime,
        timestamp: Date.now()
      };
    } catch (error) {
      return {
        success: false,
        error: {
          type: AvatarErrorType.AUTHENTICATION_FAILURE,
          message: `Failed to enable user override: ${error instanceof Error ? error.message : 'Unknown error'}`,
          timestamp: Date.now(),
          platform: this.getCurrentPlatform(),
          recoverable: true
        },
        executionTime: Date.now() - startTime,
        timestamp: Date.now()
      };
    }
  }

  async enableSafetyLimits(identityId: string, enabled: boolean): Promise<AvatarApiResponse<void>> {
    const startTime = Date.now();
    
    try {
      const settings = await this.getUserControlSettings(identityId);
      if (!settings.success || !settings.data) {
        return {
          success: false,
          error: settings.error,
          executionTime: Date.now() - startTime,
          timestamp: Date.now()
        };
      }

      settings.data.safetyLimitsEnabled = enabled;
      this.controlSettings.set(identityId, settings.data);

      return {
        success: true,
        executionTime: Date.now() - startTime,
        timestamp: Date.now()
      };
    } catch (error) {
      return {
        success: false,
        error: {
          type: AvatarErrorType.AUTHENTICATION_FAILURE,
          message: `Failed to enable safety limits: ${error instanceof Error ? error.message : 'Unknown error'}`,
          timestamp: Date.now(),
          platform: this.getCurrentPlatform(),
          recoverable: true
        },
        executionTime: Date.now() - startTime,
        timestamp: Date.now()
      };
    }
  }

  async enableParentalControls(identityId: string, enabled: boolean): Promise<AvatarApiResponse<void>> {
    const startTime = Date.now();
    
    try {
      const settings = await this.getUserControlSettings(identityId);
      if (!settings.success || !settings.data) {
        return {
          success: false,
          error: settings.error,
          executionTime: Date.now() - startTime,
          timestamp: Date.now()
        };
      }

      settings.data.parentalControlsEnabled = enabled;
      
      // If enabling parental controls, apply restrictions
      if (enabled) {
        settings.data.safetyLimitsEnabled = true;
        if (settings.data.voicePersonality === 'casual') {
          settings.data.voicePersonality = 'friendly';
        }
        if (settings.data.voiceTone === 'casual') {
          settings.data.voiceTone = 'conversational';
        }
      }
      
      this.controlSettings.set(identityId, settings.data);

      return {
        success: true,
        executionTime: Date.now() - startTime,
        timestamp: Date.now()
      };
    } catch (error) {
      return {
        success: false,
        error: {
          type: AvatarErrorType.AUTHENTICATION_FAILURE,
          message: `Failed to enable parental controls: ${error instanceof Error ? error.message : 'Unknown error'}`,
          timestamp: Date.now(),
          platform: this.getCurrentPlatform(),
          recoverable: true
        },
        executionTime: Date.now() - startTime,
        timestamp: Date.now()
      };
    }
  }
  // Accessibility Controls
  async setAccessibilityMode(identityId: string, enabled: boolean): Promise<AvatarApiResponse<ControlOverrideResult>> {
    return this.updateControlWithOverride(identityId, 'accessibilityMode', enabled, (settings, value) => {
      const originalValue = settings.accessibilityMode;
      
      settings.accessibilityMode = value;
      
      // If enabling accessibility mode, apply accessibility-friendly settings
      if (value) {
        settings.reducedMotion = true;
        settings.highContrast = true;
        if (settings.gestureIntensity === 'expressive') {
          settings.gestureIntensity = 'natural';
        }
      }

      return {
        applied: true,
        originalValue,
        newValue: value,
        reason: value ? 'Accessibility mode enabled with optimized settings' : 'Accessibility mode disabled',
        safetyBoundaryTriggered: false
      };
    });
  }

  async setReducedMotion(identityId: string, enabled: boolean): Promise<AvatarApiResponse<ControlOverrideResult>> {
    return this.updateControlWithOverride(identityId, 'reducedMotion', enabled, (settings, value) => {
      const originalValue = settings.reducedMotion;
      
      settings.reducedMotion = value;
      
      // If enabling reduced motion, adjust gesture settings
      if (value) {
        if (settings.gestureIntensity === 'expressive') {
          settings.gestureIntensity = 'natural';
        }
        settings.gestureFrequency = Math.min(settings.gestureFrequency, 3);
      }

      return {
        applied: true,
        originalValue,
        newValue: value,
        reason: 'Reduced motion setting updated',
        safetyBoundaryTriggered: false
      };
    });
  }

  async setHighContrast(identityId: string, enabled: boolean): Promise<AvatarApiResponse<ControlOverrideResult>> {
    return this.updateControlWithOverride(identityId, 'highContrast', enabled, (settings, value) => {
      const originalValue = settings.highContrast;
      
      settings.highContrast = value;

      return {
        applied: true,
        originalValue,
        newValue: value,
        reason: 'High contrast setting updated',
        safetyBoundaryTriggered: false
      };
    });
  }

  // Cultural Controls
  async setCulturalAdaptation(identityId: string, enabled: boolean): Promise<AvatarApiResponse<ControlOverrideResult>> {
    return this.updateControlWithOverride(identityId, 'culturalAdaptation', enabled, (settings, value) => {
      const originalValue = settings.culturalAdaptation;
      
      settings.culturalAdaptation = value;

      return {
        applied: true,
        originalValue,
        newValue: value,
        reason: 'Cultural adaptation setting updated',
        safetyBoundaryTriggered: false
      };
    });
  }

  async setGestureStyle(identityId: string, style: 'western' | 'eastern' | 'neutral'): Promise<AvatarApiResponse<ControlOverrideResult>> {
    return this.updateControlWithOverride(identityId, 'gestureStyle', style, (settings, value) => {
      const originalValue = settings.gestureStyle;
      
      settings.gestureStyle = value;

      return {
        applied: true,
        originalValue,
        newValue: value,
        reason: 'Gesture style updated',
        safetyBoundaryTriggered: false
      };
    });
  }

  async setEyeContactLevel(identityId: string, level: number): Promise<AvatarApiResponse<ControlOverrideResult>> {
    return this.updateControlWithOverride(identityId, 'eyeContactLevel', level, (settings, value) => {
      const originalValue = settings.eyeContactLevel;
      
      // Validate range
      if (value < 0.0 || value > 1.0) {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'Eye contact level must be between 0.0 and 1.0',
          safetyBoundaryTriggered: true
        };
      }

      settings.eyeContactLevel = value;

      return {
        applied: true,
        originalValue,
        newValue: value,
        reason: 'Eye contact level updated',
        safetyBoundaryTriggered: false
      };
    });
  }

  async setPersonalSpacePreference(identityId: string, preference: number): Promise<AvatarApiResponse<ControlOverrideResult>> {
    return this.updateControlWithOverride(identityId, 'personalSpacePreference', preference, (settings, value) => {
      const originalValue = settings.personalSpacePreference;
      
      // Validate range
      if (value < 0.0 || value > 1.0) {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'Personal space preference must be between 0.0 and 1.0',
          safetyBoundaryTriggered: true
        };
      }

      settings.personalSpacePreference = value;

      return {
        applied: true,
        originalValue,
        newValue: value,
        reason: 'Personal space preference updated',
        safetyBoundaryTriggered: false
      };
    });
  }

  // Validation and Safety
  async validateControlSettings(settings: UserControlSettings): Promise<AvatarApiResponse<SafetyBoundaryViolation[]>> {
    const startTime = Date.now();
    
    try {
      const violations: SafetyBoundaryViolation[] = [];

      // Check expressiveness conflicts
      if (settings.minimalMode && settings.expressiveness !== 'low') {
        violations.push({
          type: 'expressiveness_limit',
          severity: 'error',
          description: 'Minimal mode requires low expressiveness',
          suggestedAction: 'Set expressiveness to low or disable minimal mode',
          autoCorrect: true
        });
      }

      // Check gesture conflicts
      if (settings.minimalMode && settings.gestureIntensity !== 'subtle') {
        violations.push({
          type: 'gesture_limit',
          severity: 'error',
          description: 'Minimal mode requires subtle gesture intensity',
          suggestedAction: 'Set gesture intensity to subtle or disable minimal mode',
          autoCorrect: true
        });
      }

      // Check accessibility conflicts
      if (settings.reducedMotion && settings.gestureIntensity === 'expressive') {
        violations.push({
          type: 'accessibility_requirement',
          severity: 'warning',
          description: 'Reduced motion mode conflicts with expressive gestures',
          suggestedAction: 'Use natural or subtle gesture intensity with reduced motion',
          autoCorrect: true
        });
      }

      // Check voice speed limits
      if (settings.voiceSpeed < this.SAFETY_LIMITS.minVoiceSpeed || settings.voiceSpeed > this.SAFETY_LIMITS.maxVoiceSpeed) {
        violations.push({
          type: 'voice_limit',
          severity: 'error',
          description: `Voice speed must be between ${this.SAFETY_LIMITS.minVoiceSpeed} and ${this.SAFETY_LIMITS.maxVoiceSpeed}`,
          suggestedAction: 'Adjust voice speed to within acceptable range',
          autoCorrect: true
        });
      }

      return {
        success: true,
        data: violations,
        executionTime: Date.now() - startTime,
        timestamp: Date.now()
      };
    } catch (error) {
      return {
        success: false,
        error: {
          type: AvatarErrorType.AUTHENTICATION_FAILURE,
          message: `Failed to validate control settings: ${error instanceof Error ? error.message : 'Unknown error'}`,
          timestamp: Date.now(),
          platform: this.getCurrentPlatform(),
          recoverable: true
        },
        executionTime: Date.now() - startTime,
        timestamp: Date.now()
      };
    }
  }

  async applySafetyBoundaries(settings: UserControlSettings): Promise<AvatarApiResponse<UserControlSettings>> {
    const startTime = Date.now();
    
    try {
      const correctedSettings = { ...settings };
      const violations: SafetyBoundaryViolation[] = [];

      // Apply minimal mode constraints
      if (correctedSettings.minimalMode) {
        if (correctedSettings.expressiveness !== 'low') {
          correctedSettings.expressiveness = 'low';
          violations.push({
            type: 'expressiveness_limit',
            severity: 'warning',
            description: 'Expressiveness auto-corrected for minimal mode',
            suggestedAction: 'Expressiveness set to low',
            autoCorrect: true
          });
        }
        
        if (correctedSettings.gestureIntensity !== 'subtle') {
          correctedSettings.gestureIntensity = 'subtle';
          violations.push({
            type: 'gesture_limit',
            severity: 'warning',
            description: 'Gesture intensity auto-corrected for minimal mode',
            suggestedAction: 'Gesture intensity set to subtle',
            autoCorrect: true
          });
        }
      }

      // Apply accessibility constraints
      if (correctedSettings.reducedMotion && correctedSettings.gestureIntensity === 'expressive') {
        correctedSettings.gestureIntensity = 'natural';
        violations.push({
          type: 'accessibility_requirement',
          severity: 'warning',
          description: 'Gesture intensity auto-corrected for reduced motion',
          suggestedAction: 'Gesture intensity set to natural',
          autoCorrect: true
        });
      }

      // Apply safety limits
      if (correctedSettings.safetyLimitsEnabled) {
        // Clamp voice speed
        if (correctedSettings.voiceSpeed < this.SAFETY_LIMITS.minVoiceSpeed) {
          correctedSettings.voiceSpeed = this.SAFETY_LIMITS.minVoiceSpeed;
        } else if (correctedSettings.voiceSpeed > this.SAFETY_LIMITS.maxVoiceSpeed) {
          correctedSettings.voiceSpeed = this.SAFETY_LIMITS.maxVoiceSpeed;
        }

        // Clamp gesture frequency
        if (correctedSettings.gestureFrequency > this.SAFETY_LIMITS.maxGestureFrequency) {
          correctedSettings.gestureFrequency = this.SAFETY_LIMITS.maxGestureFrequency;
        }

        // Clamp emotional responsiveness
        if (correctedSettings.emotionalResponsiveness > this.SAFETY_LIMITS.maxEmotionalResponsiveness) {
          correctedSettings.emotionalResponsiveness = this.SAFETY_LIMITS.maxEmotionalResponsiveness;
        }

        // Clamp emotional stability
        if (correctedSettings.emotionalStability < this.SAFETY_LIMITS.minEmotionalStability) {
          correctedSettings.emotionalStability = this.SAFETY_LIMITS.minEmotionalStability;
        }
      }

      // Notify about violations
      for (const violation of violations) {
        this.notifySafetyBoundaryTriggered('', violation, correctedSettings);
      }

      return {
        success: true,
        data: correctedSettings,
        executionTime: Date.now() - startTime,
        timestamp: Date.now()
      };
    } catch (error) {
      return {
        success: false,
        error: {
          type: AvatarErrorType.AUTHENTICATION_FAILURE,
          message: `Failed to apply safety boundaries: ${error instanceof Error ? error.message : 'Unknown error'}`,
          timestamp: Date.now(),
          platform: this.getCurrentPlatform(),
          recoverable: true
        },
        executionTime: Date.now() - startTime,
        timestamp: Date.now()
      };
    }
  }
  async checkCompatibility(settings: UserControlSettings, platform: Platform): Promise<AvatarApiResponse<boolean>> {
    const startTime = Date.now();
    
    try {
      let compatible = true;

      // Check platform-specific limitations
      switch (platform) {
        case 'android':
        case 'ios':
          // Mobile platforms have limited resources
          if (settings.expressiveness === 'high' && settings.gestureIntensity === 'expressive') {
            compatible = false;
          }
          break;
          
        case 'web':
          // Web platform has limited 3D capabilities
          if (settings.gestureIntensity === 'expressive' && !settings.reducedAnimations) {
            compatible = false;
          }
          break;
      }

      return {
        success: true,
        data: compatible,
        executionTime: Date.now() - startTime,
        timestamp: Date.now()
      };
    } catch (error) {
      return {
        success: false,
        error: {
          type: AvatarErrorType.AUTHENTICATION_FAILURE,
          message: `Failed to check compatibility: ${error instanceof Error ? error.message : 'Unknown error'}`,
          timestamp: Date.now(),
          platform: this.getCurrentPlatform(),
          recoverable: true
        },
        executionTime: Date.now() - startTime,
        timestamp: Date.now()
      };
    }
  }

  // Presets
  async getControlPresets(): Promise<AvatarApiResponse<UserControlPreset[]>> {
    const startTime = Date.now();
    
    try {
      const presets: UserControlPreset[] = [
        {
          id: 'professional',
          name: 'Professional Mode',
          description: 'Formal, focused settings for business environments',
          category: 'professional',
          recommended: true,
          settings: {
            expressiveness: 'low',
            emotionalResponsiveness: 0.4,
            emotionalStability: 0.9,
            gestureIntensity: 'subtle',
            gestureFrequency: 2,
            gestureVariety: 0.5,
            voicePersonality: 'formal',
            voiceTone: 'professional',
            voiceSpeed: 1.0,
            minimalMode: false,
            reducedAnimations: false,
            staticMode: false,
            userOverrideEnabled: true,
            safetyLimitsEnabled: true,
            parentalControlsEnabled: false,
            accessibilityMode: false,
            reducedMotion: false,
            highContrast: false,
            culturalAdaptation: true,
            gestureStyle: 'neutral',
            eyeContactLevel: 0.8,
            personalSpacePreference: 0.7
          }
        },
        {
          id: 'friendly',
          name: 'Friendly Companion',
          description: 'Warm, expressive settings for personal interactions',
          category: 'personal',
          recommended: true,
          settings: {
            expressiveness: 'high',
            emotionalResponsiveness: 0.8,
            emotionalStability: 0.6,
            gestureIntensity: 'expressive',
            gestureFrequency: 6,
            gestureVariety: 0.9,
            voicePersonality: 'friendly',
            voiceTone: 'conversational',
            voiceSpeed: 1.1,
            minimalMode: false,
            reducedAnimations: false,
            staticMode: false,
            userOverrideEnabled: true,
            safetyLimitsEnabled: true,
            parentalControlsEnabled: false,
            accessibilityMode: false,
            reducedMotion: false,
            highContrast: false,
            culturalAdaptation: true,
            gestureStyle: 'western',
            eyeContactLevel: 0.7,
            personalSpacePreference: 0.5
          }
        },
        {
          id: 'minimal',
          name: 'Minimal Mode',
          description: 'Reduced animations and expressions for distraction-free work',
          category: 'minimal',
          recommended: false,
          settings: {
            expressiveness: 'low',
            emotionalResponsiveness: 0.2,
            emotionalStability: 0.9,
            gestureIntensity: 'subtle',
            gestureFrequency: 1,
            gestureVariety: 0.3,
            voicePersonality: 'formal',
            voiceTone: 'professional',
            voiceSpeed: 1.0,
            minimalMode: true,
            reducedAnimations: true,
            staticMode: false,
            userOverrideEnabled: true,
            safetyLimitsEnabled: true,
            parentalControlsEnabled: false,
            accessibilityMode: false,
            reducedMotion: true,
            highContrast: false,
            culturalAdaptation: false,
            gestureStyle: 'neutral',
            eyeContactLevel: 0.5,
            personalSpacePreference: 0.8
          }
        },
        {
          id: 'accessibility',
          name: 'Accessibility Optimized',
          description: 'Optimized for users with accessibility needs',
          category: 'accessibility',
          recommended: false,
          settings: {
            expressiveness: 'medium',
            emotionalResponsiveness: 0.5,
            emotionalStability: 0.8,
            gestureIntensity: 'natural',
            gestureFrequency: 3,
            gestureVariety: 0.6,
            voicePersonality: 'friendly',
            voiceTone: 'conversational',
            voiceSpeed: 0.9,
            minimalMode: false,
            reducedAnimations: true,
            staticMode: false,
            userOverrideEnabled: true,
            safetyLimitsEnabled: true,
            parentalControlsEnabled: false,
            accessibilityMode: true,
            reducedMotion: true,
            highContrast: true,
            culturalAdaptation: true,
            gestureStyle: 'neutral',
            eyeContactLevel: 0.6,
            personalSpacePreference: 0.7
          }
        },
        {
          id: 'performance',
          name: 'Performance Optimized',
          description: 'Optimized for lower-end devices and better battery life',
          category: 'performance',
          recommended: false,
          settings: {
            expressiveness: 'medium',
            emotionalResponsiveness: 0.5,
            emotionalStability: 0.7,
            gestureIntensity: 'natural',
            gestureFrequency: 3,
            gestureVariety: 0.5,
            voicePersonality: 'friendly',
            voiceTone: 'conversational',
            voiceSpeed: 1.0,
            minimalMode: false,
            reducedAnimations: true,
            staticMode: false,
            userOverrideEnabled: true,
            safetyLimitsEnabled: true,
            parentalControlsEnabled: false,
            accessibilityMode: false,
            reducedMotion: false,
            highContrast: false,
            culturalAdaptation: true,
            gestureStyle: 'neutral',
            eyeContactLevel: 0.6,
            personalSpacePreference: 0.6
          }
        }
      ];

      return {
        success: true,
        data: presets,
        executionTime: Date.now() - startTime,
        timestamp: Date.now()
      };
    } catch (error) {
      return {
        success: false,
        error: {
          type: AvatarErrorType.AUTHENTICATION_FAILURE,
          message: `Failed to get control presets: ${error instanceof Error ? error.message : 'Unknown error'}`,
          timestamp: Date.now(),
          platform: this.getCurrentPlatform(),
          recoverable: true
        },
        executionTime: Date.now() - startTime,
        timestamp: Date.now()
      };
    }
  }

  async applyControlPreset(identityId: string, presetId: string): Promise<AvatarApiResponse<ControlOverrideResult[]>> {
    const startTime = Date.now();
    
    try {
      const presetsResponse = await this.getControlPresets();
      if (!presetsResponse.success || !presetsResponse.data) {
        return {
          success: false,
          error: presetsResponse.error,
          executionTime: Date.now() - startTime,
          timestamp: Date.now()
        };
      }

      const preset = presetsResponse.data.find(p => p.id === presetId);
      if (!preset) {
        return {
          success: false,
          error: {
            type: AvatarErrorType.AUTHENTICATION_FAILURE,
            message: `Preset not found: ${presetId}`,
            timestamp: Date.now(),
            platform: this.getCurrentPlatform(),
            recoverable: false
          },
          executionTime: Date.now() - startTime,
          timestamp: Date.now()
        };
      }

      // Apply preset settings
      const updateResponse = await this.updateUserControlSettings(identityId, preset.settings);
      if (!updateResponse.success) {
        return {
          success: false,
          error: updateResponse.error,
          executionTime: Date.now() - startTime,
          timestamp: Date.now()
        };
      }

      // Create override results for all applied settings
      const overrideResults: ControlOverrideResult[] = Object.entries(preset.settings).map(([key, value]) => ({
        applied: true,
        originalValue: undefined, // Would need to track previous values
        newValue: value,
        reason: `Applied from preset: ${preset.name}`,
        safetyBoundaryTriggered: false
      }));

      return {
        success: true,
        data: overrideResults,
        executionTime: Date.now() - startTime,
        timestamp: Date.now()
      };
    } catch (error) {
      return {
        success: false,
        error: {
          type: AvatarErrorType.AUTHENTICATION_FAILURE,
          message: `Failed to apply control preset: ${error instanceof Error ? error.message : 'Unknown error'}`,
          timestamp: Date.now(),
          platform: this.getCurrentPlatform(),
          recoverable: true
        },
        executionTime: Date.now() - startTime,
        timestamp: Date.now()
      };
    }
  }

  // Event Handling
  onControlChanged(callback: ControlChangeCallback): void {
    this.controlChangeCallbacks.push(callback);
  }

  onSafetyBoundaryTriggered(callback: SafetyBoundaryCallback): void {
    this.safetyBoundaryCallbacks.push(callback);
  }

  // Cleanup
  async cleanup(): Promise<AvatarApiResponse<void>> {
    const startTime = Date.now();
    
    try {
      this.controlSettings.clear();
      this.controlChangeCallbacks.length = 0;
      this.safetyBoundaryCallbacks.length = 0;

      return {
        success: true,
        executionTime: Date.now() - startTime,
        timestamp: Date.now()
      };
    } catch (error) {
      return {
        success: false,
        error: {
          type: AvatarErrorType.AUTHENTICATION_FAILURE,
          message: `Failed to cleanup: ${error instanceof Error ? error.message : 'Unknown error'}`,
          timestamp: Date.now(),
          platform: this.getCurrentPlatform(),
          recoverable: true
        },
        executionTime: Date.now() - startTime,
        timestamp: Date.now()
      };
    }
  }
  // Private helper methods
  private createDefaultSettings(): UserControlSettings {
    return {
      // Expressiveness Controls
      expressiveness: 'medium',
      emotionalResponsiveness: 0.7,
      emotionalStability: 0.8,
      
      // Gesture Controls
      gestureIntensity: 'natural',
      gestureFrequency: 5,
      gestureVariety: 0.8,
      
      // Voice Controls
      voicePersonality: 'friendly',
      voiceTone: 'conversational',
      voiceSpeed: 1.0,
      
      // Mode Controls
      minimalMode: false,
      reducedAnimations: false,
      staticMode: false,
      
      // Safety Boundaries
      userOverrideEnabled: true,
      safetyLimitsEnabled: true,
      parentalControlsEnabled: false,
      
      // Accessibility
      accessibilityMode: false,
      reducedMotion: false,
      highContrast: false,
      
      // Cultural Sensitivity
      culturalAdaptation: true,
      gestureStyle: 'neutral',
      eyeContactLevel: 0.7,
      personalSpacePreference: 0.5
    };
  }

  private getCurrentPlatform(): Platform {
    if (typeof window !== 'undefined') {
      return 'web';
    } else if (typeof process !== 'undefined') {
      switch (process.platform) {
        case 'win32': return 'windows';
        case 'darwin': return 'macos';
        case 'linux': return 'web';
        default: return 'web';
      }
    }
    return 'web';
  }

  private isExpressivenessWithinLimits(level: ExpressivenessLevel): boolean {
    const levels: ExpressivenessLevel[] = ['low', 'medium', 'high'];
    const maxIndex = levels.indexOf(this.SAFETY_LIMITS.maxExpressiveness);
    const levelIndex = levels.indexOf(level);
    return levelIndex <= maxIndex;
  }

  private isGestureIntensityWithinLimits(intensity: GestureIntensity): boolean {
    const intensities: GestureIntensity[] = ['subtle', 'natural', 'expressive'];
    const maxIndex = intensities.indexOf(this.SAFETY_LIMITS.maxGestureIntensity);
    const intensityIndex = intensities.indexOf(intensity);
    return intensityIndex <= maxIndex;
  }

  private async updateControlWithOverride<T>(
    identityId: string,
    controlType: string,
    value: T,
    updateFunction: (settings: UserControlSettings, value: T) => ControlOverrideResult
  ): Promise<AvatarApiResponse<ControlOverrideResult>> {
    const startTime = Date.now();
    
    try {
      const settingsResponse = await this.getUserControlSettings(identityId);
      if (!settingsResponse.success || !settingsResponse.data) {
        return {
          success: false,
          error: settingsResponse.error,
          executionTime: Date.now() - startTime,
          timestamp: Date.now()
        };
      }

      const settings = settingsResponse.data;
      const result = updateFunction(settings, value);

      if (result.applied) {
        // Store updated settings
        this.controlSettings.set(identityId, settings);
        
        // Notify callbacks
        this.notifyControlChanged(identityId, controlType, result.originalValue, result.newValue, result);
      }

      return {
        success: true,
        data: result,
        executionTime: Date.now() - startTime,
        timestamp: Date.now()
      };
    } catch (error) {
      return {
        success: false,
        error: {
          type: AvatarErrorType.AUTHENTICATION_FAILURE,
          message: `Failed to update control: ${error instanceof Error ? error.message : 'Unknown error'}`,
          timestamp: Date.now(),
          platform: this.getCurrentPlatform(),
          recoverable: true
        },
        executionTime: Date.now() - startTime,
        timestamp: Date.now()
      };
    }
  }

  private notifyControlChanged(
    identityId: string,
    controlType: string,
    oldValue: unknown,
    newValue: unknown,
    overrideResult: ControlOverrideResult
  ): void {
    for (const callback of this.controlChangeCallbacks) {
      try {
        callback(identityId, controlType, oldValue, newValue, overrideResult);
      } catch (error) {
        console.error('Error in control change callback:', error);
      }
    }
  }

  private notifySafetyBoundaryTriggered(
    identityId: string,
    violation: SafetyBoundaryViolation,
    correctedSettings: UserControlSettings
  ): void {
    for (const callback of this.safetyBoundaryCallbacks) {
      try {
        callback(identityId, violation, correctedSettings);
      } catch (error) {
        console.error('Error in safety boundary callback:', error);
      }
    }
  }
}