/**
 * Performance targets and thresholds for avatar system
 */

import { Platform } from '../types/Common';

/**
 * Frame rate targets by platform
 */
export const FPS_TARGETS = {
  DESKTOP: {
    MINIMUM: 60,
    TARGET: 90,
    MAXIMUM: 120
  },
  MOBILE: {
    MINIMUM: 30,
    TARGET: 60,
    MAXIMUM: 90
  },
  WEB: {
    MINIMUM: 30,
    TARGET: 60,
    MAXIMUM: 60
  }
} as const;

/**
 * Memory usage limits by platform (in bytes)
 */
export const MEMORY_LIMITS = {
  DESKTOP: {
    MINIMUM: 200 * 1024 * 1024, // 200MB
    TARGET: 300 * 1024 * 1024,  // 300MB
    MAXIMUM: 500 * 1024 * 1024  // 500MB
  },
  MOBILE: {
    MINIMUM: 100 * 1024 * 1024, // 100MB
    TARGET: 150 * 1024 * 1024,  // 150MB
    MAXIMUM: 200 * 1024 * 1024  // 200MB
  },
  WEB: {
    MINIMUM: 75 * 1024 * 1024,  // 75MB
    TARGET: 100 * 1024 * 1024,  // 100MB
    MAXIMUM: 150 * 1024 * 1024  // 150MB
  }
} as const;

/**
 * CPU usage limits (percentage)
 */
export const CPU_USAGE_LIMITS = {
  DESKTOP: {
    IDLE: 2,      // 2%
    ACTIVE: 15,   // 15%
    MAXIMUM: 25   // 25%
  },
  MOBILE: {
    IDLE: 3,      // 3%
    ACTIVE: 20,   // 20%
    MAXIMUM: 30   // 30%
  },
  WEB: {
    IDLE: 5,      // 5%
    ACTIVE: 25,   // 25%
    MAXIMUM: 35   // 35%
  }
} as const;

/**
 * GPU usage limits (percentage)
 */
export const GPU_USAGE_LIMITS = {
  DESKTOP: {
    IDLE: 5,      // 5%
    ACTIVE: 30,   // 30%
    MAXIMUM: 50   // 50%
  },
  MOBILE: {
    IDLE: 3,      // 3%
    ACTIVE: 25,   // 25%
    MAXIMUM: 40   // 40%
  },
  WEB: {
    IDLE: 2,      // 2%
    ACTIVE: 20,   // 20%
    MAXIMUM: 30   // 30%
  }
} as const;

/**
 * Startup time targets (milliseconds)
 */
export const STARTUP_TIME_TARGETS = {
  COLD_START: {
    DESKTOP: 2000,  // 2 seconds
    MOBILE: 3000,   // 3 seconds
    WEB: 2000       // 2 seconds
  },
  WARM_START: {
    DESKTOP: 500,   // 0.5 seconds
    MOBILE: 1000,   // 1 second
    WEB: 800        // 0.8 seconds
  },
  HOT_START: {
    DESKTOP: 100,   // 0.1 seconds
    MOBILE: 200,    // 0.2 seconds
    WEB: 150        // 0.15 seconds
  }
} as const;

/**
 * Battery drain limits for mobile platforms (percentage per hour)
 */
export const BATTERY_DRAIN_LIMITS = {
  IDLE: 1,        // 1% per hour
  ACTIVE: 5,      // 5% per hour
  MAXIMUM: 10     // 10% per hour
} as const;

/**
 * Thermal impact limits (temperature increase in Celsius)
 */
export const THERMAL_LIMITS = {
  DESKTOP: {
    IDLE: 2,      // 2°C
    ACTIVE: 5,    // 5°C
    MAXIMUM: 10   // 10°C
  },
  MOBILE: {
    IDLE: 1,      // 1°C
    ACTIVE: 3,    // 3°C
    MAXIMUM: 5    // 5°C
  }
} as const;

/**
 * Network usage limits (bytes per hour)
 */
export const NETWORK_USAGE_LIMITS = {
  ASSET_LOADING: {
    INITIAL: 50 * 1024 * 1024,    // 50MB initial load
    STREAMING: 10 * 1024 * 1024,  // 10MB per hour streaming
    UPDATES: 5 * 1024 * 1024      // 5MB per hour for updates
  },
  TELEMETRY: {
    BASIC: 1024 * 1024,           // 1MB per hour
    DETAILED: 5 * 1024 * 1024     // 5MB per hour
  }
} as const;

/**
 * Response time targets (milliseconds)
 */
export const RESPONSE_TIME_TARGETS = {
  API_CALLS: {
    EMOTION_CHANGE: 100,          // 100ms
    GESTURE_TRIGGER: 50,          // 50ms
    ATTENTION_CHANGE: 75,         // 75ms
    STATE_TRANSITION: 200         // 200ms
  },
  RENDERING: {
    FRAME_TIME: 16.67,            // 16.67ms (60 FPS)
    INPUT_LATENCY: 20,            // 20ms
    AUDIO_SYNC: 40                // 40ms
  },
  SYSTEM: {
    CONFIGURATION_CHANGE: 500,    // 500ms
    ASSET_LOADING: 2000,          // 2 seconds
    SYSTEM_RECOVERY: 1000         // 1 second
  }
} as const;

/**
 * Quality thresholds for performance monitoring
 */
export const QUALITY_THRESHOLDS = {
  FRAME_DROPS: {
    ACCEPTABLE: 0.01,             // 1% frame drops
    WARNING: 0.05,                // 5% frame drops
    CRITICAL: 0.10                // 10% frame drops
  },
  MEMORY_PRESSURE: {
    LOW: 0.7,                     // 70% of limit
    MEDIUM: 0.85,                 // 85% of limit
    HIGH: 0.95                    // 95% of limit
  },
  THERMAL_THROTTLING: {
    WARNING: 0.8,                 // 80% of thermal limit
    CRITICAL: 0.95                // 95% of thermal limit
  }
} as const;

/**
 * Performance monitoring intervals (milliseconds)
 */
export const MONITORING_INTERVALS = {
  REAL_TIME: 100,                 // 100ms for real-time metrics
  REGULAR: 1000,                  // 1 second for regular monitoring
  DETAILED: 5000,                 // 5 seconds for detailed analysis
  LONG_TERM: 60000               // 1 minute for long-term trends
} as const;

/**
 * Adaptive quality adjustment thresholds
 */
export const ADAPTIVE_QUALITY_THRESHOLDS = {
  UPGRADE_CONDITIONS: {
    STABLE_FPS_DURATION: 10000,   // 10 seconds of stable FPS
    MEMORY_HEADROOM: 0.2,         // 20% memory headroom
    CPU_HEADROOM: 0.3,            // 30% CPU headroom
    THERMAL_HEADROOM: 0.4         // 40% thermal headroom
  },
  DOWNGRADE_CONDITIONS: {
    FPS_DROP_THRESHOLD: 0.9,      // 90% of target FPS
    MEMORY_PRESSURE: 0.9,         // 90% of memory limit
    CPU_PRESSURE: 0.8,            // 80% of CPU limit
    THERMAL_PRESSURE: 0.8         // 80% of thermal limit
  }
} as const;

/**
 * Performance optimization strategies
 */
export const OPTIMIZATION_STRATEGIES = {
  QUALITY_REDUCTION: {
    TEXTURE_SIZE: [0.75, 0.5, 0.25],      // Reduce texture size by these factors
    MESH_COMPLEXITY: [0.8, 0.6, 0.4],     // Reduce mesh complexity
    EFFECT_QUALITY: [0.7, 0.5, 0.3],      // Reduce effect quality
    ANIMATION_FIDELITY: [0.8, 0.6, 0.4]   // Reduce animation fidelity
  },
  FEATURE_DISABLING: [
    'dynamic_lighting',
    'real_time_shadows',
    'post_processing',
    'particle_effects',
    'advanced_materials',
    'procedural_animation'
  ],
  MEMORY_OPTIMIZATION: {
    TEXTURE_COMPRESSION: true,
    MESH_COMPRESSION: true,
    ANIMATION_COMPRESSION: true,
    ASSET_STREAMING: true,
    GARBAGE_COLLECTION: true
  }
} as const;

/**
 * Platform-specific performance profiles
 */
export const PERFORMANCE_PROFILES: Record<Platform, {
  fps: { MINIMUM: number; TARGET: number; MAXIMUM: number };
  memory: { MINIMUM: number; TARGET: number; MAXIMUM: number };
  cpu: { IDLE: number; ACTIVE: number; MAXIMUM: number };
  gpu: { IDLE: number; ACTIVE: number; MAXIMUM: number };
  thermal?: { IDLE: number; ACTIVE: number; MAXIMUM: number };
  battery?: { IDLE: number; ACTIVE: number; MAXIMUM: number };
}> = {
  'windows': {
    fps: FPS_TARGETS.DESKTOP,
    memory: MEMORY_LIMITS.DESKTOP,
    cpu: CPU_USAGE_LIMITS.DESKTOP,
    gpu: GPU_USAGE_LIMITS.DESKTOP,
    thermal: THERMAL_LIMITS.DESKTOP
  },
  'macos': {
    fps: FPS_TARGETS.DESKTOP,
    memory: MEMORY_LIMITS.DESKTOP,
    cpu: CPU_USAGE_LIMITS.DESKTOP,
    gpu: GPU_USAGE_LIMITS.DESKTOP,
    thermal: THERMAL_LIMITS.DESKTOP
  },
  'android': {
    fps: FPS_TARGETS.MOBILE,
    memory: MEMORY_LIMITS.MOBILE,
    cpu: CPU_USAGE_LIMITS.MOBILE,
    gpu: GPU_USAGE_LIMITS.MOBILE,
    thermal: THERMAL_LIMITS.MOBILE,
    battery: BATTERY_DRAIN_LIMITS
  },
  'ios': {
    fps: FPS_TARGETS.MOBILE,
    memory: MEMORY_LIMITS.MOBILE,
    cpu: CPU_USAGE_LIMITS.MOBILE,
    gpu: GPU_USAGE_LIMITS.MOBILE,
    thermal: THERMAL_LIMITS.MOBILE,
    battery: BATTERY_DRAIN_LIMITS
  },
  'web': {
    fps: FPS_TARGETS.WEB,
    memory: MEMORY_LIMITS.WEB,
    cpu: CPU_USAGE_LIMITS.WEB,
    gpu: GPU_USAGE_LIMITS.WEB
  }
};

/**
 * Performance warning thresholds
 */
export const WARNING_THRESHOLDS = {
  FPS_WARNING: 0.8,               // 80% of target FPS
  FPS_CRITICAL: 0.6,              // 60% of target FPS
  MEMORY_WARNING: 0.8,            // 80% of memory limit
  MEMORY_CRITICAL: 0.95,          // 95% of memory limit
  CPU_WARNING: 0.7,               // 70% of CPU limit
  CPU_CRITICAL: 0.9,              // 90% of CPU limit
  GPU_WARNING: 0.7,               // 70% of GPU limit
  GPU_CRITICAL: 0.9,              // 90% of GPU limit
  THERMAL_WARNING: 0.7,           // 70% of thermal limit
  THERMAL_CRITICAL: 0.9,          // 90% of thermal limit
  BATTERY_WARNING: 8,             // 8% per hour
  BATTERY_CRITICAL: 12            // 12% per hour
} as const;

/**
 * Performance recovery strategies
 */
export const RECOVERY_STRATEGIES = {
  IMMEDIATE: [
    'reduce_quality',
    'disable_effects',
    'clear_caches',
    'force_garbage_collection'
  ],
  SHORT_TERM: [
    'unload_unused_assets',
    'compress_textures',
    'reduce_animation_fidelity',
    'limit_concurrent_operations'
  ],
  LONG_TERM: [
    'optimize_asset_pipeline',
    'implement_streaming',
    'profile_and_optimize',
    'update_performance_targets'
  ]
} as const;