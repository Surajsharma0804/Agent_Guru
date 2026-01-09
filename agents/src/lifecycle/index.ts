/**
 * @fileoverview Agent lifecycle management
 */

import { Agent } from '../interfaces/index.js';

export interface AgentLifecycleManager {
  startAgent(agentId: string): Promise<void>;
  stopAgent(agentId: string): Promise<void>;
  restartAgent(agentId: string): Promise<void>;
  getAgentStatus(agentId: string): AgentStatus;
}

export type AgentStatus = 'stopped' | 'starting' | 'running' | 'stopping' | 'error';

export class DefaultLifecycleManager implements AgentLifecycleManager {
  private agents = new Map<string, Agent>();
  private statuses = new Map<string, AgentStatus>();
  
  registerAgent(agent: Agent): void {
    this.agents.set(agent.id, agent);
    this.statuses.set(agent.id, 'stopped');
  }
  
  async startAgent(agentId: string): Promise<void> {
    const agent = this.agents.get(agentId);
    if (!agent) {
      throw new Error(`Agent '${agentId}' not found`);
    }
    
    const currentStatus = this.statuses.get(agentId);
    if (currentStatus === 'running' || currentStatus === 'starting') {
      return;
    }
    
    this.statuses.set(agentId, 'starting');
    
    try {
      await agent.start();
      this.statuses.set(agentId, 'running');
    } catch (error) {
      this.statuses.set(agentId, 'error');
      throw error;
    }
  }
  
  async stopAgent(agentId: string): Promise<void> {
    const agent = this.agents.get(agentId);
    if (!agent) {
      throw new Error(`Agent '${agentId}' not found`);
    }
    
    const currentStatus = this.statuses.get(agentId);
    if (currentStatus === 'stopped' || currentStatus === 'stopping') {
      return;
    }
    
    this.statuses.set(agentId, 'stopping');
    
    try {
      await agent.stop();
      this.statuses.set(agentId, 'stopped');
    } catch (error) {
      this.statuses.set(agentId, 'error');
      throw error;
    }
  }
  
  async restartAgent(agentId: string): Promise<void> {
    await this.stopAgent(agentId);
    await this.startAgent(agentId);
  }
  
  getAgentStatus(agentId: string): AgentStatus {
    return this.statuses.get(agentId) ?? 'stopped';
  }
}