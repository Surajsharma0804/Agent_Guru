/**
 * @fileoverview Agent coordination and messaging
 */

import { Agent, AgentMessage, AgentResponse } from '../interfaces/index.js';

export class AgentCoordinator {
  private agents = new Map<string, Agent>();
  
  registerAgent(agent: Agent): void {
    if (this.agents.has(agent.id)) {
      throw new Error(`Agent with id '${agent.id}' is already registered`);
    }
    this.agents.set(agent.id, agent);
  }
  
  unregisterAgent(agentId: string): boolean {
    const agent = this.agents.get(agentId);
    if (agent) {
      // Stop the agent if it's running
      agent.stop().catch(console.error);
      return this.agents.delete(agentId);
    }
    return false;
  }
  
  async routeMessage(message: AgentMessage): Promise<AgentResponse | null> {
    const recipient = this.agents.get(message.recipientId);
    if (!recipient) {
      return {
        messageId: message.id,
        success: false,
        error: `Recipient agent '${message.recipientId}' not found`,
      };
    }
    
    try {
      return await recipient.handleMessage(message);
    } catch (error) {
      return {
        messageId: message.id,
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }
  
  async broadcastMessage(message: Omit<AgentMessage, 'recipientId'>): Promise<AgentResponse[]> {
    const responses: AgentResponse[] = [];
    
    for (const [agentId, agent] of this.agents) {
      if (agentId !== message.senderId) {
        const fullMessage: AgentMessage = {
          ...message,
          recipientId: agentId,
        };
        
        try {
          const response = await agent.handleMessage(fullMessage);
          responses.push(response);
        } catch (error) {
          responses.push({
            messageId: message.id,
            success: false,
            error: error instanceof Error ? error.message : 'Unknown error',
          });
        }
      }
    }
    
    return responses;
  }
  
  listAgents(): Agent[] {
    return Array.from(this.agents.values());
  }
  
  getAgent(agentId: string): Agent | null {
    return this.agents.get(agentId) ?? null;
  }
}