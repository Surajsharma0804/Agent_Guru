/**
 * @fileoverview Skill execution engine
 */

import { SkillContext, SkillResult } from '../interfaces/index.js';
import { SkillRegistry } from '../registry/index.js';

export class SkillExecutor {
  constructor(private readonly registry: SkillRegistry) {}
  
  async execute(
    skillId: string,
    context: SkillContext,
    parameters: Record<string, unknown>
  ): Promise<SkillResult> {
    const skill = this.registry.get(skillId);
    if (!skill) {
      return {
        success: false,
        error: `Skill '${skillId}' not found`,
      };
    }
    
    // Validate parameters
    const validation = await skill.validate(parameters);
    if (!validation.valid) {
      return {
        success: false,
        error: `Parameter validation failed: ${validation.errors.join(', ')}`,
      };
    }
    
    // Check permissions
    if (skill.capabilities.requiresAuth && !this.hasAuthPermission(context)) {
      return {
        success: false,
        error: 'Authentication required for this skill',
      };
    }
    
    try {
      return await skill.execute(context, parameters);
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }
  
  private hasAuthPermission(context: SkillContext): boolean {
    return context.permissions.includes('authenticated');
  }
}