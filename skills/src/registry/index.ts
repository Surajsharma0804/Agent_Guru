/**
 * @fileoverview Skill registry and management
 */

import { Skill } from '../interfaces/index.js';

export class SkillRegistry {
  private skills = new Map<string, Skill>();
  
  register(skill: Skill): void {
    if (this.skills.has(skill.id)) {
      throw new Error(`Skill with id '${skill.id}' is already registered`);
    }
    this.skills.set(skill.id, skill);
  }
  
  unregister(skillId: string): boolean {
    return this.skills.delete(skillId);
  }
  
  get(skillId: string): Skill | null {
    return this.skills.get(skillId) ?? null;
  }
  
  list(): Skill[] {
    return Array.from(this.skills.values());
  }
  
  listByCapability(capability: keyof Skill['capabilities']): Skill[] {
    return this.list().filter(skill => skill.capabilities[capability]);
  }
  
  clear(): void {
    this.skills.clear();
  }
}