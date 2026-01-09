/**
 * @fileoverview Agent system interfaces
 */

export interface Agent {
  readonly id: string;
  readonly type: AgentType;
  readonly capabilities: AgentCapabilities;
  
  start(): Promise<void>;
  stop(): Promise<void>;
  sendMessage(message: AgentMessage): Promise<void>;
  handleMessage(message: AgentMessage): Promise<AgentResponse>;
}

export type AgentType = 'desktop' | 'mobile' | 'server' | 'coordinator';

export interface AgentCapabilities {
  readonly canExecuteCommands: boolean;
  readonly canAccessFiles: boolean;
  readonly canAccessNetwork: boolean;
  readonly canManageDevices: boolean;
}

export interface AgentMessage {
  readonly id: string;
  readonly senderId: string;
  readonly recipientId: string;
  readonly type: MessageType;
  readonly payload: unknown;
  readonly timestamp: number;
}

export type MessageType = 'command' | 'response' | 'notification' | 'heartbeat';

export interface AgentResponse {
  readonly messageId: string;
  readonly success: boolean;
  readonly data?: unknown;
  readonly error?: string;
}