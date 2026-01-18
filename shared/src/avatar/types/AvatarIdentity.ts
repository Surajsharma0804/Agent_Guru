/**
 * Avatar identity and customization data models
 */

import { 
  Gender, 
  VoiceStyle, 
  PersonalityTone, 
  VoicePersonality, 
  ExpressivenessLevel, 
  GestureIntensity,
  ColorValue,
  DigitalSignature,
  EncryptionMetadata,
  Platform
} from './Common';

/**
 * Complete avatar identity configuration
 */
export interface AvatarIdentity {
  id: string;
  version: string;
  created: Date;
  lastModified: Date;
  
  // Visual Configuration
  appearance: AvatarAppearance;
  
  // Personality Configuration
  personality: AvatarPersonality;
  
  // Platform Assets
  assets: Record<Platform, PlatformAssetSet>;
  
  // Privacy & Security
  encryption: EncryptionMetadata;
  signature: DigitalSignature;
  
  // User Preferences
  preferences: UserPreferences;
}

/**
 * Avatar visual appearance configuration
 */
export interface AvatarAppearance {
  gender: Gender;
  facialFeatures: FacialFeatureSet;
  skinTone: ColorValue;
  hairStyle: HairStyleConfig;
  eyeColor: ColorValue;
  bodyType?: BodyTypeConfig;
  accessories?: AccessoryConfig[];
}

/**
 * Facial feature morphing weights
 */
export interface FacialFeatureSet {
  faceShape: MorphTargetWeights;
  eyeShape: MorphTargetWeights;
  noseShape: MorphTargetWeights;
  mouthShape: MorphTargetWeights;
  jawline: MorphTargetWeights;
  cheekbones: MorphTargetWeights;
  eyebrows: MorphTargetWeights;
}

/**
 * Morph target weights for facial customization
 */
export interface MorphTargetWeights {
  [targetName: string]: number; // -1.0 to 1.0
}

/**
 * Hair style configuration
 */
export interface HairStyleConfig {
  style: string; // Asset reference
  color: ColorValue;
  length: 'short' | 'medium' | 'long';
  texture: 'straight' | 'wavy' | 'curly';
}

/**
 * Body type configuration for full-body avatars
 */
export interface BodyTypeConfig {
  height: number; // 0.0 to 1.0 (relative)
  build: 'slim' | 'average' | 'athletic' | 'heavy';
  proportions: MorphTargetWeights;
}

/**
 * Accessory configuration
 */
export interface AccessoryConfig {
  type: 'glasses' | 'hat' | 'jewelry' | 'clothing';
  assetId: string;
  color?: ColorValue;
  visible: boolean;
}

/**
 * Avatar personality and behavior configuration
 */
export interface AvatarPersonality {
  voiceStyle: VoiceStyle;
  tone: PersonalityTone;
  accent?: AccentConfig;
  expressiveness: EmotionalRange;
  gestureStyle: GestureProfile;
  voicePersonality: VoicePersonality;
}

/**
 * Accent configuration for voice synthesis
 */
export interface AccentConfig {
  region: string; // e.g., 'us-west', 'uk-london', 'au-sydney'
  intensity: number; // 0.0 to 1.0
}

/**
 * Emotional responsiveness configuration
 */
export interface EmotionalRange {
  intensity: number; // 0.0 to 1.0
  responsiveness: number; // 0.0 to 1.0
  stability: number; // 0.0 to 1.0
  userOverride: boolean;
  expressiveness: ExpressivenessLevel;
}

/**
 * Gesture behavior profile
 */
export interface GestureProfile {
  intensity: GestureIntensity;
  frequency: number; // gestures per minute
  variety: number; // 0.0 to 1.0
  contextSensitivity: number; // 0.0 to 1.0
  culturalStyle?: string;
}

/**
 * Platform-specific asset set
 */
export interface PlatformAssetSet {
  platform: Platform;
  version: string;
  meshes: MeshAssetCollection;
  textures: TextureAssetCollection;
  animations: AnimationAssetCollection;
  shaders: ShaderAssetCollection;
  metadata: AssetMetadata;
}

/**
 * Mesh asset collection
 */
export interface MeshAssetCollection {
  head: MeshAsset;
  body?: MeshAsset;
  hair: MeshAsset;
  accessories?: MeshAsset[];
  morphTargets: MorphTargetAsset[];
}

/**
 * Individual mesh asset
 */
export interface MeshAsset {
  id: string;
  format: 'gltf' | 'usdz' | 'fbx' | 'obj';
  lodLevels: LODLevel[];
  vertexCount: number;
  triangleCount: number;
  boundingBox: import('./Common').BoundingBox;
  url: string;
  checksum: string;
  size: number; // bytes
}

/**
 * Level of detail configuration
 */
export interface LODLevel {
  level: number; // 0 = highest quality
  distance: number; // rendering distance threshold
  vertexReduction: number; // percentage reduction
  textureReduction: number; // percentage reduction
  featureDisabling: string[]; // features to disable at this LOD
}

/**
 * Morph target asset for facial animation
 */
export interface MorphTargetAsset {
  name: string;
  category: 'expression' | 'viseme' | 'custom';
  vertexDeltas: Float32Array;
  weight: number; // default weight
}

/**
 * Texture asset collection
 */
export interface TextureAssetCollection {
  diffuse: TextureAsset[];
  normal: TextureAsset[];
  specular: TextureAsset[];
  emission?: TextureAsset[];
  roughness?: TextureAsset[];
  metallic?: TextureAsset[];
  occlusion?: TextureAsset[];
}

/**
 * Individual texture asset
 */
export interface TextureAsset {
  id: string;
  type: 'diffuse' | 'normal' | 'specular' | 'emission' | 'roughness' | 'metallic' | 'occlusion';
  format: 'png' | 'jpg' | 'webp' | 'ktx2' | 'dds';
  resolution: number; // width (assuming square)
  mipmaps: boolean;
  compression: string;
  url: string;
  checksum: string;
  size: number; // bytes
}

/**
 * Animation asset collection
 */
export interface AnimationAssetCollection {
  idle: AnimationAsset[];
  expressions: AnimationAsset[];
  gestures: AnimationAsset[];
  transitions: AnimationAsset[];
  breathing: AnimationAsset;
  blinking: AnimationAsset;
}

/**
 * Individual animation asset
 */
export interface AnimationAsset {
  id: string;
  name: string;
  duration: number; // seconds
  fps: number;
  looping: boolean;
  blendable: boolean;
  priority: number;
  tags: string[];
  keyframes: AnimationKeyframe[];
}

/**
 * Animation keyframe data
 */
export interface AnimationKeyframe {
  time: number; // seconds
  transforms: Record<string, Transform>;
  morphWeights?: Record<string, number>;
}

/**
 * 3D transform data
 */
export interface Transform {
  position: import('./Common').Vector3;
  rotation: import('./Common').Vector3; // euler angles
  scale: import('./Common').Vector3;
}

/**
 * Shader asset collection
 */
export interface ShaderAssetCollection {
  vertex: ShaderAsset[];
  fragment: ShaderAsset[];
  compute?: ShaderAsset[];
}

/**
 * Individual shader asset
 */
export interface ShaderAsset {
  id: string;
  type: 'vertex' | 'fragment' | 'compute';
  version: string; // shader language version
  source: string;
  uniforms: ShaderUniform[];
  attributes: ShaderAttribute[];
}

/**
 * Shader uniform definition
 */
export interface ShaderUniform {
  name: string;
  type: 'float' | 'vec2' | 'vec3' | 'vec4' | 'mat3' | 'mat4' | 'sampler2D';
  defaultValue?: unknown;
}

/**
 * Shader attribute definition
 */
export interface ShaderAttribute {
  name: string;
  type: 'float' | 'vec2' | 'vec3' | 'vec4';
  location: number;
}

/**
 * Asset metadata for integrity and versioning
 */
export interface AssetMetadata {
  version: string;
  created: Date;
  lastModified: Date;
  totalSize: number; // bytes
  assetCount: number;
  signature: DigitalSignature;
  dependencies: string[];
  compatibility: string[];
}

/**
 * User preferences for avatar behavior
 */
export interface UserPreferences {
  minimalMode: boolean;
  privacyLevel: 'strict' | 'balanced' | 'permissive';
  performanceMode: 'quality' | 'balanced' | 'performance';
  accessibilityOptions: AccessibilityOptions;
  culturalPreferences: CulturalPreferences;
}

/**
 * Accessibility configuration
 */
export interface AccessibilityOptions {
  reducedMotion: boolean;
  highContrast: boolean;
  largerText: boolean;
  audioDescriptions: boolean;
  subtitles: boolean;
  colorBlindSupport: boolean;
}

/**
 * Cultural preferences for appropriate behavior
 */
export interface CulturalPreferences {
  gestureStyle: string; // e.g., 'western', 'eastern', 'neutral'
  eyeContactLevel: number; // 0.0 to 1.0
  personalSpace: number; // virtual distance preference
  formalityLevel: number; // 0.0 to 1.0
}

/**
 * Avatar identity configuration for initial setup
 */
export interface AvatarIdentityConfig {
  gender: Gender;
  voiceStyle: VoiceStyle;
  personalityTone: PersonalityTone;
  accent?: string;
  facialFeatures?: Partial<FacialFeatureSet>;
  expressiveness: ExpressivenessLevel;
  gestureIntensity: GestureIntensity;
  voicePersonality: VoicePersonality;
  minimalMode: boolean;
  customizations?: Partial<AvatarAppearance>;
}