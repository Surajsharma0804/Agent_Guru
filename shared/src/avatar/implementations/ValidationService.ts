/**
 * Validation Service for Avatar Identity Configuration
 * 
 * Provides comprehensive validation for avatar identity configurations,
 * including business rules, platform compatibility, and security constraints.
 */

import {
  AvatarIdentityConfig,
  ValidationResult,
  ValidationError,
  ValidationWarning,
  ConfigurationSuggestion
} from '../interfaces/IdentityManager';

import {
  Gender,
  VoiceStyle,
  PersonalityTone,
  VoicePersonality,
  ExpressivenessLevel,
  GestureIntensity,
  Platform
} from '../types/Common';

/**
 * Validation service interface
 */
export interface ValidationService {
  validateConfiguration(config: AvatarIdentityConfig): Promise<ValidationResult>;
  validatePartialConfig(config: Partial<AvatarIdentityConfig>): Promise<ValidationResult>;
  validatePlatformCompatibility(config: AvatarIdentityConfig, platform: Platform): Promise<ValidationResult>;
  validateBusinessRules(config: AvatarIdentityConfig): Promise<ValidationResult>;
  validateSecurityConstraints(config: AvatarIdentityConfig): Promise<ValidationResult>;
}

/**
 * Production implementation of validation service
 */
export class ValidationServiceImpl implements ValidationService {
  private readonly validGenders: Gender[] = ['male', 'female', 'non-binary'];
  private readonly validVoiceStyles: VoiceStyle[] = ['calm', 'friendly', 'professional', 'energetic'];
  private readonly validPersonalityTones: PersonalityTone[] = ['co-worker', 'best-friend', 'assistant', 'mentor'];
  private readonly validVoicePersonalities: VoicePersonality[] = ['formal', 'friendly', 'casual'];
  private readonly validExpressivenessLevels: ExpressivenessLevel[] = ['low', 'medium', 'high'];
  private readonly validGestureIntensities: GestureIntensity[] = ['subtle', 'natural', 'expressive'];

  async validateConfiguration(config: AvatarIdentityConfig): Promise<ValidationResult> {
    const errors: ValidationError[] = [];
    const warnings: ValidationWarning[] = [];
    const suggestions: ConfigurationSuggestion[] = [];

    // Validate required fields
    this.validateRequiredFields(config, errors);
    
    // Validate field values
    this.validateFieldValues(config, errors, warnings);
    
    // Validate business rules
    const businessRules = await this.validateBusinessRules(config);
    errors.push(...businessRules.errors);
    warnings.push(...businessRules.warnings);
    suggestions.push(...businessRules.suggestions);
    
    // Validate security constraints
    const securityConstraints = await this.validateSecurityConstraints(config);
    errors.push(...securityConstraints.errors);
    warnings.push(...securityConstraints.warnings);
    suggestions.push(...securityConstraints.suggestions);
    
    // Generate suggestions for optimization
    this.generateOptimizationSuggestions(config, suggestions);

    return {
      valid: errors.length === 0,
      errors,
      warnings,
      suggestions
    };
  }

  async validatePartialConfig(config: Partial<AvatarIdentityConfig>): Promise<ValidationResult> {
    const errors: ValidationError[] = [];
    const warnings: ValidationWarning[] = [];
    const suggestions: ConfigurationSuggestion[] = [];

    // Validate only provided fields
    if (config.gender !== undefined) {
      this.validateGender(config.gender, errors);
    }
    
    if (config.voiceStyle !== undefined) {
      this.validateVoiceStyle(config.voiceStyle, errors);
    }
    
    if (config.personalityTone !== undefined) {
      this.validatePersonalityTone(config.personalityTone, errors);
    }
    
    if (config.voicePersonality !== undefined) {
      this.validateVoicePersonality(config.voicePersonality, errors);
    }
    
    if (config.expressiveness !== undefined) {
      this.validateExpressiveness(config.expressiveness, errors);
    }
    
    if (config.gestureIntensity !== undefined) {
      this.validateGestureIntensity(config.gestureIntensity, errors);
    }
    
    if (config.accent !== undefined) {
      this.validateAccent(config.accent, errors, warnings);
    }
    
    if (config.minimalMode !== undefined) {
      this.validateMinimalMode(config.minimalMode, config, warnings, suggestions);
    }

    return {
      valid: errors.length === 0,
      errors,
      warnings,
      suggestions
    };
  }

  async validatePlatformCompatibility(config: AvatarIdentityConfig, platform: Platform): Promise<ValidationResult> {
    const errors: ValidationError[] = [];
    const warnings: ValidationWarning[] = [];
    const suggestions: ConfigurationSuggestion[] = [];

    // Platform-specific validation rules
    switch (platform) {
      case 'android':
      case 'ios':
        // Mobile platforms have limited resources
        if (config.expressiveness === 'high' && config.gestureIntensity === 'expressive') {
          warnings.push({
            field: 'expressiveness',
            message: 'High expressiveness with expressive gestures may impact battery life on mobile devices',
            code: 'MOBILE_PERFORMANCE_WARNING',
            impact: 'performance'
          });
          
          suggestions.push({
            field: 'expressiveness',
            suggestion: 'Consider using medium expressiveness on mobile devices',
            reason: 'Better battery life and performance',
            benefit: 'Improved user experience on mobile platforms'
          });
        }
        break;
        
      case 'web':
        // Web platform has limited 3D capabilities
        if (config.gestureIntensity === 'expressive') {
          warnings.push({
            field: 'gestureIntensity',
            message: 'Expressive gestures may have limited visual impact on web platform',
            code: 'WEB_GESTURE_LIMITATION',
            impact: 'user_experience'
          });
        }
        break;
        
      case 'windows':
      case 'macos':
        // Desktop platforms support full features
        break;
    }

    return {
      valid: errors.length === 0,
      errors,
      warnings,
      suggestions
    };
  }

  async validateBusinessRules(config: AvatarIdentityConfig): Promise<ValidationResult> {
    const errors: ValidationError[] = [];
    const warnings: ValidationWarning[] = [];
    const suggestions: ConfigurationSuggestion[] = [];

    // Business rule: Professional voice style should match formal personality
    if (config.voiceStyle === 'professional' && config.voicePersonality === 'casual') {
      warnings.push({
        field: 'voicePersonality',
        message: 'Professional voice style typically works better with formal personality',
        code: 'VOICE_PERSONALITY_MISMATCH',
        impact: 'user_experience'
      });
      
      suggestions.push({
        field: 'voicePersonality',
        suggestion: 'Use formal voice personality with professional voice style',
        reason: 'Better consistency in avatar behavior',
        benefit: 'More coherent user experience'
      });
    }

    // Business rule: Best friend tone should be expressive
    if (config.personalityTone === 'best-friend' && config.expressiveness === 'low') {
      warnings.push({
        field: 'expressiveness',
        message: 'Best friend personality tone typically benefits from higher expressiveness',
        code: 'PERSONALITY_EXPRESSIVENESS_MISMATCH',
        impact: 'user_experience'
      });
      
      suggestions.push({
        field: 'expressiveness',
        suggestion: 'Consider medium or high expressiveness for best friend tone',
        reason: 'More natural and engaging interactions',
        benefit: 'Better emotional connection with avatar'
      });
    }

    // Business rule: Minimal mode should have low expressiveness
    if (config.minimalMode && (config.expressiveness === 'high' || config.gestureIntensity === 'expressive')) {
      errors.push({
        field: 'minimalMode',
        message: 'Minimal mode is incompatible with high expressiveness or expressive gestures',
        code: 'MINIMAL_MODE_CONFLICT',
        severity: 'error'
      });
    }

    // Business rule: Assistant tone should be professional or calm
    if (config.personalityTone === 'assistant' && config.voiceStyle === 'energetic') {
      warnings.push({
        field: 'voiceStyle',
        message: 'Assistant personality typically works better with professional or calm voice style',
        code: 'ASSISTANT_VOICE_MISMATCH',
        impact: 'user_experience'
      });
    }

    return {
      valid: errors.length === 0,
      errors,
      warnings,
      suggestions
    };
  }

  async validateSecurityConstraints(config: AvatarIdentityConfig): Promise<ValidationResult> {
    const errors: ValidationError[] = [];
    const warnings: ValidationWarning[] = [];
    const suggestions: ConfigurationSuggestion[] = [];

    // Security constraint: Validate accent string for injection attacks
    if (config.accent && this.containsSuspiciousContent(config.accent)) {
      errors.push({
        field: 'accent',
        message: 'Accent configuration contains potentially unsafe content',
        code: 'SECURITY_ACCENT_VALIDATION',
        severity: 'error'
      });
    }

    // Security constraint: Validate facial features for reasonable bounds
    if (config.facialFeatures) {
      for (const [category, features] of Object.entries(config.facialFeatures)) {
        if (features && typeof features === 'object') {
          for (const [feature, value] of Object.entries(features)) {
            if (typeof value === 'number' && (value < -1.0 || value > 1.0)) {
              errors.push({
                field: `facialFeatures.${category}.${feature}`,
                message: 'Facial feature values must be between -1.0 and 1.0',
                code: 'FACIAL_FEATURE_BOUNDS',
                severity: 'error'
              });
            }
          }
        }
      }
    }

    return {
      valid: errors.length === 0,
      errors,
      warnings,
      suggestions
    };
  }
  // Private validation methods
  private validateRequiredFields(config: AvatarIdentityConfig, errors: ValidationError[]): void {
    if (!config.gender) {
      errors.push({
        field: 'gender',
        message: 'Gender is required',
        code: 'REQUIRED_FIELD',
        severity: 'error'
      });
    }
    
    if (!config.voiceStyle) {
      errors.push({
        field: 'voiceStyle',
        message: 'Voice style is required',
        code: 'REQUIRED_FIELD',
        severity: 'error'
      });
    }
    
    if (!config.personalityTone) {
      errors.push({
        field: 'personalityTone',
        message: 'Personality tone is required',
        code: 'REQUIRED_FIELD',
        severity: 'error'
      });
    }
    
    if (!config.voicePersonality) {
      errors.push({
        field: 'voicePersonality',
        message: 'Voice personality is required',
        code: 'REQUIRED_FIELD',
        severity: 'error'
      });
    }
    
    if (!config.expressiveness) {
      errors.push({
        field: 'expressiveness',
        message: 'Expressiveness level is required',
        code: 'REQUIRED_FIELD',
        severity: 'error'
      });
    }
    
    if (!config.gestureIntensity) {
      errors.push({
        field: 'gestureIntensity',
        message: 'Gesture intensity is required',
        code: 'REQUIRED_FIELD',
        severity: 'error'
      });
    }
    
    if (config.minimalMode === undefined || config.minimalMode === null) {
      errors.push({
        field: 'minimalMode',
        message: 'Minimal mode setting is required',
        code: 'REQUIRED_FIELD',
        severity: 'error'
      });
    }
  }

  private validateFieldValues(config: AvatarIdentityConfig, errors: ValidationError[], warnings: ValidationWarning[]): void {
    this.validateGender(config.gender, errors);
    this.validateVoiceStyle(config.voiceStyle, errors);
    this.validatePersonalityTone(config.personalityTone, errors);
    this.validateVoicePersonality(config.voicePersonality, errors);
    this.validateExpressiveness(config.expressiveness, errors);
    this.validateGestureIntensity(config.gestureIntensity, errors);
    
    if (config.accent) {
      this.validateAccent(config.accent, errors, warnings);
    }
  }

  private validateGender(gender: Gender, errors: ValidationError[]): void {
    if (!this.validGenders.includes(gender)) {
      errors.push({
        field: 'gender',
        message: `Invalid gender. Must be one of: ${this.validGenders.join(', ')}`,
        code: 'INVALID_ENUM_VALUE',
        severity: 'error'
      });
    }
  }

  private validateVoiceStyle(voiceStyle: VoiceStyle, errors: ValidationError[]): void {
    if (!this.validVoiceStyles.includes(voiceStyle)) {
      errors.push({
        field: 'voiceStyle',
        message: `Invalid voice style. Must be one of: ${this.validVoiceStyles.join(', ')}`,
        code: 'INVALID_ENUM_VALUE',
        severity: 'error'
      });
    }
  }

  private validatePersonalityTone(personalityTone: PersonalityTone, errors: ValidationError[]): void {
    if (!this.validPersonalityTones.includes(personalityTone)) {
      errors.push({
        field: 'personalityTone',
        message: `Invalid personality tone. Must be one of: ${this.validPersonalityTones.join(', ')}`,
        code: 'INVALID_ENUM_VALUE',
        severity: 'error'
      });
    }
  }

  private validateVoicePersonality(voicePersonality: VoicePersonality, errors: ValidationError[]): void {
    if (!this.validVoicePersonalities.includes(voicePersonality)) {
      errors.push({
        field: 'voicePersonality',
        message: `Invalid voice personality. Must be one of: ${this.validVoicePersonalities.join(', ')}`,
        code: 'INVALID_ENUM_VALUE',
        severity: 'error'
      });
    }
  }

  private validateExpressiveness(expressiveness: ExpressivenessLevel, errors: ValidationError[]): void {
    if (!this.validExpressivenessLevels.includes(expressiveness)) {
      errors.push({
        field: 'expressiveness',
        message: `Invalid expressiveness level. Must be one of: ${this.validExpressivenessLevels.join(', ')}`,
        code: 'INVALID_ENUM_VALUE',
        severity: 'error'
      });
    }
  }

  private validateGestureIntensity(gestureIntensity: GestureIntensity, errors: ValidationError[]): void {
    if (!this.validGestureIntensities.includes(gestureIntensity)) {
      errors.push({
        field: 'gestureIntensity',
        message: `Invalid gesture intensity. Must be one of: ${this.validGestureIntensities.join(', ')}`,
        code: 'INVALID_ENUM_VALUE',
        severity: 'error'
      });
    }
  }

  private validateAccent(accent: string, errors: ValidationError[], warnings: ValidationWarning[]): void {
    // Validate accent format (should be region code)
    const accentRegex = /^[a-z]{2}-[a-z]{2,}$/i;
    if (!accentRegex.test(accent)) {
      errors.push({
        field: 'accent',
        message: 'Accent must be in format "language-region" (e.g., "en-us", "en-gb")',
        code: 'INVALID_ACCENT_FORMAT',
        severity: 'error'
      });
    }
    
    // Validate accent length
    if (accent.length > 10) {
      errors.push({
        field: 'accent',
        message: 'Accent string is too long (maximum 10 characters)',
        code: 'ACCENT_TOO_LONG',
        severity: 'error'
      });
    }
    
    // Warn about uncommon accents
    const commonAccents = ['en-us', 'en-gb', 'en-au', 'en-ca', 'es-es', 'es-mx', 'fr-fr', 'de-de', 'it-it', 'pt-br'];
    if (!commonAccents.includes(accent.toLowerCase())) {
      warnings.push({
        field: 'accent',
        message: 'Uncommon accent may have limited voice synthesis support',
        code: 'UNCOMMON_ACCENT',
        impact: 'compatibility'
      });
    }
  }

  private validateMinimalMode(
    minimalMode: boolean, 
    config: Partial<AvatarIdentityConfig>, 
    warnings: ValidationWarning[], 
    suggestions: ConfigurationSuggestion[]
  ): void {
    // Use warnings parameter to maintain consistency
    if (warnings.length === 0) {
      // Initialize warnings array if needed
    }
    
    if (minimalMode) {
      // Suggest compatible settings for minimal mode
      if (config.expressiveness && config.expressiveness !== 'low') {
        suggestions.push({
          field: 'expressiveness',
          suggestion: 'Use low expressiveness with minimal mode',
          reason: 'Minimal mode is designed for reduced visual activity',
          benefit: 'Consistent user experience'
        });
      }
      
      if (config.gestureIntensity && config.gestureIntensity !== 'subtle') {
        suggestions.push({
          field: 'gestureIntensity',
          suggestion: 'Use subtle gesture intensity with minimal mode',
          reason: 'Minimal mode is designed for reduced visual activity',
          benefit: 'Consistent user experience'
        });
      }
    }
  }

  private generateOptimizationSuggestions(config: AvatarIdentityConfig, suggestions: ConfigurationSuggestion[]): void {
    // Suggest performance optimizations
    if (config.expressiveness === 'high' && config.gestureIntensity === 'expressive') {
      suggestions.push({
        field: 'performance',
        suggestion: 'Consider reducing either expressiveness or gesture intensity for better performance',
        reason: 'High expressiveness with expressive gestures is resource intensive',
        benefit: 'Better performance and battery life'
      });
    }
    
    // Suggest accessibility improvements
    if (config.gestureIntensity === 'expressive') {
      suggestions.push({
        field: 'accessibility',
        suggestion: 'Consider providing a reduced motion option for users with vestibular disorders',
        reason: 'Expressive gestures may cause discomfort for some users',
        benefit: 'Better accessibility and inclusivity'
      });
    }
    
    // Suggest user experience improvements
    if (config.personalityTone === 'assistant' && config.expressiveness === 'high') {
      suggestions.push({
        field: 'expressiveness',
        suggestion: 'Consider medium expressiveness for assistant personality',
        reason: 'Assistants typically benefit from balanced emotional expression',
        benefit: 'More professional and trustworthy appearance'
      });
    }
  }

  private containsSuspiciousContent(input: string): boolean {
    // Check for common injection patterns
    const suspiciousPatterns = [
      /<script/i,
      /javascript:/i,
      /on\w+\s*=/i,
      /\$\{/,
      /\{\{/,
      /%[0-9a-f]{2}/i,
      /\\x[0-9a-f]{2}/i,
      /\\u[0-9a-f]{4}/i
    ];
    
    return suspiciousPatterns.some(pattern => pattern.test(input));
  }
}