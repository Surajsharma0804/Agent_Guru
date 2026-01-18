/**
 * GURU Humanized Avatar System
 * 
 * A production-grade, real-time digital human interface that creates emotionally responsive,
 * naturally animated avatars across Windows, macOS, Android, iOS, and Web platforms.
 * 
 * This module provides the core interfaces and types for the avatar system, designed for
 * cross-platform consistency, privacy-first processing, and performance optimization.
 */

// Core System Interfaces
export type { IdentityManager, IdentityManagerFactory } from './interfaces/IdentityManager';
export type { EmotionEngine, EmotionEngineFactory } from './interfaces/EmotionEngine';
export type { MotionSystem, MotionSystemFactory } from './interfaces/MotionSystem';
export type { LipSyncEngine, LipSyncEngineFactory } from './interfaces/LipSyncEngine';
export type { PlatformRenderer, PlatformRendererFactory } from './interfaces/PlatformRenderer';

// All Types - Re-export from types index
export * from './types';

// All Constants - Re-export from constants index
export * from './constants';

// Implementations - Re-export from implementations index
export * from './implementations';