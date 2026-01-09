/**
 * @fileoverview Monitoring and observability utilities
 */

export interface MetricsCollector {
  recordMetric(name: string, value: number, tags?: Record<string, string>): void;
  recordCounter(name: string, increment?: number, tags?: Record<string, string>): void;
  recordGauge(name: string, value: number, tags?: Record<string, string>): void;
  recordHistogram(name: string, value: number, tags?: Record<string, string>): void;
}

export interface Logger {
  debug(message: string, context?: Record<string, unknown>): void;
  info(message: string, context?: Record<string, unknown>): void;
  warn(message: string, context?: Record<string, unknown>): void;
  error(message: string, error?: Error, context?: Record<string, unknown>): void;
}

export class ConsoleLogger implements Logger {
  debug(message: string, context?: Record<string, unknown>): void {
    console.debug(`[DEBUG] ${message}`, context ? JSON.stringify(context) : '');
  }
  
  info(message: string, context?: Record<string, unknown>): void {
    console.info(`[INFO] ${message}`, context ? JSON.stringify(context) : '');
  }
  
  warn(message: string, context?: Record<string, unknown>): void {
    console.warn(`[WARN] ${message}`, context ? JSON.stringify(context) : '');
  }
  
  error(message: string, error?: Error, context?: Record<string, unknown>): void {
    console.error(`[ERROR] ${message}`, error?.stack || '', context ? JSON.stringify(context) : '');
  }
}

export class InMemoryMetricsCollector implements MetricsCollector {
  private metrics = new Map<string, { value: number; timestamp: number; tags?: Record<string, string> }[]>();
  
  recordMetric(name: string, value: number, tags?: Record<string, string>): void {
    if (!this.metrics.has(name)) {
      this.metrics.set(name, []);
    }
    this.metrics.get(name)!.push({ 
      value, 
      timestamp: Date.now(), 
      ...(tags && { tags })
    });
  }
  
  recordCounter(name: string, increment: number = 1, tags?: Record<string, string>): void {
    this.recordMetric(name, increment, tags);
  }
  
  recordGauge(name: string, value: number, tags?: Record<string, string>): void {
    this.recordMetric(name, value, tags);
  }
  
  recordHistogram(name: string, value: number, tags?: Record<string, string>): void {
    this.recordMetric(name, value, tags);
  }
  
  getMetrics(name: string): { value: number; timestamp: number; tags?: Record<string, string> }[] {
    return this.metrics.get(name) ?? [];
  }
  
  getAllMetrics(): Map<string, { value: number; timestamp: number; tags?: Record<string, string> }[]> {
    return new Map(this.metrics);
  }
}