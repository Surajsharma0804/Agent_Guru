/**
 * @fileoverview Skill system interfaces
 */

export interface Skill {
  readonly id: string;
  readonly name: string;
  readonly description: string;
  readonly version: string;
  readonly capabilities: SkillCapabilities;
  
  execute(context: SkillContext, parameters: Record<string, unknown>): Promise<SkillResult>;
  validate(parameters: Record<string, unknown>): Promise<ValidationResult>;
}

export interface SkillCapabilities {
  readonly requiresAuth: boolean;
  readonly requiresNetwork: boolean;
  readonly requiresStorage: boolean;
  readonly supportedPlatforms: string[];
}

export interface SkillContext {
  readonly userId: string;
  readonly deviceId: string;
  readonly sessionId: string;
  readonly permissions: string[];
}

export interface SkillResult {
  readonly success: boolean;
  readonly data?: unknown;
  readonly error?: string;
  readonly metadata?: Record<string, unknown>;
}

export interface ValidationResult {
  readonly valid: boolean;
  readonly errors: string[];
}