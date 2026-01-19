/**
 * Production-Grade Event Emitter Base Class
 * 
 * Eliminates duplicated callback management across all subsystems.
 * Provides thread-safe event handling, memory leak prevention, and comprehensive debugging.
 */

import { ErrorHandler } from './ErrorHandler';

export type EventListener<T = any> = (data: T) => void | Promise<void>;
export type EventListenerWithContext<T = any> = (data: T, context: EventContext) => void | Promise<void>;

export interface EventContext {
  eventName: string;
  timestamp: number;
  source: string;
  sequence: number;
  metadata?: Record<string, unknown>;
}

export interface EventEmitterConfig {
  maxListeners: number;
  enableLogging: boolean;
  enableMetrics: boolean;
  enableAsyncHandling: boolean;
  errorHandler?: ErrorHandler;
  memoryLeakWarningThreshold: number;
}

export interface EventMetrics {
  totalEvents: number;
  totalListeners: number;
  eventCounts: Map<string, number>;
  listenerCounts: Map<string, number>;
  errorCounts: Map<string, number>;
  averageExecutionTime: Map<string, number>;
}

/**
 * Production-grade event emitter with comprehensive safety and monitoring
 */
export class EventEmitter {
  private readonly listeners = new Map<string, Set<EventListener>>();
  private readonly onceListeners = new Map<string, Set<EventListener>>();
  private readonly config: EventEmitterConfig;
  private readonly errorHandler: ErrorHandler;
  private readonly metrics: EventMetrics;
  private eventSequence = 0;
  private readonly source: string;

  constructor(source: string, config: Partial<EventEmitterConfig> = {}) {
    this.source = source;
    this.config = {
      maxListeners: 100,
      enableLogging: false,
      enableMetrics: true,
      enableAsyncHandling: true,
      memoryLeakWarningThreshold: 50,
      ...config
    };

    this.errorHandler = config.errorHandler || ErrorHandler.getInstance();
    this.metrics = {
      totalEvents: 0,
      totalListeners: 0,
      eventCounts: new Map(),
      listenerCounts: new Map(),
      errorCounts: new Map(),
      averageExecutionTime: new Map()
    };
  }

  /**
   * Add event listener with memory leak protection
   */
  on<T = any>(eventName: string, listener: EventListener<T>): this {
    this.validateEventName(eventName);
    this.validateListener(listener);

    if (!this.listeners.has(eventName)) {
      this.listeners.set(eventName, new Set());
    }

    const eventListeners = this.listeners.get(eventName)!;
    
    // Memory leak protection
    if (eventListeners.size >= this.config.maxListeners) {
      const warning = `Memory leak warning: Event '${eventName}' has ${eventListeners.size} listeners (max: ${this.config.maxListeners})`;
      console.warn(warning);
      
      if (eventListeners.size >= this.config.memoryLeakWarningThreshold) {
        throw new Error(`Memory leak detected: Too many listeners for event '${eventName}' (${eventListeners.size})`);
      }
    }

    eventListeners.add(listener);
    this.updateListenerMetrics(eventName, 1);

    if (this.config.enableLogging) {
      console.debug(`📡 EventEmitter[${this.source}]: Added listener for '${eventName}' (total: ${eventListeners.size})`);
    }

    return this;
  }

  /**
   * Add one-time event listener
   */
  once<T = any>(eventName: string, listener: EventListener<T>): this {
    this.validateEventName(eventName);
    this.validateListener(listener);

    if (!this.onceListeners.has(eventName)) {
      this.onceListeners.set(eventName, new Set());
    }

    this.onceListeners.get(eventName)!.add(listener);
    this.updateListenerMetrics(eventName, 1);

    if (this.config.enableLogging) {
      console.debug(`📡 EventEmitter[${this.source}]: Added once-listener for '${eventName}'`);
    }

    return this;
  }

  /**
   * Remove specific event listener
   */
  off<T = any>(eventName: string, listener: EventListener<T>): this {
    this.validateEventName(eventName);

    // Remove from regular listeners
    const eventListeners = this.listeners.get(eventName);
    if (eventListeners && eventListeners.has(listener)) {
      eventListeners.delete(listener);
      this.updateListenerMetrics(eventName, -1);
      
      if (eventListeners.size === 0) {
        this.listeners.delete(eventName);
      }
    }

    // Remove from once listeners
    const onceListeners = this.onceListeners.get(eventName);
    if (onceListeners && onceListeners.has(listener)) {
      onceListeners.delete(listener);
      this.updateListenerMetrics(eventName, -1);
      
      if (onceListeners.size === 0) {
        this.onceListeners.delete(eventName);
      }
    }

    if (this.config.enableLogging) {
      console.debug(`📡 EventEmitter[${this.source}]: Removed listener for '${eventName}'`);
    }

    return this;
  }

  /**
   * Remove all listeners for an event
   */
  removeAllListeners(eventName?: string): this {
    if (eventName) {
      this.validateEventName(eventName);
      
      const regularCount = this.listeners.get(eventName)?.size || 0;
      const onceCount = this.onceListeners.get(eventName)?.size || 0;
      
      this.listeners.delete(eventName);
      this.onceListeners.delete(eventName);
      this.updateListenerMetrics(eventName, -(regularCount + onceCount));
      
      if (this.config.enableLogging) {
        console.debug(`📡 EventEmitter[${this.source}]: Removed all listeners for '${eventName}' (${regularCount + onceCount} total)`);
      }
    } else {
      // Remove all listeners for all events
      const totalRemoved = Array.from(this.listeners.values()).reduce((sum, set) => sum + set.size, 0) +
                          Array.from(this.onceListeners.values()).reduce((sum, set) => sum + set.size, 0);
      
      this.listeners.clear();
      this.onceListeners.clear();
      this.metrics.totalListeners = 0;
      this.metrics.listenerCounts.clear();
      
      if (this.config.enableLogging) {
        console.debug(`📡 EventEmitter[${this.source}]: Removed all listeners (${totalRemoved} total)`);
      }
    }

    return this;
  }

  /**
   * Emit event to all listeners with comprehensive error handling
   */
  async emit<T = any>(eventName: string, data: T, metadata?: Record<string, unknown>): Promise<boolean> {
    this.validateEventName(eventName);

    const context: EventContext = {
      eventName,
      timestamp: Date.now(),
      source: this.source,
      sequence: ++this.eventSequence,
      metadata
    };

    const startTime = Date.now();
    let listenersExecuted = 0;
    let errorsEncountered = 0;

    try {
      // Execute regular listeners
      const eventListeners = this.listeners.get(eventName);
      if (eventListeners && eventListeners.size > 0) {
        await this.executeListeners(Array.from(eventListeners), data, context);
        listenersExecuted += eventListeners.size;
      }

      // Execute once listeners and remove them
      const onceListeners = this.onceListeners.get(eventName);
      if (onceListeners && onceListeners.size > 0) {
        await this.executeListeners(Array.from(onceListeners), data, context);
        listenersExecuted += onceListeners.size;
        
        // Remove once listeners after execution
        this.updateListenerMetrics(eventName, -onceListeners.size);
        this.onceListeners.delete(eventName);
      }

      // Update metrics
      if (this.config.enableMetrics) {
        this.updateEventMetrics(eventName, Date.now() - startTime);
      }

      if (this.config.enableLogging && listenersExecuted > 0) {
        console.debug(`📡 EventEmitter[${this.source}]: Emitted '${eventName}' to ${listenersExecuted} listeners (${Date.now() - startTime}ms)`);
      }

      return listenersExecuted > 0;

    } catch (error) {
      errorsEncountered++;
      this.updateErrorMetrics(eventName);
      
      const errorContext = this.errorHandler.createContext('emit', 'EventEmitter', {
        additionalData: { eventName, listenersExecuted, errorsEncountered }
      });
      
      this.errorHandler.handleError(error, errorContext);
      return false;
    }
  }

  /**
   * Synchronous emit for performance-critical paths
   */
  emitSync<T = any>(eventName: string, data: T, metadata?: Record<string, unknown>): boolean {
    this.validateEventName(eventName);

    const context: EventContext = {
      eventName,
      timestamp: Date.now(),
      source: this.source,
      sequence: ++this.eventSequence,
      metadata
    };

    const startTime = Date.now();
    let listenersExecuted = 0;

    try {
      // Execute regular listeners synchronously
      const eventListeners = this.listeners.get(eventName);
      if (eventListeners && eventListeners.size > 0) {
        for (const listener of eventListeners) {
          try {
            listener(data);
            listenersExecuted++;
          } catch (error) {
            this.updateErrorMetrics(eventName);
            console.error(`EventEmitter[${this.source}]: Listener error for '${eventName}':`, error);
          }
        }
      }

      // Execute once listeners synchronously and remove them
      const onceListeners = this.onceListeners.get(eventName);
      if (onceListeners && onceListeners.size > 0) {
        for (const listener of onceListeners) {
          try {
            listener(data);
            listenersExecuted++;
          } catch (error) {
            this.updateErrorMetrics(eventName);
            console.error(`EventEmitter[${this.source}]: Once-listener error for '${eventName}':`, error);
          }
        }
        
        // Remove once listeners after execution
        this.updateListenerMetrics(eventName, -onceListeners.size);
        this.onceListeners.delete(eventName);
      }

      // Update metrics
      if (this.config.enableMetrics) {
        this.updateEventMetrics(eventName, Date.now() - startTime);
      }

      return listenersExecuted > 0;

    } catch (error) {
      this.updateErrorMetrics(eventName);
      console.error(`EventEmitter[${this.source}]: Critical error during sync emit for '${eventName}':`, error);
      return false;
    }
  }

  /**
   * Get listener count for an event
   */
  listenerCount(eventName: string): number {
    this.validateEventName(eventName);
    
    const regularCount = this.listeners.get(eventName)?.size || 0;
    const onceCount = this.onceListeners.get(eventName)?.size || 0;
    
    return regularCount + onceCount;
  }

  /**
   * Get all event names that have listeners
   */
  eventNames(): string[] {
    const names = new Set<string>();
    
    for (const name of this.listeners.keys()) {
      names.add(name);
    }
    
    for (const name of this.onceListeners.keys()) {
      names.add(name);
    }
    
    return Array.from(names).sort();
  }

  /**
   * Get comprehensive event metrics
   */
  getMetrics(): EventMetrics {
    return {
      totalEvents: this.metrics.totalEvents,
      totalListeners: this.metrics.totalListeners,
      eventCounts: new Map(this.metrics.eventCounts),
      listenerCounts: new Map(this.metrics.listenerCounts),
      errorCounts: new Map(this.metrics.errorCounts),
      averageExecutionTime: new Map(this.metrics.averageExecutionTime)
    };
  }

  /**
   * Reset all metrics (for testing)
   */
  resetMetrics(): void {
    this.metrics.totalEvents = 0;
    this.metrics.totalListeners = 0;
    this.metrics.eventCounts.clear();
    this.metrics.listenerCounts.clear();
    this.metrics.errorCounts.clear();
    this.metrics.averageExecutionTime.clear();
    this.eventSequence = 0;
  }

  /**
   * Cleanup all listeners and reset state
   */
  cleanup(): void {
    this.removeAllListeners();
    this.resetMetrics();
    
    if (this.config.enableLogging) {
      console.debug(`📡 EventEmitter[${this.source}]: Cleaned up all listeners and metrics`);
    }
  }

  // Private helper methods
  private validateEventName(eventName: string): void {
    if (!eventName || typeof eventName !== 'string') {
      throw new Error('Event name must be a non-empty string');
    }
  }

  private validateListener(listener: EventListener): void {
    if (typeof listener !== 'function') {
      throw new Error('Event listener must be a function');
    }
  }

  private async executeListeners<T>(
    listeners: EventListener<T>[],
    data: T,
    context: EventContext
  ): Promise<void> {
    if (this.config.enableAsyncHandling) {
      // Execute listeners in parallel for better performance
      const promises = listeners.map(async (listener) => {
        try {
          const result = listener(data);
          if (result instanceof Promise) {
            await result;
          }
        } catch (error) {
          this.updateErrorMetrics(context.eventName);
          console.error(`EventEmitter[${this.source}]: Listener error for '${context.eventName}':`, error);
        }
      });
      
      await Promise.all(promises);
    } else {
      // Execute listeners sequentially
      for (const listener of listeners) {
        try {
          const result = listener(data);
          if (result instanceof Promise) {
            await result;
          }
        } catch (error) {
          this.updateErrorMetrics(context.eventName);
          console.error(`EventEmitter[${this.source}]: Listener error for '${context.eventName}':`, error);
        }
      }
    }
  }

  private updateEventMetrics(eventName: string, executionTime: number): void {
    this.metrics.totalEvents++;
    
    const currentCount = this.metrics.eventCounts.get(eventName) || 0;
    this.metrics.eventCounts.set(eventName, currentCount + 1);
    
    const currentAvg = this.metrics.averageExecutionTime.get(eventName) || 0;
    const newAvg = (currentAvg * currentCount + executionTime) / (currentCount + 1);
    this.metrics.averageExecutionTime.set(eventName, newAvg);
  }

  private updateListenerMetrics(eventName: string, delta: number): void {
    this.metrics.totalListeners += delta;
    
    const currentCount = this.metrics.listenerCounts.get(eventName) || 0;
    const newCount = Math.max(0, currentCount + delta);
    
    if (newCount === 0) {
      this.metrics.listenerCounts.delete(eventName);
    } else {
      this.metrics.listenerCounts.set(eventName, newCount);
    }
  }

  private updateErrorMetrics(eventName: string): void {
    const currentCount = this.metrics.errorCounts.get(eventName) || 0;
    this.metrics.errorCounts.set(eventName, currentCount + 1);
  }
}

/**
 * Specialized event emitter for avatar subsystems
 */
export class AvatarEventEmitter extends EventEmitter {
  constructor(subsystemName: string, config?: Partial<EventEmitterConfig>) {
    super(`Avatar.${subsystemName}`, {
      maxListeners: 50,
      enableLogging: false,
      enableMetrics: true,
      enableAsyncHandling: true,
      ...config
    });
  }

  /**
   * Emit identity change event with standardized data structure
   */
  emitIdentityChanged(identityId: string, changes: any[], newIdentity: any): Promise<boolean> {
    return this.emit('identityChanged', {
      identityId,
      changes,
      newIdentity,
      timestamp: Date.now()
    });
  }

  /**
   * Emit sync completed event with standardized data structure
   */
  emitSyncCompleted(identityId: string, success: boolean, platforms: string[], errors?: string[]): Promise<boolean> {
    return this.emit('syncCompleted', {
      identityId,
      success,
      platforms,
      errors,
      timestamp: Date.now()
    });
  }

  /**
   * Emit asset loading progress with standardized data structure
   */
  emitAssetLoadingProgress(identityId: string, platform: string, progress: any): Promise<boolean> {
    return this.emit('assetLoadingProgress', {
      identityId,
      platform,
      progress,
      timestamp: Date.now()
    });
  }
}

/**
 * Factory function for creating avatar event emitters
 */
export function createAvatarEventEmitter(
  subsystemName: string,
  config?: Partial<EventEmitterConfig>
): AvatarEventEmitter {
  return new AvatarEventEmitter(subsystemName, config);
}