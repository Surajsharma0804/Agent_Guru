/**
 * Mock User Control Manager - Production-grade user control testing capabilities
 * 
 * Provides comprehensive testing for user control override authority with
 * deterministic behavior for property-based testing while maintaining
 * interface compatibility with the real UserControlManager.
 */

import {
  ExpressivenessLevel,
  GestureIntensity,
  VoicePersonality,
  Platform,
  AvatarApiResponse
} from '../../types/Common';

/**
 * User control settings interface
 */
export interface UserControlSettings {
  // Expressiveness Controls
  expressiveness: ExpressivenessLevel;
  emotionalResponsiveness: number;
  emotionalStability: number;
  
  // Gesture Controls
  gestureIntensity: GestureIntensity;
  gestureFrequency: number;
  gestureVariety: number;
  
  // Voice Controls
  voicePersonality: VoicePersonality;
  voiceTone: 'professional' | 'conversational' | 'casual';
  voiceSpeed: number;
  
  // Mode Controls
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
  eyeContactLevel: number;
  personalSpacePreference: number;
}

/**
 * Control override result interface
 */
export interface ControlOverrideResult {
  applied: boolean;
  reason: string;
  safetyBoundaryTriggered: boolean;
  previousValue?: any;
  newValue?: any;
}

/**
 * Safety boundary violation interface
 */
export interface SafetyBoundaryViolation {
  type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  description: string;
  recommendedAction: string;
}

/**
 * Control preset interface
 */
export interface ControlPreset {
  id: string;
  name: string;
  description: string;
  category: 'accessibility' | 'performance' | 'professional' | 'personal' | 'minimal';
  settings: Partial<UserControlSettings>;
}

/**
 * Production-grade Mock User Control Manager
 */
export class MockUserControlManager {
  private readonly userSettings = new Map<string, UserControlSettings>();
  private readonly instanceId: string;
  private static instanceCounter = 0;

  constructor() {
    MockUserControlManager.instanceCounter++;
    this.instanceId = `mock-user-control-${MockUserControlManager.instanceCounter.toString().padStart(3, '0')}`;
  }

  /**
   * Reset global state for test isolation
   */
  static resetGlobalState(): void {
    MockUserControlManager.instanceCounter = 0;
  }

  /**
   * Get user control settings for an identity
   */
  async getUserControlSettings(identityId: string): Promise<AvatarApiResponse<UserControlSettings>> {
    try {
      const settings = this.userSettings.get(identityId) || this.createDefaultSettings();
      
      return {
        success: true,
        data: { ...settings }, // Deep clone to prevent reference sharing
        executionTime: 1,
        timestamp: Date.now()
      };
    } catch (error) {
      return {
        success: false,
        error: {
          type: 'SETTINGS_RETRIEVAL_ERROR' as any,
          message: error instanceof Error ? error.message : 'Failed to retrieve settings',
          timestamp: Date.now(),
          platform: 'test' as any,
          recoverable: true
        },
        executionTime: 1,
        timestamp: Date.now()
      };
    }
  }

  /**
   * Update user control settings
   */
  async updateUserControlSettings(identityId: string, settings: Partial<UserControlSettings>): Promise<AvatarApiResponse<void>> {
    try {
      const currentSettings = this.userSettings.get(identityId) || this.createDefaultSettings();
      const updatedSettings = { ...currentSettings, ...settings };
      
      // BUSINESS RULE VALIDATION: Enforce minimal mode constraints
      if (updatedSettings.minimalMode) {
        updatedSettings.expressiveness = 'low';
        updatedSettings.gestureIntensity = 'subtle';
        updatedSettings.reducedAnimations = true;
      }
      
      this.userSettings.set(identityId, updatedSettings);
      
      return {
        success: true,
        data: undefined,
        executionTime: 2,
        timestamp: Date.now()
      };
    } catch (error) {
      return {
        success: false,
        error: {
          type: 'SETTINGS_UPDATE_ERROR' as any,
          message: error instanceof Error ? error.message : 'Failed to update settings',
          timestamp: Date.now(),
          platform: 'test' as any,
          recoverable: true
        },
        executionTime: 2,
        timestamp: Date.now()
      };
    }
  }

  /**
   * Set expressiveness level with override logic
   */
  async setExpressiveness(identityId: string, expressiveness: ExpressivenessLevel): Promise<AvatarApiResponse<ControlOverrideResult>> {
    try {
      const currentSettings = this.userSettings.get(identityId) || this.createDefaultSettings();
      const previousValue = currentSettings.expressiveness;
      
      // SECURITY BOUNDARY: Check user override permissions
      if (!currentSettings.userOverrideEnabled) {
        return {
          success: true,
          data: {
            applied: false,
            reason: 'User overrides are disabled',
            safetyBoundaryTriggered: false,
            previousValue,
            newValue: expressiveness
          },
          executionTime: 1,
          timestamp: Date.now()
        };
      }
      
      // SAFETY BOUNDARY: Check minimal mode constraints
      if (currentSettings.minimalMode && expressiveness !== 'low') {
        return {
          success: true,
          data: {
            applied: false,
            reason: 'Minimal mode requires low expressiveness',
            safetyBoundaryTriggered: true,
            previousValue,
            newValue: expressiveness
          },
          executionTime: 1,
          timestamp: Date.now()
        };
      }
      
      // SAFETY BOUNDARY: Check safety limits
      if (currentSettings.safetyLimitsEnabled && expressiveness === 'high') {
        return {
          success: true,
          data: {
            applied: false,
            reason: 'Safety limits prevent high expressiveness',
            safetyBoundaryTriggered: true,
            previousValue,
            newValue: expressiveness
          },
          executionTime: 1,
          timestamp: Date.now()
        };
      }
      
      // APPLY OVERRIDE: Update settings
      currentSettings.expressiveness = expressiveness;
      this.userSettings.set(identityId, currentSettings);
      
      return {
        success: true,
        data: {
          applied: true,
          reason: 'Expressiveness updated successfully',
          safetyBoundaryTriggered: false,
          previousValue,
          newValue: expressiveness
        },
        executionTime: 1,
        timestamp: Date.now()
      };
    } catch (error) {
      return {
        success: false,
        error: {
          type: 'EXPRESSIVENESS_UPDATE_ERROR' as any,
          message: error instanceof Error ? error.message : 'Failed to update expressiveness',
          timestamp: Date.now(),
          platform: 'test' as any,
          recoverable: true
        },
        executionTime: 1,
        timestamp: Date.now()
      };
    }
  }

  /**
   * Set gesture intensity with override logic
   */
  async setGestureIntensity(identityId: string, gestureIntensity: GestureIntensity): Promise<AvatarApiResponse<ControlOverrideResult>> {
    try {
      const currentSettings = this.userSettings.get(identityId) || this.createDefaultSettings();
      const previousValue = currentSettings.gestureIntensity;
      
      // SECURITY BOUNDARY: Check user override permissions
      if (!currentSettings.userOverrideEnabled) {
        return {
          success: true,
          data: {
            applied: false,
            reason: 'User overrides are disabled',
            safetyBoundaryTriggered: false,
            previousValue,
            newValue: gestureIntensity
          },
          executionTime: 1,
          timestamp: Date.now()
        };
      }
      
      // SAFETY BOUNDARY: Check minimal mode constraints
      if (currentSettings.minimalMode && gestureIntensity !== 'subtle') {
        return {
          success: true,
          data: {
            applied: false,
            reason: 'Minimal mode requires subtle gestures',
            safetyBoundaryTriggered: true,
            previousValue,
            newValue: gestureIntensity
          },
          executionTime: 1,
          timestamp: Date.now()
        };
      }
      
      // APPLY OVERRIDE: Update settings
      currentSettings.gestureIntensity = gestureIntensity;
      this.userSettings.set(identityId, currentSettings);
      
      return {
        success: true,
        data: {
          applied: true,
          reason: 'Gesture intensity updated successfully',
          safetyBoundaryTriggered: false,
          previousValue,
          newValue: gestureIntensity
        },
        executionTime: 1,
        timestamp: Date.now()
      };
    } catch (error) {
      return {
        success: false,
        error: {
          type: 'GESTURE_UPDATE_ERROR' as any,
          message: error instanceof Error ? error.message : 'Failed to update gesture intensity',
          timestamp: Date.now(),
          platform: 'test' as any,
          recoverable: true
        },
        executionTime: 1,
        timestamp: Date.now()
      };
    }
  }

  /**
   * Set voice personality with override logic
   */
  async setVoicePersonality(identityId: string, voicePersonality: VoicePersonality): Promise<AvatarApiResponse<ControlOverrideResult>> {
    try {
      const currentSettings = this.userSettings.get(identityId) || this.createDefaultSettings();
      const previousValue = currentSettings.voicePersonality;
      
      // SECURITY BOUNDARY: Check user override permissions
      if (!currentSettings.userOverrideEnabled) {
        return {
          success: true,
          data: {
            applied: false,
            reason: 'User overrides are disabled',
            safetyBoundaryTriggered: false,
            previousValue,
            newValue: voicePersonality
          },
          executionTime: 1,
          timestamp: Date.now()
        };
      }
      
      // SAFETY BOUNDARY: Check parental controls
      if (currentSettings.parentalControlsEnabled) {
        return {
          success: true,
          data: {
            applied: false,
            reason: 'Parental controls prevent voice personality changes',
            safetyBoundaryTriggered: true,
            previousValue,
            newValue: voicePersonality
          },
          executionTime: 1,
          timestamp: Date.now()
        };
      }
      
      // SAFETY BOUNDARY: Check safety limits
      if (currentSettings.safetyLimitsEnabled) {
        return {
          success: true,
          data: {
            applied: false,
            reason: 'Safety limits prevent voice personality changes',
            safetyBoundaryTriggered: true,
            previousValue,
            newValue: voicePersonality
          },
          executionTime: 1,
          timestamp: Date.now()
        };
      }
      
      // APPLY OVERRIDE: Update settings
      currentSettings.voicePersonality = voicePersonality;
      this.userSettings.set(identityId, currentSettings);
      
      return {
        success: true,
        data: {
          applied: true,
          reason: 'Voice personality updated successfully',
          safetyBoundaryTriggered: false,
          previousValue,
          newValue: voicePersonality
        },
        executionTime: 1,
        timestamp: Date.now()
      };
    } catch (error) {
      return {
        success: false,
        error: {
          type: 'VOICE_UPDATE_ERROR' as any,
          message: error instanceof Error ? error.message : 'Failed to update voice personality',
          timestamp: Date.now(),
          platform: 'test' as any,
          recoverable: true
        },
        executionTime: 1,
        timestamp: Date.now()
      };
    }
  }

  /**
   * Set minimal mode with override logic
   */
  async setMinimalMode(identityId: string, minimalMode: boolean): Promise<AvatarApiResponse<ControlOverrideResult>> {
    try {
      const currentSettings = this.userSettings.get(identityId) || this.createDefaultSettings();
      const previousValue = currentSettings.minimalMode;
      
      // SECURITY BOUNDARY: Check user override permissions
      if (!currentSettings.userOverrideEnabled) {
        return {
          success: true,
          data: {
            applied: false,
            reason: 'User overrides are disabled',
            safetyBoundaryTriggered: false,
            previousValue,
            newValue: minimalMode
          },
          executionTime: 1,
          timestamp: Date.now()
        };
      }
      
      // APPLY OVERRIDE: Update settings and enforce constraints
      currentSettings.minimalMode = minimalMode;
      
      if (minimalMode) {
        currentSettings.expressiveness = 'low';
        currentSettings.gestureIntensity = 'subtle';
        currentSettings.reducedAnimations = true;
      }
      
      this.userSettings.set(identityId, currentSettings);
      
      return {
        success: true,
        data: {
          applied: true,
          reason: 'Minimal mode updated successfully',
          safetyBoundaryTriggered: false,
          previousValue,
          newValue: minimalMode
        },
        executionTime: 1,
        timestamp: Date.now()
      };
    } catch (error) {
      return {
        success: false,
        error: {
          type: 'MINIMAL_MODE_UPDATE_ERROR' as any,
          message: error instanceof Error ? error.message : 'Failed to update minimal mode',
          timestamp: Date.now(),
          platform: 'test' as any,
          recoverable: true
        },
        executionTime: 1,
        timestamp: Date.now()
      };
    }
  }

  /**
   * Set emotional stability
   */
  async setEmotionalStability(identityId: string, stability: number): Promise<AvatarApiResponse<ControlOverrideResult>> {
    try {
      const currentSettings = this.userSettings.get(identityId) || this.createDefaultSettings();
      const previousValue = currentSettings.emotionalStability;
      
      // SECURITY BOUNDARY: Check user override permissions
      if (!currentSettings.userOverrideEnabled) {
        return {
          success: true,
          data: {
            applied: false,
            reason: 'User overrides are disabled',
            safetyBoundaryTriggered: false,
            previousValue,
            newValue: stability
          },
          executionTime: 1,
          timestamp: Date.now()
        };
      }
      
      // VALIDATION: Check value range
      if (stability < 0 || stability > 1) {
        return {
          success: true,
          data: {
            applied: false,
            reason: 'Emotional stability must be between 0 and 1',
            safetyBoundaryTriggered: true,
            previousValue,
            newValue: stability
          },
          executionTime: 1,
          timestamp: Date.now()
        };
      }
      
      // APPLY OVERRIDE: Update settings
      currentSettings.emotionalStability = stability;
      this.userSettings.set(identityId, currentSettings);
      
      return {
        success: true,
        data: {
          applied: true,
          reason: 'Emotional stability updated successfully',
          safetyBoundaryTriggered: false,
          previousValue,
          newValue: stability
        },
        executionTime: 1,
        timestamp: Date.now()
      };
    } catch (error) {
      return {
        success: false,
        error: {
          type: 'STABILITY_UPDATE_ERROR' as any,
          message: error instanceof Error ? error.message : 'Failed to update emotional stability',
          timestamp: Date.now(),
          platform: 'test' as any,
          recoverable: true
        },
        executionTime: 1,
        timestamp: Date.now()
      };
    }
  }

  /**
   * Set voice speed
   */
  async setVoiceSpeed(identityId: string, speed: number): Promise<AvatarApiResponse<ControlOverrideResult>> {
    try {
      const currentSettings = this.userSettings.get(identityId) || this.createDefaultSettings();
      const previousValue = currentSettings.voiceSpeed;
      
      // SECURITY BOUNDARY: Check user override permissions
      if (!currentSettings.userOverrideEnabled) {
        return {
          success: true,
          data: {
            applied: false,
            reason: 'User overrides are disabled',
            safetyBoundaryTriggered: false,
            previousValue,
            newValue: speed
          },
          executionTime: 1,
          timestamp: Date.now()
        };
      }
      
      // VALIDATION: Check value range
      if (speed < 0.3 || speed > 2.5) {
        return {
          success: true,
          data: {
            applied: false,
            reason: 'Voice speed must be between 0.3 and 2.5',
            safetyBoundaryTriggered: true,
            previousValue,
            newValue: speed
          },
          executionTime: 1,
          timestamp: Date.now()
        };
      }
      
      // APPLY OVERRIDE: Update settings
      currentSettings.voiceSpeed = speed;
      this.userSettings.set(identityId, currentSettings);
      
      return {
        success: true,
        data: {
          applied: true,
          reason: 'Voice speed updated successfully',
          safetyBoundaryTriggered: false,
          previousValue,
          newValue: speed
        },
        executionTime: 1,
        timestamp: Date.now()
      };
    } catch (error) {
      return {
        success: false,
        error: {
          type: 'VOICE_SPEED_UPDATE_ERROR' as any,
          message: error instanceof Error ? error.message : 'Failed to update voice speed',
          timestamp: Date.now(),
          platform: 'test' as any,
          recoverable: true
        },
        executionTime: 1,
        timestamp: Date.now()
      };
    }
  }

  /**
   * Enable or disable safety limits
   */
  async enableSafetyLimits(identityId: string, enabled: boolean): Promise<AvatarApiResponse<void>> {
    try {
      const currentSettings = this.userSettings.get(identityId) || this.createDefaultSettings();
      currentSettings.safetyLimitsEnabled = enabled;
      this.userSettings.set(identityId, currentSettings);
      
      return {
        success: true,
        data: undefined,
        executionTime: 1,
        timestamp: Date.now()
      };
    } catch (error) {
      return {
        success: false,
        error: {
          type: 'SAFETY_LIMITS_UPDATE_ERROR' as any,
          message: error instanceof Error ? error.message : 'Failed to update safety limits',
          timestamp: Date.now(),
          platform: 'test' as any,
          recoverable: true
        },
        executionTime: 1,
        timestamp: Date.now()
      };
    }
  }

  /**
   * Get available control presets
   */
  async getControlPresets(): Promise<AvatarApiResponse<ControlPreset[]>> {
    try {
      const presets: ControlPreset[] = [
        {
          id: 'accessibility-high-contrast',
          name: 'High Contrast Accessibility',
          description: 'Optimized for users with visual impairments',
          category: 'accessibility',
          settings: {
            highContrast: true,
            reducedMotion: true,
            accessibilityMode: true,
            expressiveness: 'medium',
            gestureIntensity: 'natural',
            voicePersonality: 'formal',
            minimalMode: false
          }
        },
        {
          id: 'performance-minimal',
          name: 'Performance Optimized',
          description: 'Minimal resource usage for better performance',
          category: 'performance',
          settings: {
            minimalMode: true,
            reducedAnimations: true,
            staticMode: false,
            expressiveness: 'low',
            gestureIntensity: 'subtle',
            voicePersonality: 'formal',
            culturalAdaptation: false
          }
        },
        {
          id: 'professional-formal',
          name: 'Professional Formal',
          description: 'Formal presentation style for business environments',
          category: 'professional',
          settings: {
            expressiveness: 'low',
            gestureIntensity: 'subtle',
            voicePersonality: 'formal',
            voiceTone: 'professional',
            minimalMode: false,
            culturalAdaptation: true,
            gestureStyle: 'western'
          }
        },
        {
          id: 'personal-expressive',
          name: 'Personal Expressive',
          description: 'Expressive and engaging for personal interactions',
          category: 'personal',
          settings: {
            expressiveness: 'high',
            gestureIntensity: 'expressive',
            voicePersonality: 'friendly',
            voiceTone: 'conversational',
            minimalMode: false,
            culturalAdaptation: true,
            gestureStyle: 'neutral'
          }
        },
        {
          id: 'minimal-basic',
          name: 'Minimal Basic',
          description: 'Basic functionality with minimal features',
          category: 'minimal',
          settings: {
            minimalMode: true,
            staticMode: true,
            reducedAnimations: true,
            expressiveness: 'low',
            gestureIntensity: 'subtle',
            voicePersonality: 'formal',
            culturalAdaptation: false
          }
        }
      ];
      
      return {
        success: true,
        data: presets,
        executionTime: 1,
        timestamp: Date.now()
      };
    } catch (error) {
      return {
        success: false,
        error: {
          type: 'PRESETS_RETRIEVAL_ERROR' as any,
          message: error instanceof Error ? error.message : 'Failed to retrieve presets',
          timestamp: Date.now(),
          platform: 'test' as any,
          recoverable: true
        },
        executionTime: 1,
        timestamp: Date.now()
      };
    }
  }

  /**
   * Apply a control preset
   */
  async applyControlPreset(identityId: string, presetId: string): Promise<AvatarApiResponse<void>> {
    try {
      const presetsResponse = await this.getControlPresets();
      if (!presetsResponse.success) {
        throw new Error('Failed to retrieve presets');
      }
      
      const preset = presetsResponse.data!.find(p => p.id === presetId);
      if (!preset) {
        throw new Error(`Preset not found: ${presetId}`);
      }
      
      const currentSettings = this.userSettings.get(identityId) || this.createDefaultSettings();
      const updatedSettings = { ...currentSettings, ...preset.settings };
      
      // BUSINESS RULE VALIDATION: Enforce minimal mode constraints
      if (updatedSettings.minimalMode) {
        updatedSettings.expressiveness = 'low';
        updatedSettings.gestureIntensity = 'subtle';
        updatedSettings.reducedAnimations = true;
      }
      
      this.userSettings.set(identityId, updatedSettings);
      
      return {
        success: true,
        data: undefined,
        executionTime: 2,
        timestamp: Date.now()
      };
    } catch (error) {
      return {
        success: false,
        error: {
          type: 'PRESET_APPLICATION_ERROR' as any,
          message: error instanceof Error ? error.message : 'Failed to apply preset',
          timestamp: Date.now(),
          platform: 'test' as any,
          recoverable: true
        },
        executionTime: 2,
        timestamp: Date.now()
      };
    }
  }

  /**
   * Validate platform compatibility
   */
  async validatePlatformCompatibility(identityId: string, platform: Platform): Promise<AvatarApiResponse<boolean>> {
    try {
      // All platforms are compatible in mock implementation
      return {
        success: true,
        data: true,
        executionTime: 1,
        timestamp: Date.now()
      };
    } catch (error) {
      return {
        success: false,
        error: {
          type: 'COMPATIBILITY_CHECK_ERROR' as any,
          message: error instanceof Error ? error.message : 'Failed to check compatibility',
          timestamp: Date.now(),
          platform: 'test' as any,
          recoverable: true
        },
        executionTime: 1,
        timestamp: Date.now()
      };
    }
  }

  /**
   * Cleanup for test isolation
   */
  async cleanup(): Promise<void> {
    this.userSettings.clear();
  }

  /**
   * Create default user control settings
   */
  private createDefaultSettings(): UserControlSettings {
    return {
      // Expressiveness Controls
      expressiveness: 'medium',
      emotionalResponsiveness: 0.7,
      emotionalStability: 0.8,
      
      // Gesture Controls
      gestureIntensity: 'natural',
      gestureFrequency: 5,
      gestureVariety: 0.6,
      
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
      safetyLimitsEnabled: false,
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

  /**
   * Get instance ID for debugging
   */
  getInstanceId(): string {
    return this.instanceId;
  }
}