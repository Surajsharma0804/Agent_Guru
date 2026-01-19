/**
 * Mock User Control Manager for Testing
 * 
 * Production-grade mock implementation that provides deterministic behavior
 * for property-based testing with complete override logic implementation.
 */

import {
  UserControlManager,
  UserControlSettings,
  ControlOverrideResult,
  SafetyBoundaryViolation,
  UserControlPreset,
  ControlChangeCallback,
  SafetyBoundaryCallback
} from '../../implementations/UserControlManager';

import {
  ExpressivenessLevel,
  GestureIntensity,
  VoicePersonality,
  AvatarApiResponse,
  AvatarErrorType,
  Platform
} from '../../types/Common';

/**
 * Mock User Control Manager with complete override logic
 */
export class MockUserControlManager implements UserControlManager {
  private readonly controlSettings: Map<string, UserControlSettings> = new Map();
  private readonly controlChangeCallbacks: ControlChangeCallback[] = [];
  private readonly safetyBoundaryCallbacks: SafetyBoundaryCallback[] = [];

  // Control Settings Management
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
        data: settings,
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
          error: currentSettings.error,
          executionTime: Date.now() - startTime,
          timestamp: Date.now()
        };
      }

      // Merge settings
      const updatedSettings = { ...currentSettings.data, ...settings };
      this.controlSettings.set(identityId, updatedSettings);

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
        data: defaultSettings,
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
      
      // SECURITY BOUNDARY: Check if user overrides are enabled FIRST
      if (!settings.userOverrideEnabled) {
        return {
          applied: false,
          originalValue,
          newValue: originalValue, // CRITICAL: Keep original value when blocked
          reason: 'User overrides are disabled',
          safetyBoundaryTriggered: false // This is not a safety boundary, it's a user preference
        };
      }
      
      // CRITICAL FIX: Apply minimal mode constraints FIRST - this is the primary safety boundary
      // Minimal mode must be checked before safety limits to ensure correct error messages
      if (settings.minimalMode && value !== 'low') {
        return {
          applied: false,
          originalValue,
          newValue: originalValue, // CRITICAL: Keep original value when blocked
          reason: 'Minimal mode requires low expressiveness',
          safetyBoundaryTriggered: true
        };
      }
      
      // SECURITY BOUNDARY: Apply safety limits constraints AFTER minimal mode
      if (settings.safetyLimitsEnabled && value === 'high') {
        return {
          applied: false,
          originalValue,
          newValue: originalValue, // CRITICAL: Keep original value when blocked
          reason: 'Safety limits restrict high expressiveness',
          safetyBoundaryTriggered: true
        };
      }

      // APPLY CHANGE: Only modify settings if change is allowed
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
      
      if (!settings.userOverrideEnabled) {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'User overrides are disabled',
          safetyBoundaryTriggered: false
        };
      }

      if (value < 0.0 || value > 1.0) {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'Emotional responsiveness must be between 0.0 and 1.0',
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
      
      if (!settings.userOverrideEnabled) {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'User overrides are disabled',
          safetyBoundaryTriggered: false
        };
      }

      if (value < 0.0 || value > 1.0) {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'Emotional stability must be between 0.0 and 1.0',
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
      
      if (!settings.userOverrideEnabled) {
        return {
          applied: false,
          originalValue,
          newValue: originalValue, // CRITICAL: Keep original value when blocked
          reason: 'User overrides are disabled',
          safetyBoundaryTriggered: false
        };
      }
      
      // Apply minimal mode constraints FIRST
      if (settings.minimalMode && value !== 'subtle') {
        return {
          applied: false,
          originalValue,
          newValue: originalValue, // CRITICAL: Keep original value when blocked
          reason: 'Minimal mode requires subtle gesture intensity',
          safetyBoundaryTriggered: true
        };
      }

      // APPLY CHANGE: Only modify settings if change is allowed
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
      
      if (!settings.userOverrideEnabled) {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'User overrides are disabled',
          safetyBoundaryTriggered: false
        };
      }

      if (value < 0 || value > 15) {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'Gesture frequency must be between 0 and 15',
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
      
      if (!settings.userOverrideEnabled) {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'User overrides are disabled',
          safetyBoundaryTriggered: false
        };
      }

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
      
      // SECURITY BOUNDARY: Check if user overrides are enabled FIRST
      if (!settings.userOverrideEnabled) {
        return {
          applied: false,
          originalValue,
          newValue: originalValue, // CRITICAL: Keep original value when blocked
          reason: 'User overrides are disabled',
          safetyBoundaryTriggered: false // This is not a safety boundary, it's a user preference
        };
      }
      
      // SECURITY BOUNDARY: Apply parental controls
      if (settings.parentalControlsEnabled && value === 'casual') {
        return {
          applied: false,
          originalValue,
          newValue: originalValue, // CRITICAL: Keep original value when blocked
          reason: 'Parental controls restrict casual voice personality',
          safetyBoundaryTriggered: true
        };
      }

      // SECURITY BOUNDARY: Apply safety limits (only if enabled)
      if (settings.safetyLimitsEnabled && value === 'casual') {
        return {
          applied: false,
          originalValue,
          newValue: originalValue, // CRITICAL: Keep original value when blocked
          reason: 'Safety limits restrict casual voice personality',
          safetyBoundaryTriggered: true
        };
      }

      // APPLY CHANGE: Only modify settings if change is allowed
      // CRITICAL FIX: User overrides enabled and no blocking safety boundaries - MUST apply change
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
      
      if (!settings.userOverrideEnabled) {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'User overrides are disabled',
          safetyBoundaryTriggered: false
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
      
      if (!settings.userOverrideEnabled) {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'User overrides are disabled',
          safetyBoundaryTriggered: false
        };
      }

      if (value < 0.3 || value > 2.5) {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'Voice speed must be between 0.3 and 2.5',
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
      
      if (!settings.userOverrideEnabled) {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'User overrides are disabled',
          safetyBoundaryTriggered: false
        };
      }

      settings.minimalMode = value;
      
      // Auto-adjust related settings when enabling minimal mode
      if (value) {
        settings.expressiveness = 'low';
        settings.gestureIntensity = 'subtle';
        settings.reducedAnimations = true;
      }

      return {
        applied: true,
        originalValue,
        newValue: value,
        reason: 'Minimal mode updated successfully',
        safetyBoundaryTriggered: false
      };
    });
  }

  async setReducedAnimations(identityId: string, enabled: boolean): Promise<AvatarApiResponse<ControlOverrideResult>> {
    return this.updateControlWithOverride(identityId, 'reducedAnimations', enabled, (settings, value) => {
      const originalValue = settings.reducedAnimations;
      
      if (!settings.userOverrideEnabled) {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'User overrides are disabled',
          safetyBoundaryTriggered: false
        };
      }

      settings.reducedAnimations = value;
      return {
        applied: true,
        originalValue,
        newValue: value,
        reason: 'Reduced animations updated successfully',
        safetyBoundaryTriggered: false
      };
    });
  }

  async setStaticMode(identityId: string, enabled: boolean): Promise<AvatarApiResponse<ControlOverrideResult>> {
    return this.updateControlWithOverride(identityId, 'staticMode', enabled, (settings, value) => {
      const originalValue = settings.staticMode;
      
      if (!settings.userOverrideEnabled) {
        return {
          applied: false,
          originalValue,
          newValue: value,
          reason: 'User overrides are disabled',
          safetyBoundaryTriggered: false
        };
      }

      settings.staticMode = value;
      return {
        applied: true,
        originalValue,
        newValue: value,
        reason: 'Static mode updated successfully',
        safetyBoundaryTriggered: false
      };
    });
  }

  // Safety Boundaries
  async enableUserOverrides(identityId: string): Promise<AvatarApiResponse<void>> {
    const settings = await this.getUserControlSettings(identityId);
    if (!settings.success || !settings.data) {
      return {
        success: false,
        error: settings.error,
        executionTime: 0,
        timestamp: Date.now()
      };
    }

    settings.data.userOverrideEnabled = true;
    this.controlSettings.set(identityId, settings.data);

    return {
      success: true,
      executionTime: 0,
      timestamp: Date.now()
    };
  }

  async disableUserOverrides(identityId: string): Promise<AvatarApiResponse<void>> {
    const settings = await this.getUserControlSettings(identityId);
    if (!settings.success || !settings.data) {
      return {
        success: false,
        error: settings.error,
        executionTime: 0,
        timestamp: Date.now()
      };
    }

    settings.data.userOverrideEnabled = false;
    this.controlSettings.set(identityId, settings.data);

    return {
      success: true,
      executionTime: 0,
      timestamp: Date.now()
    };
  }

  async enableSafetyLimits(identityId: string, enabled: boolean): Promise<AvatarApiResponse<void>> {
    const settings = await this.getUserControlSettings(identityId);
    if (!settings.success || !settings.data) {
      return {
        success: false,
        error: settings.error,
        executionTime: 0,
        timestamp: Date.now()
      };
    }

    settings.data.safetyLimitsEnabled = enabled;
    this.controlSettings.set(identityId, settings.data);

    return {
      success: true,
      executionTime: 0,
      timestamp: Date.now()
    };
  }

  async disableSafetyLimits(identityId: string): Promise<AvatarApiResponse<void>> {
    return this.enableSafetyLimits(identityId, false);
  }

  async validateSafetyBoundaries(identityId: string): Promise<AvatarApiResponse<SafetyBoundaryViolation[]>> {
    return {
      success: true,
      data: [],
      executionTime: 0,
      timestamp: Date.now()
    };
  }

  // Configuration Presets
  async getControlPresets(): Promise<AvatarApiResponse<UserControlPreset[]>> {
    const presets: UserControlPreset[] = [
      {
        id: 'professional',
        name: 'Professional Mode',
        description: 'Formal, focused settings for business environments',
        category: 'professional',
        settings: {
          expressiveness: 'low',
          emotionalResponsiveness: 0.3,
          emotionalStability: 0.9,
          gestureIntensity: 'subtle',
          gestureFrequency: 2,
          gestureVariety: 0.4,
          voicePersonality: 'formal',
          voiceTone: 'professional',
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
          culturalAdaptation: false,
          gestureStyle: 'western',
          eyeContactLevel: 0.7,
          personalSpacePreference: 0.6
        }
      }
    ];

    return {
      success: true,
      data: presets,
      executionTime: 0,
      timestamp: Date.now()
    };
  }

  async applyControlPreset(identityId: string, presetId: string): Promise<AvatarApiResponse<void>> {
    const presets = await this.getControlPresets();
    if (!presets.success || !presets.data) {
      return {
        success: false,
        error: presets.error,
        executionTime: 0,
        timestamp: Date.now()
      };
    }

    const preset = presets.data.find(p => p.id === presetId);
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
        executionTime: 0,
        timestamp: Date.now()
      };
    }

    return this.updateUserControlSettings(identityId, preset.settings);
  }

  // Platform Compatibility
  async validatePlatformCompatibility(identityId: string, platform: Platform): Promise<AvatarApiResponse<boolean>> {
    return {
      success: true,
      data: true,
      executionTime: 0,
      timestamp: Date.now()
    };
  }

  async getPlatformLimitations(platform: Platform): Promise<AvatarApiResponse<string[]>> {
    return {
      success: true,
      data: [],
      executionTime: 0,
      timestamp: Date.now()
    };
  }

  // Event Handling
  onControlChanged(callback: ControlChangeCallback): void {
    this.controlChangeCallbacks.push(callback);
  }

  onSafetyBoundaryViolation(callback: SafetyBoundaryCallback): void {
    this.safetyBoundaryCallbacks.push(callback);
  }

  // Cleanup
  async cleanup(): Promise<void> {
    this.controlSettings.clear();
    this.controlChangeCallbacks.length = 0;
    this.safetyBoundaryCallbacks.length = 0;
  }

  // Private helper methods
  private createDefaultSettings(): UserControlSettings {
    return {
      expressiveness: 'medium',
      emotionalResponsiveness: 0.7,
      emotionalStability: 0.8,
      gestureIntensity: 'natural',
      gestureFrequency: 5,
      gestureVariety: 0.8,
      voicePersonality: 'friendly',
      voiceTone: 'conversational',
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
      culturalAdaptation: false,
      gestureStyle: 'western',
      eyeContactLevel: 0.7,
      personalSpacePreference: 0.5
    };
  }

  // PRODUCTION-GRADE DATA INTEGRITY: Proper deep cloning with Date object preservation
  private deepCloneWithDateHandling(obj: any): any {
    if (obj === null || typeof obj !== 'object') {
      return obj;
    }
    
    if (obj instanceof Date) {
      return new Date(obj.getTime());
    }
    
    if (Array.isArray(obj)) {
      return obj.map(item => this.deepCloneWithDateHandling(item));
    }
    
    const cloned: any = {};
    for (const key in obj) {
      if (obj.hasOwnProperty(key)) {
        cloned[key] = this.deepCloneWithDateHandling(obj[key]);
      }
    }
    
    return cloned;
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

      // CRITICAL: Create deep copies to prevent mutation during validation
      const originalSettings = JSON.parse(JSON.stringify(settingsResponse.data));
      const workingSettings = JSON.parse(JSON.stringify(settingsResponse.data));
      
      // SECURITY: Execute update function with working copy
      const result = updateFunction(workingSettings, value);

      // CRITICAL SECURITY BOUNDARY: Only store settings if the change was actually applied
      if (result.applied) {
        // Change was approved - store the modified settings
        this.controlSettings.set(identityId, workingSettings);
        this.notifyControlChanged(identityId, controlType, result.originalValue, result.newValue, result);
      } else {
        // Change was blocked - ensure original settings are preserved
        this.controlSettings.set(identityId, originalSettings);
        this.notifyControlChanged(identityId, controlType, result.originalValue, result.originalValue, result);
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
}